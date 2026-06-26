# Field Devices

Sensors, switches, solenoids, motors, and other components located **outside** the main cabinet that connect to the cabinet via a single cable. Each device gets a section here so that every cabinet-side terminal entry has a matching field-side entry — full two-entry accounting at both ends of every wire.

**Format**: each device gets a section with
- **Location** — where on the machine it lives.
- **Function** — what it does electrically.
- **Cable** — the cable name (matches the label on the NM conduit or jacket).
- **Wires** — each conductor in the cable, with its color, the cabinet-side terminal it lands on, and the role of that wire.
- **Notes** — anything else.

When a new cabinet-side trace lands on a field device, add (or update) the device's section here AND make sure the cabinet-side file points back.

---

## Spindle Overheat Thermostat

- **Location**: on the spindle motor (field-mounted).
- **Function**: normally-open thermostat — closes when spindle overheats, passing +24 V through to the CNC overheat input.
- **Cable**: cable "9".
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | White | `*71` | +24 V supply to thermostat |
  | Red | `*39` (then BLK → Fagor X9/pin 36, OVERTEMP I32) | Signal back to CNC |
- **Notes**: ✓ both wires verified. PIM comment "BLK 2/9 (RED +24)" matches in cable label ("9") but swaps colors vs the actual cable.

---

## Air Pressure Sensor

- **Location**: pneumatic supply line (field-mounted).
- **Function**: monitors compressed-air supply pressure; signals CNC if pressure drops.
- **Cable**: cable "00".
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | White | `*71` | +24 V supply |
  | Red | `*37` (then → Fagor X9/pin 34, /AIRFLT I28) | Signal back to CNC |
- **Notes**: ✓ verified. PIM-named `/AIRFLT I28`.

---

## Toolsetter Solenoid Valve (NVZ3120) / Bimba Probe Deploy

- **Location**: tool-setter pneumatic actuator (field-mounted on machine).
- **Function**: air solenoid that retracts/extends the Bimba tool-probe arm. Driven by Fagor X10/pin 27 (`TOOLHT O14`).
- **Cable**: cable "00-2".
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Brown | `*61` (then → Fagor X10/pin 27, TOOLHT O14) | Drive signal from CNC |
  | (other wire) | TBD | Solenoid return / common |
- **Notes**: ✓ brown drive wire verified. Solenoid return wire not yet traced. Which physical state (extended or retracted) is "energized" vs "de-energized" still needs physical verification.

---

## Tool Probe (Bimba probe contact)

- **Location**: spindle/tool-setting area (field-mounted). The probe surface is mounted on the machine; the tool (in the spindle) is the other electrical contact (via chassis ground through the spindle).
- **Function**: probe-contact switch — signals CNC when the tool tip touches the probe surface during a tool-length measurement cycle. Different from the toolsetter solenoid (which deploys/retracts the probe arm); this is the contact-detection signal.
- **Cable**: cable "04".
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Black | `*84` (then → R10C1; R10 is an interposing relay; R10A2 → `*54` → Fagor X10/pin 17, `TOOLLEN I39`) | Probe surface electrical lead. Sits at +24 V idle (sourced via R10's coil from the +24 V bus on R10C2). On touch, the spindle's chassis ground completes the circuit; current flows through R10's coil; R10 energizes; R10A2 (NO) closes onto R10D2 (+24 V) → +24 V on white wire → `*54` → Fagor X10/pin 17 reads "touched." |
- **Notes**: ✓ verified end-to-end. The probe wiring is intentionally minimal (just one BLK wire from probe to `*84`) — the chassis ground is provided locally by the tool/spindle/chassis bond at the machine, NOT through cable 04. R10 acts as both signal regenerator and galvanic isolator: the Fagor input never sees the probe's actual voltage, only a clean +24 V from R10's NO contact. See `relays.md` R10 entry for full circuit. Fail-safe: a broken cable 04 → no current path → R10 idle → Fagor reads "not touched" (no false trigger).

---

## Drawbar UP Sensor

- **Location**: spindle nose drawbar area (field-mounted inductive proximity sensor).
- **Function**: detects when drawbar is in the UP (clamped) position.
- **Cable**: cable "30-2" for signal; shares +24 V from cable "30" with drawbar DOWN sensor.
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Red (cable 30-2) | `*69` (then WHT → Fagor X10/pin 35, IDRAWUP I38) | Signal back to CNC |
  | Red (cable 30) | `*76` | +24 V supply (shared with drawbar DOWN sensor) |
- **Notes**: ✓ verified end-to-end. Common +24 V supply for both drawbar sensors is on cable 30 red wire → `*76`.

---

## Drawbar DOWN Sensor

- **Location**: spindle nose drawbar area (field-mounted inductive proximity sensor).
- **Function**: detects when drawbar is in the DOWN (released) position.
- **Cable**: cable "30-2" (shares with drawbar UP).
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Brown (cable 30-2) | `*70` (then BLK → Fagor X10/pin 36, IDRAWDN I40) | Signal back to CNC |
  | (shared +24 V on cable 30 red → `*76`) | `*76` | +24 V supply |
- **Notes**: ✓ verified end-to-end. Cable 30 + 30-2 is a shielded bundle for both drawbar sensors.

---

## Cable 92 — Tool-Change Pneumatic Suite + Chip Blow-off

Cable 92 is a multi-conductor cable that carries the **full pneumatic-actuator control suite** for the tool-change cycle plus the chip blow-off output for cutting. Five active wires + shield.

- **Location**: field-mounted solenoid manifold (external to cabinet), near the spindle/tool-change area.
- **Cable**: cable "92" (multi-conductor with shield).

### Wires

| Field-side color | Cabinet-side terminal | Cabinet → Fagor path | Fagor pin | PIM symbol | Function |
|---|---|---|---|---|---|
| Brown | `*90` | `*90` → R9A2 (NO) → R9 coil driven by `*55` (yellow) → `*55` (brown) → X10/pin 21 | X10/pin 21 | `BITCOOL O2` | **Chip blow-off (cutting)** — used continuously or M-coded during cutting. For wood: air-only, NOT coolant. |
| Orange | `*63` | `*63` (brown) → X10/pin 29 (direct) | X10/pin 29 | `OCLAMP O18` | **Drawbar IN (clamp tool)** — energize to clamp the tool in the spindle taper. |
| Yellow | `*64` | `*64` (red) → X10/pin 30 (direct) | X10/pin 30 | `OBLOWOFF O20` | **Spindle taper air purge** — blows out the spindle taper during tool change to clear chips/dust before clamping the next tool. |
| Green | `*65` | `*65` (orange) → X10/pin 31 (direct) | X10/pin 31 | `ODRAW O22` | **Drawbar OUT (release tool)** — energize to release the tool from the spindle taper. |
| White | `*71` (+24 V bus) | bonded to bus | — | — | +24 V common (sensor/solenoid common supply for the field-side devices). |
| Thick green | shield (cabinet side) | grounded at cabinet end | — | — | Cable shield — single-point grounded at cabinet (not a signal). |

### Field-side continuation — BIGGREEN cable in top junction box

Cable 92 terminates in the **top junction box** at the field end. There, the signal wires are spliced to corresponding wires in a separate cable called **BIGGREEN**, which then runs to the **solenoid bank** (verified).

| Cable 92 wire | Spliced to BIGGREEN wire | Destination | PIM symbol (cabinet side) |
|---|---|---|---|
| Green (`*65`) | Red/blue (striped) | Drawbar release solenoid | `ODRAW O22` |
| Orange (`*63`) | Pink | Drawbar clamp solenoid | `OCLAMP O18` |
| Yellow (`*64`) | Yellow | Spindle taper air-purge solenoid | `OBLOWOFF O20` |

(BIGGREEN's mapping for the BRN BITCOOL wire and the WHT +24 V common not yet traced through the top junction box.)

### Notes

- ✓ cabinet → top junction box splice mapping recorded for 3 of 4 active signal wires; BIGGREEN goes from the top junction box to the solenoid bank (verified).
- Only the BITCOOL (chip blow-off) line uses an interposing relay (R9). The three tool-change outputs (OCLAMP, OBLOWOFF, ODRAW) drive their solenoid coils **directly from Fagor outputs**. Fagor outputs are rated 100 mA max — should verify each solenoid coil draws ≤ 100 mA at +24 V.
- The "drawbar in / drawbar out" pair (OCLAMP + ODRAW) implies a **two-solenoid drawbar mechanism**: one to clamp, one to release. Position feedback is from the drawbar UP/DOWN sensors at `*69` (X10/pin 35, IDRAWUP) and `*70` (X10/pin 36, IDRAWDN) — those tell the CNC when the drawbar has reached the commanded position.
- PIM colors are quite consistent on the **field-side wire** for this cable: BITCOOL=BRN matches, OCLAMP=ORN matches, OBLOWOFF=YEL matches, ODRAW=GRN matches. All four are 4-for-4 on the cable 92 side. Wire-color changes happen at each `*N` splice.
- For wood machining, BITCOOL is **air-only chip blow-off** (no liquid coolant). M95/M96 toggle it. OBLOWOFF is a separate output used during tool change (not during cutting).

---

## Rack Position Sensor (cable 92-2)

- **Location**: field-mounted at the tool rack/turret, near the spindle/tool-change area.
- **Function**: detects rack position (per user identification). PIM symbol on the Fagor side is `ITOOLIN I36` ("Tool present in spindle") but the OEM repurposed it for rack position on this machine.
- **Cable**: cable "92-2" — 4-wire shielded.
- **Wires**:
  | Color (cable 92-2) | Cabinet-side terminal | Top-junction-box splice (BIGGREEN) | Role |
  |---|---|---|---|
  | Red | `*68` (then light blue → Fagor X10/pin 34) | BIGGREEN grey | Signal output from sensor (sees +24 V when sensor active) |
  | White | `*74` (+24 V bus) | BIGGREEN purple | +24 V supply to sensor |
  | Black | (cabinet end TBD — likely chassis ground) | BIGGREEN green | Sensor ground/return |
  | Green (drain) | (cabinet end TBD — shield/ground at cabinet) | — | Cable shield |
- **Notes**: ✓ verified from cabinet to top junction box; sensor itself not yet inspected. The BLK ground wire's cabinet-end termination not explicitly recorded yet (probably tied to chassis ground bus at the cabinet entry). The cable layout (+24 V supply, signal output, ground, shield) matches a sourcing-PNP proximity-style sensor.

---

## E-Stop — On-Screen (Fagor pendant front panel)

- **Location**: Fagor 8055 on-screen / pendant front panel.
- **Function**: first link in the 3-stage series e-stop chain.
- **Cable**: integrated into the Fagor pendant cable (no field cable).
- **Wires**:
  | Cabinet-side terminal | Role |
  |---|---|
  | `*1` | E-stop chain input from +24 V |
  | `*2` | E-stop chain output → pendant button |
- **Notes**: see `screw_terminals.md` `*1`/`*2` for full chain wiring.

---

## E-Stop — Pendant

- **Location**: handheld pendant.
- **Function**: second link in the 3-stage series e-stop chain.
- **Cable**: pendant cable (along with MPG, jog buttons, etc.).
- **Wires**:
  | Cabinet-side terminal | Role |
  |---|---|
  | `*3` | E-stop chain in |
  | `*4` | E-stop chain out |
- **Notes**: see `screw_terminals.md`.

---

## E-Stop — LHS (left-hand-side cabinet button)

- **Location**: left-hand side of cabinet.
- **Function**: third (final) link in the 3-stage series e-stop chain.
- **Cable**: short cabinet harness.
- **Wires**:
  | Cabinet-side terminal | Role |
  |---|---|
  | `*5` | E-stop chain in |
  | `*6` | E-stop chain out → drives Fagor X9/pin 2 (/EMERINP I1), R2C2, R5A2 |
- **Notes**: see `screw_terminals.md` `*5`/`*6` and `relays.md` R2/R5.

---

## Limit Switches

The Fagor has limit switches on multiple axes. PIM names them XFLS/XRLS (X axis fwd/rev), YFLS/YRLS (Y), ZFLS/ZRLS (Z), WFLS (W fwd only). LIMIT+/− switches per axis are mounted adjacent so inertia can trip both.

### X+ / X− Limit Switches and W+ Limit Switch (cable "13" — gantry limits)

- **Location**: X-axis travel ends and W-axis forward travel (gantry).
- **Cable**: cable "13" (3-wire gantry limit bundle).
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Red | `*24` | "Back" contact (back end of gantry travel). NC, fail-safe. Right-side trace TBD — PIM hypothesis: continues to Fagor X9/pin 23 (`XRLS I4`), possibly also a W-axis reverse-limit pin. |
  | Black | `*25` | "Front" contact (front end of gantry travel). NC, fail-safe. Right-side trace TBD — PIM hypothesis: continues to Fagor X9/pin 24 (`XFLS I2`) and X9/pin 31 (`WFLS I22`). |
  | COM | `*73` | +24 V supply (shared with cable 23 COM on the same `*73` terminal) |
- **Notes**: cabinet-side landings traced. Field-side switch positions and Fagor-pin destinations not yet verified. X− limit is wired into the e-stop chain (per `project_machine_limit_switches.md` memory).

### Y+ / Y− Limit Switches (cable "23")

- **Location**: Y-axis travel ends.
- **Cable**: cable "23" (3-wire).
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Red | `*26` | "Left" contact. NC, fail-safe. Right-side trace TBD — PIM hypothesis: either X9/pin 21 (`YFLS I6`) or X9/pin 22 (`YRLS I8`). |
  | Black | `*27` | "Right" contact. NC, fail-safe. Right-side trace TBD — PIM hypothesis: the other of YFLS/YRLS not used at `*26`. |
  | COM | `*73` | +24 V supply (shared with cable 13 COM on `*73`) |
- **Notes**: cabinet-side landings traced. Field-side switch positions and Fagor-pin destinations not yet verified. Y limits likely in e-stop chain by symmetry with X (not yet verified).

### Z+ / Z− Limit Switches (cable "33")

- **Location**: Z-axis travel ends.
- **Cable**: cable "33" (3-wire).
- **Wires**:
  | Color | Cabinet-side terminal | Role |
  |---|---|---|
  | Red | `*28` | Z **bottom** limit (trips at lower end of Z travel). NC, fail-safe. Corrected 2026-06-24 (hardware test `input-09`); was labelled "top". Right side → X9/pin 25. |
  | Black | `*29` | Z **top** limit (trips at upper end of Z travel). NC, fail-safe. Corrected 2026-06-24 (hardware test `input-10`); was labelled "bottom". Right side → X9/pin 26. |
  | COM | `*72` | +24 V supply |
- **Notes**: cabinet-side landings traced. Field-side switch positions and Fagor-pin destinations not yet verified. Z limits are PLC-only (NOT in e-stop chain — when Z trips, only the Z drive cuts, axis is recoverable). Per `project_machine_limit_switches.md` memory.

---

## Spindle Use Counter (Hour Meter)

- **Location**: cabinet-mounted (likely on the cabinet door or operator panel).
- **Function**: counts accumulated spindle-on time — receives +24 V whenever the spindle is running (so it knows when to increment).
- **Wires**:
  | Cabinet-side connection | Role |
  |---|---|
  | R1A2 | +24 V input (high when spindle is running — R1 energized closes R1A2 onto R1D2 +24 V common) |
  | (return / 0 V — TBD) | Counter's return path |
- **Notes**: ✓ cabinet-side trace partial — R1A2 confirmed as the +24 V drive; counter's return wire / 0 V not yet recorded. R1 energizes whenever the VFD reports the spindle is running (via R1's coil drive from VG5/9, legacy; Mollom Y1, planned).

---

## Spindle Motor Cooling Fan

- **Location**: on the spindle motor (field-mounted).
- **Function**: cools the spindle motor body. Runs continuously whenever the cabinet 110 V AC bus is energized.
- **Wires**:
  | Cabinet-side connection | Role |
  |---|---|
  | 110 V AC line bus (`*A`-`*F`, specific terminal TBD) | Hot |
  | AC neutral bus (`*77`-`*79`, specific terminal TBD) | Neutral |
- **Notes**: ✓ verified as directly wired to mains (110 V hot + neutral buses, no contactor/relay). Distinct from the case fan (same wiring scheme — also directly on the buses). Specific bus terminal landings on each end not yet identified.

---

## Grease Pump

- **Location**: behind the cabinet (field-mounted lubrication pump).
- **Function**: periodic way-oil pump, driven by R1.
- **Cable**: AC power leads.
- **Wires**:
  | Cabinet-side terminal | Role |
  |---|---|
  | R1A1 | Hot — AC supply to pump (switched by R1) |
  | `*77` | Neutral return |
- **Notes**: see `relays.md` R1 and `screw_terminals.md` `*77`.

---

## To Be Documented (placeholders)

Add new device sections as their traces are verified. Known field devices not yet fully documented:

- Pendant MPG (jog wheel) — analog encoder, separate cable.
- Pendant jog/feed buttons.
- Toolsetter probe contact / Bimba — see Tool Probe section above (in progress).
- ATC carousel CW/CCW motor and feedback — per PIM but no cable yet identified.
- Spindle motor encoder (if any).
- Any zone inputs (IZONE1–IZONE8) — PIM lists them but field assignment unknown.

---

## How to Use This File

When you verify a new wire that lands on a field device:
1. Update the cabinet-side entry in `screw_terminals.md` (or `relays.md`, etc.).
2. Update or add the matching device section here.
3. Both files should cross-reference each other.

When a device's full wiring is verified end-to-end, mark it ✓.
