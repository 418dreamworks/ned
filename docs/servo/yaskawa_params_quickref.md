# Yaskawa SGDXS — parameter quick-ref (READ FIRST)

Definitive answers pulled from the manual
(`docs/servo/text/yaskawa_sigma_xs_servopack_analog_pulse_product_manual.txt`).
Read this BEFORE re-opening the manual — these questions recur.

## Absolute readout — the EXACT Sigma-X protocol (from THIS drive's manual §6.12.5, verified 2026-07-28)
- Authoritative section is **§6.12** (Absolute Encoders), NOT §10.3.6 (that's linear/fully-closed-loop).
- **PSO (CN1-48/49)** = full absolute stream, **every 40 ms**. UART: **9600 baud, 7 data bits, EVEN parity, 1 stop (7E1)**, async.
- **Rotary frame = 17 chars:** `P ± NNNNN , PPPPPPPP <CR>` = status(`P`=ok) + sign + **5-digit multiturn** + `,` + **8-digit within-one-turn** + CR. **No checksum.** (PAO burst = 8 chars, multiturn only.)
- Encoder **26-bit = 67,108,864 cnt/rev**; multiturn limit Pn205 (default 65535 → ±32767 turns).
- **Enable no-SEN auto-output:** `Pn002.2=0` (absolute) + `Pn50A.0=1` + `Pn515=n.□□□7` (always active) → streams after power-up, no handshake. (Default `Pn515=8` = SEN on CN1-4.)
- **Formula:** pos = multiturn × R + within-turn (R = Pn212); machine = pos − stored-zero. Reverse mode (Pn000=n.□□□1): PE = −M×R + PO.
- Wiring: PSO/PSO CN1-48/49 → RS-422 line-receiver → UART. SEN=CN1-4, +24VIN=CN1-47. Encoder↔drive raw serial = CN2-5/6 (PS//PS).
- **Unresolved (image-only in manual):** whether the 8-digit within-turn field is raw 26-bit or Pn212-divided — confirm from the frame diagram or empirically. No turnkey Mesa/LinuxCNC decoder exists (forum 50063); build = MCU (RS-422→UART) parses PSO, feeds lcnc absolute at startup → immediate-home. Battery retains multiturn across power-off (prerequisite).

## Absolute position IS host-readable (PSO/SEN + UART) — the head-home goal is achievable
- **§6.12.4 "Reading the Position Data from the Absolute Encoder"** (this analog/pulse pack): a host
  CAN read the 26-bit multiturn absolute position. **PSO / /PSO = CN1-48/49** ("Absolute Encoder
  Position Output", serial); **SEN = CN1-4** ("Absolute Data Request Input"; or `Pn515=n.□□□7` =
  always output, no SEN). Line 15599: *"The host controller must have a reception circuit (e.g.,
  UART)."* At power-up the drive dumps initial position on **PAO/PBO** (already wired), then PSO streams it.
- **What ned has vs needs:** battery keeps multiturn alive (done); PAO/PBO quadrature → Mesa =
  INCREMENTAL feedback (done, `encoder.08/.09`). To get ABSOLUTE (home once, keep it): add **PSO+SEN
  wiring + a UART decoder of Yaskawa's absolute format** (Mesa serial port + LinuxCNC driver, or an
  external MCU translator). The plain hm2 quadrature counter does NOT decode it. This is a build, not impossible.
- Interim with zero new hardware: 200:1 worm self-locks → park at 0/0, LinuxCNC immediate-home
  (`HOME_SEARCH_VEL=0`) each session. Same practical result; only lacks the "did it move while off?" safety.

## Software position limits — the servopack does NOT have them
- This SGDXS **analog/pulse** SERVOPACK has **no settable position software limit**.
  No `Pn8xx` parameter, no "software limit setting" section, no ToC entry. The term
  "software limit" appears only twice, incidentally ("*if* software limits are
  enabled…", lines 9360 & 33606).
- Software limits belong to the **network / SigmaLINK-II positioning** variant, not
  this pulse-input drive. In step/dir (pulse) mode the drive is a pure follower.
- **Hardware-confirmed (don't re-litigate):** ned's drive is **SGDXS-2R8A00A** — the `A`
  interface = analog/pulse (`components.md:36`). The software position limit is CiA-402 object
  **607Dh** (min/max), which exists **only** on the EtherCAT/CANopen variant's object dictionary
  (manual SIEP C710812 04, not on hand). The analog/pulse pack has no object dictionary → **no
  607Dh, no Pn801/804/806**. `Fn008` (Reset Absolute Encoder) zeroes the encoder, but there is no
  drive-side limit to reference it to — enforce ±limits in the controller. The old "soft limit"
  message that got disabled was the **overtravel / not-pot** (P-OT/N-OT, `Pn50A=8101/Pn50B=6548`),
  not a position limit.
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

## Panel JOG (Fn002) — why it gives `no_oP` / "run" with no host
- `Pn50A.1 = 7` (n.8171) = **/S-ON always active** → manual line 8437: "keeps the servo ON and
  supplies power to the motor continuously." Symptom: panel shows **"run" even with LinuxCNC off**,
  and the panel can't take servo control → JOG blocked.
- **To jog from the panel, set `Pn50A.1 = 0` (n.8171 → n.8101)** = /S-ON follows CN1-40 (manual 8442).
  Host off → CN1-40 open → servo drops to **bb** → Fn002 can turn it on itself. (n.8101 is also the
  correct normal-op value — host drives /S-ON via 7I84 output-06/07 → CN1-40.)
- Fn002 also needs: **main power on** (L1/L2/L3, NOT just control L1C/L2C) and **no active alarm**.
- A host (LinuxCNC/mpgjog) actively asserting /S-ON + pulses also fights a panel jog (two masters).

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

## Alarm codes seen (panel shows `A.□□□`; the "A." can read like "E")
- **A.101 = Motor Overcurrent Detected** (Σ-XS servopack manual §13.2, line 31929). Servo trips → ignores
  step pulses → axis won't move even though the stepgen outputs steps + /S-ON is on. Manual causes, in order:
  (1) **main-circuit (U/V/W) motor cable miswired or faulty contact** ← check first; (2) short/ground fault
  across U/V/W in the cable, motor, or servopack; (3) heavy load applied while stopped or at low speed;
  (4) noise (FG wiring). A.100 = Overcurrent Detected (same causes + regen/DB).
- **A.C90 = Encoder Communications Error** (manual §13.2, line 33152) — CN2 encoder side. Top cause:
  **faulty contact in the encoder cable connector**; also noise. NOT the step/dir or motor-power path.
- Servo jogs from the panel (Fn002) but not from Mesa step pulses, with NO alarm = either the **step/dir
  pulse wiring** (7I85 → CN1 pulse input) isn't reaching the drive, OR (if wiring is identical to the
  working axis) a **parameter**: **Pn200.0 = 0** (Sign+pulse train, positive logic — matches Mesa step/dir;
  1=CW/CCW, 2–4=quadrature won't respond) and **Pn000.1 = 1** (position control). Manual line 12704.
  Diagnose by reading Pn000 + Pn200 in SigmaWin+ and matching the non-working axis to the working one.
- A Gr.1 alarm latches: **remove the cause, then reset** (manual line 2098); motion utility fns (JOG Fn002 etc.)
  require **no active alarm** (line 9001). A position-mode HOLD against the 200:1 worm is cause #3 ("heavy load
  at stop/low speed"), unlike a brief velocity spin.
- **`no_oP`** flashing on the panel = **write-protection set (Fn010)** or a **wrong-key press** (lines 36707, 37417).
  It is NOT itself an alarm — but a live alarm still blocks a panel run.
