# A/C home-pin race — root cause and the gate that closes it (2026-08-07)

Machine notes affected: `docs/gui.md` (homing menu), `docs/update_survival.md`.

## What happened

On the 09:47:23 launch, `do_inplace` declared A at +57.344 (correct, no
motion) and C at +114.705 — and C **physically travelled −114.7048 deg**.
A declare must not move the head at all.

Arithmetic, from `lcnc.log` and the live pins: absolute homing sets the
joint position from `home_offset`, then moves to `HOME`, so
travel = `HOME − home_offset`. C had `home_offset = 114.7048` and
`HOME = 0`, giving exactly the −114.7048 observed
(`joint.5.motor-pos-fb −239.4548` vs `pos-fb −124.75` → motor_offset
−114.7048).

## Why `HOME` was 0

The destination is latched at `homing.c:1279`

```c
joint->free_tp.pos_cmd = H[joint_num].home;
```

inside `case HOME_FINAL_MOVE_START` (`homing.c:1254`, enum value 20 at
`homing.c:98`). Any write to `ini.N.home` that lands between `cmd.home()`
and that latch changes where the joint goes.

`do_inplace` looped: set `ini.4.home`, `cmd.home(4)`, `wait_complete()`,
wipe `ini.4.home`, set `ini.5.home`, `cmd.home(5)`, wipe `ini.5.home`.
`wait_complete()` is a **no-op** after `cmd.home()` — `emcmodule.cc:1121`
calls only `emcSendCommand`, which already polls for the echo — so every
one of those writes happened while joint 4 was still in its homing
sequence. `do_home_one_joint` (`homing.c:265-281`) stamps `HOME_START`
without checking whether another joint is mid-cycle, so nothing refuses
the overlap and nothing reports it.

Ruled out along the way: propagation delay (`emctaskmain.cc:3394-3396`
reads the ini HAL pins *before* the command each cycle);
`base_update_joint_homing_params` refusing mid-homing (it has no guard);
a netted pin fighting the write (`ini.5.home` has no signal); a limit
clamp (C is ±315).

## The gate

Six independent writers of `ini.4/5.home*` is why this could not be
reasoned about. There is now exactly one, in `tools/live/ned_brain.py`:

1. **`set_home_pins(jn, home, offset, why)`** — the only writer.
   Gate → write both pins → **read each back with `halcmd getp` and
   compare** → only then may the caller command. A `setp` that was lost or
   late aborts the home instead of homing to someone else's number.
2. **`head_quiet()`** — refuses unless **both** head joints read
   `HOME_IDLE`. `joint.N.home-state` is netted to `brain.hstate-4/5-in`
   (`postgui_pb.hal` / `postgui_tcp_all.hal`); the enum is
   `homing.c:76-100`. Both joints, not just the one being homed, because
   `do_home_one_joint` will not tell you the other one is busy.
3. **Nothing is written between the command and confirmation.** The wipe
   drains only when every head joint is back at `HOME_IDLE`.
4. **`do_inplace` homes ONE joint per pass** and returns; the tick retries
   the second once the first is confirmed idle.
5. **The read no longer touches the pins.** `hr_report` used to arm
   `ini.N.home_offset` at read time, leaving the number in the pin from the
   read until the home. The measurement now lives only in `self.hr_deg`
   until `set_home_pins` consumes it.
6. **The wipe is no longer load-bearing.** Because every home is preceded
   by a fresh write+read-back of both pins, a leftover can never be what a
   later home consumes. A late or missed wipe is now hygiene, not a crash.

### Detector

`do_inplace` snapshots `joint.N.motor-pos-fb` when it arms the pins; the
homed edge re-reads it. `motor-pos-fb` is raw motor position, untouched by
`home_offset`, so any change is real motion. A declare that moves logs
`DECLARE MOVED THE HEAD` and pops a LinuxCNC error. The −114.7048 swing
would have been caught on the first occurrence.

### Lockout

`brain.head-busy` is TRUE from the first pin write until positive
confirmation — no read running, no pending ref, no verify outstanding, no
owed wipe, and both head joints at `HOME_IDLE`. It nets to
`ned-tab.head-busy-in`; `NedHomingMenu._ready_poll` greys all six entries
while it is set, and `_fire` refuses again at click time with an
`error_msg` (the 500 ms poll can be half a second stale). It fails
**closed** — if `ned_controls.head_busy()` is unreachable the menu stays
disabled.

`stat.joint[j]['homing']` was already in the readiness test and is not
enough: on a zero-travel declare it can rise and fall inside one 500 ms
poll, which is the window a second homing click lands in.

## A′ — the leftover offsets

`do_inplace` restored `ini.N.home` but never `ini.N.home_offset`, so every
launch left the read angles parked in the pins (measured live: A 57.3436
with A at 102.59, C 114.7048 with C at −124.75). The confirmed wipe now
clears both. Exposure had been gated by `HOME_NO_REHOME` short-circuiting
at `homing.c:766-770`, which opens the moment anything unhomes the joint —
and `verify_fail` does exactly that.

## Status

Written and offline-verified only: `py_compile` clean, `cfg_edit.sh`
scanner green on both postgui files. **Not yet run on the machine.** First
launch must show, in `lcnc.log`:

- `HOME PINS: joint N armed ... (both read back OK; home-state 4/5 = 0/0)`
- `DECLARE: joint N did not move (... -> ...) -- correct` for both joints
- `HOME PINS: joint N wiped (home + home_offset)` after each
- `NED Homing menu disabled (... head-busy=True)` during the declare, then
  `ENABLED ... head-busy=False`

If `home-state 4/5` reads `0/0` even while a home is running, the postgui
net is missing and the gate is passing blind — that is the one failure
mode this design cannot self-detect.


---

# 2026-08-08 night: why C stayed unhomed, and what was actually wrong

The 2026-08-07 gate above was correct but the launch still stranded joint 5
and locked the whole GUI behind it. Root cause was NOT the gate. Evidence
and fixes, all verified live with the machine in E-STOP (no motion, not one
command issued to an axis).

## The chain

`do_inplace()` homes ONE joint per pass and re-arms `inplace_pending` for
the next, so it depends on being called periodically. It had no periodic
caller:

- `tick()` called it only behind `inplace_at`, a one-shot.
- `inplace_at` was assigned in exactly one place, the machine-ON edge, and
  only `if self.read_armed and ...` — **fifteen lines below
  `self.read_armed = False`, with nothing in between to set it back.**
  Unsatisfiable. `inplace_at` was never assigned in any session.
- So `read_done()` was the only caller. Joint 4 homed, joint 5 never did,
  `all(homed)` stayed false, `restore_spindle_tool` could not run, the tool
  record stayed T0 against a clamped tool, and the UNRECORDED lock plus the
  pre-home input gate held the GUI dead. 13 minutes, no message.

Proof it was reachability and not a guard: `inplace_at` has one assignment
site; the log shows the *else* arm firing
(`MACHINE ON -> head read (A/C will home IN PLACE, no motion)`, and the
other arm's message appears in no log ever); `sh_save` sits *after* the call
site in `tick()` and `stored_home.json` kept updating, so the tick was
running past it every cycle; `wchan = hrtimer_nanosleep`, one thread — the
brain was not blocked in a scripted `halcmd`.

## Fixes, and how each was verified without moving anything

1. **Periodic caller.** `do_inplace()` is now called unconditionally every
   tick; the mode/teleop switch moved below the `jns` computation so a tick
   with nothing to do does not fight the operator for the task mode.
   *Verified:* new pin `brain.inplace-calls` climbed 48 → 97 in 12 s (~4 Hz)
   with `homed4/5` FALSE in E-STOP. It would have read 0 forever before.
2. **Silent declines named.** The `inplace_pending / pending_ref /
   verify_want / read_armed` guard now logs its reason, once per change.
   *Verified:* `IN-PLACE HOME: standing by -- nothing pending` printed once
   and did not repeat across 400+ calls.
3. **`inplace_pending` is cleared on completion, not on entry.** It used to
   be dropped before `jns` was computed, so an unhomed joint with no
   measurement was removed from the list AND the retry discarded in the same
   breath. *Verified:* at 22:42:55 `declare_xyzw` had already declared all
   six, `do_inplace` logged `proceeding`, found nothing unhomed and cleared
   itself.
4. **A missing measurement is named, not silently dropped** — an unhomed
   head joint with `hr_deg[ax] is None` keeps the routine pending and says
   so. *Code only; needs a failed read to trigger.*
7. **The unsatisfiable pre-launch branch and dead `inplace_at` deleted.**
   Always a fresh read after power-on — a read taken after the drives are
   energised describes the head at the moment it is declared.
   *Live evidence of the defect:* the pre-launch read armed at 22:41:27,
   power-on at 22:42:45 logged the else arm, and a second identical read ran
   at 22:42:50-55. Every launch paid for a read it threw away.

`brain.inplace-calls` is permanent on purpose: the failure was invisible
because a routine that declines silently looks exactly like a routine that
is never called. `halcmd getp brain.inplace-calls` now separates them.

## Air interlock (2026-08-08, compressor off)

`sig-emc-enable = air.permit.out = sig-estop-released AND
sig-air-ok-debounced`, and `sig-air-pressure-ok` is 7I97 `inmux.00.input-12`
(TB5-7). With air removed, `iocontrol.0.emc-enable-in` is FALSE and the
machine cannot leave E-STOP at all — a hard blocker on the road to stale
home. Defeated for bench work with:

    halcmd unlinkp air.debounce.in
    halcmd setp air.debounce.in 1

**Every HAL reload wipes it** — it must be re-applied after each launch.
Undo with `halcmd net sig-air-pressure-ok air.debounce.in`.

## The rest of the class, triggered offline against the real code

The remaining defects only appear after a machine-ON edge, which schedules
the declare -- barred on the bench ("DO NOT MOVE THE MACHINE AT ALL. NOT
EVEN HOMING"). So they were triggered with `tools/brain_harness.py`, which
execs ned_brain.py's own text with the driver loop cut and hal/linuxcnc/
GUI_LOG stubbed. The `do_inplace` that runs there is the file the machine
runs, character for character -- not a reimplementation.

Run the same scenarios against `git show <sha>:tools/live/ned_brain.py` to
tell a real defect from a guess. Results, new code vs commit 43cf5db:

| scenario | old | new |
|---|---|---|
| C unhomed, `hr_deg['c']` is None | 0 logs, 0 homes, **`inplace_pending` dropped to False** -- and still nothing after the read lands: stranded for good, silently | names the gap ONCE, holds pending, declares the instant the measurement arrives |
| declines with a REF queued | 0 logs | `standing by -- a REF is queued for joint(s) [5]`, once |
| declines on verify / no armed read / not pending | 0 logs | one line each, named, once |
| A and C both unhomed and measured | one pass only, C stranded (no periodic caller) | joint 4 then joint 5 on successive passes, pending held until both, then cleared |
| both already homed | -- | no command issued, pending cleared |

So: defect 4 CONFIRMED real and fixed; defect 5 (the fixed `(4,'a'),(5,'c')`
order) is real but harmless once a periodic caller exists -- both joints get
declared, A simply goes first; defect 6 (a home silently no-oping on an
already-homed absolute joint, `homing.c:766-770`) is **REJECTED** as a live
risk: `do_inplace` lists only unhomed joints, so it never hands a home to a
homed one, and `fire_pending_refs` unhomes before it homes.

One thing the night did demonstrate: the launch declare is genuinely
zero-motion. At 22:42:49 all six joints went homed via `DECLARED HOME
(zero-motion, NML 112)` — a set-position, not a move — with A at +102.5877
and C at -124.7503, unchanged all evening, and `do_inplace` never issued a
single `cmd.home()`.
