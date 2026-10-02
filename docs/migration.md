# migration.md — everything queued behind the current job

Operator 2026-09-28: **"we deal witha ll these after this job. make this
migration.md"**

Nothing here is started. Nothing here gets started without him saying so.
Each item says where the work already sits, so none of it has to be
rediscovered.

---

## 1. Leave Probe Basic

Operator: *"we need to migrate out of PB but after I finish this small job. i
hate PB"*, and earlier, *"i want to use the most stable UI which is AXIS."*

**The ask is for the most STABLE UI, not the most capable.** AXIS is the named
candidate.

**What makes it hard is not the screens.** `ned_controls.py` carries the
machine's real logic and is written as a qtpyvcp user tab: A/C homing checked
against the Yaskawa drive, the ATC gates, TCP calibration, the jog and clamp
guards, the tool-state lock. Ask what moves with it before costing anything.

**Evidence collected 2026-09-28:**

| | |
|---|---|
| `probe_basic` CPU | **51.1%** on a 4-core Pi 5 carrying a 1 ms servo thread — 3x the next userspace consumer |
| loadavg | 5.95 / 6.97 / 7.40 on 4 cores |
| Mesa link failures | `hm2_7i97.0: error finishing read!` at 17:25 and 21:25 |
| the second one | took `joint 5 following error` with it 1.2 s later |

Two controls the source *claims* exist and never builds:

```
ned_controls.py:1028   "SET C REF is a PREREQUISITE for StartC, so it goes
                        above them"      -- no _mkbtn call, no CAL_SUBS key
ned_controls.py:1941   'pivot': ('cal_pivot_touch', 'PIVOT TOUCH', False)
                                         -- dead entry, no caller
```

`cal_c_ref.ngc` and `cal_pivot_touch.ngc` sit on disk unreachable. Whatever
replaces PB must not be able to do that silently.

**qtpyvcp is PySide6.** One PyQt5 import into `ned_controls.py` killed the
whole calibration page, and `py_compile`, `cfg_edit.sh`'s scanner and the
pre-commit hook all passed it — none of them import the module. Reverted in
`93e1205`.

---

## 2. isolcpus — the real fix for the Mesa dropouts

```
/proc/cmdline    no isolcpus -- RT threads share all 4 cores with everything
```

`rtapi_app` has no core of its own. Both link failures are host timing, not
the wire: `eth0` is dedicated to the Mesa at `10.10.10.1/24`, 100 Mb full
duplex, and every error counter is zero.

```
rx_errors 0  rx_dropped 0  rx_missed 0  rx_fifo 0
tx_errors 0  tx_dropped 0  tx_fifo 0   collisions 0
```

Needs a `/boot/firmware/cmdline.txt` edit and a reboot. **His call, not
mine.** Mitigated for now by putting this session on `SCHED_IDLE` at `nice 19`.

---

## 3. Tool table — data-only, all sandboxed

Scripts live in the session scratchpad and **refuse to run while LinuxCNC is
up**, because `tool_table.db` is WAL and PB owns it. All proven against a copy.

### 3a. Labels carry their unit

Operator: *"can we put units in all the table numbers instead of the
column"* → *"just change what is being displayed. that way, no code hange"* →
*"shank is useful for me to grab collets. so, i want it, but likewise, in and
mm in the column."*

`SHANK IN` already did this; the rest did not.

```
probe_offset   OFFSET        -> PBOFFSET MM      "change offset to PBOFFSET"
flute_depth    DOC           -> DOC MM
shoulder       SHOULDER      -> SHOULDER MM
safety_x       SAFETY X      -> PULLOUT X MM
safety_y       SAFETY Y      -> PULLOUT Y MM
shank_dia      SHANK IN      -> unchanged
flutes         FLUTES        -> unchanged, a count
shoulder_dia   SHOULDER DIA  -> unchanged, text
```

**Values are untouched**, so nothing has to be stripped or parsed on read —
which is what he rejected the first version for.

### 3b. Columns in and out

| | |
|---|---|
| `notes` | **out.** *"take out notes, usless"* — 15 rows, 0 set, read by nothing |
| `oal` | **flagged.** 0 set, read by nothing. *"i take care of that when I load the tool."* Not yet told to drop it |
| `safety_x` | **in.** It is the per-tool pullout and it was not in `ui_visible_column` at all, so there was no way to type one |
| `safety_y` | stays hidden — `m21.ngc:31-34`, entry on this rack is X-only |

Hidden, not deleted: one INSERT puts any of them back.

### 3c. `flutes` renders as a float

The data is clean — `value_type` is `int`, stored `'6' '2' '2' '2' '3' ...`,
no decimals anywhere. If a cell shows `2.0` that is the editor drawing an int
through a float delegate. **Core PB**, so it dies with item 1.

---

## 4. Define a V bit — T8

Operator: *"i also need a way to define a V bit. which is tool8"*.

A V bit is the one tool the table cannot describe: its cutting diameter is a
function of depth, so the single `diameter` column means nothing on its own.

```
width(d) = tip_dia + 2 * d * tan(included / 2)
max DOC  = (diameter - tip_dia) / (2 * tan(included / 2))
```

Two new custom fields, created and proven on a copy:

```
V ANGLE DEG    the INCLUDED angle, tip to tip
TIP DIA MM     the flat at the point; 0 for a true point
```

`diameter` then means the MAX diameter and the depth ceiling is derived, not
typed twice. Worked example on the copy, 90 deg / 12.7 / true point: max
usable DOC 6.3500 mm, width at 1 mm depth 2.0000 mm.

`front_angle` / `back_angle` / `orientation` exist in the schema and were
**deliberately not used** — they are LinuxCNC lathe fields, nothing on ned
reads them, and a lathe angle meaning a router V angle is unreadable later.

**Blocked on three numbers from him:** included angle, max diameter, tip flat.
T8 currently holds nothing but `tool_no 8, pocket 8`.

---

## 5. Tool-specific fork pullout — the guard

Operator: *"implement tool specific pullouts from the fork ... a few tools
need very specific pullouts and its dangerous for me to use one for
everything."*

**It already existed.** `SAFETY X` -> `#[4200 + 2T]`, read by both rack subs:

```
m22.ngc:31   #<tsx> = #[4200 + [2 * #<tin>]]
m22.ngc:34     #<cx> = [#<sx> - #<tsx>]            tool-specific
m22.ngc:36     #<cx> = [#<sx> + [#3987 - #3983]]   global = -64.0000 mm
m22.ngc:97   G1 G53 F[#3980] X[#<cx>]              <- the pullout
```

**Every `safety_x` is NULL**, so every change has silently taken the global
−64.0000 — exactly the "one for everything" he is worried about.

Sandboxed in `m21.ngc` and `m22.ngc`, both `parses clean` under rs274:

```
+ #<min_pullout> = 20.0
+ o108 if [#<tsx> LT #<min_pullout>]
+   (abort, pullout: SAFETY X for this tool is too small - ...)
+ (PRINT, PULLOUT: tool-specific SAFETY X used)
+ (PRINT, PULLOUT: no SAFETY X for this tool - global clearance used)
```

It says which number it used and refuses an implausibly small one. Pairs with
3b, which puts the column on screen so a value can be entered at all.

---

## 6, 9 and 10 moved to Machining

The travel box (E1), the joint-travel check and the feeds-and-speeds
table are the admission check and live in `ned/docs/admission.md`.
Moved 2026-10-01 with the setup/maintenance split.

---

## 7. Head calibration — what is still wrong

See `docs/commissioning/head_cal_2026-09-28.md` for the full record.

**The `mp`/`mn` split.** The two tilt sides disagree and the gap does not
shrink as the L error does, so it is not L:

```
pair 1   mp +1.6439   mn +2.2677
pair 9   mp -0.2320   mn +0.5793
```

`diff = L·sin(phi)` puts it at an A zero off by **0.160 deg**, against
StartA's 0.011. The mean-based Newton cannot remove it — it converges L onto
the average of two disagreeing sides. **This is the next thing to chase, not
more pairs.**

**C is uncalibrated.** `#3071 = 0`, StartC has never completed, and its taught
pose (`#3058 = 193.16`) back-solves to an L of 273 against today's 302.55.
Re-teach: `CLEAR C REF`, `START C`, jog, `START C`.

**The probe standoff change is committed but never run** (`3887f15`). Release,
then a fixed 0.5 mm, then the slow probe — because five reference touches at
the same pose spread 0.0450 mm when a rigid puck should give single microns.

`cal_probe_center.ngc` and `tcp_touch.ngc` still use a **plain `G1`** for
their standoff. That is what threw "Probe tripped during non-probe move"
three times at pair 19. Their backoff is 1.0 mm rather than 0.8, so more
margin, but the same failure mode.

---

## 8. `side_l` — with Production, not here

Filed to `418ops/mail/production/inbox/`. For discussion at the recode, not
for action.

```
one block, N105, spends 56.1 s crossing 186.95 mm of air at F200
whole file: 145.6 s cutting at F2700 against 237.1 s linking at F100/F200
retracts climb to Z 98.5008 against a stock top of 17.4625 -- 81.04 mm
```

Constraint for whatever comes back: faster links must not become rapids below
the stock top (safety rule R7, linter `D3`). In air it does not matter; at the
machine it does.

---

