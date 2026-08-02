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
