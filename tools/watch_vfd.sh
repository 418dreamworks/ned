#!/bin/bash
# watch_vfd.sh [seconds]   (default 60)
# Logs BOTH VFD->LinuxCNC inputs during one run-until-error event:
#   spindle-running  input-11  TB5-5  *36   (Y1 -> interposer -> R1 -> R1A3 -> *36)
#   vfd-fault        input-13  TB5-8  *38   (RY1, F5-02=2)
# Run the VFD up until it faults; this captures running going TRUE, then the
# fault going TRUE (and running dropping as it coasts to stop).
dur="${1:-60}"
P=hm2_7i97.0
RUN=$P.inmux.00.input-11
FLT=$P.inmux.00.input-13
LOG=/tmp/watch_vfd_runerror.log
{
echo "###############################################################"
echo "# CMD     : $0 $*"
echo "# WATCH   : spindle-running  $RUN   (TB5-5  *36)"
echo "#           vfd-fault        $FLT   (TB5-8  *38)"
echo "# STARTED : $(date '+%Y-%m-%d %H:%M:%S')"
echo "# EXPECT  : running FALSE->TRUE on RUN, ->FALSE as it coasts on fault"
echo "#           fault   FALSE->TRUE when it errors out"
echo "###############################################################"
} | tee "$LOG"
# verify comms are live (frozen io_error = stale reads)
ioerr=$(halcmd getp $P.io_error 2>/dev/null)
echo "# io_error = $ioerr  (must be FALSE, else restart LinuxCNC)" | tee -a "$LOG"
prun=""; pflt=""; t0=$(date +%s)
while :; do
  el=$(( $(date +%s) - t0 ))
  [ "$el" -ge "$dur" ] && break
  vr=$(halcmd getp $RUN 2>/dev/null)
  vf=$(halcmd getp $FLT 2>/dev/null)
  flag=""
  [ -n "$prun" ] && [ "$vr" != "$prun" ] && flag="$flag   <<< spindle-running $prun->$vr"
  [ -n "$pflt" ] && [ "$vf" != "$pflt" ] && flag="$flag   <<< vfd-fault $pflt->$vf"
  printf "%3ds  running=%-5s  fault=%-5s%s\n" "$el" "$vr" "$vf" "$flag" | tee -a "$LOG"
  prun="$vr"; pflt="$vf"
  sleep 1
done
echo "# done $(date '+%H:%M:%S')" | tee -a "$LOG"
