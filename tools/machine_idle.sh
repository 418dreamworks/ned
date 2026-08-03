#!/bin/bash
# CLAUDE.md rule 21: is it safe to write under configs/?
# Exit 0 = safe (LinuxCNC down, or up and genuinely idle). Exit 1 = DO NOT WRITE.
#
# Uses the NML status buffer, not pgrep. On 2026-08-03 a `pgrep -f
# 'qt_pb.*probe_basic'` matched its OWN command line and reported PB up while
# it was down -- the same self-matching trap that made a terminal-log grep
# invent three crashes. Ask the machine, not the process table.
python3 - <<'PY'
import sys
try:
    import linuxcnc
    s = linuxcnc.stat(); s.poll()
except Exception:
    print('LinuxCNC not running -- safe to write'); sys.exit(0)
idle = (s.interp_state == linuxcnc.INTERP_IDLE) and s.inpos
m = {1:'IDLE',2:'READING',3:'PAUSED',4:'WAITING'}
print('PB up: interp=%s inpos=%s -- %s'
      % (m.get(s.interp_state, s.interp_state), s.inpos,
         'safe to write' if idle else 'DO NOT WRITE, a cycle is in flight'))
sys.exit(0 if idle else 1)
PY
