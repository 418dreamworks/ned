#!/bin/bash
# Live 1-Hz log of the 3 HQD ATC sensors on the 7I84.
# Ctrl-C to stop.
P=hm2_7i97.0.7i84.0.0
while true; do
  printf '%s  shaft-stop(29)=%s  lock(30)=%s  rel(31)=%s\n' \
    "$(date +%T)" \
    "$(halcmd getp $P.input-29)" \
    "$(halcmd getp $P.input-30)" \
    "$(halcmd getp $P.input-31)"
  sleep 1
done
