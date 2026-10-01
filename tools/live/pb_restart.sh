#!/bin/bash
# pb_restart.sh -- the ONLY sanctioned way for Claude to restart PB.
#
# WHY (2026-08-04): a hand-shortened inline kill block SIGTERM'd a live
# session, missed the kill -9 escalation, left the GUI alive with ned_brain
# and ned_pendant dead, and the follow-up launch refused on the survivor --
# the operator then drove a zombie session with no MPG and no homing guards.
# Hand-written kill blocks degrade under editing; this script does not.
#
# Discipline, in order, no step skippable:
#   1. idle gate      -- machine_idle.sh (NML), refuse if a cycle is in flight
#   2. SIGTERM        -- polite close of probe_basic/linuxcncsvr/milltask/halui
#   3. wait <= 10 s
#   4. kill -9        -- escalate to anything that survived
#   5. VERIFY DEAD    -- if anything still lives, ABORT. Never launch over
#                        survivors: that is exactly the zombie this exists
#                        to prevent.
#   6. brain/pendant  -- pkill the userspace comps (children of the session)
#   7. launch         -- run5.sh, backgrounded, log kept
#   8. report         -- wait, then print the new session's arming lines
#
# --close-only: steps 1-6 and STOP (operator closes/relaunches themselves;
# CLAUDE.md rule 12 -- launching is never mine). Same gate, same SIGTERM
# then kill -9 escalation, same verify-dead abort. Added 2026-08-05 so a
# "close PB" never becomes another hand-written kill block.
set -u
NED=/home/brains/Documents/ned
OUT=/tmp/pb_restart.last
CLOSE_ONLY=0
[ "${1:-}" = "--close-only" ] && CLOSE_ONLY=1

pids() { { pgrep -f "[b]in/probe_basic"; pgrep -x linuxcncsvr
           pgrep -x milltask; pgrep -x halui; } 2>/dev/null | sort -u; }

if ! timeout 10 "$NED/tools/machine_idle.sh" 2>&1 | grep -qE 'safe to write|not running'; then
  echo "pb_restart: REFUSED -- machine is not idle (cycle in flight)."
  exit 1
fi

P=$(pids)
if [ -n "$P" ]; then
  echo "pb_restart: closing session: $(echo $P | tr '\n' ' ')"
  # STEP 0: CLOSE THE WINDOW, DO NOT SIGNAL IT (operator 2026-08-12: "i said
  # ALWAYS kill PB with exit command so that anything in GUI is saved").
  # qtpyvcp writes .vcp_persistent_data.pickle from Qt's closeEvent ->
  # terminate() -> terminatePlugins() (application.py:265). SIGTERM does not
  # raise closeEvent, so every setting changed since launch was thrown away
  # -- that is why the ATC rapid rate kept reverting to 1000 after being set
  # to 6000 six times. windowclose sends WM_DELETE_WINDOW, which is the same
  # thing the EXIT button does.
  W=$(DISPLAY=:0 xdotool search --name "Probe Basic" 2>/dev/null | tail -1)
  if [ -n "$W" ]; then
    # CTRL+Q, NOT windowclose (2026-08-13). FILE -> EXIT is bound to Ctrl+Q,
    # and that menu action is the path the operator uses and the one that
    # actually exits. windowclose sends WM_DELETE_WINDOW, which never
    # completed here -- every close this session sat through the full wait
    # and escalated to kill -9, which is precisely the case where qtpyvcp
    # does NOT write .vcp_persistent_data.pickle. So the "graceful" path was
    # discarding the settings it existed to save.
    echo "pb_restart: sending CTRL+Q to window $W (FILE -> EXIT, saves GUI settings)"
    DISPLAY=:0 xdotool windowactivate "$W" 2>/dev/null
    sleep 1
    DISPLAY=:0 xdotool key --window "$W" ctrl+q 2>/dev/null
    # 60 s, NOT 20 (2026-08-12). CONFIRM_EXIT = False here, so closeEvent
    # goes straight to app.quit() with no dialog -- but tearing down
    # linuxcncsvr, milltask and halui behind it takes longer than 20 s, and
    # the short wait made this script kill -9 a shutdown that was working,
    # throwing away the settings the clean close exists to save.
    # 120 s. 60 was still not enough -- every close this session timed out
    # and escalated to kill -9, which is exactly the case where the GUI
    # settings are NOT written, so the wait defeated its own purpose.
    for _ in $(seq 1 120); do sleep 1; [ -z "$(pids)" ] && break; done
    if [ -z "$(pids)" ]; then
      echo "pb_restart: closed cleanly -- persistent settings written"
    else
      echo "pb_restart: window close did not finish in 120 s -- escalating"
    fi
  else
    echo "pb_restart: no Probe Basic window found -- cannot close cleanly"
  fi
  P=$(pids)
fi
if [ -n "$P" ]; then
  # shellcheck disable=SC2086
  kill $P 2>/dev/null
  for _ in $(seq 1 10); do sleep 1; [ -z "$(pids)" ] && break; done
  R=$(pids)
  if [ -n "$R" ]; then
    echo "pb_restart: escalating kill -9: $(echo $R | tr '\n' ' ')"
    # shellcheck disable=SC2086
    kill -9 $R 2>/dev/null
    sleep 2
  fi
  if [ -n "$(pids)" ]; then
    echo "pb_restart: ABORT -- session did NOT die: $(pids | tr '\n' ' ')"
    echo "pb_restart: launching over survivors makes a zombie. Nothing launched."
    exit 1
  fi
fi
pkill -f "[n]ed_brain.py"   2>/dev/null
pkill -f "[n]ed_pendant.py" 2>/dev/null
pkill -f "live/dro2.py" 2>/dev/null   # the second-monitor DRO restarts with PB
sleep 1

if [ "$CLOSE_ONLY" = "1" ]; then
  echo "pb_restart: CLOSED. Nothing launched -- run5.sh is the operator's."
  exit 0
fi

# relaunch the SAME session flavor (mode grammar 2026-08-05): run5 now
# REQUIRES a spelled mode; reuse the one the dying session recorded
_MODEFLAGS="-xyz"
if [ -f "$NED/.last_run5_mode" ]; then
  . "$NED/.last_run5_mode"
  _MODEFLAGS="-${NED_MODE:-xyz}"
  # ALWAYS SPELL THE KINS. run5 now refuses without it, and rightly: a
  # default silently decides whether XYZ means the spindle or the tool tip.
  if [ "${NED_KINS:-identity}" = "tooltip" ]; then
    _MODEFLAGS="$_MODEFLAGS -tcp"
  else
    _MODEFLAGS="$_MODEFLAGS -notcp"
  fi
fi
# shellcheck disable=SC2086
# DETACH INTO ITS OWN SESSION (2026-08-05). Plain `nohup ... &` left the
# whole tree -- run5, its `script` wrapper, linuxcnc, PB -- in the CALLER's
# process group. Launched from an agent tool call, that group is torn down
# when the call returns: the pty master closes and PB dies on its next
# write with "ICE default IO error handler doing an exit(), errno = 32",
# taking rtapi_app down with it (signal 11). Twice, both at ~t+104s, while
# operator-launched sessions ran for many minutes. nohup only ignores
# SIGHUP; setsid is what survives the group kill.
# SAY WHICH CONFIGURATION IS ABOUT TO START. This script relaunches from
# .last_run5_mode, NOT from whatever was actually running -- so if that file
# is stale it will silently bring the machine up in a different machine.
# That happened on 2026-08-12: the operator started -xyzab, a restart read a
# stale xyzac and came back with no B axis at all, and the only symptom was a
# program stopping dead on its first B word.
echo "pb_restart: RELAUNCHING AS  $_MODEFLAGS   (from .last_run5_mode)"
setsid nohup "$NED/tools/run5.sh" $_MODEFLAGS > "$OUT" 2>&1 < /dev/null &
echo "pb_restart: launching (log: $OUT) -- waiting 60 s"
sleep 60

if ! pgrep -f "[b]in/probe_basic" >/dev/null; then
  echo "pb_restart: LAUNCH FAILED -- probe_basic not running. Tail of $OUT:"
  tail -5 "$OUT"
  exit 1
fi
echo "pb_restart: up. Session arming lines:"
"$NED/tools/lcnc_session.sh" 2>/dev/null | grep -aE 'REDUNDANCY|LOCK [AC] ->|RACK TABLE|DECLARATION|countdown wired|error flag armed|pendant: ready' | head -8
