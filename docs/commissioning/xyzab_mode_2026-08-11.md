# `-xyzab -notcp` — workpiece rotary B replaces the head spin C (2026-08-11)

Operator: *"i want to set up -xyzab -notcp. when launched in this mode. if C
is not already at zero, it automatically does the physical homing for XYZ and
C. XYZ so that we get to a safe place to home C automatically. A is left where
it is. And instead of controlling C, everything that used to control C now
controls the rotaries."*

## Shape

**B is joint 6. C is NOT removed.** C still has to be homed to zero and held
there, and a joint with no axis letter cannot exist under trivkins. So joints
0-5 are byte-identical to every other mode and B is appended:

```
JOINTS = 7
KINEMATICS = trivkins coordinates=XYZXACB kinstype=B
COORDINATES = X Y Z X A C B
```

The ini is **generated** by `run5.sh` (same pattern as the tool-tip ini), not
forked, so every numeric parameter stays single-sourced in
`configs/params/*.inc` (CLAUDE.md rule 11).

`-tcp` is REFUSED in this mode: `ned_ac_kins` models the swivel head and would
compensate XYZ for rotations of a C that is parked. There is no A-head +
B-table kinematics module on this machine (task #24).

## The iron

Two mirrored steppers, one joint. They sit on the same worm, so they are not a
gantry pair — there is no second feedback to square against. `joint.6`'s single
`position-cmd` feeds both stepgens and the scales carry opposite signs.

| | |
|---|---|
| stepgen.00 | 7I85S TB2-11/12 STEP±, TB2-13/14 DIR±, scale **+22.222** |
| stepgen.01 | 7I85S TB2-19/20 STEP±, TB2-21/22 DIR±, scale **−22.222** |
| SCALE | 22.222 steps/deg = 400 p/rev × 20 (worm) ÷ 360 (`docs/components.md:50`) |
| feedback | none — open loop, `motor-pos-fb` ← the stepgen's own `position-fb` |
| holding | the worm is **self-locking**: B holds position with the brick dead |

Sources: `docs/mesa_7i85s_wiring.md:15-16`, `docs/components.md:50`.

## R4 is one relay doing two jobs

`7I84 output-05` (`brain.r4-select`, `postgui_pb.hal:96`) is **both** the PSO
pack-select for the A/C absolute read **and** the second gate of the 70 V
rotary brick. The first gate is R11, whose coil sits on the drive-enable node
`*7` (`docs/components.md:89`), so R11 closes whenever the machine is enabled
and is not separately software-controlled.

Operator ruling: *"its fine because we can always turn the rotaries off to home
A, since when homing, everything else isn't moving anyway."*

So the arbitration is a strict priority, in `ned_brain.b_power()`:

- a head read **always** wins; B goes dark for its duration
- otherwise R4 is held on, and `brain.b-armed` rises `B_SETTLE = 0.25 s` later
- `ned5_b.hal` ANDs `b-armed` into both stepgen enables, so **no step can
  leave the FPGA before the drives are live**

That last point is not cosmetic: B is open loop with no encoder, so a step into
an unpowered drive is lost silently and every later B coordinate is wrong.
Losing power costs B nothing (self-locking worm); losing the pack-select costs
the head read its correctness, which is how a 66° head got declared as home on
2026-08-01. The priority runs in the safe direction.

## Launch sequence

Lives in `ned_controls.xyzab_launch_start` / `_ab_tick`, **not** in the brain —
`ned_controls` already owns every motion command on this machine, and the
brain's standing rule is that stale home is a declaration and the brain issues
no motion at all. It goes out through the same `request_homeall` /
`ac_to_zero` paths the buttons use, so there is no second, less-tested route to
the same iron. Polled at 2 Hz, never blocking.

1. wait for machine ON + all six of XYZAC homed (the stale-home declare)
2. read C. Inside ±0.05° → skip to step 5
3. `request_homeall()` — the real switch-seeking XYZ cycle, so the head has
   room. A and C are unhomed and re-adopted from the absolute encoder; **A is
   not moved**
4. `ac_to_zero('c')` — adopt, then joint-jog C to zero
5. `home_b_inplace()` — B has no switch and no encoder, so `HOME_SEARCH_VEL`
   and `HOME_LATCH_VEL` are 0 and `HOME == HOME_OFFSET == 0`: the cycle sets
   the coordinate and the final move is zero length. **Wherever the chuck is
   sitting becomes B0.**

Both waits carry deadlines (180 s / 120 s). A breach stops the sequence and
says so; nothing is assumed and C is not moved on a timeout.

## C's controls become B's

Taken literally, and it is also the cheapest correct implementation: the
pendant, the DRO lock buttons and the angular increment ladder all keep their
existing `c` pins and behaviour, and the **last** HAL file re-points those
signals at `axis.b` / `joint.6`. No new pendant pin, no new GUI button, no
second code path to keep in step.

| where | what changed |
|---|---|
| `postgui_b.hal` | `unlinkp` C's jog enable/counts/scale (axis **and** joint), re-net to B |
| `dros_xyzac.py` | `DRO_JOINT['c'] = 6`, `AXIS_IDX['c'] = 4`, `axis_label_c` relabelled to **B** |
| `ned_controls.py` | `_INC_AXES` slot 4 → `'b'`, so a wheel-zero emits `G10 L20 P0 B0` |
| `ned_pendant.py` | the rotary slot's auto-lock gates on joint **6**, not joint 5 |
| `dro2.py` | `sig-mpg-lock-c` / `sig-lock-c` colour the **B** row |
| `ned_homing_menu.py` | `Home C` → `Home B`; `Home A&C` dropped |

C itself is left with no jog pins at all, and `apply_mode` clamps it once it
reaches zero.

## Two bugs this work exposed in existing code

**1. The un-spelled-rotary clamp was centred on zero.** `apply_mode` wrote
`ini.N.min_limit = -0.001`, `max_limit = +0.001`. But A and C home by
*adopting the absolute encoder*, so a head parked at +102.6° homes to +102.6 —
and a window centred on zero puts the joint 102° outside its own soft limits
the instant it is applied. `get_pos_cmds()` tests those limits every servo
cycle (`control.c:1489-1510`), so that is an immediate limit fault on a machine
that has not moved. The window is now centred on the live position
(`here ± 0.001`), same total width, which is what "frozen where it stands"
actually means. This was latent in `-xyz` and `-xyza` too.

**2. The hardcoded joint count.** `homed[:6]` (20 sites) and
`range(6)` (17 sites) across `ned_controls.py`, `dros_xyzac.py` and
`ned_homing_menu.py` all mean "all joints", and in this mode that is seven.
They now read `NJ`, set once per module from `NED_MODE`. A half-swept file is
the dangerous state: some gates would release while B was still unhomed, and
LinuxCNC cannot enter teleop without every joint homed, so world jogging would
fail with the GUI showing ready.

The one exception is `_ab_tick`'s own readiness test, pinned back to six with a
comment — B is homed by the sequence's last step, so waiting for seven there
would deadlock the thing that homes B.

## Placeholder numbers — NOT measured

`[JOINT_6]` / `[AXIS_B]` carry bench placeholders and are marked as such in the
generated ini: `MAX_VELOCITY = 30`, `MAX_ACCELERATION = 300`,
`STEPGEN_MAXVEL = 36`, `STEPGEN_MAXACCEL = 450`, step timings 2500/2500/20000/
20000 ns copied from the head stepgens. No soft limits (`±3600000`) — a
continuous workpiece rotary. **A 360° commanded move must be checked against a
mark on the chuck before any of this is trusted.**

## Verified offline

- generated ini parses; `[KINS]`, `[TRAJ]`, `[AXIS_B]`, `[JOINT_6]` all present
  with the right values
- every `[SECTION]KEY` referenced by `ned5_b.hal`, `ned5_iron.hal`,
  `postgui_b.hal` and `postgui_pb.hal` resolves against it, includes expanded
- `logic` personality `0x102` = 2 inputs + `and` output, pins `in-00`/`in-01`/
  `and` (`logic(9)`); HAL backslash continuation confirmed in `halcmd(1)`
- `tools/cfg_edit.sh` green: userspace pin order, class-attr/method,
  HAL syntax, `ned-tab` pin cross-check, `gcode_check --all`
- undefined-name sweep on all three GUI modules
- `py_compile` on every touched module

## NOT verified — nothing has been launched

`tools/halcheck.sh` needs LinuxCNC **down** and has not been run. Nothing in
this mode has ever loaded. First launch is `tools/run5.sh -xyzab -notcp` and
must be watched for, in order:

1. `run5: -xyzab -- B (workpiece rotary) is joint 6; C is homed to 0 and held.`
2. HAL loads at all — `b.pwr` is a component this machine has never loaded
3. `B POWER: R4 on, 0.25 s settle before steps are allowed`
4. `XYZAB: C reads ... -- physical XYZ homing first`
5. `XYZAB: XYZ homed; driving C to zero`
6. `XYZAB: B (joint 6) homed in place`
7. `MODE xyzab: C reached zero` then `C CLAMPED at ...`

If `b-armed` never rises, B will sit dead with no error — the enable is an AND
and nothing reports a gate that simply stays shut.
