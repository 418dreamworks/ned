#!/bin/bash
# move.sh -- unified STANDALONE bench/diagnostic mover for ned.  TESTING ONLY.
# KILLS LinuxCNC + any HAL session on start, loads its OWN HAL (move.hal), owns the
# board, tears everything down on exit. No LinuxCNC needed -- ever.
# Replaces drive_move.sh, maxspeed.sh, enable_force.sh, enable_hold.sh, test_aout.sh.
#
#   move.sh x  -volts V [-time S] [-counts N]    X+W GANTRY together (anti-rack)
#   move.sh y  -volts V [-time S] [-counts N]    Y (pwmgen 01)
#   move.sh z  -volts V [-time S] [-counts N]    Z (pwmgen 02)
#   move.sh w  -volts V [-time S] [-counts N]    W rail alone (RACKS frame -- warns)
#       -volts -10..10 REQUIRED (sign=direction); give -time and/or -counts
#       flags:  -hold   hold until Ctrl-C, auto-abort at +/-3000 encoder counts
#               -meter  force the AOUT only, DRIVES NOT ENABLED, hold to meter TB3
#   move.sh hold                  all 4 axes enabled at 0 V, hold to Ctrl-C
#   move.sh spindle <RPM> <s> [-rev]   Mollom VFD: pwmgen.05 (0..10V -> AI2) + R6/R7
#       needs Mollom powered + F0-02=1 (Terminal run), F0-03=3 (AI2), F4-00=1. START LOW.
#   move.sh rotary <RPM>         both workpiece rotaries, opposite directions, Ctrl-C stop
#   move.sh a  <RPM> <seconds>    head TILT, time-BOUNDED (hard +/-120 stops!)
#   move.sh c  <RPM> <seconds>    head SPIN, time-BOUNDED   (head deg ~= 0.03*RPM*sec)
#
# HOLD: x/y/z/w and a/c END the move HOLDING position (drives stay enabled) --
# Ctrl-C releases + tears down. rotary spins to Ctrl-C; spindle stops after its time.
# SAFETY: open-loop, NO software limits. e-stops released, axis clear, finger on e-stop.

P=hm2_7i97.0
source "$(dirname "${BASH_SOURCE[0]}")/../live/ned_params.sh"   # gear ratios + SCALEs -- SINGLE SOURCE (edit ned_params.sh only)
OUT08=$P.7i84.0.0.output-08     # drive-enable -> R5 -> *7 (R0 + head/rotary contactors)
SONA=$P.7i84.0.0.output-07      # /S-ON head A (tilt) -- head packs cross-wired (motor+enc swapped at the packs)
SONC=$P.7i84.0.0.output-06      # /S-ON head C (spin)
SEN=$P.7i84.0.0.output-04       # head SEN (CN1-42, both packs). Pn515=8882 -> SEN MUST be high with /S-ON or /S-RDY
                                # never comes up and the pack stays BB (manual 6.1.9 L11711-15). Costless to hold high.
HAL="$(dirname "$(readlink -f "$0")")/move.hal"

usage(){ awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "$0"; exit 1; }
case "$1" in ""|-h|--help|help) usage ;; esac
axis="$1"; shift

# ---------- own the board: kill LinuxCNC + any HAL session, load our own ----------
pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing running LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."
sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED to start -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

# --- HARD AIR INTERLOCK: air is a prerequisite -- move NOTHING without it ------
# input-12 / *37, fail-safe: TRUE=air OK; FALSE/unreadable => refuse (drives + spindle).
air=$(halcmd getp $P.inmux.00.input-12 2>/dev/null)
if [ "$air" != "TRUE" ]; then
  echo "🛑 AIR NOT CONNECTED (input-12/*37 = ${air:-unreadable}) -- refusing to move anything (drives + spindle)."
  echo "   Connect air (spindle air-seal + drawbar) and retry."
  kill "$HALPID" 2>/dev/null; halrun -U >/dev/null 2>&1   # trap not set yet -- clean up here
  exit 1
fi
echo "  air pressure: OK (*37/input-12)"

alloff(){
  halcmd sets gvel 0 2>/dev/null; halcmd sets gen 0 2>/dev/null   # gantry shared signals, if made
  for i in 00 01 02 03; do halcmd setp $P.stepgen.$i.velocity-cmd 0 2>/dev/null; halcmd setp $P.stepgen.$i.enable 0 2>/dev/null; done
  for i in 00 01 02 03 04 05; do halcmd setp $P.pwmgen.$i.value 0 2>/dev/null; halcmd setp $P.pwmgen.$i.enable 0 2>/dev/null; done
  for o in output-04 output-06 output-07 output-08 output-09 output-10; do halcmd setp $P.7i84.0.0.$o 0 2>/dev/null; done
}
teardown(){ echo; echo ">>> stop + all off"; alloff; sleep 0.5; kill "$HALPID" 2>/dev/null; halrun -U >/dev/null 2>&1; echo "done."; }
trap 'teardown; exit' EXIT INT TERM

estop_ok(){ [ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" = "TRUE" ]; }

case "$axis" in

# ================= STEPGEN: workpiece rotary pair (stepgen 00/01) =================
rotary|rot)
  RPM="$1"; [ -z "$RPM" ] && { echo "usage: move.sh rotary <RPM>"; exit 1; }
  REVS=$(awk "BEGIN{printf \"%.4f\", $RPM/60}")
  halcmd setp $OUT08 1; echo "drive-enable on (R11 -> 70V brick); settling 1.5s"; sleep 1.5
  halcmd setp $P.stepgen.00.enable 1; halcmd setp $P.stepgen.01.enable 1
  halcmd setp $P.stepgen.00.velocity-cmd "$REVS"; halcmd setp $P.stepgen.01.velocity-cmd "-$REVS"
  echo "spinning BOTH rotary steppers at $RPM RPM, opposite. Ctrl-C to stop."
  while kill -0 "$HALPID" 2>/dev/null; do
    V0=$(halcmd getp $P.stepgen.00.velocity-fb 2>/dev/null); V1=$(halcmd getp $P.stepgen.01.velocity-fb 2>/dev/null)
    printf '  s00 ~ %.0f RPM   s01 ~ %.0f RPM   (target %s)\n' "$(awk "BEGIN{print ${V0:-0}*60}")" "$(awk "BEGIN{print ${V1:-0}*60}")" "$RPM"
    sleep 1
  done ;;

# ================= STEPGEN: head A (tilt) / C (spin) =================
a|c)
  if [ "$axis" = a ]; then SG=$P.stepgen.03; SON=$SONA; GEAR=$GEAR_A; else SG=$P.stepgen.02; SON=$SONC; GEAR=$GEAR_C; fi
  # ---- precise degree move (position mode):  move.sh a deg 45   /   move.sh c deg -45 ----
  if [ "$1" = deg ]; then
    DEG="$2"; [ -z "$DEG" ] && { echo "usage: move.sh $axis deg <degrees>"; exit 1; }
    REVS=$(awk "BEGIN{printf \"%.5f\", $DEG*$GEAR/360}")   # axis deg -> motor-rev (gear from ned_params.sh: A=$GEAR_A / C=$GEAR_C)
    halcmd setp $OUT08 1; halcmd setp $SON 1; halcmd setp $SEN 1; echo "drive-enable + /S-ON + SEN; settling 3s"; sleep 3
    halcmd setp $SG.control-type 0; halcmd setp $SG.position-cmd 0; halcmd setp $SG.enable 1
    for n in 0 1 2 3 4 5 6 7 8 9; do eb[$n]=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null); done
    echo ">>> head $axis -> $DEG deg ($REVS motor-rev), position mode. NO soft limits -- ensure clearance. e-stop ready."
    halcmd setp $SG.position-cmd "$REVS"
    for k in $(seq 1 60); do
      pf=$(halcmd getp $SG.position-fb 2>/dev/null)
      enc=""; for n in 0 1 2 3 4 5 6 7 8 9; do r=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null); enc+=$(printf "e%s=%+d " "$n" "$(( ${r:-0} - ${eb[$n]:-0} ))"); done
      printf '  pos-fb %.3f / %.3f rev   %s\n' "${pf:-0}" "$REVS" "$enc"
      awk "BEGIN{d=${pf:-0}-$REVS; exit !(d<0.01 && d>-0.01)}" && { echo ">>> reached $DEG deg. HOLDING (Ctrl-C releases)."; break; }
      sleep 0.5
    done
    while true; do sleep 1; done
  fi
  RPM="$1"; SECS="$2"
  { [ -z "$RPM" ] || [ -z "$SECS" ]; } && { echo "usage: move.sh $axis <RPM> <seconds>   |   move.sh $axis deg <degrees>"; exit 1; }
  awk "BEGIN{exit !($SECS>0 && $SECS<=30)}" 2>/dev/null || { echo "seconds must be 0..30"; exit 1; }
  REVS=$(awk "BEGIN{printf \"%.4f\", $RPM/60}")
  halcmd setp $OUT08 1; halcmd setp $SON 1; halcmd setp $SEN 1
  echo "drive-enable + /S-ON + SEN asserted; settling 3s"; sleep 3
  halcmd setp $SG.enable 1; halcmd setp $SG.velocity-cmd "$REVS"
  echo ">>> head $axis @ $RPM motor-RPM for ${SECS}s ($(date +%H:%M:%S)). e-stop ready."
  for n in 0 1 2 3 4 5 6 7 8 9; do eb[$n]=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null); done   # head fb baselines (7I85 e6-e9)
  echo "    watching head encoders e6-e9 (raw delta) -- the column that MOVES is $axis's feedback channel"
  loops=$(awk "BEGIN{printf \"%d\",($SECS/0.5)+0.5}")
  for ((k=1;k<=loops;k++)); do
    V=$(halcmd getp $SG.velocity-fb 2>/dev/null)
    enc=""; for n in 0 1 2 3 4 5 6 7 8 9; do r=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null); enc+=$(printf "e%s=%+d " "$n" "$(( ${r:-0} - ${eb[$n]:-0} ))"); done
    printf '  +%.1fs  ~ %.0f RPM   %s\n' "$(awk "BEGIN{print $k*0.5}")" "$(awk "BEGIN{print ${V:-0}*60}")" "$enc"
    sleep 0.5
  done
  halcmd setp $SG.velocity-cmd 0
  echo ">>> ${SECS}s elapsed. HOLDING position (servo stays enabled). Ctrl-C to release."
  while true; do sleep 1; done ;;

# ================= SPINDLE (Mollom VFD) =================
spindle|s)
  RPM="$1"; SECS="$2"; REL=$P.7i84.0.0.output-09; DIR=FWD
  [ "$3" = -rev ] && { REL=$P.7i84.0.0.output-10; DIR=REV; }
  case "$RPM" in -*) RPM="${RPM#-}"; REL=$P.7i84.0.0.output-10; DIR=REV ;; esac   # -500 = reverse
  { [ -z "$RPM" ] || [ -z "$SECS" ]; } && { echo "usage: move.sh spindle <RPM> <seconds> [-rev]   (start LOW, e.g. 500 3)"; exit 1; }
  awk "BEGIN{exit !($SECS>0 && $SECS<=60)}" 2>/dev/null || { echo "seconds must be 0..60"; exit 1; }
  estop_ok || { echo "E-STOP ENGAGED (input-04 != TRUE) -> Mollom S3 faults (Err15). Abort."; exit 1; }
  halcmd setp $REL 1                                      # R6->S1 FWD  (or R7->S2 REV)
  halcmd setp $P.pwmgen.05.value "$RPM"; halcmd setp $P.pwmgen.05.enable 1   # AOUT5=TB3-24, scale 18000 = 10V
  echo ">>> SPINDLE $DIR @ $RPM RPM for ${SECS}s ($(date +%H:%M:%S)). e-stop ready."
  loops=$(awk "BEGIN{printf \"%d\",($SECS/0.5)+0.5}")
  for ((k=1;k<=loops;k++)); do
    RUN=$(halcmd getp $P.inmux.00.input-11 2>/dev/null); FLT=$(halcmd getp $P.inmux.00.input-13 2>/dev/null)
    printf '  +%.1fs  vfd-running=%s  vfd-fault=%s\n' "$(awk "BEGIN{print $k*0.5}")" "${RUN:-?}" "${FLT:-?}"
    [ "$FLT" = "TRUE" ] && { echo "  !! VFD FAULT asserted -> stopping"; break; }
    sleep 0.5
  done ;;

# ================= PWMGEN: hold all at 0 V =================
hold)
  estop_ok || { echo "E-STOP ENGAGED -> enable does nothing. Abort."; exit 1; }
  halcmd setp $OUT08 1
  for i in 00 01 02 03; do halcmd setp $P.pwmgen.$i.value 0; halcmd setp $P.pwmgen.$i.enable 1; done
  echo ">>> ALL DRIVES ENABLED at 0 V. Bus up; axes stiff by hand. Ctrl-C to release."
  while true; do sleep 1; done ;;

# ================= PWMGEN axes =================
x|y|z|w)
  case "$axis" in
    x) idx=00; scale=50; tb="TB3 pin 4 (AOUT0) vs pin 3 (GND)" ;;
    y) idx=01; scale=50; tb="TB3 pin 8 (AOUT1) vs pin 7 (GND)" ;;
    z) idx=02; scale=40; tb="TB3 pin 12 (AOUT2) vs pin 11 (GND)" ;;
    w) idx=03; scale=50; tb="TB3 pin 16 (AOUT3) vs pin 15 (GND)" ;;
  esac
  volts=""; secs=""; counts=""; mode=move
  while [ $# -gt 0 ]; do case "$1" in
    -volts) volts="$2"; shift 2 ;; -time) secs="$2"; shift 2 ;; -counts) counts="$2"; shift 2 ;;
    -hold) mode=hold; shift ;; -meter) mode=meter; shift ;;
    *) echo "unknown argument: $1"; exit 1 ;; esac; done
  [ -z "$volts" ] && { echo "-volts is REQUIRED"; exit 1; }
  awk "BEGIN{exit !($volts>=-10 && $volts<=10)}" 2>/dev/null || { echo "voltage must be -10..10"; exit 1; }
  cmd=$(awk "BEGIN{printf \"%.4f\", $volts/10.0*$scale}")
  MEN=$P.pwmgen.00.enable          # 7I97: pwmgen.00.enable gates the whole 0-3 group

  if [ "$mode" = meter ]; then
    halcmd setp $P.pwmgen.$idx.value "$cmd"; halcmd setp $P.pwmgen.$idx.enable 1; halcmd setp $MEN 1
    echo ">>> $axis AOUT forced to ${volts} V (value=$cmd), DRIVES OFF."
    echo ">>> METER: $tb  -- Ctrl-C when done."
    while true; do sleep 1; done
  fi

  [ "$mode" = move ] && [ -z "$secs" ] && [ -z "$counts" ] && { echo "give -time and/or -counts (or -hold)"; exit 1; }
  [ -n "$secs" ] && { awk "BEGIN{exit !($secs>0 && $secs<=60)}" 2>/dev/null || { echo "-time must be 0..60"; exit 1; }; }
  estop_ok || { echo "E-STOP ENGAGED (input-04 != TRUE) -> enable does nothing. Abort."; exit 1; }
  [ "$mode" = hold ] && loops=999999 || loops=$([ -n "$secs" ] && awk "BEGIN{printf \"%d\",($secs/0.25)+0.5}" || echo 240)

  if [ "$axis" = x ]; then
    # gantry: both rails from ONE shared signal -> same servo cycle, can't rack on skewed cmds
    halcmd net gvel $P.pwmgen.00.value $P.pwmgen.03.value
    halcmd net gen  $P.pwmgen.00.enable $P.pwmgen.03.enable
    x0=$(halcmd getp $P.encoder.00.count 2>/dev/null); w0=$(halcmd getp $P.encoder.03.count 2>/dev/null)
    halcmd setp $OUT08 1; echo ">>> ALL DRIVES ENABLED - settling 1s"; sleep 1
    halcmd sets gen 1; halcmd sets gvel "$cmd"
    echo ">>> GANTRY @ ${volts}V ($(date +%H:%M:%S)) -- X/W deltas must track; OPPOSITE sign = RACK. e-stop ready."
    stop=""
    for ((k=1;k<=loops;k++)); do
      xe=$(halcmd getp $P.encoder.00.count 2>/dev/null); we=$(halcmd getp $P.encoder.03.count 2>/dev/null)
      dx=$((xe-x0)); dw=$((we-w0)); adx=${dx#-}; adw=${dw#-}
      printf "    +%.2fs  X.delta=%-8s  W.delta=%-8s  skew=%s\n" "$(awk "BEGIN{print $k*0.25}")" "$dx" "$dw" "$((dx-dw))"
      if [ "$mode" = hold ]; then { [ "$adx" -ge 3000 ] || [ "$adw" -ge 3000 ]; } 2>/dev/null && { stop="AUTO-ABORT >3000"; break; }
      elif [ -n "$counts" ]; then { [ "$adx" -ge "$counts" ] || [ "$adw" -ge "$counts" ]; } 2>/dev/null && { stop="counts"; break; }; fi
      sleep 0.25
    done
    halcmd sets gvel 0; sleep 0.7
    echo "=== X enc $x0 -> $(halcmd getp $P.encoder.00.count 2>/dev/null) | W enc $w0 -> $(halcmd getp $P.encoder.03.count 2>/dev/null) | stop: ${stop:-time} ==="
    echo ">>> HOLDING at 0 V (drives stay enabled). Ctrl-C to release."
    while true; do sleep 1; done
  else
    ENC=$P.encoder.$idx.count
    e0=$(halcmd getp $ENC 2>/dev/null)
    halcmd setp $OUT08 1; echo ">>> ALL DRIVES ENABLED - settling 1s"; sleep 1
    halcmd setp $P.pwmgen.$idx.value "$cmd"; halcmd setp $P.pwmgen.$idx.enable 1; halcmd setp $MEN 1
    [ "$axis" = w ] && echo "!! W ALONE RACKS THE GANTRY -- keep it SHORT/SMALL"
    echo ">>> $axis @ ${volts}V ($(date +%H:%M:%S)) <-- WATCH IT, e-stop ready"
    stop=""
    for ((k=1;k<=loops;k++)); do
      enc=$(halcmd getp $ENC 2>/dev/null); d=$((enc-e0)); ad=${d#-}
      printf "    +%.2fs  enc.%s=%-12s  delta=%s\n" "$(awk "BEGIN{print $k*0.25}")" "$idx" "$enc" "$d"
      if [ "$mode" = hold ]; then [ "$ad" -ge 3000 ] 2>/dev/null && { stop="AUTO-ABORT >3000"; break; }
      elif [ -n "$counts" ]; then [ "$ad" -ge "$counts" ] 2>/dev/null && { stop="counts"; break; }; fi
      sleep 0.25
    done
    halcmd setp $P.pwmgen.$idx.value 0; sleep 0.7
    echo "=== enc.$idx $e0 -> $(halcmd getp $ENC 2>/dev/null) | stop: ${stop:-time} ==="
    echo ">>> HOLDING at 0 V (drives stay enabled). Ctrl-C to release."
    while true; do sleep 1; done
  fi ;;

*) echo "unknown axis: $axis"; usage ;;
esac
exit 0   # EXIT trap runs teardown (all off + session down)
