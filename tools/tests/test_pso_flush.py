#!/usr/bin/env python3
# BARRIER 2 verification: does hr_start's pso-reset rising edge actually
# reach pso_live and zero multiturn/within? Real board, NO motion, no
# LinuxCNC (refuses if a session is up). Sequence mirrors ned_brain:
#   idle: enable=0 reset=0  ->  hr_start: enable=1 THEN reset=1
# PASS = multiturn/within read 0/0 after the edge, having been non-zero.
import subprocess, tempfile, os, sys, re

if subprocess.run(['tools/machine_idle.sh'], capture_output=True,
                  text=True).stdout.find('not running') < 0:
    sys.exit('REFUSING: LinuxCNC is up -- a second hm2_eth would fight it')

hal = tempfile.mktemp(suffix='.hal'); log = tempfile.mktemp(suffix='.log')
open(hal, 'w').write('''loadrt hostmot2
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=10 num_pwmgens=6 num_stepgens=4 num_inmuxs=1 num_pktuarts=1 sserial_port_0=0xxxxxxx"
loadrt pso_live names=hm2_7i97.0.pktuart.0
loadrt threads name1=servo period1=1000000
addf hm2_7i97.0.read              servo
addf hm2_7i97.0.pktuart.0.pso-live servo
addf hm2_7i97.0.write             servo
setp hm2_7i97.0.7i84.0.0.output-04 0
setp hm2_7i97.0.7i84.0.0.output-05 1
setp hm2_7i97.0.pktuart.0.enable 1
setp hm2_7i97.0.pktuart.0.reset 0
start
loadusr -w sleep 2
setp hm2_7i97.0.7i84.0.0.output-04 1
loadusr -w sleep 6
setp hm2_7i97.0.7i84.0.0.output-04 0
loadusr -w sleep 2
setp hm2_7i97.0.7i84.0.0.output-04 1
loadusr -w sleep 6
getp hm2_7i97.0.pktuart.0.parsed
getp hm2_7i97.0.pktuart.0.multiturn
getp hm2_7i97.0.pktuart.0.within
setp hm2_7i97.0.pktuart.0.enable 0
loadusr -w sleep 1
setp hm2_7i97.0.pktuart.0.enable 1
setp hm2_7i97.0.pktuart.0.reset 1
loadusr -w sleep 1
getp hm2_7i97.0.pktuart.0.parsed
getp hm2_7i97.0.pktuart.0.multiturn
getp hm2_7i97.0.pktuart.0.within
setp hm2_7i97.0.pktuart.0.reset 0
setp hm2_7i97.0.7i84.0.0.output-04 0
setp hm2_7i97.0.7i84.0.0.output-05 0
exit
''')
subprocess.run(['halrun', '-U'], capture_output=True)
r = subprocess.run(['timeout', '60', 'halrun', '-f', hal],
                   capture_output=True, text=True)
subprocess.run(['halrun', '-U'], capture_output=True)
out = r.stdout + r.stderr
open(log, 'w').write(out)
nums = [int(m) for m in re.findall(r'^(-?\d+)$', out, re.M)]
print('numbers seen:', nums)
if len(nums) >= 6:
    before, after = (nums[1], nums[2]), (nums[4], nums[5])
    print('BEFORE mt/within = %s   AFTER the reset edge = %s' % (before, after))
    if before == (0, 0):
        print('INCONCLUSIVE: no frame parsed (pins already empty)')
    elif after == (0, 0):
        print('BARRIER 2 PASS: the reset edge zeroed the pins')
    else:
        print('BARRIER 2 FAIL: pins survived the edge -- flush never fired')
else:
    print('halrun gave too few values; tail:', out.strip()[-300:])
