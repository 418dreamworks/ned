# Kinematics (ned) — read-first quick-ref

Config: `KINEMATICS = trivkins coordinates=XYZXBACB kinstype=B`, `JOINTS = 8`.
Joints: 0=X, 1=Y, 2=Z, 3=X (gantry twin), 4=B, 5=A, 6=C, 7=B (gantry twin, SCALE −).
Rotaries: **A = head tilt (tool-side)**, **C = head spin (tool-side)**, **B = workpiece rotary table (table-side)**.

## Facts (upstream linuxcnc.org kinematics.html + man9/kins.9)
- Axis **letter = rotation axis only** (A about X, B about Y, C about Z). It does NOT encode tool-vs-workpiece. That distinction lives in the kinematics **module's geometry**, not the letter — e.g. `maxkins`: B = tool head, C = table; `xyzac-trt`: A & C both table. Same letters, different mounts.
- **trivkins = pure identity passthrough — NO TCP/RTCP compensation.** Rotating A/B/C does not move commanded XYZ (source: `pos->a = joints[3]`). Fine for 3-axis + gantry with rotaries used as indexed/positioning axes at a fixed angle.
- Duplicate letters in `coordinates=` = multi-motor axis (gantry): our X = joints 0 & 3, B = joints 4 & 7.
- `kinstype=B` = KINEMATICS_BOTH = module provides forward + inverse → joint mode (homing) **and** teleop/world mode (`$` toggles in Axis). This is NOT identity↔TCP runtime switching — that is the separate `switchkins` facility (module must be built switchable; most ship `KINS_NOT_SWITCHABLE`).

## Real 5-axis TCP on ned: NO stock module fits
ned has TWO tool-side rotaries (A tilt + C spin head) AND a table rotary (B). Stock 5-axis modules:
- `xyzac-trt-kins` / `xyzbc-trt-kins` — both rotaries on the TABLE
- `5axiskins` — tool-side only
- `maxkins` — one tool (B head) + one table (C)

None covers two tool rotaries + a table rotary. Real TCP/RTCP requires a **custom kinematics module** (`userkins.comp` template → `halcompile`; switchable via `switchkins`, `millturn.comp` is the example). Deferred — not needed while A/B/C index at fixed angles.

## Note
Vendored `docs/linuxcnc/manual/motion/kinematics.html` is locally patched/corrupted (a Spanish word spliced into an English sentence at ~line 407). Trust upstream linuxcnc.org, not the repo copy. (Same divergence class as the S-curve/PLANNER_TYPE doc — see `motion_quickref.md`.)
