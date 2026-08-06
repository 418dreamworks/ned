#!/usr/bin/env python3
# Random A+C simultaneous-move PID survey (operator 2026-08-06).
# Waits for power, parks A/C to 0, then N random (A,C,F) legs, each
# envelope-checked against the tip-fixed joint solution. 15 s feedback
# rule: progress lines land in ac_random_progress.log continuously.
import linuxcnc, time, subprocess, json, math, random, sys
SP='/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
PROG=open(SP+'/ac_random_progress.log','a',buffering=1)
def log(m): PROG.write('%s %s\n'%(time.strftime('%H:%M:%S'),m)); print(m,flush=True)
def gp(p): return float(subprocess.run(['timeout','5','halcmd','getp',p],capture_output=True,text=True).stdout.strip())
s=linuxcnc.stat(); c=linuxcnc.command()
N=40; M=5.0
# wait for power (operator presses)
for i in range(600):
    s.poll()
    if s.task_state==linuxcnc.STATE_ON and all(s.homed[:6]): break
    if i%10==0: log('waiting for POWER (state=%d)'%s.task_state)
    time.sleep(3)
else: sys.exit('no power in 30 min')
log('machine ON and homed')
L=gp('ned_ac_kins.pivot-length')
assert abs(L-320.7741)<0.01, 'pivot wrong (%.3f) -- G43 not in force, REFUSING'%L
def mdi_retry(line, watch_joint, timeout_start=8):
    for attempt in range(4):
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        j0=gp(watch_joint); c.mdi(line)
        t0=time.time()
        while time.time()-t0<timeout_start:
            time.sleep(1)
            if abs(gp(watch_joint)-j0)>0.3: return True
            s.poll()
            if s.interp_state!=linuxcnc.INTERP_IDLE and time.time()-t0>3: return True
        log('MDI no-motion attempt %d: %s'%(attempt+1,line))
    return False
def wait_done(deadline):
    t0=time.time(); last=t0
    while time.time()-t0<deadline:
        time.sleep(1.5); s.poll()
        if s.task_state!=linuxcnc.STATE_ON:
            log('MACHINE DROPPED (state=%d)'%s.task_state); return 'dropped'
        if time.time()-last>14:
            log('  ... A=%.1f C=%.1f interp=%d'%(s.actual_position[3],s.actual_position[5],s.interp_state)); last=time.time()
        if s.interp_state==linuxcnc.INTERP_IDLE and s.inpos and time.time()-t0>4: return 'done'
    return 'deadline'
# park A and C to 0 first
ja,jc=gp('joint.4.pos-fb'),gp('joint.5.pos-fb')
log('parking from A=%.2f C=%.2f'%(ja,jc))
if abs(ja)>0.1 or abs(jc)>0.1:
    assert mdi_retry('o<tcp_pidt_ac> call [0] [0] [450]','joint.4.pos-fb' if abs(ja)>0.1 else 'joint.5.pos-fb'), 'park never started'
    r=wait_done(240)
    assert r=='done', 'park: '+r
ja,jc=gp('joint.4.pos-fb'),gp('joint.5.pos-fb')
assert abs(ja)<0.1 and abs(jc)<0.1, 'not parked (A=%.2f C=%.2f)'%(ja,jc)
log('parked at A0 C0')
# tip world position from the upright pose (identity at A=0)
Xt,Yt,Zt=gp('joint.0.pos-fb'),gp('joint.1.pos-fb'),gp('joint.2.pos-fb')
xlo,xhi=gp('ini.0.min_limit')+M,gp('ini.0.max_limit')-M
ylo,yhi=gp('ini.1.min_limit')+M,gp('ini.1.max_limit')-M
zlo=gp('ini.2.min_limit')+M
log('tip=(%.1f, %.1f, %.1f) L=%.3f'%(Xt,Yt,Zt,L))
# FULL-BALL path safety: any pose in A<=90, any C reaches at most
# Jx,Jy = tip +- L and Jz = tip - L(1-cos a) >= tip - L. If the whole
# ball fits, every INTERMEDIATE pose of every leg is safe too (the
# planner does not police joints under world moves).
assert xlo<=Xt-L and Xt+L<=xhi, 'X ball out of limits'
assert ylo<=Yt-L and Yt+L<=yhi, 'Y ball out of limits'
assert Zt-L>=zlo, 'Z ball short %.1f mm -- raise the tip'%(zlo-(Zt-L))
log('full +-90/+-180 ball verified inside soft limits (X %.0f..%.0f, Y %.0f..%.0f, Zmin %.0f)'%(Xt-L,Xt+L,Yt-L,Yt+L,Zt-L))
def joints_for(a,cdeg):
    t=math.radians(cdeg+90.0); p=math.radians(180.0-a)
    rx=L*math.sin(p)*math.cos(t); ry=L*math.sin(p)*math.sin(t); rz=L*math.cos(p)
    return Xt-rx, Yt-ry, Zt-L-rz
def ok(a,cdeg):
    jx,jy,jz=joints_for(a,cdeg)
    return xlo<=jx<=xhi and ylo<=jy<=yhi and jz>=zlo
man=open(SP+'/ac_random_manifest.ndjson','a',buffering=1)
random.seed()
pa,pc=0.0,0.0
for n in range(N):
    for draw in range(200):
        a=random.uniform(-90,90); cdeg=random.uniform(-180,180); F=random.uniform(150,600)
        if ok(a,cdeg) and (abs(a-pa)>5 or abs(cdeg-pc)>5): break
    else: sys.exit('no valid draw')
    dist=max(abs(a-pa),abs(cdeg-pc))
    deadline=dist/(F/60.0)+2*(F/60.0)/2.0+25
    rec={'n':n,'a':round(a,2),'c':round(cdeg,2),'F':round(F,0),'t_issue':round(time.time(),3)}
    log('leg %2d/%d: A%+7.2f C%+8.2f F%.0f (deadline %.0fs)'%(n+1,N,a,cdeg,F,deadline))
    if not mdi_retry('o<tcp_pidt_ac> call [%.3f] [%.3f] [%.0f]'%(a,cdeg,F),'joint.4.pos-fb' if abs(a-pa)>5 else 'joint.5.pos-fb'):
        log('leg %d never started -- stopping'%n); break
    r=wait_done(deadline)
    rec['t_done']=round(time.time(),3); rec['result']=r
    man.write(json.dumps(rec)+'\n')
    if r!='done':
        log('leg %d ended %s -- stopping'%(n,r))
        if r=='deadline': c.abort()
        break
    pa,pc=a,cdeg
    time.sleep(1)
log('SURVEY ENDED after %d legs -- staying at the last pose (operator: no return to 0)'%(n+1))
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete(2.0); c.teleop_enable(1)
log('AC SURVEY COMPLETE')
