# LinuxCNC motion — acceleration / jerk / velocity (read-first quick-ref)

## Acceleration smoothing
- Trajectory planner is **trapezoidal only** — constant acceleration, applied as an instantaneous step at every start / stop / direction-change (that step *is* the felt "jerk").
- **No jerk-limiting / S-curve on this machine.** Installed `motmod.so` is a stock build: `strings /usr/lib/linuxcnc/modules/motmod.so | grep -i jerk` → empty (verified 2026-07-26).
- The vendored manual DOES document an S-curve planner — `[TRAJ]PLANNER_TYPE=1`, `[TRAJ]MAX_LINEAR_JERK`, `[JOINT_n]MAX_JERK`, `[AXIS_L]MAX_JERK` (`docs/linuxcnc/manual/config/ini-config.html` §2.10 [TRAJ] lines 1687/1691, `.../integrator-concepts.html` §5 lines 465-477). **This does NOT apply here** — the vendored manual is patched and diverges from upstream 2.9; the installed binary lacks it. Those keys are silently ignored if set (no effect, no error).
- **Only lever to soften acceleration = `[AXIS_*]`/`[JOINT_*]` `MAX_ACCELERATION`** (lower = gentler). Getting real jerk-limited motion would need a patched/newer LinuxCNC build or drive-side ramp smoothing.

## Velocity vs. jolt
- Jolt magnitude is set by `MAX_ACCELERATION`, not speed. `MAX_VELOCITY` only changes how long the accel/decel lasts, not how hard it hits.

## Velocity ceiling
- Effective top speed = `[JOINT]MAX_OUTPUT` (clamp on PID velocity output, mm/s), **not** `MAX_VELOCITY`. Any commanded speed above `MAX_OUTPUT` → following error.
- `MAX_OUTPUT` is a hand-set commissioning throttle (raised 5→10→25→50→100 mm/s), well below the drives' capability (`OUTPUT_SCALE` 356.5 mm/s @10 V; Fagor `MAX_VELOCITY` 338.7). Raise further only with PID/velocity-loop tuning.
- `pid.output` is in **mm/s** (feeds `pwmgen.value`, `pwmgen.scale = OUTPUT_SCALE` maps mm/s→10 V). The ned.hal comment "PID output is in VOLTS" is wrong — fix it.

## PID loop (servo axes) — Fagor heritage & hold-zero
- Fagor 8055 position loop was **pure proportional**: Kv = 16.7 s⁻¹ → `[JOINT]P = 16.7`; FFGAIN = 0, DERGAIN = 0 (`docs/commissioning/calibration_plan.md:62,69-70`, "Fagor ran FF=0, pure P"). Fagor axis loop params are only PROGAIN(P23)/DERGAIN(P24)/FFGAIN(P25) — **no integral term** (`docs/fagor/text/fagor_8055_operating_manual_en.txt` ~line 12519).
- Our loop adds `FF1 = 1` (velocity feed-forward) on top — better tracking than Fagor had.
- **Hold-zero — same drives as Fagor, so pure-P *can* hold it.** The ~0.05 mm standing error is a residual zero-offset, NOT a missing integral. The analog drives are physically the same ones Fagor drove, so their null trim ("0 V = no motion") is unchanged. What changed is the controller: Fagor's ±10 V came from a trimmed DAC (true 0.000 V on a zero command); the 7I97 makes ±10 V from a PWM→analog stage (`ned.hal:36`), which may sit a few mV off 0 at `pid.output = 0` → creep → P loop chases it.
- **Parity fix = null the zero, not add integral.** Either trim the drive's balance pot (same knob as the Fagor null) or add a small fixed HAL bias on the analog output to cancel the 7I97 offset. Integral (`I` + a `maxerrorI` windup bound, not currently setp in ned.hal) only *hides* the offset — a crutch, not needed if the zero is truly zero.
- **Diagnose (DMM):** with the axis commanded 0 / amp disabled, meter the 7I97 analog output. Nonzero V → controller offset (cancel/trim). True 0 V but still creeping → drive null drifted, re-trim its balance pot. See task #4.
