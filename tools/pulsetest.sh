#!/bin/bash
# pulsetest.sh -- ONE-SHOT (60 s): flips the DIR output of stepgen.02 (A) + stepgen.03 (C)
# every 2 seconds so a DMM can follow it. The DIR line HOLDS a DC level for 2 s, flips, holds 2 s.
#
# KILL SERVO MAIN POWER first (keep control power L1C/L2C). Nothing moves -- the Mesa drives its
# outputs regardless of servo power.
#
#   A DIR pair = 7I85 TB1-5 (DIR-) / TB1-6 (DIR+)      A STEP pair = TB1-3/4
#   C DIR pair = 7I85 TB1-13 (DIR-) / TB1-14 (DIR+)    C STEP pair = TB1-11/12
#
# DMM (DC volts) across a DIR pair, or one leg to Mesa GND: it FLIPS every 1 s (a few volts).
#   At the Mesa TB1 both A and C should flip. Then probe the SAME pair at C's servopack CN1
#   (SIGN=CN1-11, /SIGN=CN1-12): flips there too -> cable OK; flat at CN1 while TB1 flips -> cable.
#   (STEP pulses are microseconds wide -- NOT visible on a DMM, ignore them.)

P=hm2_7i97.0
RPM=6
HAL="$(dirname "$(readlink -f "$0")")/move.hal"

pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."; sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED to start -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

# --- air-pressure warning (input-12 / *37; active-high: TRUE=OK, FALSE=low; fail-safe NC switch) ---
air=$(halcmd getp $P.inmux.00.input-12 2>/dev/null)
case "$air" in
  TRUE)  echo "  air pressure: OK (*37)" ;;
  FALSE) echo "  ⚠️  WARNING: LOW AIR PRESSURE (*37/input-12)" ;;
  *)     echo "  ⚠️  air pressure UNREADABLE (input-12=${air:-?})" ;;
esac

teardown(){ echo; echo ">>> stop + off";
  for i in 02 03; do halcmd setp $P.stepgen.$i.velocity-cmd 0 2>/dev/null; halcmd setp $P.stepgen.$i.enable 0 2>/dev/null; done
  halcmd setp $P.7i84.0.0.output-06 0 2>/dev/null; halcmd setp $P.7i84.0.0.output-07 0 2>/dev/null
  kill "$HALPID" 2>/dev/null; pkill -9 -f "halcmd -f.*move.hal" 2>/dev/null; halrun -U >/dev/null 2>&1; echo done.; }
trap 'teardown; exit' EXIT INT TERM

REVS=$(awk "BEGIN{printf \"%.5f\", $RPM/60}")
halcmd setp $P.7i84.0.0.output-06 1    # /S-ON A -> TB3-23
halcmd setp $P.7i84.0.0.output-07 1    # /S-ON C -> TB3-24
for i in 02 03; do halcmd setp $P.stepgen.$i.enable 1; done
echo ">>> A (TB1-5/6) + C (TB1-13/14) DIR flips every 2 s for 60 s. DMM the DIR pair."
echo ">>> Kill servo MAIN power first. Ctrl-C to stop early."
for k in $(seq 1 30); do
  if (( k % 2 )); then V=$REVS; D="FWD +"; else V="-$REVS"; D="REV -"; fi
  for i in 02 03; do halcmd setp $P.stepgen.$i.velocity-cmd "$V"; done
  printf "\r  +%2ds/60   DIR = %s   (A TB1-5/6,  C TB1-13/14)   " "$((k*2))" "$D"
  sleep 2
done
echo; echo ">>> 60 s done."
