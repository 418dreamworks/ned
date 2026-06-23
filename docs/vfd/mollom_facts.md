# Mollom G75 — Facts

The replacement VFD being installed in place of the Saftronics VG5.
Facts only — pulled straight from the manual or directly observable on the unit.

Source manual: `docs/mollom_G75_AC_drive_manual.pdf` (Version 1.02, Jan 2022).
Text-searchable extract: `docs/text/mollom_G75_AC_drive_manual.txt`.

---

## This Drive's Specific Model

**`G75-2T-7R5-G-B`**

Decoded per manual section 2.2:

| Position | Code | Meaning |
|---|---|---|
| Series | **G75** | Asynchronous-motor general-purpose flux vector inverter (G75E would be synchronous) |
| Voltage class | **2T** | 3-phase 220 V input |
| Motor power | **7R5** | 7.5 kW |
| Application | **G** | General (not Fan/Pump) |
| Braking unit | **B** | Built-in braking IGBT |

So this is a **7.5 kW (~10 HP) general-purpose 3-phase 220 V AC drive with built-in braking unit**.

---

## Power Wiring (this model)

| Terminal | Connection | Notes |
|---|---|---|
| **R, S, T** | 3-phase 220 V input | Phase order does not matter (manual section 3.2.7 wiring diagram and section 3.2.2). Connect each to one phase of the supply. **Do not connect neutral to any of R/S/T.** |
| **U, V, W** | 3-phase output to motor | Connects to motor U/V/W. Phase order determines rotation direction (swap any two to reverse). |
| **P+, PB** | Braking resistor across this pair | This drive has the built-in braking unit (suffix B), so the resistor goes here. The internal IGBT switches it. |
| **P1, P+** (or **[+]**) | DC reactor (optional) | If used. |
| **P+, P−** (or **[+], [−]**) | External braking unit (NOT used on this drive) | This drive doesn't need an external unit. |
| **PE** (chassis ground symbol) | Earth ground | Grounding required. |

⚠ The L, N terminals shown elsewhere in the manual are for the **single-phase 2S** variant only — this drive does not have them.

---

## Braking Resistor Spec (for this 7.5 kW drive, 3PH 220V)

From the manual's resistor table (section 3.2.6):

| AC drive power | Resistor power | Resistor value |
|---|---|---|
| 7.5 kW (3PH 220V) | **1000 W** | **≥ 16 Ω** |

Default DC braking start voltage: **760 V** on the DC bus (F9-07, range 650–800 V). The IGBT switches the resistor when bus voltage exceeds this.

---

## I/O at a Glance

From manual sections 2.1, 3.2.3, 3.2.4, 3.2.7:

### Power supplies (provided by the drive)
- **+10 V → GND**, 50 mA max — for analog reference (e.g., external pot).
- **+24 V → COM**, 200 mA max — for digital input common (sourcing).
- These two supplies are **internally isolated** from each other.

### Digital inputs (DI) — 5 total
- **S1, S2, S3, S4, S5/HDI** — all photo-coupler isolated.
- Input impedance: **1.03 kΩ**.
- HDI/S5 also accepts high-speed pulse input, up to **100 kHz**.
- **Sink / source switchable** by a jumper above the DI terminals (factory default = **sink**).
  - Sink mode: DI terminal is internally pulled to +24 V; external switch closes DI to **COM** (0 V) to activate.
  - Source mode: DI terminal is internally pulled to COM; external switch closes DI to **+24 V** to activate.
- DI functions are assigned by parameters F4-00 (S1), F4-01 (S2), F4-02 (S3), F4-03 (S4), F4-04 (S5/HDI).

### Analog inputs (AI)
- **AI1 → GND** — single-polarity, 0~10 V or 4~20 mA (jumper-selectable). Default: voltage. Current impedance: 160 Ω.
- **AI2 → GND** — **dual-polarity (±10 V)**, or 4~20 mA. Also supports PT100 / NTC sensor input. Default: voltage. Default scaling: ±10 V = ±100% (F4-18 = −10 V, F4-19 = −100%, F4-20 = +10 V).
- **AI3** — keypad potentiometer only (cannot be wired externally).

### Analog outputs (AO)
- **AO1 → GND** — voltage 0~10 V or current 0~20 mA, jumper-selectable.
- **AO2 → GND** — same.
- Function set by F5-07 (AO1) and F5-08 (AO2).

### Relay output (RY1) — **one SPDT relay**
- **TA = common pole**, **TB = NC contact**, **TC = NO contact**.
- Contact capacity: **250 V AC, 3 A** / **30 V DC, 5 A**.
- Function set in F5 group.

### Open-collector outputs
- **Y1 → COM** — multi-function open-collector. Sinks to COM when active.
- **HDO → +24 V** — high-speed pulse output, up to 100 kHz. Can be reconfigured to general open-collector. Driven by +24 V to external loads, circuited with COM after activation.

### Serial communication
- **485+, 485−** — one RS-485 channel, Modbus-RTU protocol.

---

## Control Modes Available

- **SVC** (Sensorless Vector Control): speed range 1:100, accuracy ±0.5%.
- **FVC** (Closed-loop Vector Control, needs encoder): speed range 1:1000, accuracy ±0.02%.
- **V/F** (open-loop scalar): basic.
- **Torque control**.

Type G (this drive) overload capability: **150% for 60 s, 180% for 3 s**.

---

## Frequency Range

- Output frequency: **0.00 Hz to 500.00 Hz** (default) or **500.00 Hz to 3000.00 Hz** (selectable via F0-22).
- Carrier frequency: **0.5 kHz to 16.0 kHz**, auto-adjustable depending on load.

---

## Environment

- Operating temperature: **−10 °C to +50 °C**.
- Avoid: dust/oil, direct sunlight, strong vibration (>0.6 g), high humidity, corrosive/combustible/explosive gases, mounting on combustible surfaces.
- Install vertically with airflow clearance: A ≥ 50 mm (sides), B ≥ 100 mm (top/bottom) for drives 0.7–15 kW (this drive falls in this band).

---

## Key Parameter Groups (for future reference)

From section 6 of the manual:

| Group | Purpose |
|---|---|
| F0 | Basic function |
| F1 | Motor parameters group 1 |
| F2 | Vector control parameters of motor 1 |
| F3 | V/F control parameter |
| F4 | **Input terminals** (DI function assignment, AI scaling) |
| F5 | **Output terminals** (DO function assignment, AO scaling) |
| F6 | Start/Stop control |
| F7 | Keypad and Display |
| F8 | Auxiliary function |
| F9 | Fault and protection |
| FA | PID function |
| Fb | Wobble, Length and Count function |
| FC | Multi-step speed reference and Simple PLC |
| Fd | Serial communication |
| FE | Advance solution application |
| FP | User Management |
| AO | Torque control and limit |
| U0–U3 | Monitor / fault trace / fault history (read-only) |

---

## Single-Phase Operation (Temporary — Until 3-Phase Power Is Available)

**Status: temporary setup. Plan is to get a rotary phase converter and switch to proper 3-phase input later.**

The manual does NOT document single-phase operation of this 2T variant. The configuration below is standard practice for running a 3-phase VFD on single-phase input, accepted with derating.

### Wiring (single-phase derated)
- **L (hot) → R**
- **N (neutral) → S** (or T — pick one)
- **Third terminal left open** (do not connect anything)
- Do NOT spread single-phase across all three input terminals (R=L1, S=L2, T=N is wrong — creates inconsistent rectifier input voltages)

For US split-phase 240 V (two hots, no neutral going to the drive): **L1 → R, L2 → T, leave S open**.

### Parameter change required
**F9-12 — Input phase loss or power loss protection**
- Default = 11 (both enabled)
- Set to **10** to disable input phase loss detection while keeping power loss detection enabled
- Without this change the drive throws **ERR12 — Input phase loss** on startup

### Expected derating
- Industry rule of thumb: **50 – 67%** of 3-phase nameplate
- Nameplate: 7.5 kW / 32 A output
- Derated output: ~3.75 – 5 kW, ~16 – 21 A
- Spindle (~9 kW / 12 HP) won't reach full nameplate HP under load — accept this until phase converter installed

### What's not protected at single-phase
- DC bus ripple is larger (120 Hz instead of 360 Hz) → bus caps age faster, accepted tradeoff for temp setup
- Input current per leg is higher → make sure input breaker / wire sized for actual current draw, not nameplate-derated
- Output phase loss protection (F9-13) and ERR13 detection remain valuable — keep enabled

### Migration to 3-phase
When the phase converter arrives:
- Re-wire R / S / T to the three converter outputs (phase order doesn't matter to the drive; rotation set by U/V/W output order)
- Set **F9-12 back to 11** (re-enable input phase loss detection)
- Full nameplate capacity available

---

## Migration Wiring — VG5 Harness to Mollom Terminals

The existing harness (originally landed on the VG5) lands on the Mollom as follows. All wires are described by what you see physically (color, label) plus where their other end goes in the cabinet so you can pick them out.

### Digital Inputs (Sink Mode — Factory Default; do not move the sink/source jumper)

| Wire (color, label, source end) | → Mollom terminal |
|---|---|
| **Brown wire** (unlabelled, single conductor, other end at R6A2) | **S1** |
| **Red wire** (unlabelled, single small-gauge conductor, other end at R7A2) — NOT one of the shielded cable reds | **S2** |
| **Orange wire labelled "2"** (standalone, other end at R2B2) | **S3** |
| **Orange wire labelled "3"** (standalone, other end at R2A2) | **S4** |

### Sequence Input Common (COM)

All three orange wires from the relay COM terminals land together on **Mollom COM**:

| Wire | Other end at | → Mollom |
|---|---|---|
| Crimped pair: orange "1" + orange "2" (two conductors joined into one physical termination) | R7D2 (the "1") and R6D2 (the "2") | **COM** |
| Standalone orange "1" (not in any crimp) | R2D2 | **COM** |

So three conductors total (two in the crimped pair + one standalone) all land on the single Mollom COM terminal.

### Analog Speed Reference (±10 V from Fagor X8 spindle output)

Cable "7" is a 4-conductor shielded cable with 2 red + 2 black + shield. Only one of each color is active; the others are spares parked dead in the cabinet.

| Wire | → Mollom |
|---|---|
| Active **red** of cable "7" (the one that continues out toward the Fagor; the other red is dead-ended) | **AI2** |
| Active **black** of cable "7" (paired with the active red) | **GND** |
| Cable "7" **shield / drain** | **GND** (alongside the green wire — single-point analog common, matches existing VG5 architecture) |
| Spare red + spare black of cable "7" | Leave dead-ended at the power-side terminal block (reserved for future expansion) |
| **Green wire** (cabinet shield-ground wire that was on VG5 terminal 12) | **GND** (same terminal as the shield) |

Jumper above AI1/AI2: leave on **Voltage** (factory default).

### Outputs — Split RY1 (fault) + Y1 (running)

| Wire | Other end at | → Mollom |
|---|---|---|
| **White wire** (unlabelled, the supply leg from the cabinet +24 V bus at `*71`-`*76`) — NOT the jumper between VG5 terminals 10/20 (that one becomes obsolete) | `*71`-`*76` (+24 V) | **TA** (RY1 common pole) |
| **Yellow wire** (unlabelled, going to `*38`) | `*38` (the CNC fault-input path) | **TC** (RY1 NO) |
| **Blue wire** (was on VG5/9, now on R1C2 at one end) | R1C2 (R1's coil terminal) | **Interposing relay NO contact output** (NOT directly to Y1 — see below) |

**Polarity handled by a small interposing relay module**, so R1 stays untouched (C1 still at 0 V, no flyback diode flip).

> **VFD-swap rule:** the **interposing relay lives with the Mollom permanently** — its input side wires to Mollom's Y1 / +24 V / COM and its output COM taps Mollom's TA. The only wire that physically moves between the VG5 and Mollom installations is the **blue wire**:
> - **VG5 setup:** blue wire lands directly on **VG5 terminal 9**. The interposing relay is not in circuit.
> - **Mollom setup:** blue wire lands on the **interposing relay's NO output**. The interposer is what feeds R1C2.
>
> In both setups, the blue wire's other end stays on **R1C2**. R1 itself never changes.

The module is a logic-input style relay: **DC+ / DC- / IN** on the input side, **NC / NO / COM** SPDT contact on the output side, with an **H/L jumper** to select active-high vs active-low input.

**Interposer input side (logic):**

| Terminal | Connected to |
|---|---|
| **DC+** | Mollom **+24 V** terminal (internal supply) |
| **DC-** | Mollom **COM** terminal |
| **IN** | Mollom **Y1** |
| **H/L jumper** | **L** (active low — module energizes when IN sinks toward DC-) |

DC+ and DC- come from Mollom's own +24 V/COM (not the cabinet `*71`-`*76` bus), so the IN signal references the same node Y1 sinks to.

**Interposer output side (power switch to R1):**

| Terminal | Connected to |
|---|---|
| **COM** | Mollom **TA** (which is already at cabinet +24 V via the white wire to `*71`-`*76`). A direct jumper from `*71`-`*76` would be electrically identical. |
| **NO** | **Blue wire** → R1C2 |
| **NC** | unused |

**Behavior:**

- Mollom running → Y1 sinks IN to Mollom COM (= DC-) → (jumper L) module energizes → NO closes → cabinet +24 V flows through COM→NO contact → blue wire → R1C2 → R1 energizes (C1 = 0 V, C2 = +24 V). Same end-state as VG5/9 sourcing.
- Mollom not running → Y1 floats → IN floats high via the module's internal pull-up to DC+ → module de-energizes → NO opens → R1C2 loses +24 V → R1 de-energizes. (If the module has no internal pull-up, add an external 10 kΩ pull-up from IN to DC+.)

Don't connect anything to TB. Leave the spare red + spare black of cable "7" dead-ended.

### Parameter Settings to Make on the Mollom Keypad

| Parameter | Value | Function |
|---|---|---|
| F4-00 | 1 | S1 = Forward RUN (default — may already be set) |
| F4-01 | 2 | S2 = Reverse RUN (default — may already be set) |
| **F4-02** | **33** | S3 = External fault (closed-relay logic — fault asserted when DI closed to COM). Matches existing R2 NC scheme. |
| **F4-03** | **9** | S4 = Fault reset |
| F4-04 | 0 | S5/HDI unused |
| **B1-01** | **1** | Master frequency reference from terminal 13/14 (i.e., AI2) |
| **B1-02** | **1** | Run command from terminal inputs (S1/S2) |
| **F5-02** | **2** | RY1 (TA/TB/TC) = Fault output |
| **F5-03** | **1** | Y1 = AC drive operating (running indicator) |
| **F9-12** | **10** | Disable input phase loss detection (single-phase derated operation — see "Single-Phase Operation" section above) |

Defaults that match without change: AI2 scaling (F4-18 = −10 V, F4-19 = −100 %, F4-20 = +10 V).

### Sanity-Check Tally

You should have **12 wire ends to land on the Mollom** + **2 to leave dead** + **1 blue wire to move to the interposer** + **interposer's own short pigtails to Mollom**. R1 stays untouched.

On the Mollom (direct wire landings):
- 4 single inputs → S1, S2, S3, S4.
- 3 wire ends (crimped pair counts as 2 + standalone 1) → COM.
- 1 active red of cable 7 → AI2.
- 1 active black of cable 7 → GND.
- 1 shield of cable 7 → GND.
- 1 green wire → GND.
- 1 white supply → TA.
- 1 yellow → TC.
- 2 spare conductors of cable 7 → leave dead.

Interposer wiring (relay stays with Mollom):
- Interposer DC+ → Mollom **+24 V** terminal.
- Interposer DC- → Mollom **COM** terminal.
- Interposer IN → Mollom **Y1**.
- Interposer output COM → Mollom **TA** (or jumper to `*71`-`*76`).
- Interposer output NO → **blue wire** (other end on R1C2).
- Jumper set to **L**.

---

## What's Different vs the VG5 (Concrete)

| Feature | VG5 | Mollom G75-2T-7R5-G-B |
|---|---|---|
| Digital inputs | 8 multi-function (terminals 1–8) | 5 multi-function (S1–S5/HDI) |
| DI mode | Hardware fixed | Sink / source switchable by jumper (default sink) |
| Run/Stop terminals | 2-wire dedicated terminals 1 (FWD) and 2 (REV) | DIs S1–S5 reassigned via F4 parameters |
| Sequence input common | Terminal 11 | COM terminal |
| Speed reference | Terminal 13 (±10 V) vs terminal 17 | AI2 vs GND (±10 V default scaling) |
| Shield ground | Terminal 12 | PE terminal in the analog input section |
| Running indicator | NO contact terminals 9–10 | One SPDT relay RY1 (TA-TC NO, TA-TB NC) **OR** Y1 open collector |
| Fault indicator | SPDT terminals 18 (NO), 19 (NC), 20 (common) | Same single SPDT relay RY1 **OR** Y1 open collector |
| 24 V supply for input common | External (cabinet `*71`–`*76`) | Internal +24 V → COM, max 200 mA |
| Number of dry-contact outputs | 2 (running NO + fault SPDT) | **1 SPDT** + Y1 + HDO open-collectors |

⚠ Only **one** SPDT relay vs the VG5's two-contact arrangement means the OEM running-feedback + fault-feedback chain must be split: one signal uses RY1, the other uses an open-collector output (Y1 or HDO). Open-collector outputs **sink** to COM when active, opposite polarity from the VG5's sourcing dry contacts — may require rewiring the downstream relay coil (R1 today) or adding an interposing relay. See `fagor8055/VG5_wiring.md` "Outputs — Need Restructuring" for the migration plan.
