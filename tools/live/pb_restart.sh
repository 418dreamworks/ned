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
  [ "${NED_KINS:-identity}" = "tooltip" ] && _MODEFLAGS="$_MODEFLAGS -tcp"
fi
# shellcheck disable=SC2086
nohup "$NED/tools/run5.sh" $_MODEFLAGS > "$OUT" 2>&1 &
echo "pb_restart: launching (log: $OUT) -- waiting 60 s"
sleep 60

if ! pgrep -f "[b]in/probe_basic" >/dev/null; then
  echo "pb_restart: LAUNCH FAILED -- probe_basic not running. Tail of $OUT:"
  tail -5 "$OUT"
  exit 1
fi
echo "pb_restart: up. Session arming lines:"
"$NED/tools/lcnc_session.sh" 2>/dev/null | grep -aE 'REDUNDANCY|LOCK [AC] ->|RACK TABLE|DECLARATION|countdown wired|error flag armed|pendant: ready' | head -8
