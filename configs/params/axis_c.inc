# axis_c.inc -- shared [AXIS_C] body (swivel-head SPIN about Z, degrees).
# SOFT LIMIT C = +/-315 deg (crash-preventing; inside the manufacturer hard range).
# NOTE: enforced only AFTER homing, and absolute only if home = true head angle.
# Bounded (NOT a wrapping/rollover axis) so a +ve->-ve move interpolates through 0.
MAX_VELOCITY = 30
MAX_ACCELERATION = 300
MIN_LIMIT = -315.0
MAX_LIMIT = 315.0
