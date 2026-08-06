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
MAX_ACCELERATION = 30
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
# HOME_ABSOLUTE_ENCODER=1: homing sets the DRO to this position, then MOVES the head to 0
# (= encoder zero in head_zero.inc = physical zero) at HOME_FINAL_VEL.
HOME_OFFSET = 0.0
HOME_ABSOLUTE_ENCODER = 1
HOME_FINAL_VEL = 5
HOME_SEARCH_VEL = 0
HOME_LATCH_VEL = 0
# sequence 2 (POSITIVE): last in HOME ALL, A+C home concurrently via the homing
# module's own machinery (individually-commanded concurrent homes wedged joint 4's
# state machine 2026-07-31). A per-axis ref homes ONLY that joint (ini-homing.adoc:267).
# The REF ALL button (dros_xyzac.py -> ned_controls.request_homeall) unhomes A/C
# FIRST (HOME_NO_REHOME no-op otherwise) and tools/live/ned_brain.py arms the fresh
# absolute read in parallel while XYZ homes; its guard blocks un-armed A/C homing.
HOME_SEQUENCE = 3
HOME_USE_INDEX = NO
