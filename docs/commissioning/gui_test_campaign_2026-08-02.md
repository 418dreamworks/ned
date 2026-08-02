# GUI test campaign — 2026-08-02 (unattended, ~4 h)

Operator brief: *"TEST every single button and function in the gui so long
your movement is restricted to that 10cm box from physical home … pretend to
be a human who attempts to break every single rule and see what happens. you
really must close all errors as you record them, and never wait more than 15
seconds for something unless you KNOW you will need to wait longer."*

Frame: work zero at machine **−50, −50, −50**; every move inside the 10 cm
cube. `gt/boxguard.py` polled 5×/s and would have aborted any escape — **it
never fired once** across ~250 machine operations. The spindle was never
started. Raw log: the session's `gt/report.md`.

## Result

| Phase | What | Verdict |
|---|---|---|
| 1 | 11 tabs, jog speeds, presets, typed moves, zeros, locks, overrides, units | 25 pass, 0 fail |
| 2 | Adversarial: garbage input, limit violations, mid-motion clicks, spam, locked axes | 10 pass, 0 fail (re-run clean) |
| 3b | Effect verification: override values + ZERO buttons read back | 18 pass |
| 4 / 4b | Control panel, GO TO buttons, jog increments, MDI entry | 7 pass, 4 skipped on rules |
| 5 / 5b | Homing menu with start-detection, E-STOP, recovery | 17 pass |
| 6 / 6b | Menu bar, right column, notifications, offsets, file, tool table | 15 pass |
| 7 | Parameter persistence across a real restart | 3 pass |

Measured on the machine: jog speeds **200 / 1200 / 2670 mm/min**; typed and
preset moves land within **0.03 mm**; Home All runs Z → Y → X-pair with A/C
parallel in **32 s**; single-axis homes 9–13 s.

## Product bugs found and FIXED

1. **One REF killed every later REF** (`7d4ea4b`). Home A then Home C refused C
   with "previous head cycle still completing" — permanently, for the rest of
   the session. The brain's homed-edge tracker sat below `if self.hr_step:
   … return`, so the unhome-and-rehome that happens *inside* a ~5 s head read
   was never seen; no rising edge, no post-home verify, and `verify_want`
   stayed set — which is exactly the flag the REF serialization guard tests.
   Fixed by tracking edges at the top of the tick. Verified: `HOME VERIFY OK
   (A)` then `HOME VERIFY OK (C)` back to back.

2. **Intermittent dead presets** (`4e51d70`). "task_mode never reached MDI" —
   the panel asked for MDI, waited 2 s and quit, losing a race with the
   brain's MANUAL restore. Now re-asserts across 4 s and logs how many tries
   it took.

3. **The same message had two meanings** (`d05818e`). It also appears benignly
   before the declare lands, because LinuxCNC silently refuses MDI on
   non-identity kinematics until all six joints are homed. The message now
   reports homed state and `echo_serial` and says RESTART REQUIRED only for
   the real wedge.

## Behaviour confirmed (not bugs — recorded so nobody "fixes" them)

- Presets and GOs are **locked during motion**; a mode switch mid-move
  **aborts** it. Both by design.
- **V and R overrides cap at 100 %**, F and S reach 110 % — LinuxCNC ceilings.
  Feed floors at 0 with no wrap-around.
- **The GUI E-STOP is a machine-off, not a software e-stop.** It takes
  task_state 4 → 2 with `stat.estop == 0`, because the external chain is the
  authority (`ned5_iron.hal:262-269`). It does stop the machine and refuse
  moves, but it is **not** a substitute for the physical button. **Homing
  survives it** — no re-home needed.
- **LOAD SPINDLE with T0 aborts** ("Tool 0 is already stored in carousel"):
  the stock occupancy loop treats an empty pocket, which holds 0, as a match.
- Parameter persistence now works end to end: markers written → clean
  shutdown → present in the var file → relaunch → still there.

## Open: the task wedge (finding 17) — NOT root-caused

After ~90 min of continuous adversarial clicking, LinuxCNC's task stopped
accepting commands entirely:

- `task_mode` stuck at MANUAL; `cmd.mode(MDI)` had no effect
- `echo_serial_number` **frozen** across three different requests — task was
  not consuming the command channel at all
- `linuxcnc.error_channel()` returned **nothing**
- milltask alive, 0.4 % CPU, parked in `do_select` (its normal idle wait)
- status still updating, so the DROs looked completely normal
- GUI-only clicks failed identically → not an artifact of the test harness's
  python client

Only a restart cleared it. **It did not reproduce** in an immediate re-run of
the identical sequence, so a soak (`gt/soak.sh`) was left running to repeat the
adversarial phase and capture a full dossier the moment it recurs.

**Distinguishing test if you ever see it:** `echo_serial_number`. If it
advances, task is alive and merely refusing (usually: not homed). If it is
frozen while commands are being sent, it is this wedge — restart.

## Skipped deliberately, with reasons

- **Spindle** — operator rule: never start it. A draft test that issued M3 and
  killed it a second later was written, blocked, and removed: intending to
  switch it off again is not an exemption.
- **Rack / ATC / M6** — the rack lies far outside the box.
- **Probe cycles** — they plunge Z up to 300 mm and drive to the setter.
- **Program RUN** — any real g-code file leaves the box.
- **Tool table SAVE/DELETE** — writes operator data (the db was backed up and
  verified unchanged: T1, T2 intact).

## Testing lessons (they cost five wrong results)

A click that lands in the wrong place looks **exactly** like a pass.

1. qtpyvcp error toasts are Qt widgets **inside** the PB window — no X window,
   invisible to xdotool/wmctrl — and they stack up and **swallow clicks**. An
   entire 11-tab sweep "passed" while clicking stale error boxes.
2. Coordinates typed instead of measured produced three false failures
   (readout instead of +10 %, tool-table row 340 px low, panel 31 px stale
   between launches). Widget positions **shift between launches**;
   `ned_controls` dumps live ones at +9 s and `harness.jp_coords()` reads them.
3. Typing into the g-code editor believing it was the MDI line voided every
   MDI verdict — including a comforting "M3 did not spin the spindle" that
   proved nothing, since the command never reached the interpreter. Retracted.
4. Know the interaction before scoring it: the DRO zeros are **one** click plus
   a 3 s countdown, and a second click **cancels**. Double-clicking them
   cancelled the test and looked like a broken button.
5. For homing, require proof the joint actually **unhomed** — otherwise a
   menu entry that does nothing scores identically to a full cycle. That is
   precisely how bug 1 hid as a pass.

**Rule adopted:** verify an observable effect (position moved, status value
changed, log line appeared). "No error appeared" is not a pass.
