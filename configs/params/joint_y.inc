# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# joint_y.inc -- Y cross. Lifted verbatim from configs/ned/ned.ini [JOINT_1].
# In the 5-axis config this is JOINT_1 (axis Y).
TYPE = LINEAR
# MAX_VELOCITY + MAX_OUTPUT: WRITTEN by tools/live/ned_params.sh (MAX_VEL_LIN) -- edit THERE, never here.
MAX_VELOCITY = 200
MAX_ACCELERATION = 200.0
FERROR = 25.4
MIN_FERROR = 12.7
MIN_LIMIT = -1787.0
MAX_LIMIT = 1.0
P = 16.7
I = 4.975
D = 0.0
FF0 = 0.0
FF1 = 1.005
FF2 = 0.0
BIAS = 1.0095
DEADBAND = 0.005
MAX_OUTPUT = 200
INPUT_SCALE  = 250.0
OUTPUT_SCALE = 356.5
HOME = 0.0
HOME_OFFSET = 5.0
HOME_SEARCH_VEL = 64.0
HOME_LATCH_VEL = 1.666
HOME_FINAL_VEL = 6.35
HOME_SEQUENCE = 1
HOME_USE_INDEX = NO
HOME_IGNORE_LIMITS = YES
