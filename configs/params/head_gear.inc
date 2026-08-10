# GENERATED from configs/params/MASTER.params by tools/live/gen_params.py -- DO NOT HAND-EDIT.
# Edit MASTER.params, then run: gen_params.py check && gen_params.py write
# head_gear.inc -- HAL-readable copy of the head gear ratios, GENERATED from
# [drivetrain] so the SSOT stays tools/live/ned_params.sh (rule 11). Exists so
# postgui can `setp` pso_live's gear pins from the ini instead of a literal.
# #INCLUDE under a [HEAD_GEAR] header.
A_GEAR = 128.25
C_GEAR = 203.7471
# direction convention, matches SIGN in tools/live/ned_brain.py
A_SIGN = -1
C_SIGN = 1
