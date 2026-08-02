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
