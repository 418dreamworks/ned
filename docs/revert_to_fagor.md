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

## 3. Tool-changer / drawbar sensor inputs (`*68` / `*69` / `*70`)
**Change:** the Fagor tool-changer/drawbar sensors were replaced by the HQD head's
sensors, and the X10 cable's far end moved off the Fagor CNC (X10 connector) onto the
Mesa **7I84U TB2**. This is **NOT a 1:1 swap** — the sensor set itself changed, so a
revert restores different physical sensors, not just re-landed wires.

| Terminal (X10 conductor) | Fagor-original | Current (LinuxCNC / HQD) |
|---|---|---|
| `*68` (X10/pin 34) | `ITOOLIN I36` — rack-position sensor. Cable 92-2 RED → BIGGREEN **grey**; +24 V on BIGGREEN purple, 0 V on green. (Fagor PIM symbol "ITOOLIN/tool-present" was OEM-repurposed as rack-position.) | 7I84U TB2 **INPUT29** — HQD **shaft-stopped** S3 (field lead blue → BIGGREEN grey); purple/green now spare |
| `*69` (X10/pin 35) | `IDRAWUP I38` — drawbar-UP sensor. Cable 30-2 RED → BIGGREEN **red** | 7I84U TB2 **INPUT30** — HQD **tool-locked** S1 (field lead red → BIGGREEN red) |
| `*70` (X10/pin 36) | `IDRAWDN I40` — drawbar-DOWN sensor. Cable 30-2 BROWN → BIGGREEN **brown** | 7I84U TB2 **INPUT31** — HQD **tool-released** S2 (field lead yellow → BIGGREEN brown) |

**Revert:** re-land the X10 cable (pins 34/35/36) on the Fagor CNC X10 connector, and
restore the Fagor field sensors (rack-position + drawbar up/down) in place of the HQD
sensors. Drawbar-pair sensor +24 V is on cable 30 RED → `*76`; the rack sensor's
supply/return were BIGGREEN purple/green (now spare). Because the Fagor sensor set
(rack + drawbar up/down) differs from the HQD set (shaft-stopped + tool-locked +
tool-released), this is not a wire-for-wire reversal — the field sensors change too.
