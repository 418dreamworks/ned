#!/bin/bash
# run5.sh -- launch the machine under PROBE BASIC (configs/ned5_pb/ned5_pb.ini)
# with FULL output capture, so Claude can self-monitor and NEVER needs anything
# pasted from the terminal.
#
#   LinuxCNC + Probe Basic stdout/stderr (startup errors, tracebacks, runtime)
#       -> ned/lcnc.log
#   Machine events (head reads, homing verify, resume arming, teleop, programs)
#       -> ned/gui.md          (written by tools/live/ned_brain.py)
#   Mesa pin states
#       -> ned/mesa.log        (tools/live/mesalog.sh)
#
# Launch the machine with:   ned/tools/run5.sh
# Launch WITHOUT re-homing XYZ:   ned/tools/run5.sh resume     (machine must NOT
#   have been moved since the last homed session). Consent happens HERE, before
#   launch: the stored positions are shown and you must type y. ned_brain then
#   arms ini.0-3.home/home_offset at startup; HOME ALL homes joints 0-3 IN
#   PLACE at those values with zero motion. A/C still do their normal absolute
#   read -> home -> verify (ned_brain).
# Then just tell Claude "I did X" -- Claude reads lcnc.log / gui.md / mesa.log.
#
# probe_basic + qtpyvcp live in the qt_pb venv -> put it on PATH first
# (a plain `linuxcnc ned5_pb.ini` from a non-login shell will NOT find them).

NED="/home/brains/Documents/ned"

# AUTO-POWER is the DEFAULT (operator 2026-08-04): "power button is to
# enable motion, nothing else" -- waiting for a human click only delayed the
# ON-edge stale-home declare. `-nopower` restores the wait-for-the-button
# behaviour. Flags scan so `resume` and `-nopower` combine in any order.
NOPOWER=0
RESUME=0
# MODE GRAMMAR (operator 2026-08-05): the mode flag is REQUIRED -- spell
# out exactly which axes are alive. Un-spelled rotaries get clamped
# (soft limits +-0.001 deg after homing) so nothing can move them.
#   -xyz      pure XYZ machine (A+C clamped at 0)
#   -xyza     head tilt A live, C clamped at 0
#   -xyzac    full swivel head
#   -xyz_a  -xyz_b  -xyza_b  -xyzb_a   table-rotary modes: parse but
#             REFUSED until the B-table build lands (task #25)
# -tcp: tool-tip mode (ned_ac_kins type 1) -- XYZ means the TOOL TIP and
# the linears chase it while the head rotates. Inert in -xyz. Refuses
# until the module is installed AND a pivot length exists.
NED_MODE=""
NED_KINS=identity
for _a in "$@"; do
  case "$_a" in
    -nopower)  NOPOWER=1 ;;
    resume)    RESUME=1 ;;
    -xyz|-xyza|-xyzac|-xyzab) NED_MODE="${_a#-}" ;;
    -xyz_a|-xyz_b|-xyza_b|-xyzb_a)
      echo "run5: $_a refused -- superseded by -xyzab (task #25)"
      exit 1 ;;
    -tcp)      NED_KINS=tooltip ;;
    -notcp)    NED_KINS=identity ;;   # explicit; identity is also the default
    -trivkins) NED_KINS=identity ;;   # old name, kept as alias for identity
    *) echo "run5: unknown flag '$_a'"; exit 1 ;;
  esac
done
if [ -z "$NED_MODE" ]; then
  echo "run5: SPELL THE MODE. one of: -xyz  -xyza  -xyzac  -xyzab"
  echo "      (+ -tcp / -notcp, -nopower, resume)"
  exit 1
fi
# -xyzab = workpiece rotary B instead of the head spin C (operator 2026-08-11).
# There is no A-head + B-table kinematics module on this machine -- ned_ac_kins
# models the swivel head and would compensate XYZ for a C that is parked. So
# the table mode is identity-only, and the refusal is loud rather than a
# silent downgrade.
if [ "$NED_MODE" = "xyzab" ] && [ "$NED_KINS" = "tooltip" ]; then
  echo "run5: -tcp refused in -xyzab -- ned_ab_kins does not exist (task #24)."
  echo "      relaunch as: run5.sh -xyzab -notcp"
  exit 1
fi
if [ "$NED_KINS" = "tooltip" ] && [ "$NED_MODE" = "xyz" ]; then
  echo "run5: note -- -tcp is inert in -xyz (no rotary can move); launching identity"
  NED_KINS=identity
fi
if [ "$NED_KINS" = "tooltip" ]; then
  if [ ! -f /usr/lib/linuxcnc/modules/ned_ac_kins.so ]; then
    echo "run5: -tcp refused -- ned_ac_kins.so is not installed (update_survival A1b)"
    exit 1
  fi
  if ! grep -q '^#<_pivot_length>' "$NED/configs/params/head_pivot.inc" 2>/dev/null &&      ! grep -q 'PIVOT' "$NED/configs/params/head_pivot.inc" 2>/dev/null; then
    echo "run5: -tcp refused -- no pivot length (configs/params/head_pivot.inc missing)"
    echo "      tape-measure A-pivot to spindle nose for PLAY, calibrate before CUTTING"
    exit 1
  fi
fi
# remember the mode so pb_restart relaunches the SAME session flavor
echo "NED_MODE=$NED_MODE NED_KINS=$NED_KINS" > "$NED/.last_run5_mode"
export NED_MODE NED_KINS
INI="$NED/configs/ned5_pb/ned5_pb.ini"
LOG="$NED/lcnc.log"
VENV="$HOME/qt_pb/qtpyvcp/venv"

if [ ! -x "$VENV/bin/probe_basic" ]; then
  echo "run5: probe_basic not found in $VENV -- see tools/live/qt_pb.sh +"
  echo "      docs/commissioning/probe_basic_migration.md (cmake/PySide6/vtk)"; exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# 0. ALREADY-RUNNING CHECK (operator 2026-08-02): a second launch on top of a
# live session used to go straight into `halrun -U` below and wreck the running
# machine. Detect first, ASK, and never touch anything unless told to.
# Bracket patterns ([b]in/...) so pgrep can never match this script's own
# command line -- that self-match has bitten us three times.
run5_running_pids() {
  { pgrep -f "[b]in/probe_basic"
    pgrep -x linuxcncsvr
    pgrep -x milltask
    pgrep -x halui; } 2>/dev/null | sort -u
}
EXISTING=$(run5_running_pids)
if [ -n "$EXISTING" ]; then
  echo "run5: a LinuxCNC/Probe Basic session is ALREADY RUNNING:"
  # shellcheck disable=SC2086
  ps -o pid=,etime=,args= -p $EXISTING 2>/dev/null | cut -c1-110 | sed 's/^/      /'
  if [ ! -t 0 ]; then
    echo "run5: refusing to launch on top of it (no terminal to ask on)."
    echo "      Close that session first, then run5.sh again."
    exit 1
  fi
  read -r -p "run5: close it and launch a fresh session? [y/N] " closeok
  if [ "$closeok" != "y" ]; then
    echo "run5: left the running session alone -- nothing was touched."
    exit 1
  fi
  echo "run5: closing the running session ..."
  # shellcheck disable=SC2086
  kill $EXISTING 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    [ -z "$(run5_running_pids)" ] && break
  done
  STUBBORN=$(run5_running_pids)
  if [ -n "$STUBBORN" ]; then
    echo "run5: still up after 10 s -- forcing"
    # shellcheck disable=SC2086
    kill -9 $STUBBORN 2>/dev/null
    sleep 2
  fi
  if [ -n "$(run5_running_pids)" ]; then
    echo "run5: FAILED to close the old session -- aborting so nothing is corrupted"
    exit 1
  fi
  # the brain/pendant are children of that session; make sure they went too
  pkill -f "[n]ed_brain.py"   2>/dev/null
  pkill -f "[n]ed_pendant.py" 2>/dev/null
  sleep 1
  echo "run5: old session closed."
fi

# `resume` -> stored homing. HOME_SEARCH_VEL is config-time only (inihal exposes
# just home/home_offset/home_sequence at runtime), so skipping the switch search
# REQUIRES a different ini: generate one whose [JOINT_0..3] home IN PLACE
# (search/latch vel 0 -> homing.c:807 immediate path). Overrides sit between the
# section header and the #INCLUDE line (IniFile::Find returns the FIRST match).
# The nedgui confirmation dialog is gone -- consent is THIS prompt; ned_brain
# refuses to arm without NED_RESUME_OK=1 and aborts any un-armed homing attempt.
if [ "$RESUME" = "1" ]; then
  SH="$NED/configs/ned5/stored_home.json"
  if [ ! -r "$SH" ]; then echo "run5: resume refused -- $SH missing"; exit 1; fi
  echo "run5: RESUME -- joints 0-3 will be declared homed AT (no motion):"
  python3 - "$SH" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
j = d['joints']
print('      saved {}   X {:+.3f}   Y {:+.3f}   Z {:+.3f}   X2 {:+.3f}'.format(
    d.get('saved', '?'), j['0'], j['1'], j['2'], j['3']))
EOF
  echo "      ONLY if the machine has NOT been moved since then."
  read -r -p "run5: proceed? [y/N] " ok
  [ "$ok" = "y" ] || { echo "run5: resume declined"; exit 1; }
  export NED_RESUME_OK=1
  GEN="$NED/configs/ned5_pb/ned5_pb_resume_gen.ini"
  awk '{
    print
    if ($0 ~ /^\[JOINT_[0-3]\]$/) {
      print "# RESUME overrides (generated by run5.sh resume -- do not hand-edit; first-match-wins"
      print "# shadows the #INCLUDE values below): home IN PLACE at ini.N.home_offset, no motion."
      print "HOME_SEARCH_VEL = 0"
      print "HOME_LATCH_VEL = 0"
      print "HOME_USE_INDEX = NO"
    }
  }' "$INI" > "$GEN" || { echo "run5: resume ini generation FAILED"; exit 1; }
  INI="$GEN"
  echo "run5: RESUME mode -- ned_brain arms the stored positions at startup"
fi

# -xyzab: WORKPIECE ROTARY B AS A SEVENTH JOINT (operator 2026-08-11).
# C is NOT removed -- it still has to be homed and then held at zero, and a
# joint with no axis letter cannot exist under trivkins. So joints 0-5 are
# byte-identical to every other mode and B is appended as joint 6. Generated,
# not a forked ini, so all the numeric params stay single-sourced in
# configs/params/*.inc (CLAUDE.md rule 11).
if [ "$NED_MODE" = "xyzab" ]; then
  GEN_AB="$NED/configs/ned5_pb/ned5_pb_ab_gen.ini"
  GEN_PG_AB="$NED/configs/ned5_pb/postgui_ab_all.hal"
  cat "$NED/configs/ned5_pb/postgui_pb.hal" \
      "$NED/configs/ned5_pb/postgui_b.hal" > "$GEN_PG_AB" \
      || { echo "run5: ab postgui concat FAILED"; exit 1; }
  # WHY PYTHON AND NOT awk (2026-08-11): check_config.tcl:226-230 runs its
  # limit validation ONLY for trivkins -- every other kins module hits the
  # `default` arm and exits 0 with the checks skipped. Every launch on this
  # machine since the axis limits were disabled (2026-08-07) has been a
  # ned_ac_kins launch, so nobody had seen that [AXIS_*] is now WIDER than
  # the joints it drives, which trivkins rejects outright:
  #   [JOINT_0]MIN_LIMIT > [AXIS_X]MIN_LIMIT (-4042.725 > -5042.725)
  # -xyzab is trivkins, so it is the first mode to actually meet the check.
  #
  # The fix belongs HERE and nowhere else. configs/params/axis_*.inc is
  # shared with the tool-tip mode, where those wide limits are deliberate
  # (an axis limit bounds the TOOL TIP under ned_ac_kins, and a joint-sized
  # number there refused most of Z). So this generated ini alone pins each
  # [AXIS_c] to the tightest bound of the joints that drive it -- identical
  # behaviour, because under identity kins axis and joint ARE the same
  # travel, and "whichever comes first" is unchanged.
  python3 - "$INI" "$GEN_AB" <<'ABGEN' || { echo "run5: ab ini generation FAILED"; exit 1; }
import io, os, re, sys
src, dst = sys.argv[1], sys.argv[2]

def expand(path, depth=0):
    out = []
    for ln in io.open(path, encoding='utf-8'):
        m = re.match(r'\s*#INCLUDE\s+(\S+)', ln)
        if m and depth < 6:
            inc = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
            if os.path.exists(inc):
                out += expand(inc, depth + 1)
                continue
        out.append(ln)
    return out

# joint limits, from the ini with every #INCLUDE resolved
flat, sec, vals = expand(src), None, {}
for ln in flat:
    h = re.match(r'\s*\[([A-Z0-9_]+)\]\s*$', ln)
    if h:
        sec = h.group(1); continue
    kv = re.match(r'\s*([A-Z0-9_]+)\s*=\s*(\S+)', ln)
    if kv and sec:
        vals.setdefault(sec, {}).setdefault(kv.group(1), kv.group(2))

# joint -> axis letter, straight off the coordinate string
COORD = 'XYZXACB'
bound = {}
for jn, letter in enumerate(COORD):
    j = vals.get('JOINT_%d' % jn, {})
    if 'MIN_LIMIT' not in j or 'MAX_LIMIT' not in j:
        continue
    lo, hi = float(j['MIN_LIMIT']), float(j['MAX_LIMIT'])
    if letter in bound:      # gantry X: the pair's INTERSECTION, never the union
        lo = max(lo, bound[letter][0]); hi = min(hi, bound[letter][1])
    bound[letter] = (lo, hi)

out, axis_sec = [], None
for ln in io.open(src, encoding='utf-8'):
    st = ln.rstrip('\n')
    if st.startswith('JOINTS = '):
        out.append('JOINTS = 7'); continue
    if st.startswith('KINEMATICS = '):
        out.append('KINEMATICS = trivkins coordinates=%s kinstype=B' % COORD); continue
    if st.startswith('COORDINATES = '):
        out.append('COORDINATES = ' + ' '.join(COORD)); continue
    if st.startswith('POSTGUI_HALFILE = '):
        out.append('POSTGUI_HALFILE = postgui_ab_all.hal'); continue
    if st == 'HALFILE = ../ned5/ned5_iron.hal':
        out.append(st)
        out.append('# -xyzab overlay: workpiece rotary B on 7I85S stepgen.00/01.')
        out.append('HALFILE = ../ned5/ned5_b.hal'); continue
    a = re.match(r'\[AXIS_([A-Z])\]\s*$', st)
    if a and a.group(1) in bound:
        # SHADOWING IS NOT ENOUGH. iniFind returns the first match, but
        # check_config.tcl reads EVERY value and then compares the whole
        # list ("Unexpected multiple values [AXIS_X]MIN_LIMIT: -4042.725
        # -5042.725", then "[JOINT_0]MAX_LIMIT < [AXIS_X]MAX_LIMIT (1.0 <
        # 1.0 1001)"). The old value has to be GONE, so this section's
        # #INCLUDE is inlined here with its limits filtered out.
        lo, hi = bound[a.group(1)]
        in_axis = os.path.dirname(src)
        out.append(st)
        out.append('# GENERATED -xyzab: [AXIS_%s] inlined from its .inc with'
                   % a.group(1))
        out.append('# MIN_LIMIT/MAX_LIMIT replaced by the driving joint(s)')
        out.append('# bounds, so check_config.tcl passes under trivkins.')
        out.append('MIN_LIMIT = %r' % lo)
        out.append('MAX_LIMIT = %r' % hi)
        axis_sec = a.group(1)
        continue
    if axis_sec:
        if re.match(r'\s*\[', st):
            axis_sec = None                     # next section, stop filtering
        else:
            body = ([l.rstrip('\n') for l in
                     expand(os.path.normpath(os.path.join(
                         os.path.dirname(src),
                         re.match(r'\s*#INCLUDE\s+(\S+)', st).group(1))))]
                    if re.match(r'\s*#INCLUDE\s+\S+', st) else [st])
            for b in body:
                if not re.match(r'\s*(MIN|MAX)_LIMIT\s*=', b):
                    out.append(b)
            continue
    out.append(st)

out += ['',
 '# ===================== GENERATED BY run5.sh -xyzab =====================',
 '# Hand-edits here are destroyed on the next launch. B has no encoder and',
 '# no switches; the worm is self-locking, so it holds unpowered.',
 '[AXIS_B]',
 'MAX_VELOCITY = 30',
 'MAX_ACCELERATION = 300',
 '# No soft limits on B (operator: continuous workpiece rotary).',
 'MIN_LIMIT = -3600000',
 'MAX_LIMIT = 3600000',
 '',
 '[JOINT_6]',
 'TYPE = ANGULAR',
 'MAX_VELOCITY = 30',
 'MAX_ACCELERATION = 300',
 'STEPGEN_MAXVEL = 36',
 'STEPGEN_MAXACCEL = 450',
 '# 22.222 steps/deg = 400 p/rev x 20 worm / 360 (docs/components.md:50).',
 '# The two drives are mechanically mirrored, hence the sign flip.',
 'SCALE = 22.222',
 'SCALE_MIRROR = -22.222',
 'FERROR = 5.0',
 'MIN_FERROR = 1.0',
 'MIN_LIMIT = -3600000',
 'MAX_LIMIT = 3600000',
 '# In-place home: search and latch both zero, HOME == HOME_OFFSET, so',
 '# the cycle sets the position and the final move is zero length.',
 'HOME = 0.0',
 'HOME_OFFSET = 0.0',
 'HOME_SEARCH_VEL = 0',
 'HOME_LATCH_VEL = 0',
 'HOME_USE_INDEX = NO',
 '# No HOME_SEQUENCE: B stays out of Home All, like A and C.']
io.open(dst, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
for k in sorted(bound):
    print('run5: [AXIS_%s] pinned to %+.3f .. %+.3f (driving joint bounds)'
          % (k, bound[k][0], bound[k][1]))
ABGEN
  INI="$GEN_AB"
  echo "run5: -xyzab -- B (workpiece rotary) is joint 6; C is homed to 0 and held."
  echo "      R4 (7I84 output-05) gates BOTH the 70 V brick and the A/C absolute"
  echo "      read. The brain drops B power to take a head read; the worm is"
  echo "      self-locking so B holds position while it is dark."
fi

# cores ON: rtapi_app said "dumping core" on the 2026-07-31 SIGSEGV but ulimit -c
# was 0, so there was no core to autopsy. Next time there will be.
# TOOL-TIP LAUNCHES DIRECTLY IN TYPE 0 (2026-08-05): switching switchkins
# at runtime UNHOMES every joint (LinuxCNC invalidates homing on a kins
# change) -- the machine came up homed, switched, and then refused to jog.
# Instead generate an ini whose type 0 IS the tool-tip kins. Safe because
# identity and tool-tip agree EXACTLY at A=0, which is where homing happens.
if [ "$NED_KINS" = "tooltip" ]; then
  GEN_TCP="$NED/configs/ned5_pb/ned5_pb_tcp_gen.ini"
  # base ini stays trivkins (the known-good default); the tool-tip kins and
  # its own postgui live ONLY in this generated copy
  # ONE POSTGUI FILE, CONCATENATED (2026-08-05). This used to append a
  # SECOND "POSTGUI_HALFILE =" line, and qtpyvcp's launcher reads exactly
  # one (launcher.py:196 loads `postgui_halfile`, singular). The tcp file
  # was therefore never loaded: `arm` never existed, ned_brain's
  # `setp arm.in0 157` went nowhere, and ned_ac_kins.pivot-length sat at
  # its 250 mm DEFAULT placeholder while the GUI reported "kins=tcp".
  # Silent, and it makes every tool-tip number wrong.
  GEN_PG="$NED/configs/ned5_pb/postgui_tcp_all.hal"
  cat "$NED/configs/ned5_pb/postgui_pb.hal" \
      "$NED/configs/ned5_pb/postgui_tcp.hal" > "$GEN_PG" \
      || { echo "run5: tcp postgui concat FAILED"; exit 1; }
  # PIVOT AT LOAD TIME, NOT INTO A LIVE SERVO LOOP (2026-08-05).
  # ned_brain used to setp arm.in0 after the machine was enabled, so
  # pivot-length stepped 0 -> 157 in ONE servo period. Pivot length is a
  # term in the kinematics: at A=-24 deg that step commands 64 mm of Jy.
  # Every launch with the head off zero jerked the servos and faulted.
  # Written here, it is in place before the machine can be powered.
  _PIV=$(awk -F= '/^PIVOT_LENGTH/{gsub(/[ \t]/,"",$2); print $2; exit}' \
         "$NED/configs/params/head_pivot.inc")
  [ -n "$_PIV" ] || { echo "run5: no PIVOT_LENGTH in head_pivot.inc"; exit 1; }
  echo "setp arm.in0 $_PIV" >> "$GEN_PG"
  echo "run5: pivot arm.in0 = $_PIV set at HAL load (no live-loop write)" 
  sed -e 's|^KINEMATICS = .*|KINEMATICS = ned_ac_kins coordinates=XYZXAC|' \
      -e 's|^POSTGUI_HALFILE = .*|POSTGUI_HALFILE = postgui_tcp_all.hal|' \
      "$INI" > "$GEN_TCP" || { echo "run5: tcp ini generation FAILED"; exit 1; }
  INI="$GEN_TCP"
  echo "run5: TOOL-TIP kins at launch (no runtime switch)"
  echo "run5: NOTE -- world XYZ will mean the TOOL TIP. The pivot arm must"
  echo "      be fed (brain sets arm.in0 from head_pivot.inc); if it reads"
  echo "      0 the kins falls back to its 250 mm placeholder and jogs go"
  echo "      nowhere sensible. 2026-08-05: that cost a jogging session."
fi

ulimit -c unlimited 2>/dev/null || true

# SOFTWARE GL for the VTK backplot: TRIED AND REMOVED (2026-08-01) --
# llvmpipe ground >5 min at 95% CPU during VTK init on this Pi ("pb isnt
# even loading"). Backplot stays invisible (V3D = GL 3.1 < VTK's 3.2)
# until a lighter path is found. Do NOT re-add LIBGL_ALWAYS_SOFTWARE=1.

# 1. clear any stale realtime so the start is always clean (blocks the "won't start")
halrun -U >/dev/null 2>&1 || true

# announce who is using the machine

# 2. ensure the Mesa pin logger + log pruner are running
pgrep -f 'tools/live/mesalog.sh' >/dev/null 2>&1 || ( "$NED/tools/live/mesalog.sh" >/dev/null 2>&1 & )
pgrep -f 'tools/live/blackmark.py' >/dev/null 2>&1 || ( "$NED/tools/live/blackmark.py" >/dev/null 2>&1 & )

# SECOND-MONITOR DRO (operator 2026-08-05): comes up with PB, every launch
# and every relaunch. Self-contained (reads LinuxCNC directly), so it can
# never destabilise the GUI -- and it keeps showing the numbers even if PB
# dies. Killed and restarted here so a stale copy never lingers.
pkill -f 'live/dro2.py' >/dev/null 2>&1
# dro2 is a SEPARATE process: it inherits NED_MODE but nothing told it
# which ini is running, so ini_axes() fell back to its hardcoded XYZAC
# list and the standalone DRO showed a C row and no B at all.
( sleep 12; INI_FILE_NAME="$INI" "$NED/tools/live/dro2.py" \
    > "$NED/logs/dro2.log" 2>&1 & ) &
pgrep -f 'tools/live/logclean.sh' >/dev/null 2>&1 || ( "$NED/tools/live/logclean.sh" >/dev/null 2>&1 & )

# 3. keep lcnc.log bounded (last ~2000 lines) + stamp a session header
if [ -f "$LOG" ]; then tail -n 2000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"; fi
{ echo; echo "==================== LinuxCNC start (PROBE BASIC)  $(date '+%F %T') ===================="; } >> "$LOG"

# 3b. WORKSPACE MOVE -- REMOVED 2026-08-02. Putting PB on its own workspace
# stopped operator clicks and harness clicks colliding, but it also meant any
# stray workspace switch showed a bare desktop, which reads as the screen
# "blanking a whole lot". Not worth it: the harness now verifies PB is the
# active window before every click instead (gt/harness.py focus()).

# 3c. GUI FIT WATCHDOG. On 2026-08-03 PB came up the right size and then grew
# past the monitor a few seconds later, with the top-level window still
# reporting a correct 1920x1200 -- it was the CHILD widgets that overflowed.
# This samples the real extents for ~100 s after launch and writes FAIL lines
# into lcnc.log. Background, never blocks, report-only.
( "$NED/tools/live/pb_fit_check.sh" >/dev/null 2>&1 & )

# 4. launch under `script` so LinuxCNC sees a TTY. Without one, /usr/bin/linuxcnc:203
# pops a modal wish dialog on error and BLOCKS; with a pty the error is printed
# and captured here instead.
# AUTO-POWER helper: backgrounded BEFORE the blocking launch below. Waits
# for the NML status buffer, then ESTOP_RESET -> ON, and REPORTS the result
# either way -- if the hardware e-stop chain or air permit holds emc-enable
# low, STATE_ON is refused and the log says so instead of pretending.
if [ "$NOPOWER" != "1" ]; then
  (
    for _i in $(seq 1 60); do
      sleep 1
      python3 - <<'AUTOPOWER' && break
import sys
import linuxcnc
try:
    s = linuxcnc.stat(); s.poll()
except Exception:
    sys.exit(1)
if s.task_state == linuxcnc.STATE_ON:
    sys.exit(0)
c = linuxcnc.command()
c.state(linuxcnc.STATE_ESTOP_RESET); c.wait_complete(2.0)
c.state(linuxcnc.STATE_ON); c.wait_complete(2.0)
s.poll()
if s.task_state == linuxcnc.STATE_ON:
    print('run5: AUTO-POWER: machine ON (stale-home declare follows)', flush=True)
    sys.exit(0)
sys.exit(1)
AUTOPOWER
    done
    python3 - <<'AUTOPOWER2'
import linuxcnc
try:
    s = linuxcnc.stat(); s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        print('run5: AUTO-POWER FAILED: task_state=%d (2=estop-reset). '
              'E-stop chain or air permit is holding power off -- clear it '
              'and press POWER yourself.' % s.task_state, flush=True)
except Exception as e:
    print('run5: AUTO-POWER: no status buffer (%s)' % e, flush=True)
AUTOPOWER2
  ) >> "$LOG" 2>&1 &
fi

script -q -a -c "linuxcnc '$INI'" "$LOG"
