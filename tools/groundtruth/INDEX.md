# tools/groundtruth/ — proven bench references (read-first enumerator)

Kept for checking very basic things against known-working sequences.
IMMUTABLE in spirit: read them, run them, do not "improve" them.

| File | Ground truth for |
|---|---|
| `mpgjog.sh` | MPG wiring truth (read-only file): wheel = encoder.04, CPD = 4, button = inmux.00.input-00. Grep THIS before any pin/wiring claim. |
| `pso_read.sh` | The proven standalone Yaskawa PSO absolute read (board-free, LinuxCNC closed): RX listening → R4 select → SEN OFF→ON pulse — "order is crucial, else C leaks in". |
| `move.sh` + `move.hal` | Known-good single-axis bench move harness (script sources the .hal — a pair). |
| `solenoid.sh` + `solenoid.hal` | Known-good solenoid/IO bench harness (a pair). |
