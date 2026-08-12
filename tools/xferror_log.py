#!/usr/bin/env python3
"""Log X-axis following error so a cutting load can be seen in it.

Operator 2026-08-12: "read the encoder errors on X axis. i want to see if we
can see blips where the wood engages the bit" ... "do this for the next
20mins, 5hz is plenty".

X IS TWO JOINTS. The gantry is joints 0 (aft) and 3 (fore) and they are
logged separately: a cutting load that is off the gantry centre shows up
differently on the two sides, and averaging them would hide exactly that.
Y, Z and B are logged alongside so a blip can be placed on the workpiece
rather than just on the clock.

THE FORCE IS IN THE TORQUE COMMAND, NOT THE POSITION ERROR. A stiff
position loop answers a cutting load by pushing harder, not by moving: the
error stays inside one encoder count while pid.x.output -- the +/-10 V
velocity command on pwmgen.00 -- carries the whole disturbance. ux and uw
are the two gantry sides (pid.x = joint 0, pid.w = joint 3).

IDLE BASELINE MEASURED 2026-08-12 with the machine stopped: mean +0.0014 mm,
sd 0.0034, peak-to-peak 0.020 on joint 0 -- that is the encoder quantisation
floor, and anything a cut does has to rise above it to be real.
"""
import linuxcnc, hal, time, sys, os, atexit

OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/brains/Documents/ned/logs/xferror.csv'
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
HZ = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

# A HAL COMPONENT IS REQUIRED BEFORE hal.get_value WORKS. Without one the
# call raises "Cannot call before creating component" and the logger dies on
# its first sample. The component owns no pins -- it exists only so this
# process is allowed to read HAL -- and is left unready so nothing can wait
# on it. NOTE hal.get_value takes the global HAL mutex; at 5 Hz that is
# harmless, but this must never be raised to servo rates from userspace
# (a leaked mutex hung ned_brain on 2026-07-31).
# UNIQUE NAME PER RUN: a killed logger can leave its component
# registered, and the next launch then dies on a name clash.
_c = hal.component('xferror_log_%d' % os.getpid())
_c.ready()
atexit.register(lambda: _c.unready())

s = linuxcnc.stat()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
dt = 1.0 / HZ
t0 = time.time()
n = 0
with open(OUT, 'w', buffering=1) as f:
    f.write('t,fe0,fe3,ex,ew,ux,uw,x,y,z,b,vel,spindle_on,spindle_rpm\n')
    while time.time() - t0 < SECS:
        try:
            s.poll()
            f.write('%.3f,%.6f,%.6f,%+.7f,%+.7f,%+.6f,%+.6f,%.4f,%.4f,%.4f,%.3f,%.4f,%d,%.0f\n' % (
                time.time() - t0,
                s.joint[0]['ferror_current'], s.joint[3]['ferror_current'],
                hal.get_value('pid.x.error'), hal.get_value('pid.w.error'),
                hal.get_value('pid.x.output'), hal.get_value('pid.w.output'),
                s.actual_position[0], s.actual_position[1],
                s.actual_position[2], s.actual_position[4],
                s.current_vel,
                1 if s.spindle[0]['enabled'] else 0,
                s.spindle[0]['speed']))
            n += 1
        except Exception as e:
            f.write('# poll failed: %s\n' % e)
            time.sleep(1.0)
        time.sleep(dt)
print('xferror_log: %d samples over %.0f s -> %s' % (n, time.time() - t0, OUT))
