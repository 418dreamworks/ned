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
# 45 deg/s FOR B (operator 2026-08-13: "it should be a lot faster ... like 45
# deg a second ... just for B" / "leave A and C as is, change it for B").
# THIS IS THE SHARED ROTARY CEILING AND IT IS ALSO THE ONLY THING THAT WAS
# HOLDING B BACK. B's own [AXIS_B] MAX_VELOCITY is already 90, so B was never
# axis-limited -- it was clamped to 30 here, and a G0 B move ran at 30 deg/s.
# A AND C DO NOT MOVE. They cap themselves at [AXIS_A]/[AXIS_C] MAX_VELOCITY
# = 30, and LinuxCNC takes the lower of the axis limit and this ceiling, so
# raising the ceiling cannot speed them up. There is no per-axis TRAJ angular
# limit to set -- the axis sections ARE the per-axis limits.
MAX_ANGULAR_VELOCITY = 45
# ---- TRAJECTORY PLANNER LOOKAHEAD -----------------------------------------
# ned had NO [TRAJ] TP settings at all, so it ran on LinuxCNC's defaults --
# and the default lookahead is 50 segments. The manual gives the sizing
# formula (docs/linuxcnc/manual/config/ini-config.html:1530):
#     n = v_max / (2.0 * a_max * t_c)      t_c = servo period = 0.001 s
# and says outright: "If during testing, you notice strange slowdowns and
# can't figure out where they come from, first try increasing this depth."
# For this machine that formula asks for:
#     X/Y  200 mm/s  / 200 mm/s^2  ->  500
#     Z    169.3     / 200         ->  423
#     B     90 deg/s /  30 deg/s^2 -> 1500   <- worst, because its accel is
#                                              lowest, so its ramp is longest
# 50 was 10-30x too shallow for every axis. THAT is why the T12 groove --
# 3620 back-to-back B-only blocks of 2.000 deg -- never reached its
# commanded rate, and why raising F did nothing.
# WHY NOT JUST RAISE ACCELERATION: B is two steppers on a 1:20 worm with no
# encoder (operator 2026-08-13: "i don't want to raise acceleration because
# steppers die silently ... until i have encoders, we can't raise accel").
# Lookahead costs no torque and cannot stall anything.
# 500 FIRST, NOT 1500. The only real cost is realtime headroom -- deeper
# lookahead is more work per servo cycle and this Pi already emits
# "Unexpected realtime delay on task 0". Step up one value per run and
# revert the moment that count rises.
ARC_BLEND_ENABLE = 1
ARC_BLEND_FALLBACK_ENABLE = 0
ARC_BLEND_OPTIMIZATION_DEPTH = 500
ARC_BLEND_GAP_CYCLES = 4
ARC_BLEND_RAMP_FREQ = 100
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
