# GUI button behavior spec — the contract

Every operator control and exactly what it does. This is the CONTRACT the
code must match (audit doc: what IS intended; divergence = bug). Guards are
part of the contract: a refused action must say so or do nothing safely —
never act partially.

## DRO panel (main tab)

| Control | Behavior |
|---|---|
| ZERO X / ZERO Y / ZERO Z | Click → button text becomes a 3‑2‑1 countdown; clicking again during countdown CANCELS. At 0: current position becomes work zero for that axis (G10 L20 P0). Multiple pending zeros merge into ONE set. Refuses with an error if the machine is not fully homed. If a program/MDI is executing, waits and applies when idle. |
| ZERO ALL | Same countdown; zeroes X Y Z ONLY. A and C are never zeroed by any button. |
| Lock A / Lock C | The A/C zero buttons with the word literally swapped: identical format (big 17pt letter, small word above), word reads "Lock". INSTANT toggle, no countdown; GREEN background while locked. Locked axis is SKIPPED ENTIRELY by MPG axis selection (tap and double-tap; forward from Z wraps straight to X when both are locked); if it was the selected axis, selection immediately moves off it. Nothing else changes: servo still holds, the Homing menu still homes it, programs/MDI can still move it. |
| REF buttons | REMOVED (operator 2026-08-01: homing is rare). Homing lives ONLY in the menubar Homing menu below. |

## MOVE panel (JOG page)

| Control | Behavior |
|---|---|
| ABSOLUTE/RELATIVE | Toggle; shows which interpretation GO uses. |
| GO | Moves exactly the axes typed in the X/Y/Z/A/C fields, at the panel F feed. Blank field = that axis does not move. Absolute = work coordinates; relative = delta from current position. Move runs to completion regardless of length; MPG/manual control returns automatically ~1 s after motion truly finishes. Refused (logged/error) when: machine off, not fully homed, or something is already executing. |
| ALL→0 | Absolute move to X0 Y0 Z0 A0 C0 at panel F. Same guards as GO. |
| XY→0 | Absolute move to X0 Y0. |
| AC→0 | Absolute move to A0 C0 — the "send head to physical zero" button (when homed). |
| Z +6 | Relative move Z up 6 mm. |

## NED controls tab — JOG & PRESETS panel

The visible NED tab page is BACK (2026-08-01): its content is the JOG &
PRESETS panel (operator mockup). The module's invisible machinery is NOT a
button and stays: ned-tab HAL pins, REF ALL cycle, MPG↔GUI sync, LOCK
plumbing, mode live-gate, core hides. The tool probe stays on PB's own
stock controls (no TOOLPROBE button on this tab).

Every move this panel issues follows ONE pattern: guards (machine ON +
fully homed + interp idle + in position + no homing) → switch to MDI and
CONFIRM task_mode == MDI by polling (≤2 s; ned_brain hands MANUAL back on
its own edge — issuing early loses the race) → ONE fire-and-forget
`c.mdi("G90 G1 … F…")`. Never `wait_complete()` around motion (silent ~5 s
timeout; a mode switch aborts motion); the brain restores MANUAL + teleop
~1 s after motion truly completes. A refused move always says WHY: error
toast + log line — no silent no-ops. The panel NEVER issues G91: relative
intent (typed RELATIVE moves, the Z +10 preset) is converted to an absolute
target (current work position + delta) and sent as a single G90 line, so an
abort partway can never leave relative mode modal.

| Control | Behavior |
|---|---|
| ABSOLUTE / RELATIVE | Exclusive toggle pair; applies ONLY to the TYPED MOVE GO button. Presets are always absolute work-coordinate moves regardless of this toggle. |
| SLOW / MEDIUM / FAST | Exclusive speed toggles (amber = selected; MEDIUM at launch) setting the feed for EVERY move this panel issues. SLOW = F304.8 (1 ft/min) · 60 deg/min; MEDIUM = F3657.6 (12 ft/min) · 720 deg/min; FAST = F21945.6 (12 ft in 10 s) · 4320 deg/min. FAST is commanded above the machine limits ON PURPOSE — the planner clamps to MAXV/accel (X/Y 200 mm/s = F12000, Z 169.3 mm/s, angular 30 deg/s = 1800 deg/min) and never errors. |
| speed readout | Live amber label: "F\<mm/min\> mm/min · \<deg/min\> deg/min" for the selected speed. Updates on every toggle. |
| XY 0 | `G90 G1 X0 Y0 F<lin>` — executes IMMEDIATELY on click, no GO. |
| XYZ 0 | `G90 G1 X0 Y0 Z0 F<lin>` — ONE straight (diagonal) line, not sequenced. Immediate. |
| Z 0 | `G90 G1 Z0 F<lin>`. Immediate. |
| Z +10 | Safe lift: reads CURRENT work Z from stat and commands the ABSOLUTE target `G90 G1 Z(cur+10) F<lin>` — relative intent, absolute command; NOT absolute Z10, and never G91. Immediate. |
| XY0 Z10 | `G90 G1 X0 Y0 Z10 F<lin>` (absolute work Z10). Immediate. |
| A0 C0 | `G90 G1 A0 C0 F<ang>` — head upright. Pure-rotary line, so F is deg/min (LinuxCNC G94 rule). Lock A / Lock C do NOT block it — locks only remove axes from MPG cycling. Immediate. |
| caption | "Presets execute immediately at the selected speed — no GO needed." |
| X / Y / Z / A / C fields | Typed-move words; blank field = that axis does not move. mm for X/Y/Z, deg for A/C. |
| CLEAR | Empties all five fields. Nothing moves, no countdown. |
| GO | One linear move of exactly the filled-in words at the selected speed. ABSOLUTE = values are work-coordinate targets. RELATIVE = deltas, converted to absolute targets and still sent as one G90 line. Mixed linear+rotary words use the linear feed (F applies to the linear path); pure A/C moves use the angular feed. A non-numeric field = error toast, nothing moves; all fields blank = error toast. |
| (all moves) | Refused with an error toast + log line when: machine off, not fully homed, program/MDI executing, not in position, or homing in progress. |

## Tool page (core PB)

| Control | Behavior |
|---|---|
| UNLOAD SPINDLE | 5 s countdown on the button; clicking again during countdown cancels. Then, deterministically: verify shaft stopped (S3 quiet ≥1 s) → release drawbar → verify S2 released sensor → clear the loaded tool from the controller (M61 Q0, G49). Refused unless homed and idle. NOTE: releasing air draw afterwards may drop machine power via the air interlock — by design. |
| LOAD SPINDLE / M6 G43 | Load: clamp drawbar first, verify S1 locked-on-tool, then set the tool. M6 G43: performs the tool change of the entered tool number + applies its length offset. |

## HOLES tab

| Control | Behavior |
|---|---|
| POPULATE X / POPULATE Y | Dialog: start + count + (increment OR end, toggled); fills that column. |
| ✕ (cell hover) | Clears that one cell. |
| RUN | For every row where BOTH X and Y parse as numbers: drill a G81 hole at panel retract/depth/feed. Any other row is skipped silently. Refused unless homed. Empty table = does nothing. |
| BORE ⌀ / TOOL ⌀ / STEP fields | BORE ⌀ blank = plain drill (above). BORE ⌀ set = bore mode: TOOL ⌀ REQUIRED (error toast if missing or ≥ bore), STEP = mm per depth pass; each hole is orbited to the bore diameter (tool-center circle r=(bore−tool)/2 per pass, full G3 circle, back to center). |
| CLEAR TABLE | Empties the whole table. No countdown. |

## MPG pendant (physical wheel)

| Gesture | Behavior |
|---|---|
| rotate | Jog the selected axis, jump-size per detent. X selection moves BOTH gantry joints with identical counts (anti-rack). Jogging INTO a tripped limit direction is blocked; away is allowed. A/C capped at 1°/detent. |
| tap | Next axis X→Y→Z→A→C (wraps), skipping locked axes. |
| quick double-tap | Previous axis, skipping locked axes. |
| press + rotate | Jump size steps through the on-screen increment list (0.01/0.1/1/5 mm), 10 detents per step. Jog is OFF while pressed. |
| double-tap + HOLD + rotate | Jog speed: the on-screen 0–100% slider, 1% per detent. |
| (locked axis while selected) | Selection auto-advances off it. |

## Core PB behaviors we changed

| Control | Behavior |
|---|---|
| CHIP button (renamed from MIST) | Drives the CHIP BLOWER solenoid. FLOOD is removed from the GUI. |

## Override cluster — V / F / S / R rows (main tab)

Operator mockup 2026-08-01 23:11: each override row is
[−10%] [\<letter\> \<pct\>% button] [+10%] [absolute readout]. The stock
ActionSliders are HIDDEN, not unbound — they stay the single wiring point
(qtpyvcp actions machine.max-velocity.set / machine.feed-override.set /
spindle.override / machine.rapid-override.set), so MPG-pendant and program
override changes keep tracking and every set goes through the stock INI
clamp. Built at launch by ned_controls (build_override_clusters),
ALL-OR-NOTHING: any failed widget/layout lookup aborts the whole restyle,
stock slider rows stay visible, and the log names what was missing; a
mid-build exception rolls the journal back to stock.

| Control | Behavior |
|---|---|
| −10% / +10% | Steps that override by 10 percentage points through the hidden stock slider (setValue → stock action path). Clamped to the stock ranges: V 0–100% of 20,000 mm/min (100% = [TRAJ]MAX_LINEAR_VELOCITY × 60), F 0–150% ([DISPLAY]MAX_FEED_OVERRIDE), S 20–200% ([DISPLAY]MIN/MAX_SPINDLE_OVERRIDE), R 0–100%. Greyed while the stock gate is off (machine off / override disabled); a click that cannot act says why in the log and does nothing — never partial. |
| center "V 100%" / "F 100%" / "S 100%" / "R 100%" | The STOCK to-100 ActionButton moved into the cluster. Text is LIVE: "\<letter\> \<percent\>%", tracking every source (buttons, MPG, program). CLICK RESETS that override to 100% — the stock machine.\*-override.reset / spindle.override.reset / machine.max-velocity.reset action, untouched (V reset = full 20,000 mm/min). |
| right readout | The STOCK StatusLabel, rules untouched, moved to the right column: V = absolute mm/min (20,000 at 100%); F / S / R = percent, stock semantics. The old runtime "mm/min" units label next to the V readout is retired (mockup shows the bare number; units live in this table). |
| (failure mode) | Any missing widget/layout ⇒ NO change at all: stock slider rows remain, log line "OVERRIDE CLUSTER ABORT — stock sliders left intact: …". Mid-build exception ⇒ journaled rollback, log "OVERRIDE CLUSTER rolled back N ops". |

## Homing menu (menubar) — the ONLY homing interface

Every entry is rebound to the ned-safe cycle (the stock bindings home the
gantry sides individually and no-op on a homed head). All refuse while any
homing runs or the machine is moving.

| Entry | Behavior |
|---|---|
| Home All | Full cycle: unhome A+C → fresh head read → home Z first, then X1+X2+Y together (X pair synchronized), then A+C last. Brain verifies A/C ≤0.05°, corrects once. Ends MANUAL + teleop, MPG live. |
| Home X | Homes BOTH gantry sides together, synchronized — never one side. Nothing else. |
| Home Y / Home Z | Homes THAT single joint, nothing else. |
| Home A / Home C | One-axis head cycle: unhome that joint → fresh head read → home it alone (physically returns it to the paramfile zero) → verify that axis only. The other head axis untouched. |
| Jog-feed slider + step-size buttons (JOG page) | Owned by the pendant: they DISPLAY pendant state and follow it; the wheel gestures are how you change them. |
| Task mode (any control that switches MANUAL/MDI/AUTO) | Refused while the machine is actually moving — a mode switch aborts motion. Allowed the moment it is truly idle. |
| Notifications | Never persist; no stale toasts on hover. |
| Spindle speed | S set by program/MDI S-word (startup default 9000, so 0–200% override spans the whole range); commanded output capped at the VFD's 18000 rpm. |
| Spindle FWD / REV | Press → button reads "Check 3-2-1" (second press cancels) → spins at 0. The OPERATOR is the safety check: in MANUAL mode the iron permits spinning regardless of S1 (empty spindle is the safest spin; S1 cannot certify empty vs unclamped). In AUTO/MDI the iron still requires S1 tool-locked. STOP is instant, no countdown. |
| F / S / R / V overrides | ±10% button clusters with click-to-reset-100 centers — contract in the "Override cluster" section above. |
| Spindle numbers | LEFT = commanded speed: live M3/M4 command × override, capped 18000 — 0 at rest, the real commanded RPM while spinning (FWD and REV both). RIGHT = the baseline S word (9000 in MAN by default; the program's S when MDI/AUTO set one). |
| Gantry protection (brain) | If exactly one of joints 0/3 is ever in a homing cycle alone for ~0.5 s — from ANY source — brain aborts it with an error. One-sided gantry homing is impossible. |
| A/C at power-on | Brain reads the head absolutes and HOMES A/C IN PLACE (zero-length final move): DROs show the TRUE angles ~10 s after power-on, nothing moves, and the joints are genuinely homed. Requested homing (menu) still physically returns to zero + verifies. |
| A/C work vs machine | ALWAYS genuinely equal (no button can set an A/C work offset; nothing forces it at display level). Both DRO columns stay visible and must agree. |
| Chip load | Placeholder label where the (never-wired) spindle load meter was; per-flute chip load calc comes later from tool data. |
| After any program/MDI finishes | Brain returns MANUAL + teleop (MPG live) ~1 s after motion truly completes — never earlier, never mid-move, and never stealing the mode while you are entering a new MDI command. |
