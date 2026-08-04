#!/bin/bash
# halcheck.sh -- load ned's NEW realtime comps in ISOLATION and report whether
# every comp name, pin name, net and setp is valid. NO hm2_eth, NO board, NO
# motion: it loads only the comps, on a dummy thread, then tears down.
#
# WHY: I shipped two HAL edits in a row that killed the launch (a ';' comment,
# then an ini.N.* pin that does not exist at base-HAL load). Both were
# invisible to every other check and both cost the operator a launch cycle.
# cfg_edit.sh catches those two classes statically; this catches the rest --
# misspelled pins, wrong comp names, bad setp targets -- by actually loading.
#
# Run with LinuxCNC DOWN. Safe: touches no hardware.
#   tools/halcheck.sh
set -u
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if pgrep -x linuxcncsvr >/dev/null 2>&1; then
  echo "halcheck: LinuxCNC is RUNNING -- refusing (would fight the live HAL)."
  exit 1
fi

out=$(timeout 90 halrun -f "$D/halcheck_isolated.hal" 2>&1)
rc=$?
halrun -U >/dev/null 2>&1
if [ $rc -ne 0 ] || echo "$out" | grep -qiE 'error|does not exist|invalid|failed'; then
  echo "=== HAL ISOLATION CHECK FAILED ==="
  echo "$out" | grep -viE '^Note: Using POSIX realtime$'
  exit 1
fi
echo "halcheck: all isolated comps loaded and wired cleanly."
