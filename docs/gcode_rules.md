# ned g-code rules

Every rule here exists because breaking it cost a cycle on the machine. The
scanner `tools/live/gcode_lint.py` enforces the mechanical ones; the rest are
judgement and are listed so they can be checked by eye.

`tools/gcode_check.sh` runs the linter and then parses the file with
LinuxCNC's own interpreter (`rs274`). `tools/cfg_edit.sh` runs both on every
edit under `configs/`, so a file that breaks a rule never reaches the disk
the interpreter reads.

---

## 1. Comments

### 1.1 A `(...)` comment opens AND closes on its own line
LinuxCNC rejects the file with `Unclosed comment found` otherwise, and the
error names no line number. This has bitten this project three times, twice
in one afternoon on 2026-08-12.

```gcode
(RIGHT: this line opens and closes)
(WRONG: this line opens and never closes
(and this one continues the thought)
```

A multi-line explanation is written as one closed comment per line.

### 1.2 No parentheses INSIDE a `(...)` comment
Including inside `(abort, ...)` and `(PRINT, ...)`. The first `)` ends the
comment and the rest of the line becomes g-code.

### 1.3 `;` comments run to end of line
They may contain anything, parentheses included. Only `(...)` has to balance.

### 1.4 `.ngc` uses both; `.hal` uses `#` only
`;` is NOT a comment in HAL — text after it is parsed as arguments. Adjacent
files, opposite rules, which is exactly why it keeps happening.

---

## 2. Messages the operator reads

### 2.1 `%` truncates the message
`PRINT` and `DEBUG` substitute `#<var>` only. Any `%` ends the message at
that point — a `%.3f` format specifier silently swallows the rest of the
line. That is why rotary probing results appeared blank.

### 2.2 Every abort says what to do
`(abort, ...)` is read at the worst possible moment. It states what is
wrong, the value that is wrong, and the action that clears it.

```gcode
(abort, ROTARY FACE: X is #5420 - jog to G55 X0 before starting)
```

### 2.3 Name positions with expressions, not words
`G55 X0 Y0`, `machine Z0`, `#5420`. Never "the datum", "the reference" or
"the origin" — CLAUDE.md rule 24a.

---

## 3. Structure

### 3.1 One sub per FILE
LinuxCNC resolves o-words one per file via `SUBROUTINE_PATH`. A helper sub
defined inside its caller makes the interpreter find the wrong body and die
with `EOF in file ... seeking o-word`.

### 3.2 O-word numbers are unique within a file
A repeated number pairs the wrong `endif`, and the interpreter does not
complain — it just executes the wrong branch. Silent and expensive.

### 3.5 An o-word is `oNNN` or `o<name>` -- never a digit-letter mix
`o41a` reached the machine on 2026-08-12. LinuxCNC parsed `o41`, choked on
the `a`, and answered `Unknown control command in o` -- naming neither the
line nor the word. Enforced.

### 3.3 Named parameters are LOCAL to the sub that assigns them
Pass `#1..#30`, or use a global `#<_name>`.

### 3.4 Argument lines are a contract with the GUI
`SubCallButton` parses exactly `#<name> = #N (=default text)`. It hunts the
whole app for a widget whose objectName matches `name`, and falls back to
the default. No widget and no default and it refuses to call at all — so
every argument carries a default.

---

## 4. Motion

### 4.1 A corner costs speed
Bare `G64`, or the machine default `G64 P0.001`, cannot round anything: the
planner must arrive exactly on the corner point, so path velocity — and
every axis with it — goes to zero. Either give it a real tolerance or
remove the corner by moving the axes together.

### 4.2 `F` governs the linear axes
On a block with both linear and rotary words, `F` is the linear feed and the
rotary is slaved to it. On a rotary-only block `F` is degrees per minute.

### 4.3 Rapids are not gated by soft limits during a cycle
Check reachability before commanding, not after.

---

## 5. Verification

### 5.1 Nothing ships unparsed
`tools/gcode_check.sh <sub> [args]` before the operator is told a routine is
ready. It costs about a second.

### 5.2 rs274 has no probe hardware
`#5070` stays 0, so a probing cycle SHOULD stop on its own "no contact"
abort. That is the guard proving it works, not a failure.

### 5.3 Never write a file the machine is running
`.ngc` is re-read on EVERY call. All edits under `configs/` go through
`tools/cfg_edit.sh`, which refuses while a cycle is in flight.

---

## 6. The spindle at a tool change

### 6.1 The spindle is STOPPED before any M6
Operator 2026-08-13: *"when a tool change is issued, the spindle continues
spinning all the way as it moves from the work area to the tool change area.
this is not acceptable. the first thing that happens is stopping the tool
BEFORE the tool change"* ... *"i also want it as part of the final lint checked
here. before m6, there must be a stop spindle command"*.

The scanner tracks M3/M4/M5 through the file. An `M6` reached while a spindle
start is still in force is a HARD failure naming the line that started it.

```gcode
S9000 M3
G1 X10 F600
M5              (RIGHT: its own line, before the change)
T13 M6
```

**An `M5` in the same block as the `M6` is also a failure.** Within one block
the interpreter runs the words in its own order, not left to right, and the
manual shipped on this machine does not state where `M6` sits in that order --
so `M5 T13 M6` does not demonstrably stop the spindle first. Put the `M5` on
its own earlier line, where the sequencing is not in question.

`toolchange.ngc` carries no `M5` of its own, so today nothing stops the
spindle if the program does not. That is why this rule is HARD rather than a
warning.

### 6.2 Every M6 is BRACKETED
Operator 2026-08-16, standing rule. Before the change, retract to machine
Z0. After it, the return to the cut is **three separate blocks**:

```gcode
G53 G0 Z0          (before the change: machine Z0, nothing else in the block)
M5
T12 M6
G53 G0 Z0          (1. machine Z0, nothing else)
G0 X.. Y..         (2. the resume point in the work frame, still at machine Z0)
G0 Z..             (3. straight down to the resume height)
```

No diagonal, and no combined XYZ move anywhere near the work after a tool
change: a single `G0 X Y Z` out of the rack cuts the corner and can drag the
tool through the part, a clamp or the fixture on the way in.

Only MOTION blocks count toward the three steps. `S`, `M3`, `G4` and comments
between them are irrelevant to the geometry and are not violations.

HARD. `gcode_lint.py` checks both sides: the move immediately before the M6
must be `G53` + Z only, and the first three moves after it must match the
three steps above.

---

## 7. Who owns these rules

**This file is the only source of the rules.** Operator 2026-08-16: "set it
up so that YOU control the rules that the gcode genrator follows. gcode
genrator should not be wriitng its own rukes."

Rule 6.2 arrived as a verbal instruction to the g-code generator, which
recorded it in the header comment of the one program it was writing
(`alu_square.ngc:15-20`). A rule that lives in an output file governs that
file and nothing else, and nobody checks it.

So:

- Rules are written **here**, by the controls side, and nowhere else.
- The generator READS this file. It does not author, extend or reinterpret
  it, and `nc_files/.claude/settings.json` denies it write access to this
  repo so it cannot.
- A rule is not finished until `gcode_lint.py` enforces it or this file says
  in the rule text that it is judgement-only.
- Every program is linted before it runs, generator-written or not:
  `tools/gcode_check.sh <file.ngc>`.

### 6.3 The spindle starts at the XY resume, never before it
Operator 2026-08-16, from watching a change run: *"the spindle was turned on
after a new tool was picked up while the tool was on the way back. it should
not happen. i should only spin up when it is at XY resume."*

```gcode
G53 G0 Z0          (1. machine Z0)
G0 X.. Y..         (2. the resume point -- STILL STOPPED)
S6000 M3           (3. spindle up, now that XY is where the cut resumes)
G4 P3.0
G0 Z..             (4. down to the cut)
```

The wrong order puts a spinning cutter on a full-speed traverse across the
table from the rack. It was in `alu_square.ngc` at both changes: `S M3` sat
immediately after `G53 G0 Z0`, before the `G0 X Y`.

HARD.

### 6.4 Every spin-up from zero dwells 3 s
Operator 2026-08-16: *"there should be a 3 second dwell whever the spindle is
spinning up from zero."* `G4 P3` or longer, before the next move. Checked at
every start from stopped, not only after a tool change.

A `G4` whose `P` is a parameter (`G4 P#<spinup>`) cannot be evaluated by the
linter. That is reported as SPIN-UP DWELL NOT CHECKABLE — a warning, not a
failure, because failing a compliant file is how a linter gets switched off.
