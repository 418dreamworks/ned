#!/bin/bash
# watch_signal.sh <name> [seconds]
# <name> is a human label. The program maps it to the Mesa input pin and watches
# that ONE input once per second, showing value + wire volts (24V = not hit /
# circuit closed, 0V = hit / open). Logs to /tmp/watch_<name>.log, stamped with
# the exact command and start time so a stale log is never mistaken for fresh.
name="$1"; dur="${2:-60}"
case "$name" in
  estop)           pin=inmux.00.input-04; desc="e-stop chain         TB4-7  *6"  ;;
  x-aft)        pin=inmux.00.input-05; desc="X AFT starboard      TB4-8  *24" ;;
  x-fore)       pin=inmux.00.input-06; desc="X FORE starboard     TB4-10 *25" ;;
  y-sb)            pin=inmux.00.input-07; desc="Y starboard          TB4-11 *26" ;;
  y-port)          pin=inmux.00.input-08; desc="Y port               TB5-1  *27" ;;
  z-bottom)        pin=inmux.00.input-09; desc="Z BOTTOM             TB5-2  *28" ;;
  z-top)           pin=inmux.00.input-10; desc="Z TOP                TB5-4  *29" ;;
  spindle-running) pin=inmux.00.input-11; desc="spindle running      TB5-5  *36" ;;
  air)             pin=inmux.00.input-12; desc="air pressure OK      TB5-7  *37" ;;
  vfd-fault)       pin=inmux.00.input-13; desc="VFD fault            TB5-8  *38" ;;
  overtemp)        pin=inmux.00.input-14; desc="spindle overtemp     TB5-10 *39" ;;
  tool-probe)      pin=7i84.0.0.input-28; desc="tool probe           TB2-13 *54" ;;
  rack)            pin=7i84.0.0.input-29; desc="rack position        TB2-14 *68" ;;
  drawbar-up)      pin=7i84.0.0.input-30; desc="drawbar UP (clamped) TB2-15 *69" ;;
  drawbar-down)    pin=7i84.0.0.input-31; desc="drawbar DOWN         TB2-16 *70" ;;
  *) echo "usage: watch_signal.sh <name> [seconds]"
     echo "names: estop x-aft x-fore y-sb y-port z-bottom z-top \\"
     echo "       spindle-running air vfd-fault overtemp tool-probe rack drawbar-up drawbar-down"
     exit 1 ;;
esac
PIN="hm2_7i97.0.$pin"
LOG="/tmp/watch_${name}.log"
start_h=$(date '+%Y-%m-%d %H:%M:%S'); start_e=$(date +%s)
{
  echo "###############################################################"
  echo "# CMD     : $0 $*"
  echo "# NAME    : $name   ->   $PIN"
  echo "# IS      : $desc"
  echo "# STARTED : $start_h  (epoch $start_e)"
  echo "# COLUMNS : second   value   volts    (24V = not hit, 0V = hit)"
  echo "###############################################################"
} | tee "$LOG"
for ((i=0; i<=dur; i++)); do
  v=$(halcmd getp "$PIN" 2>/dev/null)
  case "$v" in TRUE) volt=24V ;; FALSE) volt=0V ;; *) volt=-- ;; esac
  printf '%4d    %-6s  %s\n' "$i" "$v" "$volt" | tee -a "$LOG"
  sleep 1
done
echo "# ENDED   : $(date '+%H:%M:%S')" | tee -a "$LOG"
