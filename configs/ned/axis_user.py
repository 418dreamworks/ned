# Axis GUI customization -- sourced via [DISPLAY]USER_COMMAND_FILE, run just before
# the GUI is shown (after glcanon reads the ini, so these win). Namespace has the
# live-plotter object `o` (a GlCanonDraw subclass, /usr/bin/axis).
#
# Trim the DRO so the sub-encoder-count last-digit dither isn't displayed. X is
# 200 counts/mm = 0.005 mm/count, so 0.01 mm is the meaningful digit; the 4th mm
# decimal is just float/quantization noise sitting on zero.
#   mm -> 0.01 mm   (was % 9.3f)
#   in -> 0.001 in  (was % 9.4f)
o.dro_mm = "% 9.2f"
o.dro_in = "% 9.3f"
