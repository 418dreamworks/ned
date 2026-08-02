#!/bin/bash
# mesalog.sh -- continuously log the FULL Mesa board state to ned/mesa.log, timestamped.
# Captures EVERY hm2_7i97.0 pin every cycle (ONE `halcmd show pin` -> all pins as
# name=value pairs on a single line per snapshot). This is for the ASSISTANT to
# grep/correlate against term.log -- not meant to be read live by a human. It reads
# whatever HAL session is live (e.g. move.sh's halrun). Ctrl-C to stop.
#
# Every pin is captured on purpose: a curated subset once hid output-07 (/S-ON) and
# masked a fault. Names are logged with the "hm2_7i97.0." prefix stripped, e.g.
#   7i84.0.0.output-07=TRUE   stepgen.03.velocity-fb=8.33   encoder.02.count=1234
# grep a timestamp to get the whole board state on one line; grep a pin name to trend it.
P=hm2_7i97.0
LOG=/home/brains/Documents/ned/mesa.log
: > "$LOG"
echo "logging FULL Mesa state (every pin) to $LOG  (Ctrl-C to stop)"
n=0
while true; do
  TS=$(date +%H:%M:%S.%3N)
  # ONE halcmd call dumps all pins; awk emits "<stripped-name>=<value>" for each,
  # value is the field immediately before the hm2_7i97.0.* name (halcmd's Value col).
  SNAP=$(halcmd show pin $P 2>/dev/null | awk '
    { for(i=1;i<=NF;i++) if($i ~ /^hm2_7i97\.0\./){ nm=$i; sub(/^hm2_7i97\.0\./,"",nm); printf "%s=%s ", nm, $(i-1); break } }
  ')
  if [ -z "$SNAP" ]; then
    printf '%s  --- no HAL session ---\n' "$TS" >> "$LOG"
  else
    printf '%s  %s\n' "$TS" "$SNAP" >> "$LOG"
  fi
  # prune to ~last hour (18000 snapshots @ 0.2s); rewrite every 2 min to spare the SD.
  n=$((n+1)); [ $((n % 600)) -eq 0 ] && { tail -n 18000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"; }
  sleep 0.2
done
