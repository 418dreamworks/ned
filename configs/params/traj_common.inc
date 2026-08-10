# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# traj_common.inc -- shared [TRAJ] body (minus COORDINATES, which is per-case:
# XYZAC here vs XYZXBACB in the 8-joint config). #INCLUDE'd under a [TRAJ] header
# AFTER the COORDINATES line. Lifted verbatim from configs/ned/ned.ini.
LINEAR_UNITS = mm
ANGULAR_UNITS = degree
SPINDLES = 1
DEFAULT_LINEAR_VELOCITY = 20
MAX_LINEAR_VELOCITY = 333.334
DEFAULT_ANGULAR_VELOCITY = 15
MAX_ANGULAR_VELOCITY = 30
NO_FORCE_HOMING = 0
# BOOT AT THE LAST SESSION'S COORDINATES, natively (2026-08-10).
# taskintf.cc:1673-1730: joint pos_fb is written here at shutdown and
# restored via emcJointSetMotorOffset at startup. Replaces the Python
# stored_home.json declare for XYZ. It restores A/C too -- no per-joint
# opt-out exists -- which is harmless ONLY because A/C are
# HOME_ABSOLUTE_ENCODER=2: the first home overwrites the offset from the
# live pso pin and cannot move the head. Under =1 a stored number
# becomes travel; that is the 2026-08-07 C swing. Never set A/C to =1.
POSITION_FILE = position.txt
