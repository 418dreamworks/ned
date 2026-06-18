# Cabinet Wiring Reference

Living documentation of the Motionmaster mill's control cabinet. Organised by *kind of thing*: one file per category of components.

## Structure

```
cabinet/
├── README.md              ← this file (index + conventions)
├── screw_terminals.md     ← all *N cabinet screw terminals
├── relays.md              ← all R<n> cabinet relays
└── components/
    ├── fagor_8055_axes.md ← Fagor 8055 AXES module (X8, X9, X10 connectors)
    ├── fagor_8055_io.md   ← Fagor 8055 I/O module (separate from AXES)
    ├── vg5_vfd.md         ← Saftronics VG5 VFD (legacy — being removed)
    ├── mollom_g75_vfd.md  ← Mollom G75 VFD (replacement, planned wiring)
    └── spindle.md         ← Colombo spindle junction box and sensors
```

When new components/relays/terminals are discovered, add a row to the relevant file. When a wire is traced from one end to another, both ends should appear in their respective files (e.g., the brown wire from X10 pin 3 to R6 coil appears in `components/fagor_8055_axes.md` under X10/pin3 AND in `relays.md` under R6).

## Terminology

- **Wire** = a single conductor. (Examples: "the brown wire on R6A2", "the green wire", "the blue wire to R1C2".)
- **Cable** = a bundle of wires inside an NM-type conduit or jacket. (Example: cable "7" carries 2 red wires + 2 black wires + a shield from the Fagor X8 connector to the VFD.)

If the user says "wire" but the context suggests a multi-conductor bundle, or "cable" for a single conductor, the writer should flag the ambiguity rather than guess.

## Conventions

| Pattern | Meaning |
|---|---|
| **`R<n>`** | Relay number n (user's labelling on the cabinet relays) |
| **`R<n><row><col>`** | Specific relay terminal. Rows: **A = NO** contact, **B = NC** contact, **C = coil** (cols 1 and 2 only), **D = COM**. Example: `R6A2` = relay 6, NO contact, column 2. |
| **`*<n>`** | Cabinet screw terminal n on the main terminal block |
| **`X<m>`** | Fagor connector on the AXES module (X8, X9, X10) |
| **`X<m>/pin<p>`** | Specific pin on a Fagor connector |
| **`VG5/<n>`** | Saftronics VG5 VFD control-circuit terminal number |
| **`Mollom/<id>`** | Mollom G75 VFD terminal identifier (S1–S5, COM, AI2, TA, TB, TC, Y1, etc.) |

### Trace status markers

| Marker | Meaning |
|---|---|
| **✓** | Verified by physical tracing |
| **?** | Hypothesis (color/function match only — not traced) |
| **—** | Not yet examined |

## Related files

- `../NotesToSelf.md` — personal observations on the cabinet, machine wiring history, decisions made.
- `../VG5_wiring.md` — original VG5 trace document (historical; subsumed into the structured files in this folder but kept for narrative context).
- `../mollom_facts.md` — Mollom G75 spec sheet + migration wiring plan.
- `../../docs/INDEX.md` — manuals index.
