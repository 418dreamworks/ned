# PID calibration session — 2026-08-01 (goal: errors < 2 encoder counts)

Operator goal (2 h window): "errors that are always less than 2 encoder
counts for all movements and still positions." Constraints: moves only in
machine 0..−20 mm, F200 max, tuning steps ≤ 0.5% of value, never a sign
flip. Raw per-iteration logs: `ned/logs/pid_cal_2026-08-01/`.

Counts: X/Y/W = 5 µm/count (scale 200), Z = 1.27 µm/count (scale 787.402).

## What was established, in order

### 1. Static null (BIAS) — the drives lie by ~25–30 mV
At rest every axis needed a standing output (X +0.85, Y +0.98, Z +0.43,
W +0.72 units) — un-nulled analog drive offsets carried by the integrator.
Measured exactly by disabling Igain per axis (P holds the axis; the null
appears as static ferror; bias_error = P×ferror — `bias_tune2.log`; the
first attempt used pid.errorI, which does not exist without debug=1:
`bias_tune.log` is the record of that dead end).
**Final BIAS: x 0.860, y 1.0095, z 0.437, w 0.722** (persisted).

### 2. Velocity feedforward (FF1) — was never wrong
Single-stroke estimates walked randomly (±1 count of cruise error reads as
dFF1need ≈ 0.025 — far above the 0.002 convergence bar: `pid_dyn.log`).
With 3-pair averaging and count-aware thresholds the estimator converged
immediately (`pid_ff1b.log`):
**Final FF1: x 1.000, y 1.005, w 0.993, z 0.990** (persisted).
Y shows a persistent direction-asymmetric cruise error (~2 counts more lag
one way): asymmetric drive gain — FF1 is symmetric and cannot remove it.

### 3. Stop overshoot — integrator windup, the big win
Baseline stop-settle p95: X 3.0 / W 2.8 / Y 4.8 / Z 11.9 counts.
0.5%-step Igain descent (`pid_stop.log`):
**x I=4.925 (stop 2.0), w I=4.828 (1.8), y I=4.975 (1.6), z I=4.876 (4.9)**
(persisted). Z's remaining ~5 counts (6 µm) did not respond further — no
damping exists in the chain (D=0; the 0.5%-of-value rule cannot move a
zero, so introducing D needs an explicit operator decision).

### 4. Deadband — 0.005 is optimal, wider bought nothing
With bias nulled, an ascent to ≤2-count bands produced no p99 improvement
on any axis (`pid_rest2.log`); best stayed 0.005 everywhere (Z included —
its config value 0.005 ≈ 4 of its counts). Earlier experiments (0.006,
0.012, per-axis 0.02/0.01/0.005) also never beat it.

### 5. The floor — what software cannot remove
At rest, every axis shows the SAME physical dither: ~±15–20 µm p99
(verify #1: rest p99 3.0/4.0/4.2 X/Y/W-counts and 9.2 Z-counts — one
band, four scales). Drives-off the encoders are DEAD FLAT, so the motion
is real, loop+drive-generated, and survives perfect bias, perfect FF1 and
optimal deadband. The remaining sources are below the software loop:
analog drive dither/asymmetry (40-year-old velocity drives), stiction
limit-cycling with zero damping, and any ambient vibration. Getting
"always < 2 counts" needs hardware-side work: drive null pots/service,
possibly a D term (operator decision), and for Z the goal is 4× harsher
purely because its encoder is 4× finer — its PHYSICAL rest band matches
X/Y/W.

## Verify results (formal, p99/max in own counts: rest | cruise | stop)

Verify #1 (15:20, before FF1 round 2 / deadband round):
```
X(x): 3.00/5.00 | 2.13/2.47 | 3.00/4.00   FAIL
X(w): 4.00/6.00 | 2.00/2.00 | 4.20/4.20   FAIL
Y(y): 4.00/6.40 | 2.27/2.27 | 4.80/5.60   FAIL
Z(z): 9.19/12.81 | 6.83/7.02 | 10.81/12.81 FAIL
```

Verify #2 (15:37, final values — X cruise now passing after the FF1
revert; everything else at the hardware floor):
```
X(x): 3.00/4.00 | 1.47/1.80 | 3.00/4.00     (cruise PASS)
X(w): 4.00/5.00 | 2.00/2.00 | 4.20/4.20
Y(y): 4.00/5.60 | 2.53/2.80 | 4.80/5.60
Z(z): 9.19/11.19 | 6.39/6.42 | 10.86/11.86
```

### 6. P descent — the last lever, no gain
Bounded P reduction (−0.5%/step, floor −3%, auto-revert on stop
degradation, `pid_pdesc.log`): best rest p99 on EVERY axis was at the
entry P=16.7. P is not the dither's knob either.

### 7. Settled-rest control experiment (kills the last alternative)
Hypothesis: verify's rest failures were post-stroke settle transients.
Test: 120 s captures per axis after 10+ minutes of total quiet:
```
x: p95 2.00  p99 3.00  max 4.00 counts   FAIL
y: p95 2.40  p99 3.20  max 4.80          FAIL
z: p95 6.81  p99 8.19  max 11.19         FAIL
w: p95 2.00  p99 4.00  max 5.00          FAIL
```
Identical to post-stroke rest. The dither is the machine's steady state;
Phase 1's occasional 30 s max-1-count windows were short-sample luck.

### 8. Analog output chain verified against the vendor spec
Last hypothesis: PWM quantization ripple on the ±10 V outputs (75 kHz has
only ~1300 levels). REFUTED: the 7I97T manual (:560-564) prescribes
"75 KHz PWM with dither enabled + offset mode" for LinuxCNC ≥2.9.2, and
the iron matches exactly — pwm_frequency 75000 (iron:408), dither TRUE and
offset-mode TRUE on pwmgen.00-03 (iron:399-402, live-verified). The
command chain is per-manual; the dither is not ours.

## Session 2 (operator-renewed, +2 h)

### 9. D-term: ZERO effect — a decisive null result
Authorized this round. Geometric ramp 0.0002→0.0077 (38×) per axis
(`pid_dterm.log`): metric identical at every step, no damping, no
oscillation. Best = D 0 everywhere (restored). A derivative that changes
NOTHING means the dither is not a loop resonance at all.

### 10. Frozen-loop experiment — the mechanism, finally
X held on CONSTANT voltage (P=I=FF1=0, output=bias) for 45 s:
**random-walked 96 counts (0.48 mm), slow drift 33 counts.** The drives
emit velocity noise that integrates into a position random walk; the
closed loop has been REINING that walk to ±3 counts all along. The rest
"dither" is residual chase error, not a limit cycle — which explains
every null result (bias/P-down/deadband/D insensitivity) at once.

### 11. Consequence: P-ASCENT (chase harder) — the untried direction
Residual chase error shrinks with loop gain until phase margin runs out.
P had only ever been LOWERED. Ascent with oscillation guards
(`pid_pup.log`): X/W/Y flat to ~+13% (reverted to 16.7); Z banked
P 16.7→17.21 (metric 7.8→7.2 counts, persisted). Within rest-box-safe
gain moves, loop bandwidth barely dents the tach-noise floor; real
headroom needs a dynamic session at speed.

### 12. Operator/PCW confirmation of the path
PCW: "If the analog drives have tachometer feedback, there is no reason
to adjust the pots." Consistent with all evidence: the offset is
correctly absorbed in software (BIAS), the random walk is tach-ripple
noise the drive faithfully follows (pots irrelevant), and the position
loop reining it is the designed mechanism. Remaining PID-path levers:
dynamic gain-headroom session (>F200, operator-gated) and a faster servo
thread (bandwidth; needs Pi RT headroom check).

### Final verify #3 (17:13, end of session 2; p99/max: rest | cruise | stop)
```
X(x): 3.00/3.00 | 1.47/1.53 | 2.00/3.00    cruise PASS
X(w): 3.00/4.00 | 1.67/1.67 | 2.20/2.20    cruise PASS
Y(y): 3.20/4.80 | 3.07/3.07 | 3.20/3.20
Z(z): 7.19/10.19 | 6.33/6.42 | 8.86/11.86
```
Improvement over session start: stops −33/−30/−67/−50% (X/W/Y/Z), X/W
cruise inside 2 counts, rest tails −30..−50% on X/W. Y cruise carries the
drive's direction-asymmetric gain; Z remains scale-limited (its 2-count
goal = 2.5 µm, beneath the ~±5 µm tach-noise floor all axes share).

## VERDICT vs the goal ("always < 2 counts, moving and still")

NOT MET, and demonstrably NOT REACHABLE within the authorized parameter
space (≤0.5% steps, no sign flips, no new terms). Every software lever —
BIAS, FF1, Igain, DEADBAND, Pgain — was driven to a measured optimum or
proven insensitive, with the full numeric trail in the logs. Achieved:
cruise ≤2 counts on X (1.8 max) and W (2.0), stop p95 1.6–2.8 counts on
X/Y/W (from 3–5), Z stop halved (11.9→~6). The residual — a uniform
±15–20 µm p99 rest/stop dither on all axes — is generated below the
software loop (analog drive dither and asymmetry, zero damping, Z merely
resolves the same physical band 4× finer). The path to <2 counts is
hardware + operator-gated: drive null/balance service, a D term
(introduction from 0 is outside the 0.5% rule), and a faster-move tuning
session for P/FF2 once authorized.

## Persisted final values (configs/params/joint_*.inc)

| joint | BIAS | FF1 | I | DEADBAND |
|---|---|---|---|---|
| x1 (X) | 0.860 | 0.993 | 4.925 | 0.005 |
| x2 (W) | 0.722 | 0.986 | 4.828 | 0.005 |
| y | 1.0095 | 1.005 | 4.975 | 0.005 |
| z | 0.437 | 0.990 | 4.876 | 0.005 |

## Open items for the next session (operator decisions)
- D-term introduction (blocked from 0 by the 0.5% rule) — the standard
  cure for stop overshoot + dither damping.
- Drive-side: null/balance pots (kills the offset at the source), Y's
  direction asymmetry, Z drive's dither.
- Higher-speed dynamic pass (P ceiling, FF2) once >F200 is authorized.

## Evening extension (same day): balancer, servo period, accel

- **FF1 finals above are the empirical V-curve optima** measured at
  F8000–F10800 (ladder means, bracketing): X 3.2 / W 5.9 / Y 4.1 µm
  cruise. Single-pair FF1 trim estimates are below the noise floor and
  random-walk — only bracketed sweep means are trustworthy.
- **Air balancer**: bracketed by Z direction-split (5-pair averages).
  Whole pressure range spans 26–33 µm split, σ≈4 — second-order knob,
  set-and-forget. Pressure only moves the up-stroke error (+3→+7 µm);
  the −24 µm down-lag is drive electronics, not weight.
- **Servo period 0.75 ms trial**: RT-clean (0 delays, thread max 361 µs)
  but zero benefit; reverted to 1 ms. Verdict confounded then resolved:
  rest noise had risen machine-wide with 0.7–0.9 cross-axis correlation
  — a structural disturbance (person in shop / compressor), not tuning.
  Rest-noise comparisons are only valid in a quiet shop.
- **Accel sweep (operator hypothesis confirmed)**: stop-settle scales
  ~linearly with decel; no knee down to 200 mm/s². Worst-direction
  p95/max µm at F10800 (Z F9000): 800 → X 21/48 Y 49/111 Z 51/106;
  200 → X 13/18 Y 18/32 Z 26/41. **Operator chose 200 mm/s²**;
  persisted in all XYZ/W axis+joint .inc files (was X/Y 800, Z 400).
  Final position is accel-independent (park error flat across levels)
  — the win is corners and the first ~0.5 s after a stop.
- Raw logs: accel_sweep.log, z_split runs in the session job dir;
  measurement scripts confirm MDI mode before issuing (kills the
  "Must be in MDI mode" toast storm from racing the brain's MANUAL
  restore).
