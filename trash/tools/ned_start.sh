#!/bin/bash
# ned_start.sh -- launch LinuxCNC for ned, auto-rebuilding SCALEs first.
# make-style: if ned_params.sh was edited after an INI, that INI's SCALEs are regenerated
# before LinuxCNC reads it. Use this instead of `linuxcnc ned.ini` and you never hand-edit SCALE.
DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
"$DIR/ned_params.sh" sync            # rebuild any INI older than ned_params.sh
exec linuxcnc "${1:-$HOME/linuxcnc/configs/ned/ned.ini}"
