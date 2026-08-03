# Calibration ROUTINE — operator sketch (2026-08-03 00:2x, pre-sleep, NOT final)

Decision pending — operator: "im not so sure now. im going to sleep on it
first." Captured verbatim-ish so nothing is lost; NOTHING built yet.

**Home:** NED CONTROLS (not the probe tab) — sub-tabs per step.

## Step 1 tab — bed/head coplanarity (DOCUMENTATION ONLY; not our work, for
future reference)
1. Calibrate the flatness of the bed with a laser.
2. Optional: sacrificial board on the bed.
3. Epoxy the underside of the bracket (>= 30 microns).
4. Shave the epoxy flat with a router held upside down.
5. Reattach the swivel head -> coplanarity between swivel head and bed.

## Step 2 tab — motion parameters (DOCUMENTATION)
- All PID parameters for movement.
- How steps translate to rotations on the screws.
- Yaskawa servo settings (quick-ref: docs/servo/yaskawa_params_quickref.md).

## Step 3 — the guided A/C/toolsetter program (TO DEVELOP; this is the "today"
part that got parked)
Preconditions: A, C and toolsetter approximately zeroed.
(a) Ensure CONTINUITY between spindle and rod. Insert rod (>= 3 in long),
    probe the position of the rod tip. Position the rod over the centre of
    the probe, press GO — single button.
(b) After GO: find the tip of the rod, then rotate A about 45 deg ... —
    OPERATOR STOPPED HERE ("hmmmm im not so sure now").

Open question the operator went to sleep on: the exact post-GO sequence.
Related: task #23 (A/C true zeros + counts/deg, gates toolsetter cal),
docs/todo.md:31-38 (indicator procedure), memory ac-calibration-means-what
(commanded-vs-encoder is circular; external angle reference required).
