#!/bin/bash
SP=/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad
OUT=/home/brains/Documents/ned/logs/acerr-$(date +%Y%m%d-%H%M%S).log
echo "# t ex ey ez ew A C jx jy jz" > "$OUT"; echo "$OUT"
while :; do
  v=$(timeout 2 halcmd -f "$SP/acerr_cmds.txt" 2>/dev/null | tr '\n' ' ')
  [ -n "$v" ] && printf '%s %s\n' "$(date +%s.%3N)" "$v" >> "$OUT"
  sleep 0.15
done
