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
