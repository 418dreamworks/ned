# Probe Basic migration (commissioning notes)

Goal (operator, 2026-07-31): migrate the GUI from nedgui to **Probe Basic**,
starting from https://github.com/NTULINUX/qt_pb/blob/main/qt_pb.sh (saved as
`tools/live/qt_pb.sh`).

## Install (done 2026-07-31)

qtpyvcp + probe_basic (kcjengr, `pyside6` branch) in `~/qt_pb/qtpyvcp/venv`
(python venv, `--system-site-packages`). The script alone fails on this Pi; three
additions were needed:

1. `sudo apt install cmake` — `qnative` builds a cmake project.
2. `pip install PySide6` (6.11.1, aarch64 wheel) — qtpyvcp declares PySide6
   **optional** (`pyproject.toml:29`), so nothing pulls it in; without it every
   `qcompile` call dies ("unable to call pyside6-uic").
3. `pip install vtk` (9.6.2) — the qtpyvcp VTK backplot imports it.

Re-running `qt_pb.sh` WIPES the venv (`git clean -dxf` inside the qtpyvcp
checkout, where the venv lives) — to redo a step, resume from `qcompile`
manually instead. PB example configs land in `~/linuxcnc/configs/` (they do not
touch `ned`/`ned5`). The script appends a venv `activate` line to `~/.bashrc`;
`/usr/bin/qtvcp` has an absolute python3 shebang, so nedgui launches are
unaffected.

## Machine config: `configs/ned5_pb/`

Same iron as ned5_iron.ini — `HALFILE = ../ned5/ned5_iron.hal`, same
`../params/*.inc` — only the GUI layer differs:

- `ned5_pb.ini` — `DISPLAY = probe_basic`; PB [DISPLAY]/[FILTER]/[VTK] keys;
  metric startup code (PB's example ships G20); `SUBROUTINE_PATH =
  subroutines:../ned5/ngc:...` (PB's subs incl. `on_abort` + ned's probing ngc);
  `PARAMETER_FILE = ned5_pb.var` seeded from ned5_iron.var (persistent #5211
  etc. carry over). [PSO]/[PROBE] are read-only mirrors of ned5_iron.ini
  (marked in-file; clean fix = move those bodies to `../params/*.inc`, which
  needs an explicit operator OK under the param-file rule).
- `postgui_pb.hal` — PB cycle-timer block (`time` comp + halui) and the MPG
  pendant wiring. Deliberately NOT wired: pso_live enable/reset (inert),
  R4/output-05 (parked FALSE), qtpyvcp_manualtoolchange (iron self-acks).
- `tools/live/ned_pendant.py` — the MPG state machine ported OUT of the nedgui
  handler into a GUI-independent userspace HAL component (`pendant`): tap =
  next axis, double-tap = back, hold 0.4 s + wheel = speed. Same pins/signals
  as the nedgui handler exported, so iron HAL section 7b + jogblock work
  unchanged.
- `tools/run5pb.sh` — launcher; puts the qt_pb venv on PATH (a bare `linuxcnc`
  call cannot find `probe_basic`).

## Cutover (2026-07-31, operator: "delete everything in the current gui...
## use the developed logic")

- **`tools/run5.sh` now launches Probe Basic** (`ned5_pb.ini`; `run5pb.sh`
  folded in and trashed). `run5.sh resume` keeps working: the confirmation
  dialog is replaced by a y/N prompt at launch showing the stored positions
  (consent = `NED_RESUME_OK=1`); the resume ini is generated from ned5_pb.ini.
- **nedgui archived** to `trash/configs/ned5/` (qtvcp screen + handler,
  postgui_iron.hal, postgui.hal, ned5.ini, ned5_iron.ini + generated inis;
  merged with the earlier-trashed page_probe.ui; all copies verified before
  removal). `configs/ned5/` keeps only the machine layer: `ned5_iron.hal`
  (loaded by ned5_pb.ini as `../ned5/ned5_iron.hal`), `ngc/`, vars, tool.tbl,
  stored_home.json. **ned5_pb.ini is now the [PSO]/[PROBE] single source**
  (a move to ../params/*.inc was tried 2026-08-01 and UNDONE — operator:
  "i did not understand it"; they stay inline) —
  the retired iron ini (with the full per-value commentary) is in trash.
- **`tools/live/ned_brain.py`** carries the developed logic, GUI-independent
  (loadusr from postgui_pb.hal, pins `brain.*` on the same iron signals the
  nedgui pins drove): head A/C read state machine (exact `_hr_tick` port
  incl. early-exit, stale-read + range guards, R4 parked FALSE after every
  read), reads at startup + every machine-ON transition (arming
  ini.4/5.home_offset before the operator can home), post-home verify
  (0.05 deg, one unhome+rehome correction round, then joints left UNHOMED +
  NML error_msg which PB pops), stored-home saver, resume arming (aborts any
  un-armed resume homing attempt), teleop recovery (power-on + after
  program/MDI idle), machine-event log to `gui.md`. Head zero counts are
  parsed from `configs/params/head_zero.inc` and gears from
  `tools/live/ned_params.sh` at start (rule 11: no copies).

## Not ported (open)

- Per-button GUI event logging, IO tab, solenoid force buttons + tool-release
  countdown, MPG-blocked reason display, A/C pre-home DRO display of held
  reads (brain logs/arms them; PB shows A/C 0.000 until homed). Vehicles: PB
  `user_buttons`/`user_tabs` (PySide6 widget plugins — see the template in
  configs/ned5_pb/user_buttons/).
- Note: PB gets machine state (position, homed, estop, probe trip, overrides)
  via the LinuxCNC status channel automatically — HAL wiring is only needed
  for extras. Wired: cycle timer, pendant, brain. Candidates pending first
  launch (inspect `halcmd show pin qtpyvcp`): spindle RPM readout, probe LED.

## MODE-SWITCH ABORTS MOTION (found 2026-07-31 night, cost a workpiece run)

A `c.mode()` change while motion executes ABORTS the motion. Two bugs came
from ignoring this:

1. `linuxcnc.command().wait_complete()` returns after ~5 s REGARDLESS of
   whether the MDI move finished. The MOVE panel's issue→wait→back-to-MANUAL
   recipe therefore killed every move longer than ~5 s partway ("moves toward
   target and then stops"), and could wedge task in MDI + interp READING
   (jog panel + feed/step then look "locked" — they're mode-gated). Recovery:
   `linuxcnc.command().abort()`.
2. ned_brain's return-to-MANUAL edge fired on interp idle alone — with
   task/interp running ahead of motion, that can flip modes while motion still
   runs and abort a program partway.

Fix (both files, same rule): GUI motion handlers are FIRE-AND-FORGET (issue
the MDI, return; relative moves precomputed into one absolute G90 line so no
G91 is left modal on abort); ned_brain restores MANUAL + teleop only when
interp is IDLE **and** `stat.inpos` **and** `current_vel ≈ 0`. Never call
`mode()` on a machine that may still be moving.

Two refinements (2026-08-01, after live testing):

- Brain's level-triggered flip RACED fresh MDI commands (GUI enters MDI
  mode, brain steals it back within a tick, task rejects with 'Must be in
  MDI mode', 23:44:36). Now: flip ONCE per activity episode (armed only by
  interp-busy), debounced 1 s of continuous done, debounce restarted on any
  external task-mode change.
- setTaskMode monkey-patch is no longer UNgated (a stray GUI mode action
  mid-move still aborted motion): it now carries a LIVE gate — refuse a
  mode CHANGE while interp busy / not inpos / vel > 0, from a fresh poll.
  Register row 8 renamed accordingly.

## AUDIT vs docs/gui_button_spec.md (2026-08-01, operator-ordered)

The button contract lives in `docs/gui_button_spec.md` — code must match it.
Divergences found and fixed in the audit:

1. **refY homed the X pair** — ROOT CAUSE: Y shares homing-sequence |1| with
   the X pair; when any member is negative the whole set homes synchronized
   on any single home() (ini-homing.adoc). The pair's -1 flip LEAKED when the
   brain's read-guard abort killed HOME ALL mid-cycle (no homed-edge → no
   restore). Fixes: refY/refZ rebound to normalize the pair to +1 then home
   their joint only; REF X / REF ALL restore +1 on any failure; brain got a
   watchdog (pair at -1 with no homing active ~3 s → restore +1).
2. **REF A / REF C** rebuilt as one-axis REF ALL: dros countdown →
   tab.request_single_ref → ned-tab.refa/refc-out → brain.ref-a/-c-in →
   unhome that joint → fresh read (always) → home it alone → verify judges
   only that axis (brain.verify_axes). Brain refuses the request mid-motion.
3. **REF buttons REMOVED entirely** (operator: homing is rare) — all six
   hidden in dros; the menubar Homing menu (yml HomingMenu provider) is the
   only homing interface, every entry rebound to the safe cycles
   (ned_controls.home_x_pair / home_joint / request_homeall /
   request_single_ref). Countdowns exist only on the zero buttons.
4. **NED tab page removed** (operator: "clear everything in usertab") —
   ned_controls._remove_own_tab_page pulls the page from the QTabWidget; the
   MODULE keeps loading (HAL pins + machinery). Register row addition.
5. **Mist → Chipblow** menu text rename (runtime, in _tick, next to the
   Flood hide; core touch — QAction 'action_Mist_toggle').
6. **Pendant**: jump-size 10 detents/step (was 25); LOCK A/C pins skip
   locked axes in the cycle with auto-advance off a just-locked axis.
7. Verified-as-matching: MOVE panel (fire-and-forget, rel→abs single line),
   HOLES (both-cells rule, 120 s waits, homed guard), UNLOAD (countdown,
   30 s wait), ZERO buttons (merge queue, XYZ-only, defer-while-busy),
   setTaskMode live gate, notifications persistent:false, Flood hidden,
   chip blower on coolant-mist net.

## GANTRY HOMING SAFEGUARDS — EXTREMELY IMPORTANT TO GET RIGHT (operator flag)

The X gantry (joints 0 + 3, one rigid frame, ONE shared switch signal) tolerates
exactly ONE homing mechanism: the homing module's own **synchronized negative-
sequence machinery**. Both wrong ways were hit live on 2026-07-31:

- **One-sided homing** (stock `machine.home.axis:x` = `COORDINATES.index('x')`
  = joint 0 only, machine_actions.py:780): the other side gets dragged →
  racking. Never expose a control that can home one gantry joint.
- **Two individually-commanded home() calls** (even back-to-back): independent
  state machines skew → the rigid frame drags the held side → **joint 3
  following error** (16:11). The same pattern wedged joint 4's homing state
  machine earlier (15:46) — 'homing' flag stuck, un-clearable except restart.

**The working scheme** (all verified in source, no inference):
1. `HOME_SEQUENCE` is runtime-settable: `update_joint_homing_params` stores it
   AND rebuilds the synchronized set (homing.c:637-638).
2. REF X / REF ALL first `halcmd setp ini.0/3.home_sequence -1`; with a
   negative sequence ONE `home(0)` homes BOTH joints synchronized
   (homing.c:269-272; ini-homing.adoc:265-266).
3. `ned_brain` restores `+1` on the (homed0 AND homed3) rising edge, because
   LinuxCNC bars unhomed joint-jogging of negative-sequence joints
   (ini-homing.adoc:269) and the operator requires unhomed X jog. The MPG
   wiring carries the anti-racking duty while unhomed: X-select drives joints
   0 AND 3 with identical counts/scale, and per-joint jog buttons are hidden.
4. Homing always drops to joint mode first (`mode MANUAL` + `teleop_enable(0)`,
   the stock _home_joint recipe) — "must be in joint mode" otherwise.
5. A/C: REF ALL unhomes them BEFORE the sequence starts (HOME_NO_REHOME makes
   homing an already-homed absolute-encoder joint a silent no-op), and
   ned_brain's guard aborts any A/C homing that starts without a fresh armed
   read. A/C homing runs only via the sequence (seq 2), never as
   individually-commanded concurrent pairs.

## First-launch checklist (RT was busy with the operator's session)

1. `tools/run5.sh` with the machine idle; watch lcnc.log + gui.md.
2. Likely first error: `custom_config.yml` uses the DBToolTable provider (the
   sim ships a sqlite db); ours is classic `tool.tbl` — if PB objects, switch
   the yml provider to the classic tool table plugin.
3. Verify: pendant jogs (unhomed joint mode), startup head read lands in
   gui.md + ini.4/5.home_offset, XYZ homing off switches, A/C home + verify,
   `run5.sh resume` end-to-end, PB probing screens see `motion.probe-input`,
   MPG comes back after a program (brain's MANUAL-after-idle vs PB's own MDI
   flows -- watch for mode fights).

---

# REBUILD RUNBOOK + REPLUMB REGISTER (2026-07-31 end of day)

**Structural fact:** a PB update / reinstall wipes ONLY `~/qt_pb` (qt_pb.sh does
`git clean -dxf`). Everything ned-specific lives in this repo and SURVIVES:
`configs/ned5_pb/` (config, subroutines, user_tabs, user_dro_display, yaml),
`configs/ned5/ned5_iron.hal` + `configs/params/*.inc`, `tools/live/ned_brain.py`,
`tools/live/ned_pendant.py`, `tools/run5.sh`, the comps (limdir/jogblock/pso_live).
Rebuilding = reinstall PB + re-add the undeclared deps + re-verify the
core-touch register below.

## 1. Reinstall recipe (fresh box → PB runs)

1. `tools/live/qt_pb.sh` (will FAIL mid-way — expected).
2. apt: `cmake python3-dev`; venv pip: `PySide6 vtk docopt sqlalchemy psutil
   pyudev pybind11 pyqtgraph simpleeval py-spy`.
3. Resume from the failed step (qcompile → qnative → pip -e probe_basic →
   qcompile → fonts → config copy). Do NOT re-run qt_pb.sh (wipes the venv).
4. `qnative --backplot` must end "ok built" (needs cmake + python3-dev + pybind11).
5. Launch only via `tools/run5.sh` (venv PATH + logging + resume mode).

## 2. GUI feature inventory (the "outcome" to compare a rebuild against)

- **DRO panel** (`user_dro_display/xyzac_dros/`): whole-row yellow highlight of
  the MPG-selected axis (fed in Qt from the ned_controls tab); unhomed axes
  show live JOINT positions (world freezes with kinstype=B); REF ALL/REF X
  rebound (gantry-safe, see §4); ZERO buttons: 3 s countdown per button,
  second click cancels, parallel countdowns merge into one G10, defer while
  busy; REF ALL label shows true joint homed state (stock all_axes_homed LIES
  when NO_FORCE_HOMING=1, status.py:685).
- **ned controls tab** (`user_tabs/ned_controls/`): TOOLPROBE button (green=up
  red=down grey=NO AIR, air-interlocked, ORs into sol.ts); UNLOAD SPINDLE
  wrapped with 5 s cancelable countdown; hides jogDisplay + MAN/AUTO/MDI box +
  Flood menu; pendant→screen sync (increment button click-sync, jog-speed
  slider follow); qtpyvcp setTaskMode MDI-gate removal (monkey-patch);
  homeall pin pulse for brain.
- **LOCK A / LOCK C** (`user_dro_display/xyzac_dros/`): the A/C ZERO buttons
  repurposed as checkable LOCK toggles (operator: A/C are only ever zeroed at
  their physical zero by REF). Locked axis = skipped ENTIRELY in the MPG
  selection cycle: dros `_ac_lock` -> tab `set_ac_lock` -> `ned-tab.lock-*-out`
  -> `sig-lock-a/-c` -> `pendant.lock-a/-c`; pendant `adv()` skips, auto-kicks
  if the selected axis gets locked. ZERO ALL now zeroes X Y Z only. (The
  OFFSET DRO page's stock zero_a/c buttons are untouched.)
- **MOVE panel** (`user_tabs/ned_moves/`): lives ON THE JOG PAGE (reparent);
  typed ABS/REL XYZAC moves + panel-local F + presets ALL→0/XY→0/AC→0/Z+6;
  scroll-area wrapped (raw stack blew the window to 1920x1359).
- **HOLES tab** (`user_tabs/ned_holes/`): X/Y table, POPULATE X/Y dialogs
  (start + N + increment↔end toggle), hover-✕ cell clear, blank=skip,
  retract/depth/feed + RUN HOLES (G81 per row), CLEAR TABLE. BORE mode
  (2026-08-01): BORE dia set -> TOOL dia required + STEP mm/pass, orbits
  each hole to size (bore_14_pairs pattern); BORE blank = plain drill.
- **Pendant** (`tools/live/ned_pendant.py`): tap=next axis, double-tap (0.36 s
  window)=back, press+rotate=jump size stepping the on-screen INCREMENTS list
  (25 detents/step), double-tap+HOLD+rotate=jog-speed slider 1%/detent;
  A/C capped 1°/detent.
- **Brain** (`tools/live/ned_brain.py`): head A/C read→arm→home→verify cycle
  triggered ONLY by REF ALL (homeall pin); guard aborts un-armed A/C homing;
  X-pair seq flip (see §4); stored-home saver + resume arming; teleop
  recovery; MANUAL-on-idle edge; gui.md event log; all reads on OWN netted
  pins (never hal.get_value — mutex freeze class).
- **Config**: mist toggle + M7 = chip blower (Flood hidden); spindle override
  20–200 % (absolute 18000 clamp is the guard); startup S1000; notifications
  persistent:false (no ghost toasts); CPP_BACKPLOT=0; LOG_LEVEL INFO;
  ned_pb_params.inc = PB-side params (spindle 1000/18000).
- **Subroutines** (config-local, ned iron): unload_spindle (S3-stopped gate →
  release → sensor verify → software unload), clamptool/unclamptool (P0 +
  locked/released sensors), load_spindle_safety_2 clamps first; 18 sim
  routines NEUTERED (ATC/orient/surface_test — sim pin numbers hit ned's own
  solenoids: sim M64 P4 = ned chip blow-off, sim "compensation" P0 = drawbar).
  NOTE: ned is getting a 15-pocket RACK ATC (being built) — when mounted,
  adapt PB's rack_atc_sim flow + ATC_TAB_DISPLAY=2 + measured pocket table.

## 3. Iron/HAL additions (survive updates, listed for completeness)

limdir (directional limit gating; X/Y/Z direction truth operator-confirmed:
homing triggers are +X +Y +Z-up — old neg/pos mapping was inverted), jogblock
(wheel gates), shaft.edge+shaft.spin (HQD S3 is a PULSE source, manual:183-185
— stopped = no edges for 1 s via edge(both)+retriggerable oneshot.out-not),
brain/pendant/ned-tab netted pins in postgui_pb.hal. Capacity squeeze UNDONE
(operator, 2026-08-01: "done with this risky shit"): HOME_OFFSET back to 5 mm
all XYZ, X MAX_LIMIT back to 1.0, far limits pulled back 4 mm (X -4042.725,
Y -1787, Z -620), `tools/hardlimits_off.sh` moved to trash/tools/ -- nothing
runs without limit switches anymore. NOTE: the 4 mm datum shift means stored
work offsets and stored-home resume data from before 2026-08-01 are stale.

> UPDATE PROCEDURES (both PB and LinuxCNC) now live in
> **docs/update_survival.md** — the read-before-updating doc with
> detection, restore and checklists. This register remains the
> authoritative core-touch table it references.

## 4. CORE-TOUCH REPLUMB REGISTER — re-verify EVERY item after any PB/qtpyvcp update

Runtime pokes at core widgets/APIs (no source edits; they break silently if
upstream renames things). Grep key: the names below.

| # | Touch | Where (ours) | Core names relied on |
|---|-------|--------------|----------------------|
| 1 | hide jog panel + mode box | ned_controls HIDE_CORE | `jogDisplay`, `horizontalWidget` |
| 2 | hide Flood menu entry | ned_controls _tick | `action_Flood_toggle` |
| 3 | MOVE→JOG page reparent | ned_moves._move_into_jog_page | `sb_page_1` (QVBoxLayout), `user_sb_tab` |
| 4 | increment click-sync | ned_controls._on_inc | `jogincrement`, private `_buttons_by_value` |
| 5 | jog-speed slider set | ned_controls._on_jogspeed | `linear_jog_slider` |
| 6 | UNLOAD countdown rebind | ned_controls._wire_unload | `remove_tool_2` (SubCallButton) |
| 7 | REF ALL / REF X / ZERO rebinds | dros_xyzac __init__ | `ref_all_button`, `ref_x_button_3`, `zero_*_button` (our .ui, but ActionButton internals) |
| 8 | setTaskMode stale gate -> LIVE motion gate | ned_controls._remove_mdi_mode_gates | `qtpyvcp.actions.base_actions.setTaskMode`, `CMD`, `_get_stat` |
| 8b | Mist menu text -> "CHIP" | ned_controls._tick | QAction `action_Mist_toggle` |
| 8c | Homing menu (yml HomingMenu provider): ALL entries rebound to ned-safe cycles (All/X/Y/Z/A/C) | ned_controls._tick | menubar.yml `qtpyvcp.widgets.menus.homing_menu:HomingMenu`, menu title "Homing", action texts "Home All/X/Y/Z/A/C" |
| 8d | Spindle FWD/REV -> "Check" 3 s countdown (then spindle_actions.forward/reverse) | ned_controls._wire_spindle_check | buttons `spindle_forward_button`, `spindle_reverse_button` |
| 8e | Load meter -> chip-load placeholder; RPM stack -> commanded-speed label (layout.replaceWidget -- QGridLayout has NO insertWidget, crashed 13:0x; FSR button clusters tried + REVERTED) | ned_controls._restyle_spindle_section/_tick | `spindle_load_indicator`, `spindle_rpm_source_widget` |
| 8g | Homing menu rebind is BY ACTION TEXT across the whole menubar (menu-title matching silently found 0 and left STOCK bindings live -> one-sided Home X RACKED the gantry 13:08; rebind now loud on failure; brain one-sided-homing interlock added as the real guarantee) | ned_controls._tick | action texts "Home All/X/Y/Z/A/C" |
| 8f | V-slider units label | ned_controls._tick | StatusLabel `max_vel_slider` |
| 9 | probe LED net | postgui_pb.hal | pin `qtpyvcp.probe-led.on` |
| 10 | mist=blower net | postgui_pb.hal | pin `iocontrol.0.coolant-mist` (stable LinuxCNC) |
| 11 | REF X/ALL seq flip | dros/_ref_x_both, ned_controls.request_homeall, brain restore | `ini.0/3.home_sequence` runtime pins (stable LinuxCNC; homing.c:637 rebuilds sync set) |

GANTRY LAW (never violate, see the safeguards section above): X pair homes
ONLY via the synchronized negative-sequence machinery; never one-sided homes,
never concurrent individually-commanded home() pairs (wedged joint 4's state
machine; ferror'd joint 3 via frame drag).

## 5. Known-broken + intended fixes

- **G-code viewer blank**: PB ships `gcodeeditorplugin.so` as x86-64; on the
  Pi (aarch64) QUiLoader can't load it → bare QPlainTextEdit shows nothing.
  REAL FIX: move the venv to DISTRO PySide6 (apt python3-pyside6 6.8.2 +
  qt6-base-dev/qt6-tools-dev — matching Qt ABI, the arrangement qt_pb.sh
  assumed all along) and build the plugin natively. Do NOT build against apt
  Qt while running pip PySide6 6.11 (ABI mismatch, plugin rejected).
- **Backplot invisible**: Pi GL ceiling is 3.1, VTK wants 3.2. Escape hatch:
  LIBGL_ALWAYS_SOFTWARE=1 (llvmpipe, CPU cost). Also prime suspect for the
  one unexplained GUI death. Interim: preview via `rs274 -g` → artifact plot.
- **Spindle RPM readout stuck at fallback**: `spindle_stat_rpm` StatusLabel
  rule never binds live data; and PB has NO rpm entry AT ALL (S word +
  override only). Machine has no spindle encoder — commanded = S × override.
- **HAL mutex wedge class**: any killed-mid-call HAL client leaks the global
  mutex → every hal.get_value/halcmd spins, GUI freezes. Our code no longer
  uses get_value anywhere. Recovery: kill ALL HAL participants incl. halcmds,
  `halrun -U`. ONE launcher only (the operator launches; overlapping launches
  caused the wedge).
