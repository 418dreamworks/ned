#!/bin/bash
# sen_meter.sh -- repeatedly pulse SEN so you can DMM the PSO line and confirm the pack
# is actually transmitting. Runs until Ctrl-C. Needs the board FREE (LinuxCNC stopped).
#
#   tools/sen_meter.sh both   # DEFAULT: alternates R4 C,A,C,A... so ONE probe sees both packs
#   RUN IT TWICE AND COMPARE:
#     tools/sen_meter.sh both           -> /S-ON OFF  : SEN honoured, expect BURSTS
#     tools/sen_meter.sh both silent    -> /S-ON ON   : manual 6.12 p.315 says SEN is NOT
#                                          acknowledged while the servo is on -> expect SILENCE
#   'silent' is a FLAG and combines with any mode (both / A / C).
#   tools/sen_meter.sh C     # R4 de-energized -> C's PSO reaches the Mesa
#   tools/sen_meter.sh A     # R4 energized    -> A's PSO reaches the Mesa
#
# WHERE TO PROBE -- best point is AFTER the R4 mux, so one probe sees whichever pack is
# selected (docs/tracing/relays.md:192,195 -- R4 contacts feed these):
#   ** 7I85 TB1-19 (SRX+)  and  7I85 TB1-20 (SRX-) **   <- DMM across this pair
# (At the drive end instead: PSO / /PSO = servopack CN1-48 / CN1-49 --
#  docs/servo/yaskawa_params_quickref.md:9,14. That is BEFORE the mux, one pack only.)
#   DMM on DC volts ACROSS the pair.
#     idle  : steady differential, a few volts, one polarity (RS-422 MARK)
#     burst : reading visibly wiggles / dips for ~0.8 s right after each SEN rise
#   No wiggle ever = the pack is not transmitting on that axis.
#   Wiggle on both A and C = the packs are fine and the fault is on the Mesa/receive side.
#
# SEN is honoured per manual 6.12 p.315: held HIGH >= 1.3 s before each drop.
set -u
MODE=both
SON=0
for a in "$@"; do
  case "$a" in
    silent|SILENT|--silent) SON=1 ;;                 # FLAG: assert /S-ON for the WHOLE run
    A|a) MODE=A ;;  C|c) MODE=C ;;  both|BOTH) MODE=both ;;
    *) echo "usage: $0 [both|A|C] [silent]"; exit 1 ;;
  esac
done
case "$MODE" in A) R4=1; L=A; ALT=0;; C) R4=0; L=C; ALT=0;; both) R4=0; L=C; ALT=1;; esac

NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pgrep -f '[l]inuxcncsvr|[m]illtask' >/dev/null && { echo "LinuxCNC is running -- stop it first (tools/lcnc_stop.sh)"; exit 1; }
H=$(mktemp /tmp/senm_XXXX.hal)
cat > "$H" <<HAL
loadrt hostmot2
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=6 num_pwmgens=6 num_stepgens=4 num_inmuxs=1 num_pktuarts=1 sserial_port_0=0xxxxxxx"
loadrt threads name1=servo period1=1000000
addf hm2_7i97.0.read  servo
addf hm2_7i97.0.write servo
setp hm2_7i97.0.7i84.0.0.output-06 0
setp hm2_7i97.0.7i84.0.0.output-07 0
setp hm2_7i97.0.7i84.0.0.output-09 0
setp hm2_7i97.0.7i84.0.0.output-05 $R4
setp hm2_7i97.0.7i84.0.0.output-04 1
start
loadusr -w sleep 86400
HAL
cat <<BANNER
=====================================================================
 PROBE: DMM on DC volts across  7I85 TB1-19 (SRX+)  ->  TB1-20 (SRX-)
 /S-ON : $( [ "$SON" = 1 ] && echo "ON  -> SEN is NOT acknowledged -> expect SILENCE" || echo "OFF -> SEN honoured -> expect a ~1 s BURST per request" )

 FIXED SCHEDULE (starts 6 s from now, then repeats forever):
   t=0s   C  request 1     t=5s   C  request 2
   t=10s  A  request 1     t=15s  A  request 2
   t=20s  C  request 1     ... and so on, swapping axis every 10 s
 Each request: SEN low 2 s, then HIGH -> the burst happens right on the rise.
 Ctrl-C to stop (drops /S-ON, frees the board).
=====================================================================
BANNER
halrun -U >/dev/null 2>&1
halrun -f "$H" >/dev/null 2>&1 &
HP=$!
trap 'halcmd setp hm2_7i97.0.7i84.0.0.output-09 0 2>/dev/null; halcmd setp hm2_7i97.0.7i84.0.0.output-06 0 2>/dev/null; halcmd setp hm2_7i97.0.7i84.0.0.output-07 0 2>/dev/null; kill $HP 2>/dev/null; halrun -U >/dev/null 2>&1; rm -f "$H"; echo; echo "stopped, board free"; exit' INT TERM EXIT
sleep 6
# (no audio -- the schedule above tells you everything)
if [ "$SON" = 1 ]; then
  echo "  /S-ON ON: asserting on BOTH head packs (A=output-07, C=output-06)."
  echo "  Servos will ENERGIZE and hold position. No motion is commanded."
  halcmd setp hm2_7i97.0.7i84.0.0.output-07 1 2>/dev/null   # A /S-ON
  halcmd setp hm2_7i97.0.7i84.0.0.output-06 1 2>/dev/null   # C /S-ON
  sleep 3
fi
n=0
click(){ halcmd setp hm2_7i97.0.7i84.0.0.output-09 1 >/dev/null; sleep 0.15
         halcmd setp hm2_7i97.0.7i84.0.0.output-09 0 >/dev/null; }
pulse_sen(){
  click                                                   # audible R6 click = request NOW
  halcmd setp hm2_7i97.0.7i84.0.0.output-04 0 >/dev/null  # SEN low
  sleep 1
  halcmd setp hm2_7i97.0.7i84.0.0.output-04 1 >/dev/null  # rise -> burst
  n=$((n+1))
  echo "    pulse $n  on $L   (R4=$(halcmd getp hm2_7i97.0.7i84.0.0.output-05))"
}
# HOLD R4 on -> 2 pulses -> HOLD R4 off -> 2 pulses -> repeat forever.
while kill -0 $HP 2>/dev/null; do
  for R4 in 1 0; do
    [ "$R4" = 1 ] && L=A || L=C
    halcmd setp hm2_7i97.0.7i84.0.0.output-05 $R4 >/dev/null
    echo ""
    echo "  ==== R4 HELD $( [ "$R4" = 1 ] && echo ON || echo OFF ) -> reading $L  (readback=$(halcmd getp hm2_7i97.0.7i84.0.0.output-05)) ===="
    sleep 5
    pulse_sen
    sleep 5
    pulse_sen
    sleep 5
  done
done
