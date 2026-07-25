# To do

## Workpiece rotary pair (LinuxCNC axis B, joints 4 & 7) — DONE
- ✓ DONE 2026-07-09: both steppers work independently (stepgen.00 = motor 1, stepgen.01 =
  motor 2); set up as a B gantry (joints 4 & 7, duplicate B in coordinates), joint 7
  counter-rotates via negative SCALE. ned.ini + ned.hal §3/§8 done.
- ✓ RESOLVED 2026-07-23 (user): the "two rotaries turn different amounts" symptom was **a
  shield grounded in the wrong place** (noise → miscounts), NOT a gearing/ratio variance.
  Re-grounding the shield fixed it → **no per-joint SCALE trim needed.** (Supersedes the
  earlier 2026-07-09 "fixed gearing variance" conclusion.)

## Head servo → LinuxCNC
- ✓ DONE 2026-07-22: HAL brought up — AB/C axes (stepgen 02/03), /S-ON + ALM, un-INERTed
  (`ned.hal` §3/§7/§8, `ned.ini` [JOINT_5]/[JOINT_6]).
- ✓ DONE 2026-07-23: **BOTH head servos (A tilt / C spin) MOVE under software** (`move.sh a|c`).
  Drive params (all in `docs/servo/yaskawa_params_quickref.md`): Pn000=0010 (position),
  Pn50A=8171/Pn50B=6548 (not-pot cleared), Pn515=8887 (SEN always-active → leaves bb in
  absolute, no SEN wire), Pn20E=8192/Pn210=1 (electronic gear). Params copied C→A. move.hal
  stepgen.02/.03 scale=8192 to match. 10° test move confirmed on both.
- **CALIBRATION STAGE (deferred, agreed 2026-07-23):** → master list:
  **`docs/commissioning/calibration_plan.md`** (all axes+spindle, Fagor-decoded values)
  - Electronic gear / SCALE: 8192 pulses/rev is provisional — finalize with `[JOINT_5]/[JOINT_6]SCALE`.
  - Direction: both run **negative** for a +command → fix sign (Pn000.0 or scale sign).
  - Real AB/C axis limits: `MIN_LIMIT`/`MAX_LIMIT` in `ned.ini` (drive has NO soft limit — host's job).
  - /S-ON: revert from always-active (Pn50A d2=7, n.8171) → **driven** (n.8101) for normal op.
  - 5axiskins: unresolved — stock 5axiskins is B/C bridge mill, head is AB/C.
- Pn002 = absolute (n.□0□□) set on both; A.810 cleared (batteries wired).

## Spindle — turns via software
- ✓ DONE 2026-07-23: `move.sh spindle <RPM> <s>` spins the Mollom/HQD both directions
  (R6→S1 FWD, R7→S2 REV; negative RPM = reverse). Err15 = e-stop kill (chain → R2 → S3).
  move.sh is fully standalone (kills LCNC, own HAL).
- ✓ DONE 2026-07-25: **AI2 speed control tracks commanded RPM.** Spindle analog =
  **pwmgen.05 (AOUT5 = TB3-24), offset-mode 1, scale 18000** — was wrongly on pwmgen.04
  (dead AOUT4) + offset-mode 0. Fixed in ned.hal + move.hal + move.sh. `move.sh spindle N` = N rpm.

## Spindle over-temp — DONE (hardware kill in the e-stop chain)
- ✓ WIRED + DOCUMENTED 2026-07-23: NC thermostat in SERIES at the chain end — LHS e-stop
  → `*39` → thermostat NC → `*67` → yellow jumper → `*6`; white off `*71`; IN14 taps `*39`
  as a **diagnostic** (24 V + `*6` low = over-temp; `*39` 0 V = e-stop). Hot opens →
  `*6` drops → R2 → Mollom S3 ext-fault → spindle coasts. Pure hardware kill, works even if
  HAL is wrong. Verified healthy (estop TRUE, tap TRUE). Tracing docs written:
  `screw_terminals.md` (`*5`/`*6`/`*39`/`*67`), `field_devices.md`, `ned.hal:462` — Fagor
  original wiring preserved alongside the as-built.
- Later (optional): a chiller with a temp sensor is complementary **loop monitoring** (reads
  coolant, not the stator winding) — NOT a substitute for this thermostat protection.

## Spindle cooling — bucket (planned 2026-07-22)
- **Just a bucket first**: pump in the bucket → spindle → return to the bucket. Hook up the pump.
- Only if the bucket heats up in practice: add the pool loop (sump pump + heat exchanger in
  the bucket, pool water on demand — hardware already on hand).

## HQD spindle ATC sensors
- Wiring DONE (as-built HQD 2026-07-09): S1 tool-lock → input-30/`*69`, S2 tool-release → input-31/`*70`, S3 shaft-stop → input-29/`*68`. All PNP-NO (brown +24, black sig, blue 0V).
- ✓ S3 shaft-stop (input-29) VERIFIED 2026-07-09 — toggles TRUE/FALSE on hand-rotation.
- ✓ VERIFIED 2026-07-25 — **S1 tool-lock (input-30)**: with a tool holder seated + clamped, input-30 reads **TRUE** (FALSE when empty). End-to-end confirmed (BIGGREEN red → `*69` → 7I84 input-30).
- ✓ VERIFIED 2026-07-25 — **S2 tool-release (input-31)**: went **TRUE the instant the unclamp air fired** (mesalog 16:47:49) and dropped FALSE when the air released. End-to-end confirmed (BIGGREEN brown → `*70` → 7I84 input-31). All 3 HQD ATC sensors (S1/S2/S3) now proven.
- Interlocks (later): S3 must confirm stopped before unclamp; S1 must confirm locked before spin.

## Pendant / MPG handwheel
- Identify each X6 conductor's electrical **function** (encoder A/B/A̅/B̅, +5 V, 0 V, axis-selector) —
  the pin→conductor map is traced (`tracing/pendant.md`), the functions are not. Confirm MPG PPR
  rating + supply voltage (datasheet not on hand).
- Then land on Mesa (handwheel → 7I97T/7I85S encoder input; buttons → Mesa DI) + HAL.

## Greaser (way-oil pump) — move to a schedule (deferred, 2026-07-25)
- Now: grease pump AC hot is switched by **R1** (spindle-running relay ← Mollom Y1). So it only
  runs while the spindle runs. User doesn't want that tie.
- Want: run the greaser on a **schedule** (periodic timed lube, e.g. N s every M min), independent
  of spindle. Candidate: drive it from the **spare relay R4** (coil parallels R3, contacts unwired
  per `relays.md`) via a Mesa output on a HAL/LinuxCNC timer. Rewire R1A1/R1D1 pump-hot leg over
  to R4 when done.

## Docs — consistency sweep
- ✓ DONE 2026-07-22 (user-confirmed): components.md AB rename + encoder battery;
  field_devices.md cable-92 conductors; to_buy.md §4; AB rename across INDEX/mesa/relays.

## Safety
- ✓ DONE 2026-07-22 (user-confirmed): R11 swapped to NORMALLY-OPEN — fail-safe restored;
  70 V brick + head power now only with drive-enable.
- ✓ DONE 2026-07-23 (user-confirmed): R11 coil suppression fixed. Original P6KE33CA TVS
  went leaky→thermal-runaway→short (root cause of the intermittent estop/6V-sag saga +
  magic smoke); replaced with a **flyback diode** across R11 A1/A2 (band/cathode → A2/`*7`,
  anode → A1/GND). Rotary run confirms R11 pulls in cleanly, no sag.

## Misc
- ✓ DONE 2026-07-22 (user-confirmed): 5 V brick ratings recorded.
- ✓ DONE 2026-07-22 (user-confirmed): CN8 safety jumper installed.
