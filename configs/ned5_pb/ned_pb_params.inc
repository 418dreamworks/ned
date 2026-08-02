# ned_pb_params.inc -- Probe Basic GUI parameters, #INCLUDE'd under [DISPLAY]
# in ned5_pb.ini. PB-SPECIFIC values only: things the GUI wants that are not
# machine truth. IRON/machine values stay in ../params/*.inc (rule 11) --
# nothing here may duplicate a number that lives there.

# S-word preload shown by PB at startup (silences "No [DISPLAY]
# DEFAULT_SPINDLE_SPEED entry found, using 300rpm"). Set to the spindle's
# 9000: half the 18000 cap, so the 0-200% override spans the whole range
DEFAULT_SPINDLE_SPEED = 9000
# GUI spindle-speed range. MUST MATCH ../params/spindle_0.inc
# (MIN/MAX_FORWARD_VELOCITY = 1000/18000) -- the HQD GDL65 machine truth;
# without these PB caps its spindle display at a 2500 rpm default.
MIN_SPINDLE_0_SPEED = 1000
MAX_SPINDLE_0_SPEED = 18000
