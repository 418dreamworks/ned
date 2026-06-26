# Saftronics VG5 VFD (Legacy — being removed)

The original VFD installed in the cabinet, driving the spindle motor. Being replaced by the Mollom G75. This file documents the VG5's terminal wiring as it stood, for reference during the transition.

Source manual: `saftronics_vg5_users_manual.pdf` (113 pages).
Detailed trace document: `../trash/VG5_wiring.md`.

## Power Terminals

(Not catalogued in detail — being disconnected as part of the VFD swap.)

## Control Circuit Terminals (1–33, with 28–32 absent on this terminal block)

| Terminal | VG5 manual function | Wire on it | Other end | Status |
|---|---|---|---|---|
| **1** | Forward run/stop (closed = forward run) | Brown wire (unlabelled) | R6A2 | ✓ |
| **2** | Reverse run/stop (closed = reverse run) | Red wire (unlabelled, small gauge) | R7A2 | ✓ |
| **3** | External fault input (multi-function H1-01) | Orange wire labelled "2" | R2B2 | ✓ |
| **4** | Fault reset input (multi-function H1-02) | Orange wire labelled "3" | R2A2 | ✓ |
| 5–8 | (multi-function DIs, unused) | — | — | — |
| **9** | Multi-function NO contact output (default: "during running"), partner of terminal 10 | Blue wire | R1C2 (R1's coil) | ✓ |
| **10** | Multi-function NO contact output, partner of 9 | 2 white wires: one is a jumper to VG5/20; the other goes to `*71`-`*76` (+24 V bus) | (1) jumper to VG5/20; (2) `*71`-`*76` | ✓ |
| **11** | Sequence control input common (return for 1–8) | 3 orange wires: crimped pair labelled "1" + "2", plus standalone "1" | Crimped "1" → R7D2; crimped "2" → R6D2; standalone "1" → R2D2 | ✓ |
| **12** | Shield sheath connection (internally tied to terminal 17 inside the VG5) | Green wire (unlabelled) | Cabinet ground bus | ✓ |
| **13** | Master frequency reference voltage (±10 V, 20 kΩ) | 2 red wires from shielded cable "7" — only 1 is active to Fagor X8 | Active red → Fagor X8 spindle pair (+); spare red → dead-end at power-side terminal block | ✓ |
| **14** | Master frequency reference current (4–20 mA) | — | — | unused |
| **15** | +15 V power supply output | — | — | unused |
| **16** | Multi-function analog input | — | — | unused |
| **17** | Common (0 V) for control circuit | 2 black wires from cable "7" — only 1 active | Active black → Fagor X8 spindle pair (−); spare black → dead-end | ✓ |
| **18** | Fault contact output NO (closes on fault) | Yellow wire (unlabelled) | `*38` | ✓ |
| 19 | Fault contact output NC | — | — | unused |
| **20** | Fault contact output common pole | 1 white wire (jumpered to VG5/10) | VG5/10 (jumper) | ✓ |
| 21–23 | Analog output (frequency meter, current monitor) | — | — | unused |
| 25–27 | Open-collector outputs | — | — | unused |
| 33 | −15 V power supply output | — | — | unused |

## Key Architectural Notes

- VG5 was wired in **sourcing** mode for its dry-contact outputs: when the running contact (9-10) or fault contact (20-18) closed, +24 V from `*71`-`*76` (via the white wire on VG5/10) was sourced to the partner terminal.
- VG5/12 (shield) and VG5/17 (signal common) were **internally bonded** inside the VG5 — verified by continuity measurement during tracing.
- The Mollom replacement is **sinking** on its open-collector outputs (Y1). **R1 is not changed** (golden rule: no cabinet wiring changes) — the sink/source polarity is handled by the interposing relay on Y1 (see `mollom_g75_vfd.md`).

## Migration Plan

Each VG5 wire's destination on the Mollom is documented in `mollom_g75_vfd.md`. After the Mollom is fully wired and tested, the VG5 will be physically removed and this file becomes purely historical.
