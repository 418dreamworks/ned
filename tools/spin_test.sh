#!/bin/bash
# spin_test.sh — drives the rack solenoid (output-13) every 3 s for 30 s while
# watching the rack sensor (input-29). You change ONLY the tool:
#   0-15 s : tool STATIC  (don't spin it)
#   15-30 s: SPIN the tool
# Rack cycling is the constant baseline; difference between phases = the spin.
# Prints rack state + in29 each second, flags in29 changes, summarizes per phase.
P=hm2_7i97.0.7i84.0.0
OUT=$P.output-13
IN=$P.input-29
echo "================================================================"
echo " Rack solenoid cycles every 3 s the whole time (UNLOCK/LOCK)."
echo "   0-15 s : tool STATIC  (do NOT spin)"
echo "   15-30 s: SPIN the tool"
echo " WARNING: each UNLOCK can drop a loose tool — watch it."
echo "================================================================"
halcmd unlinkp $OUT 2>/dev/null
prev=""; t0=$(date +%s%N); st=0; sp=0; lastbeat=-1
while :; do
  el=$(( ($(date +%s%N) - t0)/1000000000 ))
  [ "$el" -ge 30 ] && break
  if [ $(( (el/3)%2 )) -eq 0 ]; then rs=1; rl="UNLOCK"; else rs=0; rl="LOCK  "; fi
  halcmd setp $OUT $rs 2>/dev/null
  v=$(halcmd getp $IN 2>/dev/null)
  if [ "$el" -lt 15 ]; then ph="STATIC"; else ph="SPIN  "; fi
  if [ "$v" != "$prev" ] && [ -n "$prev" ]; then
    printf "   %2ds %s rack=%s  in29 %s -> %s\n" "$el" "$ph" "$rl" "$prev" "$v"
    [ "$el" -lt 15 ] && st=$((st+1)) || sp=$((sp+1))
  fi
  if [ "$el" != "$lastbeat" ]; then
    printf "%2ds %s rack=%s  in29=%s\n" "$el" "$ph" "$rl" "$v"; lastbeat=$el
  fi
  prev="$v"
  sleep 0.2
done
halcmd setp $OUT 0 2>/dev/null
halcmd net sig-drawbar-clamp $OUT 2>/dev/null
echo "================================================================"
echo " rack LEFT LOCKED, output-13 relinked to sig-drawbar-clamp"
echo " SUMMARY: in29 transitions   STATIC=$st    SPIN=$sp"
echo " (extra transitions in SPIN = the rotating tool passing the sensor)"
echo "================================================================"
