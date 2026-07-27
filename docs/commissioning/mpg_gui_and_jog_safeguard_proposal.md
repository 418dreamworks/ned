# MPG GUI panel + fast-jog safeguard — proposal (activate later)

Status: **proposed, not applied.** New file `configs/ned/mpg_panel.xml` is inert
(nothing references it). Nothing in `ned.ini` / `postgui.hal` / `ned.hal` /
`mpgjog.comp` was changed. Operator activates by pasting the lines below.

Panel widgets read existing signals from `configs/ned/ned.hal` + `postgui.hal`
and the `mpgjog.0` comp outputs (`configs/ned/mpgjog.comp`).

---

## (A) MPG axis + speed / increment indicator

Widgets in `mpg_panel.xml`: `pyvcp.mpg-axis` (s32, `selaxis`), `pyvcp.mpg-speed`
(s32, `selspeed`), `pyvcp.mpg-scale` (float, mm/count), `pyvcp.jog-x/-y/-z`
(bit, live jog-enable). `selaxis` 0/1/2 = X/Y/Z, `selspeed` 0/1/2 =
slow/med/fast = 0.01/0.10/1.00 mm per detent (source: `mpgjog.comp`
`incslow/incmed/incfast`, `selaxis/selspeed` pin defs).

## (B) Limit-switch LEDs

Six `rectled` (`pyvcp.lim-x-aft`, `-x-fore`, `-y-sb`, `-y-port`, `-z-bottom`,
`-z-top`). Signals are NC, TRUE = at limit (`ned.hal` §5 / §7 lines 243-248,
450-460) → LED red = at limit, green = healthy.

### Activate (A)+(B) — two files

`ned.ini`, `[DISPLAY]` section, add:

```
PYVCP = mpg_panel.xml
# optional: panel at bottom instead of right
#PYVCP_POSITION = BOTTOM
```

`postgui.hal`, append (do both A+B together — the `pyvcp.*` pins only exist
once the panel is loaded by the `PYVCP=` line above):

```
# --- (A) MPG axis/speed indicator (mpg_panel.xml) ---
net sig-mpg-selaxis   mpgjog.0.selaxis  => pyvcp.mpg-axis
net sig-mpg-selspeed  mpgjog.0.selspeed => pyvcp.mpg-speed
net sig-mpg-jscale                      => pyvcp.mpg-scale
net sig-mpg-sel-x                       => pyvcp.jog-x
net sig-mpg-sel-y                       => pyvcp.jog-y
net sig-mpg-sel-z                       => pyvcp.jog-z

# --- (B) limit-switch LEDs (mpg_panel.xml) ---
net sig-limit-x-aft     => pyvcp.lim-x-aft
net sig-limit-x-fore    => pyvcp.lim-x-fore
net sig-limit-y-sb      => pyvcp.lim-y-sb
net sig-limit-y-port    => pyvcp.lim-y-port
net sig-limit-z-bottom  => pyvcp.lim-z-bottom
net sig-limit-z-top     => pyvcp.lim-z-top
```

`sig-mpg-jscale`, `sig-mpg-sel-x/y/z`, and `sig-limit-*` already have a writer;
each line above only adds `pyvcp.*` as an extra reader (valid — one writer, many
readers). `selaxis`/`selspeed` are unused comp outputs → new nets, no conflict.

---

## (C) MPG fast-jog accel/velocity safeguard (FIRST PASS)

**Problem** (per task, confirmed): at the fast setting the planner ramps toward
`[JOINT]MAX_VELOCITY` 338.7 / `MAX_ACCELERATION` 1354.7 mm/s² (Z 169.3 / 677.3),
but the drive command is clamped at `MAX_OUTPUT` = 25 mm/s → commanded position
outruns actual → `FERROR` 25.4 / `MIN_FERROR` 12.7 trips (`ned.ini` [JOINT_0..3]).

**Mechanism found (primary source).** The complete per-axis/per-joint jog pin
set in the motion man page is: `jog-counts`, `jog-enable`, `jog-scale`,
`jog-vel-mode`, `jog-accel-fraction` (+ read-only `kb-/wheel-jog-active`).
So there is **one** jog-specific dynamics knob — accel — and **no** jog-specific
velocity pin. Verbatim (`docs/linuxcnc/manual/man/man9/motion.9.html`, also
`/usr/share/man/man9/motion.9`):

- `axis.L.jog-accel-fraction` — *"Sets acceleration for wheel jogging to a
  fraction of the INI max_acceleration for the axis. Values greater than 1 or
  less than zero are ignored."*
- `axis.L.jog-vel-mode` — *"When FALSE (the default), the jogwheel operates in
  position mode. The axis will move exactly jog-scale units for each count,
  regardless of how long that might take. When TRUE, the wheel operates in
  velocity mode - motion stops when the wheel stops…"*

Consequence: wheel-jog **acceleration** is set jog-only by `jog-accel-fraction`;
wheel-jog **peak velocity** is bounded only by the axis/joint `MAX_VELOCITY`
(the sibling INI limit) — it cannot be scoped to jogs alone in core LinuxCNC.
(The manual's MPG example `docs/linuxcnc/manual/examples/mpg.html` reaches for
`ilowpass` to *"limit the acceleration"* — again accel, and it needs a `ned.hal`
rewire of the counts net, so out of scope for an additive first pass.)

### Design decision

Do the accel limit jog-specifically now (no ini edit, no G-code impact); offer
the velocity ceiling as an optional ini change the operator owns.

**Primary — `postgui.hal`, append (jog-only, harmless, apply now):**

```
# --- (C) MPG fast-jog accel safeguard: 0.25 s ramp to the 25 mm/s drive cap ---
setp axis.x.jog-accel-fraction 0.0738
setp axis.y.jog-accel-fraction 0.0738
setp axis.z.jog-accel-fraction 0.1477
```

Derivation (all from ini / calibration_plan):
- Drive-followable ceiling = `MAX_OUTPUT` = **25 mm/s** (`ned.ini` [JOINT_*],
  task-confirmed).
- Ramp time = Fagor `ACCTIME` = **0.25 s** (`calibration_plan.md` §1.3; check:
  338.7/0.25 = 1354.8 ≈ 1354.7 ✓, 169.3/0.25 = 677.2 ≈ 677.3 ✓).
- Target jog accel = 25 mm/s ÷ 0.25 s = **100 mm/s²** (same ramp feel, but to the
  25 cap instead of full speed).
- fraction = 100 ÷ `[AXIS]MAX_ACCELERATION`: X/Y 100/1354.7 = **0.0738**,
  Z 100/677.3 = **0.1477**.
- Effect: one fast detent (1.0 mm) peaks at √(2·100·1) = **14.1 mm/s < 25** ✓;
  detent-paced fast jogging stays under the cap. Only continuously *queuing*
  > ~3 mm of fast motion (√(2·100·3) = 24.5) reaches the cap — beyond that a
  sustained non-stop fast spin still climbs toward `MAX_VELOCITY`, which the
  optional ceiling below closes.

**Optional — velocity ceiling, `ned.ini`. DO NOT APPLY without sign-off (caps
G-code feed too):**

```
[TRAJ]    MAX_LINEAR_VELOCITY = 25.0     # was 338.7
[DISPLAY] MAX_LINEAR_VELOCITY = 25.0     # was 338.7
[AXIS_X]  MAX_VELOCITY = 25.0            # was 338.7
[AXIS_Y]  MAX_VELOCITY = 25.0            # was 338.7
[AXIS_Z]  MAX_VELOCITY = 25.0            # was 169.3
[JOINT_0] MAX_VELOCITY = 25.0            # was 338.7
[JOINT_1] MAX_VELOCITY = 25.0            # was 338.7
[JOINT_2] MAX_VELOCITY = 25.0            # was 169.3
[JOINT_3] MAX_VELOCITY = 25.0            # was 338.7
```

Rationale: with no jog-velocity pin, the only way to stop the planner commanding
faster than the drive can produce is to lower `MAX_VELOCITY` to the `MAX_OUTPUT`
ceiling (25). This is **commissioning-only**: `MAX_OUTPUT`=25 already caps the
drive at 25 mm/s regardless, so it costs no usable speed today — restore
338.7/169.3 once `OUTPUT_SCALE`/`MAX_OUTPUT` are finalized for full-speed ops
(calibration_plan §1.3-1.4). B/A/C rotary joints untouched.

Optional companion (not required): `jog-vel-mode 1` on the fast setting makes
motion stop when the wheel stops (no queued over-travel after you quit spinning);
`ned.hal` §6b currently sets `jog-vel-mode 0` (position). Does not change peak
velocity — mentioned only for completeness.

---

## Assumptions

1. **"pim files" → the LinuxCNC `.ini`** (`configs/ned/ned.ini`). All (C) source
   values were read from it.
2. `MAX_OUTPUT` = 25 is the drive-followable velocity ceiling (per task +
   `ned.ini` [JOINT_*] `MAX_OUTPUT`=25.0). Aside: `ned.hal` header models PID
   output as *volts* while `OUTPUT_SCALE` implies *mm/s* — not resolved here; I
   only used 25 as the ceiling as the task stated. Not my files to touch.
3. MPG jogs run through `axis.x/y/z.jog-*` (world/teleop, post-home; `ned.hal`
   §6b), so `jog-accel-fraction` is set on `axis.*`. If jogging in JOINT mode
   (e.g. before homing), also `setp joint.0/1/2/3.jog-accel-fraction` to the same
   fractions (0/3 and 1 = 0.0738, 2 = 0.1477).
4. `jog-accel-fraction` default = 1.0 (full `MAX_ACCELERATION`) = present
   behavior; (C) lowers it for jogs only.
5. ACCTIME 250 ms (calibration_plan §1.3, Fagor-derived) is the ramp-time basis.
6. Panel only *adds readers* to existing signals + *new nets* on the unused
   `selaxis`/`selspeed` comp outputs — no existing writer/reader disturbed.
7. `cpd`=4 (`mpgjog.comp`): jog-scale = increment ÷ 4 = 0.0025/0.025/0.25 mm per
   count. Panel "mm/count" readout shows that; "increment/detent" label shows
   0.01/0.10/1.00.
8. **Could not render the panel** — LinuxCNC is live; no GUI launch permitted.
   XML verified well-formed (`python3 xml.dom.minidom` parse OK) and widget
   tags/attributes checked against the PyVCP manual
   (`.../docs/linuxcnc .../gui/pyvcp.adoc`); visual layout unverified.

## Sources

- Jog pins / accel-fraction / vel-mode: motion man page —
  `docs/linuxcnc/manual/man/man9/motion.9.html`, `/usr/share/man/man9/motion.9`.
- MPG example + ilowpass note: `docs/linuxcnc/manual/examples/mpg.html`.
- PyVCP widget syntax (`labelframe`, `s32`, `number`, `led`, `rectled`, `hbox`):
  LinuxCNC PyVCP manual, gui/pyvcp.
- vel/accel/ACCTIME/MAX_OUTPUT/FERROR values: `configs/ned/ned.ini` [JOINT_0..3]
  + `docs/commissioning/calibration_plan.md` §1.3-1.4.
- Signal names: `configs/ned/ned.hal` §5 (limits), §6b (MPG); `postgui.hal`.
