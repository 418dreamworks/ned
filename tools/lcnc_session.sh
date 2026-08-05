#!/bin/bash
# Print ONLY the current (latest) PB/LinuxCNC session's slice of lcnc.log.
#
# Why this exists: ~/.bashrc wraps EVERY interactive shell into
# logs/term-<stamp>-<pid>.log, so those files contain whatever the terminal
# printed -- including my own tool output. On 2026-08-03 I grepped a term log
# for "Bus error", matched text I had printed myself while investigating, and
# reported four crashes when there had been exactly one. lcnc.log is written
# by run5.sh (`script -q -a -c "linuxcnc ..."`) and carries ONLY what the
# machine session emitted.
#
# SINGLE PASS (2026-08-04): the old grep-for-line-number-then-tail pair raced
# logclean.sh, which rewrites lcnc.log every 20 s -- between the two reads the
# numbers went stale and whole spans of the CURRENT session silently vanished
# from the slice. That artifact read exactly like "the GUI stopped logging"
# and cost a five-restart phantom hunt. One awk pass = one read = no race.
#
# Usage:  tools/lcnc_session.sh            # whole current session
#         tools/lcnc_session.sh ERROR      # grep -i within it
#         tools/lcnc_session.sh -c 'Bus error'   # count within it
set -u
LOG=/home/brains/Documents/ned/lcnc.log
[ -f "$LOG" ] || { echo "no $LOG"; exit 1; }
SLICE=$(awk '/==================== LinuxCNC start/{buf=""} {buf=buf $0 "\n"} \
             END{printf "%s", buf}' "$LOG" | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g')
case "${1:-}" in
  '')  printf '%s\n' "$SLICE" ;;
  -c)  printf '%s\n' "$SLICE" | grep -c "${2:-}" ;;
  *)   printf '%s\n' "$SLICE" | grep -i "$1" ;;
esac
