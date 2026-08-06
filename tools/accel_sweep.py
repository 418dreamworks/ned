#!/usr/bin/env python3
# Accel sweep at F450 (operator 2026-08-06): 0.5..20 deg/s2, one short
# cycle (90,0,90,0) each. Loud progress to accel_sweep_progress.log.
import linuxcnc, time, subprocess, glob, os, sys, json
SP='/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
PROG=open(SP+'/accel_sweep_progress.log','a',buffering=1)
def log(m): PROG.write('%s %s\n'%(time.strftime('%H:%M:%S'),m)); print(m,flush=True)
def gp(p): return float(subprocess.run(['timeout','5','halcmd','getp',p],capture_output=True,text=True).stdout.strip())
def sp(p,v): subprocess.run(['timeout','5','halcmd','setp',p,str(v)],capture_output=True)
def nd_latest(): 
    f=sorted(glob.glob('/home/brains/Documents/ned/logs/pid_track_*.ndjson'))
    return f[-1] if f else ''
def legs(f):
    try: return sum(1 for l in open(f) if '"t": "leg"' in l)
    except OSError: return 0
s=linuxcnc.stat(); c=linuxcnc.command()
ACCELS=[0.5,1,2,3,5,8,12,20]
man=open(SP+'/accel_sweep_manifest.ndjson','a',buffering=1)
for a in ACCELS:
    s.poll()
    assert s.task_state==linuxcnc.STATE_ON, 'machine dropped'
    for i in range(20):
        s.poll()
        if s.interp_state==linuxcnc.INTERP_IDLE and s.inpos: break
        time.sleep(1.5)
    ja=gp('joint.4.pos-fb')
    assert abs(ja)<0.2, 'A not parked (%.2f) before accel %s'%(ja,a)
    sp('ini.a.max_acceleration',a); sp('ini.4.max_acceleration',a)
    assert abs(gp('ini.a.max_acceleration')-a)<0.01
    before=nd_latest()
    c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
    c.mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}._pidt_press{}])')
    c.wait_complete(4.0)
    t0=time.time(); nd=''
    while time.time()-t0<15:
        time.sleep(1); nd=nd_latest()
        if nd!=before: break
    assert nd!=before, 'press made no new run at accel %s'%a
    man.write(json.dumps({'accel':a,'nd':nd,'t0':time.time()})+'\n')
    log('accel %-4s -> %s'%(a,os.path.basename(nd)))
    deadline=time.time()+360
    while time.time()-deadline<0:
        time.sleep(3); s.poll()
        n=legs(nd)
        if n>=3 and s.interp_state==linuxcnc.INTERP_IDLE and s.inpos and abs(s.actual_position[3])<0.1:
            break
        if time.time()>deadline:
            log('DEADLINE at accel %s (legs=%d A=%.1f) -- aborting sweep'%(a,n,s.actual_position[3]))
            sys.exit(2)
    log('accel %-4s done: %d legs, parked'%(a,legs(nd)))
    time.sleep(4)
sp('ini.a.max_acceleration',3); sp('ini.4.max_acceleration',3)
log('SWEEP COMPLETE -- accel pins left at 3 (the operator-approved value)')
