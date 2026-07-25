# Mollom G75 — Parameterization (ned spindle)

Living record of every Mollom parameter we set, **verified against the actual
manual** (`docs/vfd/text/mollom_G75_AC_drive_manual.txt`, parameter table F0→U0,
manual lines ~1358–3345). Every value below cites the manual. Audit it against
the PDF/text before keying anything in.

## Context (read before trusting any value)
- **Drive:** Mollom **G75-2T-7R5-G-B** = 7.5 kW, **220 V class ("2T")**, Type G
  (constant-torque) — `mollom_facts.md`.
- **Input feed:** **240 V split-phase = SINGLE-PHASE to the drive** (split-phase is one
  center-tapped phase, not 3-phase), on **8 AWG → 40 A breaker** (~9.6 kVA available).
  Single-phase derates the drive to ~half rated — **ceiling ≈ 3.5–4 kW / ~16 A output**,
  regardless of the fat feed (the drive, not the wire, is the bottleneck). We cap below that
  at **~3 kW / ~10 A** via `F8-36`. Full power would need 3-phase. **`F9-12 = 10` mandatory.**
- **Motor:** GDL65 head spindle [cmp:head-spindle] — **9 kW / 220 V / 30 A / 450 Hz, 4-pole
  async** (cos φ 0.86, η 0.82). **Voltage matches the drive** → full flux to base 450 Hz,
  field-weaken 450→600 Hz. GDL65 is the **only** motor: **Motor 1 = `F1` group, `F0-24 = 0`**;
  the `A2` (Motor 2) group is unused.

## ⚠️ Our manual is ABRIDGED
`mollom_G75_AC_drive_manual.txt` is the **quick-setup manual** (states so at line 53).
It lists F0-00→F0-27 then jumps straight to F1 — the real drive has **more parameters
it does not document** (e.g. F0-28+). **Policy: any parameter not found in this manual
is left at factory default** (we can't verify a value we can't read). If we ever need
one of those, get the full manual first.

## ⚠️ Correction to earlier docs
`mollom_facts.md` / `mollom_g75_vfd.md` referenced **`B1-01` / `B1-02`** for
speed/run source. **There is no B group in this manual** (groups are F0–FP,
A0–A6, U0). The real parameters are **run source = `F0-02`, speed source = `F0-03`**
(see table). Those B-codes were wrong; do not use them.

---

## Parameter table (verified)

Legend: ✅ value decided · ⬜ needs machine data · ⚠️ conditional/caution.
"Mfr default" = the manual's default.

### Run / command / reference source (Group F0)
| Param | Name | Manual range / default | Set to | Why | |
|---|---|---|---|---|---|
| F0-00 | Type G/P | 1=G(const-torque), 2=P(fan/pump); def **1** | **1** | spindle = constant torque | ✅ |
| F0-01 | Motor 1 control mode | 0=SVC,1=FVC,2=V/F; def **2** | **2 (V/F)** | no encoder → V/F | ✅ |
| F0-02 | Command source | 0=panel,1=Terminal,2=comm; def 0 | **0 (panel) for BENCH; 1 (Terminal) for production** | bench: keypad RUN/STOP. Production: CNC run via S1/S2 (R6/R7). | ✅ |
| F0-03 | Main freq source | 0/1=digital,2=AI1,**3=AI2**,4=AI3 pot,5=pulse…; def 4 | **3 (AI2)** | speed = ±10 V on AI2 (from pwmgen.04) | ✅ |
| F0-10 | Max frequency | 500–3000 Hz (with F0-22=1); def 50 Hz | **600.00 Hz** | = motor max; anchors the V/F top | ✅ |
| F0-12 | Freq upper limit | lower-lim..max; def 50 Hz | **600.00 Hz** | real speed cap = 18000 rpm; lower this to cap speed | ✅ |
| F0-15 | Carrier frequency | 0.5–16.0 kHz | **16.0 kHz** | | ✅ 2026-07-25 |
| F0-17 | Accel time 1 | 0.0–6500.0 s (F0-19=1) | **10.0 s** (was 60) | 10 s 0→18000 rpm. Ref = Max Freq (F0-25=0 default → 0→600 Hz) | ✅ 2026-07-25 |
| F0-18 | Decel time 1 | 0.0–6500.0 s | **10.0 s** (was 60) | 10 s 18000→0 | ✅ 2026-07-25 |
| F0-25 | Acc/Dec time base freq | 0=MaxFreq(F0-10), 1=set, 2=100Hz; def **0** | **0 (default)** | so accel time = 0→600 Hz full sweep | ✅ |
| F0-19 | Acc/Dec time unit | 0=1s,1=0.1s,2=0.01s; def **1** | **1** | keep default (0.1 s) | ✅ |
| F0-22 | Max-freq range | 2=≤500 Hz (def), 1=500–3000 Hz | **1** | **REQUIRED** to exceed 500 Hz (manual 1420–1472) | ✅ |
| F0-24 | Motor select | 0=M1(F1), 1=M2(A2); def 0 | **0** | GDL65 = Motor 1 | ✅ |

> F0-22 / F0-10 are stop-to-change (□) globals → changing them = stop, reconfigure, not live.

### Motor-1 nameplate (Group F1, GDL65) — verified vs manual lines 1513–1554
Protections (F8-36, F9-00/01) are all **% of F1-03**, so these must be right.
| Param | Name | Set to | |
|---|---|---|---|
| F1-00 | Motor type | **0** (std async) | ✅ |
| F1-01 | Rated power | **9.0 kW** | ✅ nameplate |
| F1-02 | Rated voltage | **220 V** | ✅ nameplate |
| F1-03 | Rated current | **30.0 A** | ✅ nameplate |
| F1-04 | Rated frequency | **450.0 Hz** (V/F base) | ✅ nameplate |
| F1-05 | Rated speed | **13500 RPM** | ✅ nameplate (4-pole: 450 Hz → 13500 sync) |
| F1-06..10 | stator/rotor R, L, no-load I | **static auto-tune** | ⚠️ matched motor — static tune OK, do NOT rotate-tune in the head |
| F1-37 | Auto-tuning | **0 (none) for now** | ⚠️ static only; never rotate-tune in the head |

> cos φ 0.86 / η 0.82 = informational (no F1/A2 param for them). Async derives poles
> from freq/speed. (Same nameplate was verified in the A2/Motor-2 group at manual
> 2902–2917 when the GDL65 was briefly planned as Motor 2; it now lives in F1 as Motor 1.)

### V/F curve (Group F3)
| Param | Name | Range / default | Set to | |
|---|---|---|---|---|
| F3-00 | V/F curve | 0=linear,2=square…; def 0 | **0 (linear)** — constant-torque spindle | ✅ |
| F3-01 | Torque boost | 0.1–30%, 0.0=auto; def model | **0.0 (auto)** | ✅ |

### Start / stop (Group F6)
| Param | Name | Range / default | Set to | |
|---|---|---|---|---|
| F6-00 | Start mode | 0=direct,1=speed-track,2=pre-exc; def 0 | **0 (direct)** | ✅ |
| F6-07 | Acc/Dec mode | 0=linear,1=static S,2=dyn S; def 0 | **0** (or 1=S-curve for softer) | ✅ |
| F6-10 | Stop mode | 0=decel,1=coast; def 0 | **0 (decel)** w/ long F0-18 | ✅ |

### Current guards / protection (Groups F8, F9, A5)
All % values reference **F1-03 = 30 A**.
| Param | Name | Manual range / default | Set to | Why | |
|---|---|---|---|---|---|
| F8-36 | Output overcurrent threshold | **0.1–300.0 % of F1-03**, 0=off; def 200 % | **33 %** (≈10 A ≈ 3 kW) | caps output to the single-phase-derated ~3 kW capability: 9 kW↔30 A → 3 kW↔~10 A, 10/30 = 33 %. Manual line 2329. | ✅ |
| F8-37 | …detection delay | 0.00–600.00 s; def 0.00 | **0.1 s** | small filter vs inrush nuisance | ✅ |
| F9-00 | Motor overload protect | 0/1; def 1 | **1 (enable)** | thermal, refs F1-03 | ✅ |
| F9-01 | …gain | 0.20–10.00; def 1.00 | **1.00** | | ✅ |
| F9-05 | Overcurrent protect | 0/1; def 1 | **1 (enable)** | | ✅ |
| F9-06 | …level | **50–200 % of DRIVE rated**; def 150 % | **150 % (default)** | secondary guard only | ✅ |
| F9-13 | Output phase loss | 0/1; def 1 | **1**, ⚠️ may nuisance-trip at very low current — disable (0) if it does | conditional | ⚠️ |
| F9-12 | Input phase loss / power loss | units=in-phase-loss, tens=power-loss; def **11** | **10** (REQUIRED) | single-phase input → input-phase-loss MUST be off or it trips | ✅ |
| A5-04 | Fast overcurrent-limiting | 0/1; def 1 | **1 (enable)** | hardware backstop (not adjustable to a low value) | ✅ |

### Input terminals (Group F4) — match the cabinet relay wiring
| Param | Name | Value(meaning) | Set to | |
|---|---|---|---|---|
| F4-00 | S1 function | 1=FWD | **1** (R6, spin-cw) | ✅ |
| F4-01 | S2 function | 2=REV | **2** (R7, spin-ccw) | ✅ |
| F4-02 | S3 function | 11=ext-fault opened-relay, 33=closed-relay | **11** (CORRECTED from 33) | empirically `33` faults on an OPEN S3; R2 NC holds S3 open when healthy → need fault-on-CLOSED = **11**. Matches VG5 behavior on unchanged wiring. | ✅ |
| F4-03 | S4 function | **9**=Fault reset | **9** (R2 NO) | ✅ |
| F4-11 | Terminal I/O mode | 0=two-wire 1 (def) | **0** | ✅ |
| F4-33 | AI curve select | def 0x321 → AI2 uses Curve 2 | **default** | ✅ |
| F4-18..21 | AI Curve 2 (AI2) | def −10 V=−100 %, +10 V=+100 % | **default (bipolar ±10 V)** | ✅ |

> **TODO — direct spindle over-temp interlock (deferred 2026-07-08).** Make the VFD stop on GDL65
> over-temp **without the CNC in the loop.** *Now:* the NC thermal switch only feeds the 7I97
> `spindle-overtemp` input → CNC reacts (`components.md:182`, `ned.hal:462`).
> *Wanted:* wire the GDL65 **NC thermal switch** (opens ≥100 °C = fault) to a **spare DI — S5
> (`F4-04`)** and set **`F4-04 = 33`** (external fault, **fault-on-OPEN**). Polarity per the
> **empirically-verified** note on F4-02: **33 faults on OPEN, 11 on CLOSED** — NC over-temp opens
> on fault → needs **33** (opposite of S3/R2 which is 11 because R2 is fault-on-closed).
> Result: over-temp opens → **ERR15 External Fault** → drive stops, latched, no CNC.
> **Verify on bench:** open contact → ERR15; closed → runs. (S1–S4 taken: FWD/REV/ext-fault-R2/
> fault-reset; S5 free since speed = AI2, not pulse.)

### Output terminals (Group F5) — feed back to the 7I97 inputs
| Param | Name | Value(meaning) | Set to | drives | |
|---|---|---|---|---|---|
| F5-02 | Control-board relay (RY1, TA/TB/TC) | 2=Fault output (coast-to-stop fault) | **2** | `vfd-fault` → input-13 | ✅ |
| F5-03 | Y1 function | 1=AC drive operating (running) | **1** | `spindle-running` → input-11 | ✅ |

### Panel display — show RPM instead of Hz (Group F7)
**This unit's keypad = LED "Type 2" (manual Fig 4-2): two-line LED, NO Hz/A/V unit-indicator
LEDs (only status LEDs like RUN).** So the manual's "Hz、A lit = RPM" convention does NOT apply
here — identify fields by the F7-03 SHIFT-cycle order, not by indicator LEDs. (per user 2026-07-25)
**RPM = the "Running speed" item = F7-03 BIT13**, shown when the **Hz + A indicators BOTH light**
(manual line 1241 "Hz、A = RPM for motor speed"; line 2149 BIT13 "Running speed, Hz & A ON").
Already enabled — F7-03 default `0xE00F` includes BIT13 (`0x2000`).
- **View:** spindle must be **RUNNING**, then press the **SHIFT key (移位)** repeatedly (the key that
  "selects the displayed parameter in RUNNING status", manual line 1181 — NOT ENTER+SHIFT) to step
  the monitor display until both Hz and A light.
- Value = motor RPM from output freq = **30 × Hz** (4-pole: 450 Hz→13500, 600 Hz→18000).
- If SHIFT won't cycle to it, **set F7-03 = `2000`** (BIT13 only) → the run display shows **ONLY
  RPM**, no cycling. **`2001`** = Hz (BIT0) + RPM (BIT13), SHIFT toggles the two. Revert to `E00F`
  for the full default set.
- ÷10 gotcha (RESOLVED 2026-07-25): the speed read **÷10** because **F7-07 (load-speed decimal) = 1**
  put a decimal place in (3000 rpm showed as `300.0`). **Set F7-07 = 0** → integer RPM, no decimal
  (5-digit panel holds 18000). All multiplier params are correct: F1-04=450, F1-05=13500 (→ ×30),
  F7-06=1.0. Sanity: RPM = Hz × 30.
- ⚠ NOT the same as F7-04 BIT7 "Load speed" (a separately-scalable readout via F7-06 coefficient) —
  that was an earlier mistake; the Hz+A motor-RPM display is F7-03 BIT13.

---

## Constraints
1. **Power mismatch (bounds real spindle power).** GDL65 **9 kW / 30 A** vs Mollom **7.5 kW**.
   - **Single-phase input (current): ~3 kW / ~10 A = spin-only.** `F9-12 = 10`, `F8-36 = 33 %`.
   - **3-phase 220 V input (future): ~7.5 kW / ~28 A** = usable cutting, current-matches the 30 A
     motor. Would set `F9-12 = 11` and raise `F8-36` toward the drive's real capability.
   Wiring decision, not a param.
2. **Voltage is a clean match:** 220 V motor on 220 V drive → full flux to base speed **450 Hz**,
   then field-weakens 450→600 Hz = the motor's own **constant-power** region. V/F curve aligns
   with the nameplate torque curve (6.36 Nm flat to 13500 rpm → 4.77 Nm @ 18000 rpm, ≈ 9 kW).
3. **Protection is % of F1-03 (30 A).** On single-phase, `F8-36 = 33 %` holds output ≈ 10 A ≈ 3 kW
   (matches the derated capability). Keep `F9-00 = 1`, `F9-01 = 1.00`, `F9-06` default.

## Notes
- The drive has **no user-settable hold-current limit.** `A5-04` clamps only at the drive's own
  high overcurrent point; the only low-settable current control is the **`F8-36` output-overcurrent
  TRIP** (% of motor current) — a trip, not a hold.
- Input-current protection for the 8 AWG feed is the **upstream 40 A breaker**, not a VFD parameter.
- Manual sections still to read for completeness: wiring/terminal chapter, fault-code list
  (Ch 8.2), U0 monitoring group (what to watch live).
