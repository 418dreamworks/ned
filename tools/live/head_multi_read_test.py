#!/usr/bin/env python3
"""IRON TEST: several A/C drive reads in ONE PB session, with a known jog of A
and C between reads. Part of the commissioning of ANY homing change.

    python3 tools/live/head_multi_read_test.py [--xy 1770,114] [--no-move]

Needs: PB up, machine ON, all joints homed, interpreter idle, spindle unloaded,
head free to move 1 deg. MOVES A and C by at most 1.5 deg and returns them to
where they started. --no-move takes the reads without jogging.

A read = a double-click on READ HEAD (3 s countdown): the brain unhomes A/C,
takes a fresh SEN read of C then A, and declares both in place.
--xy is the READ HEAD button's screen position; 1770,114 on the 8c9bba3 screen.

PASS, per read:
  - A and C unhome and come back homed within 45 s
  - the PktUART frame counter (parsed) advanced: the frames are NEW
  - the drive angle equals the joint position BEFORE the read (which includes
    the jog) within 0.05 deg -- so the number followed the move
  - hm2_7i97.0.packet-error-exceeded stays FALSE (the Mesa link is up)

Evidence is taken from HAL pins and linuxcnc.stat, never from lcnc.log: the
brain's stdout is block-buffered and the log lags by minutes.
First passed 2026-10-01 21:16 on ned 8c9bba3: seven reads, one session.
"""
import os
import subprocess
import sys
import time

import linuxcnc

os.environ.setdefault('DISPLAY', ':0')
TOL = 0.05
XY = '1770,114'
MOVE = '--no-move' not in sys.argv
if '--xy' in sys.argv:
    XY = sys.argv[sys.argv.index('--xy') + 1]
BX, BY = XY.split(',')
PLAN = [(1.0, 1.0), (-0.5, -1.5), (0.7, 0.2)] if MOVE else [(0.0, 0.0)] * 3

c = linuxcnc.command()
s = linuxcnc.stat()
fails = []


def getp(pin):
    r = subprocess.run(['halcmd', 'getp', pin], capture_output=True, text=True)
    return r.stdout.strip()


def link_down():
    return getp('hm2_7i97.0.packet-error-exceeded') == 'TRUE'


def read_head(n, expect_a, expect_c):
    p0 = int(getp('hm2_7i97.0.pktuart.0.parsed'))
    subprocess.run(['xdotool', 'mousemove', BX, BY, 'click', '--repeat', '2', '--delay', '120', '1'])
    t0 = time.time()
    unhomed = False
    while time.time() - t0 < 45:
        time.sleep(0.25)
        s.poll()
        if not (s.homed[4] or s.homed[5]):
            unhomed = True
        if unhomed and s.homed[4] and s.homed[5]:
            time.sleep(2)
            p1 = int(getp('hm2_7i97.0.pktuart.0.parsed'))
            da = float(getp('hm2_7i97.0.pktuart.0.deg-a'))
            dc = float(getp('hm2_7i97.0.pktuart.0.deg-c'))
            ok = p1 > p0 and abs(da - expect_a) <= TOL and abs(dc - expect_c) <= TOL and not link_down()
            print('READ %d  %s  drive A %+.4f (expected %+.4f)  drive C %+.4f (expected %+.4f)  '
                  'parsed %d->%d  %.0fs  %s' % (n, time.strftime('%T'), da, expect_a, dc, expect_c,
                                                 p0, p1, time.time() - t0, 'ok' if ok else 'FAIL'), flush=True)
            if not ok:
                fails.append('read %d' % n)
            return ok
    print('READ %d FAILED: A/C unhomed=%s, not back homed in 45 s; parsed %d->%s; link down=%s'
          % (n, unhomed, p0, getp('hm2_7i97.0.pktuart.0.parsed'), link_down()), flush=True)
    fails.append('read %d' % n)
    return False


def jog(jn, deg):
    if abs(deg) < 1e-6:
        return True
    s.poll()
    if s.task_state != linuxcnc.STATE_ON or not all(s.homed[:6]) or s.interp_state != linuxcnc.INTERP_IDLE:
        print('JOG refused: task_state=%s homed=%s interp=%s' % (s.task_state, s.homed[:6], s.interp_state))
        fails.append('jog refused')
        return False
    c.mode(linuxcnc.MODE_MANUAL)
    c.wait_complete()
    c.teleop_enable(0)
    c.wait_complete()
    start = s.joint_actual_position[jn]
    c.jog(linuxcnc.JOG_INCREMENT, True, jn, 1.0, deg)
    t0 = time.time()
    while time.time() - t0 < 20:
        time.sleep(0.3)
        s.poll()
        if abs(s.joint_actual_position[jn] - (start + deg)) < 0.002 and s.inpos:
            break
    print('JOG joint %d by %+.2f deg: %+.4f -> %+.4f' % (jn, deg, start, s.joint_actual_position[jn]), flush=True)
    if abs(s.joint_actual_position[jn] - (start + deg)) > 0.01:
        fails.append('jog joint %d did not arrive' % jn)
        return False
    return True


s.poll()
if s.task_state != linuxcnc.STATE_ON or not all(s.homed[:6]) or s.interp_state != linuxcnc.INTERP_IDLE:
    sys.exit('REFUSED: needs machine ON, joints 0-5 homed, interpreter idle '
             '(task_state=%s homed=%s interp=%s)' % (s.task_state, s.homed[:6], s.interp_state))
if link_down():
    sys.exit('REFUSED: hm2_7i97.0.packet-error-exceeded is TRUE -- the Mesa link is down, relaunch')
a0, c0 = s.joint_actual_position[4], s.joint_actual_position[5]
print('start: joint A %+.4f  joint C %+.4f' % (a0, c0))

n = 1
ok = read_head(n, a0, c0)
for da, dc in PLAN + [None]:
    if not ok:
        break
    s.poll()
    if da is None:                               # last leg: back to the start
        da, dc = a0 - s.joint_actual_position[4], c0 - s.joint_actual_position[5]
    if not (jog(4, da) and jog(5, dc)):
        break
    c.teleop_enable(1)
    c.wait_complete()
    time.sleep(2)
    s.poll()
    n += 1
    ok = read_head(n, s.joint_actual_position[4], s.joint_actual_position[5])

print('link: packet-error-exceeded=%s packet-error-total=%s' % (
    getp('hm2_7i97.0.packet-error-exceeded'), getp('hm2_7i97.0.packet-error-total')))
if fails or n < 5:
    print('FAIL: %d read(s) taken; %s' % (n, ', '.join(fails) or 'stopped early'))
    sys.exit(1)
print('PASS: %d fresh A/C drive reads in one session, each within %.2f deg of the joint' % (n, TOL))
