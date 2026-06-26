# Fagor 8055 Backup — 2026-06-23 (via WinDNC)

Full WinDNC pull of the Fagor 8055 controller on the Motionmaster mill. Captured before any HAL bring-up / SD-card hard-drive replacement work, so this is the **ground-truth OEM state** of the controller as last commissioned.

Source: WinDNC v6.02 → `WORK/` directory pulled to PC, then copied here.
Total files: 65 (including 2 subdirectories: `PLC/` and `USER/`).

---

## Machine Parameter Tables (no extension)

These are the configuration that defines machine behavior — kinematics, axis limits, gains, spindle range, etc. Restore-able to a fresh Fagor 8055 to rebuild this specific machine.

| File | What it is | Notes |
|---|---|---|
| **MPG** | **General machine parameters** | P000-Pxxx — axis assignments (P000=1, P001=2, P002=3, P003=6 = X,Y,Z,W), I/O config, comms, etc. |
| **MX1** | Machine parameters AXIS 1 | per-axis: limits, INPUT_SCALE, gains, REFSHIFT, etc. |
| **MX2** | Machine parameters AXIS 2 | same |
| **MX3** | Machine parameters AXIS 3 (= **Z** per MPG P002=3) | Z-axis REFSHIFT (P047) = **−0.25000 mm** |
| **MX4** | Machine parameters AXIS 4 | |
| **MX5** | Machine parameters AXIS 5 | |
| **MX6** | Machine parameters AXIS 6 | |
| **MX7** | Machine parameters AXIS 7 | |
| **MPS** | Main spindle machine parameters | spindle range (P002 = 18000 RPM max), gear ratios, S-output config |
| **MS2** | Auxiliary spindle machine parameters | |
| **MPX** | Auxiliary M-function machine parameters | |
| **MP1** | PLC machine parameters | |
| **MP2** | PLC machine parameters (continued) | |

## Compensation Tables (no extension)

Per-axis precision corrections measured during commissioning.

| File | What it is |
|---|---|
| **ML1** | Leadscrew error compensation, X axis (X position → EX error pairs) |
| **ML2** | Leadscrew error compensation, Y axis |
| **ML3** | Leadscrew error compensation, Z axis |
| **ML4** | Leadscrew error compensation, W axis |
| **LP0** – **LP6** | Per-axis leadscrew parameter tables (likely zero-init / unused; verify if needed) |
| **MC1** | Cross-axis compensation table (Y position → Z error — Y droop correction) |

## Tool & Setup Tables (no extension)

| File | What it is |
|---|---|
| **TLF** | Tool table (T-number → D-number / F-family assignment) |
| **TO** | Tool offsets table (D-number → R, L, I, K dimensions) |
| **TMZ** | Tool magazine occupancy (carousel position → T-number) |
| **ORG** | Work coordinate system origins (G54, G55, G56, …) — currently has values for G54 and G55 |
| **AUM** | Auxiliary M-function → PLC subroutine mapping (M6→S9001, M10→S9002, M11→S9011, etc.) |
| **GUP** | General User Parameters (P100+, user-defined arithmetic) |
| **HDE** | Hardware / version diagnose info |

## PLC

| File | What it is |
|---|---|
| **PLC_PRG.PIM** | **PLC source program** — the OEM ladder/sequential logic that defines what every input/output does. This is the most machine-specific file — losing this loses the OEM integration. |
| **PLC_MSG.PIM** | PLC user messages (text displayed by the PLC during operation) |
| **PLC_ERR.PIM** | PLC error messages (text for OEM-defined faults) |
| **PLC/** | Subdirectory (additional PLC artifacts) |

## User Programs (PIM files, numbered)

User-saved part programs and subroutines:

| File | Name (from header) |
|---|---|
| 000001.PIM | XFOLLOW |
| 000007.PIM | RESURFACE SOFTJAWS |
| 000008.PIM | SURFACE PLASTIC |
| 000009.PIM | SURFACE BLOCK |
| 000011.PIM | SURFACE PLASTIC |
| 000666.PIM | TESTAIR |
| 055555.PIM | USER PROGRAM |
| 100906.PIM | 100906 |
| 555555.PIM | (untitled) |
| 555556.PIM | HOME |
| 559999.PIM | GOODNIGHT |
| 569999.PIM | WARMUP |
| 999990.PIM | TableFace |
| 999991.PIM | A7995S1 |
| 999992.PIM | A7995S2 |
| 999994.PIM | SUBROUTINES |
| 999995.PIM | MANUAL TOOL CHANGE |
| 999996.PIM | M-CODES |
| 999997.PIM | TOOLLEN |
| 999998.PIM | TOOLSET |
| 999999.PIM | TOOL CHNG & REFEREN |

## Screen Panels & Simulation Files

| File pattern | What it is |
|---|---|
| **001.PAN, 002.PAN** | OEM custom screen panels |
| **000.SIM – 007.SIM** | Simulation / graphics files |

## Subdirectories

- **USER/** — user file area (`PRG`, `KEY`, `T`, `TAB`, `PAN`, `P` subdirs)
- **PLC/** — additional PLC artifacts

---

## What This Backup Does NOT Capture

- Fagor system firmware / OS (`/SYSTEM`-level files not exposed to WinDNC)
- Bootloader / BIOS
- Raw disk image of the CF or hard drive (would require physical pull + `dd`)
- RAM state (volatile, rebuilds on power-up)

For full disaster recovery this WinDNC pull covers the **OEM integration layer** (PLC, parameters, programs, tool tables, compensation). To also recover from a dead hard drive you'd need a sector-by-sector image done separately by pulling the drive.

## Key Reference Values Already Extracted

| Where | Value | Meaning |
|---|---|---|
| MX3 P047 (REFSHIFT, Z axis) | **−0.25000 mm** | Z encoder index → home offset |
| MPS P002 (spindle max RPM) | 18000 | Main spindle redline |
| MPG P000–P003 (axis assignment) | 1, 2, 3, 6 | Logical X=1, Y=2, Z=3, W=6 mapped to physical AXIS1–AXIS4 |
