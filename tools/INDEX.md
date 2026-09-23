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
| `ned_health.sh` | **ASSISTANT MANAGER CHECK** (418ops charter 2026-09-23: Machining is assistant manager for ned). Tailnet, exactly one `mailsync`, exactly one 418ops checkout, disk, the five HAL modules a LinuxCNC upgrade clobbers (`docs/update_survival.md`), mesalog, `gh` login. **Silent when all is well** -- the output IS the one-line report to GM. Read-only. `-v` prints every check. |
| `admit.sh` | **THE ADMISSION GATE.** Only a program that passes here may be in `nc_files/`. Three stages, each fatal: the central linter (`~/418ops/machine/gcode-lint/lint_ngc.py`), `sign_ngc.py --verify` (STRUCT must be unchanged; BODY differing is expected -- feeds are the machinist's; exit 2 = no key on ned = unverifiable, which does NOT refuse), then `rs274` under a throwaway HOME. Reads `PROGRAM_PREFIX` from the ini rather than a typed path. Source is `~/linuxcnc/incoming/`; refused files MOVE to `nc_files_quarantine/refused/` with a `.findings.txt` beside them. `--dry-run` decides without moving. |
| `publish_machine_facts.py` | Publishes ned's machine facts to `~/418ops/machine/` per `418ops/contracts/machine-facts.md` -- `limits.json`, `work_offsets.json`, `fixtures.json`, `tool_table.json`. Nothing is hand-typed: every number is read from the file that owns it (`configs/params/*.inc`, `configs/ned5_pb/ned5_pb.var`, `docs/fixtures/*.json`, `docs/tool_library/tool_table.json`) and carries that file's path and mtime, so a stale fact shows as a stale date. Run it after any home, re-measure, new fixture or tool re-probe. `--dry-run` prints the md5s without writing. |
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
