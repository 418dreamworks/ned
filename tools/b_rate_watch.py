#!/usr/bin/env python3
"""Time the four sweeps of b_rate_test.ngc and print the actual deg/s.

WHY: the kakeya groove is 3620 back-to-back B-only blocks of 2.000 deg at
F2700 (= 45 deg/s on a rotary-only block) and it ran far slower than that.
Raising F cannot help if the planner never reaches the commanded speed on
short blocks, and raising acceleration is not available -- B is two steppers
on a 1:20 worm with no encoder, so a stall is silent. This measures whether
the trajectory planner carries speed across short blocks.

RUN IT YOURSELF, alongside the program:

    python3 /home/brains/Documents/ned/tools/b_rate_watch.py

Start it FIRST, then press Cycle Start on b_rate_test.ngc. It prints a line
per pass and exits when the program ends. Ctrl-C stops it early.

WHAT TO LOOK FOR. All four passes travel the same 180 deg at the same
commanded feed; only the block size differs. Pass 4 is one long move and is
the control -- it should reach 45 deg/s.

    pass 4 fast, passes 1-2 much slower  -> the planner is stopping at
                                            block boundaries; lookahead
    all four about equal                 -> blending is fine, look elsewhere

Arithmetic to compare against, with [AXIS_B] MAX_ACCELERATION = 30 deg/s^2:

    full 45 deg/s        -> 180 deg in about  4.0 s (plus ramps)
    stop every 2.000 deg -> sqrt(2*30*2) = 10.95   -> about 16.4 s
    stop every 1.000 deg -> sqrt(2*30*1) =  7.75   -> about 23.2 s
"""
import sys
import time

try:
    import linuxcnc
except ImportError:
    sys.exit('linuxcnc python module not available -- run this on the machine')

# B is axis index 4 in the XYZABCUVW ordering. COORDINATES here is
# X Y Z X A C B, so the AXIS letter B is index 4 and C is 5 -- checked
# against stat.actual_position on 2026-08-13, do not "fix" this to 5.
B = 4
PASSES = [('1', '90 blocks x 2.000 deg'),
          ('2', '180 blocks x 1.000 deg'),
          ('3', '18 blocks x 10.000 deg'),
          ('4', '1 block x 180.000 deg  (control)')]
SWEEP = 180.0
POLL = 0.05


def main():
    s = linuxcnc.stat()
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        print('machine is not ON -- power up first')
        return 1

    print('waiting for motion... start b_rate_test.ngc now (Ctrl-C to quit)')
    b0 = s.actual_position[B]
    while True:
        time.sleep(POLL)
        s.poll()
        if abs(s.actual_position[B] - b0) > 0.05:
            break
        b0 = s.actual_position[B]

    start = time.time()
    origin = b0
    print('\nB started at %.3f deg\n' % origin)
    print('%-6s %-34s %9s %11s %11s'
          % ('pass', 'blocks', 'seconds', 'deg/s', 'vs 45 deg/s'))

    peak = 0.0
    for idx, (name, desc) in enumerate(PASSES):
        target = origin + SWEEP * (idx + 1)
        t0 = time.time()
        last_b, last_t = s.actual_position[B], t0
        while True:
            time.sleep(POLL)
            s.poll()
            b, t = s.actual_position[B], time.time()
            if t > last_t:
                rate = abs(b - last_b) / (t - last_t)
                peak = max(peak, rate)
            last_b, last_t = b, t
            # done when this sweep's travel is complete, or the program ended
            if abs(b - origin) >= SWEEP * (idx + 1) - 0.5:
                break
            if s.interp_state == linuxcnc.INTERP_IDLE and t - t0 > 2.0:
                print('%-6s %-34s %9s %11s   program ended early'
                      % (name, desc, '-', '-'))
                return 0
        dt = time.time() - t0
        rate = SWEEP / dt if dt > 0 else 0.0
        print('%-6s %-34s %9.2f %11.2f %10.0f%%'
              % (name, desc, dt, rate, 100.0 * rate / 45.0))

    print('\npeak instantaneous rate seen: %.2f deg/s' % peak)
    print('[AXIS_B] MAX_VELOCITY = 90, [TRAJ] MAX_ANGULAR_VELOCITY = 45,')
    print('MAX_ACCELERATION = 30 deg/s^2, ARC_BLEND_OPTIMIZATION_DEPTH = 500')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nstopped')
