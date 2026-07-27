# Reverting the ned cabinet to Fagor 8055

Physical cabinet wiring changes made for the LinuxCNC retrofit that deviate from the
original Fagor 8055 wiring, and how to undo each. (Fagor-decoded parameters and the
removed spindle drive live in their own records — this file is only the cabinet deltas.)

## 1. Spindle over-temp thermostat in the e-stop chain
**Change:** the spindle over-temp thermostat was inserted in series at the end of the
e-stop chain. The LHS e-stop's other NC-contact wire was moved off `*6` onto `*39`, and
`*6`-left is now fed by a yellow jumper from `*67` (the thermostat's output):
`LHS e-stop → *39 → thermostat NC → *67 → yellow jumper → *6`
(`docs/tracing/screw_terminals.md`, `*5`/`*6`/`*39`/`*67`). A hot thermostat opens the
chain → `*6` drops → spindle killed like any e-stop.

**Revert:** move the LHS e-stop wire from `*39` back onto `*6` (the Fagor original —
`screw_terminals.md` `*6` "Left side (FAGOR original)"), remove the `*67`→`*6` yellow
jumper, and take the thermostat out of the chain. The `*39` diagnostic tap
(`sig-spindle-overtemp`, 7I97 IN14) then goes dead.

## 2. Rotary (B) 70 V-brick power via spare relay R4
**Change:** the 70 V stepper-brick mains was moved off R11 pole 4 onto the spare relay
R4 so the noisy B rotary steppers can be powered separately: `110 V → R4A2`,
`R4D2 → brick`. R4's coil (`R4C2`) was lifted off the `*7`/R5D2 drive-enable node and is
now driven by Mesa 7I84 **OUTPUT5 (TB3-22)** via HAL `sig-rotary-power`
(`docs/tracing/relays.md`, R4).

**Revert: Fagor does not use R4** — it was a Fagor-era spare. Just remove the retrofit
wiring from R4 (110 V off `R4A2`, brick off `R4D2`, Mesa off `R4C2`) and R4 returns to
its Fagor state (unused). Note the 70 V brick, R11, and the B rotary steppers are
themselves retrofit additions the Fagor machine never had (`relays.md`, R11) — a full
Fagor revert removes all of them.
