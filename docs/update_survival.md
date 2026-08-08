# UPDATE SURVIVAL — read BEFORE updating LinuxCNC or Probe Basic

Two updates can silently destroy machine-critical behavior. This document
is the complete map of what each update clobbers, how to detect the
damage, and how to restore it. Companion docs: the button-behavior
contract `docs/gui_button_spec.md` (what the GUI must do) and the
commissioning runbook `docs/commissioning/probe_basic_migration.md`
(history + the core-touch replumb register §4).

============================================================================
## A. LinuxCNC update (`linuxcnc-uspace` package)
============================================================================

### A1. THE PATCHED homemod.so — the big one

- **What:** `/usr/lib/linuxcnc/modules/homemod.so` is NOT the distro build.
  It carries the upstream fix for bug **#3717** (commit `b7914b469c`,
  "fix multiple homing of absolute encoders"): stock 2.9.8 ADDS
  home_offset into motor_offset on EVERY home and never resets it, so the
  A/C head lands off by −offset on every REHOME (first home of a session
  is exact, nth home is off by −(n−1)×offset).
- **Install record (2026-08-01):**
  - installed sha256: `56972276b34e9d3d25d6c25fee0806bef4342d9e0f57f0fb34bdcca708bf613b`
  - stock backup: `/usr/lib/linuxcnc/modules/homemod.so.2.9.8-stock`
  - source: `~/Documents/linuxcnc` branch `ned-298-3717`
    (v2.9.8-88 + cherry-pick, local commit ab24b58bd6)
  - built artifact kept at `~/Documents/linuxcnc/rtlib/homemod.so`
- **A package upgrade OVERWRITES this file silently and the bug RETURNS.**
- **Detect:** either of
  1. `sha256sum /usr/lib/linuxcnc/modules/homemod.so` ≠ the hash above
     (and ≠ whatever new build you intentionally installed), or
  2. behavior: `ned/gui.md` shows `HOME VERIFY: ... NOT actually homed,
     correcting` on EVERY single-axis A/C rehome (one correction round
     converges — that is the brain absorbing the bug, not health).
- **Restore:** with LinuxCNC STOPPED:
  ```
  sudo cp -a /usr/lib/linuxcnc/modules/homemod.so /usr/lib/linuxcnc/modules/homemod.so.NEW-stock
  sudo cp ~/Documents/linuxcnc/rtlib/homemod.so /usr/lib/linuxcnc/modules/homemod.so
  ```
  BUT FIRST check whether the new LinuxCNC already ships the fix
  (changelog / `git log` for `b7914b469c` or PR #3774, or issue #3717):
  if it ships, keep the distro module and delete this section's warning.
  If the new version is not 2.9.8 anymore, REBUILD from a matching source
  tree instead of copying the old .so (module ABI can change between
  versions).
- Optional protection: `sudo apt-mark hold linuxcnc-uspace` until ready.

### A2. Our halcompile-installed components live in the SAME directory

`pso_live`, `jogblock`, `limdir` (sources in `ned/tools/live/*.comp`) are
installed into `/usr/lib/linuxcnc/modules/` by halcompile. A package
upgrade can remove or orphan them → the session then DIES AT LOAD
("pso_live: module not found" or similar in term/lcnc logs).

- **Detect:** launch fails in iron HAL at `loadrt pso_live|jogblock|limdir`.
- **Restore:** for each comp:
  ```
  sudo halcompile --install ned/tools/live/pso_live.comp
  sudo halcompile --install ned/tools/live/jogblock.comp
  sudo halcompile --install ned/tools/live/limdir.comp
  ```

### A3. Version-sensitive knowledge

- Source cites in docs/memory (homing.c line numbers, command.c:584 MDI
  homed wall, base_actions.py:37-43) are 2.9.8-accurate; re-verify before
  trusting them on a new version.
- The MDI-unhomed wall (non-identity kins refuse COORD mode unless all
  homed) is core motion behavior — expected to persist, but the guard
  messages cite 2.9.8 line numbers.

### A4. After ANY LinuxCNC update — checklist

1. `sha256sum /usr/lib/linuxcnc/modules/homemod.so` — decide stock vs
   re-patch (A1).
2. Confirm `pso_live/jogblock/limdir` load (A2) — launch reaches PB.
3. Home All (full cycle, head read, `HOME VERIFY OK` in gui.md).
4. Home A alone TWICE — both must land `HOME VERIFY OK` with NO
   correction round (this is the #3717 probe).
5. One MDI move + one program dry-run; MPG jog each axis.

============================================================================
## B. Probe Basic / qtpyvcp update (re-running `tools/live/qt_pb.sh`)
============================================================================

### B1. What is destroyed vs what survives

- **DESTROYED:** the whole `~/qt_pb` tree — venv, qtpyvcp + probe_basic
  source, every pip package we added, every native build. `qt_pb.sh` runs
  `git clean -dxf` — re-running it IS a wipe.
- **SURVIVES (all machine truth lives in the ned repo):**
  `configs/ned5_pb/` (ini, postgui, user_tabs/ned_controls,
  user_dro_display incl. lock.png, subroutines, ned_pb_params.inc,
  custom_config.yml, tool_table.db, var files), `configs/ned5/` iron,
  `configs/params/*.inc`, `tools/live/*` (brain, pendant, comps),
  `tools/run5.sh`.

### B2. Reinstall recipe (proven 2026-07-31)

The script alone does NOT produce a working install on this Pi. After it:
1. `sudo apt install cmake python3-dev`
2. venv pip: `PySide6` (matching what qtpyvcp expects), `vtk`, `docopt`,
   `sqlalchemy`, `psutil`, `pyudev`, `pybind11`, `pyqtgraph`,
   `simpleeval` (+ `py-spy` for debugging).
3. `qnative --backplot` (needs cmake + python3-dev + pybind11).
4. Do NOT re-run qt_pb.sh to "fix" a broken step — it wipes again; resume
   from `qcompile` manually.
Details + gotchas: runbook §1.

### B3. Core-touches to re-verify — USE THE LOG, NOT MEMORY

Everything we changed in PB core is a RUNTIME poke keyed on core
objectNames/menus that can drift with any PB/qtpyvcp update. The full
authoritative table is the runbook §4 REPLUMB REGISTER. Verification is
mechanical because every touch logs LOUDLY. After first post-update
launch, `grep` lcnc.log for ALL of these lines:

| Expected log line | What it proves |
|---|---|
| `ned-tab HAL component ready` | user tab loaded, HAL pins exist (postgui nets depend on them) |
| `MDI mode gate: stale isRunning gate replaced with live-motion gate` | mode-switch abort protection active |
| `Homing menu: 6 actions rebound to ned-safe homing cycles` | **CRITICAL — if instead you see `rebind INCOMPLETE (n/6)` the STOCK menu is live and Home X one-side-homes the gantry.** Do not home from the menu until fixed. (Brain's one-sided-homing interlock is the backstop.) |
| `NED tab page removed (module machinery stays)` | tab page hidden, machinery loaded |
| `spindle FWD/REV wired to Check countdown` | spin Check gate active |
| `spindle section: chip-load placeholder in; commanded-RPM drives N stock label(s)` | RPM readout + placeholder installed |
| `V slider units label added (mm/min)` | maxV units |
| `GUI numbering: N controls badged -> ned/gui_map.txt` | badge map regenerated (numbers may SHIFT after updates — regenerate references) |
| `ned_pendant: ready` (term/lcnc) | pendant loaded (tap/jump/speed/lock gestures) |
| `==== ned_brain start ====` (gui.md) | brain loaded (reads, guards, verify, watchdogs) |

Any line missing = that feature silently dead → fix before trusting the
GUI. Also verify behavior against `docs/gui_button_spec.md` (the
contract) — buttons, locks, homing menu, zeros, countdowns.

### B3a. PATCHED qtpyvcp core file: obj_status.py (boot-lottery fix, 2026-08-02)

- **What:** `~/qt_pb/qtpyvcp/src/qtpyvcp/utilities/obj_status.py`,
  `hal_poll_thread`: stock code runs `halcmd -s show pin` with
  `stdout=PIPE`. halcmd holds the GLOBAL HAL MUTEX while printing; once
  output exceeds the 64 KB pipe buffer it sleeps in `pipe_write` STILL
  HOLDING THE MUTEX. Meanwhile the GUI main thread spins in
  `hal.component.newpin()` on that same mutex WITHOUT releasing the GIL,
  so the poll thread can never drain the pipe: GIL <-> pipe <-> HAL-mutex
  three-way deadlock. Symptom = "boot lottery": PB freezes mid-boot at
  ~100 % CPU (py-spy: MainThread in hal_qlib.py addPin/newpin, identical
  stack forever), and every later `halcmd` spins in R-state on the held
  mutex. Proof captured 2026-08-02 12:36 (py-spy + /proc wchan
  `pipe_write`), dossier in the session's tmp/boot_lottery.txt.
- **Patch:** halcmd stdout goes to a `tempfile.TemporaryFile()` instead of
  a pipe (a file write never blocks), `p.wait()` (releases GIL), then read
  the file back. Race becomes impossible.
- **Stock backup:** `obj_status.py.stock` alongside the patched file.
- **A PB/qtpyvcp update (B1: qt_pb.sh WIPES ~/qt_pb) removes the patch and
  the lottery RETURNS.**
- **Detect:** `grep -n "tempfile.TemporaryFile" ~/qt_pb/qtpyvcp/src/qtpyvcp/utilities/obj_status.py`
  — no match = stock code = lottery is back. Behavior: any PB boot that
  hangs >30 s with a `halcmd` stuck in `pipe_write` (`cat /proc/<pid>/wchan`).
- **Restore:** re-apply the patch (this section is the spec; diff vs
  `.stock` if present), or check whether upstream qtpyvcp fixed it.

### B4. Known version-coupled items

- `gcode_editor` native plugin: PB ships x86-64; on this Pi it must be
  built natively or the editor falls back to a plain text box (current
  state; planned fix = distro PySide6 + qt6 dev + native build).
- VTK backplot needs GL 3.2; the Pi's V3D gives 3.1 → run5.sh exports
  `LIBGL_ALWAYS_SOFTWARE=1` (llvmpipe). A PB/VTK update may change the
  needed workaround.
- `menubar.yml` (Homing menu provider, Mist entry) is PB core — our CHIP
  rename + menu rebinds are runtime pokes keyed on action TEXTS
  ("Home All", "Home X", ..., 'action_Mist_toggle'); renamed texts break
  them (loud in the log per B3).
- Zero/Lock buttons: `lock.png` (ours, in the repo) mimics PB's
  `zero.png` style; if PB restyles its zero buttons, re-render lock.png
  to match (dros_xyzac.py comments say how it was made).

### B5. After ANY PB/qtpyvcp update — checklist

1. B2 reinstall completes; `run5.sh` launches to a working screen.
2. B3 log-line sweep — every row present.
3. Contract sweep vs `docs/gui_button_spec.md`: zeros countdown, Lock
   A/C skip in MPG cycle, Homing menu entries (Home A/C individually,
   Home X synchronized — listen to the gantry), FWD/REV Check, UNLOAD
   countdown, notifications non-persistent.
4. A/C rehome probe (A4.4) — brain verify machinery unchanged by PB
   updates but confirm gui.md shows the cycle.

### A6. Raspberry Pi Connect = the screen-blanking culprit (killed 2026-08-02)

`rpi-connect-wayvnc.service` (user unit) crash-looped every 5 s -- 24,593
restarts -- probing for a Wayland socket that does not exist on this X11
desktop, and each attempt disturbed the display: the operator saw the screen
"blanking a whole lot", in PB and in plain terminals alike.

Both user units are now stopped, disabled and **masked** (symlinked to
/dev/null): `rpi-connect.service`, `rpi-connect-wayvnc.service`. The operator
never uses Pi Connect.

- **Detect a comeback:** screen blanks with machine off; `journalctl --user -u
  rpi-connect-wayvnc | tail` shows restart spam.
- **An OS update may reinstall/re-enable it.** Re-mask:
  `systemctl --user mask rpi-connect.service rpi-connect-wayvnc.service`

### A5. Rack ATC + MASTER.params (added 2026-08-02)
- The M6 remap chain lives in `configs/ned5_pb/` (subroutines/, python/,
  ini REMAP + [PYTHON] + [ATC]) — config-side, SAFE from PB package
  updates, but a PB update may change the RackATC widget/QML side:
  re-test the ATC page after any PB update.
- `configs/params/*.inc` are GENERATED from `configs/params/MASTER.params`
  once `gen_params.py write` has stamped them. NEVER hand-edit a stamped
  .inc: run `tools/live/gen_params.py check` after any upgrade or manual
  intervention; `write` regenerates.
- `timedelay` in ned5_iron.hal loads TWO instances in ONE loadrt
  (`air.debounce,head.ready`) — adding another loadrt of the same comp
  anywhere kills the launch at insmod.

## Bx. qtpyvcp notification popup -- ned patch 2026-08-03

`~/qt_pb/qtpyvcp/src/qtpyvcp/lib/native_notification.py`
Stock copy kept beside it as `native_notification.py.stock-20260803`.
**A PB update wipes ~/qt_pb -- re-apply after every update.**

Two changes, both in `setNotify()`:

1. **info/debug self-dismiss after 1 s.** `captureMessage()` already tags every
   message `error` / `debug` / `info` and passes it as the title, but the
   widget discarded that and gave everything the same permanent lifetime --
   messages stayed until clicked or until a sixth evicted them. Only real
   faults should demand a hand. Adds `nedAutoDismiss()`, guarded so a message
   the operator already closed is not double-freed.
2. **Fixed anchor.** X was recomputed from the widget own width after
   `adjustSize()`, so the box jumped sideways whenever a message arrived or
   left -- moving under the operator hand. Pinned to `NED_FIXED_W = 520`.

Also needs `QTimer` added to the `PySide6.QtCore` import line.

## By. probe_basic.py -- NO LONGER PATCHED (2026-08-07)

The STATUS-tab red-title error flag was **removed** on 2026-08-07 at the
operator's direction ("i don't care about the status red signal at this
point ... remove code that was made for that purpose"). It never showed
in the GUI.

`~/qt_pb/probe_basic/src/probe_basic/probe_basic.py` is now **byte-identical
to `probe_basic.py.stock-20260803`** (verified: `diff` returns nothing), so
ned carries NO patch in this file and a PB update cannot break anything
here. Do not re-apply it.

Only the tab-title colouring was removed -- `_ned_err_tabs/_ned_err_index/
_ned_err_colour`, the `QTabWidget` walk, two `setTabTextColor` calls and the
`notifications.error_message` subscription. No lock, gate, guard or tool
logic was in that patch. `ned_controls._tool_alarm` is untouched and still
does `LOG.error` + `linuxcnc.command().error_msg`; the popup self-dismisses
after 1 s (see Bx) and **lcnc.log is the durable record of an alarm**.

## Bz. PATCHED Probe Basic core file: probe_basic.ui (GcodeTextEdit + DECLARE row, 2026-08-03/04)

`~/qt_pb/probe_basic/src/probe_basic/probe_basic.ui`
Stock copy kept beside it as `probe_basic.ui.stock-20260803`.

**A PB update OVERWRITES this file** and two things break silently:
- the g-code text pane goes BLANK again (stock points it at the C++
  `GCodeEditor` widget, which never instantiates in this venv; ned repoints
  the customwidget class/extends/header and both widget tags to the Python
  `GcodeTextEdit`), and
- the DECLARE row in TOOL CHANGE PANEL disappears (`ned_declare_input`
  VCPLineEdit + `ned_declare_btn`, deep-copied from the M6 row, filename
  property removed). `ned_controls.py:_build_declaration` then logs
  "DECLARATION: DECLARE row NOT found" instead of wiring it.

**Loud-log check after any PB update:** launch once and require
`DECLARATION: DECLARE row wired from the .ui` in lcnc.log, and confirm
g-code text is visible in the editor pane.

## Bw. PATCHED qtpyvcp core file: mill_tool_table.py (DIAMETER MM/IN + live P column, 2026-08-03/04)

`~/qt_pb/qtpyvcp/src/qtpyvcp/widgets/input_widgets/mill_tool_table.py`
Stock copy kept beside it as `mill_tool_table.py.stock-20260803`.

**A qtpyvcp update OVERWRITES this file** and the tool table reverts to a
single DIAMETER column and the stale DB pocket field. The ned patch:
- DIAMETER MM (the stored value, fed to LinuxCNC) + DIAMETER IN (=/25.4
  view) via data()/setData() overrides;
- P column reads the LIVE rack map from the var file (#4001..#4024), shows
  S for the spindle tool, '-' for on-the-table; edits route through
  `_declare_spindle` / `_declare_fork` (duplicates refused by name) and
  every pocket write goes through `_store_pocket` + immediate save.

**Loud check after any qtpyvcp update:** TOOL tab must show DIAMETER MM and
DIAMETER IN columns and the P column must match the rack graphic; if it
shows one DIAMETER column, the patch is gone — re-apply from git history
(this repo does not carry the file; diff the .stock backup against git log
notes from 2026-08-03/04 sessions).

## Bv. ned .ui PURGE (operator 2026-08-04: "light and nimble, no bloat")

DELETED outright (not hidden) from `probe_basic.ui`: mdi_entry_box_5/6/7,
prog_coolant_setting_frame, ang_jog_slider_link (did nothing: no code and no
setting read it; the sliders are hard-linked by a .ui connection anyway).
From `rack_atc/template_rack_atc/template_rack_atc.ui`: mdi_entry_box_4,
mdi_entry_box_rack_tab, rack_mdi_2, rack_atc_load_frame (took its buttons
with it), reference_carousel_2, spindle_image_label,
loaded_spindle_tool_number, m6_tool_call_button_tool_page,
tool_number_entry_tool_page. Pre-purge backups: *.pre-purge-20260804.

**A PB update restores ALL of them.** The SPARE lists in ned_controls.py are
kept as a RESURRECTION NET: on a stock .ui they re-hide everything and log
"STOCK SPARE(S) RESURRECTED" as an ERROR -- that line in lcnc.log after an
update means: reapply this purge. "confirmed deleted" at INFO is the healthy
state.

### Bw addendum (2026-08-04 night): tool table is ground truth
mill_tool_table.py now also: LOC + Z columns non-editable (flags), every
accepted edit saves the DB immediately (_rt_save), DELETE sweeps records
via o<tool_loc_declare>. probe_basic.ui lost tool_table_save_button /
reload / update_tool_after_reload (resurrection net covers them).
rack_atc.py/qml: fork circles = double-click record-only cycle
(circle_cycle) + spindle badge click-to-declare (tool_length_6 event
filter in ned_controls). A PB/qtpyvcp update clobbers ALL of it — diff
against the .pre-* backups and this section.

### A1c. qtpyvcp tool-database session leak (upstream fix, cherry-picked 2026-08-07)
The fork carries UPSTREAM commit `9ac9f430` (kcjengr/qtpyvcp `pyside6`,
cherry-picked as `2eb47b99`; our own inferior one-liner `2e9fbb02` was
reverted first by `98d725a4`). Two files:
`widgets/display_widgets/vtk_backplot/tool_actor.py` and
`widgets/db_widgets/tool_model.py`. Both held a SQLAlchemy `Session` as an
instance attribute, so each object kept a pooled connection checked out for
its whole life. `VTKBackPlot.update_tool()` builds a fresh `ToolActor` on
every toolTableChanged / toolOffsetChanged / toolInSpindleChanged, so
connections piled up one per tool change until the pool (size 5, overflow
10) was exhausted and the VCP died with `QueuePool limit of size 5 overflow
10 reached`. Killed a 6.5 h overnight GA run at 08:34 on 2026-08-07.
The fix scopes every query in `with Session() as session:` and DELETES the
attribute, so nothing can hold a connection again; in tool_actor the
session closes before any VTK object is built. Side effect: a tool row with
no STL no longer reaches `setFilename(None)`, which raised on PySide6 --
that raise used to escape `__init__` and leak the connection anyway, which
is why a trailing `close()` was not enough. Lathe configs leaked Session
objects but never checked out connections (the lathe branch returns before
the query); only mills crashed.
Stock copy: `tool_actor.py.stock-20260807`. Verify after any qtpyvcp
update: `grep -c 'self\.session' ` on both files must be 0, and
`grep -c 'with Session() as session'` must be 1 in tool_actor.py and 2 in
tool_model.py. Once the fork rebases past `9ac9f430` this section is
historical -- the fix is upstream, not a local carry.

### A1b. ned_ac_kins.so — the swivel-head switchable kins (2026-08-05)
Source `~/Documents/linuxcnc/src/emc/kinematics/ned_ac_kins.c` (tree commit
47dc37aadd) + Makefile entries (objs list MUST include sincos/kins_util/
switchkins/$(USERKFUNCS) or the .so exports nothing and ld dies on an empty
version script). Build: `make ../rtlib/ned_ac_kins.so` in the tree's src/.
Install (root): copy to /usr/lib/linuxcnc/modules/ like homemod (§A1).
A LinuxCNC package update DELETES it; rebuild+reinstall, then verify with
ned/tools/kins/kins_check.py (math lockstep) and an identity-mode launch.
INI (when wired): KINEMATICS = ned_ac_kins coordinates=XYZXAC sparm=identityfirst
