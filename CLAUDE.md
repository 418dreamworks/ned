# Project Instructions

1. Answer the question and STOP. Say no more. Give the SHORTEST possible answer — one word/token ("No.", "R4.", "`*B`.") when that answers it. Give ONLY the value asked for, no citation, source, restatement, or trailing clause unless explicitly asked. The USER reasons — do NOT reason, analyze, weigh options, hypothesize, or explain unless explicitly asked.
2. NEVER suggest next steps, alternatives, or recommendations. NEVER ask questions. Only answer what was asked.
3. Do not guess or make up information. If you don't know, say so.
4. Any answer about machine condition/wiring MUST be based on the project notes read IN THEIR ENTIRETY.
5. Any answer that uses a manual MUST be based on that manual read IN ITS ENTIRETY.
6. Read primary sources (photos, manuals, datasheets, notes) directly. Never reference deleted or unreliable files.
7. When a question has a DEFINITIVE answer in a manual, get the answer FROM the manual — never from memory or inference. Then record it in a read-first quick-ref file (e.g. `docs/servo/yaskawa_params_quickref.md`) with the manual line cites, because the user will likely ask again. Read that quick-ref before re-opening the manual.
8. Before asking the user to check or report any machine/Mesa status, first check whether you can read it yourself (mesa.log, term.log, halcmd — including starting a temporary HAL session if none is running) and DO it. Only involve the user when software genuinely cannot read it (DMM on copper, drive panel displays). Don't waste user time.
9. Monitoring the Mesa and the terminal is YOUR job, ALL THE TIME. Keep `tools/mesalog.sh` running yourself (restart it if dead or running a stale version — the user never touches it), and read `mesa.log` + `term.log` proactively whenever anything is tested or goes wrong.
10. Two kinds of docs, kept separate:
    - **Machine notes** (tracing, components, wiring, params/quick-refs, calibration values) = FINAL/CURRENT STATE ONLY. NO origin stories ("originally", "was X → Y", "we tried", "turned out", "used to be", "reverted from", dated diagnostic narrative, superseded-plan context). Just what IS.
    - **Commissioning notes** = where ALL history/narrative/origin stories live, AND they give the PATH (links) to the relevant machine notes. History belongs here and nowhere else.
