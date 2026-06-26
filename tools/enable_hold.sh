#!/bin/bash
# enable_hold.sh
# Enables ALL drives (output-08 -> R5 -> R0 power + R3 run) with 0 V commanded on
# all 4 axes. HOLDS until Ctrl-C, then commands 0, disables all, relinks.
# Run with GUI machine OFF, e-stops RELEASED, FINGER ON E-STOP.
# Watch: DC bus should come up, drives should HOLD (try moving by hand -> stiff),
# and the encoder stream should stay put. If any axis count creeps at 0 V = that
# drive's offset/null is untrimmed (or runaway). Slam the e-stop if anything runs.
P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" != "TRUE" ] && { echo "E-STOPS NOT RELEASED -> bus won't come up. Abort."; exit 1; }

safe(){
  for n in 00 01 02 03; do halcmd setp $P.pwmgen.$n.value 0 2>/dev/null; halcmd setp $P.pwmgen.$n.enable 0 2>/dev/null; done
  halcmd setp $OUT08 0 2>/dev/null
  halcmd net sig-x-vel-volts $P.pwmgen.00.value 2>/dev/null; halcmd net sig-y-vel-volts $P.pwmgen.01.value 2>/dev/null
  halcmd net sig-z-vel-volts $P.pwmgen.02.value 2>/dev/null; halcmd net sig-w-vel-volts $P.pwmgen.03.value 2>/dev/null
  halcmd net sig-x-amp-enable $P.pwmgen.00.enable 2>/dev/null; halcmd net sig-y-amp-enable $P.pwmgen.01.enable 2>/dev/null
  halcmd net sig-z-amp-enable $P.pwmgen.02.enable 2>/dev/null; halcmd net sig-w-amp-enable $P.pwmgen.03.enable 2>/dev/null
  halcmd net sig-drive-enable $OUT08 2>/dev/null
  echo; echo "ALL DRIVES DISABLED + relinked"; exit
}
trap safe INT TERM

# command 0 V on all axes FIRST, so the bank powers up already holding zero
for n in 00 01 02 03; do
  halcmd unlinkp $P.pwmgen.$n.value; halcmd unlinkp $P.pwmgen.$n.enable
  halcmd setp $P.pwmgen.$n.value 0; halcmd setp $P.pwmgen.$n.enable 1
done
halcmd unlinkp $OUT08; halcmd setp $OUT08 1
echo "=== ALL DRIVES ENABLED, all axes commanded 0 V  ($(date +%H:%M:%S)) ==="
echo ">>> DC bus should be up. Try the axis by hand -> it should be STIFF now."
echo ">>> HOLDING. Watch the encoder counts for creep. Ctrl-C to disable."
while true; do
  printf "\r enc  X=%-9s Y=%-9s Z=%-9s W=%-9s   " \
    "$(halcmd getp $P.encoder.00.count 2>/dev/null)" "$(halcmd getp $P.encoder.01.count 2>/dev/null)" \
    "$(halcmd getp $P.encoder.02.count 2>/dev/null)" "$(halcmd getp $P.encoder.03.count 2>/dev/null)"
  sleep 0.5
done
