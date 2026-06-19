# Pendant — Handwheel + Buttons

The pendant is a handheld unit containing a manual pulse generator (MPG / handwheel) plus buttons. Connects to the Fagor AXES module **X6** connector via a multi-conductor shielded cable.

## Hardware

### Axis Selector Button

A small button on the pendant labeled as the "axis selector". Has **5 terminals**:

| Terminal | Meaning | Connected to |
|---|---|---|
| `+` | LED illumination supply, positive | **unwired** |
| `−` | LED illumination supply, negative / common | **unwired** |
| `C` | Contact common | RED wire in **ORN cable** |
| `NO` | Normally open contact | **unwired** |
| `NC` | Normally closed contact | MPG/B2 → BLK wire in **Yel cable** |

Only **C and NC are wired**; the NO contact and the LED illumination (+, −) are unused. The button is acting purely as a momentary NC contact between Yel/BLK (via MPG/B2) and ORN/RED.

Note: the pendant has **5 cables** entering it, for a total of **10 conductors**:

| Cable | Conductors | Notes |
|---|---|---|
| Yel (yellow) | RED, BLK | Signal cable |
| ORN (orange) | RED, BLK | Signal cable; BLK is dead-ended (taped) at pendant — unused |
| Red | RED, BLK | Signal cable |
| Brn (brown) | RED, BLK | Signal cable |
| Grey (generic 2-conductor) | (2 conductors) | **E-stop cable** — goes to the pendant e-stop NC contacts (other ends at `*3`/`*4` in the cabinet) |

Of the 10 conductors: 8 in the 4 colored signal cables go to MPG/axis-selector terminals (1 taped, 7 actively wired); 2 in the grey cable run to the e-stop.

### MPG (Handwheel)

- **Type**: OLM 01 2DZ1 11A
- Output: TBD (datasheet not on hand)
- Supply voltage: TBD

**Terminal layout** (8 screw terminals on the MPG body):
- Arranged in **2 rows × 4 columns** → 8 terminals total: `A1, A2, A3, A4, B1, B2, B3, B4`.
- **Row A** = the row closer to the model-info sticker on the MPG body.
- **Row B** = the row farther from the sticker.

Pin-function assignment (which terminal carries which signal) is TBD — to be identified during the X6 trace.

#### MPG terminal traces (in progress)

| MPG terminal | Connected to (internal) | Cable conductor | Notes |
|---|---|---|---|
| **A1** | — | **unwired** | — |
| **A2** | TBD | BLK wire in **Brn cable** | — |
| **A3** | TBD | BLK wire in **Red cable** | — |
| **A4** | — | **unwired** | — |
| **B1** | TBD | RED wire in **Yel cable** | — |
| **B2** | Axis selector button **NC** | BLK wire in **Yel cable** | The axis selector's NC contact uses MPG/B2 as a junction point — the BLK conductor of the yellow pendant cable then carries this signal onward toward X6 / cabinet. |
| **B3** | TBD | RED wire in **Brn cable** | — |
| **B4** | TBD | RED wire in **Red cable** | — |

### Pendant Body

- Steel construction. The body is **electrically tied to the cable shield**.
- The shield is bonded to ground **at the controller end only** (single-point grounding via the X6 connector shell / pin to chassis ground).
- The pendant body therefore acts as an **extension of the shield surface** — it provides no independent ground bond at the field end. Effectively "more shield conductor" rather than a true second-side ground.

## Cable

- Routes from the pendant to the cabinet, terminating at **X6** on the Fagor AXES module.
- **7 of 8 conductors used + shield** (one conductor unused).
- Pin-level signal mapping at X6: **NOT YET TRACED**. Planned tracing target.

## Pendant E-Stop

The pendant also carries an e-stop button (NC contact, fail-safe, part of the 3-stage series e-stop chain). Its two NC-contact leads land on cabinet screw terminals:

- One side → `*3`
- Other side → `*4`

Polarity not important since this is a daisy-chain link. The chain runs: `*1`→`*2` (on-screen e-stop) → `*2`/`*3` jumper → `*3`/`*4` (pendant e-stop) → `*4`/`*5` jumper → `*5`/`*6` (LHS cabinet e-stop) → out to Fagor X9/pin 2, R2C2, R5A2.

The e-stop conductors are NOT part of the X6 cable's 7 used signal conductors (which carry handwheel + buttons). Whether the e-stop runs in a physically separate cable or in additional conductors within the same outer jacket is not yet recorded — to confirm during X6 tracing.

## X6 Connector Pin Mapping

Mapping each X6 pin (cabinet end) to the conductor it carries and the pendant-side destination.

| X6 pin | Cable / conductor | Pendant-side destination |
|---|---|---|
| 1 | RED wire in **Brn cable** | MPG/B3 |
| 2 | BLK wire in **Brn cable** | MPG/A2 |
| 3 | RED wire in **Red cable** | MPG/B4 |
| 4 | BLK wire in **Red cable** | MPG/A3 |
| 5 | RED wire in **ORN cable** | Axis selector **C** |
| 6 | — | (unused) |
| 7 | RED wire in **Yel cable** | MPG/B1 |
| 8 | BLK wire in **Yel cable** | MPG/B2 (also = axis selector NC) |
| 9–14 | — | (unused) |
| 15 | Shield | bonded to pendant body via cable shield |
| 16–26 (if 26-pin) | — | (unused) |

**7 active signal pins + 1 shield pin used.** The ORN cable's BLK conductor (which was dead-ended at the pendant end) does NOT land on any X6 pin — it's disconnected at the cabinet end too.

## What We Know From PIM

PIM does NOT cover X6 pin-level signals. PIM only covers PLC I/O on X9/X10.

PIM does reference two pendant-related digital inputs, but they appear at **X9** pins, not X6:
- `PENX I3` at X9/pin 3 — pendant X axis selector
- `PENY I5` at X9/pin 4 — pendant Y axis selector

Whether these signals route through X6 first (and are internally cross-connected to X9 inputs by the AXES module) or arrive at X9 via separate cabinet wires is **unknown**.

## Plan for X6 Tracing

Expected breakdown of the 7 used conductors + shield:
- 4 lines: differential handwheel encoder (A, /A, B, /B)
- 2 lines: +5 V supply and 0 V return
- 1 line: axis selector switch position OR button common
- (1 unused conductor)
- Plus shield

To map each conductor:
1. Identify shield (continuity to pendant body).
2. Spin the handwheel and probe for toggling lines → identifies A/B encoder pair (and probably differential partners by signal inversion).
3. Probe for +5 V and 0 V rails (continuity to known supply rails inside the cabinet, or measured DC voltage from X6 with everything powered).
4. Press each pendant button / move the axis selector and watch which conductor changes state → identifies button signals.

## LinuxCNC Migration Notes

When migrating to LinuxCNC + Mesa (7I97T + 7I85S + 7I84U):
- Handwheel encoder differential lines → one of the encoder inputs on 7I97T or 7I85S.
- Pendant button digital signals → Mesa digital inputs (7I97T native or 7I84U via sserial).
- Identification is easiest by landing all conductors first, then pressing buttons / spinning the wheel and watching HAL pins live.

## Open Items

- [ ] Physically trace each of the 7 used X6 conductors to identify function.
- [ ] Confirm MPG PPR rating (100 vs other).
- [ ] Confirm supply voltage (5 V vs 12 V).
- [ ] Identify which conductor is unused.
- [ ] Map pendant buttons to specific cable conductors.
