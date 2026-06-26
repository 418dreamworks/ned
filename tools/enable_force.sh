#!/bin/bash
# enable_force.sh <x|y|z|w> <voltage>
# Enables ALL drives (output-08 -> R5 -> R0 power + R3 run), forces ONE axis to
# <voltage>, streams that axis's encoder, and HOLDS until Ctrl-C.
# AUTO-ABORTS (zero+disable) if the axis travels past +/-3000 counts, so a runaway
# is bounded. Drives go live -> START LOW (1 V), e-stops released, FINGER ON E-STOP.
P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
case "$1" in
  x) idx=00; scale=50; vsig=sig-x-vel-volts; esig=sig-x-amp-enable; tb="TB3 pin4(AOUT0) vs pin3" ;;
  y) idx=01; scale=50; vsig=sig-y-vel-volts; esig=sig-y-amp-enable; tb="TB3 pin8(AOUT1) vs pin7" ;;
  z) idx=02; scale=40; vsig=sig-z-vel-volts; esig=sig-z-amp-enable; tb="TB3 pin12(AOUT2) vs pin11" ;;
  w) idx=03; scale=50; vsig=sig-w-vel-volts; esig=sig-w-amp-enable; tb="TB3 pin16(AOUT3) vs pin15" ;;
  *) echo "usage: enable_force.sh <x|y|z|w> <voltage>"; exit 1 ;;
esac
volts="$2"; [ -z "$volts" ] && { echo "usage: enable_force.sh <x|y|z|w> <voltage>"; exit 1; }
[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" != "TRUE" ] && { echo "E-STOPS NOT RELEASED. Abort."; exit 1; }
VAL=$P.pwmgen.$idx.value; EN=$P.pwmgen.$idx.enable; ENC=$P.encoder.$idx.count
cmd=$(awk "BEGIN{printf \"%.3f\", $volts/10*$scale}")

safe(){ halcmd setp $VAL 0 2>/dev/null; halcmd setp $EN 0 2>/dev/null; halcmd setp $OUT08 0 2>/dev/null
        halcmd net $vsig $VAL 2>/dev/null; halcmd net $esig $EN 2>/dev/null; halcmd net sig-drive-enable $OUT08 2>/dev/null
        echo; echo "DISABLED + relinked"; exit; }
trap safe INT TERM

e0=$(halcmd getp $ENC 2>/dev/null)
halcmd unlinkp $VAL; halcmd unlinkp $EN; halcmd setp $VAL 0; halcmd setp $EN 1
halcmd unlinkp $OUT08; halcmd setp $OUT08 1     # enable bank with 0 V first
echo "=== ALL DRIVES ENABLED ($(date +%H:%M:%S)).  Now commanding $1 @ ${volts}V ==="
echo ">>> Meter $tb.  Watch the axis.  Ctrl-C to stop.  Auto-abort at +/-3000 counts."
halcmd setp $VAL $cmd
while true; do
  e=$(halcmd getp $ENC 2>/dev/null); d=$((e - e0))
  printf "\r enc.%s=%-10s  delta=%-8s  (val=%s) " "$idx" "$e" "$d" "$(halcmd getp $VAL)"
  if [ "${d#-}" -gt 3000 ] 2>/dev/null; then echo; echo "!!! TRAVELED $d COUNTS — AUTO-ABORT"; safe; fi
  sleep 0.3
done
