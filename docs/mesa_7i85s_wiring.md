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

## Head Yaskawa pulse reference (A & C) — reserved (inert/future, not landed)

stepgen 02/03 → the Yaskawa CN1 pulse-reference pins. The 24 V sequence I/O (/S-ON, ALM±,
+24VIN) for these drives is on the **7I84** (`mesa_7i84u_wiring.md` → TB3 section).

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
motion comes out reversed (not confirmed in notes). Reserved, wired when the head is
commissioned.
