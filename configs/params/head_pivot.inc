# head pivot fed to arm.in0 at HAL load (run5 bakes it into the tcp postgui).
# BANKED ON THE OPERATOR'S INSTRUCTION 2026-09-28 %s: "bank it".
# Source: logs/tcp_survey_20260928-204641.ndjson pair 9 -- the damped-Newton
# sweep (SVY_GAIN 0.30), nose = L 289.2761 minus the tool in force 146.6262.
# Taken from the MEASUREMENT RECORD, not the live pin: the pin is re-seeded
# from this file at every relaunch, and reading it back wrote a stale 157
# over a finished calibration on 2026-08-05 23:52.
#
# Tool in force: T10 '23/64 PrB', length 146.6262 re-touched at G30 the same
# evening (was 146.9348). A common bias in the tool lengths cancels here --
# this number carries -delta and every arm.in1 carries +delta -- but ONLY
# while every tool is touched off against the same nose #3010 = 232.624819.
# Re-measure the nose and you must re-touch every tool.
#
# Previous: 155.9256 (89-pair consensus, 2026-08-06, against a tool of
# 164.8485). The sweep moved it 13.2757 mm.
#
# NOT CONVERGED TO THE STOP. SVY_DONE is 0.25 mm on the mean of the last 5
# dL; pair 9 still implied about 1.3 mm. Banked because it is already far
# better than 155.9256, and the remaining residual is dominated by a split
# between the two tilt sides (mp -0.2320 vs mn +0.5793) that the mean-based
# step cannot remove -- L*sin(phi) puts that at an A zero off by 0.160 deg.
PIVOT_LENGTH = 142.6499
