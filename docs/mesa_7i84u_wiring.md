# Mesa 7I84U — Wiring Decisions

Companion notes to `mesa_7i84_manual.pdf` and `mesa_7i97t_wiring.md`. The 7I84U is the digital I/O daughter card for the Mesa stack — connects to the 7I97T via sserial (RJ45). On this machine, **all of Fagor X10 lands on the 7I84U**.

Card orientation (per manual): host interface RJ-45 on the **LEFT**. Connectors:

- **TB1** — power connector (+5 V logic supply + VFIELDA/VFIELDB field power)
- **TB2** — field I/O: 16 inputs (INPUT16–INPUT31) + 8 outputs (OUTPUT8–OUTPUT15)
- **TB3** — field I/O: 16 inputs (INPUT0–INPUT15) + 8 outputs (OUTPUT0–OUTPUT7)
- **J1** — RJ-45 sserial link to 7I97T TB4 (CAT5/6 cable)

Each input and output terminal is **single-pin** (unlike the 7I97T's ± pairs). Reference voltage comes from VFIELDA (for TB3 I/O) or VFIELDB (for TB2 I/O) on TB1. Inputs are **sinking** — they register active when the input pin sees +V (matches PNP/sourcing sensor convention).

---

## TB1 — Power Connector

| TB1 pin | Signal | Function | Connect to |
|---|---|---|---|
| 1 | VFIELDB | Field power 5–32 V for TB2 I/O (bottom pin) | cabinet +24 V |
| 2 | VFIELDB | Field power 5–32 V for TB2 I/O | cabinet +24 V |
| 3 | VFIELDA | Field power 5–32 V for TB3 I/O | cabinet +24 V (or open if TB3 unused) |
| 4 | VFIELDA | Field power 5–32 V for TB3 I/O | cabinet +24 V (or open if TB3 unused) |
| 5 | **VIN** | **Card LOGIC power 8–32 V** | +24 V — or W1 LEFT to feed VIN from VFIELDB |
| 6 | GROUND | VIN/VFIELD common | cabinet 0 V |
| 7 | GROUND | VIN/VFIELD common | cabinet 0 V |
| 8 | GROUND | VIN/VFIELD common (top pin) | cabinet 0 V |

CORRECTED 2026-06-27 from the 7I84U manual (TB1 PINOUT, lines 225–232): TB1 is **8 pins** —
VFIELDB ×2 (1,2), VFIELDA ×2 (3,4), **VIN (5) = logic power**, GROUND ×3 (6,7,8, all common).
W1 LEFT ties VIN to VFIELDB. CAUTION (manual): VFIELD must connect directly to the DC source —
no switch/breaker/relay contact in the VFIELD circuit (a fuse is OK).

Tying VFIELDA and VFIELDB both to cabinet +24 V means all TB2 and TB3 I/O run at +24 V — matches the cabinet's PNP sensor + 24 V solenoid scheme.

---

## TB2 — All X10 Signals Land Here

| TB2 pin | Direction | Signal | Cabinet `*N` | Fagor X10 pin (was) | HAL signal |
|---|---|---|---|---|---|
| 13 | INPUT28 | Tool-probe contact | `*54` | 17 (TOOLLEN) | `tool-probe-contact` |
| 14 | INPUT29 | Rack position sensor | `*68` | 34 (ITOOLIN, repurposed) | `rack-position` |
| 15 | INPUT30 | Drawbar UP sensor | `*69` | 35 (IDRAWUP) | `drawbar-up` |
| 16 | INPUT31 | Drawbar DOWN sensor | `*70` | 36 (IDRAWDN) | `drawbar-down` |
| 17 | OUTPUT8 | Drive enable → R5 coil | `*8` | 2 (/EMEROUT) | `drive-enable` |
| 18 | OUTPUT9 | Spin CW → R6 coil → Mollom S1 | `*40` | 3 (SPIN-CW) | `spin-cw` |
| 19 | OUTPUT10 | Spin CCW → R7 coil → Mollom S2 | `*41` | 4 (SPIN-CCW) | `spin-ccw` |
| 20 | OUTPUT11 | Chip blow-off → R9 coil → solenoid | `*55` | 21 (BITCOOL) | `chip-blowoff` |
| 21 | OUTPUT12 | Toolsetter probe deploy → Bimba solenoid | `*61` | 27 (TOOLHT) | `toolsetter-deploy` |
| 22 | OUTPUT13 | Drawbar clamp → solenoid | `*63` | 29 (OCLAMP) | `drawbar-clamp` |
| 23 | OUTPUT14 | Spindle taper air purge → solenoid | `*64` | 30 (OBLOWOFF) | `spindle-taper-purge` |
| 24 | OUTPUT15 | Drawbar release → solenoid | `*65` | 31 (ODRAW) | `drawbar-release` |

**12 of TB2's 24 pins used (13–24).** Pins 1–12 (INPUT16–INPUT27) are free for future expansion. All 8 outputs exactly fill OUTPUT8–OUTPUT15.

Optional 9th X10 output `*42`/LATCH1 (pin 5, currently drives unused R8) is **skipped** — would have to spill to TB3 OUTPUT0 if ever needed.

---

## TB3 — Head Yaskawa sequence I/O (A & C) + spare

16 inputs (INPUT0–INPUT15) + 8 outputs (OUTPUT0–OUTPUT7). Reserved for the head Yaskawa
servos ([cmp:head-servo]); everything else free.

If using TB3: VFIELDA on TB1 must be powered (+24 V from cabinet, same as VFIELDB).

### Head Yaskawa CN1 sequence I/O — reserved (inert/future, not landed)

The pulse reference (PULS±/SIGN±) comes from the **7I85** (`mesa_7i85s_wiring.md`); the
24 V sequence I/O below comes from the **7I84**. **Set OUTPUT6 and OUTPUT7 to sourcing.**

**A and C are two separate servopacks**, each with its own CN1 — the CN1 pin numbers are
identical on both (CN1-40 = /S-ON on each); the "Yaskawa CN1" column means *that axis's own
connector*. The 7I84 pins (TB3-23/15 for A, TB3-24/16 for C) are what differ per axis.

| Axis | Signal | 7I84 pin | dir | Yaskawa CN1 |
|---|---|---|---|---|
| A (tilt) | /S-ON | TB3-23 (OUTPUT6, sourcing) | → | CN1-40 |
| A (tilt) | ALM− | TB3-15 (INPUT14) | ← | CN1-32 |
| A (tilt) | ALM+ | +24 V (TB1 rail 1–5) | → | CN1-31 |
| A (tilt) | +24VIN | 0 V (TB1 GND 6–8) | → | CN1-47 |
| C (spin) | /S-ON | TB3-24 (OUTPUT7, sourcing) | → | CN1-40 |
| C (spin) | ALM− | TB3-16 (INPUT15) | ← | CN1-32 |
| C (spin) | ALM+ | +24 V (TB1 rail 1–5) | → | CN1-31 |
| C (spin) | +24VIN | 0 V (TB1 GND 6–8) | → | CN1-47 |

Sources: TB3 pin numbers from the 7I84U manual TB3 pinout (OUTPUT6/7 = TB3-23/24,
INPUT14/15 = TB3-15/16); CN1-40/32/31/47 = Yaskawa CN1 (/S-ON, ALM±, +24VIN). New head
wiring — not yet landed.

**What the signals do**
- **/S-ON (Servo ON)** = enable, *Mesa → drive*. Asserting it energizes the motor (closes
  the loop, holds position, accepts pulses); de-asserting base-blocks the drive (motor free,
  no torque). Active-low.
- **ALM (Alarm)** = fault, *drive → Mesa*. The drive asserts it on any internal fault
  (overcurrent, overvoltage, encoder error, overload, overspeed, …).

**Why CN1-47 (+24VIN) is tied to 0 V, not +24 V.** CN1-47 is the *input common* (return
rail) for the drive's sequence inputs. Its rail depends on the Mesa output mode:
- **Source mode (chosen here):** CN1-47 = **0 V**; OUTPUT6/7 push **+24 V into CN1-40** →
  through the input opto → back to CN1-47 at 0 V. Requires OUTPUT6/7 = **sourcing**.
- Sink mode (alternative): CN1-47 = +24 V; the Mesa output pulls CN1-40 to 0 V; requires
  OUTPUT6/7 = sinking.
The pin is *named* "+24VIN" because Yaskawa's default is sink mode — in our source-mode
scheme it sits at 0 V. If CN1-47 floated, no current crosses the opto and /S-ON never acts.

**ALM is fail-safe (normally-conducting).** The alarm transistor is **ON in normal
operation** and turns **OFF on a fault or loss of power**. So Mesa reads +V = healthy, and
**loss of signal = fault**. Invert it in HAL (`not`) so "no current" maps to "faulted" — a
dead or unpowered drive then reads as a fault, not as OK.

---

## J1 — Sserial Link to 7I97T

RJ-45 jack. Connects to **7I97T TB4** RS-422 port (pins 15–18) + +5 V power on TB4 pins 19/20. Use a standard CAT5/6 cable, terminated per the pinout table in `mesa_7i97t_manual.txt` / `mesa_7i84_manual.txt`:

| CAT5 conductor | 7I97T TB4 pin | Signal |
|---|---|---|
| Blue (4) | 13 | GND |
| Blue/White (5) | 14 | GND |
| Green (6) | 15 | RX+ |
| Green/White (3) | 16 | RX− |
| Orange (2) | 17 | TX+ |
| Orange/White (1) | 18 | TX− |
| Brown/White (7) | 19 | +5 V |
| Brown (8) | 20 | +5 V |

7I97T's W23 jumper should be LEFT (RS-422 termination enabled) for the sserial link.

---

## Summary

| What | Count | Mesa landing |
|---|---|---|
| X10 inputs | 4 | TB2 INPUT28–INPUT31 (pins 13–16) |
| X10 outputs | 8 | TB2 OUTPUT8–OUTPUT15 (pins 17–24) |
| Free on TB2 | 12 inputs (pins 1–12) | future |
| Free on TB3 | 16 inputs + 8 outputs | future |

Total 7I84U capacity: 32 inputs + 16 outputs. Used: 4 inputs + 8 outputs. Free: 28 inputs + 8 outputs.
