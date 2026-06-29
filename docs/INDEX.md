# Documentation Index — `/docs/`

Everything documentation-related for the **ned** mill. Organized into one folder
per vendor/topic; your physical wiring traces are grouped under `tracing/`.

> **Machine components (models / ratings): [`components.md`](components.md) — the
> single source of truth.** Detail lives there only; everything else references a
> part by its key, `[cmp:<key>]`, and does not restate specs.

## Folder map

| Folder | Contents |
|---|---|
| [`tracing/`](tracing/) | **Your physical wiring traces** (cabinet, Fagor connectors, pendant, VFD terminals) + the wiring→HAL guide |
| [`fagor/`](fagor/) | Fagor 8055 CNC manuals (PDF + text extracts) |
| [`hqd/`](hqd/) | HQD electric spindle + swivel-head spec sheets |
| [`servo/`](servo/) | Servo drives — Yaskawa (LinuxCNC target) + legacy Servo Dynamics SDSM |
| [`vfd/`](vfd/) | Spindle VFDs — Saftronics VG5 (legacy) + Mollom G75 (replacement) |
| [`mesa/`](mesa/) | Mesa FPGA cards (7I97T/7I84U/7I85S) + card-selection notes + shopping list |
| [`linuxcnc/`](linuxcnc/) | Offline mirror of the LinuxCNC HAL manual + driver man pages |
| [`plans/`](plans/) | Forward-looking bring-up plans (numbered; superseded ones kept) |

Conventions:
- PDFs are texified — searchable plain-text extracts live in each folder's `text/` subfolder.
- The LinuxCNC HAL/INI config itself lives **outside** docs at [`../configs/ned/`](../configs/ned/) (`ned.hal`, `ned.ini`).
- Mesa **firmware bitfiles** live **outside** docs at [`../firmware/`](../firmware/) — see its `README.md`. (Note: the `7i97/` set there is the non-T `7i97.zip`, WRONG family for our 7I97T; correct one is `7i97t.zip`.)
- Superseded SPI-route card manuals (7C81/7I76/7I77) are parked in [`../trash/unrelated_cards/`](../trash/unrelated_cards/).

---

## Conventions Used in the Wiring `.md` Files

| Pattern | Meaning |
|---|---|
| **`R<n>`** | Relay number n (user's labelling). `R0` is the Deltrol contactor; `R1`–`R10` are multi-pole relays. |
| **`R<n><row><col>`** (R1–R10) | Terminal on a 4-pole relay. Rows: **A = NO**, **B = NC**, **C = coil** (C1,C2), **D = COM**. Cols 1–4. e.g. `R3B4`. |
| **`R0<row><col>`** | R0 contactor: **A = coil**, **B = switched contact**. Only A1,A2,B1,B2. |
| **`*<n>`** | Cabinet screw terminal n. e.g. `*38` = VFD-fault to CNC. |
| **`X<m>/pin<p>`** | Pin p on Fagor connector X<m>. e.g. `X10/pin3` = SPIN-CW. |
| **`VG5/<n>`** | Saftronics VG5 control terminal n. |
| **`Mollom/<id>`** | Mollom G75 terminal (S1–S5, COM, AI2, TA/TB/TC, Y1, etc.). |

**Status markers:** **✓** verified by tracing · **?** hypothesis · **—** not examined · **EMPTY** confirmed unwired.
**Wire vs Cable:** *wire* = one conductor; *cable* = a bundle in one jacket.

---

## `tracing/` — Wiring Traces (the main working docs)

| File | What it covers |
|---|---|
| [screw_terminals.md](tracing/screw_terminals.md) | All cabinet screw terminals `*1`–`*91`, one section each |
| [relays.md](tracing/relays.md) | All cabinet relays (R0 Deltrol, R1–R10), wiring per terminal |
| [field_devices.md](tracing/field_devices.md) | External sensors/switches/solenoids + which `*N` each lands on |
| [pendant.md](tracing/pendant.md) | Pendant (X6) — MPG handwheel (OLM 01 2DZ1 11A) + axis-select + e-stop; X6 pin map |
| [fagor_8055_axes.md](tracing/fagor_8055_axes.md) | Fagor AXES module — X8 (analog→drives), X9 (inputs), X10 (outputs), pin-by-pin |
| [fagor_8055_io.md](tracing/fagor_8055_io.md) | Fagor separate I/O module (X1, X2) |
| [vg5_vfd.md](tracing/vg5_vfd.md) | Saftronics VG5 terminal wiring (legacy) |
| [mollom_g75_vfd.md](tracing/mollom_g75_vfd.md) | Mollom G75 terminal wiring (replacement) |
| [wiring_to_hal_guide.md](tracing/wiring_to_hal_guide.md) | Translation guide: wiring traces → LinuxCNC HAL signal map |

## `fagor/` — Fagor 8055 CNC Manuals

| PDF | Text | Notes |
|---|---|---|
| [installation](fagor/fagor_8055_installation_manual_en.pdf) | [txt](fagor/text/fagor_8055_installation_manual_en.txt) | 706 pp. Wiring, params, e-stop, PLC I/O. V01.6X (machine runs V03.11/B) |
| [operating](fagor/fagor_8055_operating_manual_en.pdf) | [txt](fagor/text/fagor_8055_operating_manual_en.txt) | 246 pp. STATUS mode, param editing |
| [programming](fagor/fagor_8055_programming_manual_en.pdf) | [txt](fagor/text/fagor_8055_programming_manual_en.txt) | 468 pp. G-code, canned cycles |
| [windnc new features](fagor/fagor_windnc_v06_02_new_features_en.pdf) | [txt](fagor/text/fagor_windnc_v06_02_new_features_en.txt) | 2 pp |

Per-chapter + tagged text extracts (install/operating/programming) and the split scripts are in [`fagor/text/fagor_8055/`](fagor/text/fagor_8055/).

## `hqd/` — HQD Spindle / Swivel Head

| File | Text | Notes |
|---|---|---|
| [gdl65 5-axis spindle (ZH)](hqd/hqd_gdl65_5axis_electric_spindle_manual_zh.pdf) | [txt](hqd/text/hqd_gdl65_5axis_electric_spindle_manual_zh.txt) | Chinese. English: [translation.md](hqd/hqd_gdl65_5axis_electric_spindle_manual_en_translation.md) |
| [spindle motor catalog 2025-04](hqd/hqd_spindle_motor_catalog_202504.pdf) | [txt](hqd/text/hqd_spindle_motor_catalog_202504.txt) | 21 pp. **Local only — gitignored (57 MB)** |
| [HQ AC-D90-65 spec](hqd/hq_ac_d90_65_spec_sheet.pdf) | [txt](hqd/text/hq_ac_d90_65_spec_sheet.txt) | 5-axis swivelhead spec (bilingual) |
| [swivelhead 75 spec](hqd/swivelhead_75_spec_sheet.pdf) | [txt](hqd/text/swivelhead_75_spec_sheet.txt) | Swivelhead model 75 spec |

## `servo/` — Servo Drives

| File | Text | Notes |
|---|---|---|
| [Sigma-X SERVOPACK](servo/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.pdf) | [txt](servo/text/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.txt) | SGDXS analog/pulse — **our head drive** [cmp:head-servo] |
| [Sigma-X rotary motor](servo/yaskawa_sigma_x_rotary_servomotor_product_manual.pdf) | [txt](servo/text/yaskawa_sigma_x_rotary_servomotor_product_manual.txt) | SGMXJ/A/P/G motors — **our head motor** [cmp:head-servo] |
| [Servo Dynamics SDSM](servo/servo_dynamics_sdsm_manual.pdf) | [txt](servo/text/servo_dynamics_sdsm_manual.txt) | **Main-axis** analog drives [cmp:main-servo] (OCR'd) |

> Pruned to the models actually used: head = Yaskawa drive `SGDXS-2R8A00A` + motor
> `SGMXJ-04AUA6SC2` (see [cmp:head-servo] in [`components.md`](components.md)); main
> axes = SDSM [cmp:main-servo]. The Sigma-7 catalog and Sigma-7S SERVOPACK manuals
> were removed (not our hardware).

## `vfd/` — Spindle VFDs

| File | Text | Notes |
|---|---|---|
| [Saftronics VG5](vfd/saftronics_vg5_users_manual.pdf) | [txt](vfd/text/saftronics_vg5_users_manual.txt) | **Legacy** VFD |
| [Mollom G75](vfd/mollom_G75_AC_drive_manual.pdf) | [txt](vfd/text/mollom_G75_AC_drive_manual.txt) | Spindle VFD [cmp:vfd] (replaces the VG5) |
| [mollom_facts.md](vfd/mollom_facts.md) | — | Model decode, single-phase derate, VG5→Mollom migration wiring + params |

## `mesa/` — Mesa FPGA Cards (the chosen LinuxCNC hardware)

| File | Text | Notes |
|---|---|---|
| [7I97T manual](mesa/mesa_7i97t_manual.pdf) | [txt](mesa/text/mesa_7i97t_manual.txt) | [cmp:mesa-7i97t]. Jumpers W11/W12 (IP), W21/W22 (DB25), W23 (sserial term) |
| [7I84U manual](mesa/mesa_7i84u_manual.pdf) | [txt](mesa/text/mesa_7i84u_manual.txt) | [cmp:mesa-7i84u]. TB1 power 8–32 V; W1 (VIN src), W3 (operate/setup) |
| [7I85S manual](mesa/mesa_7i85s_manual.pdf) | [txt](mesa/text/mesa_7i85s_manual.txt) | [cmp:mesa-7i85s]. 5V via own terminal; W3 (cable/aux 5V) |
| [01_albersx_mesa_guide.md](mesa/01_albersx_mesa_guide.md) | — | Mesa card-selection guide (general) |
| [02_linuxcnc_forum_mesa_guide.md](mesa/02_linuxcnc_forum_mesa_guide.md) | — | Forum card-selection guide |
| [fpga_cards_listing.md](mesa/fpga_cards_listing.md) | — | Mesa FPGA card listing |
| [products_fetched.md](mesa/products_fetched.md) | — | Fetched Mesa product pages |

## `linuxcnc/` — LinuxCNC Software Docs (offline mirror)

- [README.md](linuxcnc/README.md) — index of the mirror
- [`hal/`](linuxcnc/) — the whole HAL Manual (intro, basic-hal, tutorial, rtcomps, components, canonical-devices, hal-examples, halui-examples, comp, halmodule, halshow, haltcl, tools, twopass, parallel-port, general-ref) — each as `.md` (grep-able) + `.html` (raw)
- [`man/`](linuxcnc/man/) — `hostmot2.9.md`, `hm2_eth.9.md` (authoritative Mesa pin/param names)

---

## Searching manuals

```bash
cd ~/Documents/docs
grep -in "external fault" vfd/text/mollom_G75_AC_drive_manual.txt
grep -in "encoder" mesa/text/mesa_7i97t_manual.txt
```

## Adding a new manual

1. Drop the PDF in the right vendor/topic folder under `docs/` (make a new folder if it's a new group with >1 item).
2. Texify: `pdftotext -layout <folder>/<name>.pdf <folder>/text/<name>.txt` (or `gs -sDEVICE=txtwrite`).
3. Add a row to the matching table above.
