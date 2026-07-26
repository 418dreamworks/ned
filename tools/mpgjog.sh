#!/bin/bash
# mpgjog.sh -- STANDALONE pendant MPG-jog test (unit test for the jog HAL wiring).
# Mirrors move.sh: KILLS LinuxCNC + any HAL session, loads move.hal, owns the board,
# tears down on exit. Jogs all 6 axes off the handwheel:
#   turn wheel        -> jog the SELECTED axis
#   TAP button        -> next axis   (X -> Y -> Z -> A -> C -> B(rotary) -> X)
#   HOLD button       -> speed-select (LINEAR axes only): wheel LEFT=slow / RIGHT=fast /
#                        just-hold=med; release latches. (Head/rotary are single-speed.)
#
#   X/Y/Z  pwmgen velocity jog, 3 speeds (jog VOLTAGE). Open-loop: NO decel ramp (jerks at
#          the stop -- that is the missing accel/decel, fixed by MAX_ACCELERATION in LinuxCNC).
#          Limit switch hit -> blocks motion INTO it, allows away.
#   A/C    head, stepgen POSITION mode (precise): 1 arcmin per detent, very slow.
#          Software stops: A +/-120 deg, C +/-320 deg (clamped target).
#   B      workpiece rotary PAIR (stepgen 00 +, 01 -, counter-rotating), 0.1 deg/detent.
#
#   mpgjog.sh          DRY-RUN: reads button/wheel/limits + shows the logic, DRIVES NOTHING
#   mpgjog.sh arm      ENERGIZES drives (+ head /S-ON) and actually jogs
#
# Head/rotary detents are EXACT only if the gear ratios are right (head 200:1 worm, rotary
# 20:1 -- from calibration_plan.md / ned.ini). Position mode is relative to the arm point
# (stepgen starts at 0), not absolute. Run DRY first. e-stop ready, axis clear, START SLOW.

P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08          # drive-enable -> R5 -> *7
SONA=$P.7i84.0.0.output-07 ; SONC=$P.7i84.0.0.output-06   # head /S-ON A/C -- head packs cross-wired
HAL="$(dirname "$(readlink -f "$0")")/move.hal"

# ---- tunables ----
SLOW_V=0.10 ; MED_V=0.25 ; FAST_V=0.50   # X/Y/Z jog voltages (of 10 V) slow/med/fast
HOLD_T=0.4 ; GESTURE=6 ; IDLE_T=0.15 ; DT=0.05 ; CPD=4
# stepgen axes (A C B): degrees per detent, gear (motor-rev per axis-rev), soft limits (deg)
DEG_A=0.016667 ; DEG_C=0.016667 ; DEG_B=0.1       # 1' / 1' / 0.1 deg per detent
GEAR_A=200 ; GEAR_C=200 ; GEAR_B=20
LO_A=-120 ; HI_A=120 ; LO_C=-320 ; HI_C=320 ; LO_B=-100000 ; HI_B=100000

AXNAME=(X Y Z A C B) ; KIND=(vel vel vel pos pos pos) ; SPNAME=(SLOW MED FAST)
SV=("$SLOW_V" "$MED_V" "$FAST_V") ; SCALE=(50 50 40)   # pwmgen scale X/Y/Z (W shares X=50)
POS=(input-05 input-07 input-10) ; NEG=(input-06 input-08 input-09)   # X/Y/Z limit inputs

MODE=dry ; [ "$1" = arm ] && MODE=arm
case "$1" in ""|arm) ;; -h|--help|help) awk 'NR==1{next}/^#/{sub(/^# ?/,"");print;next}{exit}' "$0"; exit 0 ;; *) echo "usage: mpgjog.sh [arm]"; exit 1 ;; esac

# ---- own the board ----
pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing running LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."
sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED to start -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

alloff(){
  for i in 00 01 02 03; do halcmd setp $P.pwmgen.$i.value 0 2>/dev/null; halcmd setp $P.pwmgen.$i.enable 0 2>/dev/null; done
  for i in 00 01 02 03; do halcmd setp $P.stepgen.$i.enable 0 2>/dev/null; done
  for o in output-06 output-07 output-08; do halcmd setp $P.7i84.0.0.$o 0 2>/dev/null; done
}
teardown(){ echo; echo ">>> stop + all off"; alloff; sleep 0.4; kill "$HALPID" 2>/dev/null; pkill -9 -f "halcmd -f.*move.hal" 2>/dev/null; halrun -U >/dev/null 2>&1; echo "done."; }
trap 'teardown; exit' EXIT INT TERM

PINS=(inmux.00.input-00 encoder.04.count encoder.00.count encoder.01.count encoder.02.count
      inmux.00.input-05 inmux.00.input-06 inmux.00.input-07 inmux.00.input-08
      inmux.00.input-09 inmux.00.input-10 inmux.00.input-04)
readpins(){ mapfile -t V < <(printf "getp $P.%s\n" "${PINS[@]}" | halcmd -f /dev/stdin 2>/dev/null); }

# motor-rev per COUNT and rev soft-limits (position-cmd is in motor-rev; scale from move.hal)
RD_A=$(awk "BEGIN{print $DEG_A*$GEAR_A/360/$CPD}") ; RD_C=$(awk "BEGIN{print $DEG_C*$GEAR_C/360/$CPD}") ; RD_B=$(awk "BEGIN{print $DEG_B*$GEAR_B/360/$CPD}")
RLO_A=$(awk "BEGIN{print $LO_A*$GEAR_A/360}") ; RHI_A=$(awk "BEGIN{print $HI_A*$GEAR_A/360}")
RLO_C=$(awk "BEGIN{print $LO_C*$GEAR_C/360}") ; RHI_C=$(awk "BEGIN{print $HI_C*$GEAR_C/360}")
RLO_B=$(awk "BEGIN{print $LO_B*$GEAR_B/360}") ; RHI_B=$(awk "BEGIN{print $HI_B*$GEAR_B/360}")
RD=("" "" "" "$RD_A" "$RD_C" "$RD_B") ; RLO=("" "" "" "$RLO_A" "$RLO_C" "$RLO_B") ; RHI=("" "" "" "$RHI_A" "$RHI_C" "$RHI_B")
D2R=("" "" "" "$(awk "BEGIN{print 360/$GEAR_A}")" "$(awk "BEGIN{print 360/$GEAR_C}")" "$(awk "BEGIN{print 360/$GEAR_B}")")  # motor-rev -> axis-deg

# ---- arm ----
if [ "$MODE" = arm ]; then
  readpins
  [ "${V[11]}" = TRUE ] || { echo "E-STOP ENGAGED (input-04 != TRUE) -> enable does nothing. Abort."; exit 1; }
  echo ">>> ARMING: drive-enable + head /S-ON, X/Y/Z at 0 V, stepgens -> position mode. settling 1.5s"
  halcmd setp $OUT08 1 ; halcmd setp $SONA 1 ; halcmd setp $SONC 1
  for i in 00 01 02 03; do halcmd setp $P.pwmgen.$i.value 0; halcmd setp $P.pwmgen.$i.enable 1; done
  for i in 00 01 02 03; do halcmd setp $P.stepgen.$i.control-type 0; halcmd setp $P.stepgen.$i.position-cmd 0; halcmd setp $P.stepgen.$i.enable 1; done
  sleep 1.5
else
  echo ">>> DRY-RUN: nothing will move. Turn the wheel / tap+hold the button to watch the logic."
fi

# ---- state ----
ax=0 ; sp=1 ; held=0 ; prev_pressed=0 ; press_t=0 ; c_hold=0
tgt=(0 0 0 0 0 0)          # stepgen targets (motor-rev) for A(3) C(4) B(5)
readpins ; prev_mpg=${V[1]} ; last_move=0 ; dir=1 ; prev_sel_enc=0 ; prev_ax=0
echo ">>> ${MODE^^}. selected=X. tap=next axis, hold+wheel=speed (X/Y/Z). Ctrl-C to quit."

while kill -0 "$HALPID" 2>/dev/null; do
  readpins
  now=$(date +%s.%N)
  btn=${V[0]} ; mpg=${V[1]}
  pressed=0 ; [ "$btn" = FALSE ] && pressed=1

  # ---- button state machine ----
  if [ "$pressed" = 1 ] && [ "$prev_pressed" = 0 ]; then press_t=$now ; held=0 ; fi
  if [ "$pressed" = 1 ]; then
    if [ "$held" = 0 ] && awk "BEGIN{exit !($now-$press_t>=$HOLD_T)}"; then held=1 ; sp=1 ; c_hold=$mpg ; fi
    if [ "$held" = 1 ] && [ "${KIND[$ax]}" = vel ]; then
      d=$((mpg - c_hold)) ; nsp=1
      [ "$d" -le "-$GESTURE" ] && nsp=0 ; [ "$d" -ge "$GESTURE" ] && nsp=2
      [ "$nsp" != "$sp" ] && { sp=$nsp ; printf '\n  speed -> %s\n' "${SPNAME[$sp]}" ; }
    fi
  fi
  if [ "$pressed" = 0 ] && [ "$prev_pressed" = 1 ] && [ "$held" = 0 ]; then
    ax=$(((ax+1)%6)) ; printf '\n  axis  -> %s\n' "${AXNAME[$ax]}"
  fi
  prev_pressed=$pressed

  dmpg=$((mpg - prev_mpg)) ; prev_mpg=$mpg
  v00=0;v01=0;v02=0;v03=0 ; gate="" ; info=""

  if [ "${KIND[$ax]}" = vel ]; then
    # ---- pwmgen velocity jog (X/Y/Z) + hardware limit gate ----
    velv=0
    if [ "$pressed" = 0 ]; then
      if [ "$dmpg" -ne 0 ]; then [ "$dmpg" -gt 0 ] && dir=1 || dir=-1 ; last_move=$now ; fi
      awk "BEGIN{exit !($now-$last_move<$IDLE_T)}" && velv=$(awk "BEGIN{print $dir*${SV[$sp]}}")
    fi
    case ${POS[$ax]} in input-05)pl=${V[5]};; input-07)pl=${V[7]};; input-10)pl=${V[10]};; esac
    case ${NEG[$ax]} in input-06)nl=${V[6]};; input-08)nl=${V[8]};; input-09)nl=${V[9]};; esac
    awk "BEGIN{exit !($velv>0)}" && [ "$pl" = FALSE ] && { velv=0 ; gate="+LIM"; }
    awk "BEGIN{exit !($velv<0)}" && [ "$nl" = FALSE ] && { velv=0 ; gate="-LIM"; }
    selenc=${V[$((ax+2))]}
    if [ "$ax" = "$prev_ax" ]; then
      [ "$pl" = FALSE ] && [ "$selenc" -gt "$prev_sel_enc" ] 2>/dev/null && { velv=0 ; gate="+LIM!"; }
      [ "$nl" = FALSE ] && [ "$selenc" -lt "$prev_sel_enc" ] 2>/dev/null && { velv=0 ; gate="-LIM!"; }
    fi
    prev_sel_enc=$selenc
    c=$(awk "BEGIN{printf \"%.3f\",$velv/10*${SCALE[$ax]}}")
    case $ax in 0) v00=$c ; v03=$c ;; 1) v01=$c ;; 2) v02=$c ;; esac
    info=$(printf 'vel:%+5.2fV lim[+:%s -:%s]%s' "$velv" "$([ "$pl" = FALSE ]&&echo HIT||echo .)" "$([ "$nl" = FALSE ]&&echo HIT||echo .)" " $gate")
  else
    # ---- stepgen position jog (A/C/B), software-clamped ----
    if [ "$pressed" = 0 ] && [ "$dmpg" -ne 0 ]; then
      tgt[$ax]=$(awk "BEGIN{t=${tgt[$ax]}+$dmpg*${RD[$ax]}; if(t<${RLO[$ax]})t=${RLO[$ax]}; if(t>${RHI[$ax]})t=${RHI[$ax]}; print t}")
    fi
    case $ax in
      3) printf "setp $P.stepgen.03.position-cmd %s\n" "${tgt[3]}" ;;   # A tilt -> stepgen.03 (packs cross-wired)
      4) printf "setp $P.stepgen.02.position-cmd %s\n" "${tgt[4]}" ;;   # C spin -> stepgen.02
      5) printf "setp $P.stepgen.00.position-cmd %s\nsetp $P.stepgen.01.position-cmd %s\n" "${tgt[5]}" "$(awk "BEGIN{print -(${tgt[5]})}")" ;;
    esac | { [ "$MODE" = arm ] && halcmd -f /dev/stdin 2>/dev/null || cat >/dev/null; }
    deg=$(awk "BEGIN{printf \"%+.4f\",${tgt[$ax]}*${D2R[$ax]}}")
    lo=$([ $ax = 3 ]&&echo $LO_A; [ $ax = 4 ]&&echo $LO_C; [ $ax = 5 ]&&echo $LO_B) ; hi=$([ $ax = 3 ]&&echo $HI_A; [ $ax = 4 ]&&echo $HI_C; [ $ax = 5 ]&&echo $HI_B)
    info=$(printf 'pos:%s deg (soft %s..%s)' "$deg" "$lo" "$hi")
  fi
  prev_ax=$ax

  # pwmgens written every cycle (selected vel axis nonzero, rest 0 -> linear axes hold at 0 V)
  if [ "$MODE" = arm ]; then
    printf "setp $P.pwmgen.00.value %s\nsetp $P.pwmgen.03.value %s\nsetp $P.pwmgen.01.value %s\nsetp $P.pwmgen.02.value %s\n" "$v00" "$v03" "$v01" "$v02" | halcmd -f /dev/stdin 2>/dev/null
  fi

  bs=UP ; [ "$pressed" = 1 ] && { bs=DOWN ; [ "$held" = 1 ] && bs=HELD ; }
  sptxt="" ; [ "${KIND[$ax]}" = vel ] && sptxt="/${SPNAME[$sp]}"
  printf '\r[%s] %s%-5s btn:%-4s mpg:%-7s d:%-4s %-42s  ' "${MODE^^}" "${AXNAME[$ax]}" "$sptxt" "$bs" "$mpg" "$dmpg" "$info"
  sleep "$DT"
done
