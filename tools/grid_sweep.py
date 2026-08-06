#!/usr/bin/env python3
# accel x F grid sweep (operator 2026-08-06): accel {0.1 0.25 0.5 1} x
# F {150 300 450 600}, pattern (-90, 0), 1 cycle each.
import linuxcnc, time, subprocess, glob, os, sys, json
SP='/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
PROG=open(SP+'/grid_progress.log','a',buffering=1)
def log(m): PROG.write('%s %s\n'%(time.strftime('%H:%M:%S'),m)); print(m,flush=True)
def gp(p): return float(subprocess.run(['timeout','5','halcmd','getp',p],capture_output=True,text=True).stdout.strip())
def sp(p,v): subprocess.run(['timeout','5','halcmd','setp',p,str(v)],capture_output=True)
def nd_latest():
    f=sorted(glob.glob('/home/brains/Documents/ned/logs/pid_track_*.ndjson'))
    return f[-1] if f else ''
def legs(f):
    try: return sum(1 for l in open(f) if '"t": "leg"' in l)
    except OSError: return 0
def first_issue_f(f):
    try:
        for l in open(f):
            r=json.loads(l)
            if r.get('t')=='issue': return r.get('f')
    except OSError: pass
    return None
s=linuxcnc.stat(); c=linuxcnc.command()
def mdi(line):
    c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
    c.mdi(line); c.wait_complete(4.0)
man=open(SP+'/grid_manifest.ndjson','a',buffering=1)
mdi('(DEBUG, EVAL[setattr{vcp.getWidget{"ned_controls"}, "PIDT_CYCLES", 1}])'); time.sleep(0.5)
mdi('(DEBUG, EVAL[setattr{vcp.getWidget{"ned_controls"}, "PIDT_WAYPOINTS", [-90.0, 0.0]}])'); time.sleep(0.5)
for a in (0.1,0.25,0.5,1.0):
    for F in (150.0,300.0,450.0,600.0):
        good=0
        for i in range(160):
            s.poll()
            assert s.task_state==linuxcnc.STATE_ON, 'machine dropped'
            if (s.interp_state==linuxcnc.INTERP_IDLE and s.inpos
                    and abs(gp('joint.4.pos-fb'))<0.2):
                good+=1
                if good>=2: break
            else:
                good=0
            time.sleep(1.5)
        assert good>=2, 'never reached parked-idle in 240s'
        sp('ini.a.max_acceleration',a); sp('ini.4.max_acceleration',a)
        assert abs(gp('ini.a.max_acceleration')-a)<0.001
        rb=SP+'/pidt_rb.txt'
        poked=False
        for pa in range(4):
            mdi('(DEBUG, EVAL[setattr{vcp.getWidget{"ned_controls"}, "PIDT_SPEEDS", [%.1f]}])'%F)
            time.sleep(0.8)
            try: os.remove(rb)
            except OSError: pass
            mdi('(DEBUG, EVAL[open{"%s","w"}.write{str{vcp.getWidget{"ned_controls"}.PIDT_SPEEDS}}])'%rb)
            time.sleep(0.8)
            try: txt=open(rb).read()
            except OSError: txt=''
            if str(F) in txt or '%.1f'%F in txt: poked=True; break
            log('F poke readback mismatch (%r), retry %d'%(txt,pa+1))
        assert poked, 'F poke never landed at a=%s F=%s'%(a,F)
        before=nd_latest(); nd=''
        for attempt in range(3):
            mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}._pidt_press{}])')
            t0=time.time()
            while time.time()-t0<12:
                time.sleep(1); nd=nd_latest()
                if nd!=before: break
            if nd!=before: break
            log('press attempt %d made no run (a=%s F=%s)'%(attempt+1,a,F))
        assert nd!=before, 'press failed 3x at a=%s F=%s'%(a,F)
        time.sleep(2)
        fi=first_issue_f(nd)
        assert fi==F, 'run %s has F=%s, wanted %s'%(os.path.basename(nd),fi,F)
        man.write(json.dumps({'accel':a,'F':F,'nd':nd})+'\n')
        log('a=%-5s F=%-4.0f -> %s'%(a,F,os.path.basename(nd)))
        deadline=time.time()+400
        while True:
            time.sleep(3); s.poll()
            if legs(nd)>=2 and s.interp_state==linuxcnc.INTERP_IDLE and s.inpos and abs(s.actual_position[3])<0.1:
                break
            if time.time()>deadline:
                log('DEADLINE a=%s F=%s (legs=%d A=%.1f) -- aborting'%(a,F,legs(nd),s.actual_position[3]))
                sys.exit(2)
        log('a=%-5s F=%-4.0f done (%d legs)'%(a,F,legs(nd)))
        time.sleep(4)
sp('ini.a.max_acceleration',3); sp('ini.4.max_acceleration',3)
log('GRID COMPLETE -- pins back at 3')
