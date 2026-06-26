# Mollom G75 — Parameterization (ned spindle)

Living record of every Mollom parameter we set, **verified against the actual
manual** (`docs/vfd/text/mollom_G75_AC_drive_manual.txt`, parameter table F0→U0,
manual lines ~1358–3345). Every value below cites the manual. Audit it against
the PDF/text before keying anything in.

## Context (read before trusting any value)
- **Drive:** Mollom **G75-2T-7R5-G-B** = 7.5 kW, **220 V class ("2T")**, Type G
  (constant-torque) — `mollom_facts.md`. **Fed SINGLE-PHASE → derate to ~3 kW**
  (single-phase stresses input rectifier/bus). Budget current as a 3 kW drive:
  ~**10 A** output at full voltage (3000 ÷ √3 ÷ 220 ÷ 0.8). `F9-12 = 10` mandatory.
- **Motor:** Colombo, **~16 HP (~12 kW), 480 V** — bigger and higher-voltage than
  the drive. **Intentional**, run **unloaded (no torque)**, current-limited.
  - 480 V motor on a ~220 V drive → drive can only reach ~220 V out, so the motor
    makes full V/Hz flux up to ~half its rated frequency, then **field-weakens**
    (reduced torque up high). Fine for no-load spin.
- **Goal right now:** very slow ramp, **output current capped ~5 A** to see if it
  can break the spindle away, input ≤ 35 A (#10 AWG → **35 A breaker upstream**,
  hardware, not a VFD parameter).

## ⚠️ Our manual is ABRIDGED
`mollom_G75_AC_drive_manual.txt` is the **quick-setup manual** (states so at line 53).
It lists F0-00→F0-27 then jumps straight to F1 — the real drive has **more parameters
it does not document** (e.g. F0-28+). **Policy: any parameter not found in this manual
is left at factory default** (we can't verify a value we can't read). If we ever need
one of those, get the full manual first.

## ⚠️ Corrections to earlier docs
`mollom_facts.md` / `mollom_g75_vfd.md` referenced **`B1-01` / `B1-02`** for
speed/run source. **There is no B group in this manual** (groups are F0–FP,
A0–A6, U0). The real parameters are:
- run source = **`F0-02`**, speed source = **`F0-03`** (see table). Those B-codes
  were wrong; do not use them.

---

## Parameter table (verified)

Legend: ✅ value decided · ⬜ needs machine data · ⚠️ conditional/caution.
"Mfr default" = the manual's default.

### Run / command / reference source (Group F0)
| Param | Name | Manual range / default | Set to | Why | |
|---|---|---|---|---|---|
| F0-00 | Type G/P | 1=G(const-torque), 2=P(fan/pump); def **1** | **1** | spindle = constant torque | ✅ |
| F0-01 | Motor 1 control mode | 0=SVC,1=FVC,2=V/F; def **2** | **2 (V/F)** | mismatched motor, no encoder → V/F | ✅ |
| F0-02 | Command source | 0=panel,1=Terminal,2=comm; def 0 | **0 (panel) for BENCH; 1 (Terminal) for production** | bench: keypad RUN/STOP. Production: CNC run via S1/S2 (R6/R7). | ✅ |
| F0-03 | Main freq source | 0/1=digital,2=AI1,**3=AI2**,4=AI3 pot,5=pulse…; def 4 | **3 (AI2)** | speed = ±10 V on AI2 (from pwmgen.04) | ✅ |
| F0-10 | Max frequency | 0–500 Hz (F0-22=2); def 50 Hz | **300.00 Hz** | = motor rated freq (anchors V/F curve + lets F1-04=300); NOT the speed cap | ✅ |
| F0-12 | Freq upper limit | lower-lim..max; def 50 Hz | **150.00 Hz** | the REAL cap: ~190 V, ≈9000 RPM. Knob full-scale=300 but clamped here | ✅ |
| F0-17 | Accel time 1 | 0.0–6500.0 s (F0-19=1) | **60.0 s** | slow ramp; tune from here | ✅ |
| F0-18 | Decel time 1 | 0.0–6500.0 s | **60.0 s** | slow ramp | ✅ |
| F0-19 | Acc/Dec time unit | 0=1s,1=0.1s,2=0.01s; def **1** | **1** | keep default (0.1 s) | ✅ |

### Motor nameplate (Group F1) — ⬜ NEED COLOMBO NAMEPLATE
Protections (F8-36, F9-00/01) are all **% of F1-03**, so these must be right.
| Param | Name | Range | Set to |
|---|---|---|---|
| F1-00 | Motor type | 0=std async,1=VF async,2=PMSM | **0** |
| F1-01 | Rated power (kW) | 0.1–1000 | **11.8** ✅ (16 HP) |
| F1-02 | Rated voltage (V) | 1–2000 | **380** ✅ nameplate |
| F1-03 | Rated current (A) | 0.01–655.35 | **28.0** ✅ nameplate (≈ drive rated A — current-matched!) |
| F1-04 | Rated freq (Hz) | 0.01–maxfreq | **300** ✅ nameplate (high-speed spindle) |
| F1-05 | Rated speed (RPM) | 1–65535 | **18000** ✅ nameplate (2-pole) |
| F1-37 | Auto-tuning | 0=none,1=static,2=rotate… | **0 (none) for now** ⚠️ don't rotate-tune a mismatched motor |

> Colombo nameplate: **380 V, 300 Hz, 18000 RPM, 2-pole.** V/Hz = 1.27. Drive holds
> full V/Hz up to ~173 Hz (220 V ÷ 1.27); only field-weakens above that. 25 Hz test
> = full flux, no weakening. Still need nameplate **kW** and **A**.

### V/F curve (Group F3)
| Param | Name | Range / default | Set to | |
|---|---|---|---|---|
| F3-00 | V/F curve | 0=linear,2=square…; def 0 | **0 (linear)** — constant-torque spindle | ✅ |
| F3-01 | Torque boost | 0.1–30%, 0.0=auto; def model | **0.0 (auto)** — keep low while current-limited | ✅ |

### Start / stop (Group F6)
| Param | Name | Range / default | Set to | |
|---|---|---|---|---|
| F6-00 | Start mode | 0=direct,1=speed-track,2=pre-exc; def 0 | **0 (direct)** | ✅ |
| F6-07 | Acc/Dec mode | 0=linear,1=static S,2=dyn S; def 0 | **0** (or 1=S-curve for softer) | ✅ |
| F6-10 | Stop mode | 0=decel,1=coast; def 0 | **0 (decel)** w/ long F0-18 | ✅ |

### Current guards / protection (Groups F8, F9, A5)
| Param | Name | Manual range / default | Set to | Why | |
|---|---|---|---|---|---|
| F8-36 | Output overcurrent threshold | **0.1–300.0 % of F1-03**, 0=off; def 200 % | **18.0 %** (5 A ÷ 28 A) for BRING-UP; later ~**36 %** (~10 A) for 3 kW single-phase normal | 5 A cap = a TRIP (no hold-limit exists) | ✅ |
| F8-37 | …detection delay | 0.00–600.00 s; def 0.00 | **0.1 s** | small filter vs inrush nuisance | ✅ |
| F9-00 | Motor overload protect | 0/1; def 1 | **1 (enable)** | thermal, refs F1-03 | ✅ |
| F9-01 | …gain | 0.20–10.00; def 1.00 | **1.00** | | ✅ |
| F9-05 | Overcurrent protect | 0/1; def 1 | **1 (enable)** | | ✅ |
| F9-06 | …level | **50–200 % of DRIVE rated**; def 150 % | **150 %** (cannot reach 5 A — floor ≈ 15 A) | secondary guard only | ✅ |
| F9-13 | Output phase loss | 0/1; def 1 | **1**, ⚠️ may nuisance-trip at very low current — disable (0) if it does | conditional | ⚠️ |
| F9-12 | Input phase loss / power loss | units=in-phase-loss, tens=power-loss; def **11** | **10** (REQUIRED) | single-phase input → input-phase-loss MUST be off or it trips | ✅ |
| A5-04 | Fast overcurrent-limiting | 0/1; def 1 | **1 (enable)** | hardware backstop (not adjustable to 5 A) | ✅ |

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

### Output terminals (Group F5) — feed back to the 7I97 inputs
| Param | Name | Value(meaning) | Set to | drives | |
|---|---|---|---|---|---|
| F5-02 | Control-board relay (RY1, TA/TB/TC) | 2=Fault output (coast-to-stop fault) | **2** | `vfd-fault` → input-13 | ✅ |
| F5-03 | Y1 function | 1=AC drive operating (running) | **1** | `spindle-running` → input-11 | ✅ |

---

## Open data still needed
1. **Colombo nameplate:** power (kW/HP), voltage, **rated current (A)**, freq (Hz),
   speed (RPM) → fills F1-01..05 and lets us compute the F8-36 % for a 5 A trip.
2. **Mollom input phasing:** single-phase or three-phase fed? → F9-12 (10 vs 11).
3. **Spindle max speed** (RPM / Hz) → F0-10, F0-12.

## Dual motor (Colombo now, HQD later)
The Mollom holds two motor sets: **Motor 1 = `F1`/`F2` (Colombo, in use)**, **Motor 2
= `A2` group (reserved for the HQD GDL65)**. Switch by `F0-24` (0/1) or a motor-select
DI (F4 value 41). HQD is a ~24 000 RPM water-cooled ATC electric spindle; manual only
requires "drive via VFD, match nameplate V + rated/cutoff Hz" — Mollom's 500–3000 Hz
range (`F0-22=1`) covers it. When it arrives, key its nameplate into A2; Colombo
stays in Motor 1. `F0-24 = 0` for now.

## Notes / decisions
- The drive has **no user-settable "hold current at 5 A" limit.** `A5-04` clamps at
  the drive's own high overcurrent point; the only low-settable current control is
  the **`F8-36` output-overcurrent TRIP** (% of motor current). So "max out at 5 A"
  = "fault if output > ~5 A" — a conservative bring-up guard.
- Input-current protection for the #10 AWG (35 A) is the **upstream breaker**, not a
  VFD parameter. With output capped ~5 A, input sits a couple amps.
- Manual sections still to read for completeness: wiring/terminal chapter,
  fault-code list (Ch 8.2), U0 monitoring group (what to watch live).
