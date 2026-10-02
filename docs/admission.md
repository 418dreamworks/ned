# Admission — what I check before a program reaches the machine

Rule 16: a program does not go to ned until I have checked it fits the travel,
against the LIVE offsets and the tool actually in the spindle. This file is
that check and nothing else.

Extracted from `docs/migration.md` sections 6, 9 and 10 on 2026-10-01, when
the setup and maintenance notes moved to Controls. The rest of `migration.md`
is theirs. Nothing here is edited from the original except this header and the
note below on where the numbers now live.

**The numbers come from `~/418ops/machine/`, never from a config:**

```
kinematics.json   pivot_length_mm 142.6499, and
                    L        = pivot + tool_length_z
                    joint X  = tipX + L*sin(A)*sin(C)
                    joint Y  = tipY - L*sin(A)*cos(C)
                    joint Z  = tipZ - L*(1 - cos(A))
limits.json       per JOINT min/max/velocity/acceleration; spindle
                  operator_min_rpm 4000 (min_rpm 1000 is only what the
                  control accepts)
tool_table.json   diameter, flutes, length offset
```

**A block only moves the axes it names, and `G53` means that block's words
are already machine coordinates.** My first version of the joint check ignored
both and flagged every `G53 G0 Z0.` in a file by reading its program X and Y
as machine coordinates.

---

## 6. Linter rule E1 — travel box in the header

Operator: *"i want the max box of travel from its datum in program comments at
the top ... make it a rule."*

Written and working in the sandbox against both live programs. Declared as one
header line, same shape as `BLANK ASSUMED` and `STOCK TOP Z`:

```
(TRAVEL BOX X <min> TO <max> Y <min> TO <max> Z <min> TO <max>)
```

**Checked, not trusted** — recomputed from every move and it must contain
them. Proven both ways on a copy of `swarf5`: a true box passes, a box 15 mm
short on Z is refused by line and axis.

**Why it is worth a rule:** whether a program fits is decided at the machine
against an offset the program cannot know. Tonight that meant reading 2909
lines twice, and the answer *changed* when the pivot length changed. A box in
the header makes it arithmetic the operator can do at the control.

It bounds the **tip**, in program coordinates. Not joint travel — under
`ned_ac_kins` the linears swing wider by the pivot length and no linter knows
the pivot or the tool. Soft limits still want the joint check.

**Not landed:** 1 of 31 existing fixtures fails, because E1 now demands a
header none of them carry. Every fixture needs the line before this ships.


---

## 9. Joint-travel check before every run — MINE, and I did not do it

Operator, 2026-09-29: *"that the toolpaths we ran earlier would have run into
the soft limit is a check YOU should have performed."*

He is right. `side_l-02_cut.ngc` was handed over as ready, ran both finish
passes, and died at the first tilted move:

```
Linear move on line 187 would exceed joint 2's negative limit
```

**Why E1 (§6) would not have caught it.** E1 bounds the **tip, in program
coordinates**. The soft limit is on the **joint**. Under `ned_ac_kins` they
differ by the pivot swing:

```
joint Z = progZ + G57z + toolz - L(1 - cos A)        L = arm.out = pivot + toolz
line 187:  50.0709 + (-711.7623) + 109.0000 - 251.6499(1-cos45) = -626.3979
floor -620.0  ->  6.3979 past.   Whole file: 83.4990 past at line 3053 (A+56.393).
```

A tip-space box check passes this file. Only the joint check refuses it.

**Why it is mine and not the linter's.** The linter cannot know `G57z`,
`toolz` or `arm.out` — they exist only at the machine, and the answer changes
every time the operator touches off or swaps a tool. I can read all three from
the live pins in under a second.

**The check, before I ever say a program is ready to press:**

1. read `g5x_offset[2]`, `tool_offset[2]`, `arm.out` from the running machine
2. walk every move, tracking `G53` correctly — a `G53 G0 Z0.` re-bases the
   modal Z and my first pass got this wrong, which produced a confident wrong
   answer (199.89 mm) before the real one (90.89)
3. compute joint X, Y, Z per move and compare against `ini.N.min_limit` /
   `max_limit` read live, never from the ini file
4. report the shortfall **as a number and a line number**, not a verdict

**It is not optional and it is not a linter rule.** It is the last thing I do
before handing a file over, the same way `tools/gcode_check.sh` is (rule 18).
A program that has not had its joint travel checked against the live offsets
has not been checked.

**Related, same session:** a longer tool GAINS joint Z at `d·cos A` — I told
him the opposite and was wrong. Raising the work gains 1:1. Both numbers
belong in the report, because the operator decides which lever to pull.


---

## 10. Feeds and speeds table -- Production posts to it, we check it

Operator 2026-09-29: *"we will need a table of parameters for feeds and speeds
that production must follow"* ... *"we own feedrates for now, but the
architecture has to change."*

**Today:** the post emits geometry and whatever F/S the CAM felt like, and I
rewrite them by hand after the fact. That happened twice in one week --
`side_l-02_cut.ngc` shipped with S9000 -> S5000 -> S9000 mid-file and a
chipload that had never been discussed, and the bore feed was four times what
the operator wanted. Both were caught by him, not by me.

**Wanted:** one table, per tool and per material, that Production's post
applies. Machining then CHECKS the output instead of rewriting it.

Minimum columns, from what we have actually had to set by hand:

```
tool      dia   flutes   material     S      chipload mm/tooth   plunge factor
T12       6.35    2      white oak    12000      0.1500              0.33
T14       3.175   2      white oak     5000      (marking only, 0.5 mm dot)
```

`F = S * flutes * chipload`, and the plunge factor is the fraction of that used
for a Z-only move. That is the whole arithmetic; it does not need a document,
it needs a table nobody is allowed to override silently.

**What blocks it:** nothing technical. It is a contract change --
`~/418ops/contracts/gcode-program-intent.md` has to say who owns F and S, and
it currently does not. Sent to Production 2026-09-29
(`mail/production/inbox/2026-09-29-machinist-swarf-segments-marking-dots-and-feeds-table.md`).

**Until it lands:** feeds and speeds are mine, and the chipload of every
cutting path gets checked before I say a program is ready -- see
[[feeds-and-speeds-are-mine]] and §9 above.
