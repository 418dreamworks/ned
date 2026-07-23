#!/bin/bash
# maxspeed.sh <RPM> -- spin BOTH B steppers in opposite directions at <RPM>.
# R11 is now a NORMALLY-OPEN contactor, so the 70 V brick is powered ONLY while
# drive-enable is asserted -> this script now ASSERTS drive-enable (output-08 ->
# R5 -> *7 -> R11 closes -> brick live) before spinning, and drops it on exit.
# Ctrl-C to stop.   example (from ~/Documents):  bash ned/tools/maxspeed.sh 600
BOARD=hm2_7i97.0
HAL="$(dirname "$(readlink -f "$0")")/maxspeed.hal"   # companion .hal next to this script
EN=$BOARD.7i84.0.0.output-08     # drive-enable -> R5 coil

RPM="$1"
if [ -z "$RPM" ]; then
  echo "usage:  bash ned/tools/maxspeed.sh <RPM>      example:  bash ned/tools/maxspeed.sh 600"
  exit 1
fi
REVS=$(awk "BEGIN{printf \"%.4f\", $RPM/60}")   # HAL scale=400 -> velocity-cmd in motor rev/s

stop() {
  echo
  echo "stopping motors + dropping drive-enable..."
  halcmd setp $BOARD.stepgen.00.velocity-cmd 0 2>/dev/null
  halcmd setp $BOARD.stepgen.01.velocity-cmd 0 2>/dev/null
  halcmd setp $EN 0 2>/dev/null                 # drop drive-enable -> brick power off
  sleep 0.5
  kill "$HALPID" 2>/dev/null
  halrun -U >/dev/null 2>&1
  echo "stopped."
  exit 0
}
trap stop INT TERM

# clean any previous session, then load + start the stepgens (still 0) in the background
halrun -U >/dev/null 2>&1
halrun -f "$HAL" &
HALPID=$!

echo "starting up (the board takes a few seconds)..."
sleep 4
if ! kill -0 "$HALPID" 2>/dev/null; then
  echo "FAILED to start -- is the Mesa powered and the network cable in? (10.10.10.10)"
  exit 1
fi

# (e-stop check removed per user 2026-07-22 — estop input is flaky; run regardless)

# assert drive-enable: output-08 -> R5 -> *7 -> R11 (NOW NO) closes -> 70 V brick powered
echo "asserting drive-enable (R11 NO -> brick power); settling 1.5 s..."
halcmd setp $EN 1 2>/dev/null
sleep 1.5

# now spin: stepgen.00 forward, stepgen.01 reverse (counter-rotate)
halcmd setp $BOARD.stepgen.00.velocity-cmd  "$REVS" 2>/dev/null
halcmd setp $BOARD.stepgen.01.velocity-cmd "-$REVS" 2>/dev/null

echo "spinning both at $RPM RPM, opposite directions. Ctrl-C to stop."
while kill -0 "$HALPID" 2>/dev/null; do
  V0=$(halcmd getp $BOARD.stepgen.00.velocity-fb 2>/dev/null)
  V1=$(halcmd getp $BOARD.stepgen.01.velocity-fb 2>/dev/null)
  R0=$(awk "BEGIN{printf \"%.0f\", ${V0:-0}*60}")
  R1=$(awk "BEGIN{printf \"%.0f\", ${V1:-0}*60}")
  printf '  stepgen.00 ~ %s RPM   stepgen.01 ~ %s RPM   (target %s)\n' "${R0:-?}" "${R1:-?}" "$RPM"
  sleep 1
done
