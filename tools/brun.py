#!/usr/bin/env python3
"""One run of b_rate_test.ngc, printing deg/s for each of the four sweeps.

Used to compare trajectory-planner settings against each other. Aborts if A
moves at all -- the operator's standing rule is that the head does not move.
"""
import linuxcnc, time, sys
s=linuxcnc.stat(); c=linuxcnc.command(); s.poll()
if s.task_state!=linuxcnc.STATE_ON or not all(s.homed[:7]): sys.exit('REFUSED: not ready')
if s.interp_state!=linuxcnc.INTERP_IDLE: sys.exit('REFUSED: busy')
if s.spindle[0]['enabled']: sys.exit('REFUSED: spindle on')
a0=s.actual_position[3]
c.mode(linuxcnc.MODE_AUTO); c.wait_complete(3)
c.program_open('/home/brains/linuxcnc/nc_files/b_rate_test.ngc'); c.wait_complete(3)
c.auto(linuxcnc.AUTO_RUN,0)
rows=[]; t0=time.time()
while time.time()-t0 < 240:
    time.sleep(0.05); s.poll()
    rows.append((time.time()-t0, s.actual_position[4]))
    if abs(s.actual_position[3]-a0)>0.01: c.abort(); sys.exit('ABORT: A MOVED')
    if s.interp_state==linuxcnc.INTERP_IDLE and time.time()-t0>3: break
o=rows[0][1]; st=rows[0][0]; out=[]
for i in range(4):
    hit=next((t for t,b in rows if abs(b-o)>=180.0*(i+1)-0.5), None)
    if hit is None: out.append('  -  '); break
    out.append('%5.2f'%(180.0/(hit-st))); st=hit
print('  '.join(out))
