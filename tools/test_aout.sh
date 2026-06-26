#!/bin/bash
# test_aout.sh <x|y|z|w> <voltage>
# Forces ONE axis analog output to <voltage> and HOLDS it until you press Ctrl-C.
# Drives are NOT enabled (no motion). Meter the listed TB3 pins while it holds.
# Applies the 7I97 offset-PWM recipe (75 kHz + dither + offset-mode) for bipolar.
P=hm2_7i97.0
case "$1" in
  x) idx=00; scale=50; tb="TB3 pin 4 (AOUT0) vs pin 3 (GND)"; vsig=sig-x-vel-volts; esig=sig-x-amp-enable ;;
  y) idx=01; scale=50; tb="TB3 pin 8 (AOUT1) vs pin 7 (GND)"; vsig=sig-y-vel-volts; esig=sig-y-amp-enable ;;
  z) idx=02; scale=40; tb="TB3 pin 12 (AOUT2) vs pin 11 (GND)"; vsig=sig-z-vel-volts; esig=sig-z-amp-enable ;;
  w) idx=03; scale=50; tb="TB3 pin 16 (AOUT3) vs pin 15 (GND)"; vsig=sig-w-vel-volts; esig=sig-w-amp-enable ;;
  *) echo "usage: test_aout.sh <x|y|z|w> <voltage -10..10>"; exit 1 ;;
esac
volts="$2"
[ -z "$volts" ] && { echo "usage: test_aout.sh <x|y|z|w> <voltage -10..10>"; exit 1; }
VAL=$P.pwmgen.$idx.value; EN=$P.pwmgen.$idx.enable
MEN=$P.pwmgen.00.enable          # master enable for the 0..3 group (linked to sig-x-amp-enable)
cmd=$(awk "BEGIN{printf \"%.4f\", $volts/10.0*$scale}")

cleanup(){ halcmd setp $VAL 0 2>/dev/null; halcmd setp $EN 0 2>/dev/null; halcmd setp $MEN 0 2>/dev/null
           halcmd net $vsig $VAL 2>/dev/null; halcmd net $esig $EN 2>/dev/null; halcmd net sig-x-amp-enable $MEN 2>/dev/null
           echo; echo "stopped + relinked (drives never enabled)"; exit; }
trap cleanup INT TERM

# TOGGLE each param so the driver actually re-writes the FPGA pwmgen config
# (setting a value to what it already is does NOT trigger an FPGA write).
halcmd setp $P.pwmgen.pwm_frequency 75000
halcmd setp $P.pwmgen.$idx.dither 0;      halcmd setp $P.pwmgen.$idx.dither 1
halcmd setp $P.pwmgen.$idx.offset-mode 0; halcmd setp $P.pwmgen.$idx.offset-mode 1
halcmd unlinkp $VAL; halcmd unlinkp $EN; halcmd unlinkp $MEN
halcmd setp $VAL $cmd; halcmd setp $EN 1; halcmd setp $MEN 1   # channel enable + group-master enable 0
echo "=== $1: pwmgen.$idx forced to ${volts} V (value=$cmd), drives OFF ==="
echo "    freq=$(halcmd getp $P.pwmgen.pwm_frequency)  dither=$(halcmd getp $P.pwmgen.$idx.dither)  offset-mode=$(halcmd getp $P.pwmgen.$idx.offset-mode)"
echo ">>> METER: $tb   — expect ~${volts} V"
echo ">>> HOLDING.  Press Ctrl-C when you're done metering."
while true; do sleep 1; done
