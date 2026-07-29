#!/bin/bash
# testall.sh -- simultaneous ALL-AXIS demo. Everything moves at once, relative to the start point
# (assumed to be the CENTER of a 6" sphere with room around the head/gantry).
#   XYZ     : slow oscillation, feedback-BOUNDED to stay inside the 6" sphere (3" radius; 0.5"/axis).
#             Aborts XYZ if the vector leaves the sphere OR any limit switch trips.
#   A / C   : head, +/-20 deg  (stepgen position; A=stepgen.03, C=stepgen.02 -- packs cross-wired).
#   B       : workpiece rotary pair, spins fwd/rev (no limit).
#   spindle : 6000 rpm -- ramps up, runs, then stops mid-demo.
# Runs ~DURATION s, then stops everything and tears down. Open-loop drives, NO soft limits beyond
# the sphere/limit checks here. e-stop READY. Clear the work envelope first. START small.

P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
SONA=$P.7i84.0.0.output-07          # A tilt /S-ON (packs cross-wired)
SONC=$P.7i84.0.0.output-06          # C spin /S-ON
SPFWD=$P.7i84.0.0.output-09         # spindle FWD relay (R6)
HAL="$(dirname "$(readlink -f "$0")")/move.hal"

DURATION=25
BOUND_IN=0.5                        # inches per axis (sqrt(3)*0.5 = 0.87" vector, well inside 3")
SPHERE_IN=2.0                       # inch vector -> abort XYZ
VJOG=0.4                            # jog volts for XYZ (slow)
CPI_X=5080 ; CPI_Y=6350 ; CPI_Z=20000    # encoder counts/inch (200/250/787.4 c/mm x 25.4)
ACREV=$(awk "BEGIN{print 20*200/360}")   # 20 deg head = 11.11 motor rev (200:1 worm, scale 8192)
BRPS=1.0                            # rotary 60 rpm -> 1 rev/s
FLIP=25                             # cycles (=5 s) between A/C target flip + B reversal
DT=0.2

pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."; sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

alloff(){
  halcmd sets gvel 0 2>/dev/null
  for i in 00 01 02 03; do halcmd setp $P.pwmgen.$i.value 0 2>/dev/null; halcmd setp $P.pwmgen.$i.enable 0 2>/dev/null; done
  halcmd setp $P.pwmgen.05.value 0 2>/dev/null; halcmd setp $P.pwmgen.05.enable 0 2>/dev/null
  for i in 00 01 02 03; do halcmd setp $P.stepgen.$i.velocity-cmd 0 2>/dev/null; halcmd setp $P.stepgen.$i.enable 0 2>/dev/null; done
  for o in output-06 output-07 output-08 output-09 output-10; do halcmd setp $P.7i84.0.0.$o 0 2>/dev/null; done
}
teardown(){ echo; echo ">>> STOP ALL"; alloff; sleep 0.6; kill "$HALPID" 2>/dev/null; pkill -9 -f "halcmd -f.*move.hal" 2>/dev/null; halrun -U >/dev/null 2>&1; echo done.; }
trap 'teardown; exit' EXIT INT TERM

[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" = TRUE ] || { echo "E-STOP engaged (input-04 != TRUE) -- abort."; exit 1; }

echo ">>> ALL DRIVES ENABLING. Clear the envelope, finger on e-stop. Starting in 3s..."; sleep 3
halcmd setp $OUT08 1; halcmd setp $SONA 1; halcmd setp $SONC 1
# gantry: X + W share one signal (anti-rack)
halcmd net gvel $P.pwmgen.00.value $P.pwmgen.03.value
halcmd net gen  $P.pwmgen.00.enable $P.pwmgen.03.enable
halcmd sets gen 1
for i in 01 02; do halcmd setp $P.pwmgen.$i.enable 1; done
sleep 1.5
# A/C position mode, B velocity mode (move.hal default control-type 1)
for i in 02 03; do halcmd setp $P.stepgen.$i.control-type 0; halcmd setp $P.stepgen.$i.position-cmd 0; halcmd setp $P.stepgen.$i.enable 1; done
for i in 00 01; do halcmd setp $P.stepgen.$i.enable 1; done
# spindle up to 6000
halcmd setp $SPFWD 1; halcmd setp $P.pwmgen.05.value 6000; halcmd setp $P.pwmgen.05.enable 1
echo ">>> spindle -> 6000 rpm (Mollom ramps ~10s)"

readarray -t S < <(printf "getp $P.encoder.0%s.count\n" 0 1 2 | halcmd -f /dev/stdin 2>/dev/null)
x0=${S[0]}; y0=${S[1]}; z0=${S[2]}
bx=$(awk "BEGIN{print $BOUND_IN*$CPI_X}"); by=$(awk "BEGIN{print $BOUND_IN*$CPI_Y}"); bz=$(awk "BEGIN{print $BOUND_IN*$CPI_Z}")
cx=$(awk "BEGIN{printf \"%.3f\",$VJOG/10*50}"); cy=$cx; cz=$(awk "BEGIN{printf \"%.3f\",$VJOG/10*40}")
dx=1; dy=1; dz=1; acs=1; bs=1; spun_down=0
cyc=$(awk "BEGIN{print int($DURATION/$DT)}")
halcmd setp $P.stepgen.03.position-cmd "$ACREV"; halcmd setp $P.stepgen.02.position-cmd "$ACREV"
halcmd setp $P.stepgen.00.velocity-cmd "$BRPS"; halcmd setp $P.stepgen.01.velocity-cmd "-$BRPS"

for ((k=1;k<=cyc;k++)); do
  readarray -t V < <(printf "getp $P.encoder.00.count\ngetp $P.encoder.01.count\ngetp $P.encoder.02.count\ngetp $P.inmux.00.input-05\ngetp $P.inmux.00.input-06\ngetp $P.inmux.00.input-07\ngetp $P.inmux.00.input-08\ngetp $P.inmux.00.input-09\ngetp $P.inmux.00.input-10\n" | halcmd -f /dev/stdin 2>/dev/null)
  ex=$((${V[0]}-x0)); ey=$((${V[1]}-y0)); ez=$((${V[2]}-z0))
  [ "$ex" -ge "$bx" ] 2>/dev/null && dx=-1; [ "$ex" -le "-$bx" ] 2>/dev/null && dx=1
  [ "$ey" -ge "$by" ] 2>/dev/null && dy=-1; [ "$ey" -le "-$by" ] 2>/dev/null && dy=1
  [ "$ez" -ge "$bz" ] 2>/dev/null && dz=-1; [ "$ez" -le "-$bz" ] 2>/dev/null && dz=1
  vec=$(awk "BEGIN{print sqrt(($ex/$CPI_X)^2+($ey/$CPI_Y)^2+($ez/$CPI_Z)^2)}")
  halt=0
  awk "BEGIN{exit !($vec>$SPHERE_IN)}" && { halt=1; echo; echo "!! SPHERE limit ($vec in) -- XYZ held"; }
  for i in 3 4 5 6 7 8; do [ "${V[$i]}" = FALSE ] && halt=1; done   # any XYZ limit tripped
  if [ "$halt" = 1 ]; then xv=0; yv=0; zv=0; else
    xv=$(awk "BEGIN{print $dx*$cx}"); yv=$(awk "BEGIN{print $dy*$cy}"); zv=$(awk "BEGIN{print $dz*$cz}")
  fi
  printf "sets gvel %s\nsetp $P.pwmgen.01.value %s\nsetp $P.pwmgen.02.value %s\n" "$xv" "$yv" "$zv" | halcmd -f /dev/stdin 2>/dev/null

  if (( k % FLIP == 0 )); then
    acs=$(( -acs )); bs=$(( -bs ))
    at=$(awk "BEGIN{print $acs*$ACREV}"); bv=$(awk "BEGIN{print $bs*$BRPS}"); nbv=$(awk "BEGIN{print -$bs*$BRPS}")
    printf "setp $P.stepgen.03.position-cmd %s\nsetp $P.stepgen.02.position-cmd %s\nsetp $P.stepgen.00.velocity-cmd %s\nsetp $P.stepgen.01.velocity-cmd %s\n" "$at" "$at" "$bv" "$nbv" | halcmd -f /dev/stdin 2>/dev/null
  fi
  # stop the spindle ~60% through, so start AND stop both show
  if [ "$spun_down" = 0 ] && (( k >= cyc*3/5 )); then halcmd setp $P.pwmgen.05.value 0; echo; echo ">>> spindle STOP (decelerating)"; spun_down=1; fi

  printf "\r  +%2ds/%s  X.d=%-7s Y.d=%-7s Z.d=%-7s vec=%.2fin  A/C=%+.0fdeg  " \
    "$(awk "BEGIN{printf \"%.0f\",$k*$DT}")" "$DURATION" "$ex" "$ey" "$ez" "$vec" "$(awk "BEGIN{print $acs*20}")"
  sleep "$DT"
done
echo; echo ">>> demo complete."
