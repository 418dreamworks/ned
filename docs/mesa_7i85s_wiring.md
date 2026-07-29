# 7I85S Wiring — step/dir to the stepper & head drives

The 7I85S is the step/dir + encoder daughtercard on the 7I97T's DB25 (P1). Card
details/ratings: see [`components.md`](components.md) → [cmp:mesa-7i85s]. In ned it
provides 4 step/dir outputs (stepgen 0–3); its 4 encoder inputs are **unused** (axis
encoders are on the 7I97 native TB1/TB2, see `ned-7i97-encoder-mapping`).

Pin functions below are from the **7I85S manual** (`docs/mesa/text/mesa_7i85s_manual.txt`).
Actual landed connections are marked with their source.

## Stepgen → terminal map (manual)

| stepgen | block | STEP− / STEP+ | DIR− / DIR+ | role |
|---|---|---|---|---|
| 00 | TB2 | 11 / 12 | 13 / 14 | workpiece rotary **drive 1** (B) — [cmp:rotary-stepper] |
| 01 | TB2 | 19 / 20 | 21 / 22 | workpiece rotary **drive 2** (B, twist) |
| 02 | TB1 | 3 / 4 | 5 / 6 | swivel-head **A** (Yaskawa, pulse) — [cmp:head-servo], future |
| 03 | TB1 | 11 / 12 | 13 / 14 | swivel-head **C** (Yaskawa, pulse) — future |

Note (manual): the "+" is the *slashed* signal (e.g. pin 12 = `/TX0,STEP0+`); match by
the STEP/DIR ± label. Outputs are 5 V differential (3.3–5 V at the drive opto — OK direct).

## Stepper drive connection (drives 1 & 2 — landed)

- STEP0 −/+ = TB2 11/12 → drive 1 PUL −/+;  DIR0 −/+ = TB2 13/14 → drive 1 DIR −/+
- STEP1 −/+ = TB2 19/20 → drive 2 PUL −/+;  DIR1 −/+ = TB2 21/22 → drive 2 DIR −/+
- ENA± → **left open** (drives enabled while powered; e-stop kills via the 70 V contactor).
- Cable: 8-conductor, aluminium-foil shielded, ± signals kept as pairs.

## ⚠ Cable shield landing — REMOVE IF ENCODERS ARE ADDED

**The step/dir cable shield is landed on 7I85S TB2 pin 18 (GND).**
Source: user decision, 2026-06-27. (TB2-18 = GND per the 7I85S manual TB2 pinout.)

**This is fine for now** — the 7I85S currently carries *only* the step/dir outputs, so
nothing else shares that ground and there are no other signals for the shield to
interfere with.

**REMOVE this shield→TB2-18 connection if/when encoders are wired onto the 7I85S.**
Once encoder channels are in use, their grounds/returns share the card, and a shield
tied to the card GND becomes a ground-loop / noise path between the encoder grounds and
the step/dir shield. At that point, move the shield to the cabinet PE bar (single-end)
instead.

## Head encoder feedback (A / C) → 7I85 encoder inputs (as-built 2026-07-28, VERIFIED)

Yaskawa servopack encoder outputs (PAO/PBO/PCO, RS-422 line drivers) → 7I85 **muxed** encoder inputs.
Needs **`num_encoders=10`** in the hm2_eth config (was 6) to expose the 7I85 counters (MuxedQCount 3/4
via the DB25). Hand-tested clean 2026-07-28: both ramp ~6800 cnt / (−10 rpm × 5 s) ≈ **8190 cnt/motor-rev**.

| Axis | 7I85 landing | enc ch | LinuxCNC pin |
|---|---|---|---|
| **A** (tilt) | TB2 pins **1–8** | ch 3 | **`encoder.09`** |
| **C** (spin) | TB3 pins **17–24** | ch 2 | **`encoder.08`** |

Per-conductor landing (both drives; colored = +, white = −):

| Color | CN1 | Signal | A → 7I85 TB2 (ch3) | C → 7I85 TB3 (ch2) | Role |
|---|---|---|---|---|---|
| blue / blue-white | 33/34 | PAO / /PAO | TB2-1 / -2 | TB3-17 / -18 | incremental (live) |
| brown / brown-white | 35/36 | PBO / /PBO | TB2-4 / -5 | TB3-20 / -21 | incremental (live) |
| green / green-white | 19/20 | PCO / /PCO | TB2-7 / -8 (IDX3) | TB3-23 / -24 (IDX2) | index (wired, not enabled) |
| SG wire | 1 | SG | TB2-3 (GND) | TB3-19 (GND) | ground ref |

- Incremental A/B (blue+brown) → **A = `encoder.09`, C = `encoder.08`**. Two mux-phases of MuxedQCount 4; ch↔pin order is hand-tested, not obvious.
- **Index (PCO, green)** on the IDX inputs (green = PCO+ → IDX+; green-white = /PCO → /IDX). Wired and available but **not enabled** in the config (no home switch → not needed); optional future index-reset. Harmless.
- **Absolute (PSO, orange pair, CN1-48/49) does NOT land on the 7I85 encoder block** — those inputs are 2:1 muxed, useless for a continuous UART (`7i97t_7i85sd.pin`: A-IDX & C-IDX both = FPGA I/O 50). Instead PSO routes through an **R4 DPDT mux** (poles 3 & 4: COM→Mesa TB1-19/20, NC = C drive, NO = A drive; coil = 7I84 OUTPUT5 — full pole/color map in `relays.md` → R4) into the 7I85's only free non-muxed RS-422 receiver = **sserial RXData1 = TB1-19 (SRX+) / TB1-20 (SRX−)** (I/O 34; `mesa_7i85s_manual.txt:326-327`). Mux COMs: D4 (blue) → TB1-19, D3 (red) → TB1-20. **PktUART now live on the card:** bitfile `firmware/7i97t/hostmot2/7i97t_7i85sd_pktuart.bin` (stock 7i97t_7i85sd + a PktUART on I/O 34/35; see `firmware/7i97t/hostmot2/pktuart_build/BUILD_NOTES.md`). `ned.hal` sets `num_pktuarts=1` → instance `hm2_7i97.0.pktuart.0`, **RX on I/O 34**. Still needed to actually home: the PSO-read HAL comp (`hm2_pktuart_config`/`_read` @ 9600 8N1, mask parity) + drive param `Pn515=7` (continuous no-SEN PSO) + the R4-mux HAL; read once at boot (A vs C via the R4 coil). Protocol/params: `docs/servo/yaskawa_params_quickref.md`.
- RS-422 jumpers (all down): ch3 = W8/W10/W12, ch2 = W1/W2/W4. +5 V (TB2-6 / TB3-22) open (Yaskawa self-powered).
- **⚠ TEMPORARY HARNESS** (mixed gauge) — re-run with gauge-appropriate cable when the machine is next moved.

## Head Yaskawa pulse reference (A & C) — reserved (inert/future, not landed)

stepgen 02/03 → the Yaskawa CN1 pulse-reference pins. The 24 V sequence I/O (/S-ON, ALM±,
+24VIN) for these drives is on the **7I84** (`mesa_7i84u_wiring.md` → TB3 section).

> Full servo-side wiring (both drives, all connections) → **`yaskawa_servo_wiring.md`** (source
> of truth). This section is the 7I85 card-centric slice.

**A and C are two separate servopacks**, each with its own 50-pin CN1. The CN1 pin numbers
are identical on both by design (both have CN1-7 = PULS, etc.) — the "CN1" column below means
*that axis's own connector* (A → Servopack-A CN1, C → Servopack-C CN1).

| Axis | stepgen | 7I85 pin | Signal | dir | Yaskawa CN1 |
|---|---|---|---|---|---|
| A (tilt) | 02 | TB1-3 (STEP−) | PULS− | → | CN1-7 (PULS) |
| A (tilt) | 02 | TB1-4 (STEP+) | PULS+ | → | CN1-8 (/PULS) |
| A (tilt) | 02 | TB1-5 (DIR−) | SIGN− | → | CN1-11 (SIGN) |
| A (tilt) | 02 | TB1-6 (DIR+) | SIGN+ | → | CN1-12 (/SIGN) |
| C (spin) | 03 | TB1-11 (STEP−) | PULS− | → | CN1-7 (PULS) |
| C (spin) | 03 | TB1-12 (STEP+) | PULS+ | → | CN1-8 (/PULS) |
| C (spin) | 03 | TB1-13 (DIR−) | SIGN− | → | CN1-11 (SIGN) |
| C (spin) | 03 | TB1-14 (DIR+) | SIGN+ | → | CN1-12 (/SIGN) |

Sources: 7I85 pins from the 7I85S manual stepgen→terminal map (above); CN1-7/8/11/12 =
Yaskawa CN1 PULS±/SIGN±. The +/− ↔ PULS//PULS **polarity is assumed** — swap the pair if
motion comes out reversed (not confirmed in notes).

### As-built — pulse cable color map (2-pair shielded, white = −)

Cable: shielded, 2 twisted pairs (orange pair = STEP/PULS, blue pair = DIR/SIGN), pairs not
individually shielded. Convention: **colored = +, white = −**. Same on both drives (A & C),
each on its own CN1.

| Wire | Signal | 7I85 TB1 (A / C) | CN1 |
|---|---|---|---|
| orange | STEP+ | 4 / 12 | **CN1-7** (PULS) |
| orange-white | STEP− | 3 / 11 | **CN1-8** (/PULS) |
| blue | DIR+ | 6 / 14 | **CN1-11** (SIGN) |
| blue-white | DIR− | 5 / 13 | **CN1-12** (/SIGN) |

**CN1 end = soldered (committed).** Any polarity fix (wrong direction / backward count) is done
at the **7I85 screw-terminal end**, not CN1.

**Shield: landed at the Yaskawa/CN1 end ONLY** — via the molded-connector grounding band (360°
bond). **7I85/cabinet end left floating** (single-ended, no ground loop). NB: this differs from
the generic `to_buy.md` "7I85-end" convention — the head pulse cable is Yaskawa-end.
