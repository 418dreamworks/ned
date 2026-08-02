# Rack ATC bring-up — 2026-08-02 (overnight session)

Operator goal: "automatically change tools. drop one tool, and go get the
other." Linear 15-fork rack (bored from the 92.0 mm hole-pair jig,
`bore_14_pairs.ngc`), tools T1–T15, **T15 is a sawblade with a custom
position — fixed tool↔fork homes are a hard rule.**

## What went live tonight

- **PB rack ATC chain ported** from `rack_atc_sim` (2025 vintage) over the
  neutered 2024 stubs: `toolchange.ngc`, `m10–m13`, `m21`, `m22`,
  `rack_id_calc.ngc`, `m6_tool_call_*`, python remap glue
  (`configs/ned5_pb/python/`), `REMAP M6 …` + `[PYTHON]` + `[ATC]
  POCKETS=15` in `ned5_pb.ini`. Old files preserved in
  `trash/configs/ned5_pb/subroutines_pre_rack/`.
- **ned adaptations:** M19 spindle-orient stripped from m21/m22 (no orient
  hardware; forks accept any rotation — proven by daily hand loading).
  M24/M25 rewritten as sensor-verified drawbar wrappers delegating to
  `unclamptool`/`clamptool` (S1/S2 gates, e-stop-gated release).
- **FIXED TOOL HOMES:** `toolchange.ngc` put-away patched: tool N returns
  to fork N, always; aborts loudly if the fork is not marked empty. The
  stock lowest-empty-pocket shuffle is forbidden on this rack.
- **Rack geometry taught** via PB's RACK SETUP page (pocket 1 + pocket 2 +
  clearance line + Z heights; `rack_id_calc` auto-derived RACK ID = 4:
  row +Y→−Y, entry from −X). Pockets interpolate 92.0 mm along the row —
  **to be replaced by the per-pocket table** (staging/rack_map) so the
  sawblade gets a custom position AND custom clearance.
- **Toolsetter calibrated:** spindle-zero = 592.941 mm (machine Z of the
  bare-nose trip: −592.941). T1 = +87.893, T2 = +114.244 measured. NOTE
  the PB flow: touch-off position is stored with Z at FULL UP and a
  ~600 mm probe window; a Z work offset ≠ 0 corrupts the spindle-zero
  number (G10 L2 P1 Z0 first). The platter sits only 27 mm above the Z
  soft floor (−620) — probe windows must respect the floor pre-check.
- **Air interlock debounce:** the drawbar release gulp dips line pressure
  and used to kill machine power mid-change. `air.debounce` (timedelay,
  2.0 s off-delay, operator's number) now sits between the raw pressure
  switch and `air.permit`; the GUI still shows the RAW switch.
  (`timedelay` is loaded ONCE for both instances — a second loadrt of the
  same comp kills the launch; cost one failed launch to learn.)

## First live results

- First automatic pickup of T1: SUCCESS (slow: traverse was 300 mm/min;
  operator settled on 1000).
- First put-away: ABORTED mid-return by ned_brain's program-done
  MANUAL/teleop restore (a mode switch aborts the remap). Fix staged:
  `staging/tc_flag/` — motion digital P1 = "tool change in progress",
  raised/dropped by toolchange.ngc + on_abort, brain suspends its restore
  while high. Apply with the stack down, verify with operator present.
- Power-loss mid-change leaves the release solenoids RE-ENERGIZED on
  re-power (digital-out-00 latched in motion; on_abort does not run on a
  power drop). Full stack shutdown is the reliable way to clear a stuck
  release. Consider an estop/power-edge clear of P0/P1 in the iron.

## Open

- Per-pocket table + RACK MAP GUI page (staging/rack_map when built):
  positions, clearances, tool↔fork assignment, teach buttons, sync.
- T15 sawblade stays quarantined from M6 until the table lands.
- T3–T14 lengths unmeasured; tool table rows beyond T3 mostly absent.
- First flagged M6 end-to-end test (operator present).
