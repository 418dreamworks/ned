# Home + find A-zero (square the head) — final method, v5

Tonight's runnable routine, and the seed of a reusable **probing framework** (many future
routines will use the rod to locate where work sits on the table — same primitives).

Implementation: runnable O-word `.ngc` under `ned5_iron.ini` (see `configs/ned5/ngc/`).

## What each kind of touch can and can't sense (the key insight)
- The tool-probe TOP is **flat**, so a straight Z-down touch trips at the **same spindle-Z
  wherever the tip lands on it** (tip hangs a fixed `L·cosα` below the spindle). A flat surface
  therefore carries **no lateral information** — you only learn its height.
- An **edge / point** does carry lateral info: the touch-Z shifts as you move across it.
So: measure the top's HEIGHT with a flat Z-down touch; find the RIM with lateral (horizontal)
touches; measure the A-ANGLE with Z-down touches onto the rim **edge** (a point).

## Hardware / constants (locked)
- Rod: 3/8″ (r_rod = 4.76 mm), steel, grounded through the spindle (conductive touch-off).
- Tool probe: conductive, a piston that rises into ~6″ of clear air on the Bimba solenoid.
  Raise = **M64 P3** (motion.digital-out-03 → toolsetter-deploy → 7I84 OUTPUT12); lower = M65 P3.
  Trip = `motion.probe-input` (tool-probe-contact / 7I84 INPUT28) → G38.2. rim_dia = TODO (ask).
- **Substantial overtravel force** → touches are slow (rapid to 1 mm, then 5 mm/min) and, where
  possible, **Z-down** (loads the piston axially, not in bending).
- PLANE_AXIS = Y. Metric (G21). A/C angular; A soft-limit ±115, C ±315.

## (a) HOME + soft-limit familiarisation
Home X/Y/Z normally; A/C home in place at the eyeballed zero (safe: ~2° zero vs 5° margin).
Then, to see how motion stops, **JOG** A toward ±115 and C toward ±315 in the GUI and watch the
soft limit stop the jog. (A soft limit tripped inside a G-code program just aborts it — so this
is a manual jog observation, not part of the routine.)

## (b) findToolProbe — teach top + rim  [reusable]
    M64 P3 (raise Bimba), dwell
    TOP:  go to approx center, 5 mm above; probe_down -> Z_top  (flat top -> its height)
    RIM (3 points, horizontal):
        tilt A = +5°   (rod tip becomes an offset POINT, so it catches the rim edge, not the barrel)
        for C in {0°, 120°, 240°}:     # C swings the offset tip to 3 clock positions
            move OUT clear of the rim ; DOWN to just below Z_top ; probe_in toward center
            (very slow) until touch -> one rim point ; retract
        A -> 0
        fit 3 points -> probe CENTER (Xc,Yc) + measured R  (sanity-check vs rim_dia/2)

## (c) go to center, D above
    rapid to (Xc, Yc), Z = Z_top + D (5 mm)

## Primitive: lean(A) -> slope   [Z-down onto the rim EDGE; A fixed]
    retract clear, THEN move to A            # never rotate near the probe
    probe_down onto the rim edge at spindle-Y = y_a  -> Z_a
    probe_down onto the rim edge at spindle-Y = y_b  -> Z_b      (y_b - y_a = y_spread)
    verify each trip (#5070) or ABORT
    return slope = (Z_b - Z_a) / (y_b - y_a)         # = cot(tilt); a POINT touch, so it varies with Y

## (d)/(e) measure both sides, split
    slope_plus = lean(+60°)                          # near-horizontal: big, sensitive signal
    find A_minus near -60° s.t. lean(A_minus) = -slope_plus within tol_slope
        (secant + bisection, bounded by max_iter and the ±115 soft limit)
    A_zero = (A_plus + A_minus) / 2                  # encoder midpoint = square

## (f) record
    store A_zero to head_zero.inc as the A home reference (single source, rule 11).
    M65 P3 (lower Bimba). Report A_zero, slope_plus, final slope_minus, rim center+R, full log.

## Params
    rim_dia=TODO  rod_dia=9.525  above=5  D=5  standoff=1  (mm)
    tilt_rim=5  tilt_lean=60  (deg)   y_spread=20 (mm)
    feed_touch=5 mm/min (after the 1 mm standoff)   tol_slope=0.002   A_step=5   max_iter=12

## Safety invariants
- Retract clear before ANY A/C move — never rotate near the probe.
- Every G38.2 checks #5070 or ABORTs — never plow.
- Rapid only to the 1 mm standoff; last mm at 5 mm/min. Single touch (position known).
- Respect ±115 / ±315; never command past, never deliberately trip a soft limit in code.
- Bimba raised the whole routine; lowered only at the end.

## Open
- rim_dia (mm) — the one value still to fill.
- Confirm on the machine that the 60° rod actually reaches the rim edge at both y offsets.
