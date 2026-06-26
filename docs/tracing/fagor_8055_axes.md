# Fagor 8055 — AXES Module

The AXES module is the Fagor 8055/B's I/O board. It has three connectors used in this machine:

- **X9** — primarily inputs (I1–I32, plus the +24 V and 0 V rails for the input common)
- **X10** — primarily outputs (O1–O24), plus a few inputs (I33–I40)
- **X8** — analog ±10 V axis and spindle command outputs

## Mesa Replacement — Connector → Card Mapping

Each Fagor AXES connector has been reassigned to a specific Mesa terminal block. Full landing details are in the per-card wiring notes.

| Fagor connector | Function | Mesa destination | Detailed notes |
|---|---|---|---|
| X1 | X-axis encoder feedback | **7I97T TB1 bottom plug** (encoder 0, pins 1–8) | `mesa_7i97t_wiring.md` TB1 section |
| X2 | Y-axis encoder feedback | **7I97T TB1 middle plug** (encoder 1, pins 9–16) | `mesa_7i97t_wiring.md` TB1 section |
| X3 | Z-axis encoder feedback | **7I97T TB1 top plug** (encoder 2, pins 17–24) | `mesa_7i97t_wiring.md` TB1 section |
| X4 | W-axis encoder feedback | **7I97T TB2 bottom plug** (encoder 3, pins 1–8) | `mesa_7i97t_wiring.md` TB2 section |
| X5 | unused | — | — |
| X6 | Pendant (handwheel + axis-selector) | Handwheel → **7I97T TB2 middle plug** (encoder 4, pins 9–16); axis-selector (X6 pin 5) → **7I97T TB4 IN0** (pin 1) | `mesa_7i97t_wiring.md` TB2 + TB4 pendant block sections |
| X7 | unused | — | — |
| X8 | Analog ±10 V outputs (X/Y/Z/W velocity + spindle) | **7I97T TB3** (plugs 1–4 + plug 6; channel 4 unused; spindle on channel 5/plug 6) | `mesa_7i97t_wiring.md` TB3 section |
| X9 | Digital inputs (e-stop + limits + spindle/safety) | **7I97T TB4 IN4–IN7** + **TB5 IN8–IN14**. TB5 IN15 reserved for future X/W homing limit. | `mesa_7i97t_wiring.md` TB4 + TB5 cabinet block sections |
| X10 | Digital inputs (tool-changer sensors) + outputs (drive-enable, spindle, solenoids) | **All on 7I84U TB2**: inputs on INPUT28–INPUT31 (pins 13–16), outputs on OUTPUT8–OUTPUT15 (pins 17–24) | `mesa_7i84u_wiring.md` TB2 section |

The X9 cable's 0 V wires (pins 18 and 19) are repurposed as the IN COMMON return for the 7I97T cabinet input block (land on TB5 pins 3 and 6, then daisy-chain to the rest of the cabinet IN COMMONs at cabinet 0 V).

## Connector Gender (for Mesa replacement)

When swapping the Fagor AXES module for Mesa cards, the existing cables stay in place. To mate with those cable ends, the Mesa-side breakout / connector needs to match the gender the Fagor side currently presents:

| AXES connector | Gender on Fagor side | What the cable end is | Mesa-side connector needed |
|---|---|---|---|
| X1 | Female | Male | Female |
| X2 | Female | Male | Female |
| X3 | Female | Male | Female |
| X4 | Female | Male | Female |
| X5 | Male | Female | Male |
| X6 | Male | Female | Male |
| X7 | Male | Female | Male |
| X8 | Male | Female | Male |
| X9 | Male | Female | Male |
| X10 | Male | Female | Male |

Summary: X1–X4 need female connectors on the Mesa side; everything else (X5–X10) needs male.

**Verified traces** (below) come from physical tracing only. **PLC reference info** at the bottom of this file comes from the OEM PLC source (`PLC_PRG.PIM`) and is a *reference for verification* — never assume the PLC tells us what's actually wired.

---

## X10 Connector — Verified Traces

| Pin | Verified other end | Status |
|---|---|---|
| 2 | `*8` (then brown wire → R5C2) | ✓ |
| 3 | `*40` (then brown wire → R6C2; the segment from X10/pin 3 to `*40` is a red wire labelled "05") | ✓ |
| 17 | `*54` (then white wire → R10A2; R10's coil is driven by the probe contact via `*84` and cable "04" BLK → tool probe surface) — TOOLLEN signal, interposed by R10 | ✓ |
| 21 | `*55` (via brown wire; then yellow wire → R9C2; R9 is the interposing relay for the chip blow-off air-blast solenoid at cable 92 BRN → `*90` → R9A2) — BITCOOL output, used here for chip blow-off (not liquid coolant) | ✓ |
| 27 | `*61` (then brown wire of cable "00-2" → toolsetter solenoid valve NVZ3120 / Bimba probe deploy) | ✓ |
| 29 | `*63` (via brown wire; then orange wire of cable 92 → field-side clamp solenoid; PIM-named `OCLAMP O18`; drawbar IN / clamp tool) | ✓ |
| 30 | `*64` (via red wire; then yellow wire of cable 92 → field-side air purge solenoid; PIM-named `OBLOWOFF O20`; spindle taper air purge during tool change) | ✓ |
| 31 | `*65` (via orange wire; then green wire of cable 92 → field-side drawbar release solenoid; PIM-named `ODRAW O22`; drawbar OUT / release tool) | ✓ |
| 34 | `*68` (via light blue wire; then RED wire of cable 92-2 → top junction box → BIGGREEN grey → field-side **rack position** sensor). PIM symbol is `ITOOLIN I36` ("Tool present in spindle") but actual function on this machine is rack position — OEM repurposed. | ✓ |
| 35 | `*69` (via white wire; then red wire of cable 30-2 → drawbar UP position sensor signal output; sensor's +24 V supply is on `*76` via cable 30 RED) | ✓ |
| 36 | `*70` (via black wire; then brown wire of cable 30-2 → drawbar DOWN position sensor signal output; sensor's +24 V supply is on `*76` via cable 30 RED) | ✓ |

All other X10 pins: not yet physically traced.

---

## X9 Connector — Verified Traces

| Pin | Verified other end | Status |
|---|---|---|
| 2 | `*6` (end of the e-stop daisy chain) | ✓ |
| 21 | `*24` (via brown wire; then RED wire of cable 13 → gantry "back" limit switch — physical X axis, gantry-X back) | ✓ |
| 22 | `*25` (via red wire; then BLK wire of cable 13 → gantry "front" limit switch — physical X axis, gantry-X front) | ✓ |
| 23 | `*26` (via orange wire; then RED wire of cable 23 → Y "left" limit switch — physical Y-axis left) | ✓ |
| 24 | `*27` (via yellow wire; then BLK wire of cable 23 → Y "right" limit switch — physical Y-axis right) | ✓ |
| 25 | `*28` (via green wire; then RED wire of cable 33 → Z **bottom** limit switch — Z-axis bottom). Corrected 2026-06-24 by hardware test (`input-09`); previously mislabelled "top". | ✓ |
| 26 | `*29` (via blue wire; then BLK wire of cable 33 → Z **top** limit switch — Z-axis top). Corrected 2026-06-24 by hardware test (`input-10`, triggered the top over-travel switch); previously mislabelled "bottom". | ✓ |
| 33 | `*36` (then → R1A3; R1 energizes when the VFD reports spindle is running, so +24 V appears on `*36`); PIM `IROTATE I26` — "spindle is rotating" feedback. The CNC reads this to confirm the spindle is actually spinning, distinct from being commanded to spin. | ✓ |
| 34 | `*37` (via light blue wire; then via red wire of cable "00" to the air pressure sensor's signal output; sensor's other wire is on `*71` for +24 V power) | ✓ |
| 35 | `*38` (via white wire; then yellow wire → VG5/18 — VFD's fault contact NO output; `SPINFLT I30` per PIM, matches actual function) | ✓ |
| 36 | `*39` (via black wire; then `*39` connects via red wire of cable "9" to the spindle overheat thermostat; thermostat +24 V is on `*71` via cable "9" white wire) | ✓ |

All other X9 pins: not yet physically traced.

---

## X6 Connector — Verified Traces

X6 is the **pendant connector** on the AXES module (handwheel + axis selector + supply). 26-pin high-density SUB-D female. See `pendant.md` for the field-side details (MPG model, terminal layout, cable inventory, axis selector wiring).

| X6 pin | Cable / conductor (pendant cable) | Pendant-side destination |
|---|---|---|
| 1 | RED wire in Brn cable | MPG/B3 |
| 2 | BLK wire in Brn cable | MPG/A2 |
| 3 | RED wire in Red cable | MPG/B4 |
| 4 | BLK wire in Red cable | MPG/A3 |
| 5 | RED wire in ORN cable | Axis selector C |
| 6 | — | (unused) |
| 7 | RED wire in Yel cable | MPG/B1 |
| 8 | BLK wire in Yel cable | MPG/B2 (also = axis selector NC) |
| 9–14 | — | (unused) |
| 15 | Shield | bonded to pendant body via cable shield |
| 16–26 | — | (unused) |

7 active signal pins + 1 shield pin used. The ORN cable BLK conductor is dead-ended at both ends.

The pendant e-stop runs in a separate grey 2-conductor cable to `*3`/`*4`, NOT through X6.

---

## X8 Connector — Verified Traces

X8 carries the analog ±10 V velocity commands from the AXES module. **The V01.6x manual's pinout for X8 (9-pin SUB-D with only 4 outputs) does NOT match the V03.11/B reality — physical tracing is the authority here.**

### X8 pin-by-pin (V03.11/B, physical trace)

Each axis uses a pair of pins (signal + ground/return). Cables are labelled at the field end by their pair number.

| Cable label | Pin (signal) | Pin (ground/return) | Goes to drive |
|---|---|---|---|
| "1" | pin 1 (RED) | pin 9 (BLK) | X drive |
| "2" | pin 2 (RED) | pin 10 (BLK) | Y drive |
| "3" | pin 3 (RED) | pin 11 (BLK) | Z drive |
| "4" | pin 4 (RED) | pin 12 (BLK) | W drive |
| "5" | pin 5 (RED) | pin 13 (BLK) | dead-ended (spare, goes nowhere) |
| "6" | pin 6 (RED) | pin 14 (BLK) | dead-ended (spare, goes nowhere) |
| "7" | pin 8 (RED) | pin 14 (BLK) | Spindle VFD (cable "7" → VG5/13 + VG5/17 + shield/green to VG5/12) |

Note: cable "7" uses pin 8 for signal (pin 7 is skipped — possibly unused or reserved), and pin 14 BLK is shared between cable "6" and cable "7" (single ground return for both pairs).

(More to come as user traces each cable.)

### Cable "7" — Spindle (previously documented)

Cable "7" is a 4-conductor shielded cable carrying the spindle ±10 V velocity command:
- Active red → VG5/13 (legacy) / Mollom AI2 (planned)
- Active black → VG5/17 (legacy) / Mollom GND (planned)
- Shield + green wire → VG5/12 + GND (legacy, internally tied to VG5/17) / Mollom GND (planned)
- Spare red + spare black: dead-ended in cabinet

The X8 pins for cable "7" will be added as the user traces them.

---

## Fagor Module Electrical Specs (from manual ch17)

| Spec | Value |
|---|---|
| Digital input nominal voltage | +24 VDC (range 18–30 V) |
| Digital input "high" threshold (VIH) | ≥ +18 VDC |
| Digital input "low" threshold (VIL) | < +5 VDC or not connected |
| Digital input typical consumption | 5 mA (max 7 mA) |
| Digital output nominal supply | +24 VDC |
| Digital output Vout | Supply − 3 V (so ~21 V at the load) |
| **Digital output max current per output** | **100 mA** |
| Output protection | Optocoupler galvanic isolation; short-circuit protection; external recovery diodes recommended for inductive loads |
| Analog axis/spindle output | ±10 V, 16-bit, min 10 kΩ load impedance, shielded cable required |

I/O conventions:
- Outputs are **sourcing** (PNP): they supply +24 V when active. Loads connect between output and 0 V.
- Inputs are designed for **sourcing sensors** (PNP): +24 V at the input registers as logic 1; common is 0 V.

---

## OEM PLC Reference (NOT verified — use to plan verification, never as a trace)

The OEM's `PLC_PRG.PIM` file declares the intended pin assignments via `DEF` statements. The comments include the OEM wire color and a terminal-block reference. **These are the OEM's documented intent. The actual cabinet wiring may differ.** Use this table as a starting point for verification, never as evidence that a pin is actually wired a certain way.

### X10 (PLC reference)

| Pin | PLC name | OEM-intended function | OEM wire color (per PLC comment) |
|---|---|---|---|
| 1 | 24 VOLTS | Internal supply rail | WHT 20 |
| 2 | `/EMEROUT O1` | Emergency output (drive enable) | BLK 20/2 |
| 3 | `SPIN-CW O3` | Spindle CW command | BRN 8/0 |
| 4 | `SPIN-CCW O5` | Spindle CCW command | RED |
| 5 | `LATCH1 O7` | (unlabeled OEM function) | ORN |
| 6 | `OZONE1 O9` | OEM zone output 1 | BRN 8/19 |
| 7 | `OZONE2 O11` | OEM zone output 2 | RED |
| 8 | `OZONE3 O13` | OEM zone output 3 | ORN |
| 9 | `OZONE4 O15` | OEM zone output 4 | YEL |
| 10 | `OZONE5 O17` | OEM zone output 5 | GRN |
| 11 | `OZONE6 O19` | OEM zone output 6 | BLU |
| 13 | `OZONE8 O23` | OEM zone output 8 | BLK |
| 14 | `IPININ I33` (input) | (unlabeled OEM input) | BRN 8/20 |
| 15 | `IRACKIN I35` (input) | Rack-in position sensor | RED |
| 16 | `IRACKOUT I37` (input) | Rack-out position sensor | ORN |
| 17 | `TOOLLEN I39` (input) | Toolsetter probe contact | YEL |
| 18, 19 | 0 VOLTS | Internal 0 V rails | GRN 20 |
| 20 | 24 VOLTS | Internal supply rail | WHT 20 |
| 21 | `BITCOOL O2` | Bit cool output (M95/M96) | BRN 20/2 |
| 22 | `ROLLERS O4` | Rollers up/down (M63/M64) | BLK/BRN/WHT |
| 23 | `ENTERLGT O6` | Enter light | WHT/RED/- |
| 24 | `ARCLGT O8` | Arc light | BLU/WHT/BLK |
| 25 | `OCARCW O10` | Carousel CW | RED 2/71 |
| 26 | `OCARCCW O12` | Carousel CCW | BLK 2/71 |
| 27 | `TOOLHT O14` | Toolsetter probe deploy | BRN 8/8 |
| 28 | `ORACK O16` | Rack actuator | RED |
| 29 | `OCLAMP O18` | Clamp solenoid | ORN |
| 30 | `OBLOWOFF O20` | Air purge / chip blow-off | YEL |
| 31 | `ODRAW O22` | Drawbar release | GRN |
| 32 | `ODUST O24` | Dust hood | BLU |
| 33 | `IDUST I34` (input) | Dust feedback | WHT |
| 34 | `ITOOLIN I36` (input) | Tool present in spindle | BRN 8/10 |
| 35 | `IDRAWUP I38` (input) | Drawbar up position | RED |
| 36 | `IDRAWDN I40` (input) | Drawbar down position | ORN |

### X9 (PLC reference)

| Pin | PLC name | OEM-intended function | OEM wire color (per PLC comment) |
|---|---|---|---|
| 2 | `/EMERINP I1` | E-stop input | BLK 20/1 |
| 3 | `PENX I3` | Pendant X | ORN/-/- |
| 4 | `PENY I5` | Pendant Y | ORN/GRN/- |
| 5 | `IZONE1 I7` | OEM zone input 1 | ORN/BRN/WHT |
| 6 | `IZONE2 I9` | OEM zone input 2 | GRN/WHT/- |
| 7 | `IZONE3 I11` | OEM zone input 3 | GRN/WHT/BLK |
| 8 | `IZONE4 I13` | OEM zone input 4 | BLK/BRN/GRN |
| 9 | `IZONE5 I15` | OEM zone input 5 | BLU/BLK/- |
| 10 | `IZONE6 I17` | OEM zone input 6 | WHT/-/- |
| 11 | `IZONE7 I19` | OEM zone input 7 | WHT/BLK/- |
| 12 | `IZONE8 I21` | OEM zone input 8 | WHT/RED/BLK |
| 13 | `PINSSW I23` | Pin switch | WHT/RED/GRN |
| 14 | `ROLLSW I25` | Rollers switch | BLK |
| 15 | `REMSTRT I27` | Remote start | GRN 20/1 (BLU/-/-) |
| 16 | `/REMSTOP I29` | Remote stop | RED 20/1 (GRN/-/-) |
| 17 | `ICARCNT I31` | Carousel count | BLK 2/8 (RED NC) |
| 18, 19 | 0 VOLTS | Internal 0 V rails | GRN 20 |
| 20 | NOT USED | — | — |
| 21 | `YFLS I6` | Y forward limit | RED 20/2 |
| 22 | `YRLS I8` | Y reverse limit | RED 20/3 |
| 23 | `XRLS I4` | X reverse limit | ORN 8/9 |
| 24 | `XFLS I2` | X forward limit | BRN |
| 25 | `ZRLS I10` | Z reverse limit | YEL |
| 26 | `ZFLS I12` | Z forward limit | RED |
| 27 | `ISAWUP I14` | Saw up | GRN |
| 28 | `ISAWDN I16` | Saw down | WHT |
| 29 | `ISAW0 I20` | Saw 0° | BLU |
| 30 | `ISAW90 I18` | Saw 90° | BLK |
| 31 | `WFLS I22` | W forward limit | BLK 20/3 |
| 32 | (`TOOLLEN I24` commented out) | Old toolsetter location | (BLK 20/4) |
| 33 | `IROTATE I26` | Rotate | BLU 20 |
| 34 | `/AIRFLT I28` | Air pressure fault | RED 20/2 |
| 35 | `SPINFLT I30` | Spindle fault | YEL 20 |
| 36 | `OVERTEMP I32` | Spindle overheat | BLK 2/9 (RED +24) |

### X8 (PLC reference)

The AXES-module general machine parameters (P000–P007 in the relevant Fagor parameter file — NOT the PIM, and NOT the MPG/handwheel parameters) assign physical X8 analog channels to logical axes:

| Pair # | Param | OEM-intended function |
|---|---|---|
| 1 | P000 = 1 | X axis drive analog ±10 V command |
| 2 | P001 = 2 | Y axis drive analog ±10 V command |
| 3 | P002 = 3 | Z axis drive analog ±10 V command |
| 4 | P003 = 6 | W axis drive analog ±10 V command |
| 5 | (no param) | Spare — pre-wired for future 5th axis |
| 6 | (no param) | Spare — pre-wired for future 6th axis |
| 7 | P007 = 10 | Main spindle ±10 V speed command |
| 8 | (no param) | Hardware-supported but unwired |
