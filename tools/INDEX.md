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
| `brain_harness.py` | Execs `live/ned_brain.py`'s OWN text with the driver loop cut and hal/linuxcnc/GUI_LOG stubbed, so `do_inplace()` and friends can be triggered with fabricated state -- no machine, no motion. Point `REAL` at `git show <sha>:tools/live/ned_brain.py` to A/B a fix against the code it replaced; that is what separated real defects from guesses on 2026-08-08. |

Everything else belongs in live/ or groundtruth/ — if something new lands
here, it is staging: finish it and move it, or trash it.
- `gcode_check.sh` — offline g-code validator: parses ned subroutines with LinuxCNC's own interpreter (rs274), no machine/HAL/motion. `--all` or `<subname> [args]`. REQUIRED before handing any routine to the operator (CLAUDE.md rule 18).
- `lcnc_session.sh` — prints ONLY the current PB session's slice of lcnc.log (ANSI stripped). Use this for machine evidence; `logs/term-*.log` contains my own terminal output and produces false matches (CLAUDE.md rule 19).
- `machine_idle.sh` — rule 21 gate: exit 0 if it is safe to write under configs/, 1 if a cycle is in flight. Asks the NML status buffer, never pgrep (which self-matches).
- `cfg_edit.sh` — the ONLY sanctioned way to edit configs/: gates on machine_idle, applies the edit, re-runs the scanner, fails as one unit (CLAUDE.md rule 21). Never Write/Edit configs/ directly.

## halcheck.sh + halcheck_isolated.hal (added 2026-08-03)
Loads ned's NEW realtime comps in ISOLATION (dummy thread, no hm2_eth, no
board, no motion) and reports whether every comp name, pin, `net` and `setp`
is valid, then tears down. Run with LinuxCNC DOWN; it refuses otherwise.
Exists because two HAL edits in a row killed the launch and were invisible to
every static check -- `cfg_edit.sh` now catches those two classes, this
catches the rest by actually loading. The `.hal` is the pair; edit both when
comps are added.
