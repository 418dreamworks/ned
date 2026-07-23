#!/bin/bash
# drive_move.sh <drive> -volts Y [-time X] [-counts Z]
#   drive    : x | y | z | c | a   (c = swivel-head C spin, a = swivel-head AB tilt)
#   -volts Y : -10.0 .. +10.0   (analog velocity command; SIGN = direction)   REQUIRED
#   -time  X : stop after X seconds            (0 < X <= 60)
#   -counts Z: stop after |encoder delta| >= Z (Z > 0; gantry: EITHER encoder)
#   Give -time, -counts, or BOTH. With both, stops on WHICHEVER IS HIT FIRST.
#   (If only -counts is given, a hard 60 s cap still applies as a dead-encoder backstop.)
#
#   x = the X GANTRY: both rails (pwmgen.00 + pwmgen.03) commanded from ONE shared
#       signal on the SAME servo cycle, so timing skew can NOT rack the frame. Streams
#       both encoders + skew; OPPOSITE-sign deltas = a mirror-mounted motor -> stop.
#   c / a = swivel head (Yaskawa step/dir) -- NOT driven by this analog pwmgen tool;
#       command the head via LinuxCNC / software. Listed here for the axis vocabulary.
#
# OPEN-LOOP move. Forces the pwmgen(s) directly, bypassing LinuxCNC motion.
#  -> RUN WITH THE LINUXCNC MACHINE OFF (else its PID fights this / following-error trips).
#  -> e-stops RELEASED, axis CLEAR with room to travel, FINGER ON THE E-STOP.
#  -> NO software limit protection here. START SMALL AND SHORT (e.g. -volts 0.5 -time 1).

P=hm2_7i97.0
OUT08=$P.7i84.0.0.output-08
usage(){ echo "usage: drive_move.sh <x|y|z|c|a> -volts <-10..10> [-time <0..60>] [-counts <n>]   (c/a = swivel head, not yet driven here)"; exit 1; }

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

gantry=0; scale=50.0
case "$drive" in
  x) gantry=1 ;;   # X IS THE GANTRY: pwmgen.00 + pwmgen.03 driven together, anti-rack
  y) idx=01; scale=50.0; vsig=sig-y-vel-volts; esig=sig-y-amp-enable ;;
  z) idx=02; scale=40.0; vsig=sig-z-vel-volts; esig=sig-z-amp-enable ;;
  c|a) echo "$drive = swivel head (Yaskawa step/dir) -- not driven by this analog pwmgen tool; command it via LinuxCNC/software"; exit 1 ;;
  *) usage ;;   # the two gantry rails are not separately selectable (driving one alone RACKS the frame)
esac

# ---- common validation ----
[ -z "$volts" ] && { echo "-volts is REQUIRED"; usage; }
[ -z "$secs" ] && [ -z "$counts" ] && { echo "give at least one limit: -time and/or -counts"; usage; }
awk "BEGIN{exit !($volts>=-10 && $volts<=10)}" 2>/dev/null || { echo "voltage must be -10..10"; exit 1; }
[ -n "$secs" ]   && { awk "BEGIN{exit !($secs>0 && $secs<=60)}" 2>/dev/null || { echo "-time must be 0..60"; exit 1; }; }
[ -n "$counts" ] && { awk "BEGIN{exit !($counts>0)}" 2>/dev/null || { echo "-counts must be > 0"; exit 1; }; }
[ "$(halcmd getp $P.io_error 2>/dev/null)" = "TRUE" ] && { echo "io_error TRUE -> restart LinuxCNC"; exit 1; }
[ "$(halcmd getp $P.inmux.00.input-04 2>/dev/null)" != "TRUE" ] && { echo "E-STOPS NOT RELEASED (input-04 != TRUE) -> enable does nothing. Abort."; exit 1; }

cmd=$(awk "BEGIN{printf \"%.4f\", $volts/10.0*$scale}")
if [ -n "$secs" ]; then loops=$(awk "BEGIN{printf \"%d\", ($secs/0.25)+0.5}"); else loops=240; fi
lim="time=${secs:-none}  counts=${counts:-none}"

if [ "$gantry" = 1 ]; then
  # ======== GANTRY: X (00) + W (03) from ONE shared signal, same servo cycle ========
  GVEL=sig-gantry-vel; GEN=sig-gantry-en
  XVAL=$P.pwmgen.00.value; XEN=$P.pwmgen.00.enable; XENC=$P.encoder.00.count
  WVAL=$P.pwmgen.03.value; WEN=$P.pwmgen.03.enable; WENC=$P.encoder.03.count
  safe() {
    halcmd sets $GVEL 0 2>/dev/null; halcmd sets $GEN 0 2>/dev/null   # both -> 0, disabled
    halcmd setp $OUT08 0 2>/dev/null
    halcmd unlinkp $XVAL 2>/dev/null; halcmd unlinkp $XEN 2>/dev/null # break the shared link
    halcmd unlinkp $WVAL 2>/dev/null; halcmd unlinkp $WEN 2>/dev/null
    halcmd net sig-x-vel-volts $XVAL 2>/dev/null; halcmd net sig-x-amp-enable $XEN 2>/dev/null
    halcmd net sig-w-vel-volts $WVAL 2>/dev/null; halcmd net sig-w-amp-enable $WEN 2>/dev/null
    halcmd net sig-drive-enable $OUT08 2>/dev/null
  }
  trap 'echo; echo ">>> stop + disable all"; safe; echo "    relinked (X+W to own signals, drive-enable)"; exit' EXIT INT TERM
  echo "=== drive_move gantry: X+W linked @ ${volts}V (val=$cmd)  STOP@ $lim (whichever first) ==="
  x0=$(halcmd getp $XENC 2>/dev/null); w0=$(halcmd getp $WENC 2>/dev/null)

  halcmd unlinkp $OUT08; halcmd setp $OUT08 1
  echo ">>> ALL DRIVES ENABLED (R0 power + R3 run) - settling 1s"; sleep 1

  halcmd unlinkp $XVAL; halcmd unlinkp $WVAL; halcmd net $GVEL $XVAL $WVAL
  halcmd unlinkp $XEN;  halcmd unlinkp $WEN;  halcmd net $GEN  $XEN  $WEN
  halcmd sets $GEN 1                        # both enables true (00 = group master) same cycle
  halcmd sets $GVEL $cmd                    # both values commanded same cycle
  echo ">>> GANTRY MOVING ($(date +%H:%M:%S)) <-- X.delta & W.delta should track; opposite sign = RACK. e-stop ready"
  stop=""
  for ((k=1;k<=loops;k++)); do
    xe=$(halcmd getp $XENC 2>/dev/null); we=$(halcmd getp $WENC 2>/dev/null)
    dx=$((xe - x0)); dw=$((we - w0)); adx=${dx#-}; adw=${dw#-}; sk=$((dx - dw))
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
  halcmd sets $GVEL 0; echo "    gantry command -> 0, settling"; sleep 0.7
  x1=$(halcmd getp $XENC 2>/dev/null); w1=$(halcmd getp $WENC 2>/dev/null)
  echo "=== X enc.00: $x0 -> $x1 (delta $((x1 - x0)))  |  W enc.03: $w0 -> $w1 (delta $((w1 - w0))) ==="
  echo "=== STOPPED BECAUSE: $stop ==="

else
  # ======== SINGLE AXIS ========
  VAL=$P.pwmgen.$idx.value
  EN=$P.pwmgen.$idx.enable
  MEN=$P.pwmgen.00.enable      # master enable for axis group 0..3 (linked to sig-x-amp-enable)
  ENC=$P.encoder.$idx.count
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

  echo "=== drive_move: $drive   ${volts} V   STOP@ $lim (whichever first)   (pwmgen.$idx value=$cmd) ==="
  enc0=$(halcmd getp $ENC 2>/dev/null)

  halcmd unlinkp $OUT08; halcmd setp $OUT08 1
  echo ">>> ALL DRIVES ENABLED (R0 power + R3 run) - settling 1s"; sleep 1

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
  halcmd setp $VAL 0
  echo "    $drive command -> 0, settling"; sleep 0.7
  enc1=$(halcmd getp $ENC 2>/dev/null)
  echo "=== encoder.$idx: $enc0 -> $enc1   (delta $((enc1 - enc0)) counts) ==="
  echo "=== STOPPED BECAUSE: $stop ==="
fi
# (c) disable-all + relink runs in the EXIT trap
