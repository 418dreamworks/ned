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
