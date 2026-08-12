#!/bin/bash
# Offline g-code validator: parse a ned subroutine with LinuxCNC's OWN
# interpreter (rs274), with NO machine, NO HAL and NO motion.
#
# Written 2026-08-03 after StartA failed three times on the machine for two
# parse faults that cost real operator time -- a helper sub defined in the
# calling file ("EOF in file ... seeking o-word"; LinuxCNC resolves subs ONE
# PER FILE via SUBROUTINE_PATH) and a comment spanning several lines inside a
# single paren ("Unclosed comment found"). Both are invisible to any text
# check and both reproduce here in about a second.
#
# Usage:  tools/gcode_check.sh <subname> [arg1 arg2 arg3]
#         tools/gcode_check.sh cal_a_zero -73.05 -1429.39 -462.00
#         tools/gcode_check.sh --all
#
# NOTE ON GUARDS: rs274 has no probe hardware, so #5070 stays 0 and every
# G38.x reports no contact. A probing cycle SHOULD therefore stop on its own
# "no contact" abort -- that is the guard proving it works, not a failure.
set -u
NED=/home/brains/Documents/ned
SUBS=$NED/configs/ned5_pb/subroutines
WORK=$(mktemp -d /tmp/gcode_check_XXXX)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/subs"
cp "$SUBS"/*.ngc "$WORK/subs/"
cat > "$WORK/test.ini" <<INI
[EMC]
VERSION = 1.1
MACHINE = gcode_check
[RS274NGC]
PARAMETER_FILE = test.var
SUBROUTINE_PATH = subs
INI
# APPEND the machine sections the subs read via #<_ini[...]> ([ATC],
# [AXIS_*]) from the real EXPANDED ini, so those lookups resolve to the
# machine's true values (2026-08-04: they were "not defined", and before
# the -v fix every #-param was 0 -- both made guards fire early and report
# "parses clean" on bodies that never parsed). The FULL expanded ini cannot
# be used: its REMAP lines crash standalone rs274.
if [ -f "$NED/configs/ned5_pb/ned5_pb.ini.expanded" ]; then
  awk '/^\[(ATC|AXIS_[A-Z])\][ \t]*$/{f=1} f && /^\[/ && !/^\[(ATC|AXIS_[A-Z])\][ \t]*$/{f=0} f' \
      "$NED/configs/ned5_pb/ned5_pb.ini.expanded" >> "$WORK/test.ini"
fi

# LINT BEFORE PARSING (2026-08-12). rs274 does catch an unclosed comment,
# but only at Cycle Start and its message names no line number -- the
# operator got "Unclosed comment found" three times on this project, twice
# in one afternoon, each time losing a run. The linter reads
# docs/gcode_rules.md's mechanical rules and prints file:line.
# NOTE: there is a SECOND lint() defined further down this file, and a shell
# function defined later WINS. Call the linter by path, never by a name that
# can be shadowed -- the first version of this hook silently did nothing for
# exactly that reason.
check() {
  local name=$1; shift
  python3 "$NED/tools/live/gcode_lint.py" \
      "$NED/configs/ned5_pb/subroutines/$name.ngc" >/tmp/gclint.$$ 2>&1 || {
    echo "$name  LINT FAILED:"; sed 's/^/    /' /tmp/gclint.$$; rm -f /tmp/gclint.$$
    return 1
  }
  rm -f /tmp/gclint.$$
  local args=""
  for a in "$@"; do args="$args [$a]"; done
  cp "$NED/configs/ned5_pb/ned5_pb.var" "$WORK/test.var"
  printf 'o<%s> call%s\nM2\n' "$name" "$args" > "$WORK/drive.ngc"
  local out
  # -v is REQUIRED: standalone rs274 IGNORES the ini's PARAMETER_FILE (found
  # 2026-08-04 -- #4107 read 0 with the var only in the ini, 1.0 with -v).
  # Without it every #-param is 0 and each sub dies on its earliest guard,
  # reporting "parses clean" for a body that never parsed.
  # HOME sandboxed: rs274 is a tool-mmap CREATOR -- it O_TRUNCs
  # $HOME/.tool.mmap before parsing options, over the LIVE table io,
  # milltask and PB share. Every scanner run against a running machine
  # truncated the live tool table (T5 "not found") and SIGBUS-crashed
  # milltask/halui (01:38 and 08:53 cores). -t would not help; only a
  # throwaway HOME does. Advisor root-cause 2026-08-06.
  out=$(cd "$WORK" && HOME="$WORK" timeout 60 rs274 -i test.ini -v test.var -g drive.ngc 2>&1)
  local fatal
  fatal=$(echo "$out" | grep -iE 'EOF in file|unclosed comment|not defined|bad character|unknown word|bad number|out of range' | head -2)
  local stop
  stop=$(echo "$out" | grep -E '^\s*\(abort,' | tail -1 | sed 's/^ *//')
  printf '%-22s %3d lines  %2d probes  ' "$name" \
    "$(echo "$out" | grep -c 'N\.\.\.\.\.')" "$(echo "$out" | grep -c 'STRAIGHT_PROBE')"
  if [ -n "$fatal" ]; then
    echo "PARSE FAULT"; echo "    $fatal"; return 1
  fi
  echo "parses clean"
  [ -n "$stop" ] && echo "    stopped on its own guard: ${stop:0:120}"
  return 0
}

# NESTED COMMENT lint (2026-08-04): rs274 -g PARSED '(a (b) c)' clean but
# the live interp aborts 'Nested comment found' -- caught on the machine
# mid-M6. Static check, every line, every file.
for f in "$WORK"/subs/*.ngc; do
  awk 'BEGIN{bad=0}
    { line=$0; sub(/;.*/,"",line)
      if (line ~ /\([^)]*\(/) { printf "  %s:%d NESTED COMMENT -> %s\n", FILENAME, NR, $0; bad=1 } }
    END{exit bad}' "$f" || FAULT=1
done
[ "${FAULT:-0}" = "1" ] && { echo "NESTED COMMENT lint FAILED"; exit 1; }

# --- static lint: the three comment/scope faults rs274 reports late or not
# --- at all, per CLAUDE.md rule 18. Cheap, so it runs over EVERY cal file.
lint() {
  python3 - "$SUBS" <<'PY'
import glob, os, sys
subs = sys.argv[1]

def scan(line):
    """Walk the line the way the interpreter does: ( opens a comment, the
    first ) closes it, and a ; is a line comment only OUTSIDE parens."""
    depth = 0
    for c in line:
        if depth == 0 and c == ';':
            return None
        if c == '(':
            if depth:
                return 'inner "(" inside a comment -- the first ")" ends it, the rest parses as code'
            depth = 1
        elif c == ')':
            if not depth:
                return 'stray ")"'
            depth = 0
    return 'unclosed comment -- a ( ... ) must open and close on ONE line' if depth else None

bad = 0
for f in sorted(glob.glob(os.path.join(subs, 'ca[l_]*.ngc'))
                + glob.glob(os.path.join(subs, 'cc_*.ngc'))):
    n = os.path.basename(f)
    for i, l in enumerate(open(f).read().split('\n'), 1):
        why = scan(l)
        if why:
            print('  LINT %s:%d %s' % (n, i, why)); bad = 1
sys.exit(bad)
PY
}

rc=0
if ! lint; then echo "LINT FAILED"; rc=1; fi
# RULES SWEEP over EVERY subroutine, not just cal_*/cc_* (docs/gcode_rules.md)
if ! python3 "$NED/tools/live/gcode_lint.py" \
        "$NED"/configs/ned5_pb/subroutines/*.ngc >/tmp/gcrules.$$ 2>&1; then
  echo "GCODE RULES: findings (docs/gcode_rules.md)"
  sed 's/^/  /' /tmp/gcrules.$$
  rc=1
fi
rm -f /tmp/gcrules.$$
if [ "${1:-}" = "--all" ]; then
  C="-73.0519 -1429.3940 -462.0033"   # a plausible puck centre; geometry is not the point
  for n in cal_probe_center cal_a_zero cal_c_ref cal_c_zero cal_c_goto \
           cal_goto_zero cal_shoulder cal_a_cycle cal_c_cycle; do
    if [ "$n" = cal_probe_center ]; then check "$n" || rc=1; else check "$n" $C || rc=1; fi
  done
else
  check "$@" || rc=1
fi
exit $rc
