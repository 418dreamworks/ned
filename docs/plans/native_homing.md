# Native homing — plan (2026-08-10)

Operator: *"i want homing to use LCNC as much as possible. python should
supply the encoder position and nothing else."* … *"use lcnc code as much as
possible unless unavoidable."*

## What LinuxCNC gives us for free

| Requirement | Native mechanism | Cite |
|---|---|---|
| Home with zero motion | `HOME_ABSOLUTE_ENCODER = 2` — position := `HOME_OFFSET`, jumps to `HOME_FINISHED`, `homed=1`, **no final move exists** | `homing.c:1139-1146`, `ini-homing.adoc:228-246` |
| Boot at last session's coordinates | `[TRAJ] POSITION_FILE` — saves `pos_fb` per joint at shutdown, restores via `emcJointSetMotorOffset` | `taskintf.cc:1673-1730` |
| Home one joint | `cmd.home(jn)` / Axis per-joint Home | stock |
| Home the same joint again | `cmd.unhome(jn)` then `cmd.home(jn)` | stock |
| Gantry pair as one axis, synchronised squaring home | duplicate-letter `COORDINATES` + negative `HOME_SEQUENCE` | `homing.c:265-281`, `ini-homing.adoc` |
| MDI/AUTO while unhomed | `[TRAJ] NO_FORCE_HOMING = 1` (already set) | `emctaskmain.cc:2208` |

## What LinuxCNC does NOT give, and why

1. **No "set homed" command.** NML 112 is
   `EMC_JOINT_SET_HOMING_PARAMS`, params only. The ONLY way to set `homed`
   is to run a home cycle. Hence `=2` rather than any declare of our own.
2. **`HOME_NO_REHOME` is implied.** `taskintf.cc:326-336` — both `=1` and
   `=2` set it, and `homing.c:766-770` sends an already-homed joint
   straight to `HOME_IDLE`, silently. **Rehome = `unhome` then `home`.**
   Native, but the GUI must do it in that order or the click does nothing.
3. **`home_flags` is not runtime-settable.** inihal exposes only
   `home`, `home_offset`, `home_sequence` (`inihal.cc:347-366`). A joint
   cannot switch between "declare" and "switch-seeking" while running.
4. **No STALE vs PHYSICAL distinction.** LinuxCNC knows `homed`, nothing
   more. This is the one boolean we keep. Display only, no motion.

## The joint split

**A and C → `HOME_ABSOLUTE_ENCODER = 2`.** No switches exist, so nothing is
lost. "Go to zero" stops being part of homing and becomes an ordinary
commanded move with normal motion protection. This is the change that makes
a wrong offset a wrong *number* instead of a 100° swing.

**X, Y, Z → unchanged.** Real switch homing, negative `HOME_SEQUENCE` for
the gantry pair. Setting them `=2` would silently kill the squaring cycle
("a request to rehome the joint is silently ignored").

Boot-to-stale-home for XYZ therefore comes from `POSITION_FILE` +
`NO_FORCE_HOMING`, not from `=2`.

## Supplying the position to LinuxCNC

`ini.N.home_offset` is a **HAL IN pin** (`inihal float IN 0
ini.4.home_offset`), so it can be driven by a signal instead of poked with
`halcmd setp`. That single fact removes the write-then-latch race that
caused every incident this week: there is no write, the value is simply
present every servo cycle.

`pso_live.comp` is already realtime and already parses the frame, but today
it publishes only raw counts (`multiturn`, `within`, `valid`, `parsed`).
The conversion to degrees lives in Python.

**Target:** pso_live gains the conversion and the output pins.

```
pin in  s32 ref_mt_a, ref_mt_c        # head_zero reference, setp at load
pin in  u32 ref_w_a,  ref_w_c
pin in  float gear_a, gear_c
pin out float deg_a, deg_c            # net -> ini.4/5.home_offset
pin out bit  deg_valid_a, deg_valid_c
```

HAL then reads, in full:

```
net a-abs-deg  pso.deg_a => ini.4.home_offset
net c-abs-deg  pso.deg_c => ini.5.home_offset
```

Homing A becomes: press Home A. Position := the pin. Done.

### The one part that may stay in Python

The SEN handshake — R4 pack select, SEN low ~1.75 s, rise, one axis at a
time. That is a sequencer with timers; it belongs in the comp, but porting
it is the bulk of the work.

**Interim, and it already removes the hazard:** leave the handshake in
Python, but have Python write *only* `pso.deg_a` / `pso.deg_c` — never
`ini.N.home_offset`, never `cmd.home()`. HAL carries the value onward
continuously. Python then supplies a number and issues no commands, which
is the stated goal even before the port.

## What gets deleted

`set_home_pins`, `head_quiet`, the `halcmd getp` read-back, `wipe_home_pins`,
the confirmed-wipe drain, `do_inplace`, `inplace_pending`, `declare_snap`,
the DECLARE-MOVED detector, `brain.inplace-calls`, `verify_want` /
`verify_eval` / `verify_fail`, `fire_pending_refs`, `pending_ref`,
`read_armed`, `hstate-4/5-in`, `head-busy`.

Every one of those exists to manage a window that stops existing.

## The two gates are UNCHANGED (operator 2026-08-10)

*"nothing works until we get to stale home and tooling database is loaded"* —
these survive the rework untouched. They are not homing code and nothing in
this plan goes near them:

1. **Startup input gate** — `_PreHomeInputGate` stays shut until
   `all(stat.homed[:6])` AND `ned-tab.table-ok-in`. Fail closed: an
   unreadable pin counts as not served. Survivors: E-STOP, POWER, EXIT.
   Under `=2` the homed half arrives sooner and without motion; the
   condition itself does not change.
2. **No table, no motion** — `tool.mm.lock2 = (UNRECORDED or PHANTOM) or
   NOT(brain.tool-table-ok)` driving `motion.jog-inhibit` +
   `feed-inhibit`, in HAL, defaulting locked.
3. **Inconsistency gate** — while `motion-lock-in` is TRUE only E-STOP,
   POWER, EXIT and the ATC/TOOL tabs are live.

`brain.tool-table-ok` is the one brain output that is NOT deleted. Its test
stays a positive fact: at least one real entry in `stat.tool_table`.

One ordering note: `POSITION_FILE` + `=2` make the homed half land earlier,
so the table becomes the slower of the two gates on most boots. That is the
intended shape — the machine waits for whichever is last.

## A AND C CARRY NO STATE. NONE. (operator 2026-08-10)

*"and NO FUCKING STATE for A and C."*

The encoder knows where the head is, every servo cycle. Nothing about A or C
is ever remembered, stored, restored or carried between cycles.

This forbids, explicitly:

- **Persisted A/C state that anything ACTS on.** `POSITION_FILE` restoring
  joints 4/5 is ACCEPTED (operator 2026-08-10: *"that's fine it can restore
  it. we can home properly after that and it should be fine. so long NO
  movement its ok"*). `emcPositionLoad` loops all `EMCMOT_MAX_JOINTS` with
  no per-joint opt-out, so it will. That is harmless HERE and only here,
  because under `=2` the first home overwrites the offset from the live pin
  and **cannot move the head** — the restored number is inert, not a
  destination. It was only ever dangerous under `=1`, where a stored
  number became travel.
  The condition attached: until that first home, the A/C DRO is showing a
  file, not the encoder. The banner must say UNHOMED and nothing may act on
  those coordinates.
- **`stored_home.json` for A/C.** Deleted outright.
- **`hr_deg`, `read_armed`, `verify_want`, `pending_ref`** — any Python
  variable that survives one read cycle.
- **A "was it physical" boolean for A/C.** There is no physical home for
  A/C; there are no switches. The banner distinction applies to XYZ only.
  For A/C the only honest states are "reading" and "read", both live.

The positive form: `ini.4/5.home_offset` is driven continuously by
`pso_live`. Homing A is "adopt the pin". Unhome and it is "adopt the pin"
again. There is nothing to go stale because nothing is stored — which is
also why rehoming A/C any number of times per session is free.

**Open item to resolve before step 2:** whether `POSITION_FILE` can be
restricted to XYZ. If it cannot, A/C need their motor offset overwritten
from the live pin at startup, and the plan must say exactly when.

## What we keep

- The SEN read sequencer (until ported).
- The reference constants in `configs/params/head_zero.inc`.
- One boolean per joint: was this home physical, or stale? Drives the
  banner. Set false at boot, true when a switch-seeking cycle completes.
- The tool-state / table interlocks — unrelated to homing.
- The class-based control gating (separate work, still wanted).

## Order of work

1. Stage and commit what is on disk now.
2. `POSITION_FILE` on, verify a boot comes up at the previous coordinates.
3. A/C to `=2`. Verify Home A is instant and moves nothing.
4. Rehome path: GUI does `unhome` then `home`. Verify twice in one session
   on each of A and C.
5. pso_live publishes `deg_a`/`deg_c`; net them to `ini.4/5.home_offset`.
6. Strip the brain to the SEN sequencer + the banner boolean.
7. Port the sequencer into pso_live. Brain leaves the homing path entirely.

Steps 2-4 are config only. Nothing before step 5 touches realtime code.

## Verification

Each step: apply, then trigger the same path and read the log — the
discipline that worked on 2026-08-08. `tools/brain_harness.py` A/Bs Python
changes against `git show <sha>:...` without a machine.

**Step 3's check is the important one:** with `=2`, `joint.N.motor-pos-fb`
must be identical before and after a Home A. If it moves at all, `=2` is
not doing what the manual says and everything after it stops.
