# Tool guard: the boot excuse is gone (2026-08-07)

Machine notes affected: none — the guard's wiring in
`configs/ned5/ned5_iron.hal:331-383` is unchanged apart from one input.

## What the guard is

One sentence: it compares what LinuxCNC thinks is in the spindle
(`iocontrol.0.tool-number`) against what the drawbar sensor says is
physically clamped (`sig-tool-locked`), and if they disagree it inhibits
jog and feed (`tool.mm.lock` → `motion.jog-inhibit` + `motion.feed-inhibit`)
until they agree again.

Two faults, deliberately distinct: **UNRECORDED** (iron holds a tool, logic
thinks empty) and **PHANTOM** (logic claims a tool, iron holds none).

## What was removed

`brain.guard-arm` — a mute switch added 2026-08-05. While FALSE it fed
`tool.mm.narm` → `tool.mm.excuse2.in1`, which excused the guard entirely:
no alarm, no lock. The brain raised it once, from `arm_tool_guard()`, on
`served or late`:

- `served` = `stat.tool_in_spindle` equals the `#3991` record.
- `late` = 25 s elapsed since `_guard_t0`.

`_guard_t0` was assigned **above** the `STATE_ON` early-return, so the clock
started when the brain launched — before POWER, during the pre-launch head
read. By the time the machine was on, 25 s had usually passed, so the guard
armed on the first tick after power-on regardless of whether the tool table
had loaded. On the 09:47:23 launch it printed its own contradiction:

```
2275  TOOL GUARD ARMED (timeout backstop): record T2, LinuxCNC T0
2276  TOOL IN SPINDLE, NOT IN LOGIC: something is clamped but the machine has no record of it
2278  TOOL-STATE LOCK ENGAGED: no movements until the spindle record matches the drawbar sensor
2296  SPINDLE RESTORE: T2 re-declared in spindle after reboot ... tool_in_spindle=2
2300  TOOL-STATE LOCK RELEASED -- jogging is live
```

**That alarm was correct.** A tool was clamped and LinuxCNC had no record of
it. The guard said so, locked motion, and released itself two seconds later
when the record was reconciled. The defect was never the message — it was
that a safety interlock had been switched off to stop it being printed, and
that the moment it switched back on was decided by a wall clock.

Operator, 2026-08-07: *"instead of this guessing wall clock and having no
guard to avoid some false error message"* … *"i don't mind waiting a little
longer for the launch to happen, but i don't want it to be possible for me
to break the machine."*

## What it is now

The guard watches from HAL load. `tool.mm.excuse2.in1` is `setp` to 0; the
`tool.mm.narm` inverter, both `sig-guard-arm` nets, the `brain.guard-arm`
pin and `arm_tool_guard()` are deleted.

Consequence at boot: while iocontrol has not yet served the tool table
(python + sqlite, seconds) and a tool is clamped, the picture is
inconsistent, so **jog and feed are inhibited**. That is the intended
answer to "I do not know what is in the spindle". It clears itself when
`restore_spindle_tool` re-declares the tool.

**Homing is not inhibited**, so the boot declare still runs and clears the
lock. Verified in source: `jog_inhibit` is read only by the jog command
handlers (`command.c:781, 849, 928`) and the jog-wheel/teleop path
(`control.c:255-258`); `feed_inhibit` only zeroes `net_feed_scale`
(`control.c:416-418`). Homing drives `joint->free_tp` directly
(`homing.c:173`, `:1290`) and consults neither.

The other two excuses are untouched, because they are real states rather
than boot artifacts: mid-toolchange / drawbar open (`tool.mm.excuse`), and
the deliberate anonymous load (`sig-anon-load`).

## Second lock: no tool table, no motion

Operator, same session: *"the table MUST load because table not loading is
itself an error and there is no reason to jog"* … *"these are so crucial,
they must be positively verified before user can do anything."*

So the guard's two mismatches are no longer the only thing that locks
motion. A second, independent condition was added, with the same
default-locked doctrine as the head-home gate:

```
tool.mm.lock  = UNRECORDED or PHANTOM
tool.mm.ntbl  = NOT(brain.tool-table-ok)
tool.mm.lock2 = tool.mm.lock or tool.mm.ntbl   -> motion.jog-inhibit + feed-inhibit
```

`brain.tool-table-ok` goes TRUE only on a **positive fact**:
`sum(1 for t in stat.tool_table if t.id > 0) > 0` — iocontrol has served a
table containing at least one real tool. Not a timer, not "it has probably
arrived by now".

Every failure leaves the machine locked, because FALSE is the default on
all three paths: the brain has not published yet, the brain never started,
the postgui net is missing, or the table never loaded. `tool.mm.ntbl.in`
reads 0 when unconnected, so `ntbl.out` is TRUE and motion is inhibited
from HAL load.

The brain logs the transition (`TOOL TABLE: served, N tools -- motion
permitted`) and, if the table has still not arrived after 20 s, says so
once on screen. That message changes nothing about the lock — the lock is
unconditional until the table exists; it only stops a never-loading table
looking like a hang.

The GUI greys `cycle_start_button` and `mdi_entry_box` off
`ned-tab.motion-lock-in`, netted to the same `sig-motion-lock` the motion
controller obeys. Previously `_tool_lock_update` keyed on its own two
Python flags, so with the table missing HAL refused motion while those
controls still looked live.

## Third piece: the GUI is gated, not just motion

Operator, 2026-08-07: *"until machine is stale homed, AND the tool table is
loaded, user cannot press ANY button. after homing and tool table, user
cannot do anything if there is inconsistency between lcnc and tool table.
cannot do anything literally means that. NO BUTTONS work other than going
to ATC/TABLE and setting the table to correct the error"* … *"also power
and estop work of course, those always work."*

Inhibiting jog and feed is not the same as blocking the GUI, so the input
filter (`_PreHomeInputGate`) now serves two windows instead of one. Same
filter, different survivor sets.

**Startup window.** Was `all(stat.homed[:6])` alone; now also requires
`ned-tab.table-ok-in`. An unreadable pin counts as NOT served — fail
closed. Survivors: `exit_button`, `power_button`, `stop_button`. Still
one-shot: it closes once per session and never re-arms, because it used to
re-arm during a mid-session REF read and ate 18 operator clicks
(2026-08-06).

**Inconsistency window.** New, live for the whole session, armed whenever
`ned-tab.motion-lock-in` is TRUE — either a spindle/record mismatch or an
unserved table. Survivors: the three above plus the `atc_tab` and
`tool_tab` PAGES and the tab bar. Naming the pages is sufficient because
the filter walks up parents, so every control inside ATC and TOOL passes.
The tab bar is a survivor or the pages could not be reached.

The cosmetic sweep (`_sweep_gate`) takes a `keep` set and skips any button
descended from a survivor, so ATC/TOOL controls stay **enabled**, not
merely un-swallowed — greying them would hide the only way out.

Keeping the two windows separate matters: the tool condition does not move
during a REF read, so the inconsistency gate can be permanently live
without reintroducing the click-eating regression.

One inherited behaviour, unchanged and deliberate: `_arm_input_gate`
refuses to arm at all if not one survivor widget resolves, and says so
loudly. That fails OPEN. It only triggers when E-STOP itself cannot be
found, where stranding the operator is the worse outcome.

### Head-read failure

Out of scope by operator ruling 2026-08-07: *"the head read failing is a
lower level error. if it fails we have to make it work, and not write
shit."* No accommodation is written for it. Note for the record that if the
head read fails while a tool is clamped, A/C never home,
`restore_spindle_tool` never runs (its gate is `all(homed[:6])` + idle), and
the lock does not clear — the same chain the 25 s timer already produced,
not something this change introduced.

## Alarm wording

Both faults now pop one line: **`CHECK SPINDLE RACK TABLE CONSISTENCY`**.
The direction of the mismatch (UNRECORDED / PHANTOM, and which button
fixes it) goes to `lcnc.log` only. The old on-screen text spelled out the
direction and was read as its own opposite — "TOOL IN SPINDLE, NOT IN
LOGIC" was reported back as *"an error saying tool not in spindle"*.

## Status

Offline-verified only: `py_compile` clean, `cfg_edit.sh` scanner green on
`ned5_iron.hal` and both postgui files, every remaining `not` instance
still has its `addf`, no `narm`/`guard-arm` reference anywhere in
`configs/` or `tools/`. **Not yet run.** First launch must show, in
`lcnc.log`:

- NO `TOOL GUARD ARMED` line — that message no longer exists.
- If a tool is clamped: `TOOL-STATE LOCK ENGAGED` early, then
  `SPINDLE RESTORE`, then `TOOL-STATE LOCK RELEASED`, in that order.
- `CHECK SPINDLE RACK TABLE CONSISTENCY -- UNRECORDED: ...` rather than the
  old wording.
- The boot declare completes despite the lock (homing is not inhibited).
