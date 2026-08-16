#!/usr/bin/env python3
"""Live machine sampler. Runs forever, one line per second, append-only.

Written 2026-08-16 because watching a campaign by waiting on its final
report means staring at nothing while the machine is doing something -- and
if it dies, the wait is the longest part of the session.
"""
import json, os, time
SP = ('/tmp/claude-1000/-home-brains-Documents/'
      'aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad')
OUT = os.path.join(SP, 'machwatch.ndjson')
LAST = os.path.join(SP, 'machwatch.last')
NAMES = {1: 'ESTOP', 2: 'ESTOP_RESET', 3: 'OFF', 4: 'ON'}
while True:
    rec = {'t': time.strftime('%H:%M:%S')}
    try:
        import linuxcnc
        s = linuxcnc.stat(); s.poll()
        rec.update(state=NAMES.get(s.task_state, s.task_state),
                   estop=int(s.estop), vel=round(s.current_vel, 3),
                   X=round(s.actual_position[0], 3),
                   Y=round(s.actual_position[1], 3),
                   Z=round(s.actual_position[2], 3),
                   A=round(s.actual_position[3], 3),
                   homed=sum(1 for j in range(6) if s.homed[j]),
                   interp=s.interp_state,
                   tools=len({t.id for t in s.tool_table if t.id > 0}),
                   spindle=int(bool(s.spindle[0]['enabled'])))
    except Exception as e:
        rec['state'] = 'DOWN'
        rec['why'] = str(e)[:40]
    line = json.dumps(rec)
    with open(OUT, 'a') as f:
        f.write(line + '\n')
    with open(LAST, 'w') as f:
        f.write(line + '\n')
    time.sleep(1)
