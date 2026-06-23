# Mollom G75 VFD (Replacement — Planned Wiring)

Model: **G75-2T-7R5-G-B** (3-phase 220 V input, 7.5 kW, general application, built-in braking unit).

Source manual: `mollom_G75_AC_drive_manual.pdf` (68 pages).
Full spec / commissioning notes: `mollom_facts.md`.

## Power Terminals

| Terminal | Function | Wire / connection | Status |
|---|---|---|---|
| R, S, T | 3-phase 220 V input (or single-phase derated until phase converter arrives — see `mollom_facts.md`) | Mains: L1 → R, N → S or T, third terminal open for derated single-phase | planned |
| U, V, W | 3-phase output to motor | To spindle motor — UVW order determines rotation (swap any two to reverse) | planned |
| P+, PB | Built-in braking unit (this drive has the "B" suffix) | External 1000 W ≥ 16 Ω braking resistor | planned |
| ⏚ | Mains chassis earth | Cabinet earth bus | planned |

## Control Circuit Terminals

| Terminal | Mollom function | F-param | Planned wire / source | Other end | Status |
|---|---|---|---|---|---|
| **S1** | Digital input 1 — Forward RUN (F4-00 = 1, default) | F4-00 = 1 | Brown wire (unlabelled) — was on VG5/1 | R6A2 | planned |
| **S2** | Digital input 2 — Reverse RUN (F4-01 = 2, default) | F4-01 = 2 | Red wire (unlabelled, small gauge) — was on VG5/2 | R7A2 | planned |
| **S3** | Digital input 3 — External fault, closed-relay logic (F4-02 = 33) | F4-02 = 33 | Orange wire labelled "2" — was on VG5/3 | R2B2 | planned |
| **S4** | Digital input 4 — Fault reset (F4-03 = 9) | F4-03 = 9 | Orange wire labelled "3" — was on VG5/4 | R2A2 | planned |
| S5 / HDI | unused | — | — | — | unused |
| **COM** | Digital input common (sink mode default) | — | 3 wires: crimped orange "1" + "2" + standalone orange "1" — all were on VG5/11 | R6D2, R7D2, R2D2 | planned |
| **+24V** | Internal +24 V supply (200 mA max). DO NOT connect to `*71`-`*76` external supply. | — | leave unused | — | unused |
| **+10V** | +10 V supply for analog pot | — | unused | — | unused |
| **AI1** | Single-polarity analog input (0–10 V) | — | unused | — | unused |
| **AI2** | Dual-polarity analog input (±10 V default, F4-18..20 = -10V, -100%, +10V) | (defaults match) | Active red from shielded cable "7" — was on VG5/13 | Fagor X8 spindle pair (+) | planned |
| **AI3** | Keypad potentiometer only | — | (not externally wireable) | — | — |
| **GND** | Analog signal common (0 V). Internally isolated from COM per manual §3.2.3 note. | — | 3 conductors: active black of cable "7" + cable "7" shield + green wire — all were on VG5/17 and VG5/12 | Fagor X8 spindle pair (−) + cabinet ground bus | planned |
| **AO1, AO2** | Analog outputs | — | unused | — | unused |
| **HDO** | High-speed pulse / open-collector output | — | unused | — | unused |
| **TA** | RY1 SPDT common pole (high side of fault output) | — | White wire (was on VG5/10 supply node) | `*71`-`*76` (+24 V bus) | planned |
| **TC** | RY1 NO contact (closes when RY1 energizes = fault active per F5-02 = 2) | F5-02 = 2 | Yellow wire (was on VG5/18) | `*38` | planned |
| **TB** | RY1 NC contact | F5-02 = 2 | unused | — | unused |
| **Y1** | Open-collector output (sinks to COM when active per F5-03 = 1) | F5-03 = 1 | Short pigtail to **interposing relay IN** (NOT the blue wire directly — see `mollom_facts.md` "Outputs — Split RY1 (fault) + Y1 (running)") | Interposer IN; interposer NO output then feeds the blue wire to R1C2 | planned — R1 untouched |
| **485+, 485−** | RS-485 Modbus | — | unused | — | unused |

## Required Parameter Settings (before power-on)

| Parameter | Value | Purpose |
|---|---|---|
| F4-00 | 1 (default) | S1 = Forward RUN |
| F4-01 | 2 (default) | S2 = Reverse RUN |
| F4-02 | **33** | S3 = External fault (closed-loop logic — matches existing R2 NC scheme) |
| F4-03 | **9** | S4 = Fault reset |
| B1-01 | 1 | Speed reference from analog terminal (AI2) |
| B1-02 | 1 | Run command from terminal inputs (S1/S2) |
| F5-02 | 2 | RY1 = Fault output (coast to stop) |
| F5-03 | 1 | Y1 = AC drive operating |
| F9-12 | 10 | Disable input phase loss detection (for single-phase derated operation) |

## Architecture Notes

- **Sink mode** (factory default): the relay contacts in the cabinet close the Mollom DIs to COM to activate. This matches the existing R6/R7/R2 NO/NC scheme — no jumper change needed.
- **GND vs COM**: GND is the analog 0 V reference, COM is the digital input return. Per manual §3.2.3, these are **internally isolated**. Do not bond them externally; leave the COM "+24V" terminal (internal supply) unused.
- **Output polarity flip — handled by interposing relay** (lives with the Mollom permanently). Y1 sinks IN on a small logic-input relay module (DC+/DC-/IN on input side, NC/NO/COM SPDT on output side, H/L jumper set to **L**). DC+/DC- come from Mollom's own +24 V/COM. Output COM taps Mollom TA (already at cabinet +24 V); NO feeds the blue wire to R1C2. R1 stays untouched. The blue wire is the only piece that moves between the VG5 and Mollom installations. See `mollom_facts.md` "Outputs — Split RY1 (fault) + Y1 (running)" for the full wiring table.
- **TA → +24 V** is the supply pole for the RY1 fault output — when RY1 energizes (fault), TC connects to TA, sourcing +24 V to the yellow wire to `*38`.

## Manual Section References

- §2.2 (p.10): Model code decoding (`G75-2T-7R5-G-B`)
- §3.2.2 (p.14): Power terminal descriptions
- §3.2.3 (p.15): Control circuit terminal table (DIs, AIs, AOs, RY1, Y1, HDO, +24V, COM, GND, +10V)
- §3.2.5 (p.16): Sink/source switchover figure (Fig 3-6)
- §3.2.7 (p.19): Full terminals wiring diagram (Fig 3-8)
- §5 (parameter table): F4-00..F4-04 functions (DI assignment), F5-02..F5-05 (DO assignment), F9-12 (input phase loss)
