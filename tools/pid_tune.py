#!/usr/bin/env python3
# PID minimization (operator 2026-08-06: minimize L2 tip error, all axes
# counted, knobs = X/Y/Z/W loops only, L and A-side untouched; "some
# genetic algorithm"). Advisor design: staged FF2 warm-start, then four
# parallel elitist (1+2)-ES lineages with archive + crossover + noise
# margin. Every trial appended to ndjson for the operator.
import subprocess, time, json, math, random, sys, atexit, signal, threading
import linuxcnc

SP = '/tmp/claude-1000/-home-brains-Documents/aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad'
STAMP = time.strftime('%Y%m%d-%H%M%S')
ND = '/home/brains/Documents/ned/logs/pid_tune_%s.ndjson' % STAMP
PROG = open(SP + '/pid_tune_progress.log', 'a', buffering=1)
def log(m): PROG.write('%s %s\n' % (time.strftime('%H:%M:%S'), m)); print(m, flush=True)
def out(rec):
    rec['ts'] = round(time.time(), 3)
    with open(ND, 'a') as f: f.write(json.dumps(rec) + '\n')

AXES = ('x', 'y', 'z', 'w')
GENES = ('Pgain', 'Igain', 'Dgain', 'FF1', 'FF2')
L_PIV = 320.77
BUDGET = 48

def gp(p):
    return float(subprocess.run(['timeout', '3', 'halcmd', 'getp', p],
                                capture_output=True, text=True).stdout.strip())
def sp_(p, v):
    subprocess.run(['timeout', '3', 'halcmd', 'setp', p, '%.6g' % v],
                   capture_output=True)

ORIG = {ax: {g: gp('pid.%s.%s' % (ax, g)) for g in GENES} for ax in AXES}
log('originals: ' + json.dumps(ORIG))
out({'t': 'originals', 'genes': ORIG})

BOUNDS = {}
for ax in AXES:
    P0, I0 = ORIG[ax]['Pgain'], ORIG[ax]['Igain']
    BOUNDS[ax] = {'Pgain': (0.5 * P0, 2.0 * P0), 'Igain': (0.0, 3.0 * I0),
                  'Dgain': (0.0, 0.05), 'FF1': (0.95, 1.03),
                  'FF2': (0.0, 0.012)}
SIG0 = lambda ax: {'Pgain': 0.10, 'Igain': 0.20 * max(ORIG[ax]['Igain'], 1.0),
                   'Dgain': 0.003, 'FF1': 0.004, 'FF2': 0.0008}

champ = {ax: dict(ORIG[ax]) for ax in AXES}
def set_axis(ax, g):
    for k in GENES: sp_('pid.%s.%s' % (ax, k), g[k])
def restore():
    for ax in AXES: set_axis(ax, champ[ax])
    log('RESTORED pins to champion-so-far')
atexit.register(restore)
signal.signal(signal.SIGTERM, lambda *a: sys.exit(1))

s = linuxcnc.stat(); c = linuxcnc.command()
PINS = ['pid.x.error', 'pid.y.error', 'pid.z.error', 'pid.w.error',
        'joint.4.f-error', 'joint.5.f-error', 'joint.4.pos-fb']
CMDF = SP + '/tune_cmds.txt'
open(CMDF, 'w').write(''.join('getp %s\n' % p for p in PINS))

class Sampler(threading.Thread):
    def __init__(self, base_peak):
        super().__init__(daemon=True)
        self.rows = []; self.stop_f = False; self.kill = None
        self.base_peak = base_peak
    def run(self):
        while not self.stop_f:
            r = subprocess.run(['timeout', '2', 'halcmd', '-f', CMDF],
                               capture_output=True, text=True).stdout.split()
            if len(r) == len(PINS):
                try:
                    v = [float(x) for x in r]
                    self.rows.append((time.time(), v))
                    if self.base_peak:
                        for i, ax in enumerate(AXES):
                            if abs(v[i]) > 5 * self.base_peak[ax]:
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
    for leg in ((60.0, 120.0, 450.0), (0.0, 0.0, 450.0)):
        if not mdi_retry('o<tcp_pidt_ac> call [%.1f] [%.1f] [%.0f]' % leg):
            okall = False; break
        try: tdone = wait_idle(90)
        except RuntimeError as e:
            log('trial %d leg failed: %s' % (ntrial[0], e)); okall = False; break
        stops.append(tdone - 2.0)
        if sam.kill: break
    sam.stop_f = True; sam.join(2)
    if sam.kill:
        c.abort(); c.wait_complete(2.0)
        set_axis(sam.kill, champ[sam.kill])
        log('KILL-SWITCH on %s -- candidate lethal' % sam.kill)
    rows = sam.rows
    res = {}
    for i, ax in enumerate(AXES):
        es = [(t, v[i] * 1000) for t, v in rows]           # um
        if not es: res[ax] = {'cost': float('inf')}; continue
        endw = [e for t, e in es if any(st - 0.1 <= t <= st + 1.0 for st in stops)]
        path = [e for t, e in es if not any(st - 0.1 <= t <= st + 1.0 for st in stops)]
        ms = lambda v: sum(x * x for x in v) / len(v) if v else 0.0
        mean_r = sum(e for _, e in es) / len(es)
        flips = sum(1 for k in range(1, len(es)) if (es[k][1] - mean_r) * (es[k - 1][1] - mean_r) < 0)
        dur = max(es[-1][0] - es[0][0], 0.1)
        pk = max(abs(e) for _, e in es)
        lethal = (sam.kill == ax or (BASE_PEAK and (pk > 3 * BASE_PEAK[ax] * 1000
                  or flips / 2.0 / dur > 10.0)))
        res[ax] = {'rms': round(math.sqrt(ms([e for _, e in es])), 2),
                   'peak': round(pk, 1),
                   'path_ms': round(ms(path), 2), 'end_ms': round(ms(endw), 2),
                   'fliphz': round(flips / 2.0 / dur, 1),
                   'cost': float('inf') if (lethal or not okall)
                           else ms(path) + ms(endw)}
    # untuned rotary tip terms (counted, not optimized)
    ra = [abs(v[4]) for _, v in rows]; rc = [abs(v[5]) for _, v in rows]
    aa = [v[6] for _, v in rows]
    rot = 0.0
    if ra:
        rot = sum((L_PIV * math.radians(a)) ** 2 for a in ra) / len(ra) * 1e6
        rot += sum((L_PIV * abs(math.sin(math.radians(p))) * math.radians(cv)) ** 2
                   for p, cv in zip(aa, rc)) / len(rc) * 1e6
    tot = sum(r['cost'] for r in res.values() if r['cost'] != float('inf'))
    out({'t': 'trial', 'n': ntrial[0], 'tag': tag,
         'genes': {ax: {g: round(cand[ax][g], 6) for g in GENES} for ax in AXES},
         'axes': res, 'rot_um2': round(rot, 1),
         'total_um2': round(tot + rot, 1),
         'pkterr_d': gp('hm2_7i97.0.packet-error-total') - pe0,
         'lethal': sam.kill})
    log('trial %2d [%s] cost x=%.0f y=%.0f z=%.0f w=%.0f rot=%.0f um2'
        % (ntrial[0], tag, *[res[a]['cost'] if res[a]['cost'] != float('inf')
                             else -1 for a in AXES], rot))
    return {ax: res[ax]['cost'] for ax in AXES}

def clip(ax, g):
    o = {}
    for k in GENES:
        lo, hi = BOUNDS[ax][k]
        o[k] = min(hi, max(lo, g[k]))
    return o
def mutate(ax, g, sig):
    o = dict(g)
    for k in GENES:
        if random.random() < 0.8:
            if k == 'Pgain':
                o[k] = math.exp(math.log(max(g[k], 1e-9)) + random.gauss(0, sig[k]))
            else:
                o[k] = g[k] + random.gauss(0, sig[k])
    return clip(ax, o)
def cross(ax, a, b):
    return clip(ax, {k: (a[k] if random.random() < 0.5 else b[k]) for k in GENES})

# ---- Stage 0: baseline x2
c1 = run_trial({ax: ORIG[ax] for ax in AXES}, 'base1')
# base peaks from trial 1 (mm units in sampler kill; store in mm)
# re-derive from ndjson record just written:
last = json.loads(open(ND).read().strip().split('\n')[-1])
BASE_PEAK = {ax: max(last['axes'][ax]['peak'] / 1000.0, 0.02) for ax in AXES}
c2 = run_trial({ax: ORIG[ax] for ax in AXES}, 'base2')
base = {ax: (c1[ax] + c2[ax]) / 2 for ax in AXES}
noise = {ax: abs(c1[ax] - c2[ax]) / max(base[ax], 1e-9) for ax in AXES}
log('baseline: ' + json.dumps({a: round(base[a], 1) for a in AXES})
    + ' noise: ' + json.dumps({a: round(noise[a], 2) for a in AXES}))
evals = {ax: {json.dumps(ORIG[ax], sort_keys=True): [c1[ax], c2[ax]]} for ax in AXES}
def key(g): return json.dumps({k: round(g[k], 6) for k in GENES}, sort_keys=True)
def fold(ax, g, cost):
    evals[ax].setdefault(key(g), []).append(cost)
def mean_cost(ax, g):
    v = [x for x in evals[ax].get(key(g), [float('inf')]) if x != float('inf')]
    return sum(v) / len(v) if v else float('inf')

# ---- Stage A: FF2 warm-start
gridres = {ax: [] for ax in AXES}
for v in (0.0, 0.0008, 0.0016, 0.0032, 0.0064, 0.0096):
    cand = {ax: clip(ax, dict(ORIG[ax], FF2=v)) for ax in AXES}
    cc = run_trial(cand, 'ff2=%g' % v)
    for ax in AXES:
        gridres[ax].append((v, cc[ax])); fold(ax, cand[ax], cc[ax])
mid = {}
for ax in AXES:
    sr = sorted(gridres[ax], key=lambda t: t[1])
    mid[ax] = (sr[0][0] + sr[1][0]) / 2
cand = {ax: clip(ax, dict(ORIG[ax], FF2=mid[ax])) for ax in AXES}
cc = run_trial(cand, 'ff2-refine')
inc = {}
for ax in AXES:
    fold(ax, cand[ax], cc[ax])
    opts = [dict(ORIG[ax], FF2=v) for v, _ in gridres[ax]] + [cand[ax]]
    inc[ax] = clip(ax, min(opts, key=lambda g: mean_cost(ax, g)))
    log('stage A winner %s: FF2=%g cost=%.0f' % (ax, inc[ax]['FF2'], mean_cost(ax, inc[ax])))
champ = {ax: dict(inc[ax]) for ax in AXES}

# ---- Stage B: evolution
arch = {ax: sorted({key(g): g for g in
        [ORIG[ax], inc[ax]]}.values(), key=lambda g: mean_cost(ax, g))[:3] for ax in AXES}
sig = {ax: SIG0(ax) for ax in AXES}
stag = 0; nofix = {ax: 0 for ax in AXES}; gen = 0
while ntrial[0] < BUDGET - 4 and stag < 8:
    gen += 1
    o1 = {ax: mutate(ax, inc[ax], sig[ax]) for ax in AXES}
    o2 = {ax: (mutate(ax, cross(ax, *random.sample(arch[ax], 2)), sig[ax])
               if len(arch[ax]) > 1 else mutate(ax, inc[ax], sig[ax])) for ax in AXES}
    ca = run_trial(o1, 'g%d-mut' % gen); cb = run_trial(o2, 'g%d-x' % gen)
    improved = False
    for ax in AXES:
        fold(ax, o1[ax], ca[ax]); fold(ax, o2[ax], cb[ax])
        best, cbest = min(((o1[ax], ca[ax]), (o2[ax], cb[ax])), key=lambda t: t[1])
        margin = max(0.5 * noise[ax] * mean_cost(ax, inc[ax]),
                     0.05 * mean_cost(ax, inc[ax]))
        if cbest < mean_cost(ax, inc[ax]) - margin:
            inc[ax] = best
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
    if gen % 4 == 0 and ntrial[0] < BUDGET - 3:
        cc = run_trial(inc, 'reeval-g%d' % gen)
        for ax in AXES: fold(ax, inc[ax], cc[ax])

# ---- Final: champion confirmation x2
cand = {ax: arch[ax][0] for ax in AXES}
for i in range(2):
    cc = run_trial(cand, 'champ%d' % (i + 1))
    for ax in AXES: fold(ax, cand[ax], cc[ax])
for ax in AXES:
    pool = sorted(arch[ax], key=lambda g: mean_cost(ax, g))
    champ[ax] = dict(pool[0])
restore()
summary = {ax: {'genes': champ[ax], 'cost': round(mean_cost(ax, champ[ax]), 1),
                'baseline': round(base[ax], 1)} for ax in AXES}
out({'t': 'champion', 'summary': summary})
log('CHAMPION: ' + json.dumps(summary))
log('TUNE COMPLETE: %d trials -> %s' % (ntrial[0], ND))
