# Mesa 7I97T — Wiring Decisions

Companion notes to `mesa_7i97t_manual.pdf` and the HAL signal map in `wiring_to_hal_guide.md`. Records the physical landings on the 7I97T card for this machine.

Card orientation (per manual): Ethernet RJ-45 on the **LEFT**, frame-ground mounting hole top-left. Terminal blocks along the top edge, left to right: **TB1, TB2, TB3, TB4, TB5**. PCB silkscreen marks pin 1 of each block with a black square pad.

---

## TB1 — Encoders 0–2 (X, Y, Z)

24-pin block, three 8-pin removable plugs. Pin 1 = QA0 (bottom of the block).

| TB1 plug | Pins | Encoder channel | Axis | Source |
|---|---|---|---|---|
| Bottom | 1–8 | 0 | **X** | Fagor X1 |
| Middle | 9–16 | 1 | **Y** | Fagor X2 |
| Top | 17–24 | 2 | **Z** | Fagor X3 |

Per-plug pinout (same pattern repeats for each encoder n):

| Plug pin | Signal |
|---|---|
| 1 | QAn |
| 2 | /QAn |
| 3 | GND |
| 4 | QBn |
| 5 | /QBn |
| 6 | +5 V |
| 7 | IDXn |
| 8 | /IDXn |

Fagor X1/X2/X3/X4 standard pinout (15-pin SUB-D HD, per `fagor_8055_installation_manual_en.txt:3102`) — same pinout for all four axis feedback connectors, only the destination plug changes:

| Fagor X pin | Signal | → 7I97T pin (within the axis's plug) |
|---|---|---|
| 1 | A | plug pin 1 (QA) |
| 2 | /A | plug pin 2 (/QA) |
| 3 | B | plug pin 4 (QB) |
| 4 | /B | plug pin 5 (/QB) |
| 5 | I0 | plug pin 7 (IDX) |
| 6 | /I0 | plug pin 8 (/IDX) |
| 9 | +5 V | plug pin 6 (+5 V) |
| 11 | 0 V | plug pin 3 (GND) |
| 15 | Shield | cable hood / chassis |

### Per-axis landing summary

| Axis | Fagor connector | 7I97T terminal block + plug | Absolute pin range |
|---|---|---|---|
| **X** | X1 | TB1 bottom plug (encoder 0) | TB1 pins 1–8 |
| **Y** | X2 | TB1 middle plug (encoder 1) | TB1 pins 9–16 |
| **Z** | X3 | TB1 top plug (encoder 2) | TB1 pins 17–24 |
| **W** | X4 | TB2 bottom plug (encoder 3) | TB2 pins 1–8 |

Example: for the **W axis**, Fagor X4 pin 1 (A) lands on TB2 pin 1 (QA3); X4 pin 2 (/A) → TB2 pin 2; X4 pin 3 (B) → TB2 pin 4; X4 pin 4 (/B) → TB2 pin 5; X4 pin 5 (I0) → TB2 pin 7; X4 pin 6 (/I0) → TB2 pin 8; X4 pin 9 (+5 V) → TB2 pin 6; X4 pin 11 (0 V) → TB2 pin 3.

---

## TB2 — Encoders 3–5 (W, MPG, spare)

Same layout convention as TB1.

| TB2 plug | Pins | Encoder channel | Function | Source |
|---|---|---|---|---|
| Bottom | 1–8 | 3 | **W** axis | Fagor X4 |
| Middle | 9–16 | 4 | **Pendant MPG (handwheel)** | Fagor X6 |
| Top | 17–24 | 5 | spare (future: spindle encoder?) | — |

### TB2 middle plug — MPG detail

Fagor X6 standard pinout for 1Vpp / differential TTL feedback (15-pin SUB-D, per `fagor_8055_installation_manual_en.txt:3170-3201`). The pendant cable conductor map is from `pendant.md:86-99`.

| Fagor X6 pin | Signal | Pendant conductor | → 7I97T TB2 pin |
|---|---|---|---|
| 1 | A | Brn RED | 9 (QA4) |
| 2 | /A | Brn BLK | 10 (/QA4) |
| 3 | B | Red RED | 12 (QB4) |
| 4 | /B | Red BLK | 13 (/QB4) |
| 7 | +5 V | Yel RED | 14 (+5 V) |
| 8 | 0 V | Yel BLK | 11 (GND) |
| 15 | Shield | cable shield | hood / chassis |

TB2 pins 15 (IDX4) and 16 (/IDX4) left open — this MPG has no index marker.

X6 pin 5 (ORN RED) is the axis-selector C pole — does NOT land on TB2; goes to TB4 IN0 (see "Reserved Pendant Block" below).

X6 pin 6 (/I0) unused — pendant has no /I0 signal.

Pendant +5 V comes from the 7I97T's internal +5 V rail via TB2 pin 14. With the Fagor removed, this is what powers the handwheel encoder.

---

## TB3 — Analog ±10 V Outputs + Drive Enables

24-pin block, six 4-pin removable plugs. Each plug = one analog channel.

Per-plug pinout (same pattern repeats for each channel n):

| Plug pin | Signal |
|---|---|
| 1 | ENAn− |
| 2 | ENAn+ |
| 3 | GND |
| 4 | AOUTn (±10 V signal) |

Channel assignment from Fagor X8 analog command outputs:

| TB3 plug | TB3 pins | Channel | Axis / function | Fagor X8 cable label |
|---|---|---|---|---|
| 1 (bottom) | 1–4 | 0 | **X** velocity cmd | cable "1" (X8 pin 1 RED → AOUT0, X8 pin 9 BLK → GND) |
| 2 | 5–8 | 1 | **Y** velocity cmd | cable "2" (X8 pin 2 RED → AOUT1, X8 pin 10 BLK → GND) |
| 3 | 9–12 | 2 | **Z** velocity cmd | cable "3" (X8 pin 3 RED → AOUT2, X8 pin 11 BLK → GND) |
| 4 | 13–16 | 3 | **W** velocity cmd | cable "4" (X8 pin 4 RED → AOUT3, X8 pin 12 BLK → GND) |
| 5 | 17–20 | 4 | **unused** — channel 4 reserved across TB2/TB3 for MPG-related signals only | — |
| 6 (top) | 21–24 | 5 | **Spindle** velocity cmd (to Mollom AI2) | cable "7" (X8 pin 8 RED → AOUT5 on TB3 pin 24, X8 pin 14 BLK → GND on TB3 pin 23) |

**ENA−/ENA+ pins are unused on this machine.** Drive enable is handled entirely by the existing electrical chain:

- HAL `drive-enable` → `7i97t.out.00` → `*8` → **R5 coil** → R5 closes (when e-stop chain intact) → `*7` energized
- `*7` energizes **R0** (servo DC bus power contactor — gates power to the SDSM chassis)
- `*7` energizes **R3** (4-pole RUN/STOP signal relay — gates the enable loop for each of the 4 axis drives)

One HAL output drops `*7`, both R0 and R3 release, all 4 axes lose both power and the enable signal simultaneously. **All-or-nothing** by design — no per-axis enable. So TB3 ENA0–ENA5 stay open (no wires landed on plug pins 1 or 2 of any TB3 plug).

See `relays.md` R0, R3, R5 sections for the full electrical chain.

### Per-axis X8 → TB3 summary

| Axis | Fagor X8 RED pin → TB3 AOUT pin | Fagor X8 BLK pin → TB3 GND pin |
|---|---|---|
| **X** | X8 pin 1 → TB3 pin 4 (AOUT0) | X8 pin 9 → TB3 pin 3 |
| **Y** | X8 pin 2 → TB3 pin 8 (AOUT1) | X8 pin 10 → TB3 pin 7 |
| **Z** | X8 pin 3 → TB3 pin 12 (AOUT2) | X8 pin 11 → TB3 pin 11 |
| **W** | X8 pin 4 → TB3 pin 16 (AOUT3) | X8 pin 12 → TB3 pin 15 |
| **Spindle** | X8 pin 8 → TB3 pin 24 (AOUT5) | X8 pin 14 → TB3 pin 23 |

X8 dead-ended spares (pins 5, 6, 7, 13) stay dead-ended in the cabinet — not landed on Mesa. Shield bonds at the Mesa-end cable hood / chassis ground.

---

## TB4 — Digital Inputs + RS-422 + Aux 5 V

24-pin block, four removable plugs: 6 + 6 + 8 + 4.

Full pinout:

| TB4 pin | Signal |
|---|---|
| 1 | IN0 |
| 2 | IN1 |
| 3 | IN COMMON 0,1 |
| 4 | IN2 |
| 5 | IN3 |
| 6 | IN COMMON 2,3 |
| 7 | IN4 |
| 8 | IN5 |
| 9 | IN COMMON 4,5 |
| 10 | IN6 |
| 11 | IN7 |
| 12 | IN COMMON 6,7 |
| 13 | GND |
| 14 | GND |
| 15 | RS-422/485 RX+ |
| 16 | RS-422/485 RX− |
| 17 | RS-422/485 TX+ |
| 18 | RS-422/485 TX− |
| 19 | +5VP (output from card) |
| 20 | +5VP (output from card) |
| 21 | +5 V (aux supply input) |
| 22 | +5 V (aux supply input) |
| 23 | GND (aux supply input) |
| 24 | GND (aux supply input) |

### Reserved Pendant Block — TB4 IN0–IN3

Pendant buttons share one logical block on TB4 to keep wiring tidy (near TB2 where the handwheel encoder lands).

| TB4 pin | Mesa input | Pendant signal | HAL signal | Status |
|---|---|---|---|---|
| 1 | IN0 | Axis selector (X6 pin 5, ORN RED) | `pendant-axis-selector` | wired |
| 2 | IN1 | reserved — future pendant button | TBD | reserved |
| 4 | IN2 | reserved — future pendant button | TBD | reserved |
| 5 | IN3 | reserved — future pendant button | TBD | reserved |

### IN COMMON wiring for pendant block

The pendant buttons are wired so their signal is pulled to **0 V** when active (e.g., the axis selector NC contact ties X6 pin 5 ORN RED to handwheel 0 V when released). For the opto-isolated inputs to read this, IN COMMON must be at **+5 V** — and that +5 V must be the **same node** as the pendant's 0 V return.

**Decision: jumper TB2 pin 14 (+5 V) → TB4 pin 3 (IN COMMON 0,1).**

Rationale: TB2 pin 14 is the +5 V supply that feeds the pendant's handwheel via Yel RED. Using the same physical tap for IN COMMON guarantees the input opto and the handwheel see the same +5 V / 0 V rails — no level mismatch, no isolation hop.

Also jumper TB4 pin 3 → TB4 pin 6 (IN COMMON 2,3) so all 4 reserved pendant slots share the same +5 V common.

Final IN COMMON jumpers for the pendant block:
- TB2 pin 14 → TB4 pin 3 (IN COMMON 0,1 at +5 V)
- TB4 pin 3 → TB4 pin 6 (IN COMMON 2,3 at same +5 V)

Equivalent alternate tap: TB4 pin 19 (+5VP) → TB4 pin 3 (shorter jumper, same electrical node). Either works; the chosen tap is TB2 pin 14 to make the shared-rail intent explicit in the wiring.

### Cabinet Block — TB4 IN4–IN7 (first 4 of 11 X9 signals)

| TB4 pin | Mesa input | Cabinet `*N` | Fagor X9 pin (was) | HAL signal |
|---|---|---|---|---|
| 7 | IN4 | `*6` | 2 (/EMERINP) | `e-stop-released` |
| 8 | IN5 | `*24` | 21 | `limit-x-back` |
| 10 | IN6 | `*25` | 22 | `limit-x-front` |
| 11 | IN7 | `*26` | 23 | `limit-y-left` |

### IN COMMON wiring for TB4 cabinet block

Cabinet sensors are PNP/sourcing (+24 V on the signal pin when active). For the Mesa opto to read this, IN COMMON ties to cabinet 0 V (the opposite rail).

- TB4 pin 9 (IN COMMON 4,5) → **cabinet 0 V**
- TB4 pin 12 (IN COMMON 6,7) → **cabinet 0 V**

These commons daisy-chain across to the TB5 cabinet block commons (see TB5 section).

### Source of the cabinet 0 V tap

The wires currently on **Fagor X9 pins 18 and 19** (the Fagor's 0 V supply input from the cabinet) are direct taps into the cabinet 0 V node. When the Fagor is removed, those two conductors are repurposed as the IN COMMON returns for the Mesa cabinet block:

- X9 cable pin 18 wire → TB5 pin 3 (IN COMMON 8,9)
- X9 cable pin 19 wire → TB5 pin 6 (IN COMMON 10,11)

From TB5 pins 3/6, jumpers fan out to all the other cabinet IN COMMON terminals (TB4 pin 9, TB4 pin 12, TB5 pin 9, TB5 pin 12), making the entire cabinet IN COMMON net one node at cabinet 0 V via two parallel return paths.

---

## TB5 — Digital Inputs + Isolated Outputs

24-pin block, four 6-pin removable plugs.

Full pinout:

| TB5 pin | Signal |
|---|---|
| 1 | IN8 |
| 2 | IN9 |
| 3 | IN COMMON 8,9 |
| 4 | IN10 |
| 5 | IN11 |
| 6 | IN COMMON 10,11 |
| 7 | IN12 |
| 8 | IN13 |
| 9 | IN COMMON 12,13 |
| 10 | IN14 |
| 11 | IN15 |
| 12 | IN COMMON 14,15 |
| 13 | OUT0− |
| 14 | OUT0+ |
| 15 | OUT1− |
| 16 | OUT1+ |
| 17 | OUT2− |
| 18 | OUT2+ |
| 19 | OUT3− |
| 20 | OUT3+ |
| 21 | OUT4− |
| 22 | OUT4+ |
| 23 | OUT5− |
| 24 | OUT5+ |

### Cabinet Block — TB5 IN8–IN14 (remaining 7 of 11 X9 signals)

| TB5 pin | Mesa input | Cabinet `*N` | Fagor X9 pin (was) | HAL signal |
|---|---|---|---|---|
| 1 | IN8 | `*27` | 24 | `limit-y-right` |
| 2 | IN9 | `*28` | 25 | `limit-z-bottom` |
| 4 | IN10 | `*29` | 26 | `limit-z-top` |
| 5 | IN11 | `*36` | 33 (IROTATE) | `spindle-running` |
| 7 | IN12 | `*37` | 34 (/AIRFLT) | `air-pressure-ok` |
| 8 | IN13 | `*38` | 35 (SPINFLT) | `vfd-fault` |
| 10 | IN14 | `*39` | 36 (OVERTEMP) | `spindle-overtemp` |

**TB5 IN15 (pin 11) reserved** for future X/W homing limit switch.

### IN COMMON wiring for TB5 cabinet block

- TB5 pin 3 (IN COMMON 8,9) → cabinet 0 V (direct from X9 cable pin 18 wire)
- TB5 pin 6 (IN COMMON 10,11) → cabinet 0 V (direct from X9 cable pin 19 wire)
- TB5 pin 9 (IN COMMON 12,13) → cabinet 0 V (via jumper from pin 6 or pin 3)
- TB5 pin 12 (IN COMMON 14,15) → cabinet 0 V (via jumper from pin 9)

All cabinet IN COMMONs (TB4 pins 9 + 12 + TB5 pins 3, 6, 9, 12) jumpered into one node at cabinet 0 V.

### Outputs — TB5 pins 13–24

| TB5 pin | Signal |
|---|---|
| 13–24 | OUT0 through OUT5 (6 outputs in ± pairs) |

**All 6 outputs unused.** All X10 outputs (drive-enable, spin-cw, spin-ccw, chip-blowoff, toolsetter-deploy, drawbar-clamp, spindle-taper-purge, drawbar-release) landed on **7I84U TB2 OUTPUT8–OUTPUT15** — see `mesa_7i84u_wiring.md`.

7I97T native outputs reserved as spare for future use.

---

## Other Connectors (not yet relevant to wiring decisions)

- **P3** — +5 V power input to the card (do not exceed 5 V). Pin 1 = +5 V (top, square pad), pin 2 = GND.
- **P2** — DB25 expansion port for 7I85S daughter card.
- **P1** — JTAG (debug only).
- **Frame ground** — top-left mounting hole. Bond to earth/cabinet ground for ESD/EMI.

---

## Jumpers (set on the card, not field wiring)

To be reviewed before powering up:
- **W19/W17/W15** — Encoder 0 differential/TTL mode (3 jumpers per encoder; right = differential, left = single-ended). Set all to **differential** for the SDSM Yaskawa encoders + the MPG.
- **W13/W9/W7** — Encoder 1 differential/TTL mode. Same.
- **W5/W3/W1** — Encoder 2 differential/TTL mode. Same.
- **W20/W18/W16** — Encoder 3. Same.
- **W14/W10/W8** — Encoder 4 (MPG). Same — unless the OLM 01 2DZ1 11A turns out to be single-ended, in which case set to single-ended.
- **W6/W4/W2** — Encoder 5. Set to differential as default; revisit when populated.
- **W22** — Expansion connector 5 V (controls whether the 7I85S daughter card gets 5 V from the host). Default DOWN = breakout 5 V disabled. Per `mesa_7i85s_manual.txt`, the 7I85S's W3 defaults to UP (expecting 5 V from host). Either flip 7I97T W22 to UP, or flip 7I85S W3 to DOWN and supply external +5 V to the 7I85S P1.
- **W21** — Expansion connector pullup/pulldown. UP = pullups on P2 I/O; DOWN = pulldowns.
- **W23** — RS-422/485 termination. LEFT = termination enabled (for the 7I84U sserial link).
- **W11/W12** — IP address selection.
