#!/bin/bash
# run5pb.sh -- launch the PROBE BASIC config (configs/ned5_pb/ned5_pb.ini).
# Same machine iron as run5.sh (ned5_iron.hal); only the GUI layer differs.
# probe_basic + qtpyvcp live in the qt_pb venv -> put it on PATH first
# (a plain `linuxcnc ned5_pb.ini` from a non-login shell will NOT find it).
# Head A/C read->home is NOT in this config yet: home XYZ only.

NED="/home/brains/Documents/ned"
INI="$NED/configs/ned5_pb/ned5_pb.ini"
LOG="$NED/lcnc.log"
VENV="$HOME/qt_pb/qtpyvcp/venv"

if [ ! -x "$VENV/bin/probe_basic" ]; then
  echo "run5pb: probe_basic not found in $VENV -- run tools/qt_pb.sh first"; exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# clear any stale realtime so the start is always clean
halrun -U >/dev/null 2>&1 || true

# announce who is using the machine
"$NED/tools/claim.sh" "${NED_CLAIM:-user}" "${NED_CLAIM_NOTE:-LinuxCNC (Probe Basic) running}" >/dev/null 2>&1 || true

# keep the Mesa pin logger + log pruner running
pgrep -f 'tools/mesalog.sh' >/dev/null 2>&1 || ( "$NED/tools/mesalog.sh" >/dev/null 2>&1 & )
pgrep -f 'tools/logclean.sh' >/dev/null 2>&1 || ( "$NED/tools/logclean.sh" >/dev/null 2>&1 & )

# keep lcnc.log bounded + stamp a session header
if [ -f "$LOG" ]; then tail -n 2000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"; fi
{ echo; echo "==================== LinuxCNC start (PROBE BASIC)  $(date '+%F %T') ===================="; } >> "$LOG"

# launch under `script` so LinuxCNC sees a TTY and every error lands in the log
script -q -a -c "linuxcnc '$INI'" "$LOG"
