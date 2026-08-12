#!/bin/bash
# STAGED 2026-08-12 -- apply at idle. No restart needed (.ngc is re-read).
set -e
cd /home/brains/Documents/ned
tools/cfg_edit.sh <<'PYEOF'
import io
p='configs/ned5_pb/subroutines/rotary_face.ngc'
s=io.open(p,encoding='utf-8').read()

old_start = s.index("    (PLUNGE CAP, SCALED BY THE TOOL.")
old_end   = s.index("    G90\n", s.index("    G1 Y[#<len> * #<dir>]")) + len("    G90\n")
new = """    (RAMP IN, DO NOT PLUNGE. A separate Z-only dive is a 90 degree corner
    (in the path: the planner has to swing from pure Y to pure Z, and even
    (with G64 P0.5 there is only half a millimetre of arc to do it in, so B
    (crawled under 5 deg/s for about 0.8 s at every corner -- measured
    (2026-08-12, 4 samples under 5 and 19 under 40 out of 1336.
    (Descending DURING the sweep removes the corner entirely: Y, Z and B all
    (move together and nothing ever changes direction mid-pass. The only
    (slowdown left is the Y reversal at the ends, which the operator accepts.
    (ONE REVOLUTION OF STOCK PER RAMP. Y advances one pitch while Z drops the
    (full radial depth and B turns once, so the entry is a helix at the same
    (feed as the cut. Z rate works out at doc/pitch times the feed, which for
    (a half-diameter stepover is exactly the feed -- well under the plunge
    (ceiling below.
    #<pmax>  = [#<tdia> * 18.9]
    #<pfeed> = #<feed>
    o106 if [#<pfeed> GT #<pmax>]
      #<pfeed> = #<pmax>
    o106 endif
    #<dz>   = [#<r> - #<rprev>]
    #<yrun> = #<len>
    #<brun> = [#<revs> * 360.0]
    o105 if [#<dz> LT 0]
      (SPINDLE UP THROUGH THE RAMP so the chip is lighter where the tool is
      (engaging axially as well as radially -- operator 2026-08-12: "spin up
      (spindle speed during the ramp to cut less". Same feed, twice the
      (teeth per minute, so half the chip load. Capped at the drive ceiling.
      #<sramp> = [#<sout> * 2.0]
      o107 if [#<sramp> GT #<rf_smax>]
        #<sramp> = #<rf_smax>
      o107 endif
      S#<sramp>
      G91
      G1 Y[#<pitch> * #<dir>] Z[#<dz>] B[360.0] F[#<pfeed>]
      G90
      #<yrun> = [#<len> - #<pitch>]
      #<brun> = [#<brun> - 360.0]
    o105 endif

    (THE REST OF THE PASS AT DEPTH. One block, no corners: Y against B is a
    (straight line, so a single G1 with both words IS the helix exactly.
    S#<sout>
    G91
    G1 Y[#<yrun> * #<dir>] B[#<brun>] F[#<feed>]
    G90
"""
s = s[:old_start] + new + s[old_end:]

# the old print referenced pfeed only; keep it honest about the ramp
a="    (PRINT, ROTARY FACE: pass #<pass> at diameter #<dnow> - Z #<r>, B #<brpm> rpm, Y feed #<fmms> mm per sec, plunge #<pmms> mm per sec, chip load #<fzreal>)"
if a in s:
    s=s.replace(a,"    (PRINT, ROTARY FACE: pass #<pass> at diameter #<dnow> - Z #<r>, B #<brpm> rpm, Y feed #<fmms> mm per sec, ramp feed #<pmms> mm per sec, chip load #<fzreal>)")
io.open(p,'w',encoding='utf-8').write(s)
bad=[(i+1,l) for i,l in enumerate(s.split('\n')) if l.count('(')!=l.count(')')]
print('unbalanced comment lines:', bad if bad else 'none')
print('ramp-in written')
PYEOF
timeout 100 tools/gcode_check.sh rotary_face 9 109 95 540 0.3 2 30 2>&1 | tail -2
echo "APPLIED -- no restart needed"
