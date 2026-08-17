# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_a.inc -- shared [AXIS_A] body (swivel-head TILT about X/W, degrees).
# A soft limit is DISABLED (see below); JOINT_4 still holds +/-115 deg.
# NOTE: LinuxCNC enforces soft limits only AFTER the axis is homed, and they are
# only ABSOLUTE if home was set to the true head angle -- see docs/gui.md.
MAX_VELOCITY = 30
# 2026-08-16: 2 -> 4 deg/s2, operator: "lets double it to 4". A's G0 was
# slow and ACCELERATION was the cap, not top speed -- at 2 deg/s2 it needed
# 225 deg to reach MAX_VELOCITY 30 and A only has 230 deg of travel, so the
# 30 was never once reached and every move was a triangular profile.
# Move time scales as 1/sqrt(a): a 90 deg move goes 13.4 s -> 9.5 s.
# STEPGEN_MAXACCEL is 450, so the stepgen is nowhere near limiting.
MAX_ACCELERATION = 4
# LIMITS DISABLED 2026-08-07 (operator: "disable all axis limits for now").
# An axis limit bounds the TOOL TIP, not the carriage; under ned_ac_kins
# the tip sits up to L*(1-cos A) above the joint, so a joint-sized number
# here refused most of Z. Real fix = limits as a function of L_tool.
# The JOINT limits below are untouched and still stop the machine.
MIN_LIMIT = -3600
MAX_LIMIT = 3600
