# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# joint_z.inc -- Z vertical. Lifted verbatim from configs/ned/ned.ini [JOINT_2].
# In the 5-axis config this is JOINT_2 (axis Z). Z homes first and to the TOP.
TYPE = LINEAR
MAX_VELOCITY = 169.3
MAX_ACCELERATION = 200.0
FERROR = 12.7
# 2.54 was five times tighter than X and Y, on the axis that does the
# longest fastest move in every program. 169.3 mm/s x 15 ms = 2.539 mm,
# so fifteen milliseconds of servo stall spent the WHOLE window -- and
# this Pi logs "Unexpected realtime delay" regularly. Z was always the
# one that tripped. Operator 2026-09-29, after a joint 2 following error
# on the first G53 G0 Z0 of a marking program: "man this is SO FUCKING
# UNSTABLE" ... "do A first". 12.7 is what joints 0, 1 and 3 already run
# at 200 mm/s on the same drives; Z is not more precious than the gantry.
MIN_FERROR = 12.7
MIN_LIMIT = -620.0
MAX_LIMIT = 1.0
P = 20.5406
I = 7.2877
D = 0.000587
FF0 = 0.0
FF1 = 0.994355
FF2 = 0.006358
BIAS = 0.437
DEADBAND = 0.005
# MAX_OUTPUT: WRITTEN by tools/live/ned_params.sh (MAX_VEL_LIN) -- edit THERE, never here.
MAX_OUTPUT = 200
INPUT_SCALE  = 787.402
OUTPUT_SCALE = 178.2
BACKLASH = 0.0
HOME = 0.0
HOME_OFFSET = 5.0
HOME_SEARCH_VEL = 80.0
HOME_LATCH_VEL = 1.666
HOME_FINAL_VEL = 6.35
HOME_SEQUENCE = 0
HOME_USE_INDEX = NO
HOME_IGNORE_LIMITS = YES
