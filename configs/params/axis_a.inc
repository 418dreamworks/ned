# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_a.inc -- shared [AXIS_A] body (swivel-head TILT about X/W, degrees).
# SOFT LIMIT A = +/-115 deg (crash-preventing; inside the manufacturer hard range).
# NOTE: LinuxCNC enforces soft limits only AFTER the axis is homed, and they are
# only ABSOLUTE if home was set to the true head angle -- see docs/gui.md.
MAX_VELOCITY = 30
MAX_ACCELERATION = 30
MIN_LIMIT = -115.0
MAX_LIMIT = 115.0
