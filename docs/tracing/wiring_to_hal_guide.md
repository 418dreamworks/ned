# From Wiring Docs to LinuxCNC HAL — Translation Guide

**For future Claude (and human collaborators).** This file explains how to take the verified wiring in `screw_terminals.md` / `relays.md` / `field_devices.md` / `fagor_8055_axes.md` and turn it into a LinuxCNC HAL/INI configuration on Mesa hardware.

The previous sessions exhaustively traced every wire in the cabinet. This guide tells you which of those wires becomes a HAL input, which becomes a HAL output, and which stay purely electrical (invisible to HAL).

---

## Mesa Hardware Target

The actual hardware configuration (not the alternatives previously considered):

### 7I97T + 7I85S + 7I84U (Ethernet route, ~$427)

- **7I97T** ($279) — Ethernet FPGA, analog servo focused. Main motion-control card.
  - 6× analog ±10 V outputs (axis velocity commands + spindle)
  - 6× encoder inputs (axis position feedback)
  - 16 isolated digital inputs
  - 6 isolated digital outputs (universal sourcing/sinking/push-pull)
  - 1 Smart Serial port (for 7I84U daisy-chain via RJ45)
  - 1 DB25 expansion port (for 7I85S daughter card)
- **7I85S** ($69) — Step/dir daughter card, plugs into 7I97T's DB25 expansion port.
  - 4 additional encoder inputs (total with 7I97T = 10 encoder inputs)
  - 8 differential outputs configurable as 4 step/dir pairs (for workholding rotaries)
  - 1 RS-422 serial interface
- **7I84U** ($79) — Digital I/O expansion via Smart Serial RJ45.
  - 32 isolated digital inputs (total with 7I97T = 48 digital inputs)
  - 16 isolated outputs (universal, 5–28 VDC, 500 mA per output) (total with 7I97T = 22 outputs)
  - Daisy-chainable for further expansion

**Total I/O surface**:
- Analog ±10 V outputs: 6 (covers 4 axes + spindle + 1 spare)
- Encoder inputs: 10 (covers X, Y, Z, W + handwheel + spindle encoder if added + spares)
- Step/dir channels: 4 (workholding rotaries)
- Digital inputs: 48
- Digital outputs: 22

---

## What Gets Migrated to HAL

HAL replaces the **Fagor 8055 X9/X10 I/O** entirely. Everything else in the cabinet (R0–R10 relay logic, e-stop chain, safety interlocks, grease pump, spindle fan rewire) is **purely electrical** and runs independent of HAL.

HAL needs to:
1. Read all sensor inputs that currently land on Fagor X9 / X10 inputs.
2. Drive all outputs that currently come from Fagor X10 outputs.
3. Read encoder feedback from servo drives (X1–X4 + handwheel X6).
4. Generate ±10 V axis command outputs (X8 pairs 1–4 + spindle pair 7).
5. Handle pendant button signals (X6, currently partially via PENX/PENY at X9/pin 3,4).

---

## Inputs — Fagor side → Mesa input pin → HAL signal

The cabinet wires that currently feed Fagor X9/X10 inputs get rerouted to Mesa input pins. The `*N` terminal stays on the same wire; only the Fagor end gets moved to Mesa.

**Note on Mesa pin placeholders below**: pins are shown as `7i97t.in.XX` for inputs and `7i97t.out.XX` for outputs as illustrative names. Actual HAL pin names depend on which board the wire physically lands on (7I97T native input/output OR 7I84U via sserial — full HAL names then look like `hm2_7i97t.0.7i84.0.0.input-XX`). The 7I97T card has 16 native inputs + 6 native outputs; 7I84U adds 32 inputs + 16 outputs via sserial. Distribution is a wiring-design decision.

### Reserved Pendant Block — 7I97T TB4 IN0–IN3 (4 native inputs)

Pendant-related digital signals are blocked off together on TB4 for tidy wiring (close to TB2 where the handwheel encoder lands). The handwheel's 0 V (TB2 pin 11) is the natural return for pendant button common.

| 7I97T TB4 pin | Mesa input | Signal | HAL signal | Status |
|---|---|---|---|---|
| 1 | IN0 | Pendant axis selector (X6 pin 5, ORN RED) | `pendant-axis-selector` | wired |
| 2 | IN1 | Reserved — future pendant button | TBD | reserved |
| 3 | IN COMMON 0,1 | tie to +V (matches IN COMMON 2,3) | — | — |
| 4 | IN2 | Reserved — future pendant button | TBD | reserved |
| 5 | IN3 | Reserved — future pendant button | TBD | reserved |
| 6 | IN COMMON 2,3 | tie to +V (same node as IN COMMON 0,1) | — | — |

Both IN COMMON terminals tied to the same +V so all 4 pendant signals share a common reference and behave consistently. Pendant cable currently has 1 spare conductor (ORN BLK, dead-ended at pendant per `pendant.md:26`) — enough for one more button without re-cabling. Beyond that, a new multi-conductor cable to the pendant is required.

**Consequence**: only 12 native 7I97T input slots remain (IN4–IN15) for the 15 cabinet signals listed below. 3 will need to relocate to 7I84U inputs. The illustrative `in.XX` numbering in the next table is preserved for HAL signal-name continuity, but the user picks which 3 signals physically land on 7I84U.

### From `fagor_8055_axes.md` X9 — Verified Traces

| Cabinet `*N` | Fagor X9 pin (was) | Mesa input (assign) | Suggested HAL signal | Function |
|---|---|---|---|---|
| `*6` | pin 2 (/EMERINP) | `7i97t.in.00` | `e-stop-released` | End of e-stop daisy chain. HIGH when all e-stops released. |
| `*24` | pin 21 | `7i97t.in.01` | `limit-x-back` | Gantry X back limit (NC, fail-safe). |
| `*25` | pin 22 | `7i97t.in.02` | `limit-x-front` | Gantry X front limit. |
| `*26` | pin 23 | `7i97t.in.03` | `limit-y-left` | Y-axis left limit. |
| `*27` | pin 24 | `7i97t.in.04` | `limit-y-right` | Y-axis right limit. |
| `*28` | pin 25 | `inmux.00.input-09` | `limit-z-bottom` | Z **bottom** limit (corrected 2026-06-24; was "top"). |
| `*29` | pin 26 | `inmux.00.input-10` | `limit-z-top` | Z **top** limit (corrected 2026-06-24; was "bottom" — TOP switch sits physically below BOTTOM switch). |
| `*36` | pin 33 (IROTATE) | `7i97t.in.07` | `spindle-running` | VFD running feedback (from R1A3). |
| `*37` | pin 34 (/AIRFLT) | `7i97t.in.08` | `air-pressure-ok` | Air pressure sensor; HIGH = OK. |
| `*38` | pin 35 (SPINFLT) | `7i97t.in.09` | `vfd-fault` | VFD fault contact (from VG5/18 or Mollom RY1 TC). |
| `*39` | pin 36 (OVERTEMP) | `7i97t.in.10` | `spindle-overtemp` | Spindle thermostat. |

### From `fagor_8055_axes.md` X10 — Verified Input Traces

| Cabinet `*N` | Fagor X10 pin (was) | Mesa input (assign) | Suggested HAL signal | Function |
|---|---|---|---|---|
| `*54` | pin 17 (TOOLLEN) | `7i97t.in.11` | `tool-probe-contact` | From R10's NO contact — tool touch via probe. |
| `*68` | pin 34 (ITOOLIN, repurposed) | `7i97t.in.12` | `rack-position` | Rack position sensor (cable 92-2). |
| `*69` | pin 35 (IDRAWUP) | `7i97t.in.13` | `drawbar-up` | Drawbar UP (clamped) position sensor. |
| `*70` | pin 36 (IDRAWDN) | `7i97t.in.14` | `drawbar-down` | Drawbar DOWN (released) position sensor. |

Mesa input pin assignments are illustrative — actual numbering depends on the chosen card and physical terminal layout.

---

## Outputs — Fagor side → Mesa output pin → HAL signal

| Cabinet `*N` | Fagor X10 pin (was) | Mesa output (assign) | Suggested HAL signal | Function |
|---|---|---|---|---|
| `*8` | pin 2 (/EMEROUT) | `7i97t.out.00` | `drive-enable` | Drive enable to R5's coil — gates the entire servo network. |
| `*40` | pin 3 (SPIN-CW) | `7i97t.out.01` | `spin-cw` | Drives R6 → VG5/1 or Mollom S1 (forward run). |
| `*41` | pin 4 (SPIN-CCW) | `7i97t.out.02` | `spin-ccw` | Drives R7 → VG5/2 or Mollom S2 (reverse run). |
| `*55` | pin 21 (BITCOOL) | `7i97t.out.03` | `chip-blowoff` | Drives R9 → external air blast solenoid (for wood machining; not coolant). |
| `*61` | pin 27 (TOOLHT) | `7i97t.out.04` | `toolsetter-deploy` | Drives NVZ3120 solenoid → Bimba probe extend. |
| `*63` | pin 29 (OCLAMP) | `7i97t.out.05` | `drawbar-clamp` | Drawbar IN (clamp tool) solenoid. |
| `*64` | pin 30 (OBLOWOFF) | `7i97t.out.06` | `spindle-taper-purge` | Air purge during tool change. |
| `*65` | pin 31 (ODRAW) | `7i97t.out.07` | `drawbar-release` | Drawbar OUT (release tool) solenoid. |
| `*42` | pin 5 (LATCH1, unused) | optionally `7i97t.out.08` | (TBD — see notes) | Currently drives R8 (unused). Could be repurposed for "spindle fan on" or "machine ready" indicator. |

---

## Analog Outputs (X8 → Mesa analog ±10 V)

X8 carries the ±10 V velocity command outputs. Currently routes from Fagor X8 to:
- Pair 7 → spindle VFD (cable "7", verified)
- Pairs 1–4 → servo drives for X/Y/Z/W (NOT physically traced — see todo)

| X8 Pair | Axis | Mesa analog output | HAL signal |
|---|---|---|---|
| 1 | X (gantry servo 1) | `7i97t.analogout.00` | `x-velocity-cmd` |
| 2 | Y (cross) | `7i97t.analogout.01` | `y-velocity-cmd` |
| 3 | Z | `7i97t.analogout.02` | `z-velocity-cmd` |
| 4 | W (gantry servo 2) | `7i97t.analogout.03` | `w-velocity-cmd` |
| 7 | Spindle (VFD AI2) | `7i97t.analogout.04` or 7I96S analog spindle | `spindle-velocity-cmd` |

**Open item**: physical destinations of pairs 1–4 not yet traced (Task #1). They go to the four SDSM Yaskawa servo drives, but the cabling between X8 and each specific drive is unmapped.

---

## Encoder Feedback (X1–X4 + X6 → Mesa encoder inputs)

Standard differential encoder pinout on all X1–X6 (per `project_axes_module_x1_x4_pinout.md` memory):

| Pin | Signal |
|---|---|
| 1, 2 | A, /A |
| 3, 4 | B, /B |
| 5, 6 | I0, /I0 |
| 9 | +5 V |
| 11 | 0 V |
| 15 | Shield ground |

Connector → axis mapping (user convention: 1=X, 2=Y, 3=Z, 4=W):

| Fagor connector | Axis | Mesa encoder input | HAL signal |
|---|---|---|---|
| X1 | X (gantry servo 1) | `7i97t.enc.00` | `x-pos-fb` |
| X2 | Y (cross) | `7i97t.enc.01` | `y-pos-fb` |
| X3 | Z | `7i97t.enc.02` | `z-pos-fb` |
| X4 | W (gantry servo 2) | `7i97t.enc.03` | `w-pos-fb` |
| X6 | Pendant handwheel + buttons | `7i97t.enc.04` on TB2 middle plug (handwheel) + TB4 IN0–IN3 block (buttons — see "Reserved Pendant Block" above) | `mpg.encoder`, `pendant-axis-selector` (IN0), three more TBD |

**X6 mapping resolved.** Fagor X6 pinout (`fagor_8055_installation_manual_en.txt:3170-3201`) is the standard 15-pin SUB-D HD encoder pinout: pin 1=A, 2=/A, 3=B, 4=/B, 5=I0 (repurposed as axis-selector C on this pendant), 6=/I0 (unused), 7=+5 V, 8=0 V (also axis-selector NC return), 15=shield. Combined with the X6→cable→MPG-terminal map in `pendant.md:86-99`, the X6 conductor functions are fully determined.

---

## What Stays Electrical (NOT in HAL)

The cabinet's internal safety/interlock electrical logic continues to function below HAL. HAL doesn't touch these — they just work:

| Component | Function | Why not in HAL |
|---|---|---|
| E-stop daisy chain (`*1`–`*6`) | Hardware safety chain through 3 e-stop buttons | Pure hardware — wire break = drop. HAL only sees the result on `*6` (e-stop-released input). |
| R0 (Analog Drive contactor) | Gates servo power | Driven by `*7` voltage — derived from R5 + e-stop chain. HAL never commands the contactor directly; it commands R5 via `*8` (drive-enable output), and R0 follows. |
| R3 + R4 (servo RUN/STOP gates) | Per-axis drive STOP signals | Driven by `*7` voltage. Open when drives may run, closed when they must stop. Hardware-only. |
| R5 (servo master gate) | Routes e-stop chain +24 V to `*7` when CNC drive-enable asserts | Coil driven by `*8` (drive-enable HAL output). When HAL outputs HIGH and e-stop chain intact, R5 picks up. |
| R2 (e-stop-driven VFD enable) | Gates the VFD external-fault path | Coil driven by e-stop chain. Pure hardware. |
| R6 (SPIN-CW interposer) | Translates Fagor SPIN-CW output into a VFD/Mollom contact closure | Coil driven by `*40` (HAL spin-cw output). HAL just outputs the command; R6 does the interposing. |
| R7 (SPIN-CCW interposer) | Same as R6 for reverse direction | Coil driven by `*41`. |
| R9 (BITCOOL interposer) | Translates BITCOOL output into 110 V solenoid drive | Coil driven by `*55`. HAL outputs the command; R9 does the gating. |
| R10 (TOOLLEN interposer) | Tool probe signal regenerator with galvanic isolation | Energizes mechanically when tool touches probe. HAL only sees the result on R10A2 → `*54` → tool-probe-contact input. |
| R1 (VFD running feedback) | Gates grease pump (R1A1) + hour meter (R1A2) + IROTATE feedback (R1A3) + spindle fan (planned R1A4) | Coil driven by VFD's running output. Pure hardware. HAL only sees the result on `*36` (spindle-running input). |
| Mollom Y1 → external relay module → blue wire | Polarity converter from Mollom sinking → cabinet sourcing | Hardware-only fix to keep R1 unchanged across VFD swaps. |

---

## Key Principles

1. **Use physical functions, not PIM symbol names.** The Fagor PIM PLC source has many leftover-template symbols (XFLS vs YFLS for axis mapping, BITCOOL for chip blow-off, ITOOLIN for rack position, etc.). These names do NOT describe what the wire physically does on this machine. Always go by the user's physical function names.
2. **Axis convention**: X1=X, X2=Y, X3=Z, X4=W. X is the gantry (W is tandem on the other side). Y is cross. Z is vertical. See `project_axis_naming_convention` memory.
3. **Don't second-guess electrical design.** R0–R10 and the e-stop chain are correct as-wired and shouldn't be moved into HAL.
4. **HAL outputs are commands; HAL inputs are feedback.** The cabinet's electrical layer translates commands into physical actions and converts physical states into feedback.
5. **Fail-safe behaviors are preserved**: limit switches are NC (open = fault), air pressure is NC (open = fault), tool probe interposer fails to "not touched", drawbar release fails to "no command".

---

## Open Items (Tasks)

- **Task #1**: Trace X8 pairs 1–4 (axis ±10 V commands) to servo drives — needed to know which Mesa analog output drives which physical drive.
- ~~**Task #2**: Trace X6 pendant pin-by-pin~~ — **DONE**. X6 standard pinout from Fagor installation manual + cable-conductor map from `pendant.md` give complete X6→7I97T mapping. Pendant block on TB4 IN0–IN3 reserved.

These should be completed before generating the HAL/INI files.

---

## When Generating HAL/INI

1. Start from this guide's signal map.
2. Cross-reference with the verified traces in `screw_terminals.md` (cabinet side) and `fagor_8055_axes.md` (Fagor side) for any new gaps.
3. Use `field_devices.md` for sensor/actuator specifications when sizing voltage thresholds, encoder counts, etc.
4. Use the limit-switch direction convention from the user (back/front/left/right/top/bottom) consistently across HAL and INI.
5. Reflect the `project_axis_naming_convention` memory in INI axis letters.
6. For the VFD swap (VG5 → Mollom), no HAL change needed if the polarity-translator external relay module is in place (R1 sees identical sourcing behavior in either case).
