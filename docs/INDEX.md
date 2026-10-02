# Documentation Index — `/docs/` — Machining: running ned as built

**Control, wiring, setup, calibration and maintenance notes moved to Controls on
2026-10-01 (operator ruling).** They live at `~/Documents/controls/` (`docs/`,
`firmware/`, `fagor8055/`, `staging/`, `unsorted/`, `gui.md`) under the same
relative paths. Ask Controls by description; do not hold copies. Machine FACTS
Machining needs to check a program are published to `~/418ops/machine/`
(`limits.json`, `kinematics.json`, `tool_table.json`, `fixtures.json`).

| Doc | What |
|---|---|
| [gcode_rules.md](gcode_rules.md) | ned g-code rules |
| [optimum_fs.md](optimum_fs.md) | **the only feeds and speeds source** — material x operation x tool, the effective-feed method, and how a number here gets set |
| [fusion_tool_mapping.md](fusion_tool_mapping.md) | tool table <-> Fusion 360 library |
| [fixtures/](fixtures/) | fixtures and setup records |
| [tool_library/](tool_library/) | tool table export (json, csv) |
| [admission.md](admission.md) | the joint-travel check before every run (numbers from ~/418ops/machine/) |
| [todo.md](todo.md) | run-side to-do: rotary roughing strategy, collet engagement warning |
