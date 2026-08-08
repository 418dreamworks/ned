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
