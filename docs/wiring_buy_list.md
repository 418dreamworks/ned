# Wiring buy list — TEMPORARY (trash after purchasing)

Working shopping list for the remaining ned wiring. Specs pulled from this session's
decisions; component refs use [cmp:key] → see `components.md`. **Delete (→ trash/)
once ordered.** Anything marked TBD/verify is not yet confirmed.

---

## 1. Signal cable — STP (shielded twisted pair) — step/dir + pulse references
Carries all the 5 V differential signal pairs (7I85 → stepper drives, and 7I85 →
Yaskawa CN1 pulse reference).

- **Type:** 4-pair **shielded** twisted pair — shielded Cat6, or 4-pair
  (ideally individually-shielded) instrumentation cable.
- **Gauge:** **24 AWG** (24–28 OK; mA signals — do NOT buy heavy gauge).
- **Pairs needed:** 2 per drive (STEP±/DIR± or PULS±/SIGN±).
  - Steppers ([cmp:rotary-stepper]): 2 drives → 4 pairs.
  - Yaskawa head ([cmp:head-servo]): 2 drives → 4 pairs (future).
- **Length:** stepper run ≈ **25 ft** (matches the motor run); head run **TBD**.
  → buy a spool (~100 ft of 4-pair) to cover both.
- Land each ± on one twisted pair; foil shield single-end at the 7I85/cabinet end.

## 2. Stepper motor power cable — drive → stepper motor
- **Gauge:** **18 AWG** (4 A phase; fine to 8 A).
- **Type:** **shielded 4-conductor** (A+, A−, B+, B−), shield grounded at the DRIVE end.
- **Length:** **25 ft** run × **2** steppers → ~50 ft (or 2× 25 ft).
- Keep physically separated from the signal cable (item 1).

## 3. 70 V brick power [cmp:stepper-brick]
- **Gauge:** **16 AWG**.
- AC input (L1 from contactor pole 4 + N) to the brick; DC output V+/V− to the 2
  stepper drives. V− bonded to cabinet GND (single point).
- Slow-blow fuse on the brick L1, ~5–6 A (rides through inrush).

## 4. Yaskawa head [cmp:head-servo] — the two runs you asked for

### ⚠ Cable length limits (servopack manual, line 1873)
- **CN1 I/O signal cable: 3 m MAX** → Yaskawa drives must live **in/near the cabinet**, ≤3 m from the Mesa cards.
- Servomotor main-circuit cable: **50 m max** · Encoder cable: **50 m max** → these are the long runs to the head.

### (a) Yaskawa ↔ Mesa cards  — CN1 (BUILD from bulk; short, in-cabinet, ≤3 m)
- **Cable:** ≤3 m. Two signal groups (keep the 5 V pulse pairs separate from the 24 V lines —
  two cables, or individually-shielded pairs):
  - **From 7I85 — 2 twisted pairs / 4 cond (5 V differential):** PULS± (CN1-7/8) + SIGN± (CN1-11/12). STP 24 AWG.
  - **From/to 7I84 — ~4 single-ended 24 V cond (NOT pairs):** /S-ON, +24VIN (input common),
    ALM, ALM-COM. Ordinary shielded, 24 AWG.
  - So ~8 conductors/drive total: 4 (85, twisted) + 4 (84, single-ended). NOT 4 pairs.
- **CN1 mating connector ×2** — drive connector = **3M 10250-52A2PL, 50-pin** (manual p.85 §2.3.1).
  ✅ **You HAVE the Yaskawa connector kits** → solder the CN1 cable straight onto the kit; no
  separate mating-connector purchase needed.

### (b) Yaskawa ↔ servomotors  — BUILD from bulk + your connector kits (long run to head)
Source: motor manual **§8.1 "Cables for the SGMXJ Servomotors."** ✅ **You HAVE the Yaskawa
connector kits**, so both cables are **buildable from bulk** — terminate the motor/encoder
ends with the kits; no pre-made Yaskawa cables needed. **Two cables per axis:**
- **(1) Servomotor main-circuit (power) cable** — U/V/W + ground. **18 AWG, 4-conductor
  shielded.** Motors have **NO holding brake** → **no brake leads** (4 conductors, not 6).
- **(2) Encoder cable** — CN2 ↔ motor 26-bit serial encoder. **2 twisted pairs + shield**:
  PS± (serial data) + PG5V/PG0V (power). Encoder is **26-bit batteryless absolute → no battery
  wires.**
  - ⚠ Encoder **5 V power pair gauge vs length**: 24 AWG is fine on a short run (~25 ft, ~0.3 V
    drop); toward 50 m it under-volts the encoder (~1.7 V drop) — use a heavier power pair for a
    long run.

Spec the bulk cable by:
- **Length** ≤50 m. **>20 m reduces intermittent-duty torque** (voltage drop), §8.1.1.
- **Flexible vs standard** — head moves → **flexible (robotic)** bulk cable.
×2 (A and C).

## 5. Misc / grounding
- Ferrules for STP conductors (24 AWG) + 18 AWG.
- Shield drain terminations; cabinet GND lugs.
- Slow-blow fuse(s) per item 3.

---

### Open items to confirm before ordering
- Head-run cable **length** (item 1, 4).
- Whether the steppers' existing 8-cond foil cable is being **replaced** by STP or kept.
