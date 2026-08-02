#!/usr/bin/env python3
"""Tool-change-active flag (staged 2026-08-02, apply AFTER verification).

Problem: ned_brain's program-done watchdog restored MANUAL mid-M6 and the
mode switch aborted the tool change (2026-08-02 01:34:22, T1 return leg).

Design: motion digital output P1 (unused in the iron) = TOOL CHANGE IN
PROGRESS. toolchange.ngc raises it first and drops it last; on_abort
drops it too. The brain nets it in (brain.tcactive-in <= sig-tc-active)
and, while TRUE: no MANUAL/teleop restore, no wedge-watchdog action on
A/C..., wedge watchdog stays (XYZ freeze mid-change must still abort).

Run this script only when the machine stack is DOWN.

GENERAL PRINCIPLE (proven 2026-08-02 02:13, harness-vs-handler): ANY
second actor sending task mode/MDI traffic while a homing sequence is
arming can wedge the group at INITIAL_SEARCH_START. The flag pattern
here is the tool-change instance of the same rule: one owner per
machine phase, everyone else waits for the flags (homing flags /
tc-active) to clear.
"""
import re
import sys

NED = '/home/brains/Documents/ned'
edits = []


def patch(path, old, new, must=1):
    src = open(path).read()
    n = src.count(old)
    if n != must:
        raise SystemExit('PATCH MISMATCH %s: %d occurrences of anchor '
                         '(want %d)' % (path, n, must))
    open(path, 'w').write(src.replace(old, new))
    edits.append(path)


# 1. toolchange.ngc: raise/drop the flag
patch(NED + '/configs/ned5_pb/subroutines/toolchange.ngc',
      "o100 if [#<_task> EQ 0]",
      "M64 P1 ; TOOL CHANGE IN PROGRESS flag (ned: brain suspends its\n"
      ";        MANUAL/teleop restore while this is high)\n"
      "o100 if [#<_task> EQ 0]")
patch(NED + '/configs/ned5_pb/subroutines/toolchange.ngc',
      "o<program_coolant> call",
      "M65 P1 ; tool change complete -> release the brain\n"
      "o<program_coolant> call")

# 2. on_abort.ngc: always drop the flag
src = open(NED + '/configs/ned5_pb/subroutines/on_abort.ngc').read()
if 'M65 P1' not in src:
    patch(NED + '/configs/ned5_pb/subroutines/on_abort.ngc',
          "o<on_abort> sub",
          "o<on_abort> sub\n"
          "M65 P1 (ned: clear the tool-change-in-progress flag on any abort)")

# 3. postgui: net the flag to a brain pin
patch(NED + '/configs/ned5_pb/postgui_pb.hal',
      "loadusr -Wn brain /home/brains/Documents/ned/tools/live/ned_brain.py",
      "loadusr -Wn brain /home/brains/Documents/ned/tools/live/ned_brain.py\n"
      "# TOOL CHANGE IN PROGRESS (toolchange.ngc M64/M65 P1): brain suspends\n"
      "# its MANUAL/teleop restore while high (it aborted an M6 mid-return,\n"
      "# 2026-08-02 01:34)\n"
      "net sig-tc-active motion.digital-out-01 => brain.tcactive-in")

# 4. brain: pin + gate
patch(NED + '/tools/live/ned_brain.py',
      "h.newpin('ref-a-in', hal.HAL_BIT, hal.HAL_IN)",
      "h.newpin('tcactive-in', hal.HAL_BIT, hal.HAL_IN)\n"
      "h.newpin('ref-a-in', hal.HAL_BIT, hal.HAL_IN)")
patch(NED + '/tools/live/ned_brain.py',
      "            if self.flip_armed and on \\\n"
      "               and s.task_mode != linuxcnc.MODE_MANUAL \\\n"
      "               and now - self.done_since >= 1.0:",
      "            if bool(h['tcactive-in']):\n"
      "                # TOOL CHANGE IN PROGRESS: never steal the mode --\n"
      "                # the restore aborted an M6 mid-return (01:34).\n"
      "                self.flip_armed = False\n"
      "                self.done_since = now\n"
      "            if self.flip_armed and on \\\n"
      "               and s.task_mode != linuxcnc.MODE_MANUAL \\\n"
      "               and now - self.done_since >= 1.0:")

print('applied to:')
for p in sorted(set(edits)):
    print('  ' + p)
import py_compile
py_compile.compile(NED + '/tools/live/ned_brain.py', doraise=True)
print('brain compiles OK')
