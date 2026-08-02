# RACK MAP — per-pocket table + teach + user tab — port notes (staging → live)

Staged 2026-08-02. STRICTLY STAGING: nothing under `configs/` or `tools/`
was touched; the machine was running verification cycles while this was
built. All tests ran offscreen against a FAKE linuxcnc (zero NML).

## What this replaces

The live `m21.ngc`/`m22.ngc` place rack pockets on a straight line
interpolated from TWO taught pockets (`#3983-#3986`), one shared clearance
(`#3987/#3988`) and an 8-case `rack_id` (`#3979`) direction switch. The
staged versions read a PER-POCKET table instead — every fork gets its own
taught seat, clearance and entry axis; entry DIRECTION falls out of the
seat-vs-clearance comparison (no rack_id cases at all).

## Param map (pocket N = 1..15, range 4104..4163)

| param | meaning |
|---|---|
| `#[4000+N]` | tool assigned to fork N (EXISTING contract — toolchange.ngc header, m13.ngc) |
| `#[4100+N*4]` | seat X, MACHINE coords (used under G53) |
| `#[4101+N*4]` | seat Y, MACHINE coords |
| `#[4102+N*4]` | clearance coordinate — ONE scalar: the entry-axis coordinate of the clearance point (other axis holds the seat value) |
| `#[4103+N*4]` | flags = entry_axis (0=X, 1=Y) + 2·seat_taught + 4·clear_taught; fully taught = 6 (X entry) or 7 (Y entry); m21/m22 abort below 6 |
| `#3980/#3981/#3982` | UNCHANGED: rack traverse F / Z load height / safe Z |
| `#3979`, `#3983–#3988` | RETIRED (no longer read; harmless leftovers in the var file) |

Teaching: `o<rack_teach> call [N] [1]` captures the CURRENT machine X/Y as
pocket N's seat (`#<_abs_x>`/`#<_abs_y>` — LinuxCNC manual, gcode/overview
Predefined Named Parameters: "Return current absolute X coordinate (G53)
including no offsets"); `call [N] [2]`, with the head parked at the pocket's
clearance position, stores the clearance scalar and derives the entry axis
(the axis with the larger |current − seat| delta; < 0.5 mm on both axes
aborts). MODE 1 clears the clearance-taught bit (a moved seat invalidates
the old clearance). Every capture PRINTs a confirmation; every refusal is
an abort — no silent no-ops.

## Files → destinations

| staged file | copies to | notes |
|---|---|---|
| `m21.ngc` | `configs/ned5_pb/subroutines/m21.ngc` | store tool in pocket N (per-pocket table) |
| `m22.ngc` | `configs/ned5_pb/subroutines/m22.ngc` | retrieve tool from pocket N |
| `rack_teach.ngc` | `configs/ned5_pb/subroutines/rack_teach.ngc` | NEW — found via `[RS274NGC]SUBROUTINE_PATH = subroutines:…` (ned5_pb.ini:89), nothing to add |
| `rack_map.py` + `rack_map.ui` | `configs/ned5_pb/user_tabs/rack_map/` | NEW folder; PB's `load_user_tabs` (probe_basic.py:587-603) imports `<dir>/<dir>.py` and instantiates its `UserTab` — folder MUST be named `rack_map` |
| `selftest_offscreen.py`, `render.py` | run beside the ported files, then trash/ | 19 checks / geometry audit |
| `render.png` | — | audited 1660×760 render |

Move the REPLACED live `m21.ngc`/`m22.ngc` to `trash/configs/ned5_pb/
subroutines/` (delete = move to trash, preserve path).

`toolchange.ngc` is NOT modified. It already enforces the FIXED-HOMES
contract this table assumes: on put-away it aborts if the tool has no fork
of its own or its fork is occupied, then `o<m21> call [#<tool_in_spindle>]`
— tool N returns to fork N, always (toolchange.ngc o150/o151/o152 block).

## Var-file seeding block (REQUIRED before first use)

`configs/ned5_pb/ned5_pb.var` currently ends its 4xxx run at `4015` and the
new table params are absent, so they'd be volatile. Persistence mechanism
(manual, gcode/overview "Numbered Parameters Persistence"): the interpreter
"reads the file when it starts up, and writes the file when it exits"; the
file needs exactly two numeric columns, ascending parameter numbers
("Parameter file out of order" otherwise). The manual's table marks 31-5000
"volatile" as a class — persistence for `#3973-#4015` on this machine comes
from their PRESENCE in the var file (the interp writes back every parameter
listed; toolchange.ngc's header calls these "persistent" and daily use
confirms it). The listed-therefore-persistent behavior was additionally
VERIFIED 2026-08-02 with the standalone `rs274` batch interpreter: a seeded
var file ran `o<rack_teach>` and the taught values came back written into
the listed 41xx lines (clearance + flags persisted). Remaining inference:
same behavior under full task on the iron — the first-teach checklist step
confirms it.

Seed by inserting these 60 lines into `ned5_pb.var` BETWEEN the `4015` line
and the `5161` line (LinuxCNC must not be running, or the exit-save will
clobber the edit):

```
4104 0.0 … 4163 0.0   (one line per param, ascending)
```

Generate them:
`python3 -c "print('\n'.join('%d 0.000000' % p for p in range(4104, 4164)))"`

## INI

Nothing new. `[ATC]POCKETS = 15` already (ned5_pb.ini:116) and the tab/ngc
are hard-ranged to 1..15; `SUBROUTINE_PATH` already covers `subroutines/`.

## M13 / rack-homed interplay

`m13.ngc` (REMAP M13, ned5_pb.ini:99) does NOT touch the 41xx table: it
loops pockets 1..`#<_ini[atc]pockets>` pushing `#[4000+N]` into PB's
`rackatc` widget (`store_tool{N, tool}` DEBUG-EVAL), then restores the
spindle with `M61 Q#3991 G43 H#3991`. Its header claims `#3989` tracks
carousel homed, but the current file never writes `#3989` — there is no
rack-homed gate anywhere in the staged path either. The tab's SPINDLE HOLDS
row commits the same pair M13 relies on (`M61 Qn` + `#3991=n`), so a
hand-load correction keeps M13/toolchange consistent. The `rackatc` widget
display refreshes only when M13 runs; the rack_map tab reads the var file
directly, so the two can differ until the next M13 — same params, two views.

## rack_map tab behavior (contract for docs/gui_button_spec.md)

| Control | Behavior |
|---|---|
| TOOL IN FORK spinbox (per row) | Commit on Enter/leave-field; no-change commits are ignored. Duplicate tool number anywhere else in the rack → REFUSED (toast + log + revert). tool≠pocket → allowed (hand-load reality) but LOUD warning (fixed-homes toolchange returns tool v to fork v). Writes `#[4000+N]=v` via house MDI pattern. |
| TEACH SEAT / TEACH CLEAR (per row) | Operator parks the head FIRST (MPG); button fires `o<rack_teach> call [N] [1|2]` via house MDI pattern (guards: ON + homed + idle; MODE_MDI CONFIRMED by poll; fire-and-forget). Immediate confirmation = the sub's PRINT line; the table repaints when the var file saves. |
| Seat X/Y, CLEARANCE labels | Read-only, var-file truth. Amber = taught, grey `—` = untaught. Clearance shows its entry axis (`X -100.000`). |
| SPINDLE HOLDS spinbox | Commit on Enter/leave-field → `M61 Qn` + `#3991=n` (one MDI each, in that order). |
| var status label | Last successful read time + param count; `var file UNREADABLE: …` on failure (also logged, once). |

Known limit: parameter READS come from `[RS274NGC]PARAMETER_FILE` polling
(2 s, mtime-gated) — numbered params are not readable over NML and
`hal.get_value()` is banned in GUI code (ned_controls.py header,
2026-07-31 UI-thread freeze). The interp saves the file on exit and at
program end; exact save timing after an MDI teach is UNVERIFIED (inference
flag) — first-launch checklist covers it.

## Rule-14 audit (this build)

- (a) Targets: all 107 interactive/label widgets are declared in
  `rack_map.ui` and found by objectName from `rack_map.py` (`_wire`
  verifies ALL names, selftest check 1 proves `_missing == []`).
- (b) Bindings: plain Qt signal→slot on OUR OWN widgets (spinbox
  `editingFinished`, button `clicked`); no core PB widget is touched, no
  stock binding exists to sever.
- (c) Layouts: everything is declared in the .ui — ZERO runtime layout
  calls (no insertWidget/replaceWidget anywhere in rack_map.py).
- (d) Load order: user tabs load synchronously (probe_basic.py:159); the
  tab polls the var file itself and needs nothing from postgui/DROs.
- (e) Provably runs, loudly: `RACK MAP: N widgets wired`, `RACK MAP:
  parameter file: …`, `RACK MAP: var file refreshed (…)`, every MDI logged
  (`… MDI "…" issued (fire-and-forget)`), every refusal a toast + ERROR
  log (`REFUSED`, `refused: machine is not ON/busy/not fully homed`,
  `var file read failed`). Silent no-ops: none — verified by selftest
  checks 6/8 (refusal paths assert the toast).
- (f) Verify on next launch — expect in lcnc.log:
  `RACK MAP: 107 widgets wired (15 pockets + sync row)`,
  `RACK MAP: parameter file: …/ned5_pb.var`,
  `RACK MAP: var file refreshed (… params, …)`.
- One deterministic fix made during the audit: QSS attribute selector
  `[rmSeat="true"]` polished inconsistently under the runtime loader
  (alternating grey rows in the offscreen render) — replaced with
  per-widget stylesheets set in `_set_lbl` (house `_jog_flash` pattern).

## Port checklist (mechanical)

1. Machine idle, LinuxCNC NOT running (var-file edit + REMAP files reload
   only on restart).
2. Trash the live `m21.ngc`/`m22.ngc` (preserve path under trash/); copy
   staged `m21.ngc`, `m22.ngc`, `rack_teach.ngc` into
   `configs/ned5_pb/subroutines/`.
3. Seed `ned5_pb.var` with 4104..4163 (block above, ascending, between
   4015 and 5161).
4. `mkdir configs/ned5_pb/user_tabs/rack_map/`; copy `rack_map.py` +
   `rack_map.ui` in; `python3 -m py_compile rack_map.py`;
   `python3 -c "import xml.etree.ElementTree as ET; ET.parse('rack_map.ui')"`.
5. Copy `selftest_offscreen.py`+`render.py` beside them, run offscreen:
   expect `19 checks, 0 failed` and `geometry audit PASS … 1660x760`;
   then move the copies to trash/.
6. USER launches (run5.sh). Verify the three RACK MAP log lines above and
   that the new tab shows 15 grey untaught rows.
7. First teach on the iron (operator): MPG the head over fork 1's seat →
   TEACH SEAT 1 → PRINT line appears; park at fork 1's clearance → TEACH
   CLEAR 1 → PRINT `flags=6/7`. Confirm when the TABLE repaints (var-file
   save timing — the flagged inference). Restart LinuxCNC once and confirm
   the taught row survives (persistence proof).
8. Only after all 15 forks are taught: first M6 under the new m21/m22 with
   fingers on STOP — entry axis/direction now comes from the table.
