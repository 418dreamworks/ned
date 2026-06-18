# Fagor 8055 Manual Index

Three PDFs live in this folder, all Ref. 1402 / Soft V01.6x.

| PDF | Pages | Tagged text | Audience |
|---|---|---|---|
| `Fagor-CNC-8055-Installation-Manual-English.pdf` | 706 | `text/tagged.txt` | Installer / electrician — wiring, PLC, parameters, hardware |
| `Fagor-CNC-8055-Operating-Manual-English.pdf` | 246 | `text/operating_tagged.txt` | Operator — keyboard, screens, JOG, MDI, tables, utilities |
| `Fagor-CNC-8055-Programming-Manual-English.pdf` | 467 | `text/programming_tagged.txt` | Programmer — G/M codes, canned cycles, high-level language |

All three were converted with `pdftotext -layout`, then tagged with `===== PAGE n =====` between every PDF page. **PDF page = printed manual page** in all three.

## Quick search recipes

```bash
# Search across all three manuals at once
grep -n "your_pattern" text/tagged.txt text/operating_tagged.txt text/programming_tagged.txt

# Jump to a specific manual page (e.g. p.137 of installation manual)
awk '/^===== PAGE 137 =====/,/^===== PAGE 138 =====/' text/tagged.txt

# Find a PLC mark by number
grep -n "M5100\|LIMIT+1" text/tagged.txt

# Find a G-code in the programming manual
grep -n "G74\|G84\|G87" text/programming_tagged.txt

# Find an operator-panel feature
grep -ni "softkey\|key\|jog" text/operating_tagged.txt
```

---

## Installation Manual — chapter map

| File | Pages | Chapter |
|---|---|---|
| `ch00_frontmatter.txt` | 1-26 | Cover, TOC, version history, safety |
| `ch01_8055_config.txt` | 27-72 | **Ch 1** — 8055 hardware: CPU, axes modules (Vpp, Vpp SB), I/O module, monitors, operator panels |
| `ch02_8055i_config.txt` | 73-107 | **Ch 2** — 8055i hardware: structure, connectors, operator panel |
| `ch03_heat.txt` | 108-112 | **Ch 3** — Heat dissipation |
| `ch04_remote_modules.txt` | 113-130 | **Ch 4** — Remote CAN/CANopen I/O modules |
| `ch05_machine_power.txt` | 131-144 | **Ch 5** — Machine and power connection, **emergency I/O wiring** |
| `ch06_machine_parameters.txt` | 145-283 | **Ch 6** — Machine parameters (general, axis, spindle, drive, PLC, tables) |
| `ch07_concepts.txt` | 284-411 | **Ch 7** — Concepts: axes, JOG, handwheels, feedback, home, software limits, M/S/T transfer, spindles, emergency, digital servo, safety |
| `ch08_plc_intro.txt` | 412-420 | **Ch 8** — PLC introduction |
| `ch09_plc_resources.txt` | 421-441 | **Ch 9** — PLC resources |
| `ch10_plc_programming.txt` | 442-459 | **Ch 10** — PLC programming language |
| `ch11_cnc_plc_comm.txt` | 460-471 | **Ch 11** — CNC-PLC communication |
| `ch12_logic_io.txt` | 472-510 | **Ch 12** — Logic CNC inputs and outputs (the big M-mark reference) |
| `ch13_internal_vars.txt` | 511-557 | **Ch 13** — Internal CNC variables (V.MPG.xxx, V.G.xxx, etc.) |
| `ch14_axes_from_plc.txt` | 558-569 | **Ch 14** — Controlling axes from the PLC channel |
| `ch15_custom_screens.txt` | 570-584 | **Ch 15** — Customizable screens |
| `ch16_config_workmode.txt` | 585-607 | **Ch 16** — Configurable work mode (OEM customization) |
| `ch17_plc_example.txt` | 608-620 | **Ch 17** — PLC programming example |
| `appendix.txt` | 621-706 | **Appendices A-Q** — Tech specs, **variable summary (F)**, **PLC commands summary (G)**, **PLC I/O summary (H)**, key codes (J), key inhibiting (L), **machine parameter setting chart (M)**, M function chart (N), leadscrew/cross comp tables, maintenance |

## Operating Manual — chapter map

| File | Pages | Chapter |
|---|---|---|
| `op_ch00_frontmatter.txt` | 1-25 | Cover, TOC, product description |
| `op_ch01_general_concepts.txt` | 26-35 | **Ch 1** — Part programs, monitor info layout, **keyboard layout**, **operator panel layout** |
| `op_ch02_operating_modes.txt` | 36-43 | **Ch 2** — Help system, software update, KeyCF (CompactFlash) |
| `op_ch03_ethernet.txt` | 44-52 | **Ch 3** — Operations via Ethernet (remote HDD, WinDNC) |
| `op_ch04_execute_simulate.txt` | 53-83 | **Ch 4** — Execute / Simulate: block search, display modes, MDI, tool inspection, graphics, single block |
| `op_ch05_edit.txt` | 84-116 | **Ch 5** — Editor: CNC-language, TEACH-IN, interactive editor, profile editor, find/replace |
| `op_ch06_jog.txt` | 117-128 | **Ch 6** — **JOG**: continuous, incremental, path-jog, handwheel modes (general/path/feed/additive), spindle movement |
| `op_ch07_tables.txt` | 129-137 | **Ch 7** — Zero offsets table, tool magazine, tool table, tool offset table, parameters tables |
| `op_ch08_utilities.txt` | 138-151 | **Ch 8** — Programs/files: directory, copy, delete, rename, protections, explorer |
| `op_ch09_status.txt` | 152-161 | **Ch 9** — Status: CNC backup/restore, DNC, Sercos, CAN |
| `op_ch10_plc.txt` | 162-192 | **Ch 10** — PLC: edit, compile, monitor, save/restore, logic analyzer |
| `op_ch11_screen_editor.txt` | 193-207 | **Ch 11** — Screen editor: user pages, graphic elements, texts |
| `op_ch12_machine_params.txt` | 208-215 | **Ch 12** — Machine parameter tables, M-function, leadscrew, cross compensation |
| `op_ch13_diagnosis.txt` | 216-234 | **Ch 13** — Diagnosis: config, hardware test, **circle geometry test**, **oscilloscope**, user, hard disk |
| `op_ch14_telediagnosis.txt` | 235-246 | **Ch 14** — CNC-PC communication, telediagnosis |

## Programming Manual — chapter map

| File | Pages | Chapter |
|---|---|---|
| `pg_ch00_frontmatter.txt` | 1-26 | Cover, TOC |
| `pg_ch01_general_concepts.txt` | 27-32 | **Ch 1** — Part programs, DNC, communication protocols |
| `pg_ch02_creating_program.txt` | 33-36 | **Ch 2** — Program structure (header, block, end) |
| `pg_ch03_axes_coords.txt` | 37-52 | **Ch 3** — Axes, plane selection (G16-G19), absolute/incremental (G90/G91), coordinate types, **work zones** |
| `pg_ch04_reference_systems.txt` | 53-60 | **Ch 4** — Reference points, **G74 home search**, G53 (machine zero), G92 (preset), G54-G59/G159 (zero offsets), G93 (polar origin) |
| `pg_ch05_iso_code.txt` | 61-80 | **Ch 5** — ISO programming: G-functions, feedrate (G94/G95/G96/G97), spindle (S, G28/G29, G30), tool (T, D), M functions |
| `pg_ch06_path_control.txt` | 81-104 | **Ch 6** — Path control: G00, G01, G02/G03, G06, G08, G09, helical, threading (G33/G34), **move to hardstop (G52)**, tangential control (G45) |
| `pg_ch07_additional_prep.txt` | 105-127 | **Ch 7** — G04 (dwell/block-prep interrupt), G07/G05/G50 (corners), G51 (look-ahead), G10-G14 (mirror), G72 (scaling), G73 (rotation), G77/G78 (electronic coupling), G28/G29 (axes toggle) |
| `pg_ch08_tool_comp.txt` | 128-143 | **Ch 8** — Tool radius compensation (G40/G41/G42), collision detection |
| `pg_ch09_canned_cycles.txt` | 144-200 | **Ch 9** — Canned cycles: G69, **G81 drill**, G82 drill+dwell, G83 deep-hole, **G84 tap**, G85 ream, G86 boring, **G87 rect pocket**, G88 circ pocket, G89, G210 bore milling, G211/G212 thread milling |
| `pg_ch10_multiple_machining.txt` | 201-219 | **Ch 10** — Multiple machining: G60 (line), G61 (rect), G62 (grid), G63 (circle), G64 (arc), G65 (arc-chord) |
| `pg_ch11_irregular_pocket.txt` | 220-280 | **Ch 11** — Irregular pocket canned cycle (2D / 3D) |
| `pg_ch12_probing.txt` | 281-331 | **Ch 12** — Probing G75/G76 and PROBE 1-12 canned cycles |
| `pg_ch13_high_level_lang.txt` | 332-384 | **Ch 13** — High-level language: lexical, variables, constants, operators, expressions |
| `pg_ch14_program_control.txt` | 385-410 | **Ch 14** — Program control: assignment, display, enable/disable, flow control, subroutines, probe, interrupt, kinematics |
| `pg_ch15_coord_transform.txt` | 411-432 | **Ch 15** — Coordinate transformation: inclined plane, G47 tool coords, G48 TCP |
| `pg_ch16_angular_transform.txt` | 433-467 | **Ch 16** — Angular transformation of incline axis |

---

## Key topics already explored

### Homing
- Operating Manual **Ch 6 (pp.117-128)** — JOG mode (operator's view)
- Install Manual **p.155** — JOG-mode homing: softkey `ALL AXES` homes all axes per home-order parameter; runs REFPSUB (P34) subroutine if set
- Install Manual **p.326-327** (ch07) — Home search procedure, REFDIREC, REFEED1, REFEED2, REFVALUE, REFPULSE, DECEL signals
- Programming Manual **p.54** — G74 machine reference search (programmable form)

### Hard limits, software limits, emergency
- Install Manual p.135 — Software limits set via a.m.p. LIMIT+ (P5) and LIMIT- (P6) after referencing
- Install Manual **p.137** — **Emergency I/O wiring.** /EMERGENCY = I01 of PLC at 24V. Loss → EXTERNAL EMERGENCY ERROR, all drive enables deactivated, all velocity commands cancelled. Cabinet typically drops /EMERGENCY on: E-stop pressed, **travel limit of any axis exceeded**, drive malfunction.
- Install Manual p.334 — Software travel limits (sec 7.6.4)
- Install Manual p.354-355 — Treatment of emergency signals (/EMERGENCY STOP, /EMERGENCY OUTPUT, /EMERGEN M5000, /ALARM M5507)
- Install Manual **p.481** — **LIMIT±n PLC marks** set by PLC; CNC stops axis feed + spindle. **In JOG mode, the axis that overran its limit can be moved in the opposite direction back into range** (no special override needed — just JOG away from the switch). Only works if drives still enabled (Path B wiring).
- Install Manual p.484 — **LIM1OFF..LIM7OFF marks** (M5115, M5165, ...) override SOFTWARE limits only — NOT hardware
- Install Manual p.484 — DRENA trailing edge cuts drive power, motor loses torque (coasts). SPENA trailing edge brakes motor while maintaining torque, then power off.

### PLC marks already noted (axis = N where mark = base + 50*(N-1))
- LIMIT+1=M5100, LIMIT-1=M5101 ; LIMIT+2=M5150, LIMIT-2=M5151 ; LIMIT+3=M5200, LIMIT-3=M5201 ; ... LIMIT+7=M5400, LIMIT-7=M5401
- DECEL1=M5102, DECEL2=M5152, ..., DECEL7=M5402 — home-reference deceleration switches
- INHIBIT1=M5103, ..., INHIBIT7=M5403 — block axis motion
- MIRROR1=M5104, ..., MIRROR7=M5404
- SWITCH1=M5105, ..., SWITCH7=M5405 — toggle vel cmd between two axes on one drive
- DRO1=M5106, ..., DRO7=M5406 — DRO mode (open-loop, ignore following error)
- SERVO1ON=M5107, ..., SERVO7ON=M5407 — close position loop
- AXIS+1=M5108, AXIS-1=M5109, ..., AXIS+7=M5408, AXIS-7=M5409 — jog axis from PLC
- SPENA1=M5110, DRENA1=M5111, ..., SPENA9=M6160, DRENA9=M6161 — drive speed enable / drive enable
- SYNCHRO1=M5112, ..., SYNCHRO7=M5412
- ELIMINA1=M5113, ..., ELIMINA7=M5413 — hide axis but keep controlling
- SMOTOF1=M5114, ..., SMOTOF7=M5414 — cancel SMOTIME (P58) filter
- LIM1OFF=M5115, ..., LIM7OFF=M5415 — ignore software limits
- MANINT1=M5116, ..., MANINT7=M5416 — additive handwheel
- DIFFCOM1=M5117, ..., DIFFCOM7=M5417 — gantry master/slave correction
- /EMERGEN = M5000 — PLC tells CNC to stop everything (active low)
- /ALARM = M5507 — CNC tells PLC an emergency condition occurred (active low)

### Axis machine parameters already noted
- P5 LIMIT+ — software positive travel limit
- P6 LIMIT- — software negative travel limit
- P13 AXISCHG — axis feedback counting direction
- P17 DWELL — delay between SERVOON check and ENABLE output
- P26 LOOPCHG — velocity command output sign
- P32 REFPULSE — type of marker pulse Io for home search
- P33 REFDIREC — home search direction
- P34 REFEED1 — fast home approach feedrate
- P35 REFEED2 — slow home feedrate
- P36 REFVALUE — coordinate at home reference
- P37 MAXVOLT — velocity command voltage at max feedrate (default 9.5V)
- P38 G00FEED — maximum G00 feedrate
- P46 ACFGAIN — value introduced in V01.60
- P58 SMOTIME — smoothing filter time
- P86 OPLDECTI — introduced in V01.08

### Path A vs Path B (limit-switch wiring on this machine)
- **Path A**: limit switch in series with cabinet e-stop chain → drops /EMERGENCY → all drive enables off → Z falls if no brake/counterbalance. **No JOG recovery possible** — drives are dead.
- **Path B**: limit switch to PLC input only → PLC sets LIMIT+n/LIMIT-n mark → CNC stops feed but drives stay enabled → **JOG away from switch recovers**.
- On this machine: **Z = Path B**, **X (and Y presumed) = Path A**. See `project_machine_limit_switches.md`.

### Useful page anchors (Installation Manual)
- p.67-69 — Operator panel
- p.131-132 — Digital (24V) / analog (±10V) I/O electrical specs
- p.300-302 — JOG mode and axis-to-JOG-key mapping
- p.303-308 — Handwheel operation (standard, path, feed, additive)
- p.370-373 — Fagor handwheels HBA / HBE / LGB wiring
- p.412+ — PLC introduction (Ch 8)
- p.643 — Appendix G: PLC commands summary
- p.647 — Appendix H: PLC I/O summary (the master mark reference)
- p.685 — Appendix M: machine parameter setting chart
