# B acceleration ceiling, measured 2026-08-14

Chucks only, no cutter, no workpiece. Operator judged stall by eye; nothing on
this machine can detect a B stall in software (open-loop steppers, no encoder,
no drive alarm line -- `stepgen.position-fb` counts steps SENT and advances
identically into a stalled motor).

## The number

| accel deg/s2 | mean rate on 2.000 deg blocks | verdict |
|---|---|---|
| 30 (shipped) | 5.5 (arithmetic) | -- |
| 960 | 30.73 | no stall |
| 1920 | 43.49 | no stall |
| 3840 | 61.54 | no stall |
| 7680 | 87.10 | no stall |
| 15360 | 121.21 | no stall |
| 30720 | 173.79 | no stall |
| 61440 | 235.40 | **STALLED** |

**Unloaded stall threshold is between 30720 and 61440 deg/s2** -- about 1000x
the shipped `[AXIS_B] MAX_ACCELERATION = 30`. It is a TORQUE ceiling, so cutting
load spends it: this figure is an upper bound that a real cut never sees.

## Why acceleration is the only lever on the groove

The kakeya T12 groove is 3620 consecutive B-only blocks of exactly 2.000 deg.
The trajectory planner carries NO speed across those boundaries -- measured
rate matched full-stop-at-every-boundary arithmetic to within 1% at every
accel tested:

    rate = sqrt(2 * a * d) / 2        d = 2.000 deg

    accel   960 -> predicted 31.0, measured 30.73
    accel  1920 -> predicted 43.8, measured 43.49
    accel  3840 -> predicted 62.0, measured 61.54

Raising the F word cannot help; the planner never reaches the commanded speed
on a 2 deg block. Rate scales as sqrt(accel), so 4x the groove speed costs 16x
the acceleration.

## Three ceilings that hid the machine, in the order they bit

1. **The F word.** On a rotary-only block F is deg/min. `F5400` = 90 deg/s
   exactly, which silently capped four trials -- accel 120/maxvel 180 and
   accel 240/maxvel 360 both returned 90.5 deg/s and neither tested its maxvel.
2. **`[TRAJ] MAX_VELOCITY = 333.334`.** Applied to path magnitude whatever the
   units, so it caps a rotary-only move at 333.334 deg/s.
3. **A hard 360 deg/s** that ignores `ini.b.max_velocity` at runtime. Asking
   for 540 and for 720 both produced a planner velocity of exactly 360.0.
   Passing it needs an ini edit and a relaunch.

`[TRAJ] MAX_ANGULAR_VELOCITY = 45` is NOT a planner clamp -- B exceeded it
sevenfold. It feeds GUI jog rates only.

## What IS adjustable on the fly

`ini.b.max_acceleration` and `ini.6.max_acceleration` are live HAL pins and
take effect immediately -- every trial above set them mid-session. Velocity is
live only up to the 360 deg/s ceiling above.

This is what makes a per-operation accel profile possible: low accel where a
cutter can push back (roughing), high accel where the material is already gone
(finishing). Operator 2026-08-14: "when the hard pushback is a risk, we should
do slow accels to have torque, but on finishing passes where we know the
material is gone, we should just fucking spin it."

A program can drive it directly with `M68 E<n> Q<accel>` into a
`motion.analog-out-NN` pin netted to `ini.b.max_acceleration` -- realtime,
synchronized with motion, no shell call. NOT BUILT YET.

## After a stall

B position is meaningless: steps were sent that the shaft never took, and B has
no encoder to notice. Home B to re-zero before anything references it.

## Harness

`tools/b_accel_trial.py <accel> [maxvel] [--short|--reverse] [--secs=N]`
- `--short` runs `b_accel_short.ngc`, 3000 blocks of 2.000 deg (groove pattern)
- refuses unless `brain.b-armed` and both stepgen enables are TRUE
- flashes the standalone DRO white 3x before moving, so the operator knows when
  to look
- aborts if A or Z move; restores `[TRAJ] MAX_VELOCITY` afterwards
- reports COMMANDED path only, never "result" -- see the open-loop note above

Raw results: `logs/b_accel_results.csv`

## What was set, 2026-08-14

Authored in `tools/run5.sh` (the `-xyzab` generator), NOT in
`configs/ned5_pb/ned5_pb_ab_gen.ini` -- that file is rewritten on every launch
and hand-edits there are destroyed.

| | before | after |
|---|---|---|
| `[AXIS_B] MAX_ACCELERATION` | 30 | **11520** |
| `[JOINT_6] MAX_ACCELERATION` | 30 | **11520** |
| `[JOINT_6] STEPGEN_MAXACCEL` | 45 | **17280** (1.5x, the ratio this joint has always carried) |
| `[AXIS_B] / [JOINT_6] MAX_VELOCITY` | 90 | 90, unchanged |
| `[JOINT_6] STEPGEN_MAXVEL` | 108 | 108, unchanged |

11520 = 0.75 x 30720 (the highest confirmed no-stall figure), halved again at
the operator's request. That leaves a 2.7x margin below the highest value that
actually held, unloaded.

Speed deliberately stays at 90 deg/s. At 11520 deg/s2 B reaches 90 deg/s in
**7.8 ms over 0.352 deg**, so a 2.000 deg block spends 87% of itself at full
speed -- the acceleration is no longer what limits the groove, and there is
nothing to gain from spinning faster.

Expected groove rate: about 67 deg/s against 5.5 today, roughly 12x.

**Takes effect on the next launch** -- run5.sh regenerates the ini at startup.

## Accel cannot be changed mid-program

Tested three ways on 2026-08-14; the planner latches acceleration when the
program starts and ignores the pin afterwards:

| test | accel at start | changed mid-run to | rate before | rate 13 s later |
|---|---|---|---|---|
| moderate | 960 | 3840 | 30.8 deg/s | 30.8 deg/s |
| extremes | 30 | 30720 | 5.5 deg/s | 5.5 deg/s |
| pause + resume | 960 | 3840 | 30.8 deg/s | 30.8 deg/s |

So a roughing-versus-finishing acceleration split has to fall on a PROGRAM
boundary. It cannot be done with an M-code inside one file, and pausing does
not re-latch it. Feed is the only thing that stays adjustable while a file
runs.
