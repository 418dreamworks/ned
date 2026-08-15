#!/usr/bin/env python3
"""One 10-second B accel trial. Usage: b_accel_trial.py <accel deg/s2> [maxvel]

Sets joint 6's acceleration live (and the two stepgens' maxaccel to 2x, the
ratio the LinuxCNC manual asks for when backlash/steppers are involved),
runs 2.000 deg blocks for 10 s, aborts, and reports what B actually achieved.
The OPERATOR judges stalled / not stalled -- nothing on this machine can.
"""
import linuxcnc, subprocess, sys, time
REVERSE = '--reverse' in sys.argv
SHORT   = '--short' in sys.argv
SECS    = 10.0
for _a in sys.argv:
    if _a.startswith('--secs='): SECS = float(_a.split('=',1)[1])
argv = [a for a in sys.argv if not a.startswith('--')]
acc = float(argv[1]); vel = float(argv[2]) if len(argv) > 2 else 90.0
def setp(p, v):
    subprocess.run(['timeout','3','halcmd','setp',p,'%g'%v], capture_output=True)
s=linuxcnc.stat(); c=linuxcnc.command(); s.poll()
if s.task_state!=linuxcnc.STATE_ON: sys.exit('REFUSED: machine not ON')
if s.interp_state!=linuxcnc.INTERP_IDLE: sys.exit('REFUSED: busy')
if s.spindle[0]['enabled']: sys.exit('REFUSED: spindle enabled')
# B CANNOT MOVE UNLESS IT IS ARMED. R4 (the 70 V brick gate) is shared with
# the A/C absolute reads, so a head read -- or one that is failing and
# retrying -- leaves brain.b-armed FALSE and the stepgens disabled. The first
# version of this harness checked task_state only, so it happily reported a
# clean "0.00 deg/s" three times while B had no power at all. A trial that
# cannot move must refuse, not return a number.
def gp(pin):
    r = subprocess.run(['timeout','3','halcmd','getp',pin], capture_output=True, text=True)
    return r.stdout.strip()
if gp('brain.b-armed') != 'TRUE':
    sys.exit('REFUSED: brain.b-armed is %s -- B has no power. head-busy=%s, '
             'r4-select=%s. Check the A/C packs; the brain may be stuck in a '
             'failing head read.' % (gp('brain.b-armed'), gp('brain.head-busy'),
                                     gp('brain.r4-select')))
for pin in ('hm2_7i97.0.stepgen.00.enable','hm2_7i97.0.stepgen.01.enable'):
    if gp(pin) != 'TRUE': sys.exit('REFUSED: %s is FALSE -- no step can leave the FPGA' % pin)
a0=s.actual_position[3]; z0=s.actual_position[2]
# BOTH the joint AND the axis pin. Setting only ini.6.* changed nothing:
# a coordinated move is governed by [AXIS_B], and ini.b.max_acceleration
# stayed at 30 while the joint pin read 60, so trial 2 silently repeated
# trial 1 (operator caught it -- identical 5.45 vs 5.46).
setp('ini.6.max_acceleration', acc)
setp('ini.6.max_velocity', vel)
setp('ini.b.max_acceleration', acc)
setp('ini.b.max_velocity', vel)
setp('hm2_7i97.0.stepgen.00.maxaccel', acc*2)
setp('hm2_7i97.0.stepgen.01.maxaccel', acc*2)
setp('hm2_7i97.0.stepgen.00.maxvel',   vel*1.2)
setp('hm2_7i97.0.stepgen.01.maxvel',   vel*1.2)
# [TRAJ] MAX_VELOCITY IS A THIRD CEILING AND IT BEAT BOTH THE OTHERS. It is
# 333.334 (mm/s for the linear axes) and the trajectory planner applies it to
# the path magnitude whatever the units are, so a rotary-only move is capped
# at 333.334 deg/s. accel 240/maxvel 360 and accel 240/maxvel 540 therefore
# travelled the SAME 3372 deg in 10 s. [TRAJ] MAX_ANGULAR_VELOCITY = 45 is NOT
# a planner clamp -- B exceeded it by 7x -- it only feeds the GUI jog rates.
# Raised for the trial and PUT BACK below, because it is shared with X/Y/Z.
TRAJ_WAS = gp('ini.traj_max_velocity')
setp('ini.traj_max_velocity', max(vel*1.5, float(TRAJ_WAS)))
print('TRIAL  accel %.0f deg/s2   maxvel %.0f deg/s   (stepgen maxaccel %.0f)%s'
      % (acc, vel, acc*2, '   2.000 deg BLOCKS (groove pattern)' if SHORT else '   REVERSING +360/-360' if REVERSE else ''))
# COUNTDOWN. B is open loop -- the DRO counts steps SENT, so it reads motion
# into a stalled motor and no number this script prints is evidence of
# anything. The operator's eyes are the only instrument, so tell them exactly
# when to look: three white flashes on the standalone DRO, then the move.
flash = subprocess.run(['timeout','3','halcmd','getp','dro2.flash-in'],
                       capture_output=True, text=True).stdout.strip()
try:
    setp('dro2.flash-in', int(flash) + 1)
    print('  WATCH THE CHUCK -- 3 flashes on the DRO, then B moves')
    time.sleep(1.6)                      # 3 x 160 ms lit + 160 ms dark + margin
except ValueError:
    print('  (no dro2.flash-in -- no countdown; watch from now)')
# THE FEED WORD IS A LIMIT TOO, AND IT SILENTLY WON. On a rotary-only block
# F is deg/min, so the F5400 the first four trials carried was a hard 90
# deg/s ceiling -- accel 120/maxvel 180 and accel 240/maxvel 360 therefore
# both returned 90.5 deg/s and neither tested its maxvel at all. The program
# now carries F99999 (1666 deg/s) so only ini.b.* can bind.
BLOCK = 2.0 if SHORT else 1080.0
if SHORT:
    import math
    print('  2.000 deg blocks. Full stop at every boundary would average '
          '%.1f deg/s; anything above that is the planner blending.'
          % (math.sqrt(2*acc*2.0)/2.0))
FEED_LIMIT = 99999.0/60.0
if vel > FEED_LIMIT:
    sys.exit('REFUSED: maxvel %.0f exceeds the F word in the program (%.0f '
             'deg/s) -- the feed would be the limit, not the machine' % (vel, FEED_LIMIT))
ramp = vel*vel/(2.0*acc)
print('  ramp to full speed: %.1f deg (%.2f s) in a %.0f deg block'
      % (ramp, vel/acc, BLOCK))
if 2*ramp < BLOCK:
    print('  cruises %.1f deg at the full %.0f deg/s -- speed IS under test'
          % (BLOCK-2*ramp, vel))
else:
    print('  NEVER REACHES %.0f deg/s: needs %.0f deg of ramp -- speed is NOT '
          'under test at this pair' % (vel, 2*ramp))
c.mode(linuxcnc.MODE_AUTO); c.wait_complete(3)
PROG = ('/home/brains/linuxcnc/nc_files/b_accel_short.ngc'   if SHORT else
        '/home/brains/linuxcnc/nc_files/b_accel_reverse.ngc' if REVERSE else
        '/home/brains/linuxcnc/nc_files/b_accel_trial.ngc')
c.program_open(PROG); c.wait_complete(3)
b0=None; samples=[]; t0=time.time(); c.auto(linuxcnc.AUTO_RUN,0)
while time.time()-t0 < 12:
    time.sleep(0.02); s.poll()
    if b0 is None and s.interp_state != linuxcnc.INTERP_IDLE:
        b0 = s.actual_position[4]; tm = time.time()
    if abs(s.actual_position[3]-a0) > 0.01: c.abort(); sys.exit('ABORT: A MOVED')
    if abs(s.actual_position[2]-z0) > 0.05: c.abort(); sys.exit('ABORT: Z MOVED')
    if b0 is not None:
        samples.append((time.time(), s.actual_position[4], s.current_vel))
        if time.time()-tm >= SECS: break
c.abort(); c.wait_complete(5); time.sleep(1.5); s.poll()
span = abs(s.actual_position[4]-b0)
# NOT A MEASUREMENT OF THE SHAFT. position[4] is derived from the stepgen's
# own count of steps SENT, so it advances identically whether the motor turned
# or sat still (operator 2026-08-14: "if you look at DRO you will always see
# motion, so your shit is not info you want to rely on"). This line says what
# was COMMANDED. Whether it happened is the operator's call, every time.
path = sum(abs(samples[k][1]-samples[k-1][1]) for k in range(1, len(samples)))
print('  COMMANDED path %.1f deg in %.0f s = %.2f deg/s mean speed   (%.2f rev)'
      % (path, SECS, path/SECS, path/360.0))
if REVERSE:
    revs = sum(1 for k in range(2, len(samples))
               if (samples[k][2] < 1.0) and (samples[k-1][2] >= 1.0))
    print('  reversals completed: %d  (each one sheds and rebuilds %.0f deg/s)'
          % (revs, vel))
if samples:
    t_end = samples[-1][0]
    steady = sorted(v for (t, b, v) in samples if t > t_end - min(5.0, SECS*0.5))
    if steady:
        print('  PLANNER VELOCITY over the last 5 s: median %.1f  max %.1f  '
              'deg/s   (asked for %.0f)'
              % (steady[len(steady)//2], steady[-1], vel))
        if steady[-1] < vel*0.97:
            print('  IT NEVER GOT THERE -- something below %.0f is clamping'
                  % vel)
setp('ini.traj_max_velocity', float(TRAJ_WAS))
print('  [TRAJ] MAX_VELOCITY restored to %s' % TRAJ_WAS)
print('  DID IT TURN? -- nothing here can tell you; that is your call')
print('  B now %.3f     A %.4f (delta %.5f)'
      % (s.actual_position[4], s.actual_position[3], s.actual_position[3]-a0))
