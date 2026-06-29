# ned circuit-by-circuit bench test plan

## Context
Retrofitting "ned" from Fagor 8055 to LinuxCNC (Mesa 7I97T + 7I85S + 7I84U). The
field wires are being moved off the Fagor and onto the Mesa cards. We want to
verify **every circuit end-to-end** as it's landed, using the HAL toolchain
(`halcmd`, `halmeter`, `halshow`, `halscope`).

Current electrical state constrains what is testable now:
- **E-stops pressed in** → servo drives are electrically dead (cannot move).
- **VFD (Mollom G75) unpowered** → no spindle, no VFD status.
- Air supply: **available** → solenoid outputs + air-pressure-ok input fully
  testable today (confirm actual actuation, not just 24 V).
- **X8 analog cable not yet landed on Mesa** (connector gender; fixed ~tomorrow)
  → Phase 5 deferred. No drives to be moved today regardless.

**Today's runnable set:** Phase 1 → 1.5 → 2 → 3, plus Phase 4 for anything
hand-turnable (MPG, back-drivable axes). Phases 5/6/7 wait (X8 / drives / VFD).

This is good for bench testing: with drives dead we can safely fire the
drive-enable and spin relays and command analog voltages without anything moving.

---

## PREREQUISITE (decided: wiring docs are authoritative) — rewrite ned.hal §7

Decision made: the updated wiring docs reflect the physical build, so
`configs/ned/ned.hal` §7 must be reconciled to them **before** any circuit test.
The mismatch is documented below; the rewrite is Phase 1.5.

**Where digital INPUTS land:**
- Wiring docs (`mesa_7i97t_wiring.md`, `tracing/fagor_8055_axes.md`):
  - X9 cabinet inputs (e-stop, 6 limits, spindle-running, air-ok, vfd-fault,
    overtemp) → **7I97T native isolated inputs** TB4 IN4–IN7 + TB5 IN8–IN14.
  - X10 tool-changer inputs (tool-probe, rack, drawbar-up, drawbar-down) →
    **7I84U TB2** INPUT28–INPUT31 (pins 13–16).
- Current `ned.hal` §7: routes **all 15** digital inputs through the **7I84**
  (`hm2_7i97.0.7i84.0.0.input-00 … input-14`).

**Numbering also disagrees** (even for the I/O both agree is on the 7I84):
- Docs land X10 outputs on 7I84 TB2 = silkscreen **OUTPUT8–OUTPUT15**; HAL uses
  `output-00 … output-07`.
- Docs land X10 inputs on TB2 = silkscreen **INPUT28–INPUT31**; HAL uses
  `input-11 … input-14`.

**Implication:** if the docs reflect the build, §7 needs a rewrite —
- cabinet inputs re-pointed to the 7I97T's own input pins (exact HAL names TBD,
  confirm with `halcmd show pin hm2_7i97.0`), and
- the 7I84 in/out indices renumbered to match the TB2 silkscreen.

**Unverified assumption to confirm on hardware:** that the 7I97T firmware as
loaded (`num_encoders=6 num_pwmgens=6 num_stepgens=4 num_inmuxs=0
sserial_port_0=0xxxxxxx`) actually exposes those TB4/TB5 isolated inputs as HAL
pins. Verify with `halcmd show pin hm2_7i97.0` before committing the rewrite. The
7I97T input/output HAL pin names are NOT yet confirmed — do not invent them.

**The §7 rewrite (Phase 1.5):**
- Cabinet inputs (e-stop, 6 limits, spindle-running, air-ok, vfd-fault,
  overtemp): re-point from `7i84.0.0.input-00..10` to the **7I97T native input
  pins** (exact HAL names resolved in Phase 1 via `halcmd show pin hm2_7i97.0`).
  Keep the `sig-*` signal names and the `-not` inversion on the NC limits.
- X10 tool-changer inputs: `input-11..14` → **`input-28..31`** (7I84 TB2).
- X10 outputs: `output-00..07` → **`output-08..15`** (7I84 TB2).
- §3–§6 stay untouched — they only use `sig-*` names; §7 is the only hardware
  seam (per the file's own architecture note).

---

## Answers to the two grounding questions

**1. Input commons on the 97 → cabinet 0 V (you're right, they need grounding).**
The cabinet inputs are active-high (+24 V appears on the pin when active), so each
IN COMMON is the 0 V return:
- `TB4 pin 9` (IN COMMON 4,5) and `TB4 pin 12` (IN COMMON 6,7) → cabinet 0 V.
- `TB5 pins 3, 6, 9, 12` (IN COMMON 8,9 / 10,11 / 12,13 / 14,15) → cabinet 0 V.
- Source per docs: X9 cable pins 18 & 19 (old Fagor 0 V taps); jumper the
  remaining commons across from those.
- **Exception — pendant block:** `TB4 pin 3` and `TB4 pin 6` go to **+5 V**
  (TB2 pin 14), NOT ground (those buttons sink to 0 V). Don't ground these.

**2. Shield landing — use the cabinet PE bar, not a 7I97 GND screw.**
The 7I97 GND terminals (`TB4 pins 13–14`, the unused TB3 plug-5 `GND`, TB5 GNDs)
are **logic/signal ground**, not earth. The Fagor traces landed cable shields on
**chassis** (every Fagor conn pin 15 = Shield → chassis). Best practice: land
shields **single-end at the cabinet PE/earth bar** to avoid a ground loop.
- If you specifically want a screw *near the card*: `TB4 pins 13–14` are two free
  GND points and the unused TB3 plug-5 `GND` (pin 19) is open — but these are
  logic GND; tying shields there can inject cable noise into logic ground.
  Prefer the PE bar. (This is a judgment call, flagged as inference, not a
  manual-quoted rule.)

---

## Test phases (gated by available power)

### Phase 0 — pre-power, no LinuxCNC
- Land input commons + shields per above.
- Confirm field power: ~24 V at 7I84 TB1 VFIELDB (pins 1,2) ref GND (pins 5,6);
  cabinet +24 V available to inputs.
- Visual/continuity audit each landed wire against the doc's `*N` terminal map.

### Phase 1 — load LinuxCNC, confirm cards enumerate
- `linuxcnc ~/linuxcnc/configs/ned/ned.ini` (or `halrun` if testing HAL alone).
- `halcmd show pin hm2_7i97.0` → confirm board id (`hm2_7i97` vs `hm2_7i97t`),
  encoder/pwmgen/stepgen counts, **and whether TB4/TB5 isolated inputs appear**.
- Confirm 7I84 sserial came up: `halcmd show pin hm2_7i97.0.7i84.0.0`.
- This is the step that resolves the real HAL pin names for the §7 rewrite.

### Phase 1.5 — rewrite ned.hal §7 to match the wiring docs
Apply the §7 changes listed in the PREREQUISITE section above (cabinet inputs →
7I97T native pins; 7I84 in→input-28..31; 7I84 out→output-08..15). Reload and
confirm `linuxcnc ned.ini` still starts clean before tripping any wire.

### Phase 2 — digital INPUTS (testable NOW: cabinet 24 V + field power)
Method: `halshow` Watch tab (or `halmeter sig <name>`); physically trip each
input; confirm the signal flips. NC limits read through `-not` → signal TRUE when
switch closed/healthy, FALSE when opened (= at limit / broken wire).

| signal | how to test now | expected |
|---|---|---|
| `sig-estop-released` | e-stop is IN now → read FALSE; release one → TRUE | toggles |
| `sig-limit-x-back/front`, `-y-left/right`, `-z-top/bottom` | press each switch by hand | TRUE→FALSE on open |
| `sig-tool-probe` | touch toolsetter contact | TRUE on contact |
| `sig-rack-pos` | actuate rack sensor | toggles |
| `sig-drawbar-up` / `sig-drawbar-down` | actuate each position sensor | toggles |
| `sig-air-pressure-ok` | air is on → reads TRUE; bleed/close supply → FALSE | toggles |

VFD-fed inputs (`sig-spindle-running`, `sig-vfd-fault`, `sig-spindle-overtemp`)
→ **deferred to Phase 7** (need VFD powered).

### Phase 3 — digital OUTPUTS (testable NOW; drives dead = safe to fire relays)
Method: unlink the hm2 output pin from its signal, force it, meter 24 V at the
field terminal / listen for the relay or solenoid, then relink:
```
halcmd unlinkp <hm2 output pin>
halcmd setp    <hm2 output pin> 1     # fire → meter 24 V at *N
halcmd setp    <hm2 output pin> 0
halcmd net <sig-name> <hm2 output pin>  # relink when done
```
- `sig-drive-enable` → R5 coil (safe, drives estopped) — confirm coil pulls in.
- `sig-spin-cw` → R6, `sig-spin-ccw` → R7 — relay coils energize (VFD off, no
  rotation) — confirm coils + contacts.
- Solenoids (`sig-chip-blowoff`, `sig-toolsetter-deploy`, `sig-drawbar-clamp`,
  `sig-taper-purge`, `sig-drawbar-release`) — **air available** → confirm actual
  actuation (blast / probe extend / clamp / purge / release), plus 24 V at the
  terminal. Cross-check: `sig-drawbar-release` should drive `sig-drawbar-down`
  sensor active; `sig-drawbar-clamp` should drive `sig-drawbar-up` active —
  closes the loop between Phase 3 outputs and Phase 2 drawbar inputs.

### Phase 4 — encoders (testable NOW: 7I97 internal 5 V, no drives needed)
- `halscope`, sample on servo-thread, add `hm2_7i97.0.encoder.NN.count` (or
  `.position`). Back-drive / hand-move each axis (if back-drivable with drives
  off) → count changes.
- Check **direction** (count up on + move; if backward, swap A/B or flip
  `encoder.NN.scale`) and rough **scale** (counts per known travel).
- X=enc.00, Y=enc.01, Z=enc.02, W=enc.03, MPG=enc.04 (spin handwheel).

### Phase 5 — analog velocity outputs (BLOCKED today — X8 not landed)
X8 is not connected to the Mesa yet (wrong connector gender; replacement arrives
~tomorrow, quick fix). This is output only and the least important. Skip today;
do this when X8 is landed. With drives dead the drive won't move, but the ±10 V
is still produced — measure it at the terminal with a meter:
- Force the DAC: `halcmd unlinkp hm2_7i97.0.pwmgen.00.value` then
  `setp hm2_7i97.0.pwmgen.00.value <v>` and `setp …pwmgen.00.enable 1`; meter
  TB3 plug-1 pin 4 (AOUT) ref pin 3 (GND).
- Verify 0 V at rest, correct polarity, and scale (OUTPUT_SCALE: X/Y/W=50,
  Z=40 → command = scale gives full ±10 V). Relink after.
- Full closed-loop motion test → Phase 6.

### Phase 6 — DEFERRED: needs drives live (e-stop released)
drive-enable actually enabling amps; closed-loop jog; per-axis direction/scale
sign vs encoder; PID tune (P→I→D, all values currently placeholders / "NOT
APPROVED"); homing (Z first seq 0, Y seq 2, gantry X shared switch — no
auto-square); FERROR behavior. **Motors can move — e-stop in hand, axes clear.**

### Phase 7 — DEFERRED: needs VFD powered + parameters set
Set Mollom params (F4-00=1, F4-01=2, **F4-02=33**, **F4-03=9**, **B1-01=1**,
**B1-02=1**, **F5-02=2**, **F5-03=1**, **F9-12=10**; AI2 ±10 V default scaling).
Then test inputs `sig-spindle-running` (Y1→interposer→R1), `sig-vfd-fault`
(RY1 TC→*38), `sig-spindle-overtemp`; spin CW/CCW direction; analog speed via
pwmgen.04 (unipolar 0–10 V, scale = SPINDLE_0 MAX_FORWARD_VELOCITY 24000 RPM);
spindle interlock (runs only when `sig-drawbar-up` HIGH).

---

## Acceptance per circuit
A circuit passes when: (a) the physical wire is on the doc's terminal, (b) the
HAL signal it should drive/read responds, and (c) for outputs, 24 V is measured
at the field terminal. Log each pass against the `*N` map.

## Safety notes
- Phase 3 fires the drive-enable + spin relay coils — fine while drives are
  estopped and VFD is off; re-verify estop is IN before each.
- With air on, `sig-drawbar-release` will actually unclamp — **pull any tool from
  the spindle first** or it drops.
- Phase 6 onward can produce motion/rotation — keep e-stop reachable.
- After any `unlinkp`/`setp`, **relink with `net`** before normal operation, or
  restart LinuxCNC to restore the config.
