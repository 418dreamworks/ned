# Yaskawa SGDXS — parameter quick-ref (READ FIRST)

Definitive answers pulled from the manual
(`docs/servo/text/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.txt`).
Read this BEFORE re-opening the manual — these questions recur.

## Software position limits — the servopack does NOT have them
- This SGDXS **analog/pulse** SERVOPACK has **no settable position software limit**.
  No `Pn8xx` parameter, no "software limit setting" section, no ToC entry. The term
  "software limit" appears only twice, incidentally ("*if* software limits are
  enabled…", lines 9360 & 33606).
- Software limits belong to the **network / SigmaLINK-II positioning** variant, not
  this pulse-input drive. In step/dir (pulse) mode the drive is a pure follower.
- ∴ "zero, then set + and − stops" is **LinuxCNC's** job, not the drive's:
  home the axis to zero (repeatable via the absolute encoder), then set per-joint
  **`MIN_LIMIT` / `MAX_LIMIT`** in `ned.ini`. Hardware P-OT/N-OT switches are the
  only drive-level travel stop, and they are switch-triggered, not taught positions.

## Overtravel disable (the "not-pot" fix) — Pn50A / Pn50B
**USE THESE VALUES: `Pn50A = n.8101`, `Pn50B = n.6548`. Power-cycle (both "After restart").**

Why not the "obvious" `n.8000`/`n.0008` (which FAILED to clear not-pot, 2026-07-23):
- Pn50A's **last digit = Input Signal Allocation Mode** (line 11080-11088):
  `0` (default) = use *default* allocations → the P-OT/N-OT allocation digits are
  **IGNORED**. `1` = Sigma-7S mode → the digits take effect. Must set the mode to **1**.
- Allocation value **8** = "not allocated to a pin, always inactive — set to 8 if the
  signal is not used" (line 11259-11261). `5` only moves P-OT to CN1-45 (still
  pin-dependent) — **8 disables, not 5**. (The "(enable forward drive)" parenthesis at
  line 11277 describes pin allocation, not disabling — confusing wording.)
- Digit map (defaults Pn50A=**2100h**, Pn50B=**6543h**, from param list line 43710):
  - `Pn50A = n.[P-OT][/P-CON][/S-ON][mode]` → `n.8101` = P-OT off(8), /P-CON→CN1-41(1),
    /S-ON→CN1-40(0, matches ned wiring), mode=1.
  - `Pn50B = n.[/N-CL][/P-CL][/ARM-RST][N-OT]` → `n.6548` = keep 6/5/4, N-OT off(8).
- ⚠ Line 11103: disabling P-OT/N-OT removes drive-level overtravel protection. OK here
  (no OT switches wired) — LinuxCNC MIN/MAX_LIMIT + hardware e-stop cover it.
- The manual's trial-op procedure (line 17649) writes "`n.8□□□`/`n.□□□8`" but omits the
  mode digit — that shorthand only works once mode=1; hence `n.8101`/`n.6548`.

## Control mode (already set)
- `Pn000 = n.□□1□ = 0010` = position control (pulse/step-dir). 0000 = analog speed.
  Required for the 7I85S step/dir to do anything.

## Drive stuck on "bb" (won't energize even with /S-ON forced)
`bb` that won't clear even with /S-ON always-active (Pn50A n.8171) = a **/S-RDY
condition** is failing. Manual §6.1.9 (line 11706): the drive only becomes ready to
accept /S-ON when ALL of these hold —
1. Main circuit power ON  2. No HWBB (CN8)  3. No alarms  4. No forced stop (FSTP ON)
5. **Absolute encoder → SEN signal ON (high)**  6. Polarity detection complete.
- **Most common trap here (#5): Pn002 = absolute but SEN not wired.** ned's CN1 has
  no SEN (`yaskawa_servo_wiring.md` §2) → SEN never high → never ready → permanent bb.
  - Bench-test fix (manual line 17655): **Pn002 = n.□1□□ (incremental)** → no SEN needed.
  - Keep-absolute fix (manual §6.12 (1)(b) "absolute WITHOUT the SEN signal", line 15630):
    **Pn50A = n.□□□1** (mode 1 — already set as n.8171) **+ Pn515 = n.8887** (default
    8888h, SEN digit 8→7 = always active). Restart. Needs no wire.
    NOTE: Pn515 is IGNORED if Pn50A ends in 0 (default alloc mode) — must be mode 1.
    Default Pn515 SEN digit = 8 (always INACTIVE) → that is the usual bb cause in absolute.
- Diagnose in SigmaWin+: **[Monitor]→[Wiring Check]** (SEN, /HWBB1//HWBB2, FSTP states);
  **[Monitor]→[Monitor]→[Status Monitor]** (/S-RDY flag; Main Circuit DC Voltage ≈0 =
  main power/head-contactor absent).

## Electronic gear (Pn20E / Pn210) — motor barely moves / wrong speed
- Encoder: SGMXJ…**U = 26-bit = 67,108,864 counts/rev** (manual line 10087).
- **Command pulses per motor rev = enc_res × Pn210 / Pn20E = 67,108,864 × Pn210/Pn20E.**
  (verified: Pn20E=256/Pn210=1 → 262,144 pulses/rev; move.hal @1000 pulses/rev gave
  motor = 1000/262,144 = 1/262 of commanded → "1000" cmd = ~3 RPM.)
- **Range limit: 0.001 ≤ Pn20E/Pn210 ≤ 64000** (manual line 10037), else **A.040**.
  → min achievable = 67,108,864/64000 ≈ **1049 pulses/rev**. "1000 pulses/rev" is
  IMPOSSIBLE (needs gear 67108 > 64000).
- **ned head setting: Pn20E = 8192, Pn210 = 1 → 8192 pulses/rev**, and **move.hal
  stepgen.02/.03 position-scale = 8192** must match. Then move.sh RPM = real motor RPM;
  stepgen tops out ~1465 motor-RPM (200 kHz / 8192). Software-reset after (Pn20E/210).
- Sign inverted (motor runs negative for a +command) = fix with **Pn000.0** (direction)
  or a negative scale — separate from the gear.

## Panel displays
- **`bb`** = **base block** (manual line 1344): motor power shut off at the drive =
  normal servo-**OFF** standby (drive ready, no alarm, waiting for /S-ON). **NOT an
  error.** Goes to **`run`** when /S-ON is asserted. Seeing `bb` instead of not-pot =
  the overtravel/Pn50A-B fix worked.

## Encoder
- `Pn002 = n.□X□□`: `0`=absolute (battery-required, BAT± on CN2 3/4), `1`=incremental.
- Battery-required 26-bit absolute → **A.810** every power-up if BAT± unbatteried.
