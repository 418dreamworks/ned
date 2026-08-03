# Project Instructions

1. Answer the question and STOP. Say no more. Give the SHORTEST possible answer — one word/token ("No.", "R4.", "`*B`.") when that answers it. Give ONLY the value asked for, no citation, source, restatement, or trailing clause unless explicitly asked. The USER reasons — do NOT reason, analyze, weigh options, hypothesize, or explain unless explicitly asked.
2. NEVER suggest next steps, alternatives, or recommendations. NEVER ask questions. Only answer what was asked.
3. Do not guess or make up information. If you don't know, say so.
4. Any answer about machine condition/wiring MUST be based on the project notes read IN THEIR ENTIRETY.
5. Any answer that uses a manual MUST be based on that manual read IN ITS ENTIRETY.
6. Read primary sources (photos, manuals, datasheets, notes) directly. Never reference deleted or unreliable files.
7. When a question has a DEFINITIVE answer in a manual, get the answer FROM the manual — never from memory or inference. Then record it in a read-first quick-ref file (e.g. `docs/servo/yaskawa_params_quickref.md`) with the manual line cites, because the user will likely ask again. Read that quick-ref before re-opening the manual.
8. Before asking the user to check or report any machine/Mesa status, first check whether you can read it yourself (mesa.log, term.log, halcmd — including starting a temporary HAL session if none is running) and DO it. Only involve the user when software genuinely cannot read it (DMM on copper, drive panel displays). Don't waste user time.
9. Monitoring the Mesa and the terminal is YOUR job, ALL THE TIME. Keep `tools/live/mesalog.sh` running yourself (restart it if dead or running a stale version — the user never touches it), and read `mesa.log` + `term.log` proactively whenever anything is tested or goes wrong.
10. Two kinds of docs, kept separate:
    - **Machine notes** (tracing, components, wiring, params/quick-refs, calibration values) = FINAL/CURRENT STATE ONLY. NO origin stories ("originally", "was X → Y", "we tried", "turned out", "used to be", "reverted from", dated diagnostic narrative, superseded-plan context). Just what IS. The ONLY doc that references superseded/old (Fagor) wiring is `docs/revert_to_fagor.md` (the retrofit-delta + how-to-undo list). Redundancy across machine notes is DELIBERATE (same wiring fact in several docs = a cross-check): when copies diverge, surface it, the USER rules which is correct, fix the wrong copy — do NOT collapse wiring prose into one owner. (Parameters are the opposite — see rule 11.)
    - **Commissioning notes** = where ALL history/narrative/origin stories live, AND they give the PATH (links) to the relevant machine notes. History belongs here and nowhere else.
11. **Single source of truth for parameters.** Any value stored in `tools/live/ned_params.sh` (gear ratios, drive PPR, microstep, and the derived SCALEs) lives THERE and nowhere else. Never restate that number in any other file — docs cite `tools/live/ned_params.sh` instead of copying it. Config files LinuxCNC must read (INIs, `configs/params/*.inc`) get the value ONLY by being generated from ned_params.sh (`ned_params.sh sync`), never hand-typed. Before writing any parameter value into any file, check ned_params.sh first; if it lives there, reference it — do not copy it.
12. **Kill protocol (LinuxCNC/PB).** NEVER kill without asking the user
    first. Permission, when granted, is valid for EXACTLY ONE kill — the
    next kill needs a fresh ask. Never ask the USER to kill anything:
    if PB needs killing, ask for permission to do it yourself.
    LAUNCHING is always the user's job (tools/run5.sh) — never launch.
13. **tools/ layout + read-first indexes.** `tools/` root = staging (+
    run5.sh only); `tools/live/` = needed to run the machine;
    `tools/groundtruth/` = proven bench references. Each folder has an
    `INDEX.md` enumerating every file and why it is there. READ ALL THREE
    INDEX.md FILES at session start and after every compaction — they are
    the fast, authoritative map of the tooling. Look there FIRST before
    searching tools/; keep them updated whenever a tool is added, moved,
    or trashed.
14. **FULL-STACK AUDIT before every GUI change.** No PB/GUI modification
    lands without tracing the ENTIRE stack and stating it checks out:
    (a) the target widget exists and is found the way the code finds it
    (objectName, menu provider, dynamic action); (b) the binding mechanism
    is understood (ActionButton action vs QAction vs rules vs slot) and the
    old binding is actually severed; (c) the layout type is verified before
    layout calls (QGridLayout has NO insertWidget); (d) load order is
    respected (user DROs load AFTER postgui; menus are yml-built); (e) the
    code path PROVABLY RUNS: loud log line on success AND on failure —
    silent no-ops are forbidden (a silent zero-match rebind left a stock
    one-sided Home X live and RACKED the gantry, 2026-08-01); (f) verify
    the log line on the next launch. GUI widget references: use the badge
    numbers in `ned/gui_map.txt` (regenerated every launch).
15. **Never post to GitHub on the user's behalf.** No PR/issue comments, no review replies, no PR titles or bodies published or edited under their name. Draft the text, show it in chat, and the USER posts it. Pushing a branch or opening/updating a PR happens only when the user asks for that specific action in their current message.
16. **MOTION PRECONDITIONS — the most serious rule here. A violation of this
    is a crash, not a bug.** On 2026-08-02 21:15 I commanded a continuous
    full-speed Z jog "into a clamp" that was NOT ARMED, with the box guard
    NOT RUNNING. Z ran 310 mm down to −325 uncontrolled. My own console had
    printed `LinuxCNC floor -620.000` — proof the clamp was off — and I did
    not read it. Nothing was damaged; that was luck, not design.
    BEFORE ANY command that can move the machine:
    (a) **ASSERT the precondition, in code, and abort if it is false.** If a
        test depends on a guard/clamp/limit being active, READ IT BACK and
        stop if it is not. Never infer it from "I just clicked enable" — the
        click may have missed (it did).
    (b) **The box guard must be RUNNING.** If it was stopped for any reason
        (operator took over, a move had to leave the box), restart it before
        the next motion command. Never leave it off "for a moment".
    (c) **NEVER issue a continuous/unbounded jog** in a script. Increment
        jogs only, with a known distance, and a target computed to stay
        inside the box.
    (d) **Print the precondition and the target BEFORE moving**, and make the
        script refuse when they disagree — a printed warning nobody reads is
        worth nothing.
    (e) If the machine must leave the box (recovery), stop the guard, make
        ONE bounded move, and re-arm the guard immediately afterwards.
17. **PHYSICALLY HOMED, EVERY SINGLE TIME, NO EXCEPTIONS.** Before ANY command
    that can move the machine, the machine MUST have been PHYSICALLY homed in
    THIS LinuxCNC session — a real switch-seeking cycle that MOVED, verified.
    `stat.homed == 1` IS NOT ENOUGH AND NEVER WAS: every launch DECLARES home
    wherever the machine happens to be sitting, so the flag is true while the
    coordinates mean nothing. That is exactly what the STALE HOME banner is
    telling you.
    - **Every relaunch invalidates homing.** PB restarted = re-home before you
      move. I violated this repeatedly on 2026-08-02 (relaunched four times,
      kept testing, then set a "Z floor -90" that was 90 mm below an arbitrary
      boot position instead of true zero), and was about to do it again minutes
      after writing rule 16.
    - **Verify the home ACTUALLY RAN:** the joint must be seen UNHOMED, then
      `homing` TRUE, then a non-zero joint velocity. A home that returns in 0 s
      having moved nothing is a NO-OP that reports success — and for a gantry
      pair BOTH joints (0 and 3) must be unhomed first or `home(0)` completes
      instantly without moving.
    - **No "it was homed earlier".** Earlier was a different session.
    - If homing cannot be completed, DO NOT MOVE THE MACHINE. Say so and stop.
    - **THIS RULE BINDS ME, NOT THE OPERATOR.** It governs motion I command
      from a script or test. NEVER turn it into a GUI gate: no button, cycle
      or panel may refuse the operator because home was not physically re-run
      this session. Declaring home from stored coordinates and flying the
      STALE HOME banner is deliberate -- it exists so the operator can work
      through many restarts without re-homing, and that is their risk to take
      (operator 2026-08-03: "it should NEVER gate anything ... we are going to
      restart a lot"). I added exactly such a gate to the calibration buttons
      and it was wrong.

18. **NEVER hand over g-code that has not been machine-checked.** Run
    `tools/gcode_check.sh --all` (or `<subname> [args]`) BEFORE telling the
    operator a routine is ready. It parses each subroutine with LinuxCNC's own
    interpreter (`rs274`) — no machine, no HAL, no motion, about a second per
    sub. On 2026-08-03 the operator pressed StartA three times and got only
    errors, because I shipped g-code I had merely read: a helper sub defined in
    the calling file (`EOF in file ... seeking o-word` — LinuxCNC resolves subs
    ONE PER FILE via SUBROUTINE_PATH) and a comment spanning several lines
    inside one pair of parens (`Unclosed comment found`). Both are invisible to
    inspection and both reproduce offline instantly. Also: named parameters are
    LOCAL to the sub that assigns them (pass `#1..#30` or use a global
    `#<_name>`), and a comment or `(abort, ...)` message must contain no inner
    parentheses. rs274 has no probe hardware, so `#5070` stays 0 and a probing
    cycle SHOULD stop on its own "no contact" abort — that is the guard
    proving it works, not a failure.

19. **READ THE LOG THE MACHINE WROTE, NOT A TERMINAL LOG.** `~/.bashrc` wraps
    EVERY interactive shell into `logs/term-<stamp>-<pid>.log`, so those files
    contain whatever that terminal printed — including MY OWN tool output. On
    2026-08-03 I grepped a term log for "Bus error", matched the words I had
    printed myself while investigating, and told the operator there had been
    four crashes when there had been exactly ONE. Twice in one session I built
    a conclusion on my own echo.
    - PB / LinuxCNC evidence comes from **`ned/lcnc.log`** (written by
      `run5.sh` under `script`, session-stamped) and
      **`configs/ned5_pb/pb.log`**. Use `tools/lcnc_session.sh` — it slices
      lcnc.log at the last `==== LinuxCNC start ====` header, so it is the
      CURRENT session only, and strips ANSI.
    - NEVER count or quote occurrences from `logs/term-*.log` as machine
      evidence. If one is genuinely needed (it captures stdout that lcnc.log
      misses), first confirm the file belongs to the session that launched PB,
      and exclude my own output before counting.
    - Counting is where this bites: a bare `grep -c` over the wrong file
      manufactures a pattern out of nothing. Anchor on a signature only the
      machine can emit (e.g. `linuxcnc: line NNN: PID Bus error`), never a
      bare phrase.
