#!/bin/bash
# THE ADMISSION GATE. Only a program that passes here may sit in nc_files/.
#
# GM 2026-08-19: "Only a program that has passed your linter may be in
# nc_files/. Not 'should be' -- may be." The machine runs what is in
# PROGRAM_PREFIX, so if only this script can put a file there, only checked
# programs can run. CLAUDE.md rule 21 is the standard it is built to: a
# separate check I have to remember is not a check -- the gate IS the write.
#
#   tools/admit.sh                 every .ngc in ~/linuxcnc/incoming
#   tools/admit.sh <file> [...]    those files
#   tools/admit.sh --dry-run ...   say what would happen, move nothing
#
# THREE STAGES, in this order, each fatal on its own:
#
#   1 LINT   the central linter, ~/418ops/machine/gcode-lint/lint_ngc.py.
#           ONE linter, written by Machining, run by both (contracts/
#           machine-facts.md). This is the pass that admits -- not a signature
#           made elsewhere at another time against the machine as PUBLISHED.
#   2 SIGN   sign_ngc.py --verify. STRUCT must be unchanged; BODY differing is
#           expected, feeds are the machinist's. Exit 1 (tag wrong or STRUCT
#           moved) REFUSES. Exit 2 (this machine holds no key) does NOT refuse:
#           it is unknown, it is reported, and stage 1 is what admitted the file.
#   3 PARSE  rs274, LinuxCNC's own interpreter, under a throwaway HOME.
#           The only check that sees what the interpreter itself will refuse.
#
# WHY THE SIGNATURE IS NOT THE PROOF OF LINT. The key is machine-local and was
# minted by whoever signed first; ned holds no copy, so a signature made on
# sleight cannot be verified here at all. Treating "signed" as "linted" would
# import a lint that happened on another machine, at another time, against the
# machine as published. This gate exists to not do that -- so it lints, every
# file, every time, and reads the signature only for what it can actually say.
#
# REFUSED FILES ARE MOVED, NOT DELETED (ned house rule), to
# nc_files_quarantine/refused/ with the findings in a .findings.txt beside them.
set -u
NED=/home/brains/Documents/ned
LINT=/home/brains/418ops/machine/gcode-lint/lint_ngc.py
SIGN=/home/brains/418ops/machine/gcode-lint/sign_ngc.py
INI=$NED/configs/ned5_pb/ned5_pb_ab_gen.ini.expanded
INCOMING=/home/brains/linuxcnc/incoming
REFUSED=/home/brains/linuxcnc/nc_files_quarantine/refused

DRY=0
[ "${1:-}" = "--dry-run" ] && { DRY=1; shift; }

# PROGRAM_PREFIX from the ini, so the gate follows the config rather than a
# re-typed path -- same rule gcode_quarantine.py already follows.
NC=$(awk -F= '/^[ \t]*PROGRAM_PREFIX[ \t]*=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2;exit}' "$INI" 2>/dev/null)
[ -z "$NC" ] && NC=/home/brains/linuxcnc/nc_files

if [ $# -gt 0 ]; then FILES=("$@"); else
  shopt -s nullglob
  FILES=("$INCOMING"/*.ngc "$INCOMING"/*.nc)
  shopt -u nullglob
fi
[ ${#FILES[@]} -eq 0 ] && { echo "nothing in $INCOMING"; exit 0; }

mkdir -p "$REFUSED"
WORK=$(mktemp -d /tmp/admit_XXXX)
trap 'rm -rf "$WORK"' EXIT

# rs274 harness. HOME is sandboxed because rs274 is a tool-mmap CREATOR: it
# O_TRUNCs $HOME/.tool.mmap before it parses its own options, over the LIVE
# table io, milltask and PB share. Running the scanner beside a live session
# truncated the tool table and SIGBUS-crashed milltask on 2026-08-06.
mkdir -p "$WORK/subs"
cp "$NED"/configs/ned5_pb/subroutines/*.ngc "$WORK/subs/" 2>/dev/null
cp "$NED"/configs/ned5_pb/ned5_pb.var "$WORK/test.var"
cat > "$WORK/test.ini" <<INI
[EMC]
VERSION = 1.1
MACHINE = admit
[RS274NGC]
PARAMETER_FILE = test.var
SUBROUTINE_PATH = subs
INI
[ -f "$INI" ] && awk '/^\[(ATC|AXIS_[A-Z])\][ \t]*$/{f=1} f && /^\[/ && !/^\[(ATC|AXIS_[A-Z])\][ \t]*$/{f=0} f' "$INI" >> "$WORK/test.ini"

ADMITTED=0; RSD=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "MISSING  $f"; RSD=$((RSD+1)); continue; }
  name=$(basename "$f")
  rep="$WORK/$name.findings.txt"
  : > "$rep"
  verdict=""

  echo "== $name"

  # ---- 1 LINT ------------------------------------------------------------
  if ! python3 "$LINT" "$f" >>"$rep" 2>&1; then
    verdict="LINT"
  fi

  # ---- 2 SIGNATURE -------------------------------------------------------
  if [ -z "$verdict" ]; then
    python3 "$SIGN" --verify "$f" >>"$rep" 2>&1; sig=$?
    case $sig in
      0) echo "   signature verifies, STRUCT unchanged" ;;
      2) echo "   signature UNVERIFIABLE here (no key on ned) -- STRUCT reported above, lint is what admits" ;;
      *) verdict="SIGNATURE" ;;
    esac
  fi

  # ---- 3 rs274 -----------------------------------------------------------
  if [ -z "$verdict" ]; then
    out=$(cd "$WORK" && HOME="$WORK" timeout 60 rs274 -i test.ini -v test.var -g "$f" 2>&1)
    echo "$out" >>"$rep"
    fatal=$(echo "$out" | grep -iE 'EOF in file|unclosed comment|nested comment|not defined|bad character|unknown word|bad number|out of range' | head -2)
    [ -n "$fatal" ] && { verdict="PARSE"; echo "   $fatal"; }
  fi

  # ---- verdict -----------------------------------------------------------
  if [ -z "$verdict" ]; then
    # Never overwrite a file the interpreter may already hold. machine_idle.sh
    # asks the NML status buffer; the process table lies (CLAUDE.md rule 19).
    if [ -e "$NC/$name" ] && ! "$NED/tools/machine_idle.sh" >/dev/null 2>&1; then
      echo "   REFUSED: $name already in nc_files and the machine is not idle"
      RSD=$((RSD+1)); continue
    fi
    if [ $DRY = 1 ]; then echo "   would ADMIT -> $NC/$name"
    else mv "$f" "$NC/$name"; echo "   ADMITTED -> $NC/$name"; fi
    ADMITTED=$((ADMITTED+1))
  else
    if [ $DRY = 1 ]; then echo "   would REFUSE ($verdict) -> $REFUSED/$name"
    else
      mv "$f" "$REFUSED/$name"; cp "$rep" "$REFUSED/$name.findings.txt"
      echo "   REFUSED ($verdict) -> $REFUSED/$name"
      echo "   findings            $REFUSED/$name.findings.txt"
    fi
    RSD=$((RSD+1))
  fi
done

echo
echo "admitted $ADMITTED   refused $RSD"
[ $RSD -gt 0 ] && exit 1
exit 0
