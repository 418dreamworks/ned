# JOG & PRESETS v2 — NARROW SQUEEZE — port notes (staging → live)

Staged 2026-08-01 (v2 operator spec, mockup screenshot_2026-08-01_23-14-28.png);
reworked 2026-08-02 into a single 200-px column. **The port target is now the
STOCK JOG PAGE** of PB's right-side JOG/WCS/PLOT sidebar stack (screenshot-
measured ~200 × 730 px) — the stock jog arrow buttons there get replaced by
this panel. The ned_controls tab returns to an EMPTY page.
Another agent may be editing the live `configs/ned5_pb/user_tabs/ned_controls/`
— this port is a MERGE against whatever the live files look like when the
operator says go, not a blind copy.

## Files in this folder

| File | What it is |
|---|---|
| `ned_controls.py` | Full module, v2 panel code applied on top of v1. Only the regions listed below differ from v1; everything else (HAL pins, homing machinery, spindle/unload, badges, `_tick`) is v1. 2026-08-02 delta: `_jog_flash` stylesheet metrics match the narrow QLineEdit QSS (padding 2px 6px, 10pt). |
| `ned_controls.ui` | NARROW v2 panel layout: single 200-px column (see structural notes below). Same 21 `_JOG_WIDGETS` names as wide-v2. |
| `selftest_offscreen.py` | 25-check offscreen test with a FAKE linuxcnc (zero NML). Copy beside the live files to test the ported result. Last run 2026-08-02: `25 checks, 0 failed`. |
| `render_200x730.py` | Offscreen render at EXACTLY 200×730 + programmatic geometry audit (bounds / pairwise overlap / text-fit walk over every `jp_*` widget). Last run: PASS, 27 visible widgets, `jp_panel` fills 0,0,200×730. |
| `render_200x730.png` | The audited render. |
| `PORT_NOTES.md` | This file. |

## PORT TARGET: the stock JOG page (probe_basic.ui line cites)

Source of truth: `/home/brains/qt_pb/probe_basic/src/probe_basic/probe_basic.ui`
(32213 lines, current install). The right sidebar's JOG/WCS/PLOT stack:

| widget | class | line |
|---|---|---|
| `sidebar_widget` | `QStackedWidget` (the JOG/WCS/PLOT stack) | 22548 |
| `sb_page_1` | `QWidget` — **the JOG page** | 22557 |
| `verticalLayout_64` | **`QVBoxLayout`** on sb_page_1, 0 margins, its ONLY item is jogDisplay | 22561 |
| `jogDisplay` | `VCPStackedWidget` — **the stock jog container to replace** | 22575 |
| `jog_xyzac` | jogDisplay's page for ned's XYZAC kins (stock arrow ActionButtons, `machine.jog.axis:*`) | 24403 |
| `sb_page_2` / `sb_page_3` / `sb_page_4` | WCS page / PLOT page / empty (reserved for a PB "sidebar" user tab, probe_basic.py:604-607) | 25849 / 26531 / 26664 |
| `jog_tab` / `wcs_tab` / `plot_tab` | the stack's selector QPushButtons | 27055 / 27121 / 27184 |

Width context: sb_page_1 sits inside `frame_26` (201 px fixed width); the
measured usable area is ~200 × 730 — exactly what `render_200x730.py` audits.

### Locating it at runtime

`jogDisplay` is unique in the window: `jd = self.window().findChild(QWidget,
'jogDisplay')`. Its layout parent: `lay = jd.parentWidget().layout()` (that
parent is `sb_page_1`, layout `verticalLayout_64`, a **QVBoxLayout** — rule 14c:
layout class verified above by line cite; `replaceWidget` is used anyway, which
exists on box AND grid layouts, the house pattern from
`_restyle_spindle_section`).

### replaceWidget / hide procedure (add to `__init__` via `QTimer.singleShot(0, …)`)

```python
def _jog_page_takeover(self):
    win = self.window()
    jd = win.findChild(QWidget, 'jogDisplay') if win else None
    panel = self.findChild(QWidget, 'jp_panel')
    if jd is None or panel is None or jd.parentWidget() is None \
       or jd.parentWidget().layout() is None:
        LOG.error('JOG page takeover FAILED: jogDisplay/jp_panel/layout '
                  'not found -- stock jog page left as-is')   # LOUD, rule 14e
        return
    lay = jd.parentWidget().layout()
    self.layout().removeWidget(panel)      # detach from the ned tab page
    lay.replaceWidget(jd, panel)           # panel reparents into sb_page_1
    jd.hide()                              # stock arrows: hidden, unreachable
    LOG.info('JOG page takeover: jogDisplay (stock jog arrows) replaced by '
             'jp_panel at 200x730; ned tab page now empty')
```

Rule-14 trace for the takeover itself:
- (a) target found by objectName `jogDisplay` (probe_basic.ui:22575, unique);
- (b) old binding = the stock `ActionButton`s (`machine.jog.axis:*`) inside
  jogDisplay's pages — they stay constructed but the whole stack is hidden and
  out of every layout, so they are unreachable; nothing is rebound, no
  homing/jog action can fire from them;
- (c) layout is `QVBoxLayout` (probe_basic.ui:22561) and `replaceWidget` is
  used regardless (no `insertWidget`-on-grid hazard);
- (d) load order: PB's `load_user_tabs` runs synchronously at window
  construction (probe_basic.py:159, 587-603) and `jogDisplay` is static .ui
  content, so it exists when the singleShot fires; the loud-fail branch covers
  a PB update renaming it;
- (e)/(f) success AND failure log lines above; verify on next launch.

### Removal of the v1 panel from the ned_controls tab

The takeover MOVES `jp_panel` out of `ned_controls_root`'s layout — the NED
tab page stays registered in `tabWidget` (PB adds every UserTab) but renders
as an empty page. That is the operator-approved end state ("tab returns to
empty page"). Do NOT re-add `jogDisplay` to `HIDE_CORE` — the takeover hides
it once; `_tick`'s HIDE_CORE loop stays `('horizontalWidget',)`.

## .py — regions to port (line refs = staged file, 1200 lines)

1. **`JOG_SPEEDS` table** (lines 43–47 + comment 37–42): SLOW 200/15,
   MEDIUM 1200/60, FAST 4000/180 (mm/min / deg/min). `JOG_AXIS_IDX`
   (line 51) unchanged from v1.
2. **The whole `# ---- JOG & PRESETS panel (v2 …)` section** (lines
   259–679, through `_jog_stop`), replacing v1's section. New/changed
   members: `_JOG_WIDGETS` (21 names), `_JOG_PRESETS`, `_JOG_MOVERS`,
   `_jog_wire`, `_jog_limits_load`, `_jog_parse_fields`,
   `_jog_entry_changed`, `_jog_enter`, `_jog_apply_enables`, `_jog_flash`
   (narrow metrics), `_jog_status_tick`, `_jog_stop`, `_jog_go(rel)`,
   `_jog_issue(label, vals)`.
3. **`__init__`**: `self._jog_speed = 'medium'` + `self._jog_wire()` stay
   AFTER the ui load + toolprobe block; ADD the
   `QTimer.singleShot(0, self._jog_page_takeover)` line and the
   `_jog_page_takeover` method from this file's procedure above.
4. Nothing else in the .py differs from v1.

## .ui — narrow-squeeze structure (vs the wide v2 layout)

1. Root: `ned_controls_root` → 0-margin `nedLayout` → `jp_panel` ONLY
   (outer HBox, right spacer, bottom spacer all deleted; no 500-px cap).
2. One column, top→bottom: `jp_title` → `jp_speed_caption` → `jp_slow` /
   `jp_medium` / `jp_fast` STACKED (30 px, 10pt) → `jp_feed_readout` (8pt)
   → `jp_presets_caption` → `jp_grid` now **2 cols × 3 rows** (44 px, 9pt:
   xy0+xyz0 / z0+zp10 / xy0z10+a0c0) → `jp_presets_note` → `jp_typed_caption`
   → five FULL-WIDTH `jp_in_*` QLineEdits (28 px, 10pt, **axis+unit moved
   into placeholders** "X · mm" … "C · deg"; `jp_lbl_*`/`jp_unit_*` labels
   and `jp_typed_frame` DELETED) → `jp_clear` → `jp_go_abs` → `jp_go_rel`
   (full-width, 40 px, single-line captions "GO ABS · move to") →
   status row (`jp_status_dot` min 16 px, `jp_status_text` min 150 px,
   spacer) → full-width `jp_stop` (30 px).
3. All 21 `_JOG_WIDGETS` names unchanged — the .py ports with NO widget-name
   edits; QSS is the same dark+amber scheme with narrow metrics
   (QLineEdit padding 2px 6px 10pt — mirrored in `_jog_flash`).
4. Tap-target fonts: buttons 10pt (presets 9pt), edits 10pt — all ≥ 9pt.

## Behavior contract (paste into docs/gui_button_spec.md on port)

Unchanged from wide-v2 (speeds table, split GO ABS/GO REL delta-to-absolute,
GO gating, soft-limit REJECT with red flash, status strip, moving lockout,
STOP=abort, presets immediate). One addition:

| Control | Behavior |
|---|---|
| Panel location | Lives on the stock JOG page of the right sidebar stack (replaces the stock jog arrows; MPG owns axis jogging). NED tab page is empty. |

## Port checklist (mechanical)

1. Confirm live `ned_controls.py/.ui` state with the other agent's diff;
   merge regions above (or whole-file copy if live == v1).
2. `python3 -m py_compile ned_controls.py` in the live dir.
3. `python3 -c "import xml.etree.ElementTree as ET; ET.parse('ned_controls.ui')"`.
4. Copy `selftest_offscreen.py` + `render_200x730.py` beside the live files,
   run both offscreen: expect `25 checks, 0 failed` and
   `geometry audit PASS … at 200x730`. Move the copies to trash/ after.
5. Update `docs/gui_button_spec.md` (table above + location row).
6. Next PB launch (USER launches, run5.sh), verify in lcnc.log:
   - `JOG panel: soft limits loaded: A[-115..115] C[-315..315] X[…] Y[…] Z[…]`
   - `JOG speed -> MEDIUM (F1200 mm/min, 60 deg/min)`
   - `JOG panel: 21 widgets wired`
   - `JOG page takeover: jogDisplay (stock jog arrows) replaced by jp_panel …`
   - `JOG status: IDLE — ready` (or `OFF — machine not on`)
   Failure forms: `JOG panel: N missing: …`, `JOG panel wiring failed: …`,
   `JOG page takeover FAILED: …`, `JOG panel: soft-limit table unavailable
   (…) -- pre-check DISABLED`, `JOG status: stat poll failed (…)` (once).
7. Rule-14 spot check on the iron: machine ON+homed, JOG page selected,
   type a value beyond a limit (e.g. Z 500) → toast "GO ABS REJECTED: …",
   field flashes, nothing moves. Then check the NED tab is an empty page
   and the stock jog arrows are gone from the JOG page.

## Known limits / decisions

- Soft-limit table is the STATIC INI truth; runtime ini-pin overrides are
  not visible to GUI code (no HAL access by design). The planner remains
  the hard enforcement.
- G5x XY rotation is not modeled in the work→machine conversion (house
  math, same as dros_xyzac/ned_moves).
- STOP aborts whatever task is executing (MDI or program), not only panel
  moves — the operator-facing meaning of a panel STOP.
- `status unavailable` leaves the panel USABLE (guards still refuse loudly).
- After a move starts, typed values persist; placeholders (axis+unit) are
  hidden while a field holds text — the field order (X Y Z A C, top→bottom)
  is the identity cue at 200 px.
- The hidden `jogDisplay` still exists (PB update-safe: nothing deleted);
  a PB update that renames it makes the takeover fail LOUDLY and leaves the
  stock jog page usable.
