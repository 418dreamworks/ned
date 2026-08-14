# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# display_common.inc -- shared [DISPLAY] body (minus the DISPLAY= GUI selector,
# which is per-config). #INCLUDE'd under a [DISPLAY] header, AFTER the DISPLAY=
# line. Lifted verbatim from configs/ned/ned.ini.
CYCLE_TIME = 0.05
POSITION_OFFSET = RELATIVE
POSITION_FEEDBACK = ACTUAL
# 200%: the operator ran out of override on the kakeya groove and the log
# shows it pinned -- "OVR F: 150 -> 150" over and over (2026-08-13).
MAX_FEED_OVERRIDE = 2.0
MAX_SPINDLE_OVERRIDE = 2.0
MIN_SPINDLE_OVERRIDE = 0.2
INTRO_GRAPHIC = linuxcnc.gif
INTRO_TIME = 2
PROGRAM_PREFIX = /home/brains/linuxcnc/nc_files
INCREMENTS = 0.01 mm, 0.05 mm, 0.1 mm, 0.5 mm, 1 mm
SPINDLES = 1
DEFAULT_LINEAR_VELOCITY = 20
MAX_LINEAR_VELOCITY = 333.334
