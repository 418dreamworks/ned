#!/bin/bash
# actuate_output.sh <name> [seconds]
# Energizes ONE field output for <seconds> (default 5) so you can watch the
# physical actuator, then de-energizes and relinks it to its signal. One at a
# time; report what it physically does. The "IS" line is the EXPECTED function
# from the trace — confirm or correct it.
name="$1"; dur="${2:-5}"
case "$name" in
  drive-enable)      out=output-08; sig=sig-drive-enable;      desc="DRIVE ENABLE -> R5  *8   ⚠ enables servo amps (drives are estopped now)" ;;
  spin-cw)           out=output-09; sig=sig-spin-cw;           desc="spindle CW -> R6    *40  (VFD off -> relay click only)" ;;
  spin-ccw)          out=output-10; sig=sig-spin-ccw;          desc="spindle CCW -> R7   *41  (VFD off -> relay click only)" ;;
  chip-blowoff)      out=output-11; sig=sig-chip-blowoff;      desc="chip blow-off -> R9  *55  (air blast)" ;;
  toolsetter-deploy) out=output-12; sig=sig-toolsetter-deploy; desc="toolsetter deploy   *61  (Bimba probe arm extend)" ;;
  rack)              out=output-13; sig=sig-drawbar-clamp;     desc="RACK in/out (OCLAMP) *63  (CONFIRMED: energize moves rack)" ;;
  taper-purge)       out=output-14; sig=sig-taper-purge;       desc="spindle taper purge  *64  (air)" ;;
  drawbar-release)   out=output-15; sig=sig-drawbar-release;   desc="drawbar RELEASE      *65  ⚠ unclamps spindle (tool drops if seated)" ;;
  *) echo "usage: actuate_output.sh <name> [seconds]"
     echo "names: drive-enable spin-cw spin-ccw chip-blowoff toolsetter-deploy \\"
     echo "       rack taper-purge drawbar-release"
     exit 1 ;;
esac
P=hm2_7i97.0.7i84.0.0
LOG="/tmp/actuate_${name}.log"
{
  echo "###############################################################"
  echo "# CMD     : $0 $*"
  echo "# OUTPUT  : $P.$out   ($sig)"
  echo "# IS      : $desc"
  echo "# STARTED : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "# ACTION  : energize ${dur}s -> de-energize -> relink"
  echo "###############################################################"
} | tee "$LOG"
halcmd unlinkp $P.$out 2>/dev/null
echo ">>> ENERGIZE (24V on $out) — watch it..." | tee -a "$LOG"
halcmd setp $P.$out 1 2>/dev/null
sleep "$dur"
echo ">>> DE-ENERGIZE (back to default)..." | tee -a "$LOG"
halcmd setp $P.$out 0 2>/dev/null
halcmd net $sig $P.$out 2>/dev/null
echo "# relinked, done $(date '+%H:%M:%S')" | tee -a "$LOG"
