# Kinematics (ned) — read-first quick-ref

**ned runs TWO kinematics, chosen at launch by `run5.sh`.**

| launch | ini | `KINEMATICS` |
|---|---|---|
| `-notcp` | `ned5_pb_lim_gen.ini` (or `_ab_gen` with B) | `trivkins coordinates=XYZXAC kinstype=B` |
| `-tcp` | `ned5_pb_tcp_gen.ini` | `ned_ac_kins coordinates=XYZXAC` |

Joints: 0=X, 1=Y, 2=Z, 3=X (gantry twin), 4=A, 5=C — plus B as 4 & 7 in the
`-ab` config only.
Rotaries: **A = head tilt (tool-side)**, **C = head spin (tool-side)**,
**B = workpiece rotary (table-side)**.

## TCP is in the KINEMATICS, not in the G-code

`ned_ac_kins` is ned's own module (`linuxcnc/src/emc/kinematics/ned_ac_kins.c`),
non-switchable by operator instruction 2026-08-06 *"never use switchkins, remove
all possibility"* — identity sessions load `trivkins`, tool-tip sessions load
`ned_ac_kins`, and nothing switches at runtime.

**A post emits no TCP word.** There is no `G43.4` and no RTCP mode to turn on.
The post emits the **tool-tip XYZ** plus A and C, and the module swings the
linears to keep the tip there:

```
ned_ac_kins.c:74   pos->tran.z = joints[JZ] + pivot_length + r.z
```

**`G43` MUST STAY LIVE FROM FIRST MOVE TO LAST.** The pivot the module rotates
about is fed the live tool length:

```
postgui_tcp.hal:21   net sig-tool-zoff  motion.tooloffset.z => arm.in1
postgui_tcp.hal:22   net sig-pivot-arm  arm.out => ned_ac_kins.pivot-length
head_pivot.inc       PIVOT_LENGTH = 155.9256   (head constant, operator bank 2026-08-06)
```

so `pivot-length = 155.9256 + motion.tooloffset.z`. A `G49` sets that offset to
zero and the module then rotates about a point one tool-length wrong. It is not
a Z error: the error grows with tilt angle and is zero only at A0 C0, so it
hides on a flat move and appears in a swarf.

**Found 2026-09-28** in `linuxcnc.cps` output: one `G43`, two `G49`, no restore —
the whole second swarf uncompensated.

## Facts (upstream linuxcnc.org kinematics.html + man9/kins.9)
- Axis **letter = rotation axis only** (A about X, B about Y, C about Z). It does NOT encode tool-vs-workpiece. That distinction lives in the kinematics **module's geometry**, not the letter — e.g. `maxkins`: B = tool head, C = table; `xyzac-trt`: A & C both table. Same letters, different mounts.
- **trivkins = pure identity passthrough — NO TCP/RTCP compensation.** Rotating A/B/C does not move commanded XYZ (source: `pos->a = joints[3]`). Fine for 3-axis + gantry with rotaries used as indexed/positioning axes at a fixed angle.
- Duplicate letters in `coordinates=` = multi-motor axis (gantry): our X = joints 0 & 3, B = joints 4 & 7.
- `kinstype=B` = KINEMATICS_BOTH = module provides forward + inverse → joint mode (homing) **and** teleop/world mode (`$` toggles in Axis). This is NOT identity↔TCP runtime switching — that is the separate `switchkins` facility (module must be built switchable; most ship `KINS_NOT_SWITCHABLE`).

## Why ned has its own module

No stock module fits: `xyzac-trt-kins` / `xyzbc-trt-kins` put both rotaries on
the TABLE, `5axiskins` is tool-side only, `maxkins` is one tool plus one table.
ned has two tool-side rotaries (A tilt + C spin) and a table rotary (B), so
`ned_ac_kins` was written for it. **This section used to say TCP was deferred and
no module fitted. That has been untrue since the module was built** — corrected
2026-09-28 after the stale text was read as current while sizing a 5-axis post.

## Note
Vendored `docs/linuxcnc/manual/motion/kinematics.html` is locally patched/corrupted (a Spanish word spliced into an English sentence at ~line 407). Trust upstream linuxcnc.org, not the repo copy. (Same divergence class as the S-curve/PLANNER_TYPE doc — see `motion_quickref.md`.)
