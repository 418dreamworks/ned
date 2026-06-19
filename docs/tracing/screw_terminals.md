# Cabinet Screw Terminals (`*N` series)

One section per screw terminal in the cabinet's main terminal block. Terminals 1–91 enumerated below.

**Each terminal has a LEFT side and a RIGHT side** — a wire on each. The format under each terminal records both, so it's visible at a glance whether one side has been traced and the other not. Use `(not yet examined)` when nothing is known about a side.

Convention: `*<n>` means cabinet screw terminal n. See `INDEX.md` for full conventions.

---

## Categories / Bus Ranges (Quick Reference)

| Range | Function |
|---|---|
| `*71` – `*76` | **+24 VDC bus** ("signal common" in local naming, despite being +24 V from the 24 V transformer) |
| `*77` – `*79` | **AC neutral / power common** |
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
- **Notes**: ✓ verified. Polarity not important (daisy-chain link).

## *6

- **Left side**: LHS (left-hand-side machine) e-stop, the other NC contact wire (via cable 20)
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

- **Left side**: RED wire from cable 33 → Z-axis limit switch, "top" contact (upper end of Z travel). NC, fail-safe.
- **Right side**: GREEN wire → Fagor X9/pin 25.
- **Notes**: ✓ verified end-to-end. Z-axis "top" limit.

## *29

- **Left side**: BLK wire from cable 33 → Z-axis limit switch, "bottom" contact (lower end of Z travel). NC, fail-safe.
- **Right side**: BLUE wire → Fagor X9/pin 26.
- **Notes**: ✓ verified end-to-end. Z-axis "bottom" limit.

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

- **Left side**: YELLOW wire → VG5/18 (legacy connection — VG5's fault contact NO output) / planned to land on Mollom RY1 TC instead
- **Right side**: WHITE wire → Fagor X9/pin 35 (`SPINFLT I30`, spindle fault input)
- **Notes**: ✓ verified end-to-end. Carries +24 V when the VFD is in fault state. Full chain: VFD detects internal fault → VFD/18 contact closes → +24 V flows through yellow wire → `*38` → white wire → X9/pin 35 → CNC reads "spindle fault" and reacts (typically aborts the running program and asserts error). Wire-color change at `*38` (yellow VG5-side, white Fagor-side).

## *39

- **Left side**: RED wire from cable "9" → spindle overheat thermostat (signal output). Partner wire in cable "9" is white → `*71` (+24 V), supplying the thermostat.
- **Right side**: BLACK wire → Fagor X9/pin 36 (PIM-named `OVERTEMP I32`, spindle overheat input)
- **Notes**: ✓ verified end-to-end. When the spindle thermostat closes on overtemp, +24 V from `*71` is passed through cable "9" red → `*39` → black → X9/pin 36 → CNC reads "spindle overheat." PIM color comment for OVERTEMP is "BLK 2/9 (RED +24)": cable label "9" matches; signal-side BLK matches the Fagor-side wire color (not the field-cable side). This is the opposite of the `*69`/`*70` PIM-color pattern — confirming PIM colors are unreliable in either direction.

## *40

- **Left side**: red wire labelled "05" → Fagor X10/pin 3
- **Right side**: brown wire → R6's coil high side (R6C2)
- **Notes**: ✓ verified. Splice point where the wire color/label convention changes between Fagor cabinet conventions (red "05") and field-harness conventions (brown).

## *41

- **Left side**: ORANGE wire → Fagor X10/pin 4 (`SPIN-CCW O5`)
- **Right side**: ORANGE wire → R7C2 (R7's coil high side)
- **Notes**: ✓ verified end-to-end. `*41` is the SPIN-CCW splice analog of `*40` (SPIN-CW splice for R6). When the Fagor asserts SPIN-CCW, +24 V at X10/pin 4 flows through orange wire → `*41` → orange wire → R7C2 → R7 energizes → R7A2 closes → reverse-run command reaches VG5/2 (legacy) / Mollom S2 (planned). Both wires at `*41` are orange — no wire-color change at this splice (unlike `*40` where red "05" changed to brown).

## *42

- **Left side**: YELLOW wire → Fagor X10/pin 5 (PIM `LATCH1 O7`, "unlabeled OEM function")
- **Right side**: ORANGE wire → R8C2 (R8's coil high side)
- **Notes**: ✓ verified end-to-end. Wire-color change at the splice (yellow Fagor-side, orange R8-side). R8 is unused on this machine (R8A2 → `*83` dead-ends in the field; no other R8 contacts wired to useful loads), so this Fagor output isn't driving anything in practice — leftover from the OEM template.

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

- **Left side**: YELLOW wire → R9C2 (R9's coil high side). When asserted, drives R9's coil → R9A2 closes → +24 V is sourced out to `*90` → cable 92 BRN → external solenoid.
- **Right side**: BROWN wire → Fagor X10/pin 21 (PIM-named `BITCOOL O2`, "Bit cool output (M95/M96)"). PIM color BRN 20/2 matches the actual brown wire.
- **Notes**: ✓ verified end-to-end. Function: chip/debris **air blow-off** solenoid. The PIM name `BITCOOL` and OEM M-codes M95/M96 are consistent with this — "bit cool" generically covers air-based cooling (which both cools the bit and clears chips). M95/M96 are OEM-defined codes that toggle this output. Wire-color change at `*55` (yellow to R9C2 inside cabinet, brown to Fagor X10/pin 21).

## *56

(not yet examined)

## *57

(not yet examined)

## *58

(not yet examined)

## *59

(not yet examined)

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

- **Left side**: YELLOW wire from cable 92 → field-side pneumatic solenoid (function: air purge per PIM name OBLOWOFF — second air-blast output, separate from the BITCOOL chip blow-off at `*90`)
- **Right side**: RED wire → Fagor X10/pin 30 (PIM-named `OBLOWOFF O20`, "Air purge / chip blow-off")
- **Notes**: ✓ verified end-to-end. PIM color for OBLOWOFF is YEL, matching the cable 92 yellow wire on the field side. Wire-color change at `*64` (yellow field-side, red Fagor-side). **Direct connection — no interposing relay**, unlike `*55` (BITCOOL through R9) and `*54` (TOOLLEN through R10). Fagor X10/pin 30 sources +24 V (max 100 mA per Fagor output spec) → `*64` → cable 92 yellow → solenoid coil → field-side ground. ⚠️ Solenoid coil current draw should be checked against the 100 mA limit if not already verified by the OEM.

## *65

- **Left side**: GREEN wire from cable 92 → field-side drawbar release solenoid (releases tool — drawbar OUT)
- **Right side**: ORANGE wire → Fagor X10/pin 31 (PIM-named `ODRAW O22`, "Drawbar release")
- **Notes**: ✓ verified end-to-end. PIM color for ODRAW is GRN — **matches** the cable 92 green wire on the field side. Wire-color change at `*65` (green field-side, orange Fagor-side). **Direct connection — no interposing relay**, like `*64` (OBLOWOFF). Fagor X10/pin 31 sources +24 V (max 100 mA per Fagor output spec) → `*65` → cable 92 green → solenoid coil → field-side ground.

## *66

(not yet examined)

## *67

- **Left side**: ORANGE wire from cable 91 (cable 91 terminates at the top junction box on the other end)
- **Right side**: nothing — dead-ended at this terminal
- **Notes**: ✓ verified. This wire is connected at one end (`*67`) and dead-ended at the other end (top junction box). Probably pre-wiring for an unused future function. Not the same as wire labelled "91" landing on `*91` — that's a different conductor.

## *68

- **Left side**: RED wire from cable "92-2" → field-side **rack position** sensor (per user). Cable 92-2 RED is spliced in the top junction box to BIGGREEN grey, which continues to the sensor.
- **Right side**: LIGHT BLUE wire → Fagor X10/pin 34 (PIM-named `ITOOLIN I36`, "Tool present in spindle"). **Function mismatch**: PIM symbol is ITOOLIN but the actual sensor on this machine is a rack position sensor — OEM repurposed this PIM I/O.
- **Notes**: ✓ verified end-to-end. Cable 92-2 is a 4-wire shielded cable carrying a single sensor circuit: +24 V supply (`*74` ↔ WHT), signal (`*68` ↔ RED), ground/return (BLK), shield (GRN). Field-side splices to BIGGREEN: BLK→green, RED→grey, WHT→purple. PIM color for ITOOLIN is BRN 8/10 — neither cable 92-2 RED nor the Fagor-side LIGHT BLUE matches. PIM color is unreliable here.

## *69

- **Left side**: RED wire from cable 30-2 → drawbar UP position sensor (signal output)
- **Right side**: WHITE wire → Fagor X10/pin 35 (PIM-named `IDRAWUP I38`, drawbar UP sensor input)
- **Notes**: ✓ verified end-to-end. Sensor's +24 V supply is on cable 30 RED wire → `*76`. When drawbar is in the UP (clamped) position, the inductive sensor outputs +24 V → through cable 30-2 red wire → `*69` → white wire → X10/pin 35 → CNC reads "drawbar up." Wire-color change at `*69` (red sensor-side, white Fagor-side). The PIM documents IDRAWUP as RED, which **matches the sensor-side (cable 30-2) wire color, not the Fagor-side**. Working hypothesis: PIM color comments refer to the field-cable wire, not the OEM's internal harness on the Fagor side.

## *70

- **Left side**: BROWN wire from cable 30-2 → drawbar DOWN position sensor (signal output)
- **Right side**: BLACK wire → Fagor X10/pin 36 (PIM-named `IDRAWDN I40`, drawbar DOWN sensor input)
- **Notes**: ✓ verified end-to-end. Wire-color change at `*70` (brown sensor-side, black Fagor-side). Yet another PIM color mismatch: PIM documents IDRAWDN as ORN but the actual Fagor-side wire is black. Cable 30-2 carries both drawbar sensors: `*69` for drawbar UP (cable red → Fagor white), `*70` for drawbar DOWN (cable brown → Fagor black). Sensor +24 V supply for both is on `*76` via cable 30 RED wire.

## +24 VDC Bus — `*71` through `*76`

`*71`–`*76` are all bonded together into one electrical node — the +24 VDC bus, supplied by the +24 V transformer output. Each terminal below lists only the **external wires landing on it** (the +24 V bus side is implicit for every entry). External loads include relay coils, limit-switch COMs, field-sensor +24 V power, and (legacy) VG5/10.

### *71

- **External wires landing here**:
  - WHITE wire from cable "00" → air pressure sensor's +24 V power input
  - WHITE wire from cable "9" → spindle overheat thermostat's +24 V power input
  - WHITE wire from VG5/10 → VG5 running-contact source (legacy; will be removed when VG5 is replaced by the Mollom)

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

## AC Neutral Bus — `*77` through `*79`

`*77`–`*79` are all bonded together into one electrical node — the AC neutral bus, terminating at mains neutral. Each terminal below lists only the **external wires landing on it** (the neutral-bus side is implicit).

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

- **External wires landing here**: TBD (spindle motor cooling fan hot lands somewhere on this bus — specific terminal not yet identified)

## *80

(not yet examined)

## *81

(not yet examined)

## *82

(not yet examined)

## *83

- **Left side**: → R8A2 (R8's NO contact, col 2)
- **Right side**: dead-ends in the field (no load wired on the field side)
- **Notes**: ✓ verified. R8 is unused on this machine; `*83` is the only output landing from R8, and it goes nowhere on the field side. Leftover from OEM template.

## *84

- **Left side**: BLACK wire from cable "04" → tool probe (probe surface terminal). Probe is mounted at the spindle; cable 04 runs from probe up to the cabinet.
- **Right side**: → R10C1 (R10's coil terminal 1)
- **Notes**: ✓ verified. `*84` is the **probe-surface +24 V supply AND signal node**, sourced through R10's coil from the +24 V bus on R10C2. Circuit: +24 V bus → R10C2 → R10 coil → R10C1 → `*84` → cable 04 BLK → probe surface. The spindle (chassis 0 V) is the other side of the probe contact. Idle: no current flows (open circuit at probe), so `*84` sits at +24 V and R10 is de-energized. Touch (tool contacts probe surface): probe-to-spindle path closes, current flows through R10's coil to chassis ground, coil sees ~24 V → R10 energizes → R10A2 closes to R10D2 (+24 V) → signal exits via white wire to `*54`. R10 is acting as an interposing relay that uses its own coil as a current-limiter for the probe +24 V supply.

## *85

(not yet examined)

## *86

(not yet examined)

## *87

(not yet examined)

## *88

(not yet examined)

## *89

(not yet examined)

## *90

- **Left side**: BROWN wire from cable "92" → external solenoid valve (suspected: chip/debris blow-off — air-actuated)
- **Right side**: BROWN wire → R9A2 (R9's NO contact col 2). R9 is acting as an interposing relay between the Fagor output and the solenoid.
- **Notes**: ✓ both sides traced. Full chain (hypothesised): Fagor X10/pin 30 (`OBLOWOFF O20`, PIM-named) → R9 coil drives via R9C2 (TBD) → R9 energizes → R9A2 (NO) closes to R9D2 (TBD, presumed +24 V) → +24 V flows out via `*90` → cable 92 BRN → solenoid coil → solenoid actuates → air blast clears chips. Same interposing-relay pattern as R6 (SPIN-CW) and R10 (tool probe).

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
| Cable `33` | 3-wire cable carrying Z limit switch signals: RED → `*28` (top), BLK → `*29` (bottom), COM → `*72`. ✓ user-traced. |
| Cable `20` | Carries the LHS machine e-stop wires from the e-stop to `*5`/`*6`. ✓ user-observed. |

Wire labels that need re-verification before assuming function:
- Wire labels like `33`, `9`, `00`, `00-2`, `0_4`, `2`, `3`, `4` were noted in earlier (trashed) NotesToSelf entries. The OBSERVATIONS of which wires existed and where they went physically were the user's. The inference about which Fagor pin each connected to was based on PLC names (e.g., "wire 33 → Z limit → must be ZFLS at X9/pin 26"). These pin-level connections have not been physically verified and should be re-traced.
