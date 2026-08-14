# PID tuning on ned — handoff

Written 2026-08-13 for another operator + assistant starting PID work.
Everything here is what was actually run on this machine, with the file
and log it came from. Nothing is theory.

**Read this first, then `docs/commissioning/pid_calibration_2026-08-01.md`
(the static session in full) and `tools/pid_tune.py` (the GA).**

---

## 0. The machine, only the parts that matter to the loop

| | |
|---|---|
| Controller | LinuxCNC 2.9.8, Pi 5, servo thread 1 ms |
| I/O | Mesa 7I97T (Ethernet) + 7I84U + 7I85S |
| X | **gantry pair**, joints 0 and 3, HAL names `pid.x` and `pid.w` |
| Y, Z | single joints 1, 2 — `pid.y`, `pid.z` |
| A, C | Yaskawa servopacks, **closed inside the drive** — not ours to tune |
| Drives | 40-year-old analog velocity drives, ±10 V command |

Two consequences you cannot design around:

1. **X is two motors on one gantry.** `pid.x` and `pid.w` must always
   carry *identical* gains. Tune them as one entity. The GA does this by
   making `xw` a single lineage that writes both pins.
2. **A/C are not yours.** Their loops live in the Yaskawa packs. Log their
   f-error for reference, never optimise it.

### Encoder counts — the unit everything is judged in

| axis | `INPUT_SCALE` | one count |
|---|---|---|
| X, Y, W | 200 counts/mm | **5.00 µm** |
| Z | 787.402 counts/mm | **1.27 µm** |

Z's encoder is ~4× finer. A "counts" target is therefore 4× harsher on Z
for the same physical motion. When the 2026-08-01 session demanded
"< 2 counts everywhere", Z was being asked for 2.5 µm while X/Y/W were
asked for 10 µm. **Judge in µm, or state the count target per axis.**

---

## 1. Where the numbers live — three layers, one direction

```
configs/params/joint_x1.inc   joint_x2.inc   joint_y.inc   joint_z.inc
        |   P, I, D, FF0, FF1, FF2, BIAS, DEADBAND, MAX_OUTPUT
        v   (#INCLUDEd by the ini generator)
configs/ned5_pb/ned5_pb_ab_gen.ini.expanded      [JOINT_0..6]
        |   read once at launch
        v
HAL pins   pid.x.*  pid.y.*  pid.z.*  pid.w.*     <- what actually runs
```

**The ini is read once, at launch.** `halcmd setp` changes the running
loop instantly and is lost on restart. That asymmetry is the whole
workflow: experiment on the pins, persist to the `.inc` only when a value
has earned it.

> **House rule on this machine:** never write `configs/params/*.inc`
> unless the operator's current message explicitly asks for that edit.
> Compute, present, and stop. (`param-file-edit-explicit-only`.)

### What is in there right now

```
joint_x1.inc / joint_x2.inc (X gantry pair -- MUST match)
   P = 15.878   I = 6.4276   D = 0.0
   FF0 = 0.0    FF1 = 0.995816   FF2 = 0.002414
   BIAS = 0.860 (x1) / 0.722 (x2)   DEADBAND = 0.005   MAX_OUTPUT = 200

joint_y.inc
   P = 19.5382  I = 7.2158   D = 0.00055
   FF1 = 1.001578  FF2 = 0.007378  BIAS = 1.0095

joint_z.inc
   P = 20.5406  I = 7.2877   D = 0.000587
   FF1 = 0.994355  FF2 = 0.006358  BIAS = 0.437
```

`logs/pid_original_gains.json` holds the pre-campaign set — the known-good
fallback the GA restores to after any abort:

```json
x {"Pgain":16.7,  "Igain":4.925, "Dgain":0.0, "FF1":0.993, "FF2":0.0}
y {"Pgain":16.7,  "Igain":4.975, "Dgain":0.0, "FF1":1.005, "FF2":0.0}
z {"Pgain":17.21, "Igain":4.876, "Dgain":0.0, "FF1":0.990, "FF2":0.0}
w {"Pgain":16.7,  "Igain":4.828, "Dgain":0.0, "FF1":0.986, "FF2":0.0}
```

---

## 2. How to read the values

```bash
# one gain
halcmd getp pid.x.Pgain

# the whole set, all four loops
for ax in x y z w; do
  printf '%s ' $ax
  for g in Pgain Igain Dgain FF0 FF1 FF2 bias deadband maxerror maxoutput; do
    printf '%s=%s ' $g "$(halcmd getp pid.$ax.$g)"
  done; echo
done
```

**Always wrap scripted `halcmd` in `timeout`.** An unwrapped scripted
`halcmd` deadlocked this machine's boot once (qtpyvcp PIPE bug,
`ned-boot-lottery`). `timeout 3 halcmd ...` everywhere.

Writing:

```bash
timeout 3 halcmd setp pid.x.Pgain 16.7      # instant, volatile
```

---

## 3. How to read the *error* — the data you optimise

### The pins that matter

```python
PINS = ['pid.x.error', 'pid.y.error', 'pid.z.error', 'pid.w.error',
        'joint.4.f-error', 'joint.5.f-error',      # A/C, reference only
        'joint.4.pos-fb', 'joint.5.pos-fb',        # A/C angle, for kins
        'joint.0.pos-fb', 'joint.1.pos-fb', 'joint.2.pos-fb']
```

`pid.N.error` is **millimetres** of following error. Multiply by 1000 for
µm; divide by the count size above for counts.

### Sampling them without killing the servo thread

Do **not** call `halcmd getp` once per pin per sample. Write the whole
list to a command file and let one `halcmd` invocation return all of them:

```python
CMDF = '/tmp/tune_cmds.txt'
open(CMDF,'w').write(''.join('getp %s\n' % p for p in PINS))
# then, in the sampler loop:
r = subprocess.run(['timeout','2','halcmd','-f',CMDF],
                   capture_output=True, text=True).stdout.split()
v = [float(x) for x in r]           # one coherent row
```

This is a **userspace sampler at ~20 Hz**. Know its limits:

- It cannot see a transient shorter than ~50 ms.
- The machine's own f-error trip will always beat it in a race. A 0.624 mm
  excursion was measured live and the machine dropped *before* the script's
  abort landed. **The sampler is a coarse backstop, not a safety system.**
- Real protection comes from *bounds the GA cannot escape*, not from
  catching the excursion afterwards.

### The three regimes, separated

Error means different things at different moments, and mixing them hides
everything. Split each run by timestamp:

| regime | window | what it exposes |
|---|---|---|
| **rest** | machine idle, no command | bias null, dither floor, stiction limit-cycle |
| **cruise / path** | mid-move, constant feed | FF1 (velocity feedforward) |
| **stop / settle** | last command point −0.1 s … +1.0 s | Igain windup, D damping |

In `pid_tune.py` this is exactly:

```python
endw = [e for t,e in es if any(st-0.1 <= t <= st+1.0 for st in stops)]
path = [e for t,e in es if not any(st-0.1 <= t <= st+1.0 for st in stops)]
```

---

## 4. What the static session already settled — do not re-derive

From `docs/commissioning/pid_calibration_2026-08-01.md`. Repeating this
work is a wasted day.

**a. Static null (BIAS) — the drives lie by 25–30 mV.** Every axis needs a
standing output at rest, carried by the integrator if you do not supply it.
Measure it by **disabling Igain per axis**: P alone holds the axis, the
null shows up as a static f-error, and `bias = P × ferror`.

> Dead end already walked: `pid.errorI` **does not exist** unless the pid
> component is loaded with `debug=1`. The first bias attempt read it,
> got nothing, and produced a whole useless log.

**b. FF1 was never wrong.** Single-stroke estimates walk randomly: ±1 count
of cruise error reads as ΔFF1 ≈ 0.025, which is ten times the 0.002
convergence bar. **Average at least 3 stroke pairs and make the threshold
count-aware**, and it converges immediately. Y keeps a direction-asymmetric
cruise error (~2 counts more lag one way) — that is asymmetric drive gain,
and FF1 is symmetric, so FF1 cannot remove it. Don't chase it.

**c. Integrator windup was the big win.** Baseline stop-settle p95 was
X 3.0 / W 2.8 / Y 4.8 / Z 11.9 counts. A 0.5 %-per-step Igain descent took
X to 2.0, W to 1.8, Y to 1.6, Z to 4.9.

**d. Deadband: 0.005 is optimal.** Wider bought nothing on any axis.

**e. There is a hardware floor, and you will hit it.** At rest every axis
shows the *same physical* dither, ~±15–20 µm p99 — one band expressed in
four different count scales. With the drives off the encoders are **dead
flat**, so the motion is real and loop+drive generated. It survives perfect
bias, perfect FF1 and optimal deadband. P descent doesn't touch it either
(best rest p99 on every axis was at the entry P).

**Tell the operator this early.** Below ~15 µm the remaining work is
hardware: drive null pots, drive service, damping. Software tuning past
that point produces graphs, not accuracy.

---

## 5. The GA — what was used and why

`tools/pid_tune.py`. Not a textbook GA: a **(1+2) elitist evolution
strategy per axis**, four lineages in parallel, sharing one physical trial.

### Why this shape

- **Trials are expensive and few.** Each is a real move on real iron —
  seconds, not microseconds. Budget was 48 trials per run. A population-50
  generational GA never gets past generation one. With a (1+2)-ES every
  trial is either the incumbent or one of two children of it.
- **The axes are nearly independent but share a trial.** One move exercises
  X, Y and Z at once, so one trial scores three lineages. Free parallelism.
- **The search is local.** You are polishing a working machine, not
  discovering gains from scratch. Mutation around an incumbent is right;
  broad crossover is not.

### Genome

```python
AXES  = ('xw', 'y', 'z')        # xw = the gantry pair, ONE lineage, both pins
GENES = ('Pgain', 'Igain', 'Dgain', 'FF1', 'FF2')
```

`BIAS` and `DEADBAND` are **not** genes — the static session settled them
and they are not move-dependent. `FF0` stays 0.

### Bounds — the real safety system

```python
BOUNDS[ax] = {'Pgain': (0.7*P0, 1.5*P0),     # P0 = the banked original
              'Igain': (0.0,  2.0*I0),
              'Dgain': (0.0,  0.02),
              'FF1':   (0.97, 1.02),
              'FF2':   (0.0,  0.008)}
```

Chosen by measurement, not taste: within 0.5×–2× P the worst tip error seen
was ~0.13 mm, so nothing inside these bounds can approach even a 1 mm
excursion. **This is what keeps the machine safe — not the abort path.**

### Mutation, and the two knobs that stop it thrashing

```python
SIG0 = {'Pgain': 0.03, 'Igain': 0.06*max(I0,1), 'Dgain': 0.0008,
        'FF1': 0.0012, 'FF2': 0.00025}          # per-gene sigma
STEP_CAP = {'Pgain': 0.08*P, 'Igain': 0.12*max(I,1), ...}   # per-step ceiling
```

Each gene mutates with probability 0.4. Sigma adapts: **×1.3 on an
improvement, ×0.6 after 4 barren generations** (floored at SIG0/10). The
step cap is separate from sigma and prevents a fat tail from producing one
absurd jump.

### The cost function

Per axis, in µm², summing the two regimes that matter:

```python
cost = mean_square(path_error_um) + mean_square(stop_error_um)
```

Plus a whole-machine figure — the **exact tip error**, XYZ only, computed
through forward kinematics from the joint feedback and the live pivot
length:

```python
tip2 = [((v_x + v_w)/2)**2 + v_y**2 + v_z**2 for each sample]
tip3d_um2 = mean(tip2) * 1e6
```

Two details worth stealing:

- The gantry term is `(x + w)/2` for the *tip*, but the gantry lineage's own
  cost uses `max(|x|, |w|, |x − w|)` — the differential `|x − w|` is racking,
  and racking must be punished even when the average looks fine.
- Forward kins uses the **true** pivot length, not the live HAL pin, so a
  wrong-pivot or count-drift failure shows up as a geometry error instead of
  hiding inside the cost.

### Rejecting noise — the part most tuning scripts get wrong

A trial is only an *estimate*. Accepting any improvement makes the GA chase
measurement noise forever. This one requires the child to beat the
incumbent by a **margin**:

```python
margin = max(0.5 * noise[ax] * mean_cost(ax, inc[ax]),
             0.02 * mean_cost(ax, inc[ax]))       # floor: 2 %
if cbest < mean_cost(ax, inc[ax]) - margin: accept
```

and it **re-evaluates the incumbent every 4 generations**, folding the new
measurement into a running mean. Without re-evaluation the incumbent's
score is a lucky sample and nothing can ever beat it honestly.

### Lethality and the abort path

- **Kill switch:** peak > 3 × baseline peak, or oscillation > 10 Hz of
  sign flips → candidate is lethal, cost = ∞.
- **Tip cube:** ±5 mm about the tip's measured starting point. Breach →
  `command.abort()` *immediately*, restore the champion gains, then a plain
  `G53 G1 X0 Y0 Z0 A0 C0 F800` park. No rehoming, no restart.
- **Blacklisted but kept.** A box violation scores `BOX_COST = 1e6` — high
  enough that it never reproduces, but the record stays in the data.
  Deleting failures makes the next run repeat them.

### Golden rule of the harness

> **Never delete data.** Every writer is append-only; the originals file is
> write-once; the run resumes from the ndjson if it dies. `ga_keeper.sh`
> restarts the GA whenever it exits, and only when `task_state == ON`.

---

## 6. What the campaign produced

```
18 ndjson files, 479 trials recorded, 0 box violations
best tip3d = 248.5 um^2   (trial 28, pid_tune_20260806-200756.ndjson)
             loopsum      1012.2 um^2

x  P 33.4     I 12.789  D 0.0      FF1 0.98873  FF2 0.00459
y  P 33.4     I 13.162  D 0.02132  FF1 0.98374  FF2 0.00384
z  P 21.125   I 8.172   D 0.01941  FF1 0.99820  FF2 0.00249
w  P 24.995   I 11.127  D 0.00244  FF1 0.99289  FF2 0.0
```

Note what the GA found that the hand session did not: **it doubled P, tripled
I, and introduced D and FF2 from zero.** The static session could not get
there — its own safety rule was "steps ≤ 0.5 % of value", and 0.5 % of zero
is zero, so D and FF2 were unreachable by construction.

**That result is not in the ini.** The shipped `.inc` values sit between the
originals and the GA's best. Treat the campaign numbers as a candidate to
verify, not a set to paste.

---

## 7. Order of work, if starting again

1. **Bias first, with I disabled.** Everything downstream is polluted by an
   un-nulled drive.
2. **FF1 next**, 3-pair averaged, count-aware threshold.
3. **Igain descent** for stop settle — this is where the visible win is.
4. **Deadband** — check it, expect 0.005 to win, move on.
5. **Only then the GA**, warm-started from step 4, to reach D and FF2 —
   the two terms hand tuning cannot enter from zero.
6. **Re-verify at the end** in the same three regimes, and quote p99 and
   max in each axis's own counts *and* in µm.

## 8. Gotchas that cost real time here

- `pid.errorI` needs `debug=1` on the pid component. Without it you read
  nothing and don't find out for an hour.
- X and W must move together. A gains difference between them is racking,
  and racking shows as a *good* average error.
- The 20 Hz userspace sampler cannot police safety. Bound the genes.
- `INPUT_SCALE` differs 4× between Z and the rest. A single count target
  across axes silently demands 4× more of Z.
- Wrap every scripted `halcmd` in `timeout`.
- Anything that ends a run must leave the machine on the **known-good**
  gains, not the candidate that just failed.
