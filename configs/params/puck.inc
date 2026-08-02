# puck.inc -- SINGLE SOURCE for the tool-probe ("puck") LOCATION.  [PUCK] section.
# G-code CANNOT rewrite an INI, so the checkpoint routines READ the seeds here and
# LOG their refined results to puck_result.txt (in the config dir) for you to paste
# back in. Nothing here is duplicated in any other file (CLAUDE.md rule 11).
#
#   APPROX_ABOVE  how far above the top to start CP1's down-probe (safe gap).
#   Z_TOP, CENTER_X, CENTER_Y  last measured (CP1/CP2 write to persistent params
#                              #5211/#5212/#5213 for the live run; update these from
#                              puck_result.txt so the next session seeds well).
APPROX_ABOVE = 10.0    # mm, safe start gap above the puck top for CP1
Z_TOP        = 0.0     # mm, measured top-touch spindle-Z reference (from CP1 log)
CENTER_X     = 0.0     # mm, measured puck center X (from CP2 log)
CENTER_Y     = 0.0     # mm, measured puck center Y (from CP2 log)
