# Plan 02 — Safety & machine-state layer (select prebuilt LinuxCNC behavior)

**Premise (confirmed against the docs):** ESTOP, limit handling, and machine-state
indication are almost entirely **built into LinuxCNC**, and `ned.hal`/`ned.ini`
already carry the skeleton. This layer is about **picking which prebuilt behavior
we want, confirming the wiring, and setting the INI knobs** — not authoring new
logic. Each item below lists: the prebuilt mechanism + citation, what ned already
has, and the decision to make.

Builds directly on the verified low-level layer (plan 01 done: all I/O, encoders,
analog commands, spindle loop). Order: **A ESTOP → B LIMITS → C STATE INDICATORS.**

---

## A. ESTOP — mostly wired; decide the latch + which faults are hard

**Prebuilt (the iocontrol estop chain, `config/core-components.html:626-650`):**
- `iocontrol.0.emc-enable-in` — "driven FALSE when an external E-Stop condition exists."
- `iocontrol.0.user-enable-out` — "FALSE when an internal E-Stop condition exists."
- `iocontrol.0.user-request-enable` — "TRUE when the user has requested E-Stop be cleared."

**GUI built-ins (free, `gui/axis.html:388,654`):** F1 toggles E-Stop, F2 toggles
Machine Power. No wiring — the GUI drives the chain.

**What ned already has (`ned.hal:208-209`)** — the standard *external-estop* pattern:
```
net sig-estop-released  => iocontrol.0.emc-enable-in     # hardware chain result
net sig-drive-enable    iocontrol.0.user-enable-out      # -> R5 / drive power
```
So the hardware e-stop already gates the machine, and machine-enable already drops
drive power. This works as-is.

**Decisions:**
1. **`estop_latch`?** The prebuilt software latch (`man estop_latch`) folds GUI
   estop + the external chain + *other fault sources* into one latched ok-out →
   `emc-enable-in`, reset by `user-request-enable`. Needed only if we want extra
   software estop sources or to make a monitored fault a hard estop. Minimal chain
   (current) needs no latch.
2. **Which monitored faults become HARD estop vs. status** — `sig-vfd-fault`,
   `sig-spindle-overtemp`, `sig-air-pressure-ok` are named and sitting unconsumed
   (`ned.hal:237-242`, comment already says "wire into emc-enable-in via and2
   later"). Pick per fault: hard-stop (into the latch/`and2`) vs. indicator-only.
   This is the same hook as the "stop spindle / sound alarm" interlocks.

---

## B. LIMITS — hard wired + soft already in INI; confirm values + override

**Prebuilt HARD limits:** `joint.N.neg-lim-sw-in` / `pos-lim-sw-in` (`man motion`).
Tripping aborts motion and disables the machine; the GUI offers a limit-override
to jog back off. **ned has these wired** (`ned.hal:214-219`, NC/fail-safe via the
`-not` inputs).

**Prebuilt SOFT limits:** `[JOINT_n]MIN_LIMIT` / `MAX_LIMIT`
(`config/ini-homing.html:79-80`: "soft limits automatically decelerate and stop
the axes **before** they hit the limit switches"). **ned.ini already sets them**
(currently PLACEHOLDER travel: X `-0.001..1500`, Y `..800`, Z `-400..0.001`).
`HOME_IGNORE_LIMITS = YES` is already set so homing can back off a limit switch.

**Decisions:**
1. **Real travel values** — measure each axis's usable travel and replace the
   placeholder MIN/MAX_LIMIT. (Soft limits are the everyday protection; hard
   switches are the backstop.)
2. **Soft limits only arm AFTER homing** — so they depend on homing working
   (plan 01 phase 6). Until homed, only the hard switches protect.
3. **Hard-limit override** behavior is built into the GUI — confirm it's the
   recovery path we want.

---

## C. MACHINE-STATE INDICATORS — prebuilt pins → GUI LEDs and/or lamps

**Enable halui:** add `HALUI = halui` under `[HAL]` in `ned.ini` → exposes all the
state pins below as HAL outputs.

**Prebuilt state pins (`man halui`, `man motion`):**
- `halui.machine.is-on` — machine powered/enabled
- `halui.estop.is-activated` — e-stop active
- `halui.program.is-running` / `.is-idle` / `.is-paused`
- `halui.joint.N.is-homed` (+ `halui.joint.selected.is-homed`)
- `motion.motion-enabled`, `motion.in-position`, `motion.on-soft-limit`

**Decisions:**
1. **Which states to surface** (at minimum: powered, estop/fault, homed, running).
2. **To what** — GUI panel LEDs (PyVCP/GladeVCP, built into the Axis/QtVista
   frontends) and/or **physical lamps / stack light** driven from spare 7I84
   outputs / 7I97 SSRs.
3. **Tie the fault path together** — e.g. `machine-on → green`, `estop or any hard
   fault → red lamp + alarm output`. This is where the alarm output from the
   "stop spindle / sound alarm" interlock question actually lands.

---

## What this layer is NOT
Closed-loop tuning, homing motion, and gantry squaring are plan 01 phase 6 — but
soft limits (B) and `is-homed` indication (C) **depend on homing working**, so
homing bring-up is the natural pull-through from this plan into phase 6.

## Acceptance
- E-stop (hardware + GUI F1) drops machine power and drive power; reset path works.
- Chosen monitored faults behave as selected (hard-stop vs. indicate).
- Soft limits set to real travel; hard limits stop + allow override.
- Selected machine states visible on chosen indicators (GUI and/or lamps).
