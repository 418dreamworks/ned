#!/bin/bash
# mon.sh -- live monitor of the Mesa pins in the X/W gantry drive-enable + move chain.
# Run in a SECOND terminal (LinuxCNC/HAL must be up) WHILE move.sh runs in the first:
#   bash /home/brains/mon.sh
# Ctrl-C to stop.
#
# WHAT IT SHOWS (the whole command -> DAC -> motion chain, + gates):
#   en08  = 7i84 output-08  = drive-enable command the Mesa is sending (-> R5 -> *7 -> R0)
#   estop = inmux input-04  = e-stop chain OK (must stay TRUE; if it flickers, *6 drops -> R0 drops)
#   ioerr = board io_error  = hm2_eth comms health (TRUE = board dropped, everything freezes)
#   Xval/Wval = pwmgen 00/03 value  = the analog command to the X / W drives
#   Xen/Wen   = pwmgen 00/03 enable = DAC output enabled
#   Xcnt/Wcnt = encoder 00/03 count = actual motion (changes only if the motor really turned)
#   lims = the 6 limit inputs (05..10)  -- move.sh ignores them, shown for completeness
#
# WHAT IT CANNOT SEE: R0 / *7 themselves (no aux contact -> no HAL pin).
#   Meter *7 with a DMM (or listen for the R0 clunk) alongside this.

P=hm2_7i97.0
g(){ halcmd getp "$1" 2>/dev/null; }

printf 'time         en08  estop ioerr | Xval    Xen  Xcnt       | Wval    Wen  Wcnt       | lims(05..10)\n'
while true; do
  printf '%s  %-5s %-5s %-5s | %-7s %-4s %-10s | %-7s %-4s %-10s | %s%s%s%s%s%s\n' \
    "$(date +%H:%M:%S.%3N)" \
    "$(g $P.7i84.0.0.output-08)" "$(g $P.inmux.00.input-04)" "$(g $P.io_error)" \
    "$(g $P.pwmgen.00.value)" "$(g $P.pwmgen.00.enable)" "$(g $P.encoder.00.count)" \
    "$(g $P.pwmgen.03.value)" "$(g $P.pwmgen.03.enable)" "$(g $P.encoder.03.count)" \
    "$(g $P.inmux.00.input-05)" "$(g $P.inmux.00.input-06)" "$(g $P.inmux.00.input-07)" \
    "$(g $P.inmux.00.input-08)" "$(g $P.inmux.00.input-09)" "$(g $P.inmux.00.input-10)"
  sleep 0.1
done
