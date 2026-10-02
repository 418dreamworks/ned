# The grumble register — what he says at the machine, and what it changed

Operator 2026-09-30: *"start this document where you register my complaints as
something that can help you with future files"* ... earlier the same day:
*"i just want to be able to say which line, and what the issue was"* ...
*"we will use this to build up my preferences and use this index of grumbles to
improve all future toolpath generation"*.

**How to use it.** He gives a line and a verdict. I log it RAW first — his
words, the file, the line, the block as written. Only then do I try to turn it
into a number or a rule, and the derived rule carries the grumbles it came
from. One grumble is a data point. Three that agree are a rule.

**Read this before writing any F or S.** It outranks the table in
`feeds_and_speeds.md` §3 wherever it is newer — that table is the settled
output, this is the evidence feeding it.

---

## The log

| # | date | file / code | line | his words | the block as written | class | state |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-30 | side_l 02_cut | 86-87 | *"line 86 87 is CRAWLING"* | swarf, F3600 on 4.7 mm segments | segment length | Production: merged blocks, 18.1 → 8.1 min |
| 2 | 2026-09-30 | side_l 02_cut | ~620 | *"links in region around lines 620 need to be sped up"* | link moves between cuts | segment length | Production |
| 3 | 2026-09-30 | side_l 02_cut | — | *"the boring feedrate is way too fast. make it a quarter of what it is"* | bore F | **F — mine** | done |
| 4 | 2026-09-30 | side_l 02_cut | — | *"the swarf feedrates are way too slow they should be closer to the feedrate of the finish paths"* | swarf F | **F — mine** | done |
| 5 | 2026-09-30 | all | — | *"fucking make the spindle speed 12000 everywhere"* ... *"but constant 12000 spindle"* | S9000 → S5000 → S9000 mid-file | **S — mine** | rule: S never varies within a file |
| 6 | 2026-09-30 | all | — | *"make the drill and plunge chiploads .25 of the regular one"* | — | **F — mine** | rule: drill/plunge = 0.25 × cutting chipload |
| 7 | 2026-09-30 | side_l 02_cut | between drills | *"it is dragging the bit through the material"* | G1 links at depth between holes | geometry | Production: reposted |
| 8 | 2026-09-30 | side_r 02_cut | many | *"nothing in between moves of all kinds within 10 mm of stock, ever"* then *"its ok. it works, just too close"* | 21 rapids inside stock top + 10 | clearance | Production: 21 → 3, the 3 are `c drilling (2)` |
| 9 | 2026-09-30 | side_r 01_pilot VGA | N55 | *"ITS UFCKING crawling back to the work place"* ... *"why so slow"* | `G1 X31.8 Y509.588 F800`, 510 mm, 38.29 s | **MY BUG** | my F/S pass prepended `G1` to a modal `G0`. Fixed, and the pass no longer writes a G word |
| 10 | 2026-09-30 | side_r 02_cut VXY | 68 | *"line 68 can be 20pct faster"* | `N275 G1 X47.924 Y386.1194 Z8.48 F5400` | **F — mine** | → F6480 |
| 11 | 2026-09-30 | side_r 02_cut VXY | 24 | *"line 24, going back to work area can be faster +20pct"* | `N60 G1 X179.1068 Y453.2044 F5400` | **F — mine** | → F6480 |
| 12 | 2026-09-30 | side_r 02_cut VXY | 159 | *"it errored and stopped right before cut"* ... *"it stopped, but it didn't error out actually"* ... *"its totally fine"* | `N725 G0 A0. C360.` vs `[JOINT_5] MAX_LIMIT 315.0` | travel — **my admission check** | my E1 covers X/Y/Z only. C360 == C0 |

---

## What the log has already settled

### White oak, T12 6.00 mm, 3 flutes — the cutting feed is moving UP

Grumble 10. Line 68 is a finish/contour cut in white oak:

```
N275 G1 X47.924 Y386.1194 Z8.48 F5400        chipload 5400 / (12000 x 3) = 0.1500
       +20%                     F6480        chipload 6480 / (12000 x 3) = 0.1800
```

He has never once said a cut was too fast in oak. Grumble 4 pushed the swarf
feeds up, grumble 10 pushes the contour up. **The direction is one-way so far:
0.1500 is his floor, not his target.** The band in `feeds_and_speeds.md` §6
topped out at 0.17 and this exceeds it — the band was mine, not his, so the
band moves.

Grumble 11 is the same number on an air move — `N60 G1 X179.1068 Y453.2044
F5400` is the return to the work after `G53 G0 Z0`, 509 mm of it. He called the
same +20%. Two independent lines, one asking for a faster cut and one a faster
return, both landing on F6480.

**I do not generalise past the line he named.** +20% is logged against line 68
and the contour feed; it does not touch the G83 peck feeds or T14 until he
says so.

### Three classes, three owners

| class | who | examples |
|---|---|---|
| **F and S** | **mine, and only the F and S words** | 3, 4, 5, 6, 10 |
| segment length, links, clearance, motion mode | Production | 1, 2, 7, 8 |
| my own tooling writing something it should not | mine to fix, and to own out loud | 9 |

Grumble 9 is the one to re-read. I logged it as Production's defect, sent it to
them as Production's defect, and it was mine — found by them reading their own
disk. **Check my own pass before reporting a post.**

---

## Open, from the log

- `c drilling (2)` retract offset refuses to move: 3 blocks still 2.2–2.8 mm
  inside the 10 mm band. Production has it and has not forced it.
- `D3` fires on 29 lead-in ramps in `side_r/02_cut` — it tests where a rapid
  ENDS, not the swept move. My defect.
- **`E1` checks the travel box on X/Y/Z and not on A/C.** Grumble 12: `C360.`
  against `[JOINT_5] MAX_LIMIT 315.0` went out of here unflagged and stopped
  the machine mid-program. The axis limits are Controls' to set; checking a
  program against them before it runs is MINE.
- `P2` computes reachability from the LINEAR acceleration on paths that are
  rotary-bound. My defect, and it is the 4 remaining errors on that file.
