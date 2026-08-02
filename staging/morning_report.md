# Overnight window report — 2026-08-02 (started 01:55)

## Homing goal
- (results filled as take-3 rounds land)

## Root causes nailed tonight
1. WEDGE TRIGGER REPRODUCED: second-actor task traffic (mode switches /
   MDI) during a homing-sequence start wedges X/Y/W at the search-start
   state. Reproduced harness-vs-handler at 02:13; matches every operator
   wedge (clicks + background GUI/brain traffic). Rule: ONE actor per
   machine phase; wait for homing flags to clear before any task traffic.
2. Pre-launch-read bug (mine): in-place scheduler had no executor ->
   A/C never homed on slow-boot launches; menu stayed grey forever.
   Fixed (do_inplace + tick consumer), verified live in take-2/3.

## Built, awaiting operator-present verification
- tc_flag: brain suspends mode-restore during tool changes (staging/tc_flag)
- MASTER.params + gen_params.py: round-trip PASS, 13 derived sites
- JOG & PRESETS v2 -> stock JOG page (agent, staging/jog_v2)
- RACK MAP page + per-pocket table (agent, staging/rack_map)

## For the first hour together
1. Apply tc_flag + ports (stack down), relaunch
2. First flagged M6 (T1->T2 swap, operator present)
3. Sawblade T15: teach seat + clearance on the RACK MAP page
4. Jog panel look-and-feel pass
