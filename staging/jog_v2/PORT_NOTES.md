# JOG & PRESETS v2 — port notes (staging → live)

Staged 2026-08-01 (v2 operator spec, mockup screenshot_2026-08-01_23-14-28.png).
Base: the v1 files as built earlier today. Another agent is editing the live
`configs/ned5_pb/user_tabs/ned_controls/` — this port is a MERGE against
whatever the live files look like when the operator says go, not a blind copy.

## Files in this folder

| File | What it is |
|---|---|
| `ned_controls.py` | Full module, v2 panel code applied on top of v1. Only the regions listed below differ from v1; everything else (HAL pins, homing menu rebinds, spindle/unload machinery, badges, `_tick`) is byte-identical to v1. |
| `ned_controls.ui` | Full v2 panel layout (see structural deltas below). |
| `selftest_offscreen.py` | 25-check offscreen test with a FAKE linuxcnc (zero NML). Run after porting: `cd <live dir> && QT_QPA_PLATFORM=offscreen python3 /home/brains/Documents/ned/staging/jog_v2/selftest_offscreen.py` — it loads `ned_controls.py`/`.ui` from ITS OWN directory, so copy it beside the live files (or edit `here`) to test the ported result. |
| `PORT_NOTES.md` | This file. |

## .py — regions to port (line refs = staged file)

1. **`JOG_SPEEDS` table** (lines 43–49 + comment 37–42): SLOW 200/15,
   MEDIUM 1200/60, FAST 4000/180 (mm/min / deg/min). Replaces the v1
   304.8/3657.6/21945.6 table. `JOG_AXIS_IDX` (line 51) unchanged from v1.
2. **The whole `# ---- JOG & PRESETS panel (v2 …)` section** (lines
   259–677), replacing v1's section (v1 `# ---- JOG & PRESETS panel ----`
   through the end of `_jog_mdi`). New/changed members:
   - `_JOG_WIDGETS` — 21 names (v1 had 19: `jp_abs`, `jp_rel`, `jp_go`
     OUT; `jp_go_abs`, `jp_go_rel`, `jp_stop`, `jp_status_dot`,
     `jp_status_text` IN).
   - `_JOG_PRESETS` — restructured to `(name, label, ((axis, target),…)
     or None, zlift-bool)`; `_JOG_MOVERS` new (lockout list).
   - `_jog_wire` — no ABS/REL group; adds textChanged/returnPressed wiring,
     GO ABS/REL + STOP connects, `_jog_limits_load()`, 400 ms status QTimer.
   - New methods: `_jog_limits_load`, `_jog_parse_fields`,
     `_jog_entry_changed`, `_jog_enter`, `_jog_apply_enables`, `_jog_flash`,
     `_jog_status_tick`, `_jog_stop`.
   - `_jog_go(rel)` — split-GO version (was: read toggle).
   - `_jog_issue(label, vals)` — REPLACES `_jog_mdi(label, words, feed)`:
     takes structured (axis, work-target) pairs, adds the soft-limit
     pre-check, picks the feed (pure-A/C ⇒ angular), then the unchanged
     mode-confirm + single fire-and-forget `c.mdi("G90 G1 … F…")`.
3. **`__init__`**: unchanged from v1 (`self._jog_speed = 'medium'` +
   `self._jog_wire()` at v1 lines 173–174 stay as-is). If the other
   agent's edits moved them, keep them AFTER the ui load + toolprobe block.
4. Nothing else in the .py differs from v1. `git`-less check:
   `diff <(sed -n '1,258p' staged.py) <(sed -n '1,258p' v1.py)` should show
   only the JOG_SPEEDS comment/values, module docstring line, and the v2
   section header.

## .ui — structural deltas vs v1

1. `jp_absrel_frame` (with `jp_abs`, `jp_rel`) DELETED from the top of
   `jp_v` — panel now starts title → SPEED row.
2. Typed-move button row `jp_btnrow_h`: `jp_go` replaced by TWO buttons
   `jp_go_abs` ("GO ABS\nmove to") and `jp_go_rel` ("GO REL\nmove by"),
   both `enabled=false` at load (the parse-gate enables them).
3. NEW status strip `jp_status_h` appended as the LAST item inside
   `jp_panel`: `jp_status_dot` ("●") + `jp_status_text` ("IDLE — ready") +
   spacer + `jp_stop` ("STOP", `enabled=false` at load).
4. QSS on `jp_panel`: `#jp_absrel_frame/#jp_abs/#jp_rel` rules removed;
   `#jp_go` rules replaced by `#jp_go_abs, #jp_go_rel` (+ `:disabled`);
   added generic `QPushButton:disabled`, `#jp_status_dot`,
   `#jp_status_text`, `#jp_stop` (+ `:pressed`, `:disabled`).
5. Root widget stays `ned_controls_root`; all v1 names otherwise unchanged.
   If the live .ui is still exactly v1, a whole-file replace is safe.

## Behavior contract (paste into docs/gui_button_spec.md on port)

Replace the v1 "NED controls tab — JOG & PRESETS panel" table rows that
changed; the guard/MDI-pattern paragraph stands except: add the soft-limit
pre-check sentence, and delete the ABSOLUTE/RELATIVE row. Changed rows:

| Control | Behavior |
|---|---|
| SLOW / MEDIUM / FAST | Exclusive toggles, one global feed for EVERY panel move, persists between moves: SLOW F200 · 15 deg/min, MEDIUM F1200 · 60 deg/min, FAST F4000 · 180 deg/min. Readout: "F\<lin\> mm/min · \<ang\> deg/min". |
| GO ABS ("move to") | Typed values are absolute work-coordinate targets; one `G90 G1 … F…`. Enter in any field fires GO ABS. |
| GO REL ("move by") | Typed values are offsets from the current position, converted to absolute targets (current work pos + delta) and sent as ONE G90 line — the panel never issues G91 (mockup says "(G91)"; coordinator confirmed the delta-to-absolute pattern stands). |
| GO gating | Both GOs DISABLED until ≥1 field parses as a number; blank fields are omitted (never sent as 0); fields RETAIN values after a move. |
| Soft-limit pre-check | Every move's targets are converted to MACHINE coords (work + g5x+g92+tool, rotation not modeled) and compared to the `[AXIS_*] MIN/MAX_LIMIT` INI values read at panel init. A violation is REJECTED — never clamped: error toast + loud log + the offending axis field flashes red 0.7 s. NOTE: runtime `ini.N.min/max_limit` HAL pin overrides exist and are NOT read here; the planner still enforces the live values. |
| Status strip | Green dot "IDLE — ready" when idle; amber "MOVING — \<vel\> mm/s" during motion (also HOMING); red "OFF — machine not on". NML poll, 400 ms; transitions logged. |
| While moving | All six presets + both GOs disabled; STOP enabled. |
| STOP | `linuxcnc.command().abort()` — kills the in-flight move; brain restores MANUAL + teleop. Red outline, disabled when idle. |
| (unchanged) | Presets table (XY 0 / XYZ 0 / Z 0 / Z +10 zlift / XY0 Z10 / A0 C0), immediate-on-click, guards (ON+homed+idle), mode-confirm-then-fire-and-forget, CLEAR. |

## Port checklist (mechanical)

1. Confirm with the other agent's diff what live `ned_controls.py/.ui`
   look like; merge regions above (or whole-file copy if live == v1).
2. `python3 -m py_compile ned_controls.py` in the live dir.
3. `python3 -c "import xml.etree.ElementTree as ET; ET.parse('ned_controls.ui')"`.
4. Copy `selftest_offscreen.py` beside the live files, run it offscreen:
   expect `25 checks, 0 failed`. Delete the copy (or move to trash/) after.
5. Update `docs/gui_button_spec.md` with the table above.
6. Next PB launch (USER launches, run5.sh), verify in lcnc.log:
   - `JOG panel: soft limits loaded: A[-115..115] C[-315..315] X[-4042.72..1] Y[-1787..1] Z[-620..1]`
     (values come from `configs/params/axis_*.inc` via the expanded INI)
   - `JOG speed -> MEDIUM (F1200 mm/min, 60 deg/min)`
   - `JOG panel: 21 widgets wired`
   - `NED tab page kept: JOG & PRESETS panel is its content`
   - `JOG status: IDLE — ready` (first status tick; `OFF — machine not on`
     if powered down)
   Failure forms: `JOG panel: N missing: …`, `JOG panel wiring failed: …`,
   `JOG panel: soft-limit table unavailable (…) -- pre-check DISABLED`,
   `JOG status: stat poll failed (…)` (once).
7. Rule-14 spot check on the iron: with the machine ON+homed, type a value
   beyond a limit (e.g. Z 500) → toast "GO ABS REJECTED: …", field flashes,
   nothing moves.

## Known limits / decisions

- Soft-limit table is the STATIC INI truth; runtime ini-pin overrides are
  not visible to GUI code (no HAL access by design). The planner remains
  the hard enforcement.
- G5x XY rotation is not modeled in the work→machine conversion (house
  math, same as dros_xyzac/ned_moves).
- STOP aborts whatever task is executing (MDI or program), not only panel
  moves — that is the operator-facing meaning of a panel STOP.
- `status unavailable` state leaves the panel USABLE (guards still refuse
  loudly); it never silently locks the operator out.
