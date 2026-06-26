# Commissioning log

Dated journal of bringing **ned** up on LinuxCNC at the machine. One file per
working day, named `YYYY-MM-DD.md`. Each entry records: what was connected/changed,
what was measured (live HAL pin states), discrepancies found vs the wiring docs,
config edits made, and open items carried forward.

This is a chronological lookback reference — it is NOT the source of truth for the
final wiring (that's `docs/mesa_7i97t_wiring.md` / `docs/mesa_7i84u_wiring.md`) or
the config (`configs/ned/ned.*`). When a log entry and those disagree, the log
records *what we observed on that date*; the canonical docs get corrected
separately.

| Date | Day | Summary |
|---|---|---|
| [2026-06-24](2026-06-24.md) | 1 | First connection to LinuxCNC. Both Mesa cards enumerate; InMux enabled; full I/O + encoder enumeration; Z top/bottom swap found. |
| [2026-06-25](2026-06-25.md) | 2 | Mollom G75 VFD power-up + full parameterization; F4-02 polarity fix; Colombo too big for single-phase drive; grease pump; digital I/O, encoders, drive-enable, R3 loop; spindle-from-LinuxCNC full loop pass. |
| [2026-06-26](2026-06-26.md) | 3 | Analog AOUTs fixed (PWM enable-0 group gate); drives reconnected; open-loop motion per axis; gantry linked (X+W one signal, track no rack); W encoder dead → detached X4 connector reseated; encoder map verified straight (axis N = enc N). |
