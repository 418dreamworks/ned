# ned GUI (nedgui) — QtVCP 5-axis screen

ProbeBasic-style QtVCP screen for the **5-axis** case (X, Y, Z, A head-tilt, C
head-spin — no rotary B), with a dead-simple "add a tab" mechanism.

## GUI engine

`nedgui` is a QtVCP screen (QtVCP is the engine ProbeBasic is built on).
ProbeBasic itself is not installed and not packaged for LinuxCNC 2.9.8 aarch64;
QtVCP is installed (`/usr/lib/python3/dist-packages/qtvcp`, PyQt5 5.15.11 / Qt
5.15.15). **Nothing to install.**

## What was created (all new, nothing existing was touched)

```
configs/
  ned/                     <- UNCHANGED working machine config (DISPLAY = axis)
  params/                  <- CENTRAL parameterization (shared .inc fragments)
    display_common.inc  traj_common.inc  emcmot.inc  rs274ngc.inc  spindle_0.inc
    axis_x.inc axis_y.inc axis_z.inc axis_a.inc axis_c.inc
    joint_x1.inc joint_y.inc joint_z.inc joint_x2.inc joint_a.inc joint_c.inc
  ned5/                    <- NEW thin 5-axis case config
    ned5.ini               <- thin: structure only, #INCLUDEs ../params/*.inc
    ned5.hal               <- SIM loopback HAL (no Mesa; GUI-dev only)
    postgui.hal            <- GUI HAL glue (placeholders live here)
    ned5.var  tool.tbl
    qtvcp/screens/nedgui/
      nedgui.ui            <- main screen: control column + DRO + tab area
      nedgui_handler.py    <- the PAGES list + page loader
      pages/
        page_01_overview.ui   (backplot + MDI)
        page_02_demo.ui       (worked "how to add a page" example)
        page_mpg.ui           (placeholder: MPG axis+speed indicator)
        page_limits.ui        (placeholder: limit-switch-hit light)
```

## Launch it

The `nedgui` screen runs on a **SIM loopback HAL** — it loads **no Mesa driver**
and cannot move a real axis. It is for building/laying out the GUI. First make
sure the real machine config is **not** already running (HAL shmem clash):

```
pgrep -a linuxcnc          # must be empty
linuxcnc /home/brains/Documents/ned/configs/ned5/ned5.ini
```

Estop clears, POWER turns on, jog works, all tabs show. (Homing X/Y/Z won't
complete in SIM — no home switches; A/C home immediately. Not needed for GUI work.)

Notes if this screen is ever pointed at a real (Mesa) HAL instead of the SIM:
- The **HOME ALL** button is non-checkable, so a *second* press **unhomes** the
  machine (stock qtvcp behavior). Change it or split home/unhome before real use.
- `ned5.ini` has a bare `[HALUI]` section but no `HALUI = halui` in `[HAL]`
  (mirrors `ned.ini`). If a future MPG page needs halui pins, add `HALUI = halui`.

### Switch back to the real machine

Nothing to undo — the working config is untouched. Just launch it as always:

```
linuxcnc /home/brains/Documents/ned/configs/ned/ned.ini
```

## How to ADD A PAGE (the whole point)

Two steps:

1. **Drop a `.ui` file** into `configs/ned5/qtvcp/screens/nedgui/pages/`.
   Its root widget must be a plain `QWidget`. Copy `page_02_demo.ui` to start.
2. **Add one line** to the `PAGES` list at the top of `nedgui_handler.py`:

   ```python
   PAGES = [
       ("Overview", "page_01_overview.ui"),
       ("Page 2",   "page_02_demo.ui"),
       ("My Tab",   "my_new_page.ui"),   # <- the one line you add
       ...
   ]
   ```

That's it — restart the GUI and the tab is there. `page_02_demo.ui` (the "Page 2"
tab) exists purely as the worked example; delete the file and its line to remove it.

**Rules (only two):**
- **Unique objectNames.** Every widget `objectName` must be unique across *all*
  pages *and* `nedgui.ui`. A qtvcp HAL widget turns its objectName into a HAL pin,
  so a duplicate name = duplicate pin = the screen won't load.
- Pages may use plain Qt widgets **or** qtvcp widgets. To use a qtvcp widget,
  add its `<customwidget>` entry (class + `qtvcp.widgets.<module>` header) to the
  page's `<customwidgets>` block — see `page_limits.ui` (uses the `LED` widget)
  and `nedgui.ui` for the exact form.

A page that fails to load can't crash the GUI — it becomes a red `!Tab` showing
the error and the other pages still load.

### Validate a page offline (no LinuxCNC needed)

```
cd /home/brains/Documents/ned/configs/ned5/qtvcp/screens/nedgui
QT_QPA_PLATFORM=offscreen python3 -c "import sys;from PyQt5 import QtWidgets,uic;\
QtWidgets.QApplication(sys.argv);uic.loadUi('pages/my_new_page.ui');print('OK')"
```

This catches XML/property errors. (HAL pin creation is only exercised at real
launch, so also start the SIM config once after adding HAL widgets.)

## Config architecture — thin INI + central parameters

`ned5.ini` is deliberately thin: it holds only case structure (JOINTS=6,
`KINEMATICS = trivkins coordinates=XYZXAC`, `COORDINATES = X Y Z X A C`,
`DISPLAY = qtvcp nedgui`, HAL/tool/var filenames). Every machine value (limits,
velocities, PID, scale, home) lives in `configs/params/*.inc` and is pulled in
with LinuxCNC's `#INCLUDE`:

```ini
[AXIS_X]
#INCLUDE ../params/axis_x.inc
[JOINT_4]
#INCLUDE ../params/joint_a.inc     ; A tilt is JOINT_4 in the 5-axis map
```

- `#INCLUDE` is expanded by the `linuxcnc` launcher into `ned5.ini.expanded`
  before start (it is *not* understood by `inivar`/`halcmd` reading the raw file).
  Paths are relative to `ned5.ini`'s directory. Edit a value in the `.inc`, not
  in `ned5.ini`. All `.inc` values were lifted **verbatim** from `ned/ned.ini`.
- **Joint map (5-axis):** `0=X  1=Y  2=Z  3=X(gantry twin)  4=A  5=C`.

### ⚠ ned_params.sh does NOT know the 5-axis joint map

`tools/live/ned_params.sh` is the source-of-truth for the A/C `SCALE` constants
(`SCALE_A = DRIVE_PPR*GEAR_A/360`, etc.), but its `apply`/`sync` writer keys on
the **old 8-joint** map (J4 = rotary-B, J5 = A, J6 = C) and only rewrites `.ini`
files. In `ned5` **A is JOINT_4 and C is JOINT_5**, so running `ned_params.sh`
against `configs/ned5` would write the **rotary** scale onto the A axis — a wrong
number on a head axis, silently. **Do not run `ned_params.sh apply/sync` against
`ned5`** until its joint map is taught the 5-axis layout. The current derived
scales are hand-placed in `params/joint_a.inc` (2918.4000) and `params/joint_c.inc`
(4636.3785); update them by hand if the gear ratios change.

## Pending GUI features (stubs — obvious homes, not implemented)

- **MPG axis + speed indicator** — `pages/page_mpg.ui`, labels `lbl_mpg_axis` /
  `lbl_mpg_speed`. Real data comes from `mpgjog.comp`; wire in `ned5/postgui.hal`.
- **Limit-switch-hit light** — `pages/page_limits.ui`, `LED` widget
  `led_limit_hit`. It creates HAL input pin **`nedgui.limit-hit`**; wire your
  summed hard-limit signal to it in `ned5/postgui.hal`
  (`net any-limit <src> => nedgui.limit-hit`). Find it: `halcmd show pin | grep limit-hit`.

(The rotary-B 70V-brick toggle from the original brief was dropped — no B axis in
this 5-axis case.)
