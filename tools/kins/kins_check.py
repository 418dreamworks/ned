#!/usr/bin/env python3
"""ned_ac_kins math verification (2026-08-05).

Re-run after ANY edit to ~/Documents/linuxcnc/src/emc/kinematics/
ned_ac_kins.c -- it must stay in lockstep with these formulas. Checks:
 1. comp forward == independent Rz(C)*Rx(A) derivation
 2. inverse(forward) == identity
 3. A=0  =>  TCP == identity for all C (seamless mode switch at upright)
Exit 0 = all pass.
"""
import math, random, sys
TO = math.pi / 180

def s2r(r, t, p):
    t *= TO; p *= TO
    return (r*math.sin(p)*math.cos(t), r*math.sin(p)*math.sin(t),
            r*math.cos(p))

def fwd(j, L, az=90.0, sign=1.0):
    x, y, z, a, c = j
    r = s2r(L, c + az, 180.0 - sign*a)
    return (x + r[0], y + r[1], z + L + r[2], a, c)

def inv(p, L, az=90.0, sign=1.0):
    x, y, z, a, c = p
    r = s2r(L, c + az, 180.0 - sign*a)
    return (x - r[0], y - r[1], z - L - r[2], a, c)

def fwd_ref(j, L):
    x, y, z, a, c = j
    a *= TO; c *= TO
    v = (0.0, L*math.sin(a), -L*math.cos(a))
    vx = v[0]*math.cos(c) - v[1]*math.sin(c)
    vy = v[0]*math.sin(c) + v[1]*math.cos(c)
    return (x + vx, y + vy, z + L + v[2], j[3], j[4])

def main():
    L = 200.0
    random.seed(1)
    w_ref = w_rt = 0.0
    for _ in range(20000):
        j = (random.uniform(-500, 500), random.uniform(-500, 500),
             random.uniform(-600, 0), random.uniform(-95, 95),
             random.uniform(-315, 315))
        p = fwd(j, L); pr = fwd_ref(j, L)
        w_ref = max(w_ref, max(abs(p[i]-pr[i]) for i in range(3)))
        rt = inv(p, L)
        w_rt = max(w_rt, max(abs(rt[i]-j[i]) for i in range(5)))
    ident = all(abs(fwd((1, 2, 3, 0, c), L)[i] - (1, 2, 3, 0, c)[i]) < 1e-12
                for c in range(-315, 316, 15) for i in range(3))
    print('ref-derivation worst: %.3e  round-trip worst: %.3e  '
          'A=0 identity: %s' % (w_ref, w_rt, ident))
    ok = w_ref < 1e-9 and w_rt < 1e-9 and ident
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
