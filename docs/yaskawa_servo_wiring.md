# Yaskawa Servo Wiring — head A & C (source of truth)

Wiring reference for **both** head servopacks. **A and C are electrically identical** — the
only per-axis differences are the 7I85 pulse terminals and the 7I84 sequence-I/O terminals
(§ "Per-axis differences"). Everything else (CN1 pins, motor, encoder, power) is the same on
both.

- **Components / models / ratings:** `components.md` → [cmp:head-servo] (drive SGDXS-2R8A00A,
  motor SGMXJ-04AUA6SC2), [cmp:head-contactor], [cmp:mesa-7i85s], [cmp:mesa-7i84u].
- This file is the **servo wiring source of truth**; the per-card docs (`mesa_7i85s_wiring.md`,
  `mesa_7i84u_wiring.md`) hold the card-centric view and point here.
- **Status:** both head servopacks fully wired; both axes **move under software** (`move.sh a|c`).
  Drive params in `servo/yaskawa_params_quickref.md` (Pn000=0010 position, Pn50A/B not-pot,
  Pn515=8887 SEN, Pn20E/210=8192 gear, Pn002 absolute). HAL joints 5/6 → stepgen 02/03,
  /S-ON via 7I84 output-06/07, ALM on input-14/15(-not) (`ned.hal` §3/§7/§8). SCALE + limits =
  calibration (`commissioning/calibration_plan.md`).

Axis assignment (`components.md:31-33`). **Naming: head servos are `C` (spin) and `AB` (tilt).**
"AB" = the tilt axis, **A or B TBD** — depends on the XY-axis convention / head kinematics (the
5axiskins A/C-vs-B/C question). *The LinuxCNC axis letter stays a single letter (provisional `A`)
in `ned.ini` until resolved — "AB" is the doc label, not a valid LinuxCNC axis letter.*
- **Servopack AB** → head **TILT** (AB axis, joint 5, stepgen **02**).
- **Servopack C** → head **SPIN** (C axis, joint 6, stepgen **03**).

---

## Per-axis differences (the ONLY things that differ A vs C)

| Signal group | A (tilt) | C (spin) |
|---|---|---|
| 7I85 pulse stepgen / TB1 pins | **02** — TB1 3/4/5/6 | **03** — TB1 11/12/13/14 |
| 7I84 `/S-ON` output | **TB3-23** (OUTPUT6) | **TB3-24** (OUTPUT7) |
| 7I84 `ALM−` input | **TB3-15** (INPUT14) | **TB3-16** (INPUT15) |

All CN1 pins, motor, encoder, and power connections below are **identical** on both drives.

---

## 1. Pulse reference — 7I85 → CN1 (as-built)

Cable: shielded, **2 twisted pairs** (orange pair = STEP/PULS, blue pair = DIR/SIGN; pairs not
individually shielded). Convention **colored = +, white = −**. 24 AWG, 5 V differential, ≤3 m.

| Wire | Signal | 7I85 TB1 (A / C) | CN1 (both) |
|---|---|---|---|
| orange | STEP+ | 4 / 12 | **CN1-7** (PULS) |
| orange-white | STEP− | 3 / 11 | **CN1-8** (/PULS) |
| blue | DIR+ | 6 / 14 | **CN1-11** (SIGN) |
| blue-white | DIR− | 5 / 13 | **CN1-12** (/SIGN) |

- **CN1 end soldered (committed).** Polarity fixes (wrong direction / backward count) → swap the
  pair at the **7I85 screw-terminal end**, not CN1. (+/− ↔ PULS//PULS polarity is assumed.)
- **Shield: servopack (CN1) end only**, via the molded-connector grounding band (360° bond).
  **7I85/cabinet end floats.** Single-ended, no ground loop.

## 2. Sequence I/O (24 V) — 7I84 ↔ CN1

Single-ended 24 V (NOT pairs), ordinary shielded 24 AWG. **Set OUTPUT6/7 to sourcing.**

| Signal | dir | 7I84 (A / C) | CN1 (both) |
|---|---|---|---|
| `/S-ON` (servo enable) | Mesa → drive | TB3-23 / TB3-24 (OUTPUT6/7, sourcing) | **CN1-40** |
| `ALM−` (alarm) | drive → Mesa | TB3-15 / TB3-16 (INPUT14/15) | **CN1-32** |
| `ALM+` | +24 V rail | TB1 rail (1–5) | **CN1-31** |
| `+24VIN` (input common) | 0 V rail | TB1 GND (6–8) | **CN1-47** |

- **Source mode:** OUTPUT6/7 push +24 V into CN1-40; CN1-47 (input common) sits at **0 V**.
- **ALM is fail-safe / normally-conducting** — ON when healthy, OFF on fault or power loss.
  Invert in HAL (`not`) so loss-of-signal = fault.

## 3. Motor power — servopack → motor (direct)

- **U / V / W / PE** straight from the servopack output to the motor. **No fuse, no contactor**
  between drive and motor.
- Cable: **18 AWG, 4-conductor shielded** (no brake leads — motors have **no holding brake**).
  **PE conductor = green/yellow** (motor-frame ground). The encoder cable has no green/yellow.
- Buildable from bulk + the Yaskawa connector kits. ≤50 m (>20 m derates torque).

## 4. Encoder — servopack CN2 → motor

Connector: **CN2 = Molex 53984-0681, 6-pin** (solder). Pin layout, rotary motor (manual §4.4.2, p.144):

| CN2 pin | Signal | Wired? |
|---|---|---|
| 1 | PG5V (+5 V) | ✅ power pair (encoder STP) |
| 2 | PG0V (0 V) | ✅ power pair (encoder STP) |
| 3 | BAT(+) | ✅ **battery** ← cable 92 (C: `*57`, AB: `*59`) |
| 4 | BAT(−) | ✅ **battery** ← cable 92 (C: `*56`, AB: `*58`) |
| 5 | PS (data +) | ✅ data pair (encoder STP) |
| 6 | /PS (data −) | ✅ data pair (encoder STP) |
| Shell | Shield | drain |

- ⚠ **BATTERY-REQUIRED 26-bit absolute** (verified 2026-07 — **NOT** batteryless). No backup battery on BAT± → permanent **A.810** every power-up.
- **Data + power (4 cond):** shielded STP → pins 1/2/5/6 (color map below).
- **Battery (BAT±):** carried **separately on cable 92** from cabinet-end batteries → CN2 pins 3/4. Terminals (`screw_terminals.md`): **C** — `*56` BAT−, `*57` BAT+; **AB** — `*58` BAT−, `*59` BAT+. **BAT+ = pin 3 (polarity critical).** One battery per encoder only.
- **Encoder shield → CN2 shell / servopack ground** (manual line 5491, single-end at servopack).

**As-built — encoder cable color map (2-pair + shield). Same for AB and C, both ends (straight-through):**

Data+power cable = **4 conductors + bare shield/drain** (NO green/yellow — that lives on the UVW power cable, see §3). **Battery pair (pins 3/4) is a SEPARATE cable — cable 92.**

| Wire | Signal | CN2 pin |
|---|---|---|
| orange | PG5V (+5 V) | **1** |
| orange-white | PG0V (0 V) | **2** |
| blue | PS (data +) | **5** |
| blue-white | /PS (data −) | **6** |
| shield / drain | FG | **shell** — servopack end only |
| cable 92 | BAT+ / BAT− | **3 / 4** — battery, separate cable (§4 table; `screw_terminals.md` `*56`–`*59`) |

Convention (this cable's colors are not Yaskawa-standard): **orange pair = power, blue pair =
data; colored = +/high, white = −/return.**
- ⚠ **Power-pair polarity is CRITICAL & destructive if reversed** — orange = PG5V (+5 V),
  orange-white = PG0V (0 V). Meter before powering.
- Data pair non-destructive: if the drive alarms encoder-comm, **swap blue ↔ blue-white**.
- 4 conductors straight-through, **identical at both ends** (drive CN2 + motor connector); **same for A & C**.
- **Shield/drain → CN2 shell at the servopack end ONLY** (manual line 5491); float the motor end
  (both chassis are earthed → landing both ends makes a ground loop).
- ⚠ 5 V power pair gauge vs length: 24 AWG fine short (~25 ft); heavier for long runs (under-volts
  toward 50 m).

## 5. Power to the servopack (input side)

| Terminal | Function | Spec |
|---|---|---|
| `L1 / L2 / L3` | main circuit (3-phase) — or `L1 / L2` (single-phase, set `Pn00B=n.□1□□`) | 200–240 VAC |
| `L1C / L2C` | control power | single-phase 200–240 VAC |
| `B1 / B2 / B3` | regen | 2R8A: external resistor B1–B2 **only if needed** (no internal resistor) |

Fed from **[cmp:head-contactor]** poles 1–3 → L1/L2/L3. Contactor pulled by [cmp:r5-relay].

### Fusing (per servopack; slow-blow — rectifier + SMPS inrush)
| | 3-phase | single-phase 240 |
|---|---|---|
| Main fuses | 3 (L1/L2/L3) | 2 (L1/L2) |
| Control fuses | 2 (L1C/L2C) | 2 (L1C/L2C) |
| Per drive | 5 | 4 |
| **Both drives** | **10** | **8** |

### Loads & planned values (manual §2.1 ratings; values load-adequate, **NOT factory-cited**)
- Main input: **2.5 Arms** (3-ph) / **5.0 Arms** (1-ph). Control input: **0.2 Arms**. Output 2.8 Arms.
- Planned fuses: **main 8–10 A**, **control 1 A**. Wire: **12 AWG** main→contactor, **16 AWG**
  contactor→drive, **18 AWG** control.
- ⚠ Exact factory fuse/wire is in the **Σ-X Peripheral Device Selection Manual (SIEP C710812 12,
  not on hand)** — product manual gives currents only (line 6072).

---

## Cross-references
- 7I85 pulse terminals (card view): `mesa_7i85s_wiring.md`
- 7I84 sequence I/O (card view): `mesa_7i84u_wiring.md`
- Components/ratings: `components.md` [cmp:head-servo], [cmp:head-contactor]
- Cable buy list: `to_buy.md` §4
