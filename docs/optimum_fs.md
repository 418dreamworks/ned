# Optimum F and S

**Three categories. Two belong to the material, one to the machine.**

```
REGULAR   the cutter is moving across the work          material
PLUNGE    the cutter is going into the work tip-first   material
AIR       nothing is being cut                          MACHINE
```

A material carries a surface speed and a chipload for REGULAR and for PLUNGE,
**per size class**. AIR carries none of them.

```
SMALL     D <  6.00 mm                 the 1/8 in class
MEDIUM    6.00 <= D <= 12.70 mm        1/4, 3/8, 1/2, and the 6 mm
LARGE     D >  12.70 mm                bigger than 1/2 in
SAWBLADE  its own category             NOT a diameter class
```

**A sawblade is not a large end mill.** It cuts on the rim with many teeth,
its kerf is its thickness and not its diameter, and nothing about an end
mill's chipload or Vc carries to it, however big it is.

```
S = Vc x 1000 / (pi x D)
F = S x flutes x chipload
```

The chipload is read off the table in mm/tooth and does NOT scale with
diameter inside a class.

Nothing in this file says where the cutter goes.

---

## THE MATERIAL TABLE

### WHITE OAK

| size class | REGULAR Vc | REGULAR chipload | PLUNGE Vc | PLUNGE chipload |
|---|---|---|---|---|
| **SMALL** | **ASK** | **ASK** | 120 marking, 160 pilot | **0.0225** |
| **MEDIUM** | **226** | **0.1620** | **226** | **0.0405** |
| **LARGE** | **ASK** | **ASK** | **ASK** | **ASK** |
| **SAWBLADE** | **ASK** | **ASK** | — | — |

A sawblade has no PLUNGE row. It does not go in tip-first.

### ANY OTHER MATERIAL

Every cell. **ASK.**

---

## AIR — the machine's numbers

An air move cuts nothing. **It should be a `G0`, and then it needs no feed.**
Where a post emits a feed move in air:

| the move | ceiling | **F** | from |
|---|---|---|---|
| X / Y / W only | 200 mm/s | **12000** | `[JOINT_0,1,3] MAX_VELOCITY = 200` |
| anything with Z | 169.3 mm/s | **10000** | `[JOINT_2] MAX_VELOCITY = 169.3` |
| A or C | 30 deg/s | **1800** | `[JOINT_4,5] MAX_VELOCITY = 30` |

**A `G1` in air is a defect, not a feed to tune.** The fix is a `G0` and it is
the post's. These are what I write while the post is wrong.

---

## THE RULE FOR A CELL WITH NO NUMBER

**There is no per-tool table and there never will be.** *"no tool. for any
given tool, we can read off what to do from our table"*. A tool brings three
facts — diameter, flute count, and whether it is a sawblade. The diameter
picks the size class, the table gives Vc and the chipload, and S and F fall
out. A tool that has never been run needs no new entry.

**What I ask about is an EMPTY CELL, not an unfamiliar tool.** *"if we are
using a tool where no info about it is presenting, you need to ask me"*. T6,
T9, T11 and T13 have never been run and need no question — they are MEDIUM in
oak and the row is filled. T1 and T15 need a question, because LARGE and
SAWBLADE are empty in oak and nothing fills them.

**I ask while the thing is moving.** *"you update if the number exists, if
not, you ask me how i like it when stuff is moving"*.

```
the number exists   ->  write it, no question
the number does not ->  ASK HIM, AT THE MACHINE, WHILE IT CUTS
                        his answer fills the cell for that material,
                        class and category -- for good
```

**And before a file runs I say where I will need him.** His instruction:
*"before a file is run you point out where you need my feedback"*. Not after
it has gone wrong. The pre-run note lists every tool the file uses, the class
and category of each operation, and which of those cells is empty — so he
knows in advance which passes he is being asked to judge.

**The table only ever gets fuller.** *"so as we run more and more files, you
know what to do more and more"*. Every answer he gives is permanent.

---

## WHAT HE HAS ALREADY RULED

```
PLUNGE CHIPLOAD IS 0.25 x REGULAR, FOR NOW
    "make the drill and plunge chiploads .25 of the regular one". A measured
    ratio per material, not a law -- a material's own plunge number wins.

S IS CONSTANT WITHIN A FILE -- UNLESS THE EFFECTIVE FEED SAYS OTHERWISE
    "fucking make the spindle speed 12000 everywhere" ... "but constant
    12000 spindle". That still holds for every operation that reaches its
    feed. An operation that CANNOT reach it gets its own lower S, from the
    effective-feed calculation above. He ruled that later and it wins.

NO EXTRAPOLATION ACROSS A KEY
    A number does not carry from oak to another material, from one size
    class to another, or from REGULAR to PLUNGE.
```

## OAK HAS A CEILING NOW

2026-09-30: *"i would say right now, its going a hair fast for my taste. lower
chipload by 10pct for white oak"*. **The first time he has ever called an oak
feed too fast.** Everything written above it that read "oak only moves one
way" is retired.

```
0.1800   he called it a hair fast        the ceiling
0.1620   -10%, where it sits now
0.1500   he called it too slow earlier   the floor
```

The band is narrow and both ends are now his, measured, not inferred. **Do not
drift out of it in either direction without him saying so.**

---

## EFFECTIVE FEED — WHEN THE SEGMENTS ARE TOO SHORT TO REACH THE FEED

2026-09-30, relayed through Controls: *"for the swarfs, we know what the
effective speed is due to accel. its screaming because its rubbing. adjust the
spindle down accordingly based on calculated feed"* ... *"whenever you see
segment lengths that don't actually get up to speed, work out the correct
speed for the effective feed and use that"*. And directly: *"make sure to
calculate the effective feed whenever max accel isn't reached, and apply an
averaged lower feed to obtain the correct chip load"*.

**A commanded feed the machine never reaches does not lower the chipload --
it destroys it.** The cutter still spins at S while the work moves at the
effective feed, so the chip gets thin and the tool rubs and the wood screams.
The fix is not a faster feed, which is unreachable. It is a SLOWER SPINDLE.

```
PER BLOCK, with the arc blender off (any rotary motion turns it off):
    t_axis(d, a, v) = 2*sqrt(d/a)        if sqrt(d*a) <= v
                      d/v + v/a          otherwise
    t_block = max(t_linear, t_A, t_C, t_commanded)

PER OPERATION -- THE WEIGHTING IS NOT OPTIONAL:
    F_eff = sum(linear distance) / sum(t_block) * 60

    This is TIME-WEIGHTED: total distance over total time. A block that
    takes ten times as long must count ten times. The plain mean of the
    per-block feeds counts it once and is WRONG -- on side_r it was out by
    -45.7% on `D1 FINISH END A 4` and +17.7% on `SWARF8`, in opposite
    directions, so it is not even a consistent bias. Confirmed correct
    2026-09-30: "make sure you do the average weighted correctly" ...
    "thats correct".
    if F_eff >= the chipload-correct F:   nothing is wrong, use the normal F and S
    else:                                 command F_eff, and
                                          S = F_eff / (flutes x chipload)
                                          clamped to S 4000 .. 18000
```

**THE SPINDLE FLOOR IS 4000, NOT THE CONFIG'S 1000.** Operator 2026-09-30:
*"minimum spindle is 4000. nothing lower. thats what im comfortable with"*.
`MIN_SPINDLE_0_SPEED = 1000` is what the control permits; 4000 is what he
permits, and his number is the one I write.

**When the floor binds, the chipload cannot be reached and I say so.** S can
go no lower, the feed is already at the geometry's limit, so the only lever
left is LONGER SEGMENTS, and that is Production's. A file where the floor
binds gets reported, not quietly accepted.

```
A  30 deg/s   8 deg/s^2
C  30 deg/s   4 deg/s^2       configs/params/MASTER.params, via Controls
linear  200 mm/s   200 mm/s^2
```

**NEVER ASSUME A CLASS OF OPERATION IS SLOW. COMPUTE EACH ONE.** Operator
2026-09-30: *"are you calculating based on segment lengths, don't assume all
swarfs are slow"*. Measured the same evening, the swarfs are not alike:

```
side_r  SWARF7       median seg 4.722 mm   F_eff  412    ROTARY-bound, 260/284
top     F1 SWARF      median seg 7.9 mm    F_eff  933    segment-bound, 0/131
```

Same word in the operation name, more than twice the effective feed, and a
different axis binding. The name is for picking REGULAR vs PLUNGE and nothing
else; the number comes from that operation's own blocks, every time.

**The rotary almost always binds, not the linear axes.** On `side_r/02_cut`,
525 of SWARF8's 536 blocks were rotary-bound. Linter check `P2` computes
reachability from the LINEAR acceleration only and is wrong on every rotary
path — that is my defect and this calculation replaces it.

**This retires "one S per file" wherever it applies.** S now varies per
operation, because the effective feed does.


---
---

# HOW A NUMBER IN THIS FILE GETS SET

Everything above is the answer. This is the method that produces it, moved
here from `docs/plans/grumble_index.md` on 2026-10-01 when the PB
implementation of the grumble buttons went to Controls. The buttons are
theirs to build; what a click MEANS is mine.

## A. NOT points. The unit of analysis is the cluster, and the answer is a CAM parameter.

*"you should not take points. the idea is i will give multipple feebacks and
it should be reverse engineered so that I can look at a toolpath, and comment
on the CAM side."* ... *"this is a collection of what i see on gcode side."*

**A single click is evidence, never a finding.** Nothing is fixed at the line
he clicked. The clicks accumulate, and the job is to work backwards from a
cloud of g-code observations to **the one CAM parameter that produced all of
them**.

This is not theoretical — it is exactly what 2026-09-29 was. Five separate
complaints, hours apart, at four different places in the program:

```
"marking is way too slow"                  a traverse in 00_mark
"finish path end back to start too slow"   a return in D1
"swarf sweep returns way too slow"         a return in F1
"linking speeds increase 50pct"            everywhere
```

Four grumbles, four operations, and one cause: `highFeedrateMode 'always'`
with `highFeedrate 3600.0`. Every one of them was chased and answered
separately, and every answer was a line-level fix that would have had to be
repeated on side_r. **Had the clicks been clustered instead of answered, the
parameter would have fallen out of the second one.**

### Why it works: a CAM parameter has a g-code signature

A parameter does not affect one block. It affects a **class** of blocks, the
same way, everywhere. That signature is what makes it recoverable.

| g-code signature | the CAM parameter behind it |
|---|---|
| every air move is `G1` at one exact feed | `highFeedrateMode 'always'` + `highFeedrate` |
| no `G0` anywhere above the stock top | `allowRapidRetract false` |
| cutting segments all ≤ one value | `maximumSegmentLength` |
| every retract goes to the same Z | clearance / retract height |
| one feed on all entries through the stock top | lead-in / plunge feedrate |
| consecutive ops repeat a full retract and re-index | operations not merged |
| chord deviation scales with local radius | `tolerance` |

**Reverse engineering is signature matching.** Take the clicked blocks, find
what they have in common that the un-clicked blocks do not, and look the
common property up. The output is a CAM parameter and a value — something he
can say on the CAM side, which is the whole point.

### What it emits

Not "line 1340 is too slow". This:

```
GRUMBLES     4 clicks, 3 operations, 2 programs, over 71 minutes
COMMON       every clicked block is G1, in air above the declared stock top,
             at exactly F3600; no clicked block is a cutting move
ABSENT       no G0 occurs above the stock top anywhere in either program
INFER        highFeedrateMode 'always', highFeedrate 3600.0
SAY          "set highFeedrateMode to disabled and allow rapid retract"
CONFIDENCE   4 of 4 clicks explained, 0 counter-examples
```

That last line matters. An inference that explains three of four clicks has a
fourth cause still in it, and saying so is the difference between a finding
and a guess — which is the failure mode of three of my own conclusions today.

### Four rungs, and nothing skips one

```
OBSERVATION   one click. Logged. NOTHING is changed on its account.
CLUSTER       two or more clicks sharing a signature. Now it is worth looking at.
PARAMETER     a signature match he confirms -- stated in CAM terms, sent to Production
CHECK         a parameter whose effect can be measured -- goes into lint_ngc.py
```

A rule is only ever written as **(context, quantity, value)**:

| context | quantity | value | from |
|---|---|---|---|
| air move | mode | `G0` | 2026-09-29, four separate grumbles |
| entry through the stock top | feed | half the cutting feed | "halve it" |
| link clearance | height | stock top + 11.35 mm | "aother 5mm" |
| rotary cutting path | feed | `0.5*sqrt(2*a*d)*60` rounded down to 50 | reachable-feed rule |
| bore plunge | chipload | 0.25 × the cutting chipload | "a quarter" |
| any operation | spindle | S12000 on T12 | "keep it all at 12000" |

**Context is what makes it reusable.** "Too slow" is not a preference. "Air
moves are rapids" is, and it applies to side_r, to the next part and to a
different machine.

---

## B. Where the rules go

Two consumers, and they must not disagree.

**Production, before the post.** One generated spec per job — the current rule
set, resolved to numbers against this job's tool and material. Not prose, not
a thread. They post to it; we check the output. This is the thing that stops
the same grumble recurring on side_r, and it is the half that was missing all
of 2026-09-29: every rule reached them as a message, one at a time, after he
had already seen the defect.

**The linter, after the post.** Every rule that can be measured becomes a
check. `P2` already is one — it came from "the swarf is too slow" and now
refuses any program that repeats it. A rule that cannot be expressed as a
check is not yet understood well enough to be a rule.

```
rule                                    check         state
air moves are G0                        proposed      D3 already proves it is safe
entry feed <= half the cutting feed     proposed      needs the stock-top crossing
chipload within 0.5x..1.5x of spec      proposed      needs flutes published reliably
commanded F must be reachable           P2            LANDED
rapid must not end below stock top      D3            LANDED
machine Z0 before the first XY          E3            LANDED
```

---

## C. What it would have caught

Five defects, one class: **a number describing something other than what it is
attached to.**

```
F10000 links on a path that can only fly F1336
F600 marking feed leaking onto 215.900 mm of air
F5400 surviving a spindle drop to S8000, becoming 0.2250 mm/tooth
highFeedrate 3600 set for the swarf, slowing a contour that has nothing to do with it
F3600 on the sweep-to-sweep return, 60 mm/s in air
```

He found all five, at the machine, one at a time, hours apart. The index does
not make them not happen — it makes the second one a check instead of a
conversation.

---

## D. What this is not

- **Not a ticket system.** No status, no assignee, no closing. A grumble is a
  measurement, and it stays in the log after it is fixed because the next
  pattern is built from it.
- **Not a substitute for telling Production now.** The live message still
  goes. The index is what stops it being needed a second time.
- **Not automatic.** Nothing is promoted from pattern to rule without him
  saying so. A misread grumble that becomes a linter check is worse than no
  index at all — it would refuse correct programs and he would stop trusting
  the gate.

---

## E. Open questions, his to answer, not mine to assume

1. **Where does material come from?** Stated once per job, or per program
   header? A `(MATERIAL WHITE OAK)` line would make it derivable like the
   stock top, but that is a post change.
2. **Does a grumble on a file that gets re-posted follow the geometry or the
   line number?** Line 1340 means nothing after a regeneration. Anchoring on
   the operation section plus the move's coordinates would survive; anchoring
   on the line number would not.
3. **Who owns promotion to a linter check** — me, or does he sign each one?
4. **Does the index cross parts?** A preference learned on side_l should apply
   to the whole arch assembly, and probably to every job after it. Saying so
   explicitly decides whether the store is per-run or global.

