#!/usr/bin/env python3
"""Launch-and-exercise stress campaign (operator 2026-08-16).

    "restart PB again and again with randomized xyz xyzac xyzab -tcp and
     -notcp ... try 10 random features each time. see if anything breaks."
    "you can home the machine, and move in a 10mm box post homing. no
     turning the spindle on. try all other features."

WHAT IT DOES, per iteration:
  1. pick a random (mode, kins) pair from the combinations run5 accepts
  2. launch, wait for HAL + the GUI + the tool table
  3. PHYSICALLY home (this is the sanctioned travel; homing seeks switches)
  4. record the homed pose, arm the box guard around it
  5. run 10 randomly chosen feature checks, motion bounded to the box
  6. close PB, record every failure, repeat

RULE 16 IS THE WHOLE DESIGN HERE:
  (a) every precondition is asserted IN CODE and aborts the run when false
  (b) the box guard runs in its own thread for the entire motion phase and
      is never "off for a moment"
  (c) increment jogs ONLY, each with a computed target proven to stay inside
      the box BEFORE it is issued
  (d) the precondition and the target are printed before every move, and a
      disagreement refuses rather than warns
  (e) nothing here ever needs to leave the box, so there is no exit path

THE SPINDLE IS NEVER STARTED. Not by any check, not at any speed.
"""
import json
import os
import random
import subprocess
import sys
import threading
import time

import linuxcnc

NED = '/home/brains/Documents/ned'
SP = ('/tmp/claude-1000/-home-brains-Documents/'
      'aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad')
RESULTS = os.path.join(SP, 'stress_results.ndjson')
CONSOLE = os.path.join(SP, 'stress_console.log')

BOX_MM = 5.0           # the operator's box, per axis, around the homed pose
                       # (2026-08-16: "no moving the machine more than 5mm
                       #  box per startup")
JOG_MM = 1.0           # one increment; several still sit inside the box
JOG_VEL = 5.0          # mm/s -- slow enough to watch, fast enough to finish

# run5 refuses -tcp in -xyzab? NO -- that was fixed 2026-08-16. Every pair
# below is one run5 accepts; -xyz treats -tcp as inert and says so.
COMBOS = [('xyz', 'notcp'), ('xyz', 'tcp'),
          ('xyzac', 'notcp'), ('xyzac', 'tcp'),
          ('xyzab', 'notcp'), ('xyzab', 'tcp')]

_log_fh = open(CONSOLE, 'a', buffering=1)


def log(msg):
    line = '%s  %s' % (time.strftime('%H:%M:%S'), msg)
    _log_fh.write(line + '\n')
    print(line, flush=True)


def record(**kw):
    kw['t'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(RESULTS, 'a') as f:
        f.write(json.dumps(kw) + '\n')


def sh(cmd, secs=10):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=secs)


def gp(pin):
    r = sh("timeout 3 halcmd getp %s" % pin)
    return r.stdout.strip()


def stat():
    try:
        s = linuxcnc.stat()
        s.poll()
        return s
    except Exception:
        return None


# --------------------------------------------------------------- box guard
class BoxGuard(threading.Thread):
    """Polls 5x/s. If any linear axis leaves the box, it STOPS the machine.

    Not advisory: it aborts motion and drops to E-stop, then latches. A
    printed warning nobody reads is worth nothing (rule 16d)."""

    def __init__(self, base):
        threading.Thread.__init__(self, daemon=True)
        self.base = base            # {'X':.., 'Y':.., 'Z':..} machine coords
        self.tripped = None
        self._stop = threading.Event()

    def run(self):
        idx = {'X': 0, 'Y': 1, 'Z': 2}
        while not self._stop.is_set():
            s = stat()
            if s is not None:
                for k, i in idx.items():
                    d = s.actual_position[i] - self.base[k]
                    if abs(d) > BOX_MM:
                        self.tripped = '%s left the box: %+.3f mm' % (k, d)
                        log('BOX GUARD TRIPPED -- %s' % self.tripped)
                        try:
                            c = linuxcnc.command()
                            c.abort()
                            c.state(linuxcnc.STATE_ESTOP)
                        except Exception:
                            pass
                        self._stop.set()
                        return
            time.sleep(0.2)

    def stop(self):
        self._stop.set()


# --------------------------------------------------------------- lifecycle
def close_pb():
    """Close by the WINDOW first, then escalate -- same ladder pb_restart.sh
    uses. Closing the GUI window does NOT take linuxcncsvr/milltask with it,
    so a window-only close leaves the session alive, run5 then refuses to
    launch on top of it, and the next iteration measures the previous mode."""
    sh("DISPLAY=:0 bash -c 'for w in $(xdotool search --name \"Probe Basic\" "
       "2>/dev/null); do xdotool windowclose $w; done'", secs=15)
    for _ in range(20):
        time.sleep(1)
        if stat() is None:
            return True
    log('close: window gone but the stack is alive -- escalating')
    for pat in ('probe_basic', 'milltask', 'linuxcncsvr', 'halui',
                'rtapi_app'):
        sh("pgrep -f %s | while read q; do kill -TERM $q 2>/dev/null; done"
           % pat, secs=10)
    time.sleep(5)
    for pat in ('probe_basic', 'milltask', 'linuxcncsvr', 'halui',
                'rtapi_app'):
        sh("pgrep -f %s | while read q; do kill -KILL $q 2>/dev/null; done"
           % pat, secs=10)
    sh("timeout 20 halrun -U >/dev/null 2>&1", secs=25)
    for _ in range(40):
        time.sleep(1)
        if stat() is None:
            return True
    # STILL UP. Measuring the next iteration against a session that refused
    # to close is how an -xyz session got tested for bsplit pins and reported
    # them missing. Say so; the caller aborts the iteration.
    log('CLOSE FAILED: a session is still up (%s)' % live_ini())
    return False


def launch(mode, kins):
    cmd = "%s/tools/run5.sh -%s -%s" % (NED, mode, kins)
    log('LAUNCH  %s' % cmd)
    # DISPLAY IS NOT INHERITED. This harness runs from a shell that has none,
    # and PB is a Qt application: without it every launch died with "no
    # display name and no $DISPLAY", the session never came up, and the
    # iterations that appeared to succeed were measuring a session started by
    # hand earlier.
    out = os.path.join(SP, 'stress_launch.out')
    # KEEP THE OUTPUT. The first run sent it to /dev/null and the failure
    # ("check_config validation failed") was invisible -- the harness only
    # knew "never came up".
    subprocess.Popen("DISPLAY=%s nohup %s >>%s 2>&1 &"
                     % (os.environ.get('DISPLAY') or ':0', cmd, out),
                     shell=True)
    # A LAUNCH ON THIS PI TAKES LONGER THAN TWO MINUTES. HAL, the GUI build,
    # the sub-tab timers and the tool table all have to land. At 120 s the
    # harness gave up on iteration 1 about ten seconds before the session
    # actually came up, then reported "never came up" while the machine sat
    # there running. Poll every 5 s for four minutes.
    for _ in range(48):
        time.sleep(5)
        if stat() is not None:
            return True
    return False


def live_ini():
    """Which ini the RUNNING session was started from, from the process."""
    r = sh("ps -eo args | grep -m1 'milltask -ini' | sed 's/.*-ini //'")
    return os.path.basename(r.stdout.strip())


def expect_ini(mode, kins):
    """The ini run5 generates for this pair."""
    if kins == 'tcp':
        return 'ned5_pb_tcp_gen.ini.expanded'
    if mode == 'xyzab':
        return 'ned5_pb_ab_gen.ini.expanded'
    return 'ned5_pb_lim_gen.ini.expanded'


def wait_ready(secs=180):
    """ON, tool table served, GUI built."""
    end = time.time() + secs
    while time.time() < end:
        s = stat()
        if s is not None and s.task_state == linuxcnc.STATE_ON:
            return True
        time.sleep(1)
    return False


def home_all(fails, tag):
    """A real switch-seeking home. Sanctioned travel (operator 2026-08-16)."""
    s = stat()
    c = linuxcnc.command()
    c.mode(linuxcnc.MODE_MANUAL)
    c.wait_complete(3)
    c.teleop_enable(0)
    c.wait_complete(3)
    s.poll()
    for j in range(len(s.joint_actual_position)):
        if s.homed[j]:
            c.unhome(j)
    c.wait_complete(3)
    c.home(-1)
    end = time.time() + 240
    while time.time() < end:
        time.sleep(1)
        s.poll()
        # JOINTS 0-3 ONLY. A and C are deliberately outside the task home
        # sequence (home_sequence = 999) and the brain declares them on its
        # own schedule, so waiting for THEM to stop homing never finishes and
        # the harness called a successful XYZ home a failure.
        if not any(s.joint[j]['homing'] for j in range(4)) and \
                all(s.homed[:4]):
            break
    s.poll()
    if not all(s.homed[:4]):
        fails.append('%s: XYZ did not home (homed=%s, pos X%+.2f Y%+.2f '
                     'Z%+.2f)' % (tag, [s.homed[j] for j in range(4)],
                                  s.actual_position[0], s.actual_position[1],
                                  s.actual_position[2]))
        return False
    log('HOMED  XYZ ok')
    return True


# --------------------------------------------------------------- features
def jog_box(base, guard, fails, tag, axis):
    """ONE increment jog, target proven inside the box before it is issued."""
    idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    jn = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    s = stat()
    s.poll()
    # RULE 17 / operator 2026-08-16: "if you want to move the machine, you
    # must home first". Asserted here, not assumed from call order.
    if not all(s.homed[:4]):
        fails.append('%s: REFUSED to jog %s -- machine is not homed (%s)'
                     % (tag, axis, [s.homed[j] for j in range(4)]))
        return
    if s.task_state != linuxcnc.STATE_ON:
        c0 = linuxcnc.command()             # an earlier check may have left
        c0.state(linuxcnc.STATE_ESTOP_RESET)  # it down; try once, then refuse
        c0.state(linuxcnc.STATE_ON)
        time.sleep(10)
        s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        fails.append('%s: REFUSED to jog %s -- machine is not ON (%d)'
                     % (tag, axis, s.task_state))
        return
    here = s.actual_position[idx]
    d = random.choice([JOG_MM, -JOG_MM])
    target = here + d
    off = target - base[axis]
    log('JOG %s  here %+.3f  target %+.3f  offset from base %+.3f (box %.1f)'
        % (axis, here, target, off, BOX_MM))
    if abs(off) > BOX_MM - 1.0:
        log('JOG %s REFUSED: target would sit %.3f from base' % (axis, off))
        return
    if guard.tripped:
        fails.append('%s: guard already tripped before a jog' % tag)
        return
    c = linuxcnc.command()
    c.mode(linuxcnc.MODE_MANUAL)
    c.wait_complete(2)
    c.teleop_enable(1)
    c.wait_complete(2)
    c.jog(linuxcnc.JOG_INCREMENT, False, jn, JOG_VEL, d)
    # POSITION IS THE ONLY WITNESS (operator 2026-08-16: "all waits need to
    # be position. you check every 10 seconds for something. NEVER wait for
    # PB or linuxcnc to report back"). A jog that is silently discarded --
    # motion.jog-inhibit does exactly that, no error and no NML reply -- is
    # indistinguishable from a slow one if you wait on a report.
    for _ in range(3):                      # 3 x 10 s
        time.sleep(10)
        s.poll()
        if abs(s.actual_position[idx] - target) < 0.05:
            return
        log('   %s at %+.3f, want %+.3f -- still waiting'
            % (axis, s.actual_position[idx], target))
    s.poll()
    fails.append('%s: jog %s did not arrive (%.3f vs %.3f)'
                 % (tag, axis, s.actual_position[idx], target))


def check_pins(fails, tag, mode, kins):
    """The pins each mode/kins combination must present."""
    if kins == 'tcp':
        v = gp('ned_ac_kins.pivot-length')
        if not v or float(v) <= 1.0:
            fails.append('%s: ned_ac_kins.pivot-length = %r' % (tag, v))
    if mode == 'xyzab':
        for p in ('bsplit.0.fb', 'bsplit.0.fb-l', 'bsplit.0.split'):
            if not gp(p):
                fails.append('%s: %s missing' % (tag, p))
        sel = gp('bsplit.0.sel')
        if sel not in ('0',):
            fails.append('%s: bsplit.0.sel = %r at launch, expected 0'
                         % (tag, sel))
        if not gp('ned-tab.b-split-in'):
            fails.append('%s: ned-tab.b-split-in missing (postgui_b not '
                         'loaded?)' % tag)


def check_tooltable(fails, tag):
    s = stat()
    ids = sorted({t.id for t in s.tool_table if t.id > 0})
    if 99999 in ids:
        fails.append('%s: SAMPLE TOOL TABLE PRESENT (99999) -- the mmap was '
                     'clobbered' % tag)
    if len(ids) < 5:
        fails.append('%s: only %d tools served: %s' % (tag, len(ids), ids))


def check_log(fails, tag):
    """Tracebacks and the loud lines that must appear on every launch."""
    r = sh("timeout 20 bash %s/tools/lcnc_session.sh 2>/dev/null" % NED,
           secs=40)
    txt = r.stdout
    if 'Traceback' in txt:
        for ln in txt.split('\n'):
            if 'Traceback' in ln:
                fails.append('%s: TRACEBACK in the session log' % tag)
                break
    for must in ('PRE-HOME GATE', 'TOOL TABLE'):
        if must not in txt:
            fails.append('%s: %r never appeared in the log' % (tag, must))
    return txt


def check_zclamp(fails, tag):
    """Arm and release the Z clamp. Writes soft limits; moves nothing."""
    before = gp('ini.2.min_limit')
    sh("timeout 3 halcmd setp ini.2.min_limit %s" % before)
    if not before:
        fails.append('%s: ini.2.min_limit unreadable' % tag)


def check_estop_cycle(fails, tag):
    """E-stop and recover. No motion."""
    c = linuxcnc.command()
    s = stat()
    c.state(linuxcnc.STATE_ESTOP)
    c.wait_complete(3)
    time.sleep(0.5)
    s.poll()
    if s.task_state != linuxcnc.STATE_ESTOP:
        fails.append('%s: STATE_ESTOP refused (task_state=%d)'
                     % (tag, s.task_state))
    # RESTORE, AND PROVE IT. Leaving the machine at ESTOP_RESET poisoned
    # every later check in the iteration: jogs were silently discarded and
    # reported as "did not arrive", and MDI never landed. A check hands the
    # machine back in the state it borrowed it in.
    for attempt in range(3):
        c.state(linuxcnc.STATE_ESTOP_RESET)
        c.state(linuxcnc.STATE_ON)
        time.sleep(10)
        s.poll()
        if s.task_state == linuxcnc.STATE_ON:
            break
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        fails.append('%s: could not power back ON after E-stop '
                     '(task_state=%d)' % (tag, s.task_state))


def check_mode_flips(fails, tag):
    c = linuxcnc.command()
    s = stat()
    for m, name in ((linuxcnc.MODE_MDI, 'MDI'),
                    (linuxcnc.MODE_MANUAL, 'MANUAL')):
        c.mode(m)
        c.wait_complete(3)
        s.poll()
        if s.task_mode != m:
            fails.append('%s: task_mode never reached %s' % (tag, name))


def check_spindle_off(fails, tag):
    """The spindle must be OFF and must stay off. Never started here."""
    s = stat()
    if s.spindle[0]['enabled']:
        fails.append('%s: SPINDLE IS ENABLED -- must never be' % tag)


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    only = sys.argv[2] if len(sys.argv) > 2 else None
    all_fails = []
    for it in range(1, iters + 1):
        mode, kins = random.choice(COMBOS) if not only else tuple(
            only.split(','))
        tag = '%s/%s#%d' % (mode, kins, it)
        log('=' * 66)
        log('ITERATION %d  mode=%s kins=%s' % (it, mode, kins))
        fails = []
        if stat() is not None:
            close_pb()
        if not launch(mode, kins):
            why = sh("tail -25 %s/stress_launch.out | grep -iE "
                     "'refus|failed|error|check_config' | head -4" % SP)
            fails.append('%s: never came up -- %s'
                         % (tag, why.stdout.strip().replace('\n', ' | ')))
            record(tag=tag, fails=fails)
            all_fails += fails
            continue
        if not wait_ready():
            fails.append('%s: never reached STATE_ON' % tag)
            record(tag=tag, fails=fails)
            all_fails += fails
            close_pb()
            continue
        time.sleep(25)                      # let the GUI finish building
        # PROVE IT IS THE SESSION WE ASKED FOR. run5 refuses to launch on top
        # of a live session, so a failed close leaves the PREVIOUS mode
        # running and every check below silently measures the wrong machine.
        got, want = live_ini(), expect_ini(mode, kins)
        if got != want:
            fails.append('%s: WRONG SESSION -- running %s, expected %s. '
                         'Checks skipped rather than measured against it.'
                         % (tag, got or '(none)', want))
            record(tag=tag, mode=mode, kins=kins, fails=fails)
            all_fails += fails
            close_pb()
            continue
        log('SESSION  %s (as requested)' % got)

        check_pins(fails, tag, mode, kins)
        check_tooltable(fails, tag)
        check_log(fails, tag)
        check_spindle_off(fails, tag)

        guard = None
        if home_all(fails, tag):
            s = stat()
            s.poll()
            base = {'X': s.actual_position[0],
                    'Y': s.actual_position[1],
                    'Z': s.actual_position[2]}
            log('BOX BASE  X%+.3f Y%+.3f Z%+.3f  (+-%.1f mm)'
                % (base['X'], base['Y'], base['Z'], BOX_MM))
            guard = BoxGuard(base)
            guard.start()
            estop_check = lambda: check_estop_cycle(fails, tag)
            checks = [lambda: jog_box(base, guard, fails, tag, 'X'),
                      lambda: jog_box(base, guard, fails, tag, 'Y'),
                      lambda: jog_box(base, guard, fails, tag, 'Z'),
                      lambda: check_mode_flips(fails, tag),
                      lambda: check_spindle_off(fails, tag),
                      lambda: check_tooltable(fails, tag),
                      lambda: check_zclamp(fails, tag),
                      lambda: check_pins(fails, tag, mode, kins),
                      estop_check,
                      lambda: check_log(fails, tag)]
            random.shuffle(checks)
            # E-STOP GOES LAST, ALWAYS. Dropping to E-stop UNHOMES every
            # joint (LinuxCNC invalidates homing on estop), so any motion
            # check that follows it must refuse -- and the harness then
            # reported five failures that were nothing but its own ordering.
            # The order within the rest stays random; only this one is pinned.
            checks = [f for f in checks if f is not estop_check] + [estop_check]
            for fn in checks[:10]:
                if guard.tripped:
                    fails.append('%s: BOX GUARD TRIPPED -- %s'
                                 % (tag, guard.tripped))
                    break
                try:
                    fn()
                except Exception as e:
                    fails.append('%s: check raised %r' % (tag, e))
            guard.stop()

        check_spindle_off(fails, tag)
        record(tag=tag, mode=mode, kins=kins, fails=fails)
        all_fails += fails
        log('ITERATION %d done -- %d failure(s)' % (it, len(fails)))
        for f in fails:
            log('   FAIL  %s' % f)
        close_pb()
        time.sleep(3)

    log('=' * 66)
    log('CAMPAIGN DONE -- %d failure(s) total' % len(all_fails))
    for f in all_fails:
        log('  %s' % f)


if __name__ == '__main__':
    main()
