#!/bin/bash
# rs274 SANDBOX WRAPPER -- installed 2026-08-16.
#
# WHY: rs274 calls tool_mmap_creator() at sai/driver.cc:570, BEFORE getopt()
# at :578. That opens "$HOME/.tool.mmap" O_RDWR|O_CREAT|O_TRUNC
# (tooldata_mmap.cc:33,:134-135) and, with no -t, loads the compiled-in
# sample table common/tool.tbl -- T1/T2/T3/T99999 P123. It happens on EVERY
# invocation, including --help.
#
# WHY IT MATTERS: that file is the LIVE tool table. io, milltask, halui,
# Probe Basic and ned_brain all hold the same inode MAP_SHARED. O_TRUNC keeps
# the inode, so nobody re-maps and nobody is notified: the running machine
# silently adopts the sample table, G43 applies 0.0000, and the spindle
# record stops matching what is clamped. DB_PROGRAM gives no protection --
# ioControl.cc:762 creates the mmap before the DB_ACTIVE branch at :768 --
# and no recovery, because io never re-reads it. -t does not help. Only a
# throwaway HOME does.
S=$(mktemp -d /tmp/rs274_home_XXXXXX)
printf '%s pid=%s ppid=%s cwd=%s argv=%s\n' "$(date '+%F %T.%3N')" \
  "$$" "$PPID" "$PWD" "$*" >> /home/brains/Documents/ned/rs274_calls.txt 2>/dev/null || true
HOME="$S" /usr/bin/rs274.real "$@"
rc=$?
rm -rf "$S"
exit $rc
