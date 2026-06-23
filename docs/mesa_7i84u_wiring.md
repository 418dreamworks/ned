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
| 1 | VFIELDB | Field power for TB2 I/O (5–32 VDC) | cabinet +24 V |
| 2 | VFIELDB | Field power for TB2 I/O | cabinet +24 V (duplicate) |
| 3 | VFIELDA | Field power for TB3 I/O (5–32 VDC) | cabinet +24 V (or leave open if TB3 unused) |
| 4 | VFIELDA | Field power for TB3 I/O | cabinet +24 V (or leave open if TB3 unused) |
| 5 | GND | Field power ground for TB2 | cabinet 0 V |
| 6 | GND | Field power ground for TB2 | cabinet 0 V |
| 7 | GND | Field power ground for TB3 | cabinet 0 V (or leave open if TB3 unused) |
| 8 | GND | Field power ground for TB3 | cabinet 0 V (or leave open if TB3 unused) |
| (other pins for +5 V logic supply per manual) | | | |

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

## TB3 — Free for Future Expansion

Currently empty. 16 inputs (INPUT0–INPUT15) + 8 outputs (OUTPUT0–OUTPUT7) available.

If using TB3 later: VFIELDA on TB1 needs to be powered (+24 V from cabinet, same as VFIELDB).

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
