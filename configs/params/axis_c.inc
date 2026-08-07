# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_c.inc -- shared [AXIS_C] body (swivel-head SPIN about Z, degrees).
# SOFT LIMIT C = +/-315 deg (crash-preventing; inside the manufacturer hard range).
# NOTE: enforced only AFTER homing, and absolute only if home = true head angle.
# Bounded (NOT a wrapping/rollover axis) so a +ve->-ve move interpolates through 0.
MAX_VELOCITY = 30
MAX_ACCELERATION = 2
MIN_LIMIT = -315.0
MAX_LIMIT = 315.0
