# The grumble index — plan only, nothing implemented

Operator 2026-09-29: *"i want to build a history of my comments so that we can
fix file, material and we know the tools used, and you know the machine
state."* ... *"i just want to be able to say which line, and what the issue
was."* ... *"we will use this to build up my preferences and use tis index of
grumbles to improve all future toolpath generation. plan that out. no
implemention."*

**Status: PLAN. Nothing is wired.** `tools/feedback_log.py` exists — written
before the "no implementation" instruction, and its input is wrong: it asks
for his words when it should ask for a line number. It stays unwired and
uncalled until this plan is accepted or binned.

---

## 1. He types nothing. It is buttons in PB.

*"but basically, it should be part of PB"* ... *"i want a few buttons.
everything should be written as a negative"* ... *"when I click too fast, it
registers that a line in the code was too fast."*

He is watching the cut with his hand near the panel. One click, no line
number, no typing, no dialog.

```
   TOO FAST      TOO SLOW      TOO DEEP      TOO SHALLOW

   WRONG PLACE   WASTED MOVE   TOO CLOSE     CHATTER
```

**Every face is a negative.** Not "reduce feed" — he is not prescribing, he is
complaining, and the prescription is mine to derive. A button that says
"slower" invites him to specify how much; a button that says TOO FAST records
a fact and leaves the number where it belongs.

**One click, nothing else happens.** No confirmation, no dialog, no pause —
rule 29. The cut keeps running. The only feedback is the button's own
`:checked` styling from the stock QSS for a second, so he knows it registered
(rule 27: stock widget, stock styling, only the text and the wiring are ours).

Eight faces is the ceiling. If a ninth is wanted, one of the eight was not
earning its place.

---

## 1a. WHICH LINE — and this is the part that is easy to get wrong

**`stat.current_line` is NOT the line he is looking at.** It is where the
interpreter has read to, and the interpreter runs far ahead of the machine.
`stat.motion_line` is the block whose motion is executing. That is the one to
capture, and getting this backwards would attach every grumble to a block
tens of millimetres past the one that annoyed him.

**Then subtract him.** He sees it, decides, reaches, clicks — call it 1 to 2
seconds. On a 60 mm/s air move that is 60 to 120 mm, several blocks gone by.
So a click does not capture a line, it captures a **window**:

```
click at t          motion_line = N
record              N, and the blocks covering the preceding ~2 s of motion
resolve later       to the run of blocks sharing one feed, mode and section
```

Resolving to the *run* rather than the block is what makes it robust: eleven
consecutive 36.329 mm blocks at G1 F3600 are one thing he is annoyed by, not
eleven. A click anywhere in the run means the run.

**The reaction offset is a guess and must be visible as one.** Record the raw
`motion_line`, the timestamp and the machine's position history; do the
windowing at analysis time, where it can be corrected, not at capture time,
where it cannot.

---

## 2. What the machine fills in

Everything else is derivable, and **every field below was got wrong by hand at
least once on 2026-09-29** — T12's diameter, T14's flute count, the published
tool table, the Z floor. Anything typed is a field that will disagree with the
machine by the end of the week.

From the line number alone:

| | derived from |
|---|---|
| program, its 3-letter code, its md5 | `stat.file`, or the last file pulled |
| the block itself | the file at that line |
| operation section | nearest preceding `(...)` section comment |
| modal state at that line | interpreting the file from the top: G0/G1, F, S, plane |
| the move | distance, direction, from/to XYZAC |
| **air or in material** | Z against the declared `(STOCK TOP Z ...)` |
| reachable feed | `0.5*sqrt(2*a*d)*60` — whether the commanded F is real |
| chipload | `F / (S * flutes)`, flutes from ned's tool table |
| tool | the `T` word, then diameter, flutes, measured `z_offset`, shoulder |
| machine state | tool in spindle, `tool_offset`, `g5x`, `arm.out`, homed, interp |
| material | the run's material, stated once per job, not per grumble |

**The derivation is the product.** "Line 1340, too slow" becomes:

```
F1 SWARF MITER A, block 6 of an 11-block sweep-to-sweep return
G1 F3600 = 60 mm/s, 36.329 mm, Z23.8125
Z23.8125 is 6.35 mm ABOVE the stock top 17.4625  ->  AIR
reachable on a 36.329 mm rotary segment: F3616  ->  it is NOT segment-limited
therefore: an air move deliberately emitted as a feed move
```

That last line is the finding. He said three words.

---

## The method moved to Machining

Sections 3 to 7 -- clusters not points, the g-code signature table, the
four rungs, where the rules go, and the open questions -- are the method
and they live in `ned/docs/optimum_fs.md` under "HOW A NUMBER IN THIS
FILE GETS SET". Moved 2026-10-01. What is left here is the PB build.

---

## 6a. Where it lives in PB

It is a user tab section, built the way every other ned control is — stock
widgets in a stock layout, and **the only two things that are ours are the
button text and what the click is wired to** (rule 27). No custom QSS, no
fixed heights, no explanatory labels, no status line. The `:checked` styling
already in `probe_basic_dark.qss` is the acknowledgement.

```
ned_controls.py          the eight buttons, one slot, one append per click
docs/grumbles.jsonl      append-only, one JSON object per click
tools/grumble_infer.py   OFFLINE. Clustering and signature matching.
                         Never runs in the GUI process.
```

**The click path must do almost nothing.** Read `motion_line`, `file`,
`tool_in_spindle`, `g5x`, the clock; append one line; return. No file
parsing, no inference, no disk scan of the program — this runs while the
machine is cutting and PB already sits at 51% CPU on a Pi carrying a 1 ms
servo thread. Everything expensive happens later, offline, against the log.

The full-stack audit (rule 14) applies before any of it lands: the widget
exists and is found the way the code finds it, the layout type is checked
before any layout call, the load order is respected, and the click path logs
loudly on success **and** on failure — a grumble button that silently does
nothing is worse than no button, because he will keep clicking it and believe
the record exists.

---

