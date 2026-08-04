#!/bin/bash
# toolmmap_watch.sh -- convict the SIGBUS. Every 2 s, log: milltask fd count
# (issue #1088 dies at ~1024), and the /tmp tool mmap file's inode + size
# (a SIGBUS mid-read means the backing file shrank or was replaced -- an
# inode or size change here, timestamped, is the conviction). Log ONLY on
# change. Appends to ned/screen.log so it lines up with the crash clock.
LOG=/home/brains/Documents/ned/screen.log
prev=""
echo "$(date '+%F %T') toolmmap_watch start" >> "$LOG"
while true; do
  MT=$(pgrep -x milltask | head -1)
  if [ -n "$MT" ]; then
    fds=$(ls /proc/$MT/fd 2>/dev/null | wc -l)
    # the REAL backing file (found via /proc/<milltask>/maps 2026-08-04):
    # /home/brains/.tool.mmap -- the /tmp string in the binary is a fallback
    mm=$(stat -c '%i:%s' /home/brains/.tool.mmap 2>/dev/null)
    cur="milltask=$MT fds=$fds mmap=$mm"
  else
    cur="milltask=DOWN"
  fi
  if [ "$cur" != "$prev" ]; then
    echo "$(date '+%F %T.%2N') toolmmap: $cur" >> "$LOG"
    prev="$cur"
  fi
  sleep 2
done
