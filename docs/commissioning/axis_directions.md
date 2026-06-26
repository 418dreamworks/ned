# Axis directions — commanded voltage vs physical motion

Reference for which physical direction each axis travels for a **positive** analog
velocity command (`+volts` in `tools/drive_move.sh` / `tools/drive_gantry.sh`,
i.e. a positive `pwmgen.NN.value`). Determined empirically by jogging open-loop and
watching the machine + encoder. These set the sign of `OUTPUT_SCALE` and the homing
search direction in `ned.ini`.

Hull convention for this machine: **X = STARBOARD** side, **W = PORT** side (the two
coupled gantry motors). See [ned LinuxCNC architecture] / ned.hal header.

| axis | pwmgen | encoder | +voltage moves it... | +voltage → encoder count | verified |
|------|--------|---------|----------------------|--------------------------|----------|
| Y    | 01     | enc.01  | **STARBOARD**        | counts UP (+)            | 2026-06-26 |
| X    | 00     | enc.00  | **AFT** (gantry aft) | counts UP (+)            | 2026-06-26 |
| Z    | 02     | enc.02  | **UP** (spindle up)  | TBD                      | 2026-06-26 |
| W    | 03     | enc.03  | **AFT** (tracks X)   | reads OK (X4 reseated)    | 2026-06-26 |
| A    | (step) | —       | TBD                  | TBD                      | — |

Notes:
- **Y, 2026-06-26:** positive voltage drives Y toward the **starboard** direction;
  encoder.01 counts up for +volts (confirmed: +1 V → +2276 counts/0.25 s,
  −V → counts down).
- **Z, 2026-06-26:** positive voltage drives the spindle **UP**. (encoder.02
  count sign for +volts not yet logged.)
- **X + W are the same gantry** (mechanically coupled). They must be commanded
  together (`tools/drive_gantry.sh`). 2026-06-26: ran `-volts 0.1` linked — **both
  motors physically moved AFT together (they track, no rack)**. Confirms shared
  signal drives both correctly and the motors are NOT mirror-mounted.
- **encoder.03 (W) was DEAD, now FIXED** (2026-06-26): during a linked gantry move
  W physically tracked X but `encoder.03.rawcounts` stayed flat 0 (total flatline,
  not erratic) — command side fine, encoder INPUT dead. **Cause: W's X4 feedback
  connector (DB15) was completely detached** at the cabinet. Reseating it brought
  e3 alive — hand-turning W now counts on encoder.03. Pure physical disconnect; no
  firmware issue. (An earlier reflash-mismatch theory here was WRONG — see below.)

## Encoder channel mapping — STRAIGHT, verified live (axis N = encoder N)

Verified 2026-06-26 by per-channel hand-test (`tools/watch_encoders.sh`): turn one
input, watch which `encoder.NN.rawcounts` moves. Every channel reads STRAIGHT, in
the obvious terminal order — exactly as `mesa_7i97t_wiring.md` lays it out:

| encoder | axis | 7I97 terminal | verified |
|---------|------|---------------|----------|
| e0 | X   | TB1 1–8   | ✓ (AOUT0 drove → e0) |
| e1 | Y   | TB1 9–16  | ✓ (AOUT1 drove → e1) |
| e2 | Z   | TB1 17–24 | ✓ |
| e3 | W   | TB2 1–8   | ✓ (hand-turn → e3, after reseating X4) |
| e4 | MPG | TB2 9–16  | ✓ (spin handwheel → e4) |
| e5 | —   | TB2 17–24 | spare |

⚠️ DISCARDED THEORY: an earlier version of this doc claimed the running
`7i97t_7i85sd` firmware read encoder ch3/ch4 off the **DB25** (so W and the MPG
were "mis-landed" and a reflash was needed). **That was wrong** — it came from
misreading the `mesaflash --readhmid` dump: the `MuxedQCount 3`/`4` lines on the
DB25 (P1/DB25 pins) are the 7I85 daughtercard's *counter instances*, NOT
`encoder.03`/`.04`. With `num_encoders=6`, hostmot2 takes the encoders from the
TB1/TB2 muxed counters 0/1/2 (two phases each → e0–e5), per the table above. The
DB25 counters are unused for feedback (the DB25 carries the A-axis STEP/DIR). The
firmware is correct and needs no reflash; the only fault was the detached W cable.
