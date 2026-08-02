# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# joint_x2.inc -- X gantry side 2 ("W"). Lifted verbatim from configs/ned/ned.ini
# [JOINT_3]. In the 5-axis config this is JOINT_3 (second X-gantry joint; axis X).
TYPE = LINEAR
# MAX_VELOCITY + MAX_OUTPUT: WRITTEN by tools/live/ned_params.sh (MAX_VEL_LIN) -- edit THERE, never here.
MAX_VELOCITY = 200
MAX_ACCELERATION = 200.0
FERROR = 25.4
MIN_FERROR = 12.7
MIN_LIMIT = -4042.725
MAX_LIMIT = 1.0
P = 16.7
I = 4.828
D = 0.0
FF0 = 0.0
FF1 = 0.986
FF2 = 0.0
BIAS = 0.722
DEADBAND = 0.005
MAX_OUTPUT = 200
INPUT_SCALE  = 200.0
OUTPUT_SCALE = 356.5
BACKLASH = 0.0254
HOME = 0.0
HOME_OFFSET = 5.0
HOME_SEARCH_VEL = 64.0
HOME_LATCH_VEL = 1.666
HOME_FINAL_VEL = 6.35
# +1 NOT -1 (2026-07-31): negative = synchronized-final-move marker, and LinuxCNC
# BARS joint-jogging such joints unhomed (ini-homing.adoc:269) -- operator needs
# unhomed X jog. Anti-racking is carried by the MPG wiring instead: X-select
# drives joints 0 AND 3 with identical counts+scale (postgui_pb.hal), and the
# on-screen per-joint jog buttons are hidden.
HOME_SEQUENCE = -2
HOME_USE_INDEX = NO
HOME_IGNORE_LIMITS = YES
