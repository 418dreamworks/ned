#!/bin/bash
# lcnc.sh -- launch LinuxCNC with ALL of its terminal output (operator errors shown in the
# Axis status bar, task/io/motion/HAL messages, tracebacks) teed to ned/lcnc.log, so the log
# can be read at any time. USE THIS INSTEAD OF calling `linuxcnc ...ned.ini` directly.
#
#   bash ned/tools/lcnc.sh
#
# The log is appended (a dated banner per launch) and kept to the last ~5000 lines.
LOG="$(dirname "$(readlink -f "$0")")/../lcnc.log"
INI="$HOME/linuxcnc/configs/ned/ned.ini"

{ echo; echo "================ LAUNCH $(date '+%F %T') ================"; } >> "$LOG"
# line-buffer both sides so the log is current the instant a message prints
stdbuf -oL -eL linuxcnc "$INI" 2>&1 | stdbuf -oL tee -a "$LOG"

# prune on exit
tail -n 5000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
