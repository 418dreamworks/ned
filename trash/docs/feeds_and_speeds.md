# Feeds and speeds — his preferences, and the rules I set them by

**This is the single source for every F and S I write.** It is the whole of my
job: how fast things move and how fast they spin. Nothing in here decides
where the cutter goes.

Operator 2026-09-30: *"your only job is how fast stuff goes and how fast it
spins"* ... *"nothing else"* ... *"that's literally your job to read segments
and put appropriate rules"*.

---

## 1. The arithmetic

```
F = S x flutes x chipload
```

**Recompute EVERY feed in an operation whenever S, the flute count or the tool
changes.** A feed carried across any of those is wrong by construction. This
is the mistake that keeps recurring.

---

## 2. MATERIAL FIRST. Chipload and surface speed are per material.

Operator 2026-09-30: *"for chipload and surface speed, make that material
specific"* ... *"i like what we are doing for white oak"* ... *"your final
checks includes FS and adapting the file to the material on hand"*.

**Adapting the file to the material on hand is part of the final check, not a
separate job.** A program arrives with geometry; the material decides the
numbers, and the material is what is in the vice, not what the post assumed.

| material | chipload, per mm of cutter diameter | surface speed Vc | status |
|---|---|---|---|
| **white oak** | **0.0250 mm/tooth per mm of dia** | **226 m/min** | SETTLED — he likes it |
| anything else | — | — | **ASK HIM. Do not extrapolate.** |

**White oak, derived from what he approved:**

```
T12  6.00 mm   0.1500 / 6.00 = 0.0250 per mm      Vc = pi x 6.000 x 12000 / 1000 = 226.2 m/min
T14  3.175 mm  0.0250 / 3.175 = 0.0079 per mm     Vc = pi x 3.175 x 12000 / 1000 = 119.7 m/min
     pilot                                        Vc = pi x 3.175 x 16000 / 1000 = 159.6 m/min
```

The two tools do NOT share a chipload-per-diameter — the 1/8 runs far lighter
than the scaling would give, because it is a small cutter in a deep hole. So
the table above is the rule for a 1/4-class cutter; a smaller one comes down.

**When the material changes, both numbers move.** Vc sets S for the diameter
in the spindle; the chipload then sets F. Neither carries over from oak.

**Only white oak is settled.** For anything else the honest answer is to ask
him, and to say that I am asking rather than guess from a table. He has never
given me a second material and I will not invent one.

---

## 3. His settled numbers

| | S | chipload | F | source |
|---|---|---|---|---|
| **T12** 6.00 mm, 3 flutes, white oak | | | | |
| cutting / contour | 12000 | 0.1500 | **5400** | *"the general FS was fine"*, 2026-09-30 |
| drill, plunge, entry | 12000 | 0.0375 | **1350** | *"make the drill and plunge chiploads .25 of the regular one"* |
| **T14** 3.175 mm, 2 flutes | | | | |
| marking dots, 0.5 mm into the spoil | 12000 | 0.0250 | **600** | set here, accepted in use |
| pilot drilling, G83 peck | 16000 | 0.0250 | **800** | set here, accepted in use |

**S12000 on T12 everywhere.** *"make the spindle speed 12000 everywhere"*,
*"but constant 12000 spindle"*. Never varies within a file. The complaint that
started it was S9000 → S5000 → S9000 appearing mid-program with no reason.

**The drill/plunge rule is a RATIO, not a number.** A quarter of whatever the
cutting chipload is. If the cutting chipload changes, this follows it.

---

## 4. Reading the segments — what the number has to survive

A feed is only real if the geometry lets the machine reach it.

```
LINEAR-LIMITED      reachable F = 0.5 * sqrt(2 * a * d) * 60      a = 200 mm/s2
ROTARY-LIMITED      t = 2*sqrt(dC / a_C)  per block               a_C = 4 deg/s2 (A: 8)
```

**On a path that turns A or C, the rotary almost always binds first.** Measured
2026-09-30 on `side_l-02_cut`: the swarf cut was **93% C-bound** — 497 s of
533 s set by C, against 219 s if the feed had set it. Capping the feed there
changed the commanded number and almost nothing else.

**So: do not cap a feed for reachability on a rotary path.** It is not the
constraint and the cap is cosmetic. Set the chipload-correct number. Linter
check `P2` still computes reachability from the LINEAR acceleration only and
is wrong on rotary paths — **that is my defect, not the program's**, and until
it is fixed its errors on swarf sections are to be read and ignored, not
"fixed" by lowering a feed.

**Where it does bite:** a three-axis path with short segments. There the
linear formula is right and the feed should come down to what the blocks
allow.

---

## 5. What is NOT mine

| | |
|---|---|
| where the cutter goes | tolerance, chord error, **gouge bounds**, stepover, depth of cut, stock to leave |
| segment length | Production's — it is geometry |
| accelerations, velocities, the control | Controls' |
| rapid rate | not a feed |
| **G0 vs G1** | **the motion mode is geometry. Not mine.** |

Operator 2026-09-30, after I changed two posted `G1` air moves to `G0` instead
of reporting them: *"come on. if it should be a rapid, TELL production"* ...
**"you only touch F and S"** ... **"nothing else"**. The edit was reverted and
the file put back byte-identical to what he ran. **I edit the F word and the S
word and nothing else in the line.** A move posted as a feed move when it
should be a rapid is a REPORT to Production, every time.

I gave a 0.05 mm gouge bound once, unasked. *"you DO NOT DETERMINE where the
cutter goes"*. Withdrawn, never to be reissued. **The test when asked for a
number: does it change where the cutter goes? Then ask him.**

---

## 6. The check I run on every file, every time

Not a spot check. Every S and every F in the file, grouped, with the chipload
printed:

```
for each file:
    MATERIAL -- what is actually in the vice, not what the post assumed
    tool from the T word of the M6
    diameter and flutes from machine/tool_table.json
    S from the material's Vc and that diameter
    every distinct S, every distinct F in the written file
    chipload = F / (S x flutes) for each
    FLAG anything outside the material's band
    white oak band: 0.015 .. 0.17 mm/tooth
```

**0.0100 mm/tooth is the number that keeps arriving** — S5000 F100 on a 1/8
two-flute. It rubs and burns rather than cutting. It has come in on five
consecutive posts and I have had to fix it every time.

**NEVER LET A FEED PASS WRITE A G WORD.** On 2026-09-30 my pass prepended an
explicit `G1` after `N\d+` whenever it wrote a feed onto a line — a guard added
because an earlier `re.sub(r'\bG0\b', ...)` silently did nothing on modal
lines. It hit `N55 X31.8 Y509.588`, a modal **G0** traverse in Production's
post, and made it `G1 X31.8 Y509.588 F800`: 510 mm at 13.3 mm/s, **38.29 s**,
and he stood at the machine watching it. I then reported it to Production as
THEIR defect. It was mine, found by them.

```
THE PASS MAY REWRITE THE F WORD AND THE S WORD. NOTHING ELSE IN THE LINE.
A line with no G word is MODAL -- leave it modal. If a feed does not belong
on it, the line is not mine to touch at all.
```

**A per-line pass is not enough.** On 2026-09-30 I ran a classifier over
`side_r/01_pilot` and it left `F100` on all five `G83` lines while correctly
changing the others — I reported the file as done without re-reading its feeds
afterwards, and he found it crawling at the machine. **Re-audit the written
file, not the intention.**

---

## 7. Open

- `P2` to account for the rotary bind, not just the linear acceleration.
- The feedback tool he has asked for, that improves these from what he tells
  me at the machine: `docs/plans/grumble_index.md`.
