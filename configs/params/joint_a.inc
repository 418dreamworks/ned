# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# joint_a.inc -- A swivel-head TILT (about X/W). Lifted verbatim from
# configs/ned/ned.ini [JOINT_5]. In the 5-axis config this is JOINT_4 (axis A).
#
# !!! ned_params.sh WARNING !!!
#   tools/live/ned_params.sh is the source-of-truth for SCALE (SCALE_A = DRIVE_PPR*GEAR_A/360).
#   Its `apply`/`sync` writer keys on the OLD 8-joint map (J4=B-rotary, J5=A, J6=C) and
#   only rewrites *.ini files. In THIS 5-axis config A is JOINT_4, so running
#   ned_params.sh against ned5 would write the ROTARY scale onto A. DO NOT run
#   ned_params.sh apply/sync against configs/ned5 until its joint map is updated.
#   The value below is the current derived SCALE_A, hand-placed. See docs/gui.md.
TYPE = ANGULAR
MAX_VELOCITY = 30
# 2026-08-16: 2 -> 4 deg/s2, operator: "lets double it to 4". A's G0 was
# slow and ACCELERATION was the cap, not top speed -- at 2 deg/s2 it needed
# 225 deg to reach MAX_VELOCITY 30 and A only has 230 deg of travel, so the
# 30 was never once reached and every move was a triangular profile.
# Move time scales as 1/sqrt(a): a 90 deg move goes 13.4 s -> 9.5 s.
# STEPGEN_MAXACCEL is 450, so the stepgen is nowhere near limiting.
MAX_ACCELERATION = 4
STEPGEN_MAXVEL = 36
STEPGEN_MAXACCEL = 450
# SCALE sign = A motion direction. POSITIVE (paired with pso_home.sh A sign=-1) so A+ = right-hand-rule
# while homing still lands at physical zero. Magnitude = ned_params.sh SCALE_A.
SCALE = +2918.4000
FERROR = 5.0
MIN_FERROR = 1.0
# Soft limit A = +/-115 deg (5 deg margin inside the +/-120 mechanical hard range).
MIN_LIMIT = -115.0
MAX_LIMIT = 115.0
HOME = 0.0
# HOME_OFFSET is WRITTEN at every homing by tools/live/ned_brain.py (live absolute read via
# ini.4/5.home_offset, zeroed against configs/params/head_zero.inc). SSOT of the zero is
# head_zero.inc; the value here is a fallback -- do NOT hand-edit. With
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
