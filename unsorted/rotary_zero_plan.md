```
GOAL
LinuxCNC probing routines to find machine zero AND calibrate angular scale for the A and C
rotary axes of a swivel head, using a single-point conductive probe and a straight rod in
the spindle.

CORE MODEL
A single-sided side touch on the rod at orientation theta:
    P_contact(theta) = P_center + L*tan(theta) - r*sec(theta)
    L = position along the rod, r = rod radius
- Differencing two touches at the SAME theta kills the sec term. Zeroing is r-free and is
  done as null-seeking: drive an error signal to zero, never convert a touch to an angle.
- Comparing ACROSS theta leaves r*(sec(theta2) - sec(theta1)). Scale calibration spans a
  large angular range, so it REQUIRES r. This is why rod_dia is a measured input.

SEQUENCE
    1. Zero A        (null, r-free)
    2. Calibrate A   (fit, needs r)
    3. Zero C        (null, r-free)
    4. Calibrate C   (fit, needs r)
Zero before calibrate on each axis: the fit is much better conditioned when it is centered
on a known null.

ASSUMPTIONS (correct these if wrong)
- LinuxCNC 2.9, O-word subroutines in .ngc, no host-side Python.
- A axis itself swings to +/-90 deg. C rotates about a Z-parallel axis.
- Probe is a single fixed POINT, not a plate. Approachable from +Y, -Z, and +X.
- Rod is straight and of constant diameter over the entire touched region.
- C is already known perpendicular to the bed. A starts eyeballed near zero.

DELIVERABLES
- rotary_zero.ngc      main entry, runs the four stages in order
- probe_touch.ngc      single-axis probe primitive
- null_search.ngc      shared secant + bisection driver
- find_a_zero.ngc      stage 1
- calib_a_scale.ngc    stage 2
- find_c_zero.ngc      stage 3
- calib_c_scale.ngc    stage 4
- config block of #<named> params at top of rotary_zero.ngc, nothing hardcoded downstream

CONFIG PARAMS
required, measured: rod_dia   <- micrometer, averaged over 3 places on the touched region.
                                 Do NOT use nominal stock size.
required: probe_feed fine_feed clearance standoff
          Z_a Z_b (stage 1 heights), Y_a Y_b (stage 4 positions)
          theta_list (calibration angles, e.g. 0 +/-15 +/-30 +/-45 +/-60 +/-75 +/-90)
          tol_A tol_C A_step C_step max_iter
          max_scale_err (abort threshold, arc-min per 90 deg)
optional: R_nominal (only to size the ~2R Y shift in stage 3)

STAGE 1 - ZERO A (rod vertical, probe +Y at two commanded Z heights)
- Touch at Z_a, retract, move to Z_b, touch. Record Y1, Y2 from #5062.
- error = (Y1 - Y2) / (Z_a - Z_b)      [sec term cancels, both touches same theta]
- Null on A. Result A_zero. Converge when |error| < tol_A.

STAGE 2 - CALIBRATE A SCALE (sweep theta, fit the sec term)
- For each theta in theta_list, relative to A_zero:
    rotate, re-establish clearance, probe the rod side at a fixed commanded L.
    Near vertical probe in +Y; past ~60 deg switch to -Z probing, since sec(theta)
    diverges and the +Y geometry degenerates. Record which direction was used.
- Fit measured contact positions against
      P = P_center + L*tan(k*theta_cmd + off) - r*sec(k*theta_cmd + off)
  solving for k (scale), off (residual offset), P_center. r is FIXED at rod_dia/2.
- Report (k - 1) as arc-min per 90 deg, plus fit residual RMS.
- ABORT if |scale error| > max_scale_err, or if residual RMS exceeds a few times the
  probe repeatability - a bad fit means the model is wrong, not the axis.
- Use overlapping +Y and -Z touches at mid angles as a consistency check on r: if the two
  branches disagree, rod_dia is wrong or the rod is not concentric in the spindle.

STAGE 3 - ZERO C (rod horizontal, probe +X, flip A between the two calibrated 90s)
- Use the calibrated A values for +90 and -90 from stage 2, not nominal commands.
- Lever arm R is set by commanded Y, not Z. Its value is never needed.
- Set Z so the probe bears near the rod centerline: Z = Z_bottom + rod_dia/2, where
  Z_bottom comes from a -Z touch on each side. Re-derive per side; the rod height changes
  across the A flip. An r error gives the same h both sides and cancels in the difference.
- Touch at A=+90 -> X1. Shift Y by ~2*R_nominal, flip to A=-90, re-derive Z, touch -> X2.
- error = X1 - X2       (approx 2*R*sin(eps_C); fixed offsets cancel)
- Null on C. Result C_zero. Converge when |error| < tol_C.

STAGE 4 - CALIBRATE C SCALE (rod horizontal, sweep C, probe +X at fixed Y)
- Same structure as stage 2, one plane down. For each theta in theta_list relative to
  C_zero, probe in +X at a fixed commanded Y:
      X_contact = X_center + Y*tan(theta) - r*sec(theta)
- Fit for k and off with r fixed. Report arc-min per 90 deg and residual RMS. Same aborts.
- Switch probing direction past ~60 deg for the same sec-divergence reason.

TOLERANCE CALC (print once, before stage 3)
- Off-center contact height h biases X by r - sqrt(r^2 - h^2), sensitivity h/sqrt(r^2-h^2).
- Evaluate at worst-case h from stage 2 residual tilt plus Z repeatability across the flip.
- Abort if the predicted bias exceeds tol_C rather than converging on a meaningless number.

NULL SEARCH (shared)
- Fixed first step, measure again, then secant. Bisection fallback on overshoot or
  inconsistent bracket sign. Cap at max_iter, abort with the full iteration log.

PROBE PRIMITIVE
- Rapid to standoff, G38.2 at probe_feed, read #5061-#5066.
- Check #5070; if zero, abort with a clear (ABORT,...) message.
- Always retract to clearance before ANY rotary move.
- Optional slow re-touch at fine_feed for the recorded value if repeatability is poor.
- Log rod_dia in every run header so a result can never be reinterpreted with a
  different assumed radius.

OUTPUT
- Log every touch (stage, commanded angle, probe direction, raw position) via (DEBUG,...).
- On success print A_zero, C_zero, both scale factors in arc-min per 90 deg, both residual
  RMS values, and rod_dia as used.
- Set zeros with G10 L20 P1 A0 C0. Do NOT auto-write scale factors into the INI - print
  the suggested SCALE values and let the operator apply them, since that is a config edit
  requiring a restart.

TESTING (before touching the machine)
- Port null_search and both fits to standalone Python with synthetic models
  error = k*sin(theta - theta_true) + noise, and the full sec-term contact model.
- Feed the fit a deliberately wrong r and confirm it shows up as a scale bias, so you know
  the signature when it happens on the machine.
- Feed a deliberately wrong axis scale and confirm the fit recovers it.
- Run in a sim config driving motion.probe-input from a HAL script. Confirm every abort
  path fires: probe never trips, scale error over threshold, bad residual RMS,
  tolerance calc fail, max_iter exceeded.
```
