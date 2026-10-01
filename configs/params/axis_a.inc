# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_a.inc -- shared [AXIS_A] body (swivel-head TILT about X/W, degrees).
# A soft limit is DISABLED (see below); JOINT_4 still holds +/-115 deg.
# NOTE: LinuxCNC enforces soft limits only AFTER the axis is homed, and they are
# only ABSOLUTE if home was set to the true head angle -- see docs/gui.md.
# 2026-08-16: 2 -> 4 deg/s2, operator "lets double it to 4". ACCELERATION
# was the cap on A's G0, not MAX_VELOCITY 30: at 2 deg/s2 reaching 30 needed
# 225 deg and A has only 230 deg of travel, so 30 was never reached and every
# move ran a triangular profile. Time scales 1/sqrt(a): 90 deg goes 13.4->9.5 s.
# C is deliberately LEFT at 2 -- only A was asked for and only A was reasoned
# about. STEPGEN_MAXACCEL 450 is nowhere near limiting either.
MAX_VELOCITY = 30
# 2026-09-30: doubled, operator "let's double the accel for now" (A 4->8, C 2->4).
MAX_ACCELERATION = 8
# LIMITS DISABLED 2026-08-07 (operator: "disable all axis limits for now").
# An axis limit bounds the TOOL TIP, not the carriage; under ned_ac_kins
# the tip sits up to L*(1-cos A) above the joint, so a joint-sized number
# here refused most of Z. Real fix = limits as a function of L_tool.
# The JOINT limits below are untouched and still stop the machine.
MIN_LIMIT = -3600
MAX_LIMIT = 3600
