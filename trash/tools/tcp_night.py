#!/usr/bin/env python3
"""tcp_night.py -- 500 randomized +-35 probe pairs, data-gathering only.

Operator 2026-08-06: "500 touches on each side at +-35. randomized guesses
for L and A. I just want to gather the data and stare at it in the morning.
make sure all data is saved."

Per pair (operator: "each time vary both L and A for the pair of touches.
vary A, probe Z at zero, gather data"): pick L ~ U[321.0, 325.0] (tip;
written to arm.in0 minus the live tool offset, ONLY with the head straight
by servo feedback), pick ofs ~ U[-0.30, +0.30] deg, then THREE touches:
Z at the pair's own zero (A = ofs), then +35+ofs, then -35+ofs -- all
incremental via the proven o<tcp_auto_step> repos=0 branch, no coordinate
frames anywhere. mp/mn are measured against THAT pair's own zero touch, so
the "remeasure the zero whenever it is nudged" rule holds for every sample
and the z0 series doubles as the thermal drift trace.

Every event is one JSON line in ned/logs/tcp_night_<stamp>.ndjson:
  {"t":"ref", ...}   the initial free-park reference
  {"t":"pair", "n":..., "L":..., "ofs":..., "z0":..., "zp":..., "zm":...,
   "mp":..., "mn":..., "sum":..., "diff":..., "tooloff":...}
  {"t":"miss"|"abort"|"end", ...}

Safety: preconditions asserted before every pair; a probe that does not
trip parks A0 + puck DOWN and exits loudly (no unattended hammering);
Ctrl-C and any error land in the same park path. NO SPINDLE ANYWHERE.
RUN:  python3 /home/brains/Documents/ned/tools/tcp_night.py
"""

import json
import random
import subprocess
import sys
import time

import linuxcnc

N_PAIRS = 500
L_LO, L_HI = 321.0, 325.0        # tip length range, mm
OFS_LO, OFS_HI = -0.30, 0.30     # A command-offset range, deg
PLUNGE_REF = 30.0                # first reference: operator parks ~1 in up
PLUNGE = 10.0
A_FEED = 300.0                   # deg/min
LOG = ('/home/brains/Documents/ned/logs/tcp_night_%s.ndjson'
       % time.strftime('%Y%m%d-%H%M%S'))

s = linuxcnc.stat()
c = linuxcnc.command()


def out(rec):
    rec['ts'] = time.strftime('%F %T')
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def hal_get(pin):
    r = subprocess.run(['timeout', '5', 'halcmd', 'getp', pin],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def hal_set(pin, val):
    subprocess.run(['timeout', '5', 'halcmd', 'setp', pin, '%.4f' % val],
                   capture_output=True)


def precheck():
    s.poll()
    assert s.task_state == 4, 'machine not ON'
    assert all(s.homed[:6]), 'not homed: %s' % (s.homed[:6],)
    r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                        'tool.mm.lock.out'], capture_output=True, text=True)
    assert not r.stdout.strip().upper().startswith('TRUE'), 'tool lock'


def wait_idle(deadline, tag):
    t0 = time.time()
    while True:
        time.sleep(0.4)
        s.poll()
        el = time.time() - t0
        if s.interp_state == linuxcnc.INTERP_IDLE and s.inpos and el > 1.2:
            return el
        if el > deadline:
            c.abort()
            raise RuntimeError('DEADLINE %.0fs in %s' % (deadline, tag))


def mdi(line, deadline, tag):
    s.poll()
    assert s.interp_state == linuxcnc.INTERP_IDLE and s.inpos, \
        'not idle before %s' % tag
    c.mode(linuxcnc.MODE_MDI)
    c.wait_complete(2.0)
    c.mdi(line)
    return wait_idle(deadline, tag)


def probe(plunge, tag):
    """Incremental probe via the proven sub. Returns machine Z at trip,
    or None on no-trip. repos=0: no frames, targa unused for motion."""
    s.poll()
    before = tuple(s.probed_position[:4])
    mdi('o<tcp_auto_step> call [0] [0] [0] [0] [0] [%.4f] [0]' % plunge,
        90, tag)
    s.poll()
    after = tuple(s.probed_position[:4])
    if all(abs(a - b) < 1e-6 for a, b in zip(before, after)):
        return None
    return after[2]


def rotate(a, tag):
    mdi('G1 A%.4f F%.1f' % (a, A_FEED), 60, tag)


def set_pivot(L_tip):
    """arm.in0 = tip - live tool offset. ONLY with the head straight."""
    fb = hal_get('joint.4.pos-fb')
    assert abs(fb) <= 0.05, 'pivot write refused: A=%.4f' % fb
    tooloff = hal_get('arm.in1')
    hal_set('arm.in0', L_tip - tooloff)
    return tooloff


def park(reason):
    try:
        c.abort()
        time.sleep(1.0)
        s.poll()
        wait_idle(30, 'park-settle')
    except Exception:
        pass
    for line, tag in (('G1 A0 F%.1f' % A_FEED, 'park-A0'),
                      ('M65 P3', 'puck-down'), ('M50 P1', 'fo-restore')):
        try:
            mdi(line, 60, tag)
        except Exception as e:
            out({'t': 'park-error', 'step': tag, 'err': str(e)})
    try:
        c.mode(linuxcnc.MODE_MANUAL)
        c.wait_complete(2.0)
    except Exception:
        pass
    out({'t': 'end', 'reason': reason})


def main():
    random.seed()
    precheck()
    s.poll()
    out({'t': 'start', 'n_pairs': N_PAIRS, 'L': [L_LO, L_HI],
         'ofs': [OFS_LO, OFS_HI],
         'pos': [round(v, 4) for v in s.actual_position[:4]],
         'pivot': hal_get('ned_ac_kins.pivot-length'),
         'tooloff': hal_get('arm.in1')})

    # puck UP, and it stays up for the whole night
    mdi('M64 P3', 30, 'puck-up')
    mdi('G4 P1.5', 30, 'puck-dwell')

    rotate(0.0, 'A0-initial')
    zref = probe(PLUNGE_REF, 'reference')
    if zref is None:
        raise RuntimeError('reference probe did not trip -- not over the '
                           'puck? nothing started')
    out({'t': 'ref', 'z': zref})

    t_start = time.time()
    for n in range(1, N_PAIRS + 1):
        precheck()
        L = random.uniform(L_LO, L_HI)
        ofs = random.uniform(OFS_LO, OFS_HI)
        # pivot write only at TRUE zero (servo-fb guarded), then the pair's
        # own zero touch at A = ofs
        rotate(0.0, 'A0-%d' % n)
        tooloff = set_pivot(L)
        rotate(ofs, 'zero-%d' % n)
        z0 = probe(PLUNGE, 'z0-%d' % n)
        if z0 is None:
            out({'t': 'miss', 'n': n, 'side': 'zero', 'L': L, 'ofs': ofs})
            raise RuntimeError('zero touch missed at pair %d' % n)

        rotate(35.0 + ofs, 'plus-%d' % n)
        zp = probe(PLUNGE, 'p+%d' % n)
        if zp is None:
            out({'t': 'miss', 'n': n, 'side': '+35', 'L': L, 'ofs': ofs})
            raise RuntimeError('+35 probe missed at pair %d' % n)

        rotate(-35.0 + ofs, 'minus-%d' % n)
        zm = probe(PLUNGE, 'p-%d' % n)
        if zm is None:
            out({'t': 'miss', 'n': n, 'side': '-35', 'L': L, 'ofs': ofs})
            raise RuntimeError('-35 probe missed at pair %d' % n)

        mp, mn = zp - z0, zm - z0
        el = time.time() - t_start
        out({'t': 'pair', 'n': n, 'L': round(L, 4), 'ofs': round(ofs, 4),
             'z0': round(z0, 4), 'zp': round(zp, 4),
             'zm': round(zm, 4), 'mp': round(mp, 4), 'mn': round(mn, 4),
             'sum': round(abs(mp) + abs(mn), 4),
             'diff': round(mp - mn, 4), 'tooloff': round(tooloff, 4),
             'eta_h': round((el / n) * (N_PAIRS - n) / 3600.0, 2)})

    rotate(0.0, 'A0-final')
    park('COMPLETE: %d pairs' % N_PAIRS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        park('operator Ctrl-C')
        sys.exit(1)
    except Exception as e:
        out({'t': 'abort', 'err': str(e)})
        park('ERROR: %s' % e)
        sys.exit(2)
