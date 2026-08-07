#!/usr/bin/env python3
# PID minimization, campaign edition (operator 2026-08-06, 12-hour order).
# Advisor-audited: staged FF2 warm-start + four parallel elitist (1+2)-ES
# lineages, tamed mutations, two-tier tip-cube rule, persistent trash
# blacklist, resume-from-data, feed/accel-tagged trials.
# GOLDEN RULE: never delete data -- every writer is append-only; the
# originals file is write-once. v1 preserved as pid_tune_v1_preserved.py.
import subprocess, time, json, math, random, sys, atexit, signal, threading, glob, os
import linuxcnc

SP = '/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
LOGD = '/home/brains/Documents/ned/logs'
STAMP = time.strftime('%Y%m%d-%H%M%S')
ND = '%s/pid_tune_%s.ndjson' % (LOGD, STAMP)
PROG = open(SP + '/pid_tune_progress.log', 'a', buffering=1)
def log(m): PROG.write('%s %s\n' % (time.strftime('%H:%M:%S'), m)); print(m, flush=True)
def out(rec):
    rec.setdefault('ts', round(time.time(), 3))
    with open(ND, 'a') as f: f.write(json.dumps(rec) + '\n')

AXES = ('xw', 'y', 'z')          # gantry pair = ONE lineage (identical
PINAX = {'xw': ('x', 'w'), 'y': ('y',), 'z': ('z',)}   # gains, always)
GENES = ('Pgain', 'Igain', 'Dgain', 'FF1', 'FF2')
L_PIV = 320.77
BUDGET = 48
TEST_F = 800.0
TEST_ACCEL = 2.0
CUBE_HALF_MM = 0.5          # operator: 1 mm cube -> terminate + blacklist
CUBE10_HALF_MM = 5.0        # operator: 10 mm cube -> exit 4, full rezero
POLISH = os.environ.get('TUNE_MODE') == 'polish'
TRASH = LOGD + '/pid_tune_trash.ndjson'
ORIGF = LOGD + '/pid_original_gains.json'

def gp(p):
    return float(subprocess.run(['timeout', '3', 'halcmd', 'getp', p],
                                capture_output=True, text=True).stdout.strip())
def sp_(p, v):
    subprocess.run(['timeout', '3', 'halcmd', 'setp', p, '%.6g' % v],
                   capture_output=True)

# ORIGINALS: persisted once, never re-derived from live pins (advisor:
# pins hold the previous champion after a restart; bounds would
# random-walk overnight)
if os.path.exists(ORIGF):
    ORIG = json.load(open(ORIGF))
    if 'xw' not in ORIG:
        # old 4-axis schema on disk: normalize IN MEMORY only (golden
        # rule: the file is never rewritten)
        ORIG = {'xw': ORIG['x'], 'y': ORIG['y'], 'z': ORIG['z']}
    log('originals loaded from %s' % ORIGF)
else:
    ORIG = {ax: {g: gp('pid.%s.%s' % (PINAX[ax][0], g)) for g in GENES}
        for ax in AXES}   # xw seeds from x; the pair should never differ
    with open(ORIGF, 'x') as f: json.dump(ORIG, f, indent=1)
    log('originals captured to %s' % ORIGF)
out({'t': 'originals', 'genes': ORIG})

BOUNDS = {}
for ax in AXES:
    P0, I0 = ORIG[ax]['Pgain'], ORIG[ax]['Igain']
    BOUNDS[ax] = {'Pgain': (0.5 * P0, 2.0 * P0), 'Igain': (0.0, 3.0 * I0),
                  'Dgain': (0.0, 0.05), 'FF1': (0.95, 1.03),
                  'FF2': (0.0, 0.012)}
SIGSCALE = 0.5 if POLISH else 1.0
SIG0 = lambda ax: {'Pgain': 0.05 * SIGSCALE,
                   'Igain': 0.10 * max(ORIG[ax]['Igain'], 1.0) * SIGSCALE,
                   'Dgain': 0.0015 * SIGSCALE, 'FF1': 0.002 * SIGSCALE,
                   'FF2': 0.0004 * SIGSCALE}
STEP_CAP = lambda g: {'Pgain': 0.15 * g['Pgain'], 'Igain': 0.20 * max(g['Igain'], 1.0),
                      'Dgain': 0.005, 'FF1': 0.005, 'FF2': 0.001}

def load_trash():
    # old records carry per-axis x/w genes; normalize to the xw-lineage
    # schema (one entry per gantry variant, conservative: match either)
    t = []
    try:
        for ln in open(TRASH):
            try: g = json.loads(ln)['genes']
            except (ValueError, KeyError): continue
            if 'xw' in g:
                t.append(g)
            elif 'x' in g and 'y' in g and 'z' in g:
                t.append({'xw': g['x'], 'y': g['y'], 'z': g['z']})
                if 'w' in g and g['w'] != g['x']:
                    t.append({'xw': g['w'], 'y': g['y'], 'z': g['z']})
    except OSError: pass
    return t
TRASHLIST = load_trash()
def is_trash(cand):
    # advisor: range-normalized distance (exact match never fires on
    # fresh Gaussian draws)
    for tg in TRASHLIST:
        if all(abs(cand[ax][g] - tg[ax][g])
               / (BOUNDS[ax][g][1] - BOUNDS[ax][g][0] + 1e-12) < 0.05
               for ax in AXES for g in GENES):
            return True
    return False

champ = {ax: dict(ORIG[ax]) for ax in AXES}
def set_axis(ax, g):
    for pin in PINAX[ax]:
        for k in GENES: sp_('pid.%s.%s' % (pin, k), g[k])
def restore():
    # operator doctrine (2026-08-06 ~21:50): NOTHING is banked or left
    # applied -- the GA is a data instrument; the machine always rests
    # at the file-calibration originals. Champion lives in the ndjson.
    for ax in AXES: set_axis(ax, ORIG[ax])
    log('RESTORED pins to ORIGINALS (banked calibration; champion is data)')
atexit.register(restore)
signal.signal(signal.SIGTERM, lambda *a: sys.exit(1))

s = linuxcnc.stat(); c = linuxcnc.command()
# HARD START GUARDS (operator rules): correct pivot in force, tip inside
# the cube at its center, machine homed -- refuse to run otherwise
assert abs(gp('ned_ac_kins.pivot-length') - 320.7741) < 0.01, \
    'pivot wrong -- G43 not in force, REFUSING to run trials'
def _start_tip_guard():
    jx, jy, jz = (gp('joint.0.pos-fb'), gp('joint.1.pos-fb'),
                  gp('joint.2.pos-fb'))
    ja, jc = gp('joint.4.pos-fb'), gp('joint.5.pos-fb')
    tx, ty, tz = tip_from_joints(jx, jy, jz, ja, jc)
    d = max(abs(tx - TIP_BASE[0]), abs(ty - TIP_BASE[1]),
            abs(tz - TIP_BASE[2]))
    if d > CUBE_HALF_MM:
        log('START GUARD: tip %.3f mm from cube center -- REFUSING '
            '(exit 2: wrapper re-runs the home+baseline sequence)' % d)
        sys.exit(2)
    log('start guard: tip within %.3f mm of cube center' % d)
PINS = ['pid.x.error', 'pid.y.error', 'pid.z.error', 'pid.w.error',
        'joint.4.f-error', 'joint.5.f-error', 'joint.4.pos-fb',
        'joint.5.pos-fb', 'joint.0.pos-fb', 'joint.1.pos-fb',
        'joint.2.pos-fb']
# cube center = the tip's measured starting point after the campaign's
# HOME + baseline sequence (operator rule: "centered about its starting
# point"); banked baseline is the fallback only
try:
    _tc = json.load(open(SP + '/tip_center.json'))
    TIP_BASE = (_tc['x'], _tc['y'], _tc['z'])
except (OSError, ValueError, KeyError):
    TIP_BASE = (-423.100, -1112.600, -264.600)
    log('WARNING: no tip_center.json -- using banked baseline as cube center')
def tip_from_joints(jx, jy, jz, a_deg, c_deg):
    # forward kins with the TRUE L, independent of the live pin: catches
    # wrong-pivot, count-drift, any geometry-class failure
    t = math.radians(c_deg + 90.0); p = math.radians(180.0 - a_deg)
    rx = 320.7741 * math.sin(p) * math.cos(t)
    ry = 320.7741 * math.sin(p) * math.sin(t)
    rz = 320.7741 * math.cos(p)
    return (jx + rx, jy + ry, jz + 320.7741 + rz)
CMDF = SP + '/tune_cmds.txt'
open(CMDF, 'w').write(''.join('getp %s\n' % p for p in PINS))
_start_tip_guard()   # refuse to trial unless the tip starts inside the cube

class Sampler(threading.Thread):
    def __init__(self, base_peak):
        super().__init__(daemon=True)
        self.rows = []; self.stop_f = False; self.kill = None
        self.cube = False; self.cube10 = False
        self.base_peak = base_peak
    def run(self):
        cthr = linuxcnc.command()
        while not self.stop_f:
            r = subprocess.run(['timeout', '2', 'halcmd', '-f', CMDF],
                               capture_output=True, text=True).stdout.split()
            if len(r) == len(PINS):
                try:
                    v = [float(x) for x in r]
                    self.rows.append((time.time(), v))
                    tipx, tipy, tipz = tip_from_joints(
                        v[8], v[9], v[10], v[6], v[7])
                    dev = max(abs(tipx - TIP_BASE[0]),
                              abs(tipy - TIP_BASE[1]),
                              abs(tipz - TIP_BASE[2]))
                    rack = abs(v[0] - v[3])          # gantry differential
                    worst = max(dev, rack,
                                abs(v[0] + v[3]) / 2.0, abs(v[1]), abs(v[2]))
                    if worst > CUBE_HALF_MM:
                        cthr.abort()          # THE MOMENT MUST NOT PROCEED
                        self.cube = True
                        self.cube10 = worst > CUBE10_HALF_MM
                        self.stop_f = True
                        continue
                    if self.base_peak:
                        lv = {'xw': max(abs(v[0]), abs(v[3]), rack),
                              'y': abs(v[1]), 'z': abs(v[2])}
                        for ax in AXES:
                            if lv[ax] > 5 * self.base_peak[ax]:
                                self.kill = ax; self.stop_f = True
                except ValueError: pass
            time.sleep(0.045)

def mdi_retry(line, secs=8):
    for attempt in range(4):
        c.mode(linuxcnc.MODE_MDI); c.wait_complete(2.0)
        c.mdi(line)
        t0 = time.time()
        while time.time() - t0 < secs:
            time.sleep(0.5); s.poll()
            if s.interp_state != linuxcnc.INTERP_IDLE: return True
        log('mdi attempt %d dead: %s' % (attempt + 1, line))
    return False
def wait_idle(deadline):
    t0 = time.time()
    while time.time() - t0 < deadline:
        time.sleep(1); s.poll()
        if s.task_state != linuxcnc.STATE_ON: raise RuntimeError('machine dropped')
        if s.interp_state == linuxcnc.INTERP_IDLE and s.inpos and time.time() - t0 > 3:
            return time.time()
    raise RuntimeError('leg deadline')

BASE_PEAK = {}
ntrial = [0]
def run_trial(cand, tag):
    ntrial[0] += 1
    for ax in AXES: set_axis(ax, cand[ax])
    time.sleep(0.3)
    s.poll()
    assert s.task_state == linuxcnc.STATE_ON and all(s.homed[:6])
    pe0 = gp('hm2_7i97.0.packet-error-total')
    sam = Sampler(BASE_PEAK if BASE_PEAK else None); sam.start()
    stops = []
    okall = True
    for leg in ((60.0, 120.0, TEST_F), (0.0, 0.0, TEST_F)):
        if sam.cube or sam.kill: break        # advisor BLOCKER fix
        if not mdi_retry('o<tcp_pidt_ac> call [%.1f] [%.1f] [%.0f]' % leg):
            okall = False; break
        try: tdone = wait_idle(120)
        except RuntimeError as e:
            log('trial %d leg failed: %s' % (ntrial[0], e)); okall = False; break
        stops.append(tdone - 2.0)
        if sam.cube or sam.kill: break
    sam.stop_f = True; sam.join(2)
    if sam.cube:
        for ax in AXES: set_axis(ax, champ[ax])
        rec = {'t': 'trash', 'n': ntrial[0], 'tag': tag,
               'genes': {ax: {g: round(cand[ax][g], 6) for g in GENES}
                         for ax in AXES},
               'F': TEST_F, 'accel': TEST_ACCEL,
               'reason': '10mm cube' if sam.cube10 else '1mm cube',
               'ts': round(time.time(), 3)}
        with open(TRASH, 'a') as f: f.write(json.dumps(rec) + '\n')
        out(dict(rec))
        out({'t': 'raw', 'n': ntrial[0], 'pins': PINS,
             'rows': [[round(t, 3)] + [round(x, 6) for x in v]
                      for t, v in sam.rows]})
        if sam.cube10:
            log('TIP LEFT THE 10 MM CUBE -- TRASH recorded; exit 4: wrapper '
                'must RESTART STACK + PHYSICAL REZERO + baseline (operator rule)')
            sys.exit(4)
        log('TIP CUBE VIOLATION (1 mm) -- TRASH recorded, TERMINATING '
            '(restart resumes with it blacklisted)')
        sys.exit(3)
    if sam.kill:
        c.abort(); c.wait_complete(2.0)
        set_axis(sam.kill, champ[sam.kill])
        log('KILL-SWITCH on %s -- candidate lethal' % sam.kill)
    rows = sam.rows
    res = {}
    ERRIDX = {'y': (lambda v: v[1]), 'z': (lambda v: v[2]),
              'xw': (lambda v: max(abs(v[0]), abs(v[3]), abs(v[0] - v[3])))}
    for ax in AXES:
        f = ERRIDX[ax]
        es = [(t, f(v) * 1000) for t, v in rows]
        if not es:
            res[ax] = {'rms': -1, 'peak': -1, 'path_ms': -1, 'end_ms': -1,
                       'fliphz': -1, 'cost': float('inf')}
            continue
        endw = [e for t, e in es if any(st - 0.1 <= t <= st + 1.0 for st in stops)]
        path = [e for t, e in es if not any(st - 0.1 <= t <= st + 1.0 for st in stops)]
        ms = lambda v: sum(x * x for x in v) / len(v) if v else 0.0
        mean_r = sum(e for _, e in es) / len(es)
        flips = sum(1 for k in range(1, len(es)) if (es[k][1] - mean_r) * (es[k - 1][1] - mean_r) < 0)
        dur = max(es[-1][0] - es[0][0], 0.1)
        pk = max(abs(e) for _, e in es)
        lethal = (BASE_PEAK and (pk > 3 * BASE_PEAK[ax] * 1000
                  or flips / 2.0 / dur > 10.0))
        res[ax] = {'rms': round(math.sqrt(ms([e for _, e in es])), 2),
                   'peak': round(pk, 1),
                   'path_ms': round(ms(path), 2), 'end_ms': round(ms(endw), 2),
                   'fliphz': round(flips / 2.0 / dur, 1),
                   'cost': float('inf') if (lethal or not okall)
                           else ms(path) + ms(endw)}
    # EXACT tip metric, XYZ only (operator: A/C assumed perfect -- the
    # Yaskawas own those loops; f-errors stay in raw for reference)
    tip2 = [((v[0] + v[3]) / 2.0) ** 2 + v[1] ** 2 + v[2] ** 2 for _, v in rows]
    tip_ms = sum(tip2) / len(tip2) * 1e6 if tip2 else float('inf')
    out({'t': 'raw', 'n': ntrial[0], 'pins': PINS,
         'rows': [[round(t, 3)] + [round(x, 6) for x in v] for t, v in rows]})
    tot = sum(r['cost'] for r in res.values() if r['cost'] != float('inf'))
    out({'t': 'trial', 'n': ntrial[0], 'tag': tag, 'F': TEST_F,
         'accel': TEST_ACCEL,
         'genes': {ax: {g: round(cand[ax][g], 6) for g in GENES} for ax in AXES},
         'axes': res,
         'tip3d_um2': round(tip_ms, 1) if tip_ms != float('inf') else -1,
         'loopsum_um2': round(tot, 1),
         'pkterr_d': gp('hm2_7i97.0.packet-error-total') - pe0,
         'lethal': sam.kill})
    log('trial %2d [%s] cost xw=%.0f y=%.0f z=%.0f tip=%.0f um2'
        % (ntrial[0], tag, *[res[a]['cost'] if res[a]['cost'] != float('inf')
                             else -1 for a in AXES],
           tip_ms if tip_ms != float('inf') else -1))
    return {ax: res[ax]['cost'] for ax in AXES}

def clip(ax, g):
    return {k: min(BOUNDS[ax][k][1], max(BOUNDS[ax][k][0], g[k])) for k in GENES}
def mutate(ax, g, sig):
    o = dict(g); cap = STEP_CAP(g)
    for k in GENES:
        if random.random() < 0.4:
            if k == 'Pgain':
                nv = math.exp(math.log(max(g[k], 1e-9)) + random.gauss(0, sig[k]))
            else:
                nv = g[k] + random.gauss(0, sig[k])
            o[k] = min(g[k] + cap[k], max(g[k] - cap[k], nv))
    return clip(ax, o)
def cross(ax, a, b):
    return clip(ax, {k: (a[k] if random.random() < 0.5 else b[k]) for k in GENES})

def key(g): return json.dumps({k: round(g[k], 6) for k in GENES}, sort_keys=True)
evals = {ax: {} for ax in AXES}   # key -> {'g': genes, 'c': [costs]}
def fold(ax, g, cost):
    e = evals[ax].setdefault(key(g), {'g': dict(g), 'c': []})
    e['c'].append(cost)
def mean_cost(ax, g):
    e = evals[ax].get(key(g))
    if not e: return float('inf')
    v = [x for x in e['c'][-6:] if x != float('inf')]   # sliding window
    return sum(v) / len(v) if v else float('inf')

# ---- RESUME: ingest same-F/same-accel history (advisor design C)
base_trials = []; ff2_seen = 0
for f in sorted(glob.glob(LOGD + '/pid_tune_*.ndjson')):
    for ln in open(f):
        try: r = json.loads(ln)
        except ValueError: continue
        if r.get('t') != 'trial': continue
        if r.get('F') != TEST_F or r.get('accel') != TEST_ACCEL: continue
        if 'xw' not in r['genes']:
            continue   # pre-lineage-merge schema: not valid xw points
        for ax in AXES:
            cst = r['axes'][ax]['cost']
            if cst is None: cst = float('inf')
            fold(ax, r['genes'][ax], cst)
        if r['tag'].startswith('base'): base_trials.append(r)
        if r['tag'].startswith('ff2'): ff2_seen += 1
log('resume: %d prior same-F evals (y-axis), %d base, %d ff2, %d trash'
    % (sum(len(v['c']) for v in evals['y'].values()), len(base_trials),
       ff2_seen, len(TRASHLIST)))

# ---- Stage 0: baseline (reused from history when present)
if len(base_trials) >= 2:
    base = {ax: sum(r['axes'][ax]['cost'] for r in base_trials[-2:]) / 2
            for ax in AXES}
    noise = {ax: abs(base_trials[-1]['axes'][ax]['cost']
                     - base_trials[-2]['axes'][ax]['cost'])
             / max(base[ax], 1e-9) for ax in AXES}
    BASE_PEAK = {ax: max(max(r['axes'][ax]['peak'] for r in base_trials)
                         / 1000.0, 0.02) for ax in AXES}
    log('baseline reused from history')
else:
    c1 = run_trial({ax: ORIG[ax] for ax in AXES}, 'base1')
    last = json.loads([l for l in open(ND) if '"t": "trial"' in l][-1])
    BASE_PEAK = {ax: max(last['axes'][ax]['peak'] / 1000.0, 0.02) for ax in AXES}
    c2 = run_trial({ax: ORIG[ax] for ax in AXES}, 'base2')
    base = {ax: (c1[ax] + c2[ax]) / 2 for ax in AXES}
    noise = {ax: abs(c1[ax] - c2[ax]) / max(base[ax], 1e-9) for ax in AXES}
    for ax in AXES:
        fold(ax, ORIG[ax], c1[ax]); fold(ax, ORIG[ax], c2[ax])
log('baseline: ' + json.dumps({a: round(base[a], 1) for a in AXES})
    + ' noise: ' + json.dumps({a: round(noise[a], 2) for a in AXES}))

# ---- Stage A: FF2 warm-start (skipped when history has it)
if ff2_seen < 6:
    gridres = {ax: [] for ax in AXES}
    for v in (0.0, 0.0008, 0.0016, 0.0032, 0.0064, 0.0096):
        cand = {ax: clip(ax, dict(ORIG[ax], FF2=v)) for ax in AXES}
        cc = run_trial(cand, 'ff2=%g' % v)
        for ax in AXES:
            gridres[ax].append((v, cc[ax])); fold(ax, cand[ax], cc[ax])
    mid = {ax: (sorted(gridres[ax], key=lambda t: t[1])[0][0]
                + sorted(gridres[ax], key=lambda t: t[1])[1][0]) / 2 for ax in AXES}
    cand = {ax: clip(ax, dict(ORIG[ax], FF2=mid[ax])) for ax in AXES}
    cc = run_trial(cand, 'ff2-refine')
    for ax in AXES: fold(ax, cand[ax], cc[ax])
else:
    log('stage A skipped -- FF2 grid in history')

# archive/incumbent from ALL known evals (trash excluded)
arch = {}
for ax in AXES:
    pool = [e['g'] for e in evals[ax].values()
            if mean_cost(ax, e['g']) != float('inf')
            and not is_trash({a: (e['g'] if a == ax else ORIG[a]) for a in AXES})]
    pool = pool or [ORIG[ax]]
    arch[ax] = sorted({key(g): g for g in pool}.values(),
                      key=lambda g: mean_cost(ax, g))[:3]
inc = {ax: dict(arch[ax][0]) for ax in AXES}
champ = {ax: dict(arch[ax][0]) for ax in AXES}
for ax in AXES:
    log('incumbent %s: cost=%.0f FF2=%g FF1=%g P=%.1f'
        % (ax, mean_cost(ax, inc[ax]), inc[ax]['FF2'], inc[ax]['FF1'],
           inc[ax]['Pgain']))

# ---- Stage B: evolution
sig = {ax: SIG0(ax) for ax in AXES}
stag = 0; nofix = {ax: 0 for ax in AXES}; gen = 0
REEVAL_EVERY = 2 if POLISH else 4
while ntrial[0] < BUDGET - 4 and stag < 8:
    gen += 1
    o1 = {ax: mutate(ax, inc[ax], sig[ax]) for ax in AXES}
    o2 = {ax: (mutate(ax, cross(ax, *random.sample(arch[ax], 2)), sig[ax])
               if len(arch[ax]) > 1 else mutate(ax, inc[ax], sig[ax])) for ax in AXES}
    ok = False
    for _ in range(20):
        if not (is_trash(o1) or is_trash(o2)): ok = True; break
        o1 = {ax: mutate(ax, inc[ax], sig[ax]) for ax in AXES}
        o2 = {ax: mutate(ax, inc[ax], sig[ax]) for ax in AXES}
    if not ok:
        # advisor: NEVER run a trash match -- single-gene half-sigma
        # nudge off the incumbent; still trash => skip the generation
        gknob = random.choice(GENES)
        o1 = {ax: clip(ax, dict(inc[ax], **{gknob: inc[ax][gknob]
              + random.gauss(0, SIG0(ax)[gknob] / 2)})) for ax in AXES}
        o2 = {ax: dict(inc[ax]) for ax in AXES}
        if is_trash(o1):
            log('gen %d skipped -- trash-locked neighborhood' % gen)
            stag += 1
            continue
    ca = run_trial(o1, 'g%d-mut' % gen); cb = run_trial(o2, 'g%d-x' % gen)
    improved = False
    for ax in AXES:
        fold(ax, o1[ax], ca[ax]); fold(ax, o2[ax], cb[ax])
        best, cbest = min(((o1[ax], ca[ax]), (o2[ax], cb[ax])), key=lambda t: t[1])
        margin = max(0.5 * noise[ax] * mean_cost(ax, inc[ax]),
                     0.02 * mean_cost(ax, inc[ax]))   # advisor: floor 2%
        if cbest < mean_cost(ax, inc[ax]) - margin:
            inc[ax] = dict(best)
            for k in GENES: sig[ax][k] *= 1.3
            nofix[ax] = 0; improved = True
            log('gen %d: %s improved -> %.0f' % (gen, ax, cbest))
        else:
            nofix[ax] += 1
            if nofix[ax] >= 4:
                for k in GENES: sig[ax][k] = max(sig[ax][k] * 0.6, SIG0(ax)[k] / 10)
                nofix[ax] = 0
        pool = {key(g): g for g in arch[ax] + [o1[ax], o2[ax], inc[ax]]}
        arch[ax] = sorted(pool.values(), key=lambda g: mean_cost(ax, g))[:3]
    champ = {ax: dict(arch[ax][0]) for ax in AXES}
    stag = 0 if improved else stag + 1
    if gen % REEVAL_EVERY == 0 and ntrial[0] < BUDGET - 3:
        cc = run_trial(inc, 'reeval-g%d' % gen)
        for ax in AXES: fold(ax, inc[ax], cc[ax])

# ---- Final: champion confirmation x2
cand = {ax: arch[ax][0] for ax in AXES}
for i in range(2):
    cc = run_trial(cand, 'champ%d' % (i + 1))
    for ax in AXES: fold(ax, cand[ax], cc[ax])
for ax in AXES:
    champ[ax] = dict(sorted(arch[ax], key=lambda g: mean_cost(ax, g))[0])
restore()
summary = {ax: {'genes': champ[ax], 'cost': round(mean_cost(ax, champ[ax]), 1),
                'baseline': round(base[ax], 1)} for ax in AXES}
out({'t': 'champion', 'F': TEST_F, 'accel': TEST_ACCEL, 'summary': summary})
log('CHAMPION: ' + json.dumps(summary))
log('TUNE COMPLETE: %d trials -> %s' % (ntrial[0], ND))
