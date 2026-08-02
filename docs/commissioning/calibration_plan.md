# ned calibration plan — every LinuxCNC setting, its source, and its target value

Purpose: the master list to work through as the machine is calibrated. Each value is
tagged with its source. Nothing here is entered in `ned.ini`/`ned.hal` yet unless noted —
incorporate section by section during calibration and mark ✅ as approved.

Sources:
- **FAGOR** = the 2026-06-23 WinDNC backup (`fagor8055/backup/`), decoded against the
  installation manual ch06. **⚠ THE BACKUP IS IN INCHES** (MPG P008 INCHES=1) — every
  value below is already converted to mm. Ground truth for the X/Y/Z/W iron (same
  motors/drives/screws/encoders as under Fagor).
- **YASKAWA** = SGDXS quick-ref (`docs/servo/yaskawa_params_quickref.md`), as set 2026-07-23.
- **MOLLOM/GDL65** = `docs/vfd/mollom_parameterization.md` + GDL65 nameplate.
- **BENCH** = measured on this retrofit.

---

## 1. Linear axes X / Y / Z / W — joints 0/1/2/3 (Fagor-derived)

Fagor per-axis files: X=MX1, Y=MX2, Z=MX3, **W=MX4** (NOT MX6 — MX4 carries GANTRY=1
"slave of X"; MX5/6/7 are untouched factory defaults). All axes: 1000-line encoders,
×4 quadrature, differential, analog ±10 V velocity command, 4 ms Fagor loop.

### 1.1 Scales (INPUT_SCALE, counts/mm) — replaces placeholder 1000.0

| Joint | Screw pitch | counts/rev | **INPUT_SCALE** | resolution |
|---|---|---|---|---|
| 0 X | 20.000 mm | 4000 | **200.000** | 5 µm |
| 1 Y | 16.000 mm | 4000 | **250.000** | 4 µm |
| 2 Z | 5.08 mm (5 TPI) | 4000 | **787.402** | 1.27 µm |
| 3 W | 20.000 mm | 4000 | **200.000** | 5 µm |

Signs: Fagor inverted the Z **count** (AXISCHG=YES on Z only) and the X/Y/W **analog**
(LOOPCHG=YES on X/Y/W, NO on Z). Don't copy signs blind — set them empirically at
calibration against `docs/commissioning/axis_directions.md` (count up on + move; +volts
moves +).

### 1.2 Travel limits (mm) — current ini values are WRONG

| Joint | Fagor LIMIT− | Fagor LIMIT+ | ini today |
|---|---|---|---|
| 0/3 X (gantry) | −6.35 (W: −12.7) | **+4038.6** | 1500 ⚠ (2.5 m short!) |
| 1 Y | −9.525 | **+1778.0** | 800 ⚠ |
| 2 Z | **−615.95** | +1.27 | −400 ⚠ |

→ MIN/MAX_LIMIT per joint AND per [AXIS_*], AND [TRAJ]/[DISPLAY] extents. Verify the
physical travel before trusting (limits assume Fagor's home position convention).

### 1.3 Velocity / acceleration — current ini is ~7× slow

| Joint | G00FEED | **MAX_VELOCITY** | ACCTIME | **MAX_ACCELERATION** |
|---|---|---|---|---|
| 0/1/3 X,Y,W | 20 320 mm/min | **338.7 mm/s** | 250 ms | **1354.7 mm/s²** |
| 2 Z | 10 160 mm/min | **169.3 mm/s** | 250 ms | **677.3 mm/s²** |

Also [TRAJ]MAX_LINEAR_VELOCITY (=338.7) and [DISPLAY]. Approach these gradually —
start ~25 % and ramp up during calibration.

### 1.4 Analog scaling + PID seed

Fagor drive calibration: **9.5 V = G00FEED** on every axis; pure P loop, no FF, and all
four axes tuned to the same Kv = 16.7 s⁻¹ (468 mV/mm on X/Y/W, 935 mV/mm on Z — the
gains differ exactly as the full-scale velocities do).

| ini field | X/Y/W | Z | note |
|---|---|---|---|
| OUTPUT_SCALE (mm/s at 10 V) | **356.5** | **178.2** | sign from direction test |
| MAX_OUTPUT | 10.0 | 10.0 | keep |
| **P** | **16.7** | **16.7** | = Fagor Kv; with FF1 below this is a better loop than Fagor had |
| FF1 | 1.0 | 1.0 | velocity feed-forward (Fagor ran FF=0, pure P) |
| I, D, FF0, FF2 | 0 | 0 | start; add I only if static error shows |
| FERROR (moving) | **25.4** | **12.7** | Fagor MAXFLWE1 |
| MIN_FERROR (stopped) | **12.7** | **2.54** | Fagor MAXFLWE2 |
| DEADBAND | ~1 count: 0.005 | 0.00127 | from INPUT_SCALE |
| BACKLASH | W: 0.0254 | Z: 0.0254 | Fagor BACKLASH; X/Y = 0 |

### 1.5 Homing (Fagor ground truth vs current plan — CONFLICTS to resolve)

Fagor: every axis HAS a home/decel switch (DECINPUT=YES) + homes to the **encoder
index** (REFPULSE rising). Directions: **X +, Y +, Z −, W +**. REFVALUE = 0 all; only Z
has REFSHIFT = **−6.35 mm**. Speeds (search / latch, mm/s): X 12.7/1.27 · Y 38.1/2.12 ·
Z 12.7/1.69 · W 12.7/1.27.

Conflicts with the current ned plan ("home off limit switches", all-negative search,
no index):
1. Fagor searched X/Y/W **positive** — ned.ini has −10. Reconcile with which physical
   switch is where.
2. Fagor used the **index pulse** (HOME_USE_INDEX YES; 7I97 encoders have index) —
   far more repeatable than switch-only. Adopt.
3. Fagor Z homes NEGATIVE (down)?? — ned decided Z homes UP for safety. Keep ned's
   choice, but then Z's REFSHIFT/limits reference changes sign — re-derive at machine.
4. Gantry: Fagor ran W as a true slave (GANTRY=1, MAXCOUPE 12.7 mm max skew). ned
   plan = second aft switch (`sig-limit-w-aft`, input TBD) + split HOME_SEQUENCE for
   self-squaring. Until wired, shared switch + rigid frame.
5. Fagor G74 ran subroutine 9000 (order: not yet examined) — ned order stays
   Z(0) → Y(2) → X-pair(−1) → B-pair(−3) → A(4) → C(5).

### 1.6 Compensation tables (port later, after scales/limits verified)

- **Leadscrew comp ON for all 4 axes** under Fagor: ML1 (X, 32 pts), ML2 (Y, 14),
  ML3 (Z, 6), ML4 (W, 32) → convert to LinuxCNC `COMP_FILE` per joint. ⚠ tables are in
  INCHES.
- **Cross comp MC1**: Y position → Z error, 7 pts (Y-droop). No stock LinuxCNC feature —
  candidates: external-offsets HAL or ignore initially. Decide at calibration.

---

## 2. B rotary pair — joints 4/7 (steppers, BENCH-derived)

| Setting | Value | Source/status |
|---|---|---|
| SCALE | 22.222 / −22.222 (400 p/rev × 20:1 ÷ 360) | matches DIP; verify with a measured 360° table move |
| Per-joint trim | **not needed** | the earlier "two sides turn differently" was a **misplaced shield ground** (noise → miscounts), fixed 2026-07-23 — not gearing |
| MAX_VELOCITY / ACCEL | 30 °/s / 300 °/s² placeholder | bench proved ≥825 motor RPM ≈ 250 °/s table; set by usable torque, not stepgen |
| Limits | ±3 600 000 (continuous) | keep |
| Homing | immediate (no switch), sequence −3 pair | keep; define a physical 0 mark |

---

## 3. Head A (tilt) / C (spin) — joints 5/6 (YASKAWA-derived)

| Setting | Value | Source/status |
|---|---|---|
| **SCALE** | **PER-AXIS, A ≠ C** — see `tools/live/ned_params.sh` (single source; `sync` regenerates the INI). Drive gear Pn20E=8192/Pn210=1 ✅ set | reduction differs per axis (HQD AC-D90-65); do NOT restate the number here |
| Sign | motor runs NEGATIVE for +cmd on both | pick ONE fix: drive **Pn000.0** (direction) or negative SCALE — decide at calibration, then lock |
| MAX_VELOCITY | ≤ 200 kHz stepgen ÷ SCALE; binding axis is C (larger SCALE) ≈ 43 °/s; keep 30 | STEPGEN_MAXVEL 36 still fits |
| Limits | A: **±115**, C: **±315** (within maker hard stops; A crashed once) | drive has NO soft limits (quick-ref) — LinuxCNC only |
| **/S-ON** | Pn50A=**8101**, Pn515=**8882** on BOTH | LinuxCNC enables via /S-ON (A=output-07, C=output-06) **plus SEN high** (output-04→CN1-42) — 8882 refuses /S-ON without SEN (BB) |
| Keep | Pn50B=6548, Pn002 absolute, Pn000=0010 | quick-ref ✅ |
| Homing | absolute PSO now readable on demand (SEN + 7I85 PktUART) — zeros captured in `configs/params/head_zero.inc`; LinuxCNC homes A/C to those | sequences 4/5 after linears |
| steplen/space 2500 ns | verify against SGDXS max input pulse rate (manual) | UNVERIFIED tag in ned.hal §8 |
| FERROR | open-loop — keep loose (5°) | |

---

## 4. Spindle (MOLLOM/GDL65-derived)

| Setting | Value | Source/status |
|---|---|---|
| **[SPINDLE_0]MAX_FORWARD/REVERSE_VELOCITY** | **18000** ✅ set 2026-07-25 | Mollom is configured F0-10/F0-12 = **600 Hz** (field-weakened top) → 10 V = 600 Hz = **18000 rpm**. So scale must be 18000 (NOT the 13500 base-speed, NOT the old 24000). Set in `ned.ini` + `tools/groundtruth/move.hal` pwmgen.04.scale. `move.sh spindle N` now = N rpm. (Cap at 13500 instead = lower F0-12 to 450 Hz + scale 13500.) |
| MIN_FORWARD_VELOCITY | TBD — VFD min useful freq + bearing/cooling floor | currently 1000 |
| Analog mapping | pwmgen.04 0–10 V unipolar → AI2; verify VFD curve = 0–10 V → 0–450 Hz (F4-18..21 default is ±10 V bipolar — confirm the 0..10 half maps 0..100 %) | bench check with DMM at 6750 cmd = 5.00 V |
| Direction | R6→S1 FWD / R7→S2 REV (relay, not analog sign) | ✅ proven both ways 2026-07-23 |
| Accel/decel | VFD owns the ramp: F0-17/18 = 60 s bench values → tighten for production (pick at calibration; LinuxCNC commands step, VFD ramps — same as Fagor: ACCTIME=0, OPLACETI=0, drive ramped) | |
| Spindle-at-speed | no encoder feedback (GDL65 has none; Fagor's 1000 p/r spindle encoder was the OLD motor) → derive at-speed from `vfd-running` (in-11) + timer ≥ ramp, or leave manual | ⚠ NO rigid tapping / M19 orient possible without spindle feedback |
| Power cap | F8-36 = 33 % (single-phase ≈ 3 kW) — spindle won't reach rated power; at-speed under load caveat | mollom doc |
| Override | Fagor allowed 50–150 %; ini has 20–120 % | align if desired |
| Interlock | `spindle.permit` = drawbar-up (in HAL ✅); add air-pressure-ok to the permit chain at calibration | |

---

## 5. I/O semantics to finalize (HAL, during calibration)

1. **IN14 = `*39` e-stop-chain tap** (not a thermostat input any more): rewrite
   `ned.hal:462` comment + optional GUI logic: `*39`=24 V & estop LOW → "SPINDLE
   OVER-TEMP", `*39`=0 V → "E-STOP". (Tracing-doc notes still owed — todo.)
2. **vfd-fault (in-13)**: decide — message-only or wire into estop latch.
3. **spindle-running (in-11)**: at-speed logic (see §4).
4. **Limit switches (in-05..10)**: walk each, confirm `-not` polarity = TRUE healthy.
5. **`sig-limit-w-aft`**: install + assign input, then split gantry homing (ned.hal §5
   comment has the 3-step recipe).
6. **air-pressure-ok**: interlock M6/drawbar (unclamp needs 10.5–11.5 bar) and
   optionally spindle-run (Port A seal air 4–4.5 bar).
7. ATC interlocks (later): S3 shaft-stop before unclamp; S1 tool-lock before spin.

---

## 6. Suggested calibration order

1. **Scales**: X/Y/Z/W INPUT_SCALE sign+value (dial/DMM moves); B 360° check; head 10°
   check (already ✅ rough).
2. **Directions**: axis_directions.md pass on every axis; lock all signs (incl. head
   Pn000.0 decision).
3. **Limits**: verify real travels vs §1.2, set soft limits; A-tilt physical stops.
4. **OUTPUT_SCALE + PID** (servo axes): 9.5 V ↔ G00FEED check per axis, then P=16.7 +
   FF1=1 seed, tune; FERROR from §1.4.
5. **Homing**: switches + index, per §1.5 decisions; gantry squaring once w-aft exists.
6. **Velocity/accel ramp-up** toward §1.3 targets.
7. **Spindle**: 13500 mapping, min speed, ramps, at-speed.
8. **Compensation**: ML1-4 → COMP_FILEs; decide on MC1 cross-comp.
9. Revert head /S-ON to n.8101; interlocks (§5).
