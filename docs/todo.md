# To do

## B-axis steppers — ned.hal wrong (2 SEPARATE joints, not 1)
- ✓ CONFIRMED 2026-07-09: BOTH drives + motors work **independently** — stepgen.00 (TB2 11-14) turns motor 1, stepgen.01 (TB2 19-22) turns motor 2. position-fb ramps on both; each turns its own motor. Mesa→both drives→both motors all good. No hardware fault — the earlier "only one turned" was the bench file commanding only stepgen.00.
- ⚠ `ned.hal` §8 is WRONG: drives only stepgen.00 for joint 4 and calls the pair "one stepgen / one reversed in copper". They are **TWO SEPARATE axes** — separate mechanically + electrically, only software-linked.
- Fix ned.hal: give **each stepper its own joint** (stepgen.00 and stepgen.01), not one joint driving both. stepgen.01 = "twist" per `mesa_7i85s_wiring.md:16` — axis letter + kinematics slot TBD.
- ✓ DONE 2026-07-09: set up as B gantry (joints 4 & 7, duplicate B in coordinates), joint 7 counter-rotates via negative SCALE. ned.ini done; ned.hal joint-7 wiring + §8 stepgen.01 done.
- ✓ DONE 2026-07-22 (user-confirmed). ~~**Match the two B steppers (open — deferred):**~~ they turn different amounts for the same command; **user determined it's NOT slipping — a fixed manufacturing/ratio variance** (2026-07-09). **Both drives confirmed at 400 pulses/rev + no slip → the motor shafts turn identically; the variance is downstream in the worm/wheel reduction (gearing), not motor/drive.** Fix = per-joint `SCALE` trim so both rotate identically for the same B command (works at all speeds/positions since it's a constant ratio). Method: command a known move (e.g. 10 motor revs) on each, measure each output's actual travel, ratio = the correction; multiply the short joint's `SCALE` by it. One number in `[JOINT_4]`/`[JOINT_7]SCALE` — no new HAL. (Only revisit as slip if the offset ever changes with load/speed.)

## Head servo → LinuxCNC
- ✓ DONE 2026-07-22: HAL brought up — AB/C axes (stepgen 02/03), /S-ON + ALM, un-INERTed
  (`ned.hal` §3/§7/§8, `ned.ini` [JOINT_5]/[JOINT_6]).
- ✓ DONE 2026-07-23: **BOTH head servos (A tilt / C spin) MOVE under software** (`move.sh a|c`).
  Drive params (all in `docs/servo/yaskawa_params_quickref.md`): Pn000=0010 (position),
  Pn50A=8171/Pn50B=6548 (not-pot cleared), Pn515=8887 (SEN always-active → leaves bb in
  absolute, no SEN wire), Pn20E=8192/Pn210=1 (electronic gear). Params copied C→A. move.hal
  stepgen.02/.03 scale=8192 to match. 10° test move confirmed on both.
- **CALIBRATION STAGE (deferred, agreed 2026-07-23):**
  - Electronic gear / SCALE: 8192 pulses/rev is provisional — finalize with `[JOINT_5]/[JOINT_6]SCALE`.
  - Direction: both run **negative** for a +command → fix sign (Pn000.0 or scale sign).
  - Real AB/C axis limits: `MIN_LIMIT`/`MAX_LIMIT` in `ned.ini` (drive has NO soft limit — host's job).
  - /S-ON: revert from always-active (Pn50A d2=7, n.8171) → **driven** (n.8101) for normal op.
  - 5axiskins: unresolved — stock 5axiskins is B/C bridge mill, head is AB/C.
- Pn002 = absolute (n.□0□□) set on both; A.810 cleared (batteries wired).

## Spindle — turns via software
- ✓ DONE 2026-07-23: `move.sh spindle <RPM> <s>` spins the Mollom/HQD both directions
  (pwmgen.04 0-10 V → AI2; R6→S1 FWD, R7→S2 REV; negative RPM = reverse). Err15 verified
  as the e-stop kill (chain → R2 → S3). move.sh is fully standalone (kills LCNC, own HAL).

## Spindle over-temp
- ✓ WIRED 2026-07-23 (as-built): thermostat in SERIES at chain end — LHS e-stop → `*39`
  → thermostat NC → `*67` → yellow jumper → `*6`; white off `*71`; IN14 taps `*39`
  (24 V + `*6` low = over-temp; 0 V = e-stop). Verified healthy (estop TRUE, tap TRUE).
- ⚠ TODO: tracing-doc notes for this rewire (`*5`/`*6`/`*39`/`*67`/`*71`, field_devices,
  ned.hal:462 comment) — user deferred; not yet written.
- Now: NC thermostat → `*39` → 7I97 IN14, but `sig-spindle-overtemp` is **DANGLING** in ned.hal (read only, wired to nothing) → **no working over-temp protection yet** (`ned.hal:456`, `:261`).
- **DECIDED 2026-07-22 (supersedes the R4-duplication plan):** wire the NC thermostat **in
  series at the END of the e-stop chain** (between the last button and `*6`) → opens hot →
  `*6` drops → R2 drops → Mollom S3 external fault → spindle coasts. Kill path is **pure
  hardware** (chain → R2 → S3); works even if Mesa/HAL is wrong.
  - **Diagnosis = one extra reading:** tap the node between the last button and the
    thermostat → a spare Mesa input.
    - tap 24 V + `*6` 24 V → healthy
    - tap 24 V + `*6` 0 V → **spindle over-temp** (thermostat open)
    - tap 0 V → **an e-stop button**
  - No R4 needed. If Mesa/HAL is misconfigured it only muddies the diagnosis, never the kill.
- A chiller with a temp sensor (if bought) is complementary **loop monitoring** — reads coolant, not the stator winding — NOT a substitute for the thermostat protection.

## Spindle cooling — bucket (planned 2026-07-22)
- **Just a bucket first**: pump in the bucket → spindle → return to the bucket. Hook up the pump.
- Only if the bucket heats up in practice: add the pool loop (sump pump + heat exchanger in
  the bucket, pool water on demand — hardware already on hand).

## HQD spindle ATC sensors
- Wiring DONE (as-built HQD 2026-07-09): S1 tool-lock → input-30/`*69`, S2 tool-release → input-31/`*70`, S3 shaft-stop → input-29/`*68`. All PNP-NO (brown +24, black sig, blue 0V).
- ✓ S3 shaft-stop (input-29) VERIFIED 2026-07-09 — toggles TRUE/FALSE on hand-rotation.
- TODO — confirm **S1 tool-lock (input-30)**: seat a tool holder in the taper (no air) → expect TRUE. (FALSE when empty is normal — spring over-travels the clamp detent; not a drawbar-position sensor like the Colombo.)
- TODO — confirm **S2 tool-release (input-31)**: apply unclamp air (port B, 10.5–11.5 bar) → expect TRUE. Only signal leg still unproven end-to-end.
- Interlocks (later): S3 must confirm stopped before unclamp; S1 must confirm locked before spin.

## Docs — consistency sweep
- ✓ DONE 2026-07-22 (user-confirmed): components.md AB rename + encoder battery;
  field_devices.md cable-92 conductors; to_buy.md §4; AB rename across INDEX/mesa/relays.

## Safety
- ✓ DONE 2026-07-22 (user-confirmed): R11 swapped to NORMALLY-OPEN — fail-safe restored;
  70 V brick + head power now only with drive-enable.

## Misc
- ✓ DONE 2026-07-22 (user-confirmed): 5 V brick ratings recorded.
- ✓ DONE 2026-07-22 (user-confirmed): CN8 safety jumper installed.
