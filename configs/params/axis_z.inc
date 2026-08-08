# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# axis_z.inc -- shared [AXIS_Z] body. Lifted verbatim from configs/ned/ned.ini.
MAX_VELOCITY = 169.3
MAX_ACCELERATION = 200.0
# LIMITS DISABLED 2026-08-07 (operator: "disable all axis limits for now").
# An axis limit bounds the TOOL TIP, not the carriage; under ned_ac_kins
# the tip sits up to L*(1-cos A) above the joint, so a joint-sized number
# here refused most of Z. Real fix = limits as a function of L_tool.
# The JOINT limits below are untouched and still stop the machine.
MIN_LIMIT = -1620
MAX_LIMIT = 1001
