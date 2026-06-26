#!/bin/bash
# drive_move.sh <drive> -volts Y [-time X] [-counts Z]
#   drive    : x | y | z | w
#   -volts Y : -10.0 .. +10.0   (analog velocity command; SIGN = direction)   REQUIRED
#   -time  X : stop after X seconds            (0 < X <= 60)
#   -counts Z: stop after |encoder delta| >= Z (Z > 0)
#   Give -time, -counts, or BOTH. With both, stops on WHICHEVER IS HIT FIRST.
#   (If only -counts is given, a hard 60 s cap still applies as a dead-encoder backstop.)
#
# OPEN-LOOP single-axis move. Sequence:
#   (a) enable ALL drives  : force sig-drive-enable (output-08) -> R5 -> R0 power + R3 run
#   (b) command ONE drive  : force that axis's pwmgen to <volts> until a limit is hit
#   (c) disable ALL drives : zero + disable + drop output-08, then relink everything
#
# Forces the pwmgen directly, bypassing LinuxCNC motion.
#  -> RUN WITH THE LINUXCNC MACHINE OFF (else its PID fights this / following-error trips).
#  -> e-stops RELEASED, axis CLEAR with room to travel, FINGER ON THE E-STOP.
#  -> NO software limit protection here (machine off). A wrong voltage/time drives the
#     axis into a hard stop. START SMALL AND SHORT (e.g. -time 1 -volts 0.5) to find direction.
#  -> X and W are the same gantry: moving one without the other RACKS the gantry.

P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
usage(){ echo "usage: drive_move.sh <x|y|z|w> -volts <-10..10> [-time <0..60>] [-counts <n>]"; exit 1; }

drive="$1"; shift
secs=""; volts=""; counts=""
while [ $# -gt 0 ]; do
  case "$1" in
    -time)   secs="$2";   shift 2 ;;
    -volts)  volts="$2";  shift 2 ;;
    -counts) counts="$2"; shift 2 ;;
    *) echo "unknown argument: $1"; usage ;;
  esac
done

case "$drive" in
  x) idx=00; scale=50.0; vsig=sig-x-vel-volts; esig=sig-x-amp-enable ;;
  y) idx=01; scale=50.0; vsig=sig-y-vel-volts; esig=sig-y-amp-enable ;;
  z) idx=02; scale=40.0; vsig=sig-z-vel-volts; esig=sig-z-amp-enable ;;
  w) idx=03; scale=50.0; vsig=sig-w-vel-volts; esig=sig-w-amp-enable ;;
  *) usage ;;
esac
VAL=$P.pwmgen.$idx.value
EN=$P.pwmgen.$idx.enable
MEN=$P.pwmgen.00.enable      # master enable for axis group 0..3 (linked to sig-x-amp-enable)
ENC=$P.encoder.$idx.count

[ -z "$volts" ] && { echo "-volts is REQUIRED"; usage; }
[ -z "$secs" ] && [ -z "$counts" ] && { echo "give at least one limit: -time and/or -counts"; usage; }
awk "BEGIN{exit !($volts>=-10 && $volts<=10)}" 2>/dev/null || { echo "voltage must be -10..10"; exit 1; }
[ -n "$secs" ]   && { awk "BEGIN{exit !($secs>0 && $secs<=60)}" 2>/dev/null || { echo "-time must be 0..60"; exit 1; }; }
[ -n "$counts" ] && { awk "BEGIN{exit !($counts>0)}" 2>/dev/null || { echo "-counts must be > 0"; exit 1; }; }
[ "$(halcmd getp $P.io_error 2>/dev/null)" = "TRUE" ] && { echo "io_error TRUE -> restart LinuxCNC"; exit 1; }
[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" != "TRUE" ] && { echo "E-STOPS NOT RELEASED (input-04 != TRUE) -> enable does nothing. Abort."; exit 1; }

cmd=$(awk "BEGIN{printf \"%.4f\", $volts/10.0*$scale}")
# loop ceiling (0.25 s ticks): from -time if given, else hard 60 s backstop
if [ -n "$secs" ]; then loops=$(awk "BEGIN{printf \"%d\", ($secs/0.25)+0.5}"); else loops=240; fi

safe() {
  halcmd setp $VAL 0   2>/dev/null
  halcmd setp $EN 0    2>/dev/null
  halcmd setp $MEN 0   2>/dev/null
  halcmd setp $OUT08 0 2>/dev/null
  halcmd net $vsig $VAL              2>/dev/null
  halcmd net $esig $EN               2>/dev/null
  halcmd net sig-x-amp-enable $MEN   2>/dev/null
  halcmd net sig-drive-enable $OUT08 2>/dev/null
}
trap 'echo; echo ">>> stop + disable all"; safe; echo "    relinked (sig-drive-enable, $vsig, $esig)"; exit' EXIT INT TERM

lim="time=${secs:-none}  counts=${counts:-none}"
echo "=== drive_move: $drive   ${volts} V   STOP@ $lim (whichever first)   (pwmgen.$idx value=$cmd) ==="
enc0=$(halcmd getp $ENC 2>/dev/null)

# (a) ENABLE ALL DRIVES
halcmd unlinkp $OUT08; halcmd setp $OUT08 1
echo ">>> ALL DRIVES ENABLED (R0 power + R3 run) - settling 1s"
sleep 1

# (b) COMMAND THE ONE DRIVE until a limit is hit
halcmd unlinkp $VAL; halcmd unlinkp $EN; halcmd unlinkp $MEN
halcmd setp $VAL $cmd; halcmd setp $EN 1; halcmd setp $MEN 1
echo ">>> $drive @ ${volts} V   ($(date +%H:%M:%S))   <-- WATCH IT, e-stop ready"
stop=""
for ((k=1;k<=loops;k++)); do
  enc=$(halcmd getp $ENC 2>/dev/null)
  d=$((enc - enc0)); ad=${d#-}
  printf "    +%.2fs  enc.%s=%-12s  delta=%s\n" "$(awk "BEGIN{printf \"%.2f\",$k*0.25}")" "$idx" "$enc" "$d"
  if [ -n "$counts" ] && [ "$ad" -ge "$counts" ] 2>/dev/null; then stop="counts ($d >= $counts)"; break; fi
  sleep 0.25
done
[ -z "$stop" ] && { [ -n "$secs" ] && stop="time (${secs}s)" || stop="60 s safety cap"; }
echo ">>> STOPPED on $stop"

# decel to 0
halcmd setp $VAL 0
echo "    $drive command -> 0, settling"
sleep 0.7
enc1=$(halcmd getp $ENC 2>/dev/null)
echo "=== encoder.$idx: $enc0 -> $enc1   (delta $((enc1 - enc0)) counts) ==="
echo "=== STOPPED BECAUSE: $stop ==="
# (c) disable-all + relink runs in the EXIT trap
