# Cabinet Relays (`R<n>` series)

Master list of every relay in the cabinet, with terminal-by-terminal wiring for each. See `README.md` for conventions (A = NO, B = NC, C = coil, D = COM; columns 1, 2).

The cabinet has ~10 relays. Each section below documents one, terminal by terminal.

**Coil suppression (cabinet-wide):** **every** relay and contactor coil has an **external flyback (freewheeling) diode** across it, **cathode on the +24 V side** (per the R1 example at "External flyback diode" below, and confirmed by field observation across all relays, 2026-07-08). Consequence: **every coil circuit is polarized** — the +24 V feed must land on the diode's cathode terminal, or the diode shorts the supply. Any *new* coil added to this cabinet (e.g. the head/stepper contactor, `components.md` [cmp:head-contactor]) should follow the same pattern: coil low side → 0 V, high side → its +24 V enable node, flyback **cathode on the +24 V side**, diode rated for the coil current (a 1N400x-class rectifier for a contactor coil). *Note: individual entries below do not all restate this — only R1's diode was traced line-by-line; this cabinet-wide note supersedes those gaps.*

---

## R0 — Analog Drive Power Contactor (Deltrol)

**R0 is a contactor, not a multi-pole relay.** It uses a different terminal convention than R1-R10: only **4 terminals total**, where **A = signal (coil) side** and **B = load (switched contact) side**. With all 4 terminals traced, R0 is fully defined.

| Terminal | Side | Wire / connection | Status |
|---|---|---|---|
| R0A1 | signal (coil) | → GND (0 V) | ✓ |
| R0A2 | signal (coil) | → `*7` | ✓ |
| R0B1 | load contact | → power to Analog Drive (output to the drive) | ✓ |
| R0B2 | load contact | → source power from transformer (input from supply) | ✓ |

**Function**: R0 is the main power contactor for the **Analog Drive** (SDSM servo chassis). When the coil (A1-A2) is energized — i.e., when `*7` has +24 V relative to GND — R0's load contact (B1-B2) switches state, gating the transformer power to the drive.

**State logic** (NO load contact — standard fail-safe contactor):
- Coil **energized** (`*7` = +24 V, normal) → B1-B2 closes → transformer power flows to drive → drive has power.
- Coil **de-energized** (`*7` = 0 V, emergency) → B1-B2 opens → drive has no power → drive cannot run.

Fail-safe: any failure that drops `*7` (broken wire, blown fuse on coil supply, contactor coil burnout) cuts power to the drive. To confirm the contact is NO (not NC), test continuity between B1 and B2 with the coil de-energized — should be open. Or read the contactor's model number off the body and check the datasheet.

R0 works in parallel with R3/R4: when `*7` loses voltage, R0 cuts the power AND R3/R4 close the RUN/STOP signal — two independent paths to stop each servo drive.

---

## R11 — Head-servo + 70 V-brick power contactor  (4-pole, NORMALLY-OPEN)

24 VDC coil on `*7` (drive-enable node), same as R0. **Flyback diode across A1–A2**
(band/cathode → A2/`*7`, anode → A1/GND).

Fail-safe: energize `*7` → poles close → head servopack gets power (70 V brick mains moved to R4);
drop `*7` (e-stop / no drive-enable) → poles open → power cut.

**Retrofit addition — NOT part of the original Fagor cabinet.** R11 was added for the
LinuxCNC head servos + 70 V stepper brick (the Fagor machine had neither); it is the only
relay not in the original cabinet.

| Terminal | Wire | Status |
|---|---|---|
| R11A2 (coil +) | → `*7` (drive-enable node = R5D2 = R0's coil node) | ✓ |
| R11A1 (coil −) | → GND (0 V) | ✓ |
| Poles 1–3 | L1/L2/L3 supply → head servopack L1/L2/L3 ([cmp:head-servo], A & C) | ✓ |
| Pole 4 | **unused** — brick mains moved to R4 (see R4) | ✓ |

Cross-refs: R0 (same enable node), R5 (drive-enable gate), `components.md` [cmp:head-contactor], [cmp:head-servo], [cmp:stepper-brick].

---

## R1 — VFD "running" feedback relay

Closes its contacts when the VFD is running, signaling the CNC that the spindle is spinning.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R1C1 | one coil terminal | → GND (0 V). Mollom Y1 polarity is handled by the interposing relay (`mollom_g75_vfd.md`). | ✓ |
| R1C2 | other coil terminal | Blue wire (unlabelled) → Mollom Y1 (as-built) [Fagor: VG5/9] | ✓ |
| R1A1 | NO contact, col 1 | Black wire to grease pump's hot terminal. (The pump's neutral terminal returns to `*77` — neutral side is NOT on R1.) See "Grease pump path" note below. | ✓ user-observed |
| R1A2 | NO contact, col 2 | → spindle use counter (hour meter — tracks accumulated spindle-on time). When R1 energizes (spindle running), R1A2 closes onto R1D2 (+24 V) → counter receives +24 V and increments. | ✓ |
| R1A3 | NO contact, col 3 | → `*36` → Fagor X9/pin 33 (`IROTATE`, spindle rotating feedback). When R1 energizes, R1A3 closes onto R1D3 (+24 V) → CNC reads "spindle is actually rotating." | ✓ |
| R1A4 | NO contact, col 4 | **EMPTY** — confirmed unwired | ✓ |
| R1B1, R1B2, R1B3, R1B4 | NC contacts | **EMPTY** — confirmed unwired | ✓ |
| R1D1 | COM, col 1 | AC hot supply for grease pump — sourced **direct from the cabinet transformer secondary** (so when R1A1-D1 closes, AC hot reaches the pump). | ✓ |
| R1D2 | COM, col 2 | → +24 V common (bonded `*71`-`*76` bus). When R1 energizes, R1A2 sources +24 V to its (TBD) destination. | ✓ |
| R1D3 | COM, col 3 | → +24 V common (bonded `*71`-`*76` bus). When R1 energizes, R1A3 sources +24 V to `*36` (and from there to wherever `*36`'s right side goes). | ✓ |
| R1D4 | COM, col 4 | **EMPTY** — confirmed unwired | ✓ |

**Coil drive**: R1C2 (high side) ← blue wire ← the Mollom running-output interposer (Y1 sinks → interposer NO sources +24 V); R1C1 (low side) → 0 V. Flyback diode across R1C1↔R1C2, cathode on R1C2 (+24 V side).

---

## R2 — E-stop-driven VFD enable relay

R2's coil is energized by the e-stop chain.

Direct connections:
- R2C2 ↔ `*6` (wired)
- R2C1 ↔ GND (wired)

Behavior: when all three e-stops are released, `*6` = +24 V → R2C2 sits at +24 V relative to R2C1 (at 0 V) → R2's coil sees 24 V across it → R2 energizes. When any e-stop is pressed, the chain breaks → `*6` = 0 V → no voltage across R2's coil → R2 drops out → VFD external-fault input asserts → VFD coasts spindle to stop.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R2C1 | coil low side | → GND (0 V) | ✓ |
| R2C2 | coil high side | → `*6` (end of e-stop daisy chain) → +24 V when chain intact | ✓ |
| R2A1, R2B1, R2D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R2A2 | NO col 2 | Orange wire labelled "3" → Mollom S4 (as-built) [Fagor: VG5/4] | ✓ |
| R2B2 | NC col 2 | Orange wire labelled "2" → Mollom S3 (as-built) [Fagor: VG5/3] | ✓ |
| R2D2 | COM col 2 | Standalone orange wire labelled "1" → Mollom COM (as-built) [Fagor: VG5/11] | ✓ |
| R2A3, R2B3, R2D3 | pole 3 | **EMPTY** — confirmed unwired | ✓ |
| R2A4, R2B4, R2D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

**Operating logic**:
- **E-stops released (chain intact, R2 energised)**: R2B2 NC opens → S3 disconnects from COM → VFD external fault cleared. R2A2 NO closes → S4 connects to COM → VFD fault reset asserted. **VFD enabled to run.**
- **E-stop pressed (chain broken, R2 drops out)**: R2B2 NC closes → S3 shorts to COM → VFD reads external fault → **VFD coasts to stop.** R2A2 NO opens → fault reset no longer asserted.

The same chain also drives Fagor X9/pin 2 (`/EMERINP`), so the CNC firmware reacts in parallel. Two independent stop mechanisms from one chain.

---

## R6 — Forward Run interposing relay

When the Fagor's SPIN-CW PLC output asserts, this relay closes its NO contact to command the VFD forward.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R6C1 | coil low side | → GND (0 V) | ✓ |
| R6C2 | coil high side | Brown wire ← `*40` ← red wire labelled "05" ← **Fagor X10/pin3 (SPIN-CW O3)** | ✓ |
| R6A1, R6B1, R6D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R6A2 | NO col 2 | Brown wire (unlabelled) → Mollom S1 (as-built) [Fagor: VG5/1] | ✓ |
| R6B2 | NC col 2 | **EMPTY** — confirmed unwired | ✓ |
| R6D2 | COM col 2 | Part of the crimped orange pair (this is the orange labelled "2") → Mollom COM (as-built) [Fagor: VG5/11] | ✓ |
| R6A3, R6B3, R6D3 | pole 3 | **EMPTY** — confirmed unwired | ✓ |
| R6A4, R6B4, R6D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

**Coil drive verified**:
- R6C2 is connected (via brown wire) to `*40`, which on its other side is connected (via the red wire labelled "05") to Fagor X10/pin 3 (`SPIN-CW O3`).
- R6C1 is connected to GND (0 V).

When SPIN-CW is asserted (+24 V at X10/pin 3), R6C2 sees +24 V relative to R6C1 → coil energizes → R6's NO contact closes → forward run command reaches VFD.

---

## R7 — Reverse Run interposing relay

R7 gates the reverse-run command into the VFD. Coil ← `*41` ← Fagor X10/pin4 (SPIN-CCW O5); NO contact R7A2 → Mollom S2 (reverse run).

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R7C1 | coil low side | → GND (0 V) | ✓ |
| R7C2 | coil high side | ORANGE wire → `*41` → ORANGE wire → Fagor X10/pin 4 (`SPIN-CCW O5`). Same wire color through the splice. | ✓ |
| R7A1, R7B1, R7D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R7A2 | NO col 2 | Red wire (unlabelled, small gauge — distinct from cable-7 reds) → Mollom S2 (as-built) [Fagor: VG5/2] | ✓ |
| R7B2 | NC col 2 | **EMPTY** — confirmed unwired | ✓ |
| R7D2 | COM col 2 | Part of the crimped orange pair (this is the orange labelled "1") → Mollom COM (as-built) [Fagor: VG5/11] | ✓ |
| R7A3, R7B3, R7D3 | pole 3 | **EMPTY** — confirmed unwired | ✓ |
| R7A4, R7B4, R7D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

---

## R3 — Servo-drive RUN/STOP interlock (4-pole)

Coil driven from the R3/R4/R5 node. **R3 has 4 poles** (4 NC contacts, 4 COMs, plus 4 NO contacts) — extending the column convention beyond 2 for relays of this size. Each pole gates the RUN/STOP signal for one axis drive.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R3C1 | coil low side | → GND (0 V) | ✓ |
| R3C2 | coil high side | Same electrical node as `*7`, R5D2, R4C2 (all directly wired together). Node is at +24 V when R5 is energized AND `*6` carries +24 V — that's when R3's coil sees voltage. | ✓ |
| R3B1 + R3D1 | NC pole 1 | RUN/STOP signal for **Drive W** (passes through this NC contact in series) | ✓ |
| R3B2 + R3D2 | NC pole 2 | RUN/STOP signal for **Drive Y** | ✓ |
| R3B3 + R3D3 | NC pole 3 | RUN/STOP signal for **Drive Z** | ✓ |
| R3B4 + R3D4 | NC pole 4 | RUN/STOP signal for **Drive X** | ✓ |
| R3A1, R3A2, R3A3, R3A4 | NO contacts | **EMPTY** — confirmed unwired | ✓ |

**Function**: each axis drive (X, Y, Z, W) has its RUN/STOP signal line wired through one of R3's NC contacts in series. The drive's RUN/STOP input is the "stop input" — **a continuous connection asserts STOP, breaking the line allows RUN**.

**Operating states** (fail-safe architecture):

| R3 coil state | NC contacts | RUN/STOP line at drive | Drives |
|---|---|---|---|
| **Energized** (normal — `*7` at +24 V) | All 4 NC contacts OPEN | Line broken — no STOP signal asserted | **Drives RUN** |
| **De-energized** (emergency — `*7` lost +24 V) | All 4 NC contacts CLOSED | Line continuous — STOP signal asserted | **Drives STOP** |

So R3 must be **actively energized** for drives to run. Any failure that drops `*7` (broken wire, e-stop pressed, CNC fault, R5 dropping out) de-energizes R3 → all 4 NC contacts close → STOP signal asserted on all 4 drives simultaneously → drives stop.

This is fail-safe by construction: R3 cannot end up "stuck running" from a wire break or loss-of-signal. The drive-run state requires an active +24 V on `*7` (via the e-stop chain + R5 routing), which can only happen when both the e-stop chain is intact AND R5 is held energized.

---

## R4 — Rotary (B) 70 V stepper-brick power switch  (repurposed Fagor spare)

R4 is a 4-pole relay (same type as R1, R3, R5–R10), a Fagor-era spare now repurposed to gate the 70 V stepper-brick mains so the noisy B rotary steppers can be powered separately from the rest of the machine. NO pole A2→D2 carries the brick mains (moved here off R11 pole 4); the coil is driven by Mesa 7I84 **OUTPUT5 (TB3-22, sourcing)** via HAL `sig-rotary-power` (= drive-enable AND operator request). **Fagor did not use R4.**

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R4C1 | coil low side | → GND (0 V) | ✓ |
| R4C2 | coil high side | → Mesa 7I84 **OUTPUT5 (TB3-22)**, sourcing. Energizes when HAL asserts `sig-rotary-power`. Lifted off the `*7`/R5D2 node. | ✓ |
| R4A2 | NO contact | ← 110 V brick mains (from R11 pole 4). A1/A3/A4 empty. | ✓ |
| R4B1, R4B2, R4B3, R4B4 | NC contacts | **EMPTY** — confirmed unwired | ✓ |
| R4D2 | COM | → 70 V brick ([cmp:stepper-brick] L1). D1/D3/D4 empty. | ✓ |

---

## R5 — Servo-drive master power-gating relay

R5 is the master switch in the servo-drive enable chain. Its column-2 pole selects which voltage source connects to R5D2 (which is the same electrical node as `*7`, R3C2, and R4C2):

- When R5's coil is **energized** (CNC says drives may run): R5A2-R5D2 closes → R5D2 is connected to `*6` (e-stop chain, +24 V when chain intact) → `*7` = +24 V → R0/R3/R4 energize → drives can run.
- When R5's coil is **de-energized**: R5B2-R5D2 closes → R5D2 is connected to R5B2 (TBD — presumably 0 V or floating) → `*7` ≈ 0 V → R0/R3/R4 drop → drives stop.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R5C1 | coil low side | → GND (0 V) | ✓ |
| R5C2 | coil high side | → `*8` → brown wire → Fagor X10/pin 2 (`/EMEROUT`). R5 energizes when CNC says "drives may run" (/EMEROUT high). | ✓ |
| R5A1, R5B1, R5D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R5A2 | NO col 2 | → `*6` (end of e-stop chain, +24 V when chain intact). When R5 energized, R5A2 closes to R5D2 → +24 V from e-stop chain flows to `*7` → R0/R3/R4 energize → drives can run. | ✓ |
| R5B2 | NC col 2 | **EMPTY** — confirmed unwired | ✓ |
| R5D2 | COM col 2 | → shared node with `*7`, R3C2, R4C2 | ✓ |
| R5A3, R5B3, R5D3 | pole 3 | **EMPTY** — confirmed unwired | ✓ |
| R5A4, R5B4, R5D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

**Network topology so far** (verified):
```
*7 ────┬──── R0A2 (R0's NO contact)
        ├──── R5D2 (R5's COM)
        ├──── R3C2 (R3's coil high side)
        └──── R4C2 (R4's coil high side)
```

When voltage appears at this node (from R5's switching action — exactly which terminal feeds it depends on R5's state and what's on R5A2 vs R5B2), R3 and R4 both energize together, and R0 sees +24 V on its A2 contact terminal.

---

## R8 — Unused (OEM leftover)

R8's coil is wired to Fagor X10/pin 5 (PIM `LATCH1 O7`, "unlabeled OEM function") via the `*42` splice, but R8's outputs are not connected to any useful load on this machine: R8A2 lands on `*86`, which dead-ends on the field side. No other R8 contacts are wired. R8 is effectively dead — leftover from the OEM template.

Note: R8D3 is on the **110 V AC line** rather than the +24 V common — unusual for a 4-pole DC interposing relay. Suggests the OEM intended pole 3 to switch some AC-powered load (small motor, lamp, etc.) but never finished the wiring.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R8C1 | coil low side | → GND (0 V) | ✓ |
| R8C2 | coil high side | ORANGE wire → `*42` → YELLOW wire → Fagor X10/pin 5 (`LATCH1 O7`) | ✓ |
| R8A2 | NO col 2 | → `*86` (dead-ends on field side — no load) | ✓ |
| R8D2 | COM col 2 | → +24 V common (bonded `*71`-`*76` bus) | ✓ |
| R8D3 | COM col 3 | → `*E` (110 V AC line bus) | ✓ |
| R8A1, R8A3, R8A4, R8B1–B4, R8D1, R8D4 | other contacts | not wired | ✓ (verified as unwired) |

---

## R10 — Tool-probe interposing relay

R10 acts as an interposing relay between the tool probe (at the spindle) and the Fagor TOOLLEN input. Its coil is wired between +24 V (R10C2) and the probe signal node `*87` (R10C1); it energizes only when the tool touches the probe surface and current flows through the coil to chassis ground via the spindle. The NO contact (R10A2 ↔ R10D2) then sources a clean +24 V to the Fagor input.

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R10C1 | coil terminal 1 | → `*87` (then cable 04 BLK → tool probe surface). Idle: +24 V (no current through coil); Touch: ~0 V (current flows through coil to chassis ground via spindle). | ✓ |
| R10C2 | coil terminal 2 | → +24 V common (bonded `*71`-`*76` bus). The high-side reference for the coil. | ✓ |
| R10A1, R10B1, R10D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R10A2 | NO col 2 | WHITE wire → `*54` → Fagor X10/pin 17 (`TOOLLEN I39`). Closes onto R10D2 (+24 V) when R10 is energized → +24 V appears at Fagor input. | ✓ |
| R10B2 | NC col 2 | **EMPTY** — confirmed unwired | ✓ |
| R10D2 | COM col 2 | → +24 V common (bonded `*71`-`*76` bus). The clean +24 V source that R10A2 connects to when R10 picks up. | ✓ |
| R10A3, R10B3, R10D3 | pole 3 | **EMPTY** — confirmed unwired | ✓ |
| R10A4, R10B4, R10D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

**C1/C2 convention note**: every other relay in the cabinet uses C1 = GND, C2 = high side. R10 breaks the C1 = GND part: C1 carries the probe signal node, not GND. C2 = +24 V is consistent with the high-side convention. The C1 = GND pattern is a pattern, not a rule, and this is the first relay where it doesn't hold.

---

## R9 — Chip blow-off interposing relay (verified function)

R9 is the interposing relay for the **chip blow-off air-blast solenoid**. Same interposer pattern as R6 (SPIN-CW) and R10 (tool probe): Fagor PLC output drives the coil, the NO contact sources +24 V common out to the field-side solenoid.

The Fagor PLC output is `BITCOOL O2` at X10/pin 21. PIM calls it "Bit cool" (a generic name covering air-based bit cooling, which also clears chips). The user has confirmed the field-side function is **chip blow-off**, not liquid coolant — this is intentional for wood machining (no liquid coolant on wood).

| Terminal | Wire | Other end / function | Status |
|---|---|---|---|
| R9C1 | coil low side | → GND (0 V) | ✓ |
| R9C2 | coil high side | YELLOW wire → `*55` → BROWN wire → Fagor X10/pin 21 (`BITCOOL O2`) | ✓ |
| R9A1, R9B1, R9D1 | pole 1 | **EMPTY** — confirmed unwired | ✓ |
| R9A2 | NO col 2 | BROWN wire → `*85` → cable 92 BRN → chip blow-off air-blast solenoid (field-mounted) | ✓ |
| R9B2 | NC col 2 | **EMPTY** — confirmed unwired | ✓ |
| R9D2 | COM col 2 | → +24 V common (bonded `*71`-`*76` bus). Clean +24 V source for the solenoid drive. | ✓ |
| R9A3, R9B3 | pole 3 contacts | **EMPTY** — confirmed unwired | ✓ |
| R9D3 | COM col 3 | → `*E` (110 V AC line bus) | ✓ |
| R9A4, R9B4, R9D4 | pole 4 | **EMPTY** — confirmed unwired | ✓ |

When the Fagor asserts X10/pin 21 (e.g., M95 in OEM PLC) → R9 coil energizes → R9A2-R9D2 closes → +24 V flows out `*85` → solenoid actuates → air blast at the cutting zone.
