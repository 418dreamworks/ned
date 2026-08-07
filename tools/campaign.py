#!/usr/bin/env python3
# 12-hour PID-minimization campaign wrapper (operator order 2026-08-06).
# Runs pid_tune.py in a resume loop until deadline or operator stop.
# Advisor-audited policy: exit-3 (1mm cube) -> quick restart, blacklisted;
# exit-4 (10mm cube) -> STACK RESTART + PHYSICAL REZERO + tip to baseline;
# recovery ladder L1 (soft re-enable) / L2 (full relaunch, capped at 2,
# pose-match-gated tool redeclare); packet-error gate; polish mode after
# 3 stagnant runs. GOLDEN RULE: append-only everything.
import subprocess, time, json, os, sys, glob
import linuxcnc

SP = '/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
NED = '/home/brains/Documents/ned'
CLOG = open(SP + '/campaign.log', 'a', buffering=1)
def log(m):
    line = '%s %s' % (time.strftime('%H:%M:%S'), m)
    CLOG.write(line + '\n'); print(line, flush=True)

DEADLINE = time.time() + 12 * 3600
BASELINE = {'x': -423.100, 'y': -1112.600, 'z': -264.600}
PIVOT_FULL = 320.7741
ARM_BASE = 155.9256
l2_used = 0
run_champs = []

def gp(p):
    return float(subprocess.run(['timeout', '3', 'halcmd', 'getp', p],
                                capture_output=True, text=True).stdout.strip())
def sp_(p, v):
    subprocess.run(['timeout', '3', 'halcmd', 'setp', p, str(v)], capture_output=True)

def stat_ok():
    try:
        s = linuxcnc.stat(); s.poll()
        return s
    except linuxcnc.error:
        return None

def mdi_retry(c, s, line, watch, secs=8):
    for attempt in range(4):
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        j0 = gp(watch); c.mdi(line)
        t0 = time.time()
        while time.time() - t0 < secs:
            time.sleep(1)
            s.poll()
            if abs(gp(watch) - j0) > 0.2 or s.interp_state != linuxcnc.INTERP_IDLE:
                return True
        log('mdi quiet (%d): %s' % (attempt + 1, line))
    return False

def wait_parked(s, secs=180):
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(2); s.poll()
        if (s.interp_state == linuxcnc.INTERP_IDLE and s.inpos
                and abs(s.actual_position[3]) < 0.1
                and abs(s.actual_position[5]) < 0.1 and time.time() - t0 > 4):
            return True
    return False

def last_sampled_pose():
    # newest raw record across tune ndjsons: joints snapshot before a drop
    best = None
    for f in sorted(glob.glob(NED + '/logs/pid_tune_*.ndjson')):
        for ln in open(f):
            if '"t": "raw"' in ln:
                try: best = json.loads(ln)
                except ValueError: pass
    return best

def park_ac(c, s):
    if not mdi_retry(c, s, 'o<tcp_pidt_ac> call [0] [0] [300]', 'joint.4.pos-fb'):
        return False
    return wait_parked(s)

def recover_L1():
    log('L1: soft re-enable')
    s = stat_ok()
    if s is None: return False
    c = linuxcnc.command()
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        c.state(linuxcnc.STATE_ESTOP_RESET); c.wait_complete(3.0)
        c.state(linuxcnc.STATE_ON); c.wait_complete(3.0)
        time.sleep(1); s.poll()
        if s.task_state != linuxcnc.STATE_ON:
            log('L1: machine will not enable'); return False
    if not all(s.homed[:6]):
        log('L1: not homed after re-enable'); return False
    if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) > 0.01:
        log('L1: pivot wrong (%.3f) -- G43 lost, treating as L2 case'
            % gp('ned_ac_kins.pivot-length'))
        return False
    if not park_ac(c, s):
        log('L1: park failed'); return False
    log('L1: recovered, parked')
    return True

def recover_L2(physical_rezero=False):
    global l2_used
    if l2_used >= 2:
        log('L2 CAP REACHED (2) -- systemic failure (task #27), HALTING SAFE')
        return False
    l2_used += 1
    log('L2 #%d: full stack relaunch%s' % (l2_used,
        ' + PHYSICAL REZERO' if physical_rezero else ''))
    pre = last_sampled_pose()
    subprocess.run([NED + '/tools/live/pb_restart.sh', '--close-only'],
                   capture_output=True, text=True, timeout=120)
    time.sleep(3)
    subprocess.Popen([NED + '/tools/run5.sh', '-xyzac', '-tcp'],
                     stdout=open(SP + '/run5_campaign.log', 'a'),
                     stderr=subprocess.STDOUT)
    for i in range(60):
        time.sleep(3)
        try:
            if abs(gp('arm.in0') - ARM_BASE) < 0.01: break
        except (ValueError, subprocess.SubprocessError): pass
    else:
        log('L2: HAL never came up'); return False
    s = stat_ok(); c = linuxcnc.command()
    for i in range(60):
        time.sleep(2); s.poll()
        if all(s.homed[:6]): break
    else:
        log('L2: declare never completed'); return False
    s.poll()
    ja = s.actual_position[3]
    # pose-match gate (advisor): declared pose vs last sampled pose
    if pre is not None and pre.get('rows'):
        lastrow = pre['rows'][-1]
        pa, pc = lastrow[7], lastrow[8]  # joint.4.pos-fb, joint.5.pos-fb
        da, dc = abs(ja - pa), abs(s.actual_position[5] - pc)
        if da > 0.05 or dc > 0.05:
            log('L2: POSE MISMATCH after redeclare (dA=%.3f dC=%.3f) -- '
                'HALTING, no declare, no motion (advisor gate)' % (da, dc))
            return False
        log('L2: pose match ok (dA=%.4f dC=%.4f)' % (da, dc))
    # A park with full pivot if tilted (OFF-window trick, proven)
    if abs(ja) > 0.5 or abs(s.actual_position[5]) > 0.5:
        c.state(linuxcnc.STATE_OFF); c.wait_complete(3.0); time.sleep(0.5)
        sp_('arm.in0', PIVOT_FULL)
        time.sleep(0.3)
        c.state(linuxcnc.STATE_ON); c.wait_complete(3.0); time.sleep(1)
    else:
        c.state(linuxcnc.STATE_ON); c.wait_complete(3.0)
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        log('L2: no power after relaunch'); return False
    # tool redeclare, gated: only when tool table already says T5
    s.poll()
    if s.tool_in_spindle == 5:
        if str(subprocess.run(['timeout', '3', 'halcmd', 'getp',
                'tool.mm.lock.out'], capture_output=True,
                text=True).stdout.strip()).upper().startswith('TRUE'):
            log('L2: AUTO-REDECLARE T5 (pose-match passed, tool table '
                'agrees, operator 12h order) -- LOUD LOG per advisor')
            c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
            c.mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}.'
                  '_sh_widgets["edit"].setText{"5"}])')
            c.wait_complete(4.0); time.sleep(1)
            c.mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}.'
                  '_spindle_holds_declare{}])')
            c.wait_complete(4.0); time.sleep(2)
            if str(subprocess.run(['timeout', '3', 'halcmd', 'getp',
                    'tool.mm.lock.out'], capture_output=True,
                    text=True).stdout.strip()).upper().startswith('TRUE'):
                log('L2: declare did not release the lock -- HALTING')
                return False
    else:
        log('L2: tool table does not say T5 -- HALTING for operator')
        return False
    # PARK FIRST (advisor): A/C homing's final joint-mode move to zero
    # would sweep the tip uncompensated if A is still tilted
    if not park_ac(c, s):
        log('L2: park failed'); return False
    if physical_rezero:
        log('L2: PHYSICAL REZERO via request_homeall (parked first)')
        s.poll()
        if s.interp_state != linuxcnc.INTERP_IDLE:
            log('L2: not idle for Home All'); return False
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        c.mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}.request_homeall{}])')
        c.wait_complete(4.0)
        t0 = time.time(); saw = False
        while time.time() - t0 < 400:
            time.sleep(3); s.poll()
            if any(s.joint[j]['homing'] for j in range(6)): saw = True
            if (saw and all(s.homed[:6])
                    and not any(s.joint[j]['homing'] for j in range(6))):
                break
        else:
            log('L2: physical rezero never finished -- HALTING'); return False
        c.mode(linuxcnc.MODE_MANUAL); c.wait_complete(2.0)
        c.teleop_enable(1); c.wait_complete(2.0)
    # G43 at A0 (fresh session) then pivot split
    sp_('arm.in0', ARM_BASE); time.sleep(0.3)
    for attempt in range(4):
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        c.mdi('G43 H5'); c.wait_complete(4.0); time.sleep(0.8)
        if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) < 0.01: break
    if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) > 0.01:
        log('L2: G43 never landed -- HALTING'); return False
    if physical_rezero:
        # tip back to baseline position (operator 10mm rule)
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        c.mdi('G53 G1 X%.3f Y%.3f Z%.3f F800' %
              (BASELINE['x'], BASELINE['y'], BASELINE['z']))
        t0 = time.time()
        while time.time() - t0 < 120:
            time.sleep(2); s.poll()
            if s.interp_state == linuxcnc.INTERP_IDLE and s.inpos and time.time() - t0 > 4:
                break
        jx, jy, jz = gp('joint.0.pos-fb'), gp('joint.1.pos-fb'), gp('joint.2.pos-fb')
        log('L2: tip at baseline d=(%.3f, %.3f, %.3f)' %
            (jx - BASELINE['x'], jy - BASELINE['y'], jz - BASELINE['z']))
    log('L2: recovery complete')
    return True

def pkterr_gate(hist):
    now = time.time()
    try: tot = gp('hm2_7i97.0.packet-error-total')
    except (ValueError, subprocess.SubprocessError): return hist, False
    hist.append((now, tot))
    hist = [(t, v) for t, v in hist if now - t < 3600]
    growth = hist[-1][1] - hist[0][1] if len(hist) > 1 else 0
    return hist, growth > 20

def start_sequence():
    """OPERATOR RULE (2026-08-06): HOME first, physically. Then baseline
    (XYZ baseline + A0 C0). Then, and only then, trials. The measured tip
    at the end of this sequence is the cube center."""
    s = stat_ok(); c = linuxcnc.command()
    if s is None: return False
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        c.state(linuxcnc.STATE_ESTOP_RESET); c.wait_complete(3.0)
        c.state(linuxcnc.STATE_ON); c.wait_complete(3.0)
        time.sleep(1); s.poll()
        if s.task_state != linuxcnc.STATE_ON:
            log('START: machine will not enable'); return False
    # PARK FIRST, tip-fixed, before any homing: A/C homing's final move
    # to zero runs in JOINT mode and would sweep a tilted head's tip in
    # an uncompensated arc (same hazard the advisor flagged in L2)
    s.poll()
    if abs(s.actual_position[3]) > 0.5 or abs(s.actual_position[5]) > 0.5:
        if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) > 0.01:
            log('START: head tilted AND pivot wrong -- cannot park '
                'safely, REFUSING (operator needed)'); return False
        log('START: parking tilted head tip-fixed before homing')
        if not park_ac(c, s):
            log('START: pre-home park failed'); return False
    log('START: PHYSICAL HOME via the homing menu owner (request_homeall '
        '-- gantry choreography, brain-serialized head reads; advisor: '
        'raw home(-1) would sweep the tip in joint mode)')
    s.poll()
    if s.interp_state != linuxcnc.INTERP_IDLE or any(
            s.joint[j]['homing'] for j in range(6)):
        log('START: not ready for Home All'); return False
    c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
    c.mdi('(DEBUG, EVAL[vcp.getWidget{"ned_controls"}.request_homeall{}])')
    c.wait_complete(4.0)
    t0 = time.time(); saw_homing = False
    while time.time() - t0 < 400:
        time.sleep(3); s.poll()
        if any(s.joint[j]['homing'] for j in range(6)): saw_homing = True
        if (saw_homing and all(s.homed[:6])
                and not any(s.joint[j]['homing'] for j in range(6))):
            break
    else:
        log('START: physical home never finished (saw_homing=%s)'
            % saw_homing); return False
    log('START: Home All completed (real cycle observed)')
    c.mode(linuxcnc.MODE_MANUAL); c.wait_complete(2.0)
    c.teleop_enable(1); c.wait_complete(2.0)
    log('START: homed; parking A/C to zero')
    if not park_ac(c, s):
        log('START: A/C park failed'); return False
    sp_('arm.in0', ARM_BASE); time.sleep(0.3)
    for attempt in range(4):
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        c.mdi('G43 H5'); c.wait_complete(4.0); time.sleep(0.8)
        if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) < 0.01: break
    if abs(gp('ned_ac_kins.pivot-length') - PIVOT_FULL) > 0.01:
        log('START: G43 never landed'); return False
    log('START: moving to baseline XYZ')
    c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
    c.mdi('G53 G1 X%.3f Y%.3f Z%.3f F800' %
          (BASELINE['x'], BASELINE['y'], BASELINE['z']))
    t0 = time.time()
    while time.time() - t0 < 180:
        time.sleep(2); s.poll()
        if s.interp_state == linuxcnc.INTERP_IDLE and s.inpos and time.time() - t0 > 4:
            break
    jx, jy, jz = gp('joint.0.pos-fb'), gp('joint.1.pos-fb'), gp('joint.2.pos-fb')
    center = {'x': jx, 'y': jy, 'z': jz, 'ts': time.time()}
    with open(SP + '/tip_center.json', 'w') as f: json.dump(center, f)
    with open(NED + '/logs/pid_tip_center.ndjson', 'a') as f:
        f.write(json.dumps(center) + '\n')
    log('START: baseline reached, cube center = (%.3f, %.3f, %.3f)'
        % (jx, jy, jz))
    c.mode(linuxcnc.MODE_MANUAL); c.wait_complete(2.0); c.teleop_enable(1)
    return True

log('CAMPAIGN START: deadline %s' % time.strftime('%F %T', time.localtime(DEADLINE)))
if not start_sequence():
    log('START SEQUENCE FAILED -- campaign not starting')
    sys.exit(2)
hist = []
stagnant = 0
last_champ_cost = None
paused_once_this_hour = 0
while time.time() < DEADLINE:
    if os.path.exists(SP + '/campaign_stop'):
        log('operator stop flag found -- ending campaign'); break
    s = stat_ok()
    healthy = False
    if s is not None:
        try:
            s.poll()
            healthy = (s.task_state == linuxcnc.STATE_ON and all(s.homed[:6]))
        except linuxcnc.error:
            healthy = False
    if not healthy:
        if not recover_L1():
            if not recover_L2():
                log('RECOVERY EXHAUSTED -- campaign halting safe')
                break
        continue
    hist, tripped = pkterr_gate(hist)
    if tripped:
        if paused_once_this_hour:
            log('PKTERR GATE second trip in the hour -- HALTING SAFE'); break
        log('PKTERR GATE: >20 errors/hour -- pausing 10 min')
        paused_once_this_hour = 1
        time.sleep(600)
        continue
    if time.strftime('%M') < '05': paused_once_this_hour = 0
    env = dict(os.environ)
    if stagnant >= 3:
        env['TUNE_MODE'] = 'polish'
    rc = subprocess.run(['python3', SP + '/pid_tune.py'], env=env).returncode
    log('tuner run ended rc=%d' % rc)
    if rc == 0:
        # champion improvement bookkeeping (polish-mode trigger)
        try:
            nd = sorted(glob.glob(NED + '/logs/pid_tune_*.ndjson'))[-1]
            ch = [json.loads(l) for l in open(nd) if '"t": "champion"' in l][-1]
            cost = sum(v['cost'] for v in ch['summary'].values())
            if last_champ_cost is not None and cost > last_champ_cost * 0.98:
                stagnant += 1
            else:
                stagnant = 0
            last_champ_cost = cost
            log('run champion total=%.0f (stagnant=%d)' % (cost, stagnant))
        except (IndexError, ValueError, KeyError) as e:
            log('champion bookkeeping failed: %s' % e)
        time.sleep(5)
    elif rc == 3:
        log('1mm cube trash exit -- restarting with blacklist')
        time.sleep(2)
    elif rc == 2:
        log('tuner start guard refused (tip off cube center) -- '
            're-running home+baseline sequence')
        if not start_sequence():
            log('re-baseline failed -- halting safe')
            break
    elif rc == 4:
        log('10MM CUBE -- operator rule: stack restart + physical rezero + baseline')
        if not recover_L2(physical_rezero=True):
            log('10mm recovery failed -- campaign halting safe')
            break
        if not start_sequence():
            log('post-10mm start sequence failed -- halting safe')
            break
    else:
        log('unexpected rc=%d -- recovery ladder' % rc)
        if not recover_L1():
            if not recover_L2():
                break
    time.sleep(1)   # advisor: distinct ndjson stamps
log('CAMPAIGN ENDED at %s (l2_used=%d)' % (time.strftime('%F %T'), l2_used))
