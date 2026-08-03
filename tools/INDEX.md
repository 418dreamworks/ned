# tools/ — READ THIS FIRST (and live/INDEX.md + groundtruth/INDEX.md)

Layout (operator, 2026-08-01):
- `tools/` root = **staging** — things being built/tried before they earn a
  home, plus the launcher. Keep it near-empty; an unorganized root is a bug.
- `tools/live/` = needed to RUN the machine (loaded/invoked every session).
- `tools/groundtruth/` = proven bench references for checking basic things.
- Trashed tools are in `trash/tools/` (recoverable; e.g. pso_home.sh, the
  head-zero capture tool, parked there until A/C calibration needs it).

## Files here

| File | Why it lives at root |
|---|---|
| `run5.sh` | THE launcher (USER runs it; never Claude). Starts PB via the qt_pb venv, resume y/N consent, auto-starts the live/ loggers. |

Everything else belongs in live/ or groundtruth/ — if something new lands
here, it is staging: finish it and move it, or trash it.
- `gcode_check.sh` — offline g-code validator: parses ned subroutines with LinuxCNC's own interpreter (rs274), no machine/HAL/motion. `--all` or `<subname> [args]`. REQUIRED before handing any routine to the operator (CLAUDE.md rule 18).
- `lcnc_session.sh` — prints ONLY the current PB session's slice of lcnc.log (ANSI stripped). Use this for machine evidence; `logs/term-*.log` contains my own terminal output and produces false matches (CLAUDE.md rule 19).
- `machine_idle.sh` — rule 21 gate: exit 0 if it is safe to write under configs/, 1 if a cycle is in flight. Asks the NML status buffer, never pgrep (which self-matches).
- `cfg_edit.sh` — the ONLY sanctioned way to edit configs/: gates on machine_idle, applies the edit, re-runs the scanner, fails as one unit (CLAUDE.md rule 21). Never Write/Edit configs/ directly.
