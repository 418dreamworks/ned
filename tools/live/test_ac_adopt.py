#!/usr/bin/env python3
"""THE GUARD ON A/C HOMING. Run it; do not reason about it.

Operator 2026-09-28, after a Home All left the head 21 deg off with the DRO
reading 0: "the 4 steps are. read (eg, 21). set to 21. move -21. check that
new position is zero." ... "somehow, protect that code so your future fucking
self doesn't break it."

This is that protection. It fails if:
  - ac_adopt_verdict stops refusing a mismatch, a bad drive read, or None
  - ac_to_zero stops CALLING it
  - the step-4 re-read (verify_ax) is dropped from either exit path
  - the tolerance is quietly widened

NO HAL, NO QT, NO MACHINE. Pure text + a pure function, so it runs anywhere
and there is no excuse for skipping it.

    python3 tools/live/test_ac_adopt.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.normpath(os.path.join(
    HERE, '..', '..', 'configs', 'ned5_pb', 'user_tabs',
    'ned_controls', 'ned_controls.py'))

fails = []


def check(name, cond, detail=''):
    print('%-52s %s' % (name, 'ok' if cond else 'FAILED'))
    if not cond:
        fails.append('%s%s' % (name, (' -- ' + detail) if detail else ''))


# ---- load ac_adopt_verdict WITHOUT importing the Qt module -----------------
src = open(CTRL).read()
m = re.search(r"^AC_ADOPT_TOL_DEFAULT = .*?^def ac_adopt_verdict\(.*?"
              r"(?=^\S)", src, re.M | re.S)
if not m:
    print('ac_adopt_verdict NOT FOUND in ned_controls.py -- '
          'the A/C adopt check has been removed. See its docstring.')
    sys.exit(1)
ns = {}
exec(compile(m.group(0), CTRL, 'exec'), ns)
verdict = ns['ac_adopt_verdict']
TOL = ns['AC_ADOPT_TOL_DEFAULT']

# ---- the behaviour ---------------------------------------------------------
check('tolerance is still 0.05 deg', abs(TOL - 0.05) < 1e-12, 'got %r' % TOL)

ok, _ = verdict(0.0, 0.0, True)
check('agreeing adopt passes', ok)

ok, why = verdict(0.0, 20.996, True)
check('THE 2026-09-28 CASE: joint 0, drive +20.996 -> REFUSED', not ok, why)

# C on 2026-09-28 read -0.0351 against an adopt of 0. That is INSIDE the
# 0.05 tolerance -- the same threshold M6 uses for "head is square" -- so it
# passes, and should. C had the identical defect as A; it was invisible only
# because the head happened to be sitting within the noise of zero. The check
# is not there to catch 0.035 deg, it is there to catch the 21.
ok, _ = verdict(0.0, -0.0351, True)
check('the real C reading -0.0351 is inside tolerance', ok)
ok, why = verdict(0.0, -0.9, True)
check('C genuinely off (drive -0.9) -> REFUSED', not ok, why)

ok, _ = verdict(20.996, 20.996, True)
check('a correct adopt of +20.996 passes', ok)

ok, why = verdict(0.0, 0.0, False)
check('drive read not ok -> REFUSED', not ok, why)

ok, why = verdict(0.0, None, True)
check('drive reading None -> REFUSED', not ok, why)

ok, why = verdict(None, 0.0, True)
check('no joint position -> REFUSED', not ok, why)

ok, _ = verdict(0.0, 0.049, True)
check('0.049 deg apart is inside tolerance', ok)
ok, _ = verdict(0.0, 0.051, True)
check('0.051 deg apart is outside tolerance', not ok)

# ---- the wiring: the check must actually be CALLED -------------------------
body = re.search(r"def ac_to_zero\(self, ax(?:, verify=True)?\):.*?\n    def ", src, re.S)
body = body.group(0) if body else ''
check('ac_to_zero calls ac_adopt_verdict',
      'ac_adopt_verdict(' in body)
check('ac_to_zero refuses on a bad verdict',
      re.search(r"if not ok:.*?return False", body, re.S) is not None)
check('ac_to_zero reads the drive, not just the joint',
      '_head_drive_deg(' in body)
check('step 4 is armed on the already-at-zero exit',
      body.count('verify_ax=vx') >= 2,
      'found %d of 2 verify_ax=vx call sites' % body.count('verify_ax=vx'))
check('_head_drive_deg reads the PktUART absolute stream',
      "hm2_7i97.0.pktuart.0.deg-" in src)
settle = re.search(r"def _teleop_restore_when_still\(self, label, "
                   r"verify_ax=None(?:, secs=15\.0)?\):.*?\n    def ", src, re.S)
settle = settle.group(0) if settle else ''
check('the settle path hands step 4 to a FRESH read (_verify_wait)',
      '_verify_wait(label, list(verify_ax)' in settle)
verify = re.search(r"def _verify_wait\(self, label, axes, then\):.*?\n    # ====", src, re.S)
verify = verify.group(0) if verify else ''
check('_verify_wait pulses the brain for a new SEN read',
      "getPin('verify-out').value = True" in verify)
check('_verify_wait judges only a read the brain ACCEPTED (verify-count)',
      "verify-count-in" in verify and '_judge_zero(label, ax)' in verify)
judge = re.search(r"def _judge_zero\(self, label, ax\):.*?\n    def ", src, re.S)
judge = judge.group(0) if judge else ''
check('_judge_zero reads the drive', '_head_drive_deg(ax)' in judge)
check('step 4 shouts when the drive is not at zero',
      'STEP 4 FAILED' in verify and 'STEP 4 FAILED' in judge)
check('Home A&C verifies once, after C, never in A\'s baseblock',
      "ac_to_zero('a', verify=False)" in src and "ac_to_zero('c', verify='ac')" in src)
check('the Home All chain verifies A and C once, at the end',
      "_verify_wait('HOME ALL CHAIN', ['a', 'c']" in src)

print()
if fails:
    print('%d CHECK(S) FAILED -- A/C homing is no longer verified against '
          'the drive:' % len(fails))
    for f in fails:
        print('  ' + f)
    sys.exit(1)
print('all checks pass -- A/C homing still verifies against the drive')
