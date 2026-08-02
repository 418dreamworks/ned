#!/bin/bash
# logclean.sh -- keep each ned log to the LAST 5 MINUTES OF ITS OWN LOGGED CONTENT
# (span from newest entry's timestamp back 5 min). It is measured by the log's OWN
# timestamps, NOT wall clock -- an untouched log keeps its final 5 min indefinitely,
# nothing is deleted for being "old". Point: short logs are cheap to read (tokens).
# Copy-truncates in place so writer fds keep appending. Background daemon (run5.sh).
NED="/home/brains/Documents/ned"; WIN=5; T="/tmp/logclean.$$"
# keep lines within WIN min of the file's OWN newest "YYYY-MM-DD HH:MM:SS"
keep_dt(){ local f="$1" n ne c; [ -f "$f" ] || return
  n=$(awk 'substr($0,1,4)~/^[0-9][0-9][0-9][0-9]$/{t=substr($0,1,19)}END{print t}' "$f")
  [ -n "$n" ] || return; ne=$(date -d "$n" +%s 2>/dev/null) || return
  c=$(date -d "@$((ne-WIN*60))" '+%F %T')
  awk -v c="$c" 'substr($0,1,19)>=c || substr($0,1,4)!~/^[0-9][0-9][0-9][0-9]$/' "$f" >"$T" 2>/dev/null && cat "$T" >"$f"; }
# keep lines within WIN min of the file's OWN newest "HH:MM:SS"
keep_t(){ local f="$1" n ne c; [ -f "$f" ] || return
  n=$(awk 'substr($0,1,2)~/^[0-9][0-9]$/&&substr($0,3,1)==":"{t=substr($0,1,8)}END{print t}' "$f")
  [ -n "$n" ] || return; ne=$(date -d "$n" +%s 2>/dev/null) || return
  c=$(date -d "@$((ne-WIN*60))" '+%T')
  awk -v c="$c" 'substr($0,1,8)>=c || !(substr($0,1,2)~/^[0-9][0-9]$/&&substr($0,3,1)==":")' "$f" >"$T" 2>/dev/null && cat "$T" >"$f"; }
while true; do
  keep_dt "$NED/gui.md"          # handler event log (full datetime per line)
  keep_t  "$NED/mesa.log"        # mesa pin log (time-of-day per line)
  # lcnc.log has no per-line timestamps -> cap by lines. Keep 2000: a startup traceback
  # is long, and trimming to 300 destroyed the evidence during debugging.
  [ -f "$NED/lcnc.log" ] && tail -n 5000 "$NED/lcnc.log" >"$T" 2>/dev/null && cat "$T" >"$NED/lcnc.log"
  # per-session terminal captures (script, raw/no timestamps) -> cap to recent
  # lines; SKIP any still held open by a live shell (truncating corrupts script).
  if command -v fuser >/dev/null 2>&1; then
    for tl in "$NED"/logs/term-*.log; do
      [ -e "$tl" ] || continue
      fuser -s "$tl" 2>/dev/null && continue
      tail -n 300 "$tl" >"$T" 2>/dev/null && cat "$T" >"$tl"
    done
  fi
  rm -f "$T"
  sleep 20
done
