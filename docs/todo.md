# To do — Machining: running ned as built

Setup, wiring and commissioning items moved to Controls on 2026-10-01 (~/Documents/controls/docs/todo.md).

## Rotary roughing strategy -- parallel passes, not driven rotation (2026-08-12)
Operator, after the 2in fly cutter stalled the B steppers repeatedly:
"i think its a mistake to ask the stepper to power through the flycutter.
for rough cuts, it should be parallel cuts. this lets the spindle do the
work against the wormgears. the steppers turning rapidly should be for final
finishing passes".

WHY IT MATTERS. rotary_face drives the cut with B: the stock's rotation IS
the feed, so every newton of cutting force is reacted by the steppers
through a 1:20 worm. Open loop, they stall silently and the position is
lost with nothing in software the wiser. Measured that evening: the fly
cutter asked for 2.40 mm^2 of chip per tooth against the 3/8's 1.43, with
3 teeth instead of 2, and the chip load the operator wanted needed
147.8 deg/s of B against a 90 deg/s ceiling.

THE SHAPE OF THE FIX. Rough with Y traverse at a fixed B index: the spindle
cuts along the bar, the worm merely HOLDS, and its self-locking geometry is
carrying a static load instead of a driven one. Index B by a step, cut the
next stripe, repeat. Keep the current B-driven helix for finishing, where
the depth -- and therefore the torque -- is small.

NOT BUILT. rotary_face is helix-only today.

## Collet engagement warning from OAL and SHOULDER (2026-08-13)
Operator: "if i have OAL and shoulder, i have a warning system if collet
engagement is insufficient".

    engagement = OAL - SHOULDER

SHOULDER is measured by PROBE SHOULDER against the same puck as the nose, so
it is the tip-to-nut-face distance: everything below the nut. OAL is the whole
tool. The difference is what the collet actually grips, and NO machine
constant is needed -- an earlier sketch needed the gauge-line-to-collet-face
distance and this does not.

THE RULE: collet makers want roughly 3 x shank diameter of engagement, and
SHANK IN is now a column, so the threshold is computable per tool rather than
a single number for the whole machine.

WHERE IT BELONGS: at touch-off time, not mid-cut. The tool is in the spindle
and stationary, and that is the last moment before it is trusted.

CATCHES THE OPPOSITE MISTAKE TOO: a tool so short it cannot reach the work.

NOT BUILT. Columns exist; nothing computes the difference yet.
