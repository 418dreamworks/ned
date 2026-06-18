# VG5 VFD Wiring Record

Saftronics VG5 (Revision F, April 1999) — physical wiring of the control-circuit terminal block as installed on the machine. Recorded so it can be reconstructed if disconnected.

Source manual: `/Users/tzuohann/Documents/Claude/ned/docs/saftronics_vg5_users_manual.pdf` (Installation & Quick-Start Manual)

Scope: control circuit screw terminals **1 through 33** (terminals 28–32 do not physically exist on this terminal block). Main circuit (power) terminals not catalogued here.

### Labelling Conventions (used throughout this file)

**Relay terminals — `R<n><row><col>`:**

`R<n>` = relay number n (user's labelling on the cabinet relays).
Each relay's terminal position is labelled by **row letter + column number**:

| Row | Meaning |
|---|---|
| **A** | NO (normally open) contact |
| **B** | NC (normally closed) contact |
| **C** | Signal / coil terminals (columns 1 and 2 only) |
| **D** | COM (common, pole of the contact) |

Example: `R6A2` = Relay 6, NO contact, column 2. `R6C1` = Relay 6, coil terminal 1.

**Cabinet screw terminal blocks — `*<n>`:**

`*<n>` = user's symbol for a specific screw terminal in the cabinet's terminal block.

| Range | Function |
|---|---|
| `*71` – `*76` | **Signal "common" = +24 VDC bus** (from the 24 V DC transformer; local convention names the +24 V rail as the signal common since it's the shared rail all signal circuits reference) |
| `*77` – `*79` | Power common (AC neutral) |

---

## Summary of Used Terminals

| Terminal | Wire(s) | Function | What it does |
|---|---|---|---|
| 1 | brown, unlabelled | Forward run/stop | Closing 1↔11 commands forward run (2-wire config) |
| 2 | red, unlabelled | Reverse run/stop | Closing 2↔11 commands reverse run (2-wire config) |
| 3 | orange "2" | Ext. fault input (default; multi-fn H1-01) | Closing 3↔11 = fault when at default; OEM may have reassigned via H1-01 |
| 4 | orange "3" | Fault reset input (default; multi-fn H1-02) | Closing 4↔11 resets a fault |
| 9 | blue, unlabelled | "During running" NO contact, partner of 10 | Contact 9↔10 closes when VFD is running |
| 10 | white ×2, unlabelled | "During running" NO contact, partner of 9 | One white = jumper to terminal 20. Other white = signal/supply elsewhere |
| 11 | orange ×3 (labels "1", "2", separate "1") | Sequence input common | Return for terminals 1–8. Crimped "1+2" pair + separate "1" |
| 12 | green, unlabelled | Signal-cable shield ground | Externally bonded to G via this wire. Single-sided shield ground scheme |
| 13 | red ×2 from shielded cable "7" | Master frequency ref (±10V) | Spindle speed command from Fagor X8 (signal side) |
| 17 | black ×2 from shielded cable "7" | Control circuit common (0V) | Spindle speed command 0V return; internally tied to terminal 12 |
| 18 | yellow, unlabelled | Fault contact NO output (18↔20 closes on fault) | "Fault occurred" signal |
| 20 | white, unlabelled | Fault contact common pole | Jumpered to terminal 10. Carries the 24V supply that feeds both fault-side outputs |

All other terminals (5, 6, 7, 8, 14, 15, 16, 19, 21, 22, 23, 25, 26, 27, 33) are empty — no wires connected.

---

## Control Circuit Terminals — Sequence Inputs

| Terminal | Manual function | Wire color | Wire label / ID | Notes |
|---|---|---|---|---|
| 1 | Forward run/stop. "Forward run when closed, stop when open (2-wire configuration)." Photo-coupler insulated, +24 VDC, 8 mA. | brown | unlabelled | **Traced to R6A2** — relay 6, **NO contact column 2** (per the row convention: A = NO). So R6's NO contact feeds the VFD's forward-run input. When R6 is energized, the NO contact closes → connects VFD terminal 1 to whatever's on R6D2 (the COM partner of A2) → that source supplies 24 V → VFD sees forward-run command. R6's coil (terminals R6C1/R6C2) is the side that gets driven by the Fagor PLC output `SPIN-CW O3` (X10 pin 3, brown wire). Classic interposing-relay pattern. |
| 2 | Reverse run/stop. "Reverse run when closed, stop when open (2-wire configuration)." Photo-coupler insulated, +24 VDC, 8 mA. | red | unlabelled | **Traced to R7A2** — relay 7, **NO contact column 2** (A = NO per convention). Same architecture as terminal 1: R7's NO contact feeds VFD reverse-run input. When R7 energizes, R7A2 closes → connects to R7D2 (COM partner) → 24 V supplied → VFD sees reverse-run. R7's coil (R7C1/R7C2) is driven by Fagor PLC output `SPIN-CCW O5` (X10 pin 4, red wire). Classic interposing-relay pattern matching terminal 1. |
| 3 | External fault input (default function; multi-function input H1-01). "Fault when closed, normal state when open." Photo-coupler insulated, +24 VDC, 8 mA. | orange | labelled "2" | **Traced to R2B2** — Relay 2, NC contact, column 2. R2's COM (R2D2) goes to VFD terminal 11 (via the separate orange "1" wire). When R2 is de-energized, R2B2 is closed → VFD terminal 3 shorted to terminal 11 → external fault input ACTIVE → VFD won't run. When R2 is energized, R2B2 opens → external fault clears → VFD can run. **H1-01 is likely at default** ("external fault, closed = fault") — the OEM intentionally uses the default so that loss of R2's coil drive = fail-safe stop. R2 is the spindle enable/reset relay (see topology analysis below). |
| 4 | Fault reset input (default function; multi-function input H1-02). "Reset when closed." Photo-coupler insulated, +24 VDC, 8 mA. | orange | labelled "3" | **Traced to R2A2** — Relay 2, NO contact, column 2. R2's COM (R2D2) goes to VFD terminal 11 separate "1" wire. So energizing R2 closes the A2-D2 contact → VFD terminal 4 shorted to terminal 11 → reset asserted. R2 is the spindle enable/reset relay (see topology analysis section). |
| 5 | Multi-step speed ref.1 / Master-Aux change (H1-03). Photo-coupler insulated, +24 VDC, 8 mA. | — | — | Empty / no wire. |
| 6 | Multi-step speed ref.2 (H1-04). Photo-coupler insulated, +24 VDC, 8 mA. | — | — | Empty / no wire. |
| 7 | Jog reference (H1-05). Photo-coupler insulated, +24 VDC, 8 mA. | — | — | Empty / no wire. |
| 8 | External baseblock (H1-06). Photo-coupler insulated, +24 VDC, 8 mA. | — | — | Empty / no wire. |
| 11 | Sequence control input common terminal — return for terminals 1–8. | orange ×3 | labels "1", "2", and a second "1" | First "1" and "2" are **crimped together** going into the terminal. The second "1" lands **separately**. Traced: **wire "2" of crimped pair → R6D2** (R6 COM, paired with R6A2 NO that feeds VFD terminal 1 brown wire — forward run). **Wire "1" of crimped pair → R7D2** (R7 COM, paired with R7A2 NO that feeds VFD terminal 2 red wire — reverse run). **Separate "1" → R2D2** (R2 COM, in the loop between VFD terminal 3 and terminal 11). |

---

## Control Circuit Terminals — Analog Inputs / Power Supplies

| Terminal | Manual function | Wire color | Wire label / ID | Notes |
|---|---|---|---|---|
| 12 | Connection to shield sheath of signal lead. | green | unlabelled | Externally bonded to G (ground bus) via this green wire. **Internally NOT bonded to G** — verified: with the wire removed from terminal 12, no continuity from terminal 12 to G. **Terminal 12 is internally tied to terminal 17** (analog 0V common) — verified by continuity measurement. So the VFD has a single internal common node (12 = 17 = signal common = shield landing point), brought to earth at a single external point via this green wire to G. This is a **single-sided shield ground** scheme: shields land here at the VFD end, get tied to G externally only at this single point, and the shields are left floating at the other end of each shielded cable (CNC side) to prevent ground loops. |
| 13 | Master frequency reference (voltage). −10 to +10 V (or 0 to +10 V), 20 kΩ input impedance. Primary speed command input. | red ×2 (shielded 4-conductor cable) | cable labelled "7" | **Traced**: only ONE of the two red wires is actually active — it goes to the Fagor AXES X8 connector (spindle speed command pair per MPG P007=10 main spindle). The **other red wire** is parked at terminal 13 but dead-ended on the power side of the box — it's a spare conductor from the 4-conductor cable, reserved for future signal expansion without having to pull new cable. The VFD reads voltage between terminals 13 and 17 as the speed command. |
| 14 | Master frequency reference (current). 4–20 mA, 250 Ω. Multi-function analog input H3-08/09/10/11. | — | — | Empty / no wire. |
| 15 | +15 V power supply output (20 mA max). For analog command +15 V supply. | — | — | Empty / no wire. |
| 16 | Multi-function analog input. −10 to +10 V, 20 kΩ. H3-04/05/06/07. | — | — | Empty / no wire. |
| 17 | Common (0 V) for control circuit. | black ×2 (same shielded cable as terminal 13 reds) | cable labelled "7" | **Traced**: only ONE of the two black wires is active — it pairs with the active red on terminal 13 and goes to the Fagor AXES X8 connector (spindle 0V return). The **other black wire** is dead-ended on the power side of the box, same as the spare red — a spare conductor reserved for future expansion. Measured continuous with terminal 12 (shield ground) via the **internal bond between 12 and 17 inside the VFD** (see terminal 12 note). The signal common sits at the same potential as the shield ground, which in turn sits at G via the single external green wire. |
| 33 | −15 V power supply output (20 mA max). For analog command −15 V supply. | — | — | Empty / no wire. |

---

## Control Circuit Terminals — Sequence Outputs (Dry Contacts)

| Terminal | Manual function | Wire color | Wire label / ID | Notes |
|---|---|---|---|---|
| 9 | Multi-function contact output, NO side. Default function: "During running." Dry contact, 250 VAC 1A or 30 VDC 1A. Configurable via H2-01. | blue | unlabelled | **Traced to R1C2** — Relay 1, coil terminal, column 2. The blue wire is the coil drive for R1. Architecture (**sourcing convention**): VFD running → 9-10 contact closes → +24 V (from `*71`-`*76` via second white wire on terminal 10) passes through to terminal 9 → blue wire → R1C2 → R1 energizes → R1's contacts feed the CNC's "spindle running" PLC input. R1's other coil terminal R1C1 connects to 0V somewhere for the coil current path. |
| 10 | Multi-function contact output, NO side. Default function: "During running." Dry contact, 250 VAC 1A or 30 VDC 1A. Configurable via H2-01. | white ×2 | unlabelled | Partner of terminal 9. **One white wire is a jumper to terminal 20** (fault contact common pole). **The other white wire goes to `*71`–`*76` = +24 VDC bus** (the "signal common" rail in local terminology). So terminals 10 and 20 are both at **+24 V**, and the VFD's dry contacts act as **sourcing switches** — supplying +24 V to their respective partner terminals (9 and 18) when active. The relays on the partner side (R1 on terminal 9, etc.) have 0 V on the other coil terminal (R1C1) from elsewhere, and the VFD contact closing completes the coil's current path with +24 V on the input side. |
| 18 | Fault contact output, NO side (of SPDT). "When faulted closed between terminals 18 and 20." Dry contact, 250 VAC 1A or 30 VDC 1A. | yellow | unlabelled | **Traced to `*38`** (cabinet screw terminal block). With terminals 10 and 20 at +24 V (via `*71`–`*76`), the architecture is **sourcing**: when VFD faults → 18-20 contact closes → yellow wire pulled to +24 V → whatever is connected at `*38` reads "fault active." `*38` is most likely the cabinet-side path to a relay coil (with 0 V on its other end) or directly to a Fagor PLC input — matches the Fagor input convention of "active = +24 V applied." |
| 19 | Fault contact output, NC side (of SPDT). "When faulted open between terminals 19 and 20." | — | — | Empty / no wire. The OEM is not using the "healthy / not faulted" output — only the "fault occurred" signal (yellow on 18). |
| 20 | Fault contact common pole of SPDT. 20↔19 closed in normal operation, 20↔18 closes on fault. | white | unlabelled | Jumpered to terminal 10 via the white wire. This jumper ties the running-contact node (10) to the fault-contact common (20) at +24 V — both are sourced from `*71`-`*76` via the second white wire on terminal 10. |
| 25 | Zero speed detection. Open collector output, 48 V / 50 mA max. Multi-function H2-01..H2-03. | — | — | Empty / no wire. |
| 26 | Speed agree detection. Open collector output, 48 V / 50 mA max. | — | — | Empty / no wire. |
| 27 | Open collector output common. | — | — | Empty / no wire. |

---

## Control Circuit Terminals — Analog Outputs

| Terminal | Manual function | Wire color | Wire label / ID | Notes |
|---|---|---|---|---|
| 21 | Frequency meter output. 0 to ±10 V at 0–100% frequency. Multi-function analog monitor (H4-01/02/03). | — | — | Empty / no wire. |
| 22 | Common (return for terminals 21 and 23). | — | — | Empty / no wire. |
| 23 | Current monitor. 5 V at inverter rated current. Multi-function analog monitor (H4-04/05/06). | — | — | Empty / no wire. |

---

## Topology Analysis — How the Run/Fault Feedback Chain Works

The four wires on terminals 9, 10, 18, and 20 form a tightly coupled feedback network. The white wire jumper between 10 and 20 ties the partner sides of the running NO contact and the fault SPDT common pole to the same node.

**Likely architecture (parallel detection signals sharing one supply):**

- 24 VDC enters the node via the second white wire on terminal 10.
- That node is at +24 V whenever the supply is on. It feeds:
  - Terminal 10 — one side of the running NO contact.
  - Terminal 20 — the common pole of the fault SPDT.
- **Blue wire on terminal 9** = "VFD running" output. Gets +24 V only when the running contact closes (i.e., VFD is running). The CNC reads this to know whether the spindle is actually turning.
- **Yellow wire on terminal 18** = "fault occurred" output. Gets +24 V only when the fault contact 18↔20 closes (i.e., VFD is in fault state). The CNC reads this to know whether the spindle has a fault.
- Terminal 19 (NC side of fault contact) is empty — the "healthy / not faulted" signal isn't being used. The OEM only signals fault explicitly, not health implicitly.

This is a "parallel independent signals" architecture, not a series safety chain — each contact reports its own state to the controller separately. To confirm, trace the second white wire on terminal 10 back to its source.

**Why the OEM may have done this:**
The CNC needs two pieces of info about the spindle: "is it running?" and "did it fault?" Putting them on two parallel contacts of the same VFD lets a single 24 VDC supply feed both, and the controller reads each on its own input. The white jumper is the supply distribution; the blue and yellow wires are the two independent outputs.

---

## Topology Analysis — Run/Stop Inputs

Terminals 1, 2, 3, 4 are sequence inputs that need to be closed to terminal 11 (the common) to be activated.

**Forward/reverse run (terminals 1 and 2):**
- Brown wire on terminal 1 = forward run command.
- Red wire on terminal 2 = reverse run command.
- Wire colors match Fagor PLC outputs `SPIN-CW O3` (brown) and `SPIN-CCW O5` (red).
- Per Fagor manual: PLC outputs are 24 VDC, 100 mA max per output.
- Per VG5 manual: inputs need 24 VDC, 8 mA.
- Compatible voltages — likely direct connection from Fagor PLC outputs to VFD inputs. Could go through interposing relays for isolation/troubleshooting, but not strictly required.

**External fault / permissive input (terminal 3):**
- Orange "2" wire on terminal 3, continuous with separate orange "1" on terminal 11.
- The loop is currently closed (continuity present), which means either:
  - H1-01 is at default (external fault on close) and there's a contact in the loop that's normally closed but opens under specific conditions — likely an NC contact of a fault/safety relay.
  - H1-01 has been reassigned to an inverted-logic permissive (closed = healthy, open = fault) so the closed loop is intentional and represents "OK to run."
- The second interpretation fits typical CNC OEM design — fail-safe NC-contacts-in-series chain like the Fagor e-stop chain. Confirmed only by reading H1-01 from the VFD keypad and tracing the orange "1"/"2" wires through the cabinet.

**Fault reset (terminal 4):**
- Orange "3" wire on terminal 4. Closing 4↔11 resets a latched VFD fault. The OEM may have wired this to a CNC PLC output for automatic reset on demand.

**Terminal 11 common detail:**
- Three orange wires land on terminal 11: a "1" and "2" crimped together, plus a separate second "1".
- The crimped "1+2" pair is likely the shared return for terminals 1 and 2 (forward/reverse run).
- The separate "1" is the partner of terminal 3's "2" — that's its own external loop.
- Two "1"s on the same common terminal: one is part of the run-command return path, the other is part of the fault/permissive loop. Same label but different circuits — the labels are local to each circuit and converge here at the common.

---

## Topology Analysis — Analog Spindle Speed Command

The spindle speed command is on cable labelled "7," a 4-conductor shielded cable (2 red + 2 black + shield) plus presumably its drain.

- **Source**: Fagor CNC analog output (X8 connector, spindle pair per MPG P007=10 main spindle).
- **Signal side (red ×2)** → terminal 13 (master frequency ref voltage, ±10 V, 20 kΩ).
- **Return / 0 V side (black ×2)** → terminal 17 (control common).
- **Shield** → terminal 12 (single-sided ground at VFD end; floats at CNC end).

The VFD reads voltage between terminals 13 and 17 as the speed command:
- 0 V = stopped.
- +10 V = full forward speed.
- −10 V = full reverse speed (if bipolar config enabled).

Doubling up two conductors on each terminal (rather than using one signal + one return on different terminals) is unusual. Possible explanations: the OEM used a 4-conductor cable when only 2 conductors were strictly needed and just parked the extras on the same terminals, or the doubled-up pairs slightly lower the resistance of the long cable run between the CNC and the VFD.

**Shield ground scheme:**
- Shield lands on terminal 12 at the VFD end.
- Terminal 12 is internally bonded to terminal 17 (signal common) inside the VFD.
- Terminal 12 is externally bonded to the cabinet ground bus via the green wire (verified — when the green wire is removed, no continuity from terminal 12 to G).
- Other end of the shield (at the CNC) is left floating — single-point ground at the VFD end only.
- This is the standard noise-rejection scheme: signal common and shield are at the same potential at the VFD, single earth point prevents ground loops, shield carries no ground-loop current.

---

## To-Do / Trace List

The following need physical tracing to fully reconstruct the wiring:

1. **Brown wire on terminal 1** — trace back to confirm direct connection from Fagor PLC output `SPIN-CW O3` (X10 pin 3) vs. via an interposing relay.
2. **Red wire on terminal 2** — same as above for `SPIN-CCW O5` (X10 pin 4).
3. **Orange "1" and "2" wires on terminal 3 / terminal 11** — find the contact in the loop and identify which relay it belongs to. Determine whether the loop is intentionally always-closed (permissive chain) or has an active contact that opens under specific fault conditions.
4. **Orange "3" wire on terminal 4** — trace back to whatever signal/PLC output drives the VFD fault reset.
5. **Second white wire on terminal 10** — trace to identify the 24 VDC supply source for the running/fault feedback network.
6. **Blue wire on terminal 9** — trace back to the CNC PLC input that reads "VFD running" feedback.
7. **Yellow wire on terminal 18** — trace back to the CNC PLC input that reads "VFD faulted" signal.

## VFD Parameters Worth Reading (for completeness of OEM intent)

These parameters define the actual function of multi-function terminals on this specific VFD. Reading them from the keypad would resolve a lot of the OEM-intent ambiguity:

- **H1-01** — function assignment for terminal 3 (currently named "external fault input" by default; may be reassigned to a permissive / safety chain function).
- **H1-02** — function assignment for terminal 4 (currently named "fault reset" by default).
- **H2-01** — function assignment for terminals 9/10 (currently named "during running" by default).
- **B1-01** — reference source (where the frequency reference comes from: digital operator, terminal 13/14, serial, option card, EWS).
- **B1-02** — run source (where the run command comes from: digital operator, terminal, serial, option card, EWS).
