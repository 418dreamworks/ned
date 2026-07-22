#!/bin/bash
# drive_gantry.sh -volts Y [-time X] [-counts Z]
#   Drives BOTH gantry motors X (pwmgen.00) and W (pwmgen.03) from a SINGLE shared
#   signal, so they get the identical command on the identical servo cycle -- they
#   are bolted to the same gantry and any timing skew between them racks the frame.
#
#   -volts  Y : voltage for BOTH motors  (-10..10, sign = direction)   REQUIRED
#   -time   X : stop after X seconds            (0 < X <= 60)
#   -counts Z : stop after |EITHER encoder delta| >= Z   (Z > 0)
#   Give -time, -counts, or both. Stops on WHICHEVER IS HIT FIRST.
#   (counts-only still gets a hard 60 s dead-encoder backstop.)
#
# HOW THE LINK WORKS:
#   net sig-gantry-vel -> pwmgen.00.value + pwmgen.03.value   (one writer: this script)
#   net sig-gantry-en  -> pwmgen.00.enable + pwmgen.03.enable (00 is also group master)
#   sets sig-gantry-vel <v>  --> both motors commanded the SAME value, same cycle.
#
#  -> RUN WITH THE LINUXCNC MACHINE OFF (else its PID fights this).
#  -> e-stops RELEASED, gantry CLEAR, FINGER ON THE E-STOP.
#  -> START SMALL AND SHORT (e.g. -volts 0.1 -time 0.5).
#  -> If X and W deltas come out OPPOSITE in sign, the motors are mounted mirror
#     and a shared signal RACKS them -> stop; one channel then needs inversion.

P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
GVEL=sig-gantry-vel          # shared velocity signal (created at runtime)
GEN=sig-gantry-en            # shared enable   signal (created at runtime)
usage(){ echo "usage: drive_gantry.sh -volts <-10..10> [-time <0..60>] [-counts <n>]"; exit 1; }

volts=""; secs=""; counts=""
while [ $# -gt 0 ]; do
  case "$1" in
    -volts)  volts="$2";  shift 2 ;;
    -time)   secs="$2";   shift 2 ;;
    -counts) counts="$2"; shift 2 ;;
    *) echo "unknown argument: $1"; usage ;;
  esac
done
[ -z "$volts" ] && { echo "-volts is REQUIRED"; usage; }
[ -z "$secs" ] && [ -z "$counts" ] && { echo "give at least one limit: -time and/or -counts"; usage; }

SCALE=50.0
XVAL=$P.pwmgen.00.value; XEN=$P.pwmgen.00.enable; XENC=$P.encoder.00.count
WVAL=$P.pwmgen.03.value; WEN=$P.pwmgen.03.enable; WENC=$P.encoder.03.count

awk "BEGIN{exit !($volts>=-10 && $volts<=10)}" 2>/dev/null || { echo "-volts must be -10..10"; exit 1; }
[ -n "$secs" ]   && { awk "BEGIN{exit !($secs>0 && $secs<=60)}" 2>/dev/null || { echo "-time must be 0..60"; exit 1; }; }
[ -n "$counts" ] && { awk "BEGIN{exit !($counts>0)}" 2>/dev/null || { echo "-counts must be > 0"; exit 1; }; }
[ "$(halcmd getp $P.io_error 2>/dev/null)" = "TRUE" ] && { echo "io_error TRUE -> restart LinuxCNC"; exit 1; }
[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" != "TRUE" ] && { echo "E-STOPS NOT RELEASED (input-04 != TRUE). Abort."; exit 1; }

cmd=$(awk "BEGIN{printf \"%.4f\", $volts/10.0*$SCALE}")
if [ -n "$secs" ]; then loops=$(awk "BEGIN{printf \"%d\", ($secs/0.25)+0.5}"); else loops=240; fi

safe() {
  halcmd sets $GVEL 0 2>/dev/null; halcmd sets $GEN 0 2>/dev/null   # both motors -> 0, disabled
  halcmd setp $OUT08 0 2>/dev/null
  halcmd unlinkp $XVAL 2>/dev/null; halcmd unlinkp $XEN 2>/dev/null   # break the shared link
  halcmd unlinkp $WVAL 2>/dev/null; halcmd unlinkp $WEN 2>/dev/null
  halcmd net sig-x-vel-volts $XVAL 2>/dev/null; halcmd net sig-x-amp-enable $XEN 2>/dev/null
  halcmd net sig-w-vel-volts $WVAL 2>/dev/null; halcmd net sig-w-amp-enable $WEN 2>/dev/null
  halcmd net sig-drive-enable $OUT08 2>/dev/null
}
trap 'echo; echo ">>> stop + disable all"; safe; echo "    relinked (X + W back to their own signals, drive-enable)"; exit' EXIT INT TERM

echo "=== drive_gantry: X+W linked @ ${volts}V (val=$cmd)  STOP@ time=${secs:-none} counts=${counts:-none} ==="
x0=$(halcmd getp $XENC 2>/dev/null); w0=$(halcmd getp $WENC 2>/dev/null)

# (a) ENABLE ALL DRIVES
halcmd unlinkp $OUT08; halcmd setp $OUT08 1
echo ">>> ALL DRIVES ENABLED (R0 power + R3 run) - settling 1s"
sleep 1

# (b) LINK both motors to one signal, then command once -> both move together
halcmd unlinkp $XVAL; halcmd unlinkp $WVAL; halcmd net $GVEL $XVAL $WVAL
halcmd unlinkp $XEN;  halcmd unlinkp $WEN;  halcmd net $GEN  $XEN  $WEN
halcmd sets $GEN 1                       # both enables true (00 = group master) same cycle
halcmd sets $GVEL $cmd                   # both values commanded same cycle
echo ">>> GANTRY MOVING  ($(date +%H:%M:%S))  <-- X.delta and W.delta should track; opposite sign = RACK. e-stop ready"
stop=""
for ((k=1;k<=loops;k++)); do
  xe=$(halcmd getp $XENC 2>/dev/null); we=$(halcmd getp $WENC 2>/dev/null)
  dx=$((xe - x0)); dw=$((we - w0)); adx=${dx#-}; adw=${dw#-}; sk=$((dx - dw))
  # skew as a % of each joint's own travel-from-zero (guard divide-by-zero)
  pctx=$(awk "BEGIN{ if ($dx==0) printf \"--\"; else printf \"%+.2f%%\", 100.0*$sk/$dx }")
  pctw=$(awk "BEGIN{ if ($dw==0) printf \"--\"; else printf \"%+.2f%%\", 100.0*$sk/$dw }")
  printf "    +%.2fs  X.delta=%-8s  W.delta=%-8s  skew=%-7s  skew/X=%-8s  skew/W=%-8s\n" \
    "$(awk "BEGIN{printf \"%.2f\",$k*0.25}")" "$dx" "$dw" "$sk" "$pctx" "$pctw"
  if [ -n "$counts" ]; then
    { [ "$adx" -ge "$counts" ] || [ "$adw" -ge "$counts" ]; } 2>/dev/null && { stop="counts (X=$dx W=$dw >= $counts)"; break; }
  fi
  sleep 0.25
done
[ -z "$stop" ] && { [ -n "$secs" ] && stop="time (${secs}s)" || stop="60 s safety cap"; }

halcmd sets $GVEL 0
echo "    gantry command -> 0, settling"
sleep 0.7
x1=$(halcmd getp $XENC 2>/dev/null); w1=$(halcmd getp $WENC 2>/dev/null)
echo "=== X enc.00: $x0 -> $x1 (delta $((x1 - x0)))   |   W enc.03: $w0 -> $w1 (delta $((w1 - w0))) ==="
echo "=== STOPPED BECAUSE: $stop ==="
# (c) disable-all + relink runs in the EXIT trap
