#!/bin/bash
# lcnc_stop.sh -- shut LinuxCNC down CLEANLY (no SIGKILL unless it refuses to die).
#
# A `kill -9` leaves LinuxCNC's shared memory / lock files behind, and the next start
# then pops the "an instance is already running / restart?" dialog the operator has to
# click. So: SIGTERM first, let it tear itself down, and only escalate if it hangs.
#
#   tools/lcnc_stop.sh          stop and wait
set -u
NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Bracket patterns so pgrep never matches THIS script's own command line.
# Skip ZOMBIES (stat Z): they are already dead, cannot be killed, and once made this
# script report STILL RUNNING forever over two defunct rtapi_app husks.
alive(){
  local p
  for p in $(pgrep -f '[b]in/linuxcnc|[l]inuxcncsvr|[m]illtask|[q]tvcp|[r]tapi_app' 2>/dev/null); do
    [ "$(ps -o stat= -p "$p" 2>/dev/null | cut -c1)" = "Z" ] || echo "$p"
  done
}

pids=$(alive)
if [ -z "$pids" ]; then
  halrun -U >/dev/null 2>&1
  echo "lcnc_stop: nothing running (board free)"
  exit 0
fi

# 1. polite: SIGTERM the top-level launcher first so it runs its own teardown
for p in $(pgrep -f '[b]in/linuxcnc' 2>/dev/null); do kill -TERM "$p" 2>/dev/null; done
for i in $(seq 1 15); do
  sleep 1
  [ -z "$(alive)" ] && break
done

# 2. still up? TERM whatever remains (svr/task/gui)
if [ -n "$(alive)" ]; then
  for p in $(alive); do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 10); do
    sleep 1
    [ -z "$(alive)" ] && break
  done
fi

# 3. last resort only
if [ -n "$(alive)" ]; then
  echo "lcnc_stop: WARNING -- forcing (something refused SIGTERM)"
  for p in $(alive); do kill -9 "$p" 2>/dev/null; done
  sleep 2
fi

halrun -U >/dev/null 2>&1
sleep 1
# clear the stale lock/shm that causes the "already running / restart?" dialog
rm -f /tmp/linuxcnc.lock /tmp/.emc.lock 2>/dev/null
# NOTE: do NOT ipcrm the shared-memory segments here. Doing so destroys LinuxCNC's NML
# buffers and the NEXT start fails with NML_NO_MASTER_ERROR / shmget failed. LinuxCNC
# cleans up its own shm; a SIGTERM shutdown is sufficient.

"$NED/tools/claim.sh" free "LinuxCNC stopped, board free" >/dev/null 2>&1 || true
if [ -z "$(alive)" ]; then echo "lcnc_stop: clean, board free"; else echo "lcnc_stop: STILL RUNNING"; fi
