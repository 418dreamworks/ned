# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_c.inc -- shared [AXIS_C] body (swivel-head SPIN about Z, degrees).
# C soft limit is DISABLED (see below); JOINT_5 still holds +/-315 deg.
# NOTE: enforced only AFTER homing, and absolute only if home = true head angle.
# Bounded (NOT a wrapping/rollover axis) so a +ve->-ve move interpolates through 0.
MAX_VELOCITY = 30
MAX_ACCELERATION = 2
# LIMITS DISABLED 2026-08-07 (operator: "disable all axis limits for now").
# An axis limit bounds the TOOL TIP, not the carriage; under ned_ac_kins
# the tip sits up to L*(1-cos A) above the joint, so a joint-sized number
# here refused most of Z. Real fix = limits as a function of L_tool.
# The JOINT limits below are untouched and still stop the machine.
MIN_LIMIT = -3600
MAX_LIMIT = 3600
