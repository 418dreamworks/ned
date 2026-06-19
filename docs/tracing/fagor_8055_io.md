# Fagor 8055 — Separate I/O Module

The machine has a **separate Fagor I/O module** in addition to the AXES module. This was a 32 in / 24 out expansion module.

Connector layout: **X1, X2** carry inputs in the I65+ range; outputs are in the O33+ range.

## Status

The OEM PLC source (`PLC_PRG.PIM`) **does not reference any signals on the I/O module**. All PLC DEF statements are for I1–I40 and O1–O24 (both ranges entirely within the AXES module). The I/O module is **physically wired but functionally inert** as far as the OEM software is concerned.

## Known wires landing here

| Wire | Lands at | OEM PLC behavior | Status |
|---|---|---|---|
| `44mys` | X1 or X2 (specific pin not yet identified) | No PLC DEF — input not assigned a function. The wire is connected to an input pin but the PLC ignores it. | ✓ NotesToSelf note 15 |
| `45mys` | X1 or X2 (specific pin not yet identified) | Same — pre-wired but unused | ✓ NotesToSelf note 12 |

## Implication for LinuxCNC migration

When migrating to LinuxCNC, these pre-wired inputs become available for use (if LinuxCNC can address them via whatever bus the I/O module uses — likely a specific Fagor proprietary protocol that won't be reusable). The hardware itself (the pre-wired wires to the terminals) can be salvaged and connected to the new Mesa cards.
