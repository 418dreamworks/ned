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
