# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# joint_c.inc -- C swivel-head SPIN (about Z). Lifted verbatim from
# configs/ned/ned.ini [JOINT_6]. In the 5-axis config this is JOINT_5 (axis C).
#
# !!! ned_params.sh WARNING (see joint_a.inc) !!!
#   SCALE_C = DRIVE_PPR*GEAR_C/360, source-of-truth tools/live/ned_params.sh. Its writer
#   maps J6=C (8-joint layout); here C is JOINT_5, so ned_params.sh apply/sync would
#   mis-place scales. DO NOT run it against configs/ned5. Value below hand-placed.
TYPE = ANGULAR
MAX_VELOCITY = 30
MAX_ACCELERATION = 2
STEPGEN_MAXVEL = 36
STEPGEN_MAXACCEL = 450
# SCALE sign = C motion direction (negative: motor turns opposite to encoder/DRO+). Magnitude = ned_params.sh SCALE_C.
SCALE = -4636.3785
FERROR = 5.0
MIN_FERROR = 1.0
# Soft limit C = +/-315 deg. Bounded (WRAPPED_ROTARY unset) so the homing final move
# unwinds NUMERICALLY to 0 -- from +300 it travels -300, never the +60 shortest wrap.
MIN_LIMIT = -315.0
MAX_LIMIT = 315.0
HOME = 0.0
# HOME_OFFSET is WRITTEN at every homing by tools/live/ned_brain.py (live absolute read via
# configs/params/head_zero.inc), UNWRAPPED (no mod-360 fold: +190 stays +190). SSOT of the
# zero is head_zero.inc; this line is regenerated every launch -- do NOT hand-edit. With
# HOME_ABSOLUTE_ENCODER=2 (2026-08-10): homing sets the joint position to
# HOME_OFFSET and STOPS -- homing.c:1139-1146 jumps straight to HOME_FINISHED,
# there is no final move in the state machine at all. So a wrong offset is a
# wrong NUMBER, never travel. Under =1 the final move to HOME made a bad
# offset into motion: that is the -114.7 deg C swing of 2026-08-07 and the
# ~102 deg A/C swing of 2026-08-10. A and C have no switches, so =2 costs
# nothing -- driving the head to zero is now an ordinary commanded move,
# separate from homing.
# NOTE both =1 and =2 imply HOME_NO_REHOME (taskintf.cc:326-336), so a second
# home in one session needs unhome() first (homing.c:766-770).
HOME_OFFSET = 0.0
HOME_ABSOLUTE_ENCODER = 2
HOME_FINAL_VEL = 5
HOME_SEARCH_VEL = 0
HOME_LATCH_VEL = 0
# same sequence as A (joint_a.inc) -> A and C home / rotate to zero TOGETHER
# sequence 2 (POSITIVE): last in HOME ALL, A+C home concurrently via the homing
# module's own machinery (individually-commanded concurrent homes wedged joint 4's
# state machine 2026-07-31). A per-axis ref homes ONLY that joint (ini-homing.adoc:267).
# The REF ALL button (dros_xyzac.py -> ned_controls.request_homeall) unhomes A/C
# FIRST (HOME_NO_REHOME no-op otherwise) and tools/live/ned_brain.py arms the fresh
# absolute read in parallel while XYZ homes; its guard blocks un-armed A/C homing.
# HOME_SEQUENCE removed 2026-08-06: A/C never home via the task home-all.
# The brain homes them read-gated (pending_ref) -- Home All consumed
# stale ini.N.home_offset when a prior cycle left read_armed latched,
# tilting A by the stale value each cycle (compounding).
HOME_USE_INDEX = NO
