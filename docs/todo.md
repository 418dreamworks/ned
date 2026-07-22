# To do

## B-axis steppers — ned.hal wrong (2 SEPARATE joints, not 1)
- ✓ CONFIRMED 2026-07-09: BOTH drives + motors work **independently** — stepgen.00 (TB2 11-14) turns motor 1, stepgen.01 (TB2 19-22) turns motor 2. position-fb ramps on both; each turns its own motor. Mesa→both drives→both motors all good. No hardware fault — the earlier "only one turned" was the bench file commanding only stepgen.00.
- ⚠ `ned.hal` §8 is WRONG: drives only stepgen.00 for joint 4 and calls the pair "one stepgen / one reversed in copper". They are **TWO SEPARATE axes** — separate mechanically + electrically, only software-linked.
- Fix ned.hal: give **each stepper its own joint** (stepgen.00 and stepgen.01), not one joint driving both. stepgen.01 = "twist" per `mesa_7i85s_wiring.md:16` — axis letter + kinematics slot TBD.
- ✓ DONE 2026-07-09: set up as B gantry (joints 4 & 7, duplicate B in coordinates), joint 7 counter-rotates via negative SCALE. ned.ini done; ned.hal joint-7 wiring + §8 stepgen.01 done.
- **Match the two B steppers (open — deferred):** they turn different amounts for the same command; **user determined it's NOT slipping — a fixed manufacturing/ratio variance** (2026-07-09). **Both drives confirmed at 400 pulses/rev + no slip → the motor shafts turn identically; the variance is downstream in the worm/wheel reduction (gearing), not motor/drive.** Fix = per-joint `SCALE` trim so both rotate identically for the same B command (works at all speeds/positions since it's a constant ratio). Method: command a known move (e.g. 10 motor revs) on each, measure each output's actual travel, ratio = the correction; multiply the short joint's `SCALE` by it. One number in `[JOINT_4]`/`[JOINT_7]SCALE` — no new HAL. (Only revisit as slip if the offset ever changes with load/speed.)

## Head servo → LinuxCNC  (drive side done; HAL remains)
- HAL: bring up AB/C axes (stepgen 02/03) — replace loopbacks, add /S-ON + ALM, un-INERT.
- 5axiskins: unresolved — stock 5axiskins is B/C bridge mill, head is AB/C.
- AB/C axis limits: set real values (placeholders now).
- Pn002 → absolute (n.□0□□), confirm A.810 clears (batteries now wired).

## Spindle over-temp
- Now: NC thermostat → `*39` → 7I97 IN14, but `sig-spindle-overtemp` is **DANGLING** in ned.hal (read only, wired to nothing) → **no working over-temp protection yet** (`ned.hal:456`, `:261`).
- DECIDED 2026-07-09: wire the NC thermostat **in series with the 3-button e-stop chain** (`*1→*3→*5→*6`, `screw_terminals.md:64`) → opens hot → full hardware kill, fail-safe. Limits are NOT in that chain (user-confirmed), so cause = **"3 buttons all good + tripped → spindle over-temp"** by elimination.
- DECIDED 2026-07-09 (deferred): use **R4 to duplicate the thermostat signal**. Thermostat drives R4's coil (energized cool, drops hot / on any failure = fail-safe); one R4 pole (NO) in the e-stop chain = the kill, a second R4 pole → a Mesa input = positive **"spindle over-temp"** annunciation. So the kill and the cause-signal come from the one thermostat.
  - R4 current state (`relays.md:179-187`): 4-pole spare, **coil on the `*7`/R5D2/R3C2 node** (energizes with R3 on drive-enable), all NO contacts EMPTY. → **must MOVE R4's coil off `*7`** to be driven by the thermostat instead.
  - A chiller with a temp sensor (if bought) is complementary **loop monitoring** — reads coolant, not the stator winding — NOT a substitute for the thermostat protection.

## HQD spindle ATC sensors
- Wiring DONE (as-built HQD 2026-07-09): S1 tool-lock → input-30/`*69`, S2 tool-release → input-31/`*70`, S3 shaft-stop → input-29/`*68`. All PNP-NO (brown +24, black sig, blue 0V).
- ✓ S3 shaft-stop (input-29) VERIFIED 2026-07-09 — toggles TRUE/FALSE on hand-rotation.
- TODO — confirm **S1 tool-lock (input-30)**: seat a tool holder in the taper (no air) → expect TRUE. (FALSE when empty is normal — spring over-travels the clamp detent; not a drawbar-position sensor like the Colombo.)
- TODO — confirm **S2 tool-release (input-31)**: apply unclamp air (port B, 10.5–11.5 bar) → expect TRUE. Only signal leg still unproven end-to-end.
- Interlocks (later): S3 must confirm stopped before unclamp; S1 must confirm locked before spin.

## Docs — consistency sweep (paused mid-way)
- components.md: AB rename + add encoder battery (cable 92, BAT±).
- field_devices.md: add cable-92 battery conductors (*56–*59).
- to_buy.md §4: encoder = 4-cond STP (battery on cable 92, done).
- AB rename: INDEX, mesa_7i85s/7i84u, relays.

## Safety
- ⚠ **SWAP R11 to a NORMALLY-OPEN contactor.** Currently NC (bought by mistake) → head servos + 70 V brick powered by DEFAULT; e-stop does NOT cut head/brick power via R11. Fail-safe is inverted until swapped (`relays.md` R11).

## Misc
- 5 V power brick: ratings TBD (components.md).
- CN8 safety jumper: confirm installed.
