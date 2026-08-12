#!/bin/bash
# STAGED 2026-08-12 -- apply when the cycle finishes, then restart PB.
# Three changes that belong together:
#   1. G64 P0.5 for the cycle, plain G64 restored at the end. Bare G64 only
#      collapses collinear moves, so the Y-sweep -> Z-dive corner forced the
#      path velocity to zero and B stopped between passes.
#   2. rf_bmax default 90 -> 120 deg/s in the .ngc.
#   3. RF_BMAX 90 -> 120 in the GUI, so the page and the cycle agree.
# run5.sh already carries MAX_VELOCITY 120 / STEPGEN_MAXVEL 144 (20 rpm at
# the chuck, 400 rpm at the motor); that one only takes effect on relaunch.
set -e
cd /home/brains/Documents/ned
tools/cfg_edit.sh <<'PYEOF'
import io
p='configs/ned5_pb/subroutines/rotary_face.ngc'
s=io.open(p,encoding='utf-8').read()
a="  G90\n  (SPINDLE FIRST, THEN TEN SECONDS, THEN MOVE."
b="""  G90
  (BLEND THE CORNERS SO THE STOCK NEVER STOPS TURNING. Bare G64 -- what the
  (machine defaults to -- only collapses collinear moves, so at the corner
  (between the Y sweep and the Z dive the planner must arrive exactly on the
  (corner point: Y decelerates to zero before Z starts, path velocity hits
  (zero, and B stops with it. That is the pause seen between passes.
  (P0.5 lets it miss the corner by half a millimetre and carry speed through
  (an arc instead, so B keeps turning. Plain G64 is restored at the end.
  G64 P0.5
  (SPINDLE FIRST, THEN TEN SECONDS, THEN MOVE."""
assert s.count(a)==1, 'G90 anchor'
s=s.replace(a,b)
c="  G0 G53 Z0\n  M5\n"
assert s.count(c)==1, 'tail anchor'
s=s.replace(c,"  G0 G53 Z0\n  M5\n  G64\n")
d="  #<rf_bmax>   = #8 (=90.0 B max deg/s - JOINT_6 MAX_VELOCITY, 15 rpm)"
assert s.count(d)==1, 'rf_bmax arg'
s=s.replace(d,"  #<rf_bmax>   = #8 (=120.0 B max deg/s - JOINT_6 MAX_VELOCITY, 20 rpm)")
e="""  o2 if [#<rf_bmax> LE 0]
    #<rf_bmax> = 90.0
  o2 endif"""
assert s.count(e)==1, 'rf_bmax default'
s=s.replace(e,"""  o2 if [#<rf_bmax> LE 0]
    #<rf_bmax> = 120.0
  o2 endif""")
# RADIAL DEPTH IS HALF THE TOOL DIAMETER, FULL STOP (operator 2026-08-12:
# "make the plunge 1/2 of tool diameter and the stepover 1/2 of tool
# diameter as well. it seems ok"). The 6.35 mm term was a fixed ceiling that
# did nothing for the 3/8 in hand and would have clipped any tool above
# 1/2 inch for no stated reason. Flute length still caps it, because a cut
# deeper than the flutes has nowhere to put the chip.
g='''  #<doc> = #<trad>
  o23 if [#<doc> GT 6.35]
    #<doc> = 6.35
  o23 endif
'''
assert s.count(g)==1, 'doc cap'
s=s.replace(g,'  #<doc> = #<trad>\n')
io.open(p,'w',encoding='utf-8').write(s)

q='configs/ned5_pb/user_tabs/ned_controls/ned_controls.py'
t=io.open(q,encoding='utf-8').read()
f="    RF_BMAX = 90.0        # [JOINT_6]MAX_VELOCITY, tools/run5.sh -- 15 rpm"
assert t.count(f)==1, 'RF_BMAX'
t=t.replace(f,"    RF_BMAX = 120.0       # [JOINT_6]MAX_VELOCITY, tools/run5.sh -- 20 rpm")
t=t.replace("""        doc = min(trad, 6.35)""", """        doc = trad""")
io.open(q,'w',encoding='utf-8').write(t)
print('applied: G64 P0.5, rf_bmax 120, RF_BMAX 120, radial depth = tool dia / 2')
PYEOF
python3 -m py_compile configs/ned5_pb/user_tabs/ned_controls/ned_controls.py
timeout 100 tools/gcode_check.sh rotary_face 9 140 130 200 0.3 2 30 2>&1 | tail -2
echo "STAGED CHANGES APPLIED -- restart PB to pick up MAX_VELOCITY 120"
