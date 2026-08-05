# tools/live/ — needed to RUN the machine (read-first enumerator)

| File | Role |
|---|---|
| `ned_brain.py` | Userspace HAL comp `brain` (loadusr in postgui_pb.hal): head A/C absolute reads, homing guards + post-home verify, per-axis REF handling, MANUAL/teleop restore after programs, X-pair sequence watchdog, stored-home saver, gui.md event log. |
| `ned_pendant.py` | Userspace HAL comp `pendant` (loadusr in postgui_pb.hal): MPG state machine — tap/double-tap axis cycle (skips locked A/C), press+wheel jump size (10 detents/step), double-tap+hold jog speed. |
| `pso_live.comp` | RT comp: queued PktUART reader for the head Yaskawa PSO stream (install via halcompile; loaded by iron HAL). |
| `jogblock.comp` | RT comp: gates MPG jog counts against tripped limit direction (iron HAL). |
| `limdir.comp` | RT comp: directional limit-switch logic (iron HAL). |
| `mesalog.sh` | Standing Mesa pin logger → ned/mesa.log (Claude keeps it running — CLAUDE.md rule 9). |
| `logclean.sh` | Log pruning/caps (term/mesa 1 h roll, lcnc.log 5000 lines). |
| `screenlog.sh` | Screen-blanking watcher (open task #12). |
| `ned_params.sh` | Parameter SSOT (gears, PPR, SCALEs) + `sync` writes the generated config values — CLAUDE.md rule 11. |
| `qt_pb.sh` | Probe Basic install/update wrapper (WIPES the qt_pb venv when re-run — see migration runbook before using). |
| `pb_fit_check.sh` | GUI FIT watchdog, launched in the background by `run5.sh`. Samples the PB window AND its child extents for ~100 s and writes FAIL lines to `lcnc.log` if anything exceeds the monitor. Exists because a user tab's minimum size grew the layout past the screen while the window still measured correctly (2026-08-03). Report-only. |
| `dro2.py` | Second-monitor DRO (operator 2026-08-05): its OWN process, reads `linuxcnc.stat` directly so a GUI fault cannot take the numbers away. Selected axis + jog-speed slot come from the pendant's signals via HAL pins `dro2.axis-in` / `dro2.inc-index-in` -- it keeps no record of its own. Launched and killed by `run5.sh` / `pb_restart.sh`. |

## gen_params.py (added 2026-08-02)
The MASTER parameter system (task #16). `configs/params/MASTER.params`
is the single authoritative source for every `configs/params/*.inc`
value (comment-preserving; derived scales/velocities computed from
[drivetrain] primitives). Commands: `check` (round-trip byte compare +
ned_params.sh cross-check), `write` (regenerate the .inc files),
`extract` (one-time bootstrap, refuses if MASTER exists). head_zero.inc
is EXCLUDED (ned_brain writes it at zero capture).
