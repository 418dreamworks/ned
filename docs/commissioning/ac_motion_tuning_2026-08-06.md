# A/C motion tuning — stop-transient experiments (2026-08-06)

Operator + Claude session. Question: the tool tip visibly jerked/bobbed at
the end of A rotations under tool-tip kins. What governs the error, and
what accel/feed should A and C run?

## Method
- PID TRACKING button (TCP CALIBRATION tab): cycles A between waypoints at
  a chosen feed via `subroutines/tcp_pidt_step.ngc` (slow-feed copy of the
  auto-converge sub; takes target + feed args; 2 s settle at every stop),
  no probing, no puck, geometry fixed. G43 preamble mandatory — without
  the tool length in `arm.in1` the kins holds a point one tool-length up
  the shank and the TIP sweeps an arc (seen live, fixed same day).
- PID errors sampled ~17–60 Hz by `halcmd -f` pollers (pid.x/y/z.error +
  joint.4.pos-fb); leg timestamps in `logs/pid_track_*.ndjson`.
- Error metric: peak |commanded − actual| on the LOADED joint in the ~1 s
  around each stop (Y is loaded at A=0 stops, Z at A=±90; cos/sin split
  proven by the −90/0/+90 stop table — direction of approach irrelevant,
  no backlash signature).

## Data (all in logs/, captures in logs/pid_captures_20260806/)
- 3-tier baseline (accel 300): `pid_track_20260806-153734.ndjson` +
  `fastyz_exp.log`. F150/450/1350 → loaded-axis stop peaks 50–64 /
  121–152 / 214–243 µm. X (unloaded at C=0) flat ~20–30 µm = control.
- accel 30 partial (E-stopped by Mesa read error): `...-162207.ndjson` +
  `fastyz_med.log` → 29–39 µm at F450.
- accel 3: `...-163536.ndjson` + `fastyz_1pct.log` → 14–24 µm (noise floor).
- Accel sweep 0.5→20 at F450: `...-1655xx..1705xx.ndjson` +
  `fastyz_sweep.log`, manifest `accel_sweep_manifest.ndjson` → 7→33 µm.
- accel × F grid (0.1/0.25/0.5/1 × F150/300/450/600, pattern 0→−90→0):
  manifest `grid_manifest.ndjson` + `fastyz_grid.log` → ALL cells 6–19 µm;
  time accel-dominated (170 s at 0.1 regardless of F; 54 s at 1.0/F450+).
- Chosen-setting demo runs (accel 2, F350/F450): `...-1840xx.ndjson` +
  `fastyz_a2.log` → max |err| 23–24 µm all axes.
- Plots: https://claude.ai/code/artifact/96c2f5c1-319b-4691-a66a-2bdfd7d46874
  (the accel 0.1/F150 "bobbing" cell, both legs).

## Conclusions
1. Stop-transient error is LINEAR in A acceleration: ≈1.3 µm per °/s² on a
   6–25 µm floor, verified from 0.5 to 300 °/s² (two orders of magnitude).
   Cruise feed is nearly irrelevant to error (150–600 all the same).
2. Time is accel-dominated below ~1 °/s²; feed above 450 buys nothing
   there. Frontier: accel 2–5 at F450.
3. The 6–25 µm floor is a ~0.4 Hz COMMON-MODE oscillation on X, Y and Z —
   including X, which has zero kins demand at C=0 — i.e. the structure
   sways and the motor encoders (and the operator's eye) see it. No servo
   parameter removes it.
4. Following-error at stops is symmetric in approach direction → no
   backlash signature in A/C transients. (Z axis BACKLASH comp 0.0254 —
   inherited Fagor value — was zeroed the same day: gravity preloads Z;
   the comp injected 25 µm steps at every reversal.)

## Banked decisions (operator 2026-08-06)
- `[axis.a]/[joint.a]/[axis.c]/[joint.c] MAX_ACCELERATION = 2` in
  configs/params/MASTER.params (was 300), .incs regenerated.
- Canonical A/C rotation feed = F450 (tcp_auto_step.ngc already rotates at
  450; PID TRACKING default PIDT_SPEEDS = (450,)).
- `[joint.z] BACKLASH = 0.0` (joint.x2 keeps 0.0254).

## Open issue — Mesa link drops (SEPARATE from all of the above)
Three `hm2/hm2_7i97.0: error finishing read!` events (16:23, 16:46,
18:44), each → joint ferror → machine drop; the 16:2x one also segfaulted
rtapi_app (core at 16:27). One drop physically jumped A by 13° before the
chain opened. High-rate halcmd polling (50–60 Hz process spawning) was
running near two of the three — suspected but NOT proven (a 45-min 60 Hz
capture earlier ran clean). Captures now run ≤20 Hz. Needs a real
investigation: dmesg, ethtool -S, servo thread tmax, cable/switch.
