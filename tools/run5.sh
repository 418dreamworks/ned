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
    -xyz|-xyza|-xyzac) NED_MODE="${_a#-}" ;;
    -xyz_a|-xyz_b|-xyza_b|-xyzb_a)
      echo "run5: $_a refused -- the B-table build has not landed (task #25)"
      exit 1 ;;
    -tcp)      NED_KINS=tooltip ;;
    -trivkins) NED_KINS=identity ;;   # old name, kept as alias for identity
    -5axis)    NED_KINS=tooltip ;;    # old name, kept as alias for -tcp
    *) echo "run5: unknown flag '$_a'"; exit 1 ;;
  esac
done
if [ -z "$NED_MODE" ]; then
  echo "run5: SPELL THE MODE. one of: -xyz  -xyza  -xyzac   (+ optional -tcp, -nopower, resume)"
  echo "      table modes -xyz_a -xyz_b -xyza_b -xyzb_a arrive with the B build"
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
  sed -e 's|^KINEMATICS = .*|KINEMATICS = ned_ac_kins coordinates=XYZXAC|' \
      -e 's|^POSTGUI_HALFILE = \(.*\)$|POSTGUI_HALFILE = \1\nPOSTGUI_HALFILE = postgui_tcp.hal|' \
      "$INI" > "$GEN_TCP" || { echo "run5: tcp ini generation FAILED"; exit 1; }
  INI="$GEN_TCP"
  echo "run5: TOOL-TIP kins at launch (no runtime switch)"
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
