# ned — Machine Components (single source of truth)

**This file is the ONLY place that holds detailed component descriptions** (model
numbers, ratings, where each part is used). Double-accounting rule:

> **Detail lives here. Everywhere else REFERENCES, never duplicates.**
> To cite a component from any other doc, config comment, or diary, use its
> **Key** in the form `[cmp:<key>]` — e.g. `[cmp:head-servo]`. Do not restate
> specs outside this file; if a spec is wrong, it gets fixed in ONE place (here).

Each entry carries a **Source** (where the info came from) and a **Status**
(`VERIFIED` = confirmed against nameplate/datasheet/live readout; `UNVERIFIED` =
recorded but not yet confirmed; `TBD` = model/spec not yet captured). Full vendor
manuals are in `docs/<vendor>/` and indexed in `docs/INDEX.md`.

---

## Motion — drives & motors

### Main-axis analog servo drives  ·  Key: `main-servo`
Drives **X (j0, starboard), Y (j1), Z (j2), W (j3, port)** — the gantry + Y + Z.
- **Type:** Servo Dynamics **SDSM** analog velocity drives (±10 V command).
- **Model (exact chassis P/N):** TBD — read off the cabinet (manual lists SDSMB-1/3/4-axis chassis variants).
- **Bus:** 60–170 VDC (transformer-fed via contactor [cmp:r0-contactor]).
- **Command:** ±10 V from 7I97T AOUT0–3 ([cmp:mesa-7i97t]).
- **Manual:** `docs/servo/servo_dynamics_sdsm_manual.pdf`
- **Source:** SDSM manual + cabinet. **Status:** drive class VERIFIED (live, moved this session); exact P/N **TBD**.

### Swivel-head servos (A & C)  ·  Key: `head-servo`
Drives the swivel head — **A (tilt, j5)** and **C (spin, j6)**. Currently INERT.
- **The two servopacks are physically labelled by axis (convention, 2026-06-27):**
  - **Servopack "A"** → head **TILT** (A axis, about X/W) — joint 5, stepgen.02, 7I85 TB1 STEP2/DIR2.
  - **Servopack "C"** → head **SPIN** (C axis, about Z) — joint 6, stepgen.03, 7I85 TB1 STEP3/DIR3.
- **Motor:** Yaskawa **SGMXJ-04AUA6SC2** ×2 — 400 W, 200 V, Σ-X medium-inertia.
- **Drive:** Yaskawa **SGDXS-2R8A00A** ×2 — Σ-XS SERVOPACK, analog/pulse, 200 V, 2.8 A.
- **Power:** single- or three-phase 200–240 VAC (single-phase = L1,L2 only, no N; set Pn00B=n.□1□□). Mandatory magnetic contactor [cmp:head-contactor].
- **Manuals:** `docs/servo/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.pdf` (drive); `docs/servo/yaskawa_sigma_x_rotary_servomotor_product_manual.pdf` (motor).
- **Source:** nameplate (user 2026-06-27) + servopack manual combination table (line 2686: SGMXJ-04A↔2R8A, 400 W). **Status:** models VERIFIED; `UA6SC2` suffix decode UNVERIFIED.

### Workpiece-rotary steppers (B)  ·  Key: `rotary-stepper`
Drives **B (workpiece rotary about Y, j4)** — 2 mirrored steppers as ONE stepgen (one motor reversed in copper).
- **Drive model:** TBD (no datasheet on hand). Spec (user-transcribed 2026-06-27):
  18–110 VAC / 18–160 VDC supply (NOTICE: ≤110 V either), 2.2–8.2 A out, pulse ≤300 kHz / ≥1.2 µs / falling-edge, DIR setup ≥5 µs, control 5–20 mA (typ 10), inputs 3.3–5 V, 2 s init, UV 7.5 V / OV 170 V.
- **Motor:** TBD — ~4 A/phase.
- **Supply:** 70 VDC from [cmp:stepper-brick]. **Signals:** 7I85S STEP0/DIR0 ([cmp:mesa-7i85s]).
- **Source:** user-transcribed spec. **Status:** UNVERIFIED; models **TBD**.

---

## Control — Mesa FPGA cards

### Mesa 7I97T  ·  Key: `mesa-7i97t`
Main Ethernet card (`hm2_eth`). 6 analog ±10 V (AOUT, drives [cmp:main-servo]), 6 muxed encoder inputs (TB1/TB2), 6 SSR, isolated inputs. Firmware `7i97t_7i85sd`.
- **Manual:** `docs/mesa/mesa_7i97t_manual.pdf` · **Firmware:** `firmware/7i97t/` · **Status:** VERIFIED (live).

### Mesa 7I85S  ·  Key: `mesa-7i85s`
Step/dir + encoder daughtercard on the 7I97T DB25 (P1). 8 differential outputs (STEP0–3/DIR0–3, 35 mA, 5 V). Drives [cmp:rotary-stepper].
- **Manual:** `docs/mesa/mesa_7i85s_manual.pdf` · **Status:** VERIFIED.

### Mesa 7I84U  ·  Key: `mesa-7i84u`
Smart-serial field I/O (32-in/16-out), on the 7I97T sserial. Cabinet digital I/O.
- **Manual:** `docs/mesa/mesa_7i84u_manual.pdf` · **Status:** VERIFIED (live).

---

## Power & switching

### 70 V stepper brick  ·  Key: `stepper-brick`
Isolated SMPS feeding [cmp:rotary-stepper]. **70 VDC, 5.7 A, ~400 W.** Input L/N 110 VAC + chassis GND. Output **V− bonded to cabinet GND** (single point). Fed via [cmp:head-contactor] pole 4 (L1).
- **Model:** TBD. **Source:** unit label (user). **Status:** ratings VERIFIED (label); model TBD.

### IDEC RY4S-U (relay R5)  ·  Key: `r5-relay`
4PDT control relay = the master "drives enabled" signal relay. Contacts **5 A @ 120/240 VAC** (resistive & inductive). Pulled by CNC `/EMEROUT`; pulls the contactors.
- **Datasheet:** `unsorted/RY4S-UDC100-110V.pdf` · **Source:** user + datasheet. **Status:** VERIFIED.

### R0 contactor  ·  Key: `r0-contactor`
Main power contactor for [cmp:main-servo] (SDSM transformer feed). Coil on `*7`, pulled via [cmp:r5-relay] + e-stop chain.
- **Source:** `docs/tracing/relays.md`. **Status:** wiring VERIFIED; P/N TBD.

### Head/stepper contactor  ·  Key: `head-contactor`
4-pole contactor pulled by [cmp:r5-relay]. Poles 1–3 → [cmp:head-servo] L1/L2/L3 (single-phase uses L1/L2, 1 idle); pole 4 → [cmp:stepper-brick] L1.
- **Model:** TBD (planned). **Status:** TBD.

### Cabinet supplies & relays
24 VDC supply (V−→GND), 5 VDC supply (V−→GND), relays R0–R10. Detail: `docs/tracing/relays.md`, `docs/tracing/screw_terminals.md`. **Status:** see tracing docs.

---

## Spindle

### Mollom G75 VFD  ·  Key: `vfd`
**G75-2T-7R5-G-B** — 7.5 kW, 3-phase 220 V class (run single-phase derated to ~3 kW). Drives the spindle, commanded by 7I97T pwmgen.04 (±10 V on AI2).
- **Manual:** `docs/vfd/mollom_G75_AC_drive_manual.pdf` · **Decode/params:** `docs/vfd/mollom_facts.md`, `docs/vfd/mollom_parameterization.md` · **Status:** VERIFIED.

### Spindle motor (current)  ·  Key: `spindle-motor`
Colombo — nameplate **380 V / 300 Hz / 18000 RPM, 11.8 kW (16 HP), 28 A**. Oversized for the single-phase-derated VFD (runs underpowered, not faulted).
- **Source:** nameplate (2026-06-25). **Status:** VERIFIED, in use.

> **Two spindle configurations — NOT a replacement.** The Colombo (current config) and the
> GDL65 head ([cmp:swivel-head], future config) are **alternate setups the user switches
> between** — the Colombo is **kept**. The VFD already carries both as separate motor parameter
> sets (Colombo = Motor 1 `F1/F2`, HQD = Motor 2; `vfd/mollom_parameterization.md:123`). One VFD
> output drives one spindle at a time; the changeover mechanism is TBD.

### Swivel head  ·  Key: `swivel-head`
HQD **GDL65** 5-axis electric **water-cooled, auto-tool-change** swivel head — carries the
A/C [cmp:head-servo] axes *and* the spindle. HSK-F63 or ISO-30 taper.
- **Manual:** `docs/hqd/` · **Status:** TBD (not yet commissioned).

**Wires to the head** (manual §4 "Electrical Connections"; power+signal exit the central
through-hole, §2.4.1). Air/water lines are separate (§3), not wires.

| Circuit | Cond. | Function | Lands on |
|---|---|---|---|
| A servo power | 4 | U/V/W/G — head tilt servo | [cmp:head-servo] |
| A encoder | 2 pr+shld | tilt servo encoder | [cmp:head-servo] |
| C servo power | 4 | U/V/W/G — head spin servo | [cmp:head-servo] |
| C encoder | 2 pr+shld | spin servo encoder | [cmp:head-servo] |
| Spindle motor power | 4 | White=U, Green=V, Red=W, Yel/Grn=GND — **via VFD** (§4.1) | [cmp:vfd] |
| Thermal switch | 2 | Brown(thin)×2. **NC**, opens ≥100 °C, 250 V/5 A. **In series with safety-stop chain** (§4.1) | **7I97 IN14** `spindle-overtemp` (reuse, identical NC wiring) |
| S1 tool-clamp (locked) detect | 3 | PNP NO prox: Brn +24 V / Blk sig / Blu 0 V (§4.2) | **7I84 input 29/30/31** (one of) |
| S2 tool-unclamp detect | 3 | PNP NO prox (Brn/Blk/Blu) (§4.2) | **7I84 input 29/30/31** (one of) |
| S3 axis-stop (rotation stopped) detect | 3 | PNP NO prox (§4.2). NB: ISO30 — no no-empty-start guarantee | **7I84 input 29/30/31** (one of) |

**9 circuits total.** Servo pulse/seq-I/O pins: `mesa_7i85s_wiring.md` + `mesa_7i84u_wiring.md`.

**Decision (forward note):** the three GDL65 sensors (S1/S2/S3), each **3-conductor PNP NO**, reuse
the existing 7I84 inputs **29, 30, 31** (same input family as today's clamp/drawbar prox).
**Exact sensor↔input assignment, polarity, and testing = TBD.** The Colombo **clamp** (output-13,
input-29) has **no GDL65 equivalent** (GDL65 is drawbar-only, ISO30) — input-29 is freed and
folds into this S1/S2/S3 pool. Drawbar **unclamp valve** → reuse `drawbar-release` (output-15) →
GDL65 port B.

**GDL65 pneumatics = one switched solenoid only.** Port B (tool-unclamp, 10.5–11.5 bar) is the
single switched valve (reuse output-15). Port A (air-seal + taper-clean, 4–4.5 bar) is
**always-on, regulated — no solenoid, no Mesa output** (air-seal must run continuously while the
machine is on, §3.3). Coolant C/D is its own pump loop. The existing Colombo air + wiring serve
both spindle configs.

#### Reuse from existing Fagor-era I/O — PROPOSED (functional match, not yet landed)

The GDL65 is an auto-tool-change spindle; most of its spindle-side circuits map onto I/O the
machine **already has**. Cabinet-side wiring is unchanged (golden rule) — only the field device
at the end becomes the GDL65's. Existing signals cited from the wiring docs; GDL65 needs from
manual §4. **Logic sense and VFD params still to confirm — proposed, nothing landed.**

| # | GDL65 head need | Reuse existing | Existing signal (source) | Notes |
|---|---|---|---|---|
| 1 | Spindle power U/V/W/G | shares the VFD (not the Colombo cable) | Mollom [cmp:vfd] | **NOT a replacement** — Colombo stays; GDL65 is a separate config. Head gets its **own** power cable; VFD switches to its motor set (Motor 2). Changeover TBD. |
| 2 | Thermal switch (NC, 2-wire) | 7I97 **IN14** `spindle-overtemp` (`*39` OVERTEMP) | mesa_7i97t_wiring.md:273, 282 | **identical wiring** — cabinet +24 V → NC contact → IN14, IN COMMON pin 12 @ 0 V. Closed=OK, opens on overheat=fault (fail-safe). **Field-end swap only**: old spindle's thermal contact → GDL65's 2 brown wires. Existing `spindle-overtemp` HAL logic unchanged. |
