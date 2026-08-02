#!/usr/bin/env python3
# ned_brain.py -- GUI-independent machine orchestration (userspace HAL + NML).
# The DEVELOPED LOGIC ported out of the retired nedgui handler, verbatim where
# possible, so it runs identically under Probe Basic (or any GUI):
#
#   1. Head A/C absolute read (pso_live queued reads): R4 mux -> flush -> SEN
#      LOW >=1.3 s -> SEN rising edge -> parse burst; early-exit on first parse;
#      stale-read + range guards; feeds ini.4/5.home_offset live; PARKS R4
#      (output-05, also the 70 V rotary-brick gate) de-energized after EVERY read.
#   2. Read triggers: once at startup (display) and at every machine-ON
#      transition (fresh offsets before the operator can press home).
#   3. Post-home verify: when A+C finish homing, re-read both; >0.05 deg off ->
#      one unhome+rehome correction round; still off -> joints left UNHOMED and
#      the operator gets an on-screen error (NML error_msg -> PB notification).
#   4. Stored homing: saves joints 0-3 to stored_home.json every 10 s while
#      homed + at rest. Under a *resume* ini (run5.sh resume, operator already
#      consented at launch): validates + arms ini.0-3.home/home_offset at start;
#      if arming is impossible it ABORTS any homing attempt on joints 0-3
#      (an un-armed in-place home would silently relabel machine zero).
#   5. Teleop recovery: re-enter teleop on machine-ON (all homed), and return
#      task to MANUAL + teleop when a program/MDI call finishes (MPG stays live).
#   6. Event log: appends to ned/gui.md (same format the nedgui handler wrote)
#      so self-monitoring keeps working. Does NOT consume the NML error channel
#      (Probe Basic displays those itself).
#
# Constants live where rule 11 puts them: zero counts in
# configs/params/head_zero.inc, gear ratios in tools/live/ned_params.sh -- parsed at
# start, never copied here.
import os
import re
import time
import json

import hal
import linuxcnc

NED = '/home/brains/Documents/ned'
GUI_LOG = os.path.join(NED, 'gui.md')
SH_FILE = os.path.join(NED, 'configs/ned5/stored_home.json')
HEAD_ZERO_INC = os.path.join(NED, 'configs/params/head_zero.inc')
NED_PARAMS = os.path.join(NED, 'tools/live/ned_params.sh')

R_COUNTS = 67108864            # 2^26 counts per motor rev
SIGN = {'a': -1, 'c': 1}       # axis direction convention (was nedgui HEAD_ZERO)
LIM = {'a': 115.0, 'c': 315.0}  # reject reads outside the soft limits

HR_TICK = 0.25       # s; the head-read state machine cadence
HR_ST_RISE = 7       # tick that raises SEN (low window 1.5 s > manual's 1.3 s)
HR_ST_TIMEOUT = 28   # ~5 s after the rise with no parse -> report no-frame
HR_VERIFY_TOL = 0.05  # deg


def log(msg):
    line = '{}  {}'.format(time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print('ned_brain: ' + msg, flush=True)
    try:
        with open(GUI_LOG, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def parse_head_zero():
    # head_zero.inc [HEAD_ABS_ZERO]: A_MULTITURN/A_WITHIN/C_MULTITURN/C_WITHIN
    vals = {}
    with open(HEAD_ZERO_INC) as f:
        for ln in f:
            m = re.match(r'([AC])_(MULTITURN|WITHIN)\s*=\s*(-?\d+)', ln)
            if m:
                vals[(m.group(1).lower(), m.group(2))] = int(m.group(3))
    return {ax: (vals[(ax, 'MULTITURN')], vals[(ax, 'WITHIN')]) for ax in ('a', 'c')}


def parse_gears():
    g = {}
    with open(NED_PARAMS) as f:
        for ln in f:
            m = re.match(r'GEAR_([AC])=([0-9.]+)', ln)
            if m:
                g[m.group(1).lower()] = float(m.group(2))
    return g


HEAD_M0W0 = parse_head_zero()
GEAR = parse_gears()

h = hal.component('brain')
for _p in ('sen-suppress', 'sen-force', 'pso-enable', 'pso-reset', 'r4-select'):
    h.newpin(_p, hal.HAL_BIT, hal.HAL_OUT)
# pso_live values arrive on OUR OWN netted pins (postgui_pb.hal) -- instance
# access only. NEVER hal.get_value() here: it spins on the global HAL mutex,
# and a leaked mutex silently hung this very loop mid-verify (2026-07-31
# 14:31:39). Types match pso_live.comp:36-39.
h.newpin('parsed-in', hal.HAL_U32, hal.HAL_IN)
h.newpin('multiturn-in', hal.HAL_S32, hal.HAL_IN)
h.newpin('within-in', hal.HAL_U32, hal.HAL_IN)
# rising edge = the REF ALL button was pressed (ned-tab.homeall-out). The A/C
# cycle runs ONLY on this -- per-axis X/Y/Z refs must not move the head.
h.newpin('homeall-in', hal.HAL_BIT, hal.HAL_IN)
# rising edge = REF A / REF C button (one-axis REF ALL, operator 2026-08-01):
# unhome that joint -> fresh read -> home THAT joint only -> verify it only.
h.newpin('tcactive-in', hal.HAL_BIT, hal.HAL_IN)
h.newpin('ref-a-in', hal.HAL_BIT, hal.HAL_IN)
h.newpin('ref-c-in', hal.HAL_BIT, hal.HAL_IN)
h.ready()

# LOUD DEATH: 2026-08-01 19:40 launch, brain+pendant both vanished silently
# minutes after start (no traceback anywhere) and the operator's HOME ALL
# wedged unsupervised. Name the killer next time: log every signal and exit.
import atexit
import signal
import sys


def _death(signum, frame):
    log('ned_brain EXIT on signal %d (%s)'
        % (signum, signal.Signals(signum).name))
    sys.exit(128 + signum)


for _s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
    signal.signal(_s, _death)
atexit.register(lambda: log('ned_brain exited (atexit; normal interpreter exit)'))


class Brain(object):
    def __init__(self):
        self.stat = linuxcnc.stat()
        self.cmd = linuxcnc.command()
        ini = os.path.basename(os.environ.get('INI_FILE_NAME', ''))
        self.resume_mode = 'resume' in ini
        self.resume_armed = False
        # head read state machine
        self.hr_step = 0
        self.hr_axis = 'c'
        self.hr_cb = None
        self.hr_cb_delay = 0
        self.hr_deg = {}
        self.hr_p0 = 0
        self.hr_p1 = 0
        self.hr_lastraw = None
        # verify / homing
        self.hv_attempt = 0
        self.prev_ac_homed = False
        self.correcting = False
        # stored homing saver
        self.sh_last = None
        self.sh_last_t = 0.0
        self.sh_next = 0.0
        # transitions
        self.prev_on = False
        self.prev_interp_busy = False
        self.prev_task_mode = None
        self.done_since = None
        self.flip_armed = False
        self.start_t = time.time()
        self.teleop_at = None
        self.on_settled = 0.0     # no reads before this (power-on EMI transient)
        # parallel-read bookkeeping (operator request 2026-07-31: read A/C
        # WHILE XYZ homes, not before -- "im restarting and rehoming a lot")
        self.read_armed = False   # a fresh full C+A read landed this homing cycle
        # PRE-LAUNCH READ (operator 2026-08-02: "just do the POS reads BEFORE
        # PB launches, so that when PB is up, we are all set"): the head read
        # needs only HAL (7I84 VFIELD is direct -- outputs work in ESTOP), so
        # it runs the moment the brain starts, while PB is still painting.
        self.want_read = True
        self.announce_armed = False
        self.prev_xyz_homing = False
        # per-axis REF A / REF C (one-axis REF ALL)
        self.pending_ref = set()      # joints to home once the read arms
        self.verify_axes = ('c', 'a')  # axes the CURRENT verify read judges
        # verify bookkeeping: axes AWAITING verify accumulate (a second
        # single-ref must never overwrite the first's scope -- C landed
        # -1.26 deg unflagged when Home A overwrote it, 2026-08-01 13:31)
        self.verify_want = set()
        self.head_homed_seen = set()
        self.prev_head_homed = {4: False, 5: False}
        self.prev_refa = False
        self.prev_refc = False
        # (flip machinery deleted 2026-08-02: sequences are permanent)
        self.seq_watch_n = 0

    # ---- head read (exact port of nedgui _hr_start/_hr_tick/_hr_report) -----
    def hr_start(self, axis, cb=None):
        if self.hr_step:
            return
        self.hr_cb = cb
        self.hr_axis = axis
        self.hr_step = 1
        self.hr_deg[axis] = None
        try:
            h['r4-select'] = (axis == 'a')    # settle R4 BEFORE touching SEN
            h['pso-enable'] = True
            h['pso-reset'] = True
            self.hr_p0 = int(h['parsed-in'])
        except Exception:
            self.hr_p0 = 0
        log('HEADREAD {} start (R4 set, SEN about to drop -> A/C locked)'.format(axis.upper()))

    def hr_tick(self):
        st = self.hr_step
        try:
            if HR_ST_RISE < st < HR_ST_TIMEOUT:
                # early exit: first parse after the SEN rise IS the answer
                try:
                    if int(h['parsed-in']) > self.hr_p1:
                        st = HR_ST_TIMEOUT
                except Exception:
                    pass
            if st == 1:
                h['pso-reset'] = True     # flush FIFO + buffer (stale other-axis bytes)
                h['sen-suppress'] = True  # SEN LOW
                h['sen-force'] = False
            elif st == 2:
                h['pso-reset'] = False
            elif st == HR_ST_RISE:
                try:
                    self.hr_p1 = int(h['parsed-in'])
                except Exception:
                    self.hr_p1 = self.hr_p0
                h['sen-force'] = True     # rising edge -> pack bursts
            elif st >= HR_ST_TIMEOUT:
                self.hr_step = 0
                self.hr_report()
                h['sen-force'] = False
                h['sen-suppress'] = False
                h['pso-enable'] = False   # stop touching the board (servo timing)
                # PARK R4 DE-ENERGIZED: R4 also gates the 70 V rotary brick;
                # leaving it energized = brick live all session (blanking EMI).
                h['r4-select'] = False
                if self.hr_cb:
                    self.hr_cb_delay = 2  # ~0.5 s, mirrors the 300 ms singleShot
                return
        except Exception as e:
            self.hr_step = 0
            log('HEADREAD failed: {}'.format(e))
            return
        self.hr_step = st + 1

    def hr_report(self):
        try:
            p = int(h['parsed-in'])
            mt = int(h['multiturn-in'])
            w = int(h['within-in'])
        except Exception as e:
            log('HEADREAD read failed: {}'.format(e))
            return
        ax = self.hr_axis
        if p == self.hr_p0:
            log('HEADREAD {} NO NEW FRAME (parsed still {})'.format(ax.upper(), p))
            return
        m0, w0 = HEAD_M0W0[ax]
        deg = SIGN[ax] * ((mt - m0) * R_COUNTS + (w - w0)) / (R_COUNTS * GEAR[ax]) * 360.0
        # GUARD 1 -- stale-read detection: identical raw counts = other axis's data.
        if self.hr_lastraw is not None and self.hr_lastraw == (mt, w):
            log('HEADREAD {} REJECTED: raw (mt={} w={}) identical to previous read '
                '-- stale/other-axis data, NOT writing home_offset'.format(ax.upper(), mt, w))
            return
        self.hr_lastraw = (mt, w)
        # GUARD 2 -- range check: never write an offset outside the soft limits.
        if abs(deg) >= LIM[ax]:
            log('HEADREAD {} REJECTED: {:+.3f} deg outside +/-{} -- NOT writing '
                'home_offset'.format(ax.upper(), deg, LIM[ax]))
            return
        log('HEADREAD {}: {:+.3f} deg  (mt={} w={})'.format(ax.upper(), deg, mt, w))
        self.hr_deg[ax] = deg
        jn = 4 if ax == 'a' else 5
        os.system('halcmd setp ini.{}.home_offset {:.4f} >/dev/null 2>&1'.format(jn, deg))
        log('HEADREAD -> ini.{}.home_offset = {:+.4f}'.format(jn, deg))

    # ---- stored homing (port of _sh_save / _resume_prep, consent in run5.sh) --
    def sh_save(self, now):
        if now < self.sh_next:
            return
        self.sh_next = now + 10.0
        try:
            s = self.stat
            if not all(s.homed[jn] for jn in (0, 1, 2, 3)):
                return
            if s.current_vel > 1e-6:
                return
            if any(abs(s.joint[jn]['velocity']) > 1e-4 for jn in (0, 1, 2, 3)):
                return
            pos = [round(s.joint_actual_position[jn], 4) for jn in (0, 1, 2, 3)]
            if self.sh_last is not None and now - self.sh_last_t < 600 \
               and max(abs(a - b) for a, b in zip(pos, self.sh_last)) < 0.005:
                return
            tmp = SH_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'saved': time.strftime('%Y-%m-%d %H:%M:%S'),
                           'joints': {str(j): p for j, p in zip((0, 1, 2, 3), pos)}}, f)
            os.replace(tmp, SH_FILE)
            self.sh_last = pos
            self.sh_last_t = now
        except Exception:
            pass

    def resume_arm(self):
        # Operator consent already given: run5.sh resume showed the stored values
        # and asked y/N BEFORE launch (NED_RESUME_OK=1). Without it, refuse.
        if os.environ.get('NED_RESUME_OK') != '1':
            log('STORED HOMING refused: no launch-time consent (NED_RESUME_OK unset)')
            return False
        try:
            with open(SH_FILE) as f:
                d = json.load(f)
            saved = d.get('saved', '?')
            vals = {jn: float(d['joints'][str(jn)]) for jn in (0, 1, 2, 3)}
        except Exception as e:
            log('STORED HOMING refused: stored_home.json missing/unreadable ({})'.format(e))
            return False
        for jn, v in vals.items():
            lo = self.stat.joint[jn]['min_position_limit']
            hi = self.stat.joint[jn]['max_position_limit']
            if not (lo - 0.001 <= v <= hi + 0.001):
                log('STORED HOMING refused: joint {} stored {:+.3f} outside limits '
                    '[{:.1f}, {:.1f}]'.format(jn, v, lo, hi))
                return False
        for jn, v in vals.items():
            rc = os.system('halcmd setp ini.{}.home_offset {:.4f}'.format(jn, v))
            rc |= os.system('halcmd setp ini.{}.home {:.4f}'.format(jn, v))
            if rc:
                log('STORED HOMING refused: halcmd setp failed for joint {}'.format(jn))
                return False
        log('STORED HOMING: armed joints 0-3 from stored_home.json (saved {}): {}'.format(
            saved, '  '.join('J{}={:+.3f}'.format(jn, vals[jn]) for jn in (0, 1, 2, 3))))
        return True

    def declare_xyzw(self):
        # TRUE home-in-place via EMC_JOINT_SET_HOMING_PARAMS (NML 112,
        # tools/live/ned_homing_params -- runtime homing override, operator
        # 2026-08-02): search/latch velocities zeroed -> the home command
        # declares at the current position with ZERO MOTION anywhere in the
        # travel; real switch-homing values restored right after, so the
        # menu physical reset is untouched.
        try:
            self.stat.poll()
        except Exception:
            return
        # A/C (4,5) declare TOO (operator 2026-08-02 15:5x: "i SHOULD be able
        # to unclamp the spindle after power up since we are homed but it
        # errors out"). They used to wait for the PSO read, leaving a several
        # second window where all(homed[:6]) was FALSE and every homed-gated
        # button refused -- the drawbar click at 15:57:03 landed 2 s after the
        # 0-3 declare and died on exactly that. The read still lands seconds
        # later and re-homes A/C to the true absolute offset, so this only
        # fills the gap; it never decides the final head coordinate.
        jns = [j for j in (0, 1, 2, 3, 4, 5) if not self.stat.homed[j]]
        if not jns:
            return
        SEND = '/home/brains/Documents/ned/tools/live/ned_homing_params'
        try:
            ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])

            def jini(jn, key, dflt='0'):
                return ini.find('JOINT_%d' % jn, key) or dflt

            def send(jn, home, offset, final, search, latch):
                seq = jini(jn, 'HOME_SEQUENCE', '0')
                os.system('%s %d %s %s %s %s %s 0 1 %s >/dev/null 2>&1'
                          % (SEND, jn, home, offset, final, search, latch, seq))

            self.stat.poll()
            for jn in jns:
                pos = '%.4f' % self.stat.joint_actual_position[jn]
                send(jn, pos, pos, '0', '0', '0')
            time.sleep(0.3)      # let task/motion consume the four settings
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            self.cmd.teleop_enable(0)
            self.cmd.wait_complete()
            seqs = [(0, (0, 3)), (1, (1,)), (2, (2,))]
            for j in (4, 5):
                if j in jns:
                    seqs.append((j, (j,)))
            for jarg, expect in seqs:
                for attempt in (1, 2):
                    self.cmd.home(jarg)
                    t0 = time.time()
                    while time.time() - t0 < 3:
                        self.stat.poll()
                        if all(self.stat.homed[j] for j in expect):
                            break
                        time.sleep(0.1)
                    if all(self.stat.homed[j] for j in expect):
                        break
                    log('DECLARE: home({}) missed (attempt {}), reissuing'
                        .format(jarg, attempt))
                time.sleep(0.4)
            # restore the REAL switch-homing config for the menu reset
            for jn in jns:
                send(jn,
                     jini(jn, 'HOME', '0.0'),
                     jini(jn, 'HOME_OFFSET', '0.0'),
                     jini(jn, 'HOME_FINAL_VEL', '0'),
                     jini(jn, 'HOME_SEARCH_VEL', '0'),
                     jini(jn, 'HOME_LATCH_VEL', '0'))
            self.stat.poll()
            log('DECLARED HOME (zero-motion, NML 112): joints {} where '
                'they stand; homed={} all6={} (STALE HOME until menu Home All)'
                .format(jns, self.stat.homed[:6],
                        all(self.stat.homed[:6])))
        except Exception as e:
            log('DECLARE HOME failed: {}'.format(e))


    def do_inplace(self):
        # home unhomed A/C where they stand using the armed read; no motion.
        # Skipped if a real cycle is in flight.
        if not getattr(self, 'inplace_pending', False) or self.pending_ref \
           or self.verify_want:
            return
        self.inplace_pending = False
        try:
            self.stat.poll()
        except Exception:
            return
        jns = [(jn, ax) for jn, ax in ((4, 'a'), (5, 'c'))
               if not self.stat.homed[jn] and self.hr_deg.get(ax) is not None]
        if not jns:
            return
        try:
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            self.cmd.teleop_enable(0)
            self.cmd.wait_complete()
            self.inplace_restore = set()
            for jn, ax in jns:
                os.system('halcmd setp ini.{}.home {:.4f} >/dev/null 2>&1'
                          .format(jn, self.hr_deg[ax]))
                self.cmd.home(jn)
                self.inplace_restore.add(jn)
            log('IN-PLACE HOME: joint(s) {} homed where they stand '
                '(no motion): {}'.format(
                    [j for j, _ in jns],
                    '  '.join('{}={:+.3f}'.format(ax.upper(), self.hr_deg[ax])
                              for _, ax in jns)))
        except Exception as e:
            log('IN-PLACE HOME failed: {}'.format(e))

    def read_done(self):
        # a read cycle finished; armed ONLY if BOTH axes produced an accepted
        # value (offsets written) -- a no-frame/rejected read must not arm.
        ok = (self.hr_deg.get('a') is not None and self.hr_deg.get('c') is not None)
        if ok:
            self.read_armed = True
            self.read_retries = 0
            log('HEAD READ armed: C={:+.3f} A={:+.3f}'.format(
                self.hr_deg['c'], self.hr_deg['a']))
            # STARTUP IN-PLACE HOME: read armed at power-on -> home unhomed
            # A/C joints where they stand. Factored to do_inplace() so the
            # PRE-LAUNCH-read path (ON edge with read already armed) can run
            # the same code from the tick (the 02:06 bug: inplace_at was
            # scheduled but nothing consumed it -> A/C never homed).
            self.do_inplace()
            # per-axis REF A / REF C: the read is armed -- home the requested
            # joint(s) NOW, nothing else (spec: the other head axis untouched)
            if self.pending_ref:
                jns = sorted(self.pending_ref)
                self.pending_ref = set()
                try:
                    self.cmd.mode(linuxcnc.MODE_MANUAL)
                    self.cmd.wait_complete()
                    self.cmd.teleop_enable(0)   # homing = joint mode
                    self.cmd.wait_complete()
                    for jn in jns:
                        self.cmd.home(jn)
                    log('REF single: read armed -> homing joint(s) {}'.format(jns))
                except Exception as e:
                    log('REF single homing failed: {}'.format(e))
            if self.announce_armed:
                self.announce_armed = False
                try:
                    self.cmd.error_msg('Head read armed -- press HOME again.')
                except Exception:
                    pass
        else:
            self.read_retries = getattr(self, 'read_retries', 0) + 1
            if self.read_retries < 3:
                log('HEAD READ incomplete (C={} A={}) -- retry {}'.format(
                    self.hr_deg.get('c'), self.hr_deg.get('a'), self.read_retries))
                self.want_read = True
            else:
                self.read_retries = 0
                log('HEAD READ FAILED 3x -- NOT armed; A/C homing stays blocked')
                try:
                    self.cmd.error_msg('Head A/C read FAILED 3x -- A/C homing '
                                       'blocked (packs powered? SEN chain?).')
                except Exception:
                    pass

    # ---- post-home verify (port of _post_verify/_verify_eval/_verify_fail) ---
    def verify_eval(self):
        bad, msgs = [], []
        for ax in self.verify_axes:
            d = self.hr_deg.get(ax)
            if d is None:
                bad.append(ax)
                msgs.append('{}: verify read FAILED'.format(ax.upper()))
            elif abs(d) > HR_VERIFY_TOL:
                bad.append(ax)
                msgs.append('{}: {:+.3f} deg after homing'.format(ax.upper(), d))
        if not bad:
            log('HOME VERIFY OK ({}): C={:+.3f} A={:+.3f} deg'.format(
                '+'.join(a.upper() for a in self.verify_axes),
                self.hr_deg.get('c'), self.hr_deg.get('a')))
            self.read_armed = False    # next homing cycle needs a fresh read
            self.verify_want = set()   # cycle complete; next ref may start
            # A/C homed outside the HOME ALL sequence -> task does not enter
            # teleop by itself; re-enter so the MPG axis jog is live.
            self.ensure_teleop()
            return
        if self.hv_attempt < 1:
            self.hv_attempt += 1
            log('HOME VERIFY: {} -- NOT actually homed, correcting (unhome + rehome '
                'with the fresh read)'.format('; '.join(msgs)))
            try:
                self.cmd.mode(linuxcnc.MODE_MANUAL)
                self.cmd.wait_complete()
                self.cmd.teleop_enable(0)   # homing = joint mode, always
                self.cmd.wait_complete()
                for ax in bad:
                    self.cmd.unhome(4 if ax == 'a' else 5)
                self.cmd.wait_complete()
                self.correcting = True
                for ax in bad:
                    self.cmd.home(4 if ax == 'a' else 5)
            except Exception as e:
                self.verify_fail(bad, msgs, 'correction failed: {}'.format(e))
        else:
            self.verify_fail(bad, msgs, 'still off after one correction')

    def verify_fail(self, bad, msgs, why):
        # the homed flag must not lie: leave the offending joints unhomed
        try:
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            for ax in bad:
                self.cmd.unhome(4 if ax == 'a' else 5)
        except Exception:
            pass
        txt = 'HOMING VERIFY FAILED ({}): {}. Joint(s) {} left UNHOMED.'.format(
            why, '; '.join(msgs), ', '.join(ax.upper() for ax in bad))
        log(txt)
        self.read_armed = False    # next homing attempt needs a fresh read
        self.verify_want = set()   # cycle over; a fresh ref may start
        try:
            self.cmd.error_msg(txt)   # Probe Basic pops this as an error
        except Exception:
            pass

    # ---- teleop recovery (port of _ensure_teleop/_auto_back_to_manual) -------
    def ensure_teleop(self):
        try:
            if self.stat.task_state == linuxcnc.STATE_ON and all(self.stat.homed[:6]):
                self.cmd.teleop_enable(1)
                log('TELEOP re-entered (machine ON + homed) -> MPG live')
        except Exception as e:
            log('TELEOP re-enter failed: {}'.format(e))

    # ---- main tick (0.25 s) --------------------------------------------------
    def tick(self):
        try:
            self.stat.poll()
        except Exception:
            return
        s = self.stat
        now = time.time()

        # head-read state machine has the tick when active
        if self.hr_step:
            self.hr_tick()
            return
        if self.hr_cb_delay:
            self.hr_cb_delay -= 1
            if self.hr_cb_delay == 0 and self.hr_cb:
                cb = self.hr_cb
                self.hr_cb = None
                cb()
            return

        on = (s.task_state == linuxcnc.STATE_ON)

        # resume arming: once, as soon as status is readable
        if self.resume_mode and not self.resume_armed:
            self.resume_armed = self.resume_arm()
            if not self.resume_armed:
                self.resume_mode = 'failed'   # stop retrying; guard below stays
        # resume guard: un-armed in-place homing would relabel machine zero -- abort it
        if self.resume_mode == 'failed':
            try:
                if any(s.joint[jn]['homing'] for jn in (0, 1, 2, 3)):
                    self.cmd.abort()
                    self.cmd.error_msg('RESUME NOT ARMED -- homing aborted. '
                                       'Relaunch tools/run5.sh (normal switch homing).')
                    log('RESUME guard: aborted homing attempt (not armed)')
            except Exception:
                pass

        # machine-ON transition. No reads before on_settled: relays/drives
        # energizing is this machine's EMI burst, and a lost Ethernet packet with
        # pso_live reads in flight overflows hm2_eth's UNBOUNDED read queue
        # (hm2_eth.c:981 "XXX", own comment) -> rtapi_app SIGSEGV (2026-07-31
        # 13:24:43, packet-error-total=1).
        if on and not self.prev_on:
            self.teleop_at = now + 0.8
            self.on_settled = now + 3.0
            self.read_armed = False
            # EVERY power-on: read the head absolutes and HOME A/C IN PLACE
            # (operator 2026-08-01: "at startup, A and C should always be
            # read and their absolute position reported and offset applied,
            # but no return to zero"). Trick = the resume machinery's:
            # ini.N.home is runtime-settable, so home_offset=reading AND
            # home=reading makes the homing final move a zero-length move.
            # DROs then show TRUE angles and A/C are genuinely homed.
            # Requested homing (menu) still returns to zero: ini.N.home is
            # restored to 0 the moment the in-place home completes.
            self.inplace_pending = True
            # DECLARE-HOME XYZ/W where they stand ~1.5 s after ON
            # (operator: jog-ready immediately; menu homing = the
            # physical reset; banner shows STALE HOME until then)
            self.declare_at = now + 1.5
            if self.read_armed and self.hr_deg.get('a') is not None \
               and self.hr_deg.get('c') is not None:
                # pre-launch read is armed; drives were off and A/C are
                # MPG-locked while unhomed, so the head cannot have moved.
                # In-place home fires from the tick in ~1 s; an async
                # verify read follows and corrects if anything is off.
                self.inplace_at = now + 1.0
                log('MACHINE ON -> pre-launch head read armed '
                    '(C={:+.3f} A={:+.3f}) -> A/C homing in place now'
                    .format(self.hr_deg['c'], self.hr_deg['a']))
            else:
                self.want_read = True
                log('MACHINE ON -> head read (A/C will home IN PLACE, no motion)')
        if getattr(self, 'declare_at', None) and now >= self.declare_at:
            self.declare_at = None
            self.declare_xyzw()
        if getattr(self, 'inplace_at', None) and now >= self.inplace_at:
            self.inplace_at = None
            self.do_inplace()
        if self.teleop_at and now >= self.teleop_at:
            self.teleop_at = None
            self.ensure_teleop()
        self.prev_on = on

        # PARALLEL READ ON HOME ALL: A/C are LAST in the HOME ALL sequence
        # (seq 2, joint_a/c.inc -- the homing module's own concurrent machinery;
        # brain-issued individual home commands wedged joint 4's state machine
        # 2026-07-31 15:46). The REF ALL button (dros -> ned_controls
        # .request_homeall) unhomes A/C itself and pulses homeall-in; brain
        # just arms the fresh read while XYZ homes. Per-axis refs do NOT pulse
        # the pin -> the head never moves on refX/refY/refZ ("i hit refY, but
        # A and C zeroed. that's incorrect"). The guard below still aborts any
        # A/C homing that arrives before the read is armed.
        ha = bool(h['homeall-in'])
        if ha and not getattr(self, 'prev_homeall', False) and on:
            if not self.read_armed:
                self.want_read = True
            self.verify_want = {'c', 'a'}   # full-cycle verify judges both
            self.head_homed_seen = set()
            log('HOME ALL -> parallel head read (A/C home last in the sequence)')
        self.prev_homeall = ha

        # PER-AXIS REF A / REF C (one-axis REF ALL, operator 2026-08-01):
        # rising edge -> unhome THAT joint, force a fresh read; read_done()
        # homes it once the read arms; verify judges only that axis.
        for pin, prev_attr, ax, jn in (('ref-a-in', 'prev_refa', 'a', 4),
                                       ('ref-c-in', 'prev_refc', 'c', 5)):
            cur = bool(h[pin])
            if cur and not getattr(self, prev_attr) and on:
                if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos:
                    log('REF {} refused: machine is executing/moving'.format(ax.upper()))
                    try:
                        self.cmd.error_msg('REF %s refused: machine is busy' % ax.upper())
                    except Exception:
                        pass
                    setattr(self, prev_attr, cur)
                    continue
                # SERIALIZE head cycles: a second request mid-cycle unhomed
                # the other joint under the first cycle's feet and masked
                # its verify (2026-08-01 13:30-31)
                if self.pending_ref or self.verify_want:
                    log('REF {} refused: a head cycle is still completing'.format(ax.upper()))
                    try:
                        self.cmd.error_msg('REF %s refused: previous head '
                                           'cycle still completing -- wait for '
                                           'its verify' % ax.upper())
                    except Exception:
                        pass
                    setattr(self, prev_attr, cur)
                    continue
                try:
                    self.cmd.mode(linuxcnc.MODE_MANUAL)
                    self.cmd.wait_complete()
                    self.cmd.teleop_enable(0)
                    self.cmd.wait_complete()
                    if s.homed[jn]:
                        self.cmd.unhome(jn)
                        self.cmd.wait_complete()
                    self.pending_ref.add(jn)
                    # verify_want (not verify_axes) so (a) the serialization
                    # guard has teeth after pending_ref pops and (b) the
                    # post-home verify actually triggers for single refs --
                    # both failed 17:23: Home C's read fired mid-Home-A and
                    # A's verify never ran
                    self.verify_want.add(ax)
                    self.head_homed_seen.discard(ax)
                    self.read_armed = False   # spec: ALWAYS a fresh read
                    self.want_read = True
                    log('REF {} -> unhomed joint {}, fresh read, will home it '
                        'alone'.format(ax.upper(), jn))
                except Exception as e:
                    log('REF {} request failed: {}'.format(ax.upper(), e))
            setattr(self, prev_attr, cur)

        # GUARD: A/C must NEVER home without a fresh read armed (stale offsets
        # command an unearned move). Abort, read now, tell the operator to HOME
        # again. Covers: read slower than homing, failed reads (no frame),
        # lone A/C re-homes. Verify's own correction re-home is exempt.
        ac_homing = False
        try:
            ac_homing = bool(s.joint[4]['homing'] or s.joint[5]['homing'])
        except Exception:
            pass
        if ac_homing and not self.read_armed and not self.correcting:
            try:
                self.cmd.abort()
                self.cmd.error_msg('A/C offsets not read yet -- homing aborted. '
                                   'Reading now; press HOME again when told.')
            except Exception:
                pass
            log('GUARD: A/C homing without fresh read -> aborted, reading now')
            self.want_read = True
            self.announce_armed = True

        # READ <-> HEAD-MOTION MUTEX: a read drops SEN -> BOTH packs go BB
        # (servos off). Starting a read while a head joint is homing/moving
        # SEIZES that motion mid-flight (lost steps, corrupted landing --
        # 2026-08-01 17:23, Home C's read vs Home A's final move). Defer
        # the read until the head is still.
        head_busy = False
        try:
            head_busy = bool(s.joint[4]['homing'] or s.joint[5]['homing']
                             or abs(s.joint[4]['velocity']) > 1e-3
                             or abs(s.joint[5]['velocity']) > 1e-3)
        except Exception:
            pass

        # start a wanted read once the machine is settled and the reader is free
        if self.want_read and now >= self.on_settled and self.hr_step == 0 \
           and self.hr_cb_delay == 0 and not head_busy:
            self.want_read = False
            self.hr_start('c', lambda: self.hr_start('a', self.read_done))
            return

        # post-home verify: run once EVERY axis awaiting verify has re-homed
        # (per-joint rising edges -- the old A&C-homed edge got masked when a
        # second single-ref unhomed the other joint mid-cycle, and its scope
        # got overwritten: C sat -1.26 deg unflagged, 2026-08-01 13:31)
        for jn, ax in ((4, 'a'), (5, 'c')):
            cur = bool(s.homed[jn])
            if cur and not self.prev_head_homed[jn]:
                if ax in self.verify_want:
                    self.head_homed_seen.add(ax)
                # in-place startup home completed: restore home=0 so any
                # REQUESTED homing returns the head to zero again
                if jn in getattr(self, 'inplace_restore', set()):
                    os.system('halcmd setp ini.{}.home 0 >/dev/null 2>&1'.format(jn))
                    self.inplace_restore.discard(jn)
                    log('IN-PLACE HOME: joint {} homed, ini.home restored to 0'.format(jn))
            self.prev_head_homed[jn] = cur
        if self.verify_want and self.verify_want <= self.head_homed_seen \
           and self.hr_step == 0 and self.hr_cb_delay == 0 and not head_busy:
            if not self.correcting:
                self.hv_attempt = 0
            self.correcting = False
            self.verify_axes = tuple(sorted(self.verify_want))
            self.head_homed_seen = set()
            log('HOME CYCLE: {} homed -> post-read verify'.format(
                '+'.join(a.upper() for a in self.verify_axes)))
            self.hr_start('c', lambda: self.hr_start('a', self.verify_eval))
            return

        # MODE POLICY (operator 2026-07-31: no MAN/AUTO/MDI buttons): MANUAL is
        # the resting state, always. AUTO/MDI hold only while their code runs;
        # the moment the interpreter is idle, task returns to MANUAL + teleop
        # (MPG live). PAUSED stays AUTO on purpose -- leaving AUTO mid-pause
        # ABORTS the program. The 2-tick dwell keeps us out of the tiny window
        # where the GUI sets MDI mode just before issuing an MDI command.
        # EDGE ONLY, deterministic ("don't do this idle bullshit"): the moment
        # a program/MDI run actually FINISHES, hand control back to MANUAL +
        # teleop. GUI actions that manage their own modes (our zero buttons)
        # complete synchronously and are already back in MANUAL by then.
        # Hand control back ONLY when the machine is truly done: interp idle
        # AND motion in position AND stopped (a mode switch ABORTS in-flight
        # motion). Flip ONCE per activity episode, debounced 1 s, and restart
        # the debounce whenever task mode changes under us -- a level-
        # triggered flip raced fresh MDI commands: GUI enters MDI mode, brain
        # steals it back within a tick, task rejects the command with 'Must
        # be in MDI mode' (2026-07-31 23:44).
        interp_busy = (s.interp_state != linuxcnc.INTERP_IDLE)
        try:
            done = (not interp_busy) and bool(s.inpos) and s.current_vel < 1e-6
        except Exception:
            done = not interp_busy
        now = time.time()
        if s.task_mode != self.prev_task_mode:
            self.done_since = None  # fresh mode change gets the full grace
        self.prev_task_mode = s.task_mode
        if not done:
            self.done_since = None
            if interp_busy:
                self.flip_armed = True  # a program/MDI actually ran
        else:
            if self.done_since is None:
                self.done_since = now
            if bool(h['tcactive-in']):
                # TOOL CHANGE IN PROGRESS: never steal the mode --
                # the restore aborted an M6 mid-return (01:34).
                self.flip_armed = False
                self.done_since = now
            if self.flip_armed and on \
               and s.task_mode != linuxcnc.MODE_MANUAL \
               and now - self.done_since >= 1.0:
                try:
                    self.cmd.mode(linuxcnc.MODE_MANUAL)
                    self.cmd.wait_complete()
                    log('program/MDI done (motion complete) -> MANUAL + teleop (MPG live)')
                    self.ensure_teleop()
                except Exception as e:
                    log('auto->manual failed: {}'.format(e))
                self.flip_armed = False
        self.prev_interp_busy = interp_busy



        # HOMING WEDGE WATCHDOG (2026-08-01 evening): three operator Home
        # Alls froze pre-search -- joints 0/1/3 homing=TRUE, home-state
        # parked at INITIAL_SEARCH_START, zero motion, FOREVER; the DROs
        # then look plausibly homed (frozen world column + unhomed-override
        # wiggle) and everything after runs on an unhomed machine. Ten
        # scripted reproductions never wedged -- only real GUI clicks did
        # (duplicate menu bindings; the menu is config-owned now). Belt and
        # braces regardless of mechanism: if any of joints 0-3 sits in a
        # homing cycle with NO motion on ALL its homing joints for ~5 s,
        # ABORT loudly. Real cycles move within ~1 s (HOME_DELAY is 0.1 s);
        # the synchronized final-move wait is far under 5 s.
        try:
            homing_j = [j for j in range(4) if s.joint[j]['homing']]
        except Exception:
            homing_j = []
        if homing_j:
            pos = {j: s.joint_actual_position[j] for j in homing_j}
            ref = getattr(self, 'wedge_ref', None)
            tnow = time.time()
            moved = (ref is None or ref[0] != tuple(homing_j)
                     or any(abs(pos[j] - ref[1][j]) > 0.01 for j in homing_j))
            if moved:
                self.wedge_ref = (tuple(homing_j), pos, tnow)
            elif tnow - ref[2] >= 5.0:
                try:
                    self.cmd.abort()
                    self.cmd.error_msg(
                        'HOMING WEDGED: joint(s) {} froze before the search '
                        'move -- cycle ABORTED (machine is NOT homed). '
                        'Re-home via Machine > Homing.'.format(homing_j))
                except Exception:
                    pass
                log('WEDGE WATCHDOG: homing joints {} no motion for 5 s '
                    '-> cycle ABORTED'.format(homing_j))
                self.wedge_ref = None
        else:
            self.wedge_ref = None


        # stored-home saver
        self.sh_save(now)


brain = Brain()
log('==== ned_brain start ==== (resume={} head_zero={} gears={})'.format(
    brain.resume_mode, HEAD_M0W0, GEAR))
try:
    while True:
        time.sleep(HR_TICK)
        try:
            brain.tick()
        except Exception:
            # NEVER die silently: a quiet brain loses the homing guards.
            # (gui.md went silent at 14:31:39 2026-07-31 with no traceback.)
            import traceback
            log('BRAIN TICK EXCEPTION:\n' + traceback.format_exc())
            time.sleep(1.0)
except KeyboardInterrupt:
    pass
finally:
    try:
        h['sen-force'] = False
        h['sen-suppress'] = False
        h['pso-enable'] = False
        h['r4-select'] = False    # park the rotary-brick gate on the way out
    except Exception:
        pass
