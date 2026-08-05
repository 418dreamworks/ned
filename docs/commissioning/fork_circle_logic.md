# Fork-circle declaration logic — case audit draft (2026-08-04)

Operator spec: circles on home forks replace the DECLARE row. This is the
case table for audit BEFORE any code. Advisor findings get merged below.

## Stores (unchanged)
- `P(T)`   home fork, DB pocket, operator-only, 1..14 or NONE
- `#[4000+n]` rack map: tool sitting in fork n (0 empty)
- `#3991` + `tool_in_spindle` (M61): spindle record
- drawbar sensor: "something clamped" (identity-blind) → UNRECORDED /
  PHANTOM → motion hard-lock (HAL + GUI, deployed 2026-08-04)

## Derived
- LOC(T) = 0 if tool_in_spindle==T; n if #[4000+n]==T; else -1
- circle exists on fork n  ⇔  ∃T with P(T)=n
- circle face: big "T", small state word = LOC(T): TABLE / FORK / SPINDLE

## Case table (pseudo code)

```
on SINGLE_CLICK(circle T, home = P(T)):
    if LOC(T) == SPINDLE:      no-op            # only double-click moves a spindle tool
    if LOC(T) == FORK:                          # fork -> table
        #[4000+home] = 0
    if LOC(T) == TABLE:                         # table -> fork
        require #[4000+home] == 0               # can only be violated by corrupt state:
                                                # forks hold only their own tool
        #[4000+home] = T

on DOUBLE_CLICK(circle T, home = P(T)):
    if LOC(T) == SPINDLE:                       # spindle -> table
        #3991 = 0; M61 Q0
        # sensor now clamped+no-record -> UNRECORDED lock if a tool is
        # physically still in the spindle. That is the DESIGN: the lock
        # holds until the physical tool is removed (or re-declared).
    else:                                       # fork/table -> spindle
        S = current spindle tool (tool_in_spindle)
        if S == T:  no-op                       # already there (stale click)
        if S > 0:                               # evict: record goes to TABLE
            (S's fork record is already 0 -- invariant: a spindle tool
             occupies no fork. No write needed for S beyond the M61 below.)
        if LOC(T) == FORK:
            #[4000+home] = 0                    # leaves its fork
        #3991 = T; M61 QT

on LOAD_SPINDLE(typed number T):                # unchanged flow, drawbar-gated
    if P(T) == NONE:  touch ONLY #3991/M61      # never fork records
    else:             same as DOUBLE_CLICK -> spindle path

M6 fetch  T: requires LOC(T) == FORK (rack map holds T)   else abort
M6 putaway S: requires P(S) in 1..14 AND #[4000+P(S)]==0  else abort
```

## Interlocks
- Every write above is BOOKKEEPING ONLY (params + M61) — no motion. Safe
  under the tool-state motion lock; declaration is always the way out.
- All circle writes REFUSED unless machine ON + interp IDLE (M61 needs MDI;
  a mid-program declaration is meaningless anyway).
- Qt click ordering: use a 250 ms single-click timer cancelled by
  dblclick — otherwise TABLE→FORK fires en route to SPINDLE.

## Open questions for the operator
1. Double-click SPINDLE→TABLE with the tool physically still clamped
   locks the machine (UNRECORDED) until the tool is pulled — intended?
2. Evicted spindle tool goes to TABLE by record while physically still
   clamped until hand-swapped — same lock behavior — intended?
