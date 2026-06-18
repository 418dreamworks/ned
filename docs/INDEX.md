# Documentation Index — `/docs/`

Everything documentation-related lives in this folder. Conventions:
- All PDFs are texified — searchable plain-text extracts in `text/`.
- Mesa LinuxCNC stuff is in `mesa/` (the one subfolder that's worth its own).
- Everything else is flat in `docs/`.

When a new manual or doc arrives in `/unsorted/`, move it here.

## Conventions Used in the Wiring `.md` Files

| Pattern | Meaning |
|---|---|
| **`R<n>`** | Relay number n (user's labelling on the cabinet relays). `R0` is the Deltrol relay; `R1`–`R10` are the other instances. |
| **`R<n><row><col>`** (R1–R10) | Specific terminal on a 4-pole multi-contact relay. Rows: **A = NO**, **B = NC**, **C = coil** (C1, C2 only), **D = COM**. Columns 1–4 are valid for rows A/B/D. Each relay has 14 terminals: A1–A4, B1–B4, C1–C2, D1–D4. Example: `R3B4` = relay 3, NC contact, column 4. |
| **`R0<row><col>`** | R0 is a **contactor** (Deltrol), not a multi-pole relay. Different convention: **A = signal (coil)**, **B = load (single-pole switched contact)**. Only 4 terminals: A1, A2, B1, B2. |
| **`*<n>`** | Cabinet screw terminal n on the main terminal block. Example: `*38` carries the VFD-fault signal to the CNC. |
| **`X<m>/pin<p>`** | Pin p on Fagor connector X<m>. Example: `X10/pin3` = SPIN-CW output. |
| **`VG5/<n>`** | Saftronics VG5 VFD control-circuit terminal n. |
| **`Mollom/<id>`** | Mollom G75 VFD terminal (S1–S5, COM, GND, AI2, TA, TB, TC, Y1, etc.). |

### Status markers (in tables)

| Marker | Meaning |
|---|---|
| **✓** | Verified by physical tracing |
| **?** | Hypothesis — function/color match only, not traced |
| **—** | Not yet examined |
| **EMPTY** | Physically inspected and confirmed unwired (no wire on this terminal) — distinct from "not yet examined" |

### Wire vs Cable

- **Wire** = a single conductor.
- **Cable** = a bundle of wires inside an NM conduit or jacket (example: cable "7" = 2 red + 2 black + shield).

---

## Wiring Documentation

The structured docs that organize the cabinet's wiring. These are the main working files.

| File | What it covers |
|---|---|
| [`screw_terminals.md`](screw_terminals.md) | All cabinet screw terminals `*1`–`*91`, one section per terminal |
| [`relays.md`](relays.md) | All cabinet relays (R0 = Deltrol, R1–R10), one section per relay, with wiring at each terminal |
| [`field_devices.md`](field_devices.md) | Sensors, switches, solenoids etc. outside the cabinet — each device's wires + which `*N` terminal each one lands on. Provides the second-endpoint accounting for traces that leave the cabinet. |
| [`wiring_to_hal_guide.md`](wiring_to_hal_guide.md) | Translation guide from the wiring docs to LinuxCNC HAL. For future Claude/human collaborators planning the migration to Mesa cards. |
| [`fagor_8055_axes.md`](fagor_8055_axes.md) | Fagor 8055 AXES module — X8 (analog), X9 (inputs), X10 (outputs + few inputs), pin-by-pin |
| [`fagor_8055_io.md`](fagor_8055_io.md) | Fagor 8055 separate I/O module (X1, X2) — wires connected but no OEM PLC reference |
| [`vg5_vfd.md`](vg5_vfd.md) | Saftronics VG5 VFD terminal wiring (legacy, being removed) |
| [`mollom_g75_vfd.md`](mollom_g75_vfd.md) | Mollom G75 VFD terminal wiring (replacement, planned) |
| [`mollom_facts.md`](mollom_facts.md) | Mollom G75 spec sheet, model decoding, single-phase derated setup, migration plan |

---

## Manuals — CNC Controller (Fagor 8055)

| PDF | Text extract | Notes |
|---|---|---|
| [fagor_8055_installation_manual_en.pdf](fagor_8055_installation_manual_en.pdf) | [text](text/fagor_8055_installation_manual_en.txt), [by chapter](text/fagor_8055/) | 706 pages. Wiring, parameters, e-stop circuit, PLC I/O specs. V01.6X manual — machine here runs V03.11/B firmware. |
| [fagor_8055_operating_manual_en.pdf](fagor_8055_operating_manual_en.pdf) | [text](text/fagor_8055_operating_manual_en.txt) | 246 pages. STATUS mode, parameter editing, SHIFT+RESET to apply parameter changes |
| [fagor_8055_programming_manual_en.pdf](fagor_8055_programming_manual_en.pdf) | [text](text/fagor_8055_programming_manual_en.txt) | 468 pages. G-code, canned cycles, parametric programming |
| [fagor_windnc_v06_02_new_features_en.pdf](fagor_windnc_v06_02_new_features_en.pdf) | [text](text/fagor_windnc_v06_02_new_features_en.txt) | 2 pages. WinDNC release notes |

## Manuals — VFDs

| PDF | Text extract | Notes |
|---|---|---|
| [saftronics_vg5_users_manual.pdf](saftronics_vg5_users_manual.pdf) | [text](text/saftronics_vg5_users_manual.txt) | 113 pages. **Legacy VFD** currently installed |
| [mollom_G75_AC_drive_manual.pdf](mollom_G75_AC_drive_manual.pdf) | [text](text/mollom_G75_AC_drive_manual.txt) | 68 pages. **Replacement VFD** (Mollom G75-2T-7R5-G-B) |

## Manuals — Yaskawa Servo Drives / Motors (LinuxCNC migration target)

| PDF | Text extract | Notes |
|---|---|---|
| [yaskawa_sigma7_catalog.pdf](yaskawa_sigma7_catalog.pdf) | [text](text/yaskawa_sigma7_catalog.txt) | 29 pages. Sigma-7 family catalog |
| [yaskawa_sigma_7s_servopack_analog_pulse_product_manual.pdf](yaskawa_sigma_7s_servopack_analog_pulse_product_manual.pdf) | [text](text/yaskawa_sigma_7s_servopack_analog_pulse_product_manual.txt) | 654 pages. Sigma-7S analog/pulse SERVOPACK (SGD7S). Manual SIEP S800001 26W |
| [yaskawa_sigma_xs_servopack_analog_pulse_product_manual.pdf](yaskawa_sigma_xs_servopack_analog_pulse_product_manual.pdf) | [text](text/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.txt) | 802 pages. Sigma-X SERVOPACK (SGDXS). Manual SIEP C710812 03I |
| [yaskawa_sigma_x_rotary_servomotor_product_manual.pdf](yaskawa_sigma_x_rotary_servomotor_product_manual.pdf) | [text](text/yaskawa_sigma_x_rotary_servomotor_product_manual.txt) | 304 pages. Sigma-X rotary servomotors (SGMXJ/A/P/G). Manual SIEP C230210 00H |
| [servo_dynamics_sdsm_manual.pdf](servo_dynamics_sdsm_manual.pdf) | (image-only, no text) | 87 pages. Legacy reference. Scan; would need OCR |

## Manuals — FPGA Cards / Mesa (LinuxCNC migration target)

| PDF | Text extract | Notes |
|---|---|---|
| [mesa_7c81_manual.pdf](mesa_7c81_manual.pdf) | [text](text/mesa_7c81_manual.txt) | 25 pages. Mesa 7C81 anything-I/O (Raspberry Pi GPIO) |
| [mesa_7i76_manual.pdf](mesa_7i76_manual.pdf) | [text](text/mesa_7i76_manual.txt) | 58 pages. Mesa 7I76 step/dir daughter card |
| [mesa_7i77_manual.pdf](mesa_7i77_manual.pdf) | [text](text/mesa_7i77_manual.txt) | 61 pages. Mesa 7I77 ±10V servo daughter card (analog servo systems) |
| [mesa_7i97t_manual.pdf](mesa_7i97t_manual.pdf) | [text](text/mesa_7i97t_manual.txt) | 45 pages. Mesa 7I97T standalone Ethernet analog servo interface (6× ±10V, 6× encoder, 16 in, 6 out). **+5V powered** via P3. Connectors: P3 (5V), P2 (DB25 expansion for 7I85), TB1/TB2 (encoders), TB3 (analog out), TB4 (isolated in + sserial RJ45 to 7I84), TB5 (isolated I/O). |
| [mesa_7i84_manual.pdf](mesa_7i84_manual.pdf) | [text](text/mesa_7i84_manual.txt) | 52 pages. Mesa 7I84 sserial I/O expansion (32 in, 16 out). RS-422 logic power (+5V, 30mA) comes from sserial RJ45 cable; TB1 needs external **5-32V field power** (VFIELDA, VFIELDB, VIN) for the field I/O drivers. |
| [mesa_7i85s_manual.pdf](mesa_7i85s_manual.pdf) | [text](text/mesa_7i85s_manual.txt) | 14 pages. Mesa 7I85S step/dir daughter card (4× step/dir, 4× encoder). DB25 to 7I97T's P2 expansion port. Default W3=UP → expects +5V from host card via DB25. **Default conflict with 7I97T**: 7I97T's W22 default DOWN disables breakout 5V; either flip 7I97T W22 UP, or flip 7I85S W3 DOWN and supply external +5V on P1. |

See [`mesa/`](mesa/) folder for additional notes, store pages, and shopping list.

## Manuals — Spindle / Tooling

| PDF | Text extract | Notes |
|---|---|---|
| [hqd_gdl65_5axis_electric_spindle_manual_zh.pdf](hqd_gdl65_5axis_electric_spindle_manual_zh.pdf) | [text](text/hqd_gdl65_5axis_electric_spindle_manual_zh.txt) | 19 pages. HQD GDL65 (Chinese). English translation: [hqd_gdl65_5axis_electric_spindle_manual_en_translation.md](hqd_gdl65_5axis_electric_spindle_manual_en_translation.md) |
| [hqd_spindle_motor_catalog_202504.pdf](hqd_spindle_motor_catalog_202504.pdf) | (image-only, no text) | 21 pages. HQD spindle motor catalog April 2025 |
| [hq_ac_d90_65_spec_sheet.pdf](hq_ac_d90_65_spec_sheet.pdf) | [text](text/hq_ac_d90_65_spec_sheet.txt) | 2 pages. HQ AC-D90-65 5-axis swivelhead spec (bilingual) |
| [swivelhead_75_spec_sheet.pdf](swivelhead_75_spec_sheet.pdf) | [text](text/swivelhead_75_spec_sheet.txt) | 4 pages. Swivelhead model 75 spec (bilingual) |

---

## How to Search Manuals Quickly

For any text-searchable manual, grep the `text/` folder:

```bash
cd /Users/tzuohann/Documents/Claude/ned/docs
grep -l "REFSHIFT" text/*.txt
grep -in "external fault" text/mollom_G75_AC_drive_manual.txt
grep -B 2 -A 5 "P1I" text/mesa_7i77_manual.txt
```

For image-only PDFs (`servo_dynamics_sdsm_manual.pdf`, `hqd_spindle_motor_catalog_202504.pdf`), OCR via tesseract:

```bash
brew install tesseract
pdftoppm -r 300 docs/SOMEFILE.pdf /tmp/page -png
for p in /tmp/page-*.png; do tesseract "$p" - >> docs/text/SOMEFILE.txt; done
```

---

## Adding a New Manual

1. Drop the PDF into `/unsorted/`.
2. Identify it, choose a canonical name (lowercase, words separated by underscores: `vendor_product_doc-type.pdf`).
3. Move it to `docs/`.
4. Run `pdftotext -layout docs/<name>.pdf docs/text/<name>.txt`.
5. Add a row to the appropriate table in this file.

## Folder Map at `ned/` Level (For Reference)

```
ned/
├── CLAUDE.md          ← project instructions (do not move)
├── docs/              ← THIS FOLDER — all documentation
├── fagor8055/         ← Fagor WinDNC software (install_remodnc.exe, windnc/)
├── labeled/           ← machine photos
├── trash/             ← archived/superseded files
└── unsorted/          ← download inbox — move files from here into docs/
```
