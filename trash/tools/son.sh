#!/bin/bash
# son.sh -- forces /S-ON HIGH for A (7I84 TB3-23) and C (TB3-24) and HOLDS until Ctrl-C, so you
# can DMM them at rest. Each should read +24 V to 0 V. A is the known-good reference.
# Standalone: kills LinuxCNC, loads move.hal, owns the board, releases on Ctrl-C.
P=hm2_7i97.0
HAL="$(dirname "$(readlink -f "$0")")/move.hal"

pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."; sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

teardown(){ echo; echo ">>> releasing /S-ON";
  halcmd setp $P.7i84.0.0.output-06 0 2>/dev/null; halcmd setp $P.7i84.0.0.output-07 0 2>/dev/null
  kill "$HALPID" 2>/dev/null; pkill -9 -f "halcmd -f.*move.hal" 2>/dev/null; halrun -U >/dev/null 2>&1; echo done.; }
trap 'teardown; exit' EXIT INT TERM

halcmd setp $P.7i84.0.0.output-06 1
halcmd setp $P.7i84.0.0.output-07 1
echo ">>> /S-ON HIGH:  A = TB3-23,  C = TB3-24.  DMM each to 0 V -- expect +24 V.  Ctrl-C to release."
while true; do sleep 1; done
