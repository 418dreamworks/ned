# Cabinet Screw Terminals (`*N` series)

One section per screw terminal in the cabinet's main terminal block. Terminals 1–91 enumerated below.

**Each terminal has a LEFT side and a RIGHT side** — a wire on each. The format under each terminal records both, so it's visible at a glance whether one side has been traced and the other not. Use `(not yet examined)` when nothing is known about a side.

Convention: `*<n>` means cabinet screw terminal n. See `INDEX.md` for full conventions.

---

## Categories / Bus Ranges (Quick Reference)

| Range | Function |
|---|---|
| `*71` – `*76` | **+24 VDC bus** ("signal common" in local naming, despite being +24 V from the 24 V transformer) |
| `*77` – `*83` | **AC neutral / power common** (110 V neutral bus; expanded from *77–*79, 2026-07-06) |
| `*88` – `*90` | **5 V bus** (fed from the 5 V power brick) |
| `*A` – `*F` | **110 V AC line** bus |

---

## *1

- **Left side**: on-screen (front-panel) e-stop, one of its NC contact wires
- **Right side**: tied to the +24 V bus (`*71`-`*76`) — start of the e-stop daisy chain
- **Notes**: ✓ verified.

## *2

- **Left side**: on-screen (front-panel) e-stop, the other NC contact wire
- **Right side**: jumpered to `*3`
- **Notes**: ✓ verified. Jumper to `*3` continues the daisy chain.

## *3

- **Left side**: pendant e-stop, one NC contact wire
- **Right side**: jumpered to `*2`
- **Notes**: ✓ verified. Polarity not important (daisy-chain link).

## *4

- **Left side**: pendant e-stop, the other NC contact wire
- **Right side**: jumpered to `*5`
- **Notes**: ✓ verified. Jumper to `*5` continues the daisy chain.

## *5

- **Left side**: LHS (left-hand-side machine) e-stop, one NC contact wire (via cable 20)
- **Right side**: jumpered to `*4`
- **Notes**: ✓ verified. Polarity not important (daisy-chain link). The LHS e-stop's *other* NC-contact wire lands on `*39`, putting the spindle thermostat in series at the chain end (see `*39`; revert: `docs/revert_to_fagor.md`).

## *6

- **Left side**: fed by a **YELLOW jumper from `*67`** (the spindle thermostat's output). The thermostat is in series at the chain end: LHS e-stop → `*39` → thermostat NC → `*67` → yellow jumper → `*6`. `*6` carries chain +24 V when healthy; hot thermostat opens → `*6` drops (same as any e-stop). (revert: `docs/revert_to_fagor.md`.)
- **Right side**: **three wires land here**:
  - Wire #1: connected to Fagor X9/pin 2 (`/EMERINP`). Function: CNC firmware reads this input.
  - Wire #2: connected to R2C2 (R2's coil high side). Function: when chain is intact, R2C2 = +24 V → R2 energizes; chain break → R2C2 = 0 V → R2 drops out → VFD external-fault path closes → spindle stops.
  - Wire #3: connected to R5A2 (R5's NO contact, col 2). Function: this wire is the +24 V source for R5's col-2 NO contact. R5A2 and R5D2 become electrically connected through R5's internal contact when R5 is energized; that closure then puts `*6`'s +24 V onto R5D2 (= `*7`).
- **Notes**: ✓ verified. `*6` is the **safety-power source** for the entire drive enable system. Three parallel stop mechanisms from the same chain break: (1) CNC firmware sees /EMERINP go low and reacts; (2) R2 drops → VFD external fault asserts → spindle stops; (3) R5's NO contact loses its +24 V source → `*7` loses voltage → R0 (servo power contactor) drops AND R3/R4 (RUN/STOP gate relays) drop → servo drives lose power AND see STOP signal. Triply redundant safety design.

### E-stop chain topology summary

```
24 V ──→ *1 ──[on-screen e-stop NC]──→ *2 ═══jumper═══ *3 ──[pendant e-stop NC]──→ *4 ═══jumper═══ *5 ──[LHS e-stop NC]──→ *6
                                                                                                                            │
                                                                                                                            ├──→ Fagor X9/pin 2 (/EMERINP) ── CNC firmware reads
                                                                                                                            ├──→ R2C2 (R2 coil)            ── drops VFD/spindle when chain breaks
                                                                                                                            └──→ R5A2 (R5 NO contact)      ── supplies +24 V to *7 (via R5D2) when R5 energized
                                                                                                                                                              ── *7 then gates servo drive power (R0) AND RUN/STOP signals (R3, R4)
```

All three NC contacts must be closed simultaneously (no e-stop pressed) for 24 V to reach `*6`. Press any e-stop → its NC opens → chain breaks → all three branches lose +24 V at once → emergency on all three paths in parallel.

## *7

- **Left side**: → R0A2 (R0's signal/coil terminal)
- **Right side**: → R5D2 (R5's COM, col 2). Note: R3C2 and R4C2 also land on this same electrical node via direct wires from R5D2.
- **Notes**: ✓ verified. `*7` carries the **"drives may run" signal** for the servo system. **`*7` = +24 V is the NORMAL state** (drives can run); **`*7` losing voltage is the emergency state** (drives stop). The +24 V source comes from `*6` (e-stop chain). When R5 is energized, R5A2 and R5D2 become electrically connected through R5's internal NO contact — that closure puts `*6`'s +24 V (which is wired to R5A2) onto R5D2 (which is the same electrical node as `*7`). So when R5 is energized AND the e-stop chain is intact, `*7` = +24 V → R0 energizes (servo drive power flows) AND R3/R4 energize (their NC contacts open, breaking the drives' RUN/STOP "stop input" line, allowing drives to run). When `*7` loses voltage (either e-stop pressed at `*6` OR R5 drops out because CNC pulled /EMEROUT low): R0 opens its load contact (drives lose power) AND R3/R4 close their NC contacts (asserting STOP on the drives). Triply parallel stop assertion.

## *8

- **Left side**: brown wire → Fagor **X10/pin 2** (`/EMEROUT`) — the CNC's emergency output
- **Right side**: → R5C2 (R5's coil high side)
- **Notes**: ✓ verified. `*8` is the splice point that carries the CNC's "drives may run" signal to R5's coil. When the CNC's firmware determines all internal conditions are OK (/ALARM, CNCREADY, NOT LOPEN, NOT SPINFLT, OVERTEMP — per `PLC_PRG.PIM` line 177), /EMEROUT goes high (+24 V) → R5 energizes → R5A2 closes → e-stop chain's +24 V at `*6` is routed through R5 to `*7` → servo drives are enabled. CNC fault → /EMEROUT low → R5 drops → drives stop. Color note: OEM marked /EMEROUT as BLK at X10/pin 2 in the PLC source, but the field-harness segment to R5 is brown — consistent with the OEM-side vs field-side color convention seen at `*40`.

## *9

(not yet examined)

## *10

(not yet examined)

## *11

(not yet examined)

## *12

(not yet examined)

## *13

(not yet examined)

## *14

(not yet examined)

## *15

(not yet examined)

## *16

(not yet examined)

## *17

(not yet examined)

## *18

(not yet examined)

## *19

(not yet examined)

## *20

(not yet examined)

## *21

(not yet examined)

## *22

(not yet examined)

## *23

(not yet examined)

## *24

- **Left side**: RED wire from cable 13 → gantry limit switch (physical X axis, with W as tandem/slave), "back" contact. NC, fail-safe.
- **Right side**: BROWN wire → Fagor X9/pin 21.
- **Notes**: ✓ verified end-to-end. Gantry-X back limit. (PIM label at this pin is `YFLS I6` — not relevant; physical function is gantry-X.)

## *25

- **Left side**: BLK wire from cable 13 → gantry limit switch (physical X axis, with W as tandem/slave), "front" contact. NC, fail-safe.
- **Right side**: RED wire → Fagor X9/pin 22.
- **Notes**: ✓ verified end-to-end. Gantry-X front limit. (PIM label at this pin is `YRLS I8` — not relevant.)

## *26

- **Left side**: RED wire from cable 23 → physical Y-axis limit switch, "left" contact. NC, fail-safe.
- **Right side**: ORANGE wire → Fagor X9/pin 23.
- **Notes**: ✓ verified end-to-end. Y-axis "left" limit. (PIM label at this pin is `XRLS I4` — not relevant.)

## *27

- **Left side**: BLK wire from cable 23 → physical Y-axis limit switch, "right" contact. NC, fail-safe.
- **Right side**: YELLOW wire → Fagor X9/pin 24.
- **Notes**: ✓ verified end-to-end. Y-axis "right" limit. (PIM label at this pin is `XFLS I2` — not relevant.)

## *28

- **Left side**: RED wire from cable 33 → Z-axis **bottom** limit (trips at the lower end of Z travel). NC, fail-safe. (Switch body is mounted physically HIGH — see note under *29.)
- **Right side**: GREEN wire → Fagor X9/pin 25.
- **Notes**: ✓ verified end-to-end. Z-axis **bottom** limit (corrected 2026-06-24 by hardware test `input-09`; was mislabelled "top").

## *29

- **Left side**: BLK wire from cable 33 → Z-axis **top** limit (trips at the upper end of Z travel). NC, fail-safe. (Switch body is mounted physically LOW.)
- **Right side**: BLUE wire → Fagor X9/pin 26.
- **Notes**: ✓ verified end-to-end. Z-axis **top** limit (corrected 2026-06-24 by hardware test `input-10`; was mislabelled "bottom").

> **Why *28/*29 top/bottom were reversed:** the TOP-of-travel limit switch is mounted physically BELOW the BOTTOM-of-travel switch. The original trace labelled the two switches by physical height, which swapped their actual functions. Hardware test 2026-06-24 settled it: `*28`(input-09)=bottom, `*29`(input-10)=top.

## *30

(not yet examined)

## *31

(not yet examined)

## *32

(not yet examined)

## *33

(not yet examined)

## *34

(not yet examined)

## *35

(not yet examined)

## *36

- **Left side**: → R1A3 (R1's NO contact, col 3)
- **Right side**: → Fagor X9/pin 33 (`IROTATE I26`, "spindle rotating" feedback input)
- **Notes**: ✓ verified end-to-end. Full chain: VFD's running output → R1 coil energizes → R1A3 closes onto R1D3 (+24 V common) → +24 V appears on `*36` → Fagor X9/pin 33 → CNC reads "spindle is actually rotating." This is one of three parallel running-indications from R1 (the other two are R1A1 → grease pump and R1A2 → hour meter). The IROTATE input tells the CNC the spindle is **actually** rotating (vs. just commanded to rotate), used for M3/M4 completion, speed-reached interlocks, etc.

## *37

- **Left side**: RED wire from cable "00" → air pressure sensor's signal output
- **Right side**: LIGHT BLUE wire → Fagor X9/pin 34 (`/AIRFLT I28`, air pressure fault input)
- **Notes**: ✓ verified end-to-end. Air pressure sensor is wired as a 2-wire NC switch between `*71` (+24 V power) and `*37` (signal back to CNC). When pressure is OK, switch closed, +24 V flows to `*37`; when pressure low, switch opens, signal drops to 0 V — fail-safe.

## *38

- **Left side**: YELLOW wire → Mollom RY1 TC (as-built; VFD fault output) [Fagor: VG5/18]
- **Right side**: WHITE wire → Fagor X9/pin 35 (`SPINFLT I30`, spindle fault input)
- **Notes**: ✓ verified end-to-end. Carries +24 V when the VFD is in fault state. Full chain: VFD detects internal fault → VFD/18 contact closes → +24 V flows through yellow wire → `*38` → white wire → X9/pin 35 → CNC reads "spindle fault" and reacts (typically aborts the running program and asserts error). Wire-color change at `*38` (yellow VG5-side, white Fagor-side).

## *39

**FAGOR original wiring (preserved):**
- **Left side**: RED wire from cable "9" → spindle overheat thermostat (signal output). Partner wire in cable "9" is white → `*71` (+24 V), supplying the thermostat.
- **Right side**: BLACK wire → Fagor X9/pin 36 (PIM-named `OVERTEMP I32`, spindle overheat input).
- Fagor logic: thermostat **NC** (closed cool, opens on overheat — per user; had to be closed to run). **Cool → closed → +24 V from `*71` passes** red → `*39` → black → X9/pin 36 = "OK". **Hot/broken → opens → +24 V drops → over-temp** (loss-of-signal = fault, fail-safe). Here `*39` was a *standalone* signal into the Fagor OVERTEMP input, NOT part of the e-stop chain. *(Corrected 2026-07-09: earlier note wrongly said NO/closes-on-overheat.)* Sourcing-vs-sinking at X9/pin 36 = separate, not verified. PIM color "BLK 2/9 (RED +24)": cable label "9" matches; PIM colors unreliable.

**As-built 2026-07-23 (Mesa retrofit — `*39` re-purposed as an e-stop-chain junction):**
- The thermostat is moved into series at the **end of the e-stop chain**. `*39` now lands: (1) the **LHS e-stop's 2nd NC-contact wire** (moved here from `*6`), (2) one **thermostat lead**, (3) the **Mesa tap** (black wire → now 7I97 **IN14**, was X9/pin 36).
- Path: LHS e-stop → `*39` → thermostat NC → `*67` → yellow jumper → `*6`. The thermostat's white lead is **off `*71`** (it's now fed by the chain, not +24 V) — critical, else `*39` would read 24 V forever.
- **IN14 is now a diagnostic tap**, not a kill: `*39` = 24 V & `*6` = 0 V → **thermostat open (over-temp)**; `*39` = 0 V → an **e-stop** upstream; both 24 V → healthy. The actual kill is hardware (chain drops `*6` → R2 → Mollom S3 ext-fault → spindle coasts). Verified 2026-07-23: estop TRUE, tap TRUE (healthy).

## *40

- **Left side**: red wire labelled "05" → Fagor X10/pin 3
- **Right side**: brown wire → R6's coil high side (R6C2)
- **Notes**: ✓ verified. Splice point where the wire color/label convention changes between Fagor cabinet conventions (red "05") and field-harness conventions (brown).

## *41

- **Left side**: ORANGE wire → Fagor X10/pin 4 (`SPIN-CCW O5`)
- **Right side**: ORANGE wire → R7C2 (R7's coil high side)
- **Notes**: ✓ verified end-to-end. `*41` is the SPIN-CCW splice analog of `*40` (SPIN-CW splice for R6). When the Fagor asserts SPIN-CCW, +24 V at X10/pin 4 flows through orange wire → `*41` → orange wire → R7C2 → R7 energizes → R7A2 closes → reverse-run command reaches Mollom S2 (as-built) [Fagor: VG5/2]. Both wires at `*41` are orange — no wire-color change at this splice (unlike `*40` where red "05" changed to brown).

## *42

- **Left side**: YELLOW wire → Fagor X10/pin 5 (PIM `LATCH1 O7`, "unlabeled OEM function")
- **Right side**: ORANGE wire → R8C2 (R8's coil high side)
- **Notes**: ✓ verified end-to-end. Wire-color change at the splice (yellow Fagor-side, orange R8-side). R8 is unused on this machine (R8A2 → `*86` dead-ends in the field; no other R8 contacts wired to useful loads), so this Fagor output isn't driving anything in practice — leftover from the OEM template.

## *43

(not yet examined)

## *44

(not yet examined)

## *45

(not yet examined)

## *46

(not yet examined)

## *47

(not yet examined)

## *48

(not yet examined)

## *49

(not yet examined)

## *50

(not yet examined)

## *51

(not yet examined)

## *52

(not yet examined)

## *53

(not yet examined)

## *54

- **Left side**: WHITE wire → R10A2 (R10's NO contact col 2). Part of the tool-probe signal path — R10 energizes when probe is touched, R10A2 closes to R10D2 (+24 V common), so `*54` sees +24 V when probe is touched.
- **Right side**: → Fagor X10/pin 17 (PIM-named `TOOLLEN I39`, toolsetter probe contact input). PIM color YEL — actual wire color TBD/may differ.
- **Notes**: ✓ verified end-to-end. Full probe signal chain: tool touches probe → R10 energizes → R10A2 closes to R10D2 (+24 V common) → +24 V on white wire → `*54` → X10/pin 17 → Fagor input reads logic 1 = "tool length probe contacted."

## *55

- **Left side**: YELLOW wire → R9C2 (R9's coil high side). When asserted, drives R9's coil → R9A2 closes → +24 V is sourced out to `*85` → cable 92 BRN → external solenoid.
- **Right side**: BROWN wire → Fagor X10/pin 21 (PIM-named `BITCOOL O2`, "Bit cool output (M95/M96)"). PIM color BRN 20/2 matches the actual brown wire.
- **Notes**: ✓ verified end-to-end. Function: chip/debris **air blow-off** solenoid. The PIM name `BITCOOL` and OEM M-codes M95/M96 are consistent with this — "bit cool" generically covers air-based cooling (which both cools the bit and clears chips). M95/M96 are OEM-defined codes that toggle this output. Wire-color change at `*55` (yellow to R9C2 inside cabinet, brown to Fagor X10/pin 21).

## *56

- **Left (cable 92, field run): WHITE.** **Right (servopack pigtail): WHITE.** = **Yaskawa C encoder BAT−** → C motor CN2 **pin 4**. Landed 2026-07-09; cable-92 conductor colors recorded 2026-07-20 (user).

## *57

- **Left (cable 92, field run): BLACK.** **Right (servopack pigtail): BLUE.** = **Yaskawa C encoder BAT+** → C motor CN2 **pin 3**. Landed 2026-07-09; cable-92 conductor colors recorded 2026-07-20 (user).

## *58

- **Left (cable 92, field run): RED.** **Right (servopack pigtail): YELLOW.** = **Yaskawa AB encoder BAT−** → AB motor CN2 **pin 4**. Landed 2026-07-09; cable-92 conductor colors recorded 2026-07-20 (user).

## *59

- **Left (cable 92, field run): BLUE.** **Right (servopack pigtail): BLUE.** = **Yaskawa AB encoder BAT+** → AB motor CN2 **pin 3**. Landed 2026-07-09; cable-92 conductor colors recorded 2026-07-20 (user).

> **Encoder backup batteries** (the A.810 fix). C battery: `*56` (−) / `*57` (+). AB battery: `*58` (−) / `*59` (+). ⚠ polarity critical (BAT+ = CN2 pin 3). One battery per encoder only.

## *60

(not yet examined)

## *61

- **Left side**: BROWN wire from cable "00-2" → NVZ3120 solenoid valve coil (the air solenoid)
- **Right side**: → Fagor X10/pin 27 (PIM-named `TOOLHT O14`, toolsetter probe deploy output)
- **Notes**: ✓ verified end-to-end. Full chain: Fagor X10/pin 27 asserts +24 V → `*61` → brown wire of cable "00-2" → NVZ3120 solenoid valve coil energizes → valve switches the air flow → Bimba pneumatic cylinder extends or retracts the tool probe. Cable "00-2" carries the electrical signal; the solenoid valve is what converts that into an air-flow action; the Bimba is the pneumatic actuator that physically moves the probe. **Polarity (per PIM comments, still wants physical verification)**: M61 → `SET TOOLHT` is commented "POPUPS UP" in the PLC source; M62 → `RES TOOLHT` is "POPUPS DOWN". So energized (+24 V) = probe extended (popped up); de-energized = probe retracted (stowed down). Fail-safe: any loss of +24 V signal retracts the probe out of the cutting envelope.

## *62

(not yet examined)

## *63

- **Left side**: ORANGE wire from cable 92 → field-side solenoid (function: clamp — likely rack/turret clamp or other clamping mechanism per user's "rack actuation" description)
- **Right side**: BROWN wire → Fagor X10/pin 29 (PIM-named `OCLAMP O18`, "Clamp solenoid")
- **Notes**: ✓ verified end-to-end. PIM color for OCLAMP is ORN, matching the cable 92 orange wire on the field side. Wire-color change at `*63` (orange field-side, brown Fagor-side). This is an **output** from Fagor — when X10/pin 29 asserts +24 V, it sources via brown wire → `*63` → cable 92 orange → solenoid coil → solenoid actuates.

## *64

- **Left side**: YELLOW wire from cable 92 → field-side pneumatic solenoid (function: air purge per PIM name OBLOWOFF — second air-blast output, separate from the BITCOOL chip blow-off at `*85`)
- **Right side**: RED wire → Fagor X10/pin 30 (PIM-named `OBLOWOFF O20`, "Air purge / chip blow-off")
- **Notes**: ✓ verified end-to-end. PIM color for OBLOWOFF is YEL, matching the cable 92 yellow wire on the field side. Wire-color change at `*64` (yellow field-side, red Fagor-side). **Direct connection — no interposing relay**, unlike `*55` (BITCOOL through R9) and `*54` (TOOLLEN through R10). Fagor X10/pin 30 sources +24 V (max 100 mA per Fagor output spec) → `*64` → cable 92 yellow → solenoid coil → field-side ground. ⚠️ Solenoid coil current draw should be checked against the 100 mA limit if not already verified by the OEM.

## *65

- **Left side**: GREEN wire from cable 92 → field-side drawbar release solenoid (releases tool — drawbar OUT)
- **Right side**: ORANGE wire → Fagor X10/pin 31 (PIM-named `ODRAW O22`, "Drawbar release")
- **Notes**: ✓ verified end-to-end. PIM color for ODRAW is GRN — **matches** the cable 92 green wire on the field side. Wire-color change at `*65` (green field-side, orange Fagor-side). **Direct connection — no interposing relay**, like `*64` (OBLOWOFF). Fagor X10/pin 31 sources +24 V (max 100 mA per Fagor output spec) → `*65` → cable 92 green → solenoid coil → field-side ground.

## *66

(not yet examined)

## *67

- **Left side**: ORANGE wire from cable 91 (cable 91 terminates at the top junction box on the other end) — dead-ended, unused (Fagor-era pre-wiring, still present).
- **Right side (as-built 2026-07-23)**: the other **spindle thermostat lead** + a **YELLOW jumper to `*6`**. `*67` is now the thermostat's output node in the e-stop chain (`*39` → thermostat → `*67` → yellow → `*6`).
- **Notes**: ✓ Fagor: `*67` was just the dead-ended orange cable-91 wire (unused). The retrofit reuses this spare terminal as the thermostat's downstream junction. Orange cable-91 wire left in place. Not the same as wire labelled "91" landing on `*91`.

## *68

- **Left side**: HQD **shaft-stopped** sensor S3 signal — field lead **blue** → BIGGREEN **grey** → cable 92-2 **RED** → `*68`.
- **Right side**: LIGHT BLUE (X10/pin 34 conductor) → **7I84U TB2 INPUT29** (HQD shaft-stopped).
- **Notes**: ✓ verified end-to-end 2026-07-09 — hand-rotating the spindle toggles `hm2_7i97.0.7i84.0.0.input-29` TRUE↔FALSE. Cable 92-2 is 4-wire shielded: signal (`*68` ↔ RED), +24 V (`*74` ↔ WHT), ground (BLK), shield (GRN). BIGGREEN **purple**/**green** spare (reserved for a future PNP sensor). Fagor-original: `docs/revert_to_fagor.md`.

## *69

- **Left side**: HQD **tool-locked** sensor S1 signal — field lead **red** → BIGGREEN **red** → cable 30-2 **RED** → `*69`.
- **Right side**: WHITE (X10/pin 35 conductor) → **7I84U TB2 INPUT30** (HQD tool-locked).
- **Notes**: ✓ continuity verified 2026-07-09 (not yet toggled — no tool/air). Cable 30-2 carries both tool sensors; sensor +24 V on cable 30 RED → `*76`. Wire-color change at `*69` (red field-side, white X10-side). Fagor-original: `docs/revert_to_fagor.md`.

## *70

- **Left side**: HQD **tool-released** sensor S2 signal — field lead **yellow** → BIGGREEN **brown** → cable 30-2 **BROWN** → `*70`.
- **Right side**: BLACK (X10/pin 36 conductor) → **7I84U TB2 INPUT31** (HQD tool-released).
- **Notes**: ✓ continuity verified 2026-07-09 (not yet toggled — no tool/air). Cable 30-2 carries both tool sensors: `*69` tool-locked, `*70` tool-released; sensor +24 V on cable 30 RED → `*76`. Wire-color change at `*70` (brown field-side, black X10-side). Fagor-original: `docs/revert_to_fagor.md`.

## +24 VDC Bus — `*71` through `*76`

`*71`–`*76` are all bonded together into one electrical node — the +24 VDC bus, supplied by the +24 V transformer output. Each terminal below lists only the **external wires landing on it** (the +24 V bus side is implicit for every entry). External loads include relay coils, limit-switch COMs, field-sensor +24 V power, and the Mollom RY1 fault-output supply (TA).

### *71

- **External wires landing here**:
  - WHITE wire from cable "00" → air pressure sensor's +24 V power input
  - WHITE wire from cable "9" → spindle overheat thermostat's +24 V power input
  - WHITE wire → Mollom TA (RY1 fault-output +24 V supply) [Fagor: VG5/10]

### *72

- **External wires landing here**:
  - COM wire from cable 33 → Z limit switch common (+24 V supply to Z+ and Z− limit switches)

### *73

- **External wires landing here**:
  - COM wire from cable 13 → X+W gantry limit common (+24 V supply to X+, X−, W+ limit switches)
  - COM wire from cable 23 → Y limit common (+24 V supply to Y+/Y−)

### *74

- **External wires landing here**:
  - WHITE wire from cable "92-2" → +24 V supply to field-side rack position sensor (via top junction box, spliced to BIGGREEN purple)

### *75

- **External wires landing here**: TBD

### *76

- **External wires landing here**:
  - RED wire from cable 30 (shielded) → +24 V common supply for the drawbar position sensors (both `*69` IDRAWUP and `*70` IDRAWDN are powered from this)

---

## AC Neutral Bus — `*77` through `*83`

`*77`–`*83` are all bonded together into one electrical node — the AC (110 V) neutral bus, terminating at mains neutral. **Expanded from `*77`–`*79` to `*77`–`*83` on 2026-07-06.** Each terminal below lists only the **external wires landing on it** (the neutral-bus side is implicit). `*80`–`*83` are the newly-added bus terminals (their own sections below are marked as bus members).

### *77

- **External wires landing here**:
  - AC neutral wire from the grease pump (the pump's neutral return terminal). The grease pump circuit is: AC hot → R1's NO contact (R1A1↔R1D1, closes when R1 is energized) → black wire from R1A1 → grease pump's hot terminal → motor → grease pump's neutral terminal → wire to `*77` → mains neutral. So `*77` and R1A1 are on opposite sides of the grease pump load, NOT directly connected.

### *78

- **External wires landing here**: TBD

### *79

- **External wires landing here**: TBD

---

## 110 V AC Line Bus — `*A` through `*F`

`*A`–`*F` are all bonded together by daisy-chained jumpers into one electrical node — the 110 V AC line bus (the hot side of the AC mains feed to AC-powered loads in the cabinet). Each terminal below lists only the **external wires landing on it** (the line-bus side is implicit).

### *A

- **External wires landing here**:
  - 110 V AC source (mains feed into the cabinet)

### *B

- **External wires landing here**:
  - 110 V AC supply to the **24 VDC transformer** (transformer primary, hot side)
  - 110 V AC supply to the **5 VDC brick** — `*B` feeds BOTH the 5 V and 24 V supply bricks (user-confirmed 2026-07-22)

### *C

- **External wires landing here**:
  - 110 V AC supply to the **Analog Drive fan** (the cooling fan on the SDSM Analog Drive servo chassis)

### *D

- **External wires landing here**:
  - 110 V AC supply to the **Fagor 8055 controller** (CNC controller mains power)

### *E

- **External wires landing here**:
  - 110 V AC to **R8D3** (pole 3 COM)
  - 110 V AC to **R9D3** (pole 3 COM)

### *F

- **External wires landing here**:
  - 110 V AC to the **cabinet cooling fan**
  - 110 V AC to the **spindle cooling fan**

## *80

- Part of the **AC neutral bus** (`*77`–`*83`), bonded to mains neutral. (Added to the bus 2026-07-06. Formerly held the R9A2 chip-blowoff wire, which was relocated to `*85`.)

## *81

- Part of the **AC neutral bus** (`*77`–`*83`), bonded to mains neutral. (Added 2026-07-06.)

## *82

- Part of the **AC neutral bus** (`*77`–`*83`), bonded to mains neutral. (Added 2026-07-06.)

## *83

- Part of the **AC neutral bus** (`*77`–`*83`), bonded to mains neutral. (Added 2026-07-06. Formerly held the R8A2 dead-end wire, which was relocated to `*86`.)

## *84

(empty — the tool-probe signal wire was relocated to *87, 2026-07-06)

## *85

- **Left side**: BROWN wire from cable "92" → external **chip blow-off** air-blast solenoid (field-mounted).
- **Right side**: BROWN wire → R9A2 (R9's NO contact col 2). R9 interposes between the Fagor output and the solenoid.
- **Notes**: ✓ chip blow-off solenoid drive. R9 energizes (Fagor X10/pin 21 `BITCOOL O2`, `*55`) → R9A2–R9D2 closes → +24 V out `*85` → cable 92 BRN → solenoid → air blast. **Was `*90`** (then briefly `*80`); relocated to `*85` 2026-07-06. See `relays.md` R9.

## *86

- **Left side**: → R8A2 (R8's NO contact, col 2)
- **Right side**: dead-ends in the field (no load wired on the field side)
- **Notes**: ✓ verified. R8 is unused on this machine; `*86` is the only output landing from R8, and it goes nowhere on the field side. Leftover from OEM template. (Was `*83`; wire relocated 2026-07-06.)

## *87

- **Left side**: BLACK wire from cable "04" → tool probe (probe surface terminal). Probe is mounted at the spindle; cable 04 runs from probe up to the cabinet.
- **Right side**: → R10C1 (R10's coil terminal 1)
- **Notes**: ✓ verified. `*87` is the **probe-surface +24 V supply AND signal node**, sourced through R10's coil from the +24 V bus on R10C2. Circuit: +24 V bus → R10C2 → R10 coil → R10C1 → `*87` → cable 04 BLK → probe surface. The spindle (chassis 0 V) is the other side of the probe contact. Idle: no current flows (open circuit at probe), so `*87` sits at +24 V and R10 is de-energized. Touch (tool contacts probe surface): probe-to-spindle path closes, current flows through R10's coil to chassis ground, coil sees ~24 V → R10 energizes → R10A2 closes to R10D2 (+24 V) → signal exits via white wire to `*54`. R10 is acting as an interposing relay that uses its own coil as a current-limiter for the probe +24 V supply. (Was `*84`; wire relocated 2026-07-06.)

## *88

- Part of the **5 V bus** (`*88`–`*90`), fed from the 5 V power brick. (2026-07-06.)

## *89

- Part of the **5 V bus** (`*88`–`*90`), fed from the 5 V power brick. (2026-07-06.)

## *90

- Part of the **5 V bus** (`*88`–`*90`), fed from the 5 V power brick.
- **Notes**: `*88`, `*89`, `*90` are bonded as one 5 V node. **Formerly the R9A2 chip blow-off wire** — that wire was relocated to `*85`, and `*90` was repurposed into the 5 V bus (2026-07-06).

## *91

- **Left side**: wire labelled "91"
- **Right side**: TBD (the wire labelled "91" goes to a dead-end per earlier user observation — no destination wired)
- **Notes**: possibly pre-wiring for an unused future function.

---

## Wire-Label Observations (Reference)

Wire labels found on the wires themselves (not the terminals). These are user-observed facts about what each wire's label says and where it physically goes. **Connections to specific Fagor pins are NOT included here** — Fagor-pin destinations require physical tracing, not inference from the PLC source.

| Wire label | Physical observation |
|---|---|
| `05` (red) | Continues from Fagor X10/pin 3 to `*40`, where it splices to a brown wire that continues to R6's coil. ✓ verified in this conversation. |
| `91` | Lands on `*91`, dead-ended (goes nowhere). ✓ user-observed. |
| Cable `MYS 44` | Goes from cabinet to top junction box. Does nothing (no active load at either end). Likely pre-wiring for a future glass scale on the gantry/W axis. ✓ user-observed. |
| Cable `MYS 45` | Goes from cabinet to top junction box. Does nothing. Likely pre-wiring for a future glass scale on the gantry/W axis. ✓ user-observed. |
| Cable `2` | Goes from cabinet to X-axis junction box. Does nothing. Likely pre-wiring for a future X-axis glass scale. ✓ user-observed. |
| Cable `3` | Goes from cabinet to Y-axis junction box. Does nothing. Likely pre-wiring for a future Y-axis glass scale. ✓ user-observed. |
| Cable `4` | Goes from cabinet to Z-axis junction box. Does nothing. Likely pre-wiring for a future Z-axis glass scale. ✓ user-observed. |
| Cable `13` | 3-wire cable carrying X+W gantry limit switch signals: RED → `*24` (back), BLK → `*25` (front), COM → `*73` (+24 V bus). ✓ user-traced. |
| Cable `23` | 3-wire cable carrying Y limit switch signals: RED → `*26` (left), BLK → `*27` (right), COM → `*73`. ✓ user-traced. |
| Cable `33` | 3-wire cable carrying Z limit switch signals: RED → `*28` (Z **bottom** limit), BLK → `*29` (Z **top** limit), COM → `*72`. ✓ user-traced; top/bottom corrected 2026-06-24 (TOP switch sits physically below BOTTOM switch). |
| Cable `20` | Carries the LHS machine e-stop wires from the e-stop to `*5`/`*6`. ✓ user-observed. |

Wire labels that need re-verification before assuming function:
- Wire labels like `33`, `9`, `00`, `00-2`, `0_4`, `2`, `3`, `4` were noted in earlier (trashed) NotesToSelf entries. The OBSERVATIONS of which wires existed and where they went physically were the user's. The inference about which Fagor pin each connected to was based on PLC names (e.g., "wire 33 → Z limit → must be ZFLS at X9/pin 26"). These pin-level connections have not been physically verified and should be re-traced.
