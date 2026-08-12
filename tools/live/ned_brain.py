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
import subprocess
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


def now_mono():
    return time.monotonic()


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
for _p in ('sen-suppress', 'sen-force', 'pso-enable', 'pso-reset',
           # NO GUARD-ARM PIN (deleted 2026-08-07). It muted the tool
           # guard through the boot window so the "iocontrol has not served
           # the tool table yet" mismatch would not alarm -- i.e. a safety
           # interlock switched OFF to suppress a message that was TRUE.
           # The 25 s unmute clock also started at brain start, above the
           # STATE_ON check, so it routinely expired before the machine was
           # even powered and armed on a mismatch it had just printed
           # ("TOOL GUARD ARMED (timeout backstop): record T2, LinuxCNC
           # T0", 2026-08-07 09:47). The guard now watches from HAL load;
           # a boot mismatch locks motion and clears itself the moment
           # restore_spindle_tool reconciles the record.
           'r4-select',
           # -xyzab ONLY: the 70 V workpiece-rotary brick is live and settled.
           # R4 (7I84 output-05) is ONE relay doing TWO jobs -- the PSO pack
           # select for the A/C absolute read, and the brick's second gate in
           # series with R11 (whose coil sits on the drive-enable node, so it
           # closes whenever the machine is enabled). Operator 2026-08-11:
           # "its fine because we can always turn the rotaries off to home A,
           # since when homing, everything else isn't moving anyway."
           # So the head read wins, always, and B simply goes dark for it.
           # Costless: the worm is self-locking (docs/components.md:50), B
           # holds its position with the brick dead, and B is open loop with
           # no encoder -- which is exactly why no step may leave the FPGA
           # before this pin is TRUE. A step into an unpowered drive is lost
           # silently and every subsequent B coordinate is wrong.
           'b-armed'):
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
h.newpin('seq-active-in', hal.HAL_BIT, hal.HAL_IN)   # MODE INTERLOCK
h.newpin('seq-hb-in', hal.HAL_U32, hal.HAL_IN)       # its liveness beat
h.newpin('ref-a-in', hal.HAL_BIT, hal.HAL_IN)
h.newpin('ref-c-in', hal.HAL_BIT, hal.HAL_IN)
# SPINDLE FAULT ANNUNCIATION (operator 2026-08-12). ned5_iron.hal now drops
# iocontrol.0.emc-enable-in on either of these, which e-stops the machine --
# but e-stop's own banner says nothing about WHY, and "machine stopped" with
# no reason is how an operator ends up power-cycling a VFD that is telling
# them something. The stop is HAL's job; the sentence is this loop's.
h.newpin('vfd-fault-in', hal.HAL_BIT, hal.HAL_IN)
h.newpin('overtemp-in', hal.HAL_BIT, hal.HAL_IN)
# SPINDLE COMMANDED vs SPINDLE ACTUALLY RUNNING (operator 2026-08-12:
# "that should be an error if the program commands the spindle spinning, but
# gets no positive confirmation from mollom"). spin-cmd-in is what we SEND
# (the permit that drives SPIN-CW/CCW and the 0-10 V), spin-run-in is the
# VFD's own running contact coming back on 7I97 IN11 via R1. Comparing the
# two is the only way to notice a spindle that was told to run and did not.
h.newpin('spin-cmd-in', hal.HAL_BIT, hal.HAL_IN)
h.newpin('spin-run-in', hal.HAL_BIT, hal.HAL_IN)
# THE HOMING STATE MACHINE ITSELF. homing.c exports joint.N.home-state (s32)
# and names the enum at homing.c:76-100: HOME_IDLE = 0 ... HOME_FINAL_MOVE_
# START = 20, which is the state where homing.c:1279 does
#     joint->free_tp.pos_cmd = H[joint_num].home;
# i.e. where the destination is LATCHED. Any write to ini.N.home between
# cmd.home() and that latch changes where the head goes -- on 2026-08-07 C
# travelled -114.7048 deg on a DECLARE that must not move at all. Netted
# pins, never halcmd, because this is read every tick (a getp per tick would
# fork twice a tick on a Pi, and hal.get_value spins the global mutex).
h.newpin('hstate-4-in', hal.HAL_S32, hal.HAL_IN)
h.newpin('hstate-5-in', hal.HAL_S32, hal.HAL_IN)
# TRUE while ANY head homing work is outstanding -- pins armed, a home in
# flight, a read running, a verify pending or a confirmed wipe still owed.
# The GUI greys every homing control off this (operator 2026-08-07: "prevent
# pressing homing any other button until its completely safe ... positive
# confirmation of whatever process is required to end").
h.newpin('head-busy', hal.HAL_BIT, hal.HAL_OUT)
# TOOL TABLE SERVED -- the ONLY thing that releases the default motion lock
# (tool.mm.ntbl -> tool.mm.lock2 -> motion.jog-inhibit + feed-inhibit).
# FALSE here and FALSE on an unconnected pin, so every way this can fail --
# brain not started, postgui net missing, table never served -- leaves the
# machine LOCKED. Positive verification only (operator 2026-08-07: "these
# are so crucial, they must be positively verified before user can do
# anything").
h.newpin('tool-table-ok', hal.HAL_BIT, hal.HAL_OUT)
# REACHABILITY COUNTER. do_inplace() homes one joint per pass and re-arms
# itself for the next, so it depends on being CALLED periodically -- and on
# 2026-08-08 it wasn't: its only live caller was read_done(), joint 4 homed,
# joint 5 never did, and the routine declined in silence for 13 minutes with
# nothing to show for it. A silent decline is invisible; a counter is not.
# Watch it with: halcmd getp brain.inplace-calls
h.newpin('inplace-calls', hal.HAL_S32, hal.HAL_OUT)
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
def _exit_save():
    try:
        brain.sh_save(time.time() + 1e9, force=True)
        log('stored_home.json final save at exit')
    except Exception:
        pass


atexit.register(_exit_save)
atexit.register(lambda: log('ned_brain exited (atexit; normal interpreter exit)'))


class Brain(object):
    def __init__(self):
        self.stat = linuxcnc.stat()
        self.cmd = linuxcnc.command()
        ini = os.path.basename(os.environ.get('INI_FILE_NAME', ''))
        self.resume_mode = 'resume' in ini
        self.resume_armed = False
        # -xyzab: the workpiece rotary B is joint 6 and takes over every
        # control that used to drive C (operator 2026-08-11). The ONLY thing
        # the brain owes that mode is R4 arbitration -- the launch homing
        # sequence lives in ned_controls, which already owns every motion
        # command on this machine. The brain issues none, and that stays
        # true here (memory: stale-home is a declaration, never a move).
        self.b_mode = (os.environ.get('NED_MODE', '') == 'xyzab')
        self.b_armed_at = None
        self.seq_hb_last = -1
        self.seq_hb_t = 0.0
        self.seq_was = False
        # head read state machine
        self.hr_step = 0
        self.hr_axis = 'c'
        self.hr_cb = None
        self.hr_cb_delay = 0
        self.hr_deg = {}
        self.hr_p1 = 0
        self.hr_lastraw = None
        # verify / homing
        self.prev_ac_homed = False
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
        # verify bookkeeping: axes AWAITING verify accumulate (a second
        # single-ref must never overwrite the first's scope -- C landed
        # -1.26 deg unflagged when Home A overwrote it, 2026-08-01 13:31)
        self.prev_head_homed = {4: False, 5: False}
        self.prev_refa = False
        self.prev_refc = False
        # (flip machinery deleted 2026-08-02: sequences are permanent)
        self.seq_watch_n = 0
        # joints whose ini.N.home/home_offset are still owed a wipe. The wipe
        # is drained ONLY after positive confirmation (homed latched + every
        # head joint back at HOME_IDLE), and it is deliberately NOT load
        # bearing: set_home_pins() rewrites both pins before every single
        # home, so a wipe that is late or missed cannot feed a later cycle.
        self.pin_wipe = set()
        # motor-pos-fb at the instant a DECLARE was armed. A declare must not
        # move the head; if this changes, it moved, and that is an error.
        self.declare_snap = {}

    # ---- head read (exact port of nedgui _hr_start/_hr_tick/_hr_report) -----
    # ==== ini.N.home / ini.N.home_offset -- THE ONLY WRITER ===============
    # Every path that homes a head joint goes through set_home_pins() ->
    # cmd.home(). Nothing else may touch these pins. Six independent writers
    # is why the 2026-08-07 declare could not be reasoned about.
    HEAD_JN = (4, 5)
    HOME_IDLE = 0            # homing.c:78

    def home_state(self, jn):
        try:
            return int(h['hstate-{}-in'.format(jn)])
        except Exception:
            return None

    def head_quiet(self, why=''):
        # EVERY head joint must be HOME_IDLE, not just the one about to be
        # homed: do_home_one_joint (homing.c:265-281) stamps HOME_START
        # without checking whether another joint is mid-cycle, so motion
        # will never tell us "joint 4 is busy" -- we have to look.
        for _jn in self.HEAD_JN:
            st = self.home_state(_jn)
            if st is None:
                log('HOME GATE: joint.{}.home-state unreadable -- refusing '
                    '{}'.format(_jn, why))
                return False
            if st != self.HOME_IDLE:
                log('HOME GATE: joint {} in home-state {} (not IDLE) -- '
                    'refusing {}'.format(_jn, st, why))
                return False
        return True

    def motor_fb(self, jn):
        try:
            r = subprocess.run(
                ['timeout', '5', 'halcmd', 'getp',
                 'joint.{}.motor-pos-fb'.format(jn)],
                capture_output=True, text=True)
            return float(r.stdout.strip()) if not r.returncode else None
        except Exception:
            return None

    def set_home_pins(self, jn, home, offset, why):
        """Gate -> write BOTH pins -> read back -> compare. False = refused,
        loudly, and NO home may be issued. The read-back is the point: a
        setp that was lost or late aborts the cycle instead of homing to
        someone else's number."""
        if not self.head_quiet('to arm joint {} ({})'.format(jn, why)):
            return False
        # home_offset is DRIVEN BY pso_live (postgui sig-abs-deg-a/c) since
        # 2026-08-10 -- it is a netted pin now and setp on it fails. Only
        # `home` is ours, and under HOME_ABSOLUTE_ENCODER=2 even that is
        # unused: no final move exists.
        for pin, val in (('home', home),):
            name = 'ini.{}.{}'.format(jn, pin)
            rc = os.system('halcmd setp {} {:.4f} >/dev/null 2>&1'
                           .format(name, val))
            if rc:
                log('HOME PINS: setp {} failed rc={} -- NOT homing ({})'
                    .format(name, rc, why))
                return False
            try:
                r = subprocess.run(['timeout', '5', 'halcmd', 'getp', name],
                                   capture_output=True, text=True)
                back = float(r.stdout.strip())
                ok = (r.returncode == 0) and abs(back - val) < 1e-4
            except Exception:
                back, ok = None, False
            if not ok:
                log('HOME PINS: {} reads back {} after writing {:+.4f} -- '
                    'REFUSING to home ({})'.format(name, back, val, why))
                return False
        self.pin_wipe.add(jn)
        log('HOME PINS: joint {} armed home={:+.4f} home_offset={:+.4f} '
            '(both read back OK; home-state 4/5 = {}/{}) -- {}'.format(
                jn, home, offset, self.home_state(4), self.home_state(5), why))
        return True

    def wipe_home_pins(self, jn, why):
        """Blank both pins. Gated the same way -- blanking during a home is
        exactly the bug this whole path exists to stop."""
        if not self.head_quiet('to wipe joint {} ({})'.format(jn, why)):
            return False
        os.system('halcmd setp ini.{}.home 0 >/dev/null 2>&1'.format(jn))
        self.pin_wipe.discard(jn)
        log('HOME PINS: joint {} home wiped (offset is pso-driven) -- {}'
            .format(jn, why))
        return True

    def head_busy(self):
        return bool(self.hr_step or self.pending_ref
                    or self.pin_wipe
                    or getattr(self, 'inplace_pending', False)
                    or any(self.home_state(j) not in (self.HOME_IDLE, None)
                           for j in self.HEAD_JN))

    # ------------------------------------------------------------------
    # B POWER ARBITER  (-xyzab only; a no-op in every other mode)
    # ------------------------------------------------------------------
    # One relay, two consumers, and a strict priority: the head read owns R4
    # whenever it wants it, B gets whatever is left. This is safe in the one
    # direction that matters -- losing power costs B nothing (self-locking
    # worm, it just stops), whereas a head read that cannot select its pack
    # returns the WRONG axis's frame, which is how a 66 deg head got declared
    # as home on 2026-08-01.
    #
    # SETTLE. The brick's contactor and the drives' own supplies need time
    # after R4 closes. b-armed is deliberately NOT the same edge as R4: it
    # trails it by B_SETTLE, and HAL ANDs it into the stepgen enables
    # (ned5_b.hal), so no step can be generated into a drive that is still
    # coming up. Dropping is instant -- there is no reason to delay going
    # dark, and every reason not to.
    B_SETTLE = 0.25

    def b_power(self):
        if not self.b_mode:
            return
        now = time.time()
        self.stat.poll()
        on = (self.stat.task_state == linuxcnc.STATE_ON)
        # The read machinery drives r4-select itself while it runs; do not
        # fight it for the pin, just make sure B is dark for the duration.
        # YIELD BETWEEN RETRIES TOO, not just during a read. hr_step drops
        # to 0 in the gap between a failed read and its retry, and the old
        # test let b_power slam r4-select TRUE in that window -- R4 is the
        # PSO PACK SELECT, so the next read could start against the wrong
        # pack and a settle time nobody granted. want_read is the honest
        # "a read is owed" flag; read_armed False means none has landed yet,
        # so on a boot whose read is failing B never takes the relay at all.
        if (self.head_busy() or self.hr_step or not on
                or getattr(self, 'want_read', False)
                or not getattr(self, 'read_armed', False)):
            if h['b-armed']:
                log('B POWER: dark -- R4 borrowed by the head read '
                    '(B holds position, self-locking worm)')
            h['b-armed'] = False
            self.b_armed_at = None
            return
        if not h['r4-select']:
            h['r4-select'] = True
            self.b_armed_at = now + self.B_SETTLE
            log('B POWER: R4 on, %.2f s settle before steps are allowed'
                % self.B_SETTLE)
            return
        if self.b_armed_at is None:
            # R4 was already high (parked there by something else) -- still
            # owe the settle, because we cannot know how long it has been up.
            self.b_armed_at = now + self.B_SETTLE
            return
        if not h['b-armed'] and now >= self.b_armed_at:
            h['b-armed'] = True
            log('B POWER: brick live and settled -- B may move')

    def hr_start(self, axis, cb=None):
        if self.hr_step:
            return
        self.hr_cb = cb
        self.hr_axis = axis
        self.hr_step = 1
        # STATELESS START (operator 2026-08-07: "A and C homing are fucking
        # stateless ... you don't need to know anything about the past").
        # Every carried value is destroyed before the request goes out, so
        # nothing from an earlier cycle can be mistaken for this one's
        # measurement: the degree slot, the raw-frame memory, and the two
        # ini pins the home consumes. A read that fails then leaves NOTHING.
        self.hr_deg[axis] = None
        self.hr_lastraw = None
        _jn = 4 if axis == 'a' else 5
        self.wipe_home_pins(_jn, 'stateless read start')
        try:
            h['r4-select'] = (axis == 'a')    # settle R4 BEFORE touching SEN
            h['pso-enable'] = True
            h['pso-reset'] = True
        except Exception:
            pass
        log('HEADREAD {} start (blanked: hr_deg, lastraw, ini.{}.home, '
            'ini.{}.home_offset)'.format(axis.upper(), _jn, _jn))

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
                    # POISON, never hr_p0: if the counter is unreadable at the
                    # rise we cannot PROVE freshness, so the read must fail.
                    # 1<<32 is unreachable for a u32 counter -> early-exit
                    # never fires and hr_report's `p <= hr_p1` always rejects.
                    self.hr_p1 = 1 << 32
                h['sen-force'] = True     # rising edge -> pack bursts
            elif st >= HR_ST_TIMEOUT:
                self.hr_step = 0
                self.hr_report()
                # WIPE AFTER USE (operator 2026-08-07: "delete every other
                # fucking number or pin after use"). hr_report has taken the
                # value; nothing may still hold it. hr_p1 is poisoned so a
                # later hr_report can never accept without a new SEN rise,
                # and the raw memory goes. The reader's own multiturn/within
                # are zeroed by the pso-reset edge at the next hr_start,
                # before any burst can be consumed.
                self.hr_p1 = 1 << 32
                self.hr_lastraw = None
                # CLEARING AFTER THE READ (operator 2026-08-06: "is there a
                # way to CLEAR a pin after it is read") is done by hr_start's
                # pso-reset rising edge, which the comp turns into a FIFO
                # flush + multiturn/within = 0 before every burst -- so the
                # pins are empty at the moment a read could consume them.
                # NOT pulsed here: enable drops on this same tick, and a
                # True/False pair written microseconds apart is invisible to
                # a 1 kHz comp. tools/tests/test_headread_freshness.py
                # asserts the flush actually fires.
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
            # ABORT = FULL BLANK. R4 also gates the 70 V rotary brick, and a
            # latched pso-reset swallows the next flush edge (prev_reset is
            # tracked while the comp is disabled, pso_live.comp:90).
            for _p, _v in (('sen-force', False), ('sen-suppress', False),
                           ('pso-enable', False), ('pso-reset', False),
                           ('r4-select', False)):
                try:
                    h[_p] = _v
                except Exception:
                    pass
            self.hr_p1 = 1 << 32
            self.hr_lastraw = None
            log('HEADREAD failed: {} -- all read pins blanked'.format(e))
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
        # FRESHNESS BASELINE = hr_p1 (captured at the SEN RISE, the instant
        # the pack is asked to burst) -- NOT hr_p0 (captured in hr_start,
        # 1.75 s earlier, before the flush and the SEN drop).
        # 2026-08-06 HEAD-CRASH-CLASS BUG: any byte parsed during that
        # 1.75 s window (leftover buffer, the other pack's tail) bumped
        # `parsed`, so this test passed while the pins still held an OLDER
        # frame. That frame was A-at-true-zero (mt=36 w~17.08M, 0.0001 deg
        # from the stored reference), so the brain declared A=+0.000 and
        # homing -- a pure declaration, no motion -- stamped ZERO onto a
        # head physically at +66 deg. Verify re-read the same stale frame
        # and blessed it. Nothing below can catch this; the baseline must
        # be right. A read with no post-rise frame MUST fail: hr_deg stays
        # None -> read_done refuses to arm -> A/C homing stays blocked.
        if p <= self.hr_p1:
            log('HEADREAD {} NO NEW FRAME since the SEN rise (parsed {} <= '
                '{}) -- pins hold an OLD frame, REFUSING it'.format(
                    ax.upper(), p, self.hr_p1))
            return
        # RE-PARSE, never the startup cache. Banking rewrites head_zero.inc
        # while this process runs; with the cached zero the REF re-home that
        # follows converts the encoder against the OLD zero and the DRO ends
        # up reading the correction instead of 0 (2026-08-03: banked, then
        # A read +1.218). Conversion only -- no homing logic here.
        try:
            m0, w0 = parse_head_zero()[ax]
        except Exception as e:
            log('HEADREAD: head_zero.inc re-parse failed ({}) -- using the '
                'startup values'.format(e))
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
        # THE READ NEVER TOUCHES THE PINS. It used to arm ini.N.home_offset
        # here, which meant the offset sat in the pin from the read until
        # the home -- a window anything could write into, and the number
        # outlived its use if the home never came. set_home_pins() now
        # writes BOTH pins immediately before each cmd.home(), so the
        # measurement lives only in self.hr_deg until it is consumed.
        log('HEADREAD {}: joint {} measurement held in hr_deg, pins '
            'untouched until the home'.format(ax.upper(), jn))

    # ---- stored homing (port of _sh_save / _resume_prep, consent in run5.sh) --
    def sh_save(self, now, force=False):
        # EVENT-DRIVEN, not just timed (operator 2026-08-02 23:5x: "machine
        # absolutely did not remember its told position"). The 10 s timer plus
        # the while-moving skip meant a jog followed by a quick shutdown was
        # never saved. Now: the tick calls with force=True on the falling edge
        # of motion (just stopped), and exit_save() writes once more at brain
        # shutdown, so the last position always lands on disk.
        if not force and now < self.sh_next:
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
            if not force and self.sh_last is not None \
               and now - self.sh_last_t < 600 \
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

    def declare_xyzw(self, only=None):
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
        if only is not None:
            jns = [j for j in jns if j in only]
        # DO NOT DECLARE A/C BEFORE THEIR READ EXISTS. Declaring them marks
        # all six homed, which is what flips the DRO banner to STALE HOME --
        # and the operator starts clicking the moment it says that. This
        # declare fires 1.5 s after machine-ON while a head read takes far
        # longer, so if the startup read has not landed yet the fallback would
        # declare A/C at joint_actual_position and the banner would promise a
        # frame that does not exist (operator 2026-08-03: "if it's a timing
        # thing where banner is not reality, that's part of it").
        # Leaving them out keeps all6 FALSE, so the banner stays UNHOMED and
        # tells the truth; do_inplace() then homes them the moment the read
        # arms, which is the ORIGINAL design and needs no change to it.
        for _j, _ax in ((4, 'a'), (5, 'c')):
            if _j in jns and self.hr_deg.get(_ax) is None:
                jns.remove(_j)
                log('DECLARE: {} held back -- no absolute read yet, banner '
                    'stays UNHOMED until it lands'.format(_ax.upper()))
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
            # STALE frame = the PREVIOUS session's coordinates, NOT zero
            # (operator 2026-08-02: "it must always use previous values and
            # declare stale home. not zero"). The brain refreshes
            # stored_home.json every 10 s while homed, so unless the machine
            # was pushed while off these are its true coordinates -- and the
            # STALE HOME banner is exactly this trust level. A/C never use
            # the store: their PSO absolute read follows seconds later.
            stored = {}
            try:
                import json
                with open(SH_FILE) as f:
                    d = json.load(f)
                stored = dict((int(k), float(v))
                              for k, v in d['joints'].items())
                log('DECLARE: STALE frame from stored_home.json '
                    '(saved {}): {}'.format(d.get('saved', '?'), stored))
            except Exception as e:
                log('DECLARE: stored_home.json unusable ({}) -- falling '
                    'back to declare-at-current-position'.format(e))
            # A/C DECLARE AT THE ABSOLUTE READ, not at joint_actual_position.
            # The comment above calls this declare a gap-filler because "the
            # read still lands seconds later and re-homes A/C". It does not:
            # do_inplace() only homes joints that are NOT already homed, and
            # this declare has just made them homed. So the absolute read was
            # taken, converted, written to ini.N.home_offset -- and thrown
            # away. Operator left A at -45, restarted, DRO read 0 (2026-08-03).
            # Fixed HERE and not in do_inplace: making that routine correct an
            # already-homed joint means unhome/home calls that can land inside
            # a running Home All, which wedged the cycle. This touches only the
            # value the declare hands to send() -- no extra homing, no change
            # to sequencing. If the read has not landed the old behaviour
            # stands, so nothing regresses.
            for jn in jns:
                ax = {4: 'a', 5: 'c'}.get(jn)
                if ax is not None and self.hr_deg.get(ax) is not None:
                    pos = '%.4f' % self.hr_deg[ax]
                elif jn in stored and jn not in (4, 5):
                    pos = '%.4f' % stored[jn]
                else:
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
            log('DECLARE: A/C from the absolute read: {}'.format(
                '  '.join('{}={}'.format(
                    a.upper(),
                    '{:+.4f}'.format(self.hr_deg[a])
                    if self.hr_deg.get(a) is not None else 'NOT READ YET')
                    for a in ('a', 'c'))))
            # AUTO-POWER moved the ON edge into task's startup window --
            # the tool-DB init alone can block io for 10 s, and home()
            # commands issued then are swallowed. Two attempts and giving up
            # left the banner UNHOMED forever (2026-08-04). If anything is
            # still unhomed, run the WHOLE declare again in 5 s, and keep
            # doing so while the machine is ON: the declare is idempotent
            # (it only touches still-unhomed joints).
            still = [j for j in jns if not self.stat.homed[j]]
            if still:
                self.declare_at = time.time() + 5.0
                log('DECLARE: joints {} still unhomed -- redeclaring in 5 s'
                    .format(still))
            log('DECLARED HOME (zero-motion, NML 112): joints {} where '
                'they stand; homed={} all6={} (STALE HOME until menu Home All)'
                .format(jns, self.stat.homed[:6],
                        all(self.stat.homed[:6])))
        except Exception as e:
            log('DECLARE HOME failed: {}'.format(e))


    def apply_mode(self):
        # MODE GRAMMAR (operator 2026-08-05): NED_MODE spells the live axes;
        # un-spelled rotaries get their soft limits clamped to +-0.001 deg
        # after homing -- MDI/g-code words on them die at the limit check.
        # NED_KINS=tooltip flips switchkins to type 1 (tool-tip mode) at the
        # homed upright pose, where identity and tool-tip agree exactly.
        # One shot; missing env (old launcher) = no clamps, no switch.
        if getattr(self, '_mode_applied', False):
            return
        mode = os.environ.get('NED_MODE', '')
        kins = os.environ.get('NED_KINS', 'identity')
        if not mode:
            self._mode_applied = True
            return
        try:
            self.stat.poll()
            if (self.stat.task_state != linuxcnc.STATE_ON
                    or not all(self.stat.homed[:6])
                    or self.stat.interp_state != linuxcnc.INTERP_IDLE):
                return                      # retry next tick until ready
            self._mode_applied = True
            def clamp(jn, ax):
                # idempotent: -xyzab re-enters this every tick while it waits
                # for C to reach zero, and a clamp re-applied 4x a second
                # would bury the log.
                done = self.__dict__.setdefault('_clamped', set())
                if jn in done:
                    return
                done.add(jn)
                # THE WINDOW IS AROUND WHERE THE JOINT ACTUALLY IS, not
                # around zero. A and C home by ADOPTING the absolute encoder
                # (HOME_ABSOLUTE_ENCODER = 2), so a head parked at +102.6 deg
                # homes to +102.6 -- and a +-0.001 window centred on zero
                # would put the joint 102 deg OUTSIDE its own soft limits the
                # instant it was applied. get_pos_cmds() tests those limits
                # every servo cycle (control.c:1489-1510), so that is an
                # immediate limit fault on a machine that has not moved.
                # Centring on the live position expresses the actual intent:
                # this rotary is frozen where it stands. Same 0.002 deg total
                # width, so nothing can creep.
                here = self.stat.joint[jn]['output']
                for k, v in (('min_limit', here - 0.001),
                             ('max_limit', here + 0.001)):
                    subprocess.run(['timeout', '5', 'halcmd', 'setp',
                                    'ini.%d.%s' % (jn, k), str(v)],
                                   capture_output=True)
                log('MODE %s: %s CLAMPED at %+.4f (soft limits %+.4f .. '
                    '%+.4f)' % (mode, ax.upper(), here,
                                here - 0.001, here + 0.001))
            live = mode.replace('xyz', '', 1).split('_')[0]
            # -xyzab: C is un-spelled, so it gets clamped like any un-spelled
            # rotary -- but NOT until it is actually AT zero. Clamping first
            # would make the launch drive-to-zero refuse at the soft limit,
            # and the machine would sit with C wherever it was, clamped
            # there, which is the opposite of what the mode is for.
            if 'a' not in live:
                clamp(4, 'a')
            if 'c' not in live:
                if mode == 'xyzab':
                    # 'output' (commanded), NOT 'input': ned_controls' launch
                    # sequence measures C the same way, and two
                    # different fields could disagree forever --
                    # controls declares C done, the brain never
                    # clamps, and apply_mode spins for the session.
                    cpos = self.stat.joint[5]['output']
                    if abs(cpos) > 0.05:
                        self._mode_applied = False   # retry next tick
                        if not getattr(self, '_cwait_said', False):
                            self._cwait_said = True
                            log('MODE xyzab: C is at %+.4f -- holding the '
                                'clamp until the launch sequence puts it at '
                                'zero' % cpos)
                        return
                    log('MODE xyzab: C reached zero (%+.4f)' % cpos)
                clamp(5, 'c')
            if kins == 'tooltip':
                base = None
                try:
                    with open('/home/brains/Documents/ned/configs/params/'
                              'head_pivot.inc') as f:
                        for ln in f:
                            if ln.startswith('PIVOT_LENGTH'):
                                base = float(ln.split('=')[1])
                except Exception:
                    pass
                if base is None:
                    log('MODE: tooltip REFUSED -- no PIVOT_LENGTH in '
                        'head_pivot.inc (run5 gate should have caught this)')
                    return
                # DO NOT WRITE THE PIVOT HERE. run5 puts it in the
                # generated postgui, so it is set at HAL load before the
                # machine can be powered. Writing it now steps the
                # kinematics under a live servo loop: at A=-24 deg a
                # 0->157 step commands 64 mm of Jy and faults every joint.
                # That was the startup jerk (2026-08-05).
                # NO runtime switchkins call: it unhomes every joint
                # (2026-08-05). run5 launches the tool-tip kins as type 0.
                log('MODE %s: TOOL-TIP kins (launched as type 0), pivot '
                    'base %.3f + live tool length. XYZ means the TOOL TIP.'
                    % (mode, base))
        except Exception as e:
            log('MODE apply failed: {}'.format(e))

    def tool_table_gate(self):
        """Publish 'iocontrol has served the tool table'.

        The test is POSITIVE: at least one entry with a real tool number.
        stat.tool_table is an empty tuple before the status buffer is
        initialised and holds only the spindle slot until io finishes
        loading through the DB program (python + sqlite, seconds), so
        counting id > 0 is the fact that the table exists -- not a timer,
        not "it has probably arrived by now".
        """
        try:
            self.stat.poll()
            n = sum(1 for t in self.stat.tool_table if int(t.id) > 0)
        except Exception as e:
            n = 0
            if not getattr(self, '_tbl_err', False):
                self._tbl_err = True
                log('TOOL TABLE: cannot read stat.tool_table ({}) -- motion '
                    'stays LOCKED'.format(e))
        ok = n > 0
        if ok != getattr(self, '_tbl_ok', None):
            self._tbl_ok = ok
            h['tool-table-ok'] = ok
            log('TOOL TABLE: {} -- motion {}'.format(
                'served, {} tools'.format(n) if ok else 'NOT served',
                'permitted' if ok else 'LOCKED'))
        # Say it once if it is taking abnormally long. This changes NOTHING
        # about the lock -- the lock is unconditional until the table
        # exists; this only stops a never-loading table looking like a hang.
        if not ok:
            if not hasattr(self, '_tbl_t0'):
                self._tbl_t0 = time.time()
            elif (time.time() - self._tbl_t0 > 20
                    and not getattr(self, '_tbl_shouted', False)):
                self._tbl_shouted = True
                msg = ('TOOL TABLE NOT LOADED -- motion is locked until it '
                       'is')
                log(msg)
                try:
                    self.cmd.error_msg(msg)
                except Exception:
                    log('TOOL TABLE: could not surface the message')

    def _restore_say(self, msg):
        """Say it once per CHANGE of reason -- this runs at tick rate."""
        if msg != getattr(self, '_restore_why', None):
            self._restore_why = msg
            log('SPINDLE RESTORE: {}'.format(msg))

    def restore_spindle_tool(self):
        # BACKSTOP ONLY since 2026-08-05: the tool database now reports the
        # clamped tool as P0, so LinuxCNC knows it at load time and this
        # never fires (verified: no SPINDLE RESTORE line on a clean boot).
        # Kept because it is the only recovery if the DB program fails to
        # serve -- it costs one comparison per tick and stays silent.
        #
        # #3991 (persistent .var) remembers the clamped
        # tool, but LinuxCNC boots with tool_in_spindle=0. One shot, after
        # the machine is ON + all homed + idle: if the drawbar sensor
        # (motion.digital-in-00, the M66 P0 'locked' input) confirms
        # something IS clamped, re-issue M61 Q<n>. Sensor empty -> no M61
        # (restoring the number would fabricate a PHANTOM; the always-on
        # guard flags the mismatch instead).
        # NOT A ONE-SHOT ANY MORE (2026-08-11). It used to latch
        # _spindle_restored = True the first time the gate passed, BEFORE
        # doing any work, and then return silently on three different
        # paths. If the tool table momentarily carried T12 in P0 the
        # restore saw tool_in_spindle == want, returned, and burned its
        # only attempt; a later table reload dropped tool_in_spindle to 0
        # and nothing could ever put it back. The operator arrived to a
        # machine locked on UNRECORDED with T12 physically clamped, #3991
        # = 12, and NOT ONE LINE in the log explaining it.
        # Now it watches: any time the record and the sensor disagree it
        # re-declares, and every decision says why, once per change.
        if now_mono() < getattr(self, '_restore_next', 0.0):
            return
        self._restore_next = now_mono() + 5.0
        try:
            self.stat.poll()
            if (self.stat.task_state != linuxcnc.STATE_ON
                    or not all(self.stat.homed[:6])
                    or self.stat.interp_state != linuxcnc.INTERP_IDLE):
                return
            want = 0
            with open('/home/brains/Documents/ned/configs/ned5_pb/'
                      'ned5_pb.var') as f:
                for ln in f:
                    parts = ln.split()
                    if len(parts) == 2 and parts[0] == '3991':
                        want = int(float(parts[1]))
                        break
            if want <= 0:
                self._restore_say('no tool recorded in #3991 (%r) -- nothing '
                                  'to restore' % want)
                return
            if self.stat.tool_in_spindle == want:
                self._restore_say('LinuxCNC already has T%d -- nothing to do'
                                  % want)
                return
            locked = subprocess.run(
                ['timeout', '5', 'halcmd', 'getp', 'motion.digital-in-00'],
                capture_output=True, text=True).stdout.strip().upper()
            if locked != 'TRUE':
                log('SPINDLE RESTORE: #3991 says T{} but the drawbar sensor '
                    'reads empty -- NOT restoring (guard will flag if a tool '
                    'is really there)'.format(want))
                return
            self.cmd.mode(linuxcnc.MODE_MDI)
            self.cmd.wait_complete()
            self.cmd.mdi('M61 Q{}'.format(want))
            self.cmd.wait_complete(4.0)
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            self.stat.poll()
            log('SPINDLE RESTORE: T{} re-declared in spindle after reboot '
                '(sensor-confirmed clamped); tool_in_spindle={}'
                .format(want, self.stat.tool_in_spindle))
        except Exception as e:
            log('SPINDLE RESTORE failed: {}'.format(e))

    def do_inplace(self):
        # home unhomed A/C where they stand using the armed read; no motion.
        # Skipped if a real cycle is in flight.
        try:
            self._inpl_n = getattr(self, '_inpl_n', 0) + 1
            h['inplace-calls'] = self._inpl_n
        except Exception:
            pass
        # WHY IT IS DECLINING, SAID OUT LOUD -- once per change of reason,
        # so it costs nothing at 4 Hz but can never again strand A/C in
        # silence (2026-08-08: 13 minutes of nothing while joint 5 sat
        # unhomed and the whole GUI stayed locked behind it).
        why = None
        if not getattr(self, 'inplace_pending', False):
            why = 'nothing pending'
        elif self.pending_ref:
            why = 'a REF is queued for joint(s) {}'.format(
                sorted(self.pending_ref))
        elif not self.read_armed:
            why = 'no armed head read'
        if why is not None:
            if why != getattr(self, '_inpl_why', None):
                self._inpl_why = why
                log('IN-PLACE HOME: standing by -- {}'.format(why))
            return
        if getattr(self, '_inpl_why', None) is not None:
            self._inpl_why = None
            log('IN-PLACE HOME: proceeding (pending + armed read + no REF '
                'or verify outstanding)')
        # NEVER CUT INTO A RUNNING HOMING CYCLE. This routine switches to
        # MANUAL, drops teleop and issues unhome/home; doing that under Home
        # All takes the sequencer's joint out from under it. On 2026-08-03 the
        # menu went live the instant the declare finished -- while the
        # machine-ON head read was still in flight -- the operator clicked
        # Home All in that window, this fired into it, and Z froze before its
        # search move: "HOMING WEDGED: joint(s) [2]".
        # DEFER, do not consume: the flag is left set so a later call can
        # still do the work. Nothing is lost by waiting -- declare_xyzw() has
        # already applied the absolute read to A/C, so the offsets are correct
        # meanwhile; this only re-asserts them.
        # NOTE the earlier mistake: last time I ALSO removed the
        # inplace_pending gate above, which had been keeping this out of
        # homing cycles by accident, and that broke homing outright. This adds
        # the explicit guard and changes nothing else.
        try:
            self.stat.poll()
            if any(self.stat.joint[j]['homing'] for j in range(6)):
                log('IN-PLACE HOME: deferred -- a homing cycle is running')
                return
        except Exception:
            return
        try:
            self.stat.poll()
        except Exception:
            return
        # THE FLAG IS CLEARED ON COMPLETION, NOT ON ENTRY. It used to be
        # dropped before jns was even computed, so an unhomed joint with no
        # measurement was silently removed from the list AND the retry was
        # thrown away in the same breath -- stranded for good, saying
        # nothing.
        unhomed = [(jn, ax) for jn, ax in ((4, 'a'), (5, 'c'))
                   if not self.stat.homed[jn]]
        if not unhomed:
            self.inplace_pending = False      # both declared: job done
            self._inpl_gap = None
            return
        jns = [(jn, ax) for jn, ax in unhomed
               if self.hr_deg.get(ax) is not None]
        gap = sorted(ax.upper() for jn, ax in unhomed
                     if self.hr_deg.get(ax) is None)
        if gap != (getattr(self, '_inpl_gap', None) or []):
            self._inpl_gap = gap
            if gap:
                log('IN-PLACE HOME: {} unhomed with NO measurement -- '
                    'staying pending; nothing can be declared for it until '
                    'a read lands'.format(', '.join(gap)))
        if not jns:
            return                    # pending STAYS set: retry on a read
        # throttle: this runs at tick rate now, and a home that keeps
        # failing must not become a hot loop of mode switches
        if now_mono() < getattr(self, '_inpl_next', 0.0):
            return
        self._inpl_next = now_mono() + 2.0
        try:
            # mode/teleop AFTER jns: this runs on every tick now, and
            # switching the task mode when there is nothing to home would
            # fight the operator for the whole session.
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            self.cmd.teleop_enable(0)
            self.cmd.wait_complete()
            # ONE JOINT PER PASS. The old loop homed joint 4, wiped
            # ini.4.home, then wrote ini.5.home and homed joint 5 -- all
            # while joint 4 was still in its homing sequence, because
            # wait_complete() returns on command acceptance, not on
            # completion. Those writes landed inside joint 5's window
            # between cmd.home() and the destination latch at
            # homing.c:1279, and C travelled -114.7048 deg on a declare
            # that must not move at all (2026-08-07).
            # Now: arm -> verify -> home ONE joint, then return. The next
            # joint needs every head joint back at HOME_IDLE, which only
            # happens once this one has finished; the tick retries.
            for jn, ax in jns:
                d = self.hr_deg[ax]
                # HOME == home_offset -> travel = HOME - home_offset = 0.
                if not self.set_home_pins(jn, d, d, 'declare in place'):
                    self.inplace_pending = True   # refused: retry when quiet
                    return
                self.declare_snap[jn] = self.motor_fb(jn)
                self.cmd.home(jn)
                self.cmd.wait_complete()
                log('IN-PLACE HOME: joint {} ({}) declared at {:+.3f} deg, '
                    'zero travel; nothing writes those pins until it is '
                    'confirmed idle'.format(jn, ax.upper(), d))
                self.inplace_pending = True       # the other joint, next tick
                return
        except Exception as e:
            log('IN-PLACE HOME failed: {}'.format(e))

    def fire_pending_refs(self):
        # Home queued A/C joints ONLY with an armed read and ONLY when no
        # OTHER joint is homing: homing.c do_home_one_joint() overwrites
        # an active sequencer's state unconditionally (the 2026-07-31
        # joint-4 wedge). Called from read_done AND every tick, so a
        # deferral retries until XYZ finish; the read stays armed until
        # verify. A FAILED read never arms -> A/C stay unhomed, loudly.
        if not self.pending_ref or not self.read_armed:
            return
        try:
            self.stat.poll()
            if any(self.stat.joint[j]['homing'] for j in range(6)
                   if j not in self.pending_ref):
                return
        except Exception:
            return
        # ONE JOINT PER DISPATCH (2026-08-06 23:13 wedge): home(4)+home(5)
        # back-to-back stomped the homing state machine -- C won, A's
        # cycle orphaned with homing latched through abort AND off/on.
        # do_home_one_joint sets sequencer state unconditionally, so two
        # rapid calls are the 2026-07-31 wedge in a new coat. The tick
        # retries this method; the guard above holds joint 5 back until
        # joint 4's cycle fully completes.
        jn = sorted(self.pending_ref)[0]
        try:
            self.cmd.mode(linuxcnc.MODE_MANUAL)
            self.cmd.wait_complete()
            self.cmd.teleop_enable(0)
            self.cmd.wait_complete()
            # DESTINATION IS ALWAYS 0 -- never inherit ini.N.home from an
            # earlier cycle. do_inplace() parks the read value there to home
            # without motion and restores 0 on the homed EDGE; if that edge
            # is late or missed, the leftover becomes THIS home's target and
            # the head travels to the PREVIOUS read instead of zero.
            # 2026-08-07, measured: travel was HOME - home_offset
            # = -0.1 - 66.6828 = -66.7828, which is the 0/66/0/66 swing.
            _ax = 'a' if jn == 4 else 'c'
            _d = self.hr_deg.get(_ax)
            if _d is None:
                log('REF dispatch: joint {} has no armed read -- refusing'
                    .format(jn))
                return
            # A REF drives the head TO ZERO: home = 0, offset = the reading.
            # Both are written and read back here, immediately before the
            # command, so no leftover from any earlier cycle can be what
            # this home consumes.
            if not self.set_home_pins(jn, 0.0, _d, 'REF joint {} to zero'
                                      .format(jn)):
                return                     # refused: the tick retries
            self.cmd.home(jn)
            self.cmd.wait_complete()
            self.pending_ref.discard(jn)   # only once it really went out
            self.hr_deg[_ax] = None
            log('REF dispatch: read armed + no cycle running -> homing '
                'joint {} ({} still queued)'.format(jn, sorted(self.pending_ref) or 'none'))
        except Exception as e:
            log('REF dispatch failed: {}'.format(e))

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
            # per-axis REF A / REF C and the HOME ALL handoff: dispatch is
            # factored to fire_pending_refs(), which refuses to cut into a
            # running homing cycle (the 2026-07-31 joint-4 wedge) and is
            # retried from the tick until XYZ sequences finish.
            self.fire_pending_refs()
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

    # NO POST-HOME VERIFY (2026-08-10). It asked "is the head at zero after
    # homing?" -- the right question only while homing DROVE the head to
    # zero. With HOME_ABSOLUTE_ENCODER=2 homing sets the coordinate and moves
    # nothing, so the test could only ever fail, and its failure path
    # unhomed the joint. Homing can no longer put the head anywhere, so
    # there is nothing left to verify. Driving to zero is now an ordinary
    # move and carries ordinary motion protection.

    # ---- teleop recovery (port of _ensure_teleop/_auto_back_to_manual) -------
    def seq_active(self, now):
        try:
            if not bool(h['seq-active-in']):
                if self.seq_was:
                    self.seq_was = False
                    log('SEQ INTERLOCK released -- MANUAL restore is live')
                return False
            hb = int(h['seq-hb-in'])
            if hb != self.seq_hb_last:
                self.seq_hb_last = hb
                self.seq_hb_t = now
            fresh = (now - self.seq_hb_t) < 5.0
            if fresh and not self.seq_was:
                self.seq_was = True
                log('SEQ INTERLOCK armed -- mode belongs to the sequence')
            if not fresh and self.seq_was:
                self.seq_was = False
                log('SEQ INTERLOCK flag STALE (no heartbeat 5 s) -- '
                    'ignoring it, MANUAL restore live again')
            return fresh
        except Exception:
            return False

    def ensure_teleop(self):
        try:
            if self.stat.task_state == linuxcnc.STATE_ON and all(self.stat.homed[:6]):
                self.cmd.teleop_enable(1)
                log('TELEOP re-entered (machine ON + homed) -> MPG live')
        except Exception as e:
            log('TELEOP re-enter failed: {}'.format(e))

    # ---- main tick (0.25 s) --------------------------------------------------
    SPIN_CONFIRM_S = 3.0     # VFD accel + relay: generous, still catches a no-start

    def _spindle_confirm(self, now):
        """Abort if the spindle is commanded and the VFD never confirms.

        WHY THIS IS NOT PARANOIA: on 2026-08-12 four rotary_face runs put a
        cutter into a cut with the spindle stopped and nothing said a word --
        the Mollom had no error because it had never been asked to run. A
        feed into stationary flutes is how tools and workpieces get destroyed
        quietly.

        THE STOP IS AN ABORT, NOT A MESSAGE. A toast the operator reads
        afterwards is not a guard. abort() drops the interpreter and the
        queue, which is exactly what should happen when the cutter is dead.
        """
        try:
            cmd = bool(h['spin-cmd-in'])
            run = bool(h['spin-run-in'])
        except Exception:
            return
        if not cmd:
            self._spin_since = None
            self._spin_faulted = False
            return
        if run:
            self._spin_since = None
            self._spin_faulted = False
            return
        if getattr(self, '_spin_since', None) is None:
            self._spin_since = now
            return
        if self._spin_faulted or now - self._spin_since < self.SPIN_CONFIRM_S:
            return
        self._spin_faulted = True
        text = ('SPINDLE NOT RUNNING -- commanded on %.1f s ago and the VFD '
                'running contact on 7I97 IN11 never came back. Program '
                'ABORTED before feeding into a stopped cutter. Check the '
                'Mollom keypad and R1.' % (now - self._spin_since))
        log(text)
        try:
            self.cmd.error_msg(text)
        except Exception:
            pass
        try:
            self.cmd.abort()
        except Exception:
            log('SPINDLE NOT RUNNING: abort() FAILED -- stop the machine by hand')

    def _fault_say(self, pin, flag, text):
        """Post `text` once per rising edge of `pin`. Reading our own netted
        pin costs nothing; hal.get_value() would spin the global HAL mutex,
        which has hung this loop before (ned_brain.py:122-124)."""
        try:
            now_on = bool(h[pin])
        except Exception:
            return
        if now_on and not getattr(self, flag, False):
            log(text)
            try:
                self.cmd.error_msg(text)
            except Exception:
                pass
        setattr(self, flag, now_on)

    def tick(self):
        try:
            self.stat.poll()
        except Exception:
            return
        s = self.stat
        now = time.time()

        # ---- SPINDLE FAULT ANNUNCIATION -------------------------------
        # RISING EDGE ONLY. Both pins sit asserted for as long as the fault
        # lasts, and a message every tick would bury the machine log and the
        # notification area under the same line a hundred times a second.
        self._spindle_confirm(now)
        self._fault_say('vfd-fault-in', 'vfd_said',
                        'SPINDLE VFD FAULT -- machine stopped. The Mollom has '
                        'tripped and is reporting a fault on 7I97 IN13. Clear '
                        'it on the drive keypad, then reset e-stop.')
        self._fault_say('overtemp-in', 'otemp_said',
                        'SPINDLE OVERTEMP -- machine stopped. The spindle '
                        'thermostat has opened. Drives and spindle are ALREADY '
                        'dead in hardware: the thermostat is in series in the '
                        'e-stop chain. Let the spindle cool before reset.')

        # HEAD HOMED EDGES -- TRACKED FIRST, BEFORE ANY EARLY RETURN.
        # This used to live at the bottom of the tick, below three `return`s.
        # A single-axis REF unhomes its joint and then the head READ owns the
        # tick for ~5 s (hr_step branch below), so the joint went unhomed AND
        # re-homed entirely inside that blind window: prev stayed True, no
        # rising edge was ever seen, the post-home verify never fired, and
        # verify_want stayed set FOREVER -- permanently refusing every later
        # REF A/C with "previous head cycle still completing". Found by the
        # unattended GUI campaign 2026-08-02: REF A once, then REF C dead for
        # the rest of the session.
        try:
            for _jn, _ax in ((4, 'a'), (5, 'c')):
                _cur = bool(s.homed[_jn])
                if _cur and not self.prev_head_homed[_jn]:
                    # DID THE DECLARE MOVE THE HEAD? It must not. This is
                    # the detector that would have caught C's -114.7048 deg
                    # swing the first time instead of after the fact --
                    # motor-pos-fb is raw motor position, untouched by
                    # home_offset, so any change here is real motion.
                    _snap = self.declare_snap.pop(_jn, None)
                    if _snap is not None:
                        _fb = self.motor_fb(_jn)
                        if _fb is None:
                            log('DECLARE: joint {} motor-pos-fb unreadable '
                                '-- motion NOT verified'.format(_jn))
                        elif abs(_fb - _snap) > 0.01:
                            _t = ('DECLARE MOVED THE HEAD: joint {} '
                                  'motor-pos-fb {:+.4f} -> {:+.4f} '
                                  '({:+.4f} deg) on a ZERO-TRAVEL declare'
                                  .format(_jn, _snap, _fb, _fb - _snap))
                            log(_t)
                            try:
                                self.cmd.error_msg(_t)
                            except Exception:
                                pass
                        else:
                            log('DECLARE: joint {} did not move '
                                '({:+.4f} -> {:+.4f}) -- correct'
                                .format(_jn, _snap, _fb))
                self.prev_head_homed[_jn] = _cur
        except Exception as _e:
            log('head-edge tracking failed: {}'.format(_e))

        # CONFIRMED WIPE. Drained only when EVERY head joint is back at
        # HOME_IDLE -- positive confirmation that no home is in flight, which
        # is the whole safety condition. Deliberately not load-bearing:
        # set_home_pins() rewrites both pins before every home, so a wipe
        # that is late or missed can no longer feed a later cycle. It is
        # hygiene -- no number outlives its one use (operator 2026-08-07:
        # "delete every other fucking number or pin after use").
        # silent pre-check: head_quiet() logs, and the tick runs ~10x/s, so
        # asking it directly would spam the log for the whole of every home
        if self.pin_wipe and all(self.home_state(_j) == self.HOME_IDLE
                                 for _j in self.HEAD_JN):
            for _jn in sorted(self.pin_wipe):
                self.wipe_home_pins(_jn, 'consumed -- confirmed idle')
        try:
            h['head-busy'] = self.head_busy()
        except Exception:
            pass

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
            # ALWAYS A FRESH READ AFTER POWER-ON. There used to be a branch
            # here that reused the pre-launch read and scheduled inplace_at,
            # but it tested self.read_armed FIFTEEN LINES BELOW setting it
            # False, with nothing in between to set it back -- unsatisfiable,
            # so inplace_at was never assigned and its tick call site was
            # dead code. That is what left joint 5 unhomed on 2026-08-08:
            # read_done() became the only caller of do_inplace().
            # Deleted rather than repaired: a read taken AFTER the drives are
            # energised describes the head as it is at the moment we declare
            # it, which is the read worth trusting. It costs a few seconds.
            self.want_read = True
            log('MACHINE ON -> fresh head read (A/C will home IN PLACE, '
                'no motion)')
        if getattr(self, 'declare_at', None) and now >= self.declare_at:
            self.declare_at = None
            self.declare_xyzw()
        # EVERY TICK, unconditionally. do_inplace() homes ONE joint per pass
        # and re-arms inplace_pending for the next, so it NEEDS a periodic
        # caller. It had none: inplace_at is assigned at exactly one place
        # (the ON edge, and only when the pre-launch read was already
        # armed), so on a normal launch it stays None and this call site was
        # dead -- read_done() was the only caller, joint 4 homed, joint 5
        # never did, and everything downstream stayed locked (2026-08-08
        # 21:59). The routine is self-guarded by inplace_pending, so calling
        # it every tick costs one attribute test when there is nothing to do.
        self.do_inplace()
        self.tool_table_gate()
        self.restore_spindle_tool()
        self.apply_mode()
        self.b_power()
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
        self.fire_pending_refs()
        ha = bool(h['homeall-in'])
        if ha and not getattr(self, 'prev_homeall', False) and on:
            # 2026-08-06: A/C are OUT of the task home-all sequence.
            # ALWAYS force a fresh read -- a stale armed read from an
            # unfinished earlier cycle sailed through the guard and homed
            # A against an old offset (the compounding 66.6 deg tilt).
            self.read_armed = False
            self.want_read = True
            self.pending_ref = {4, 5}
            log('HOME ALL -> fresh head read forced; brain homes A/C '
                'read-gated once XYZ sequences finish')
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
                if self.pending_ref:
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
        if ac_homing and not self.read_armed:
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
        # (homed-edge tracking moved to the TOP of tick -- see the note there)
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
            # THE MOTION QUEUE IS THE TERM THAT WAS MISSING (2026-08-12).
            # interp_state goes IDLE as soon as the interpreter has READ the
            # file -- for a short program that is a fraction of a second --
            # while the trajectory planner is still executing everything it
            # queued. inpos + current_vel~0 are then TRUE at every pause
            # between blocks, so `done` went TRUE 18 s into a 5-minute
            # rotary_face cycle, this flip stole MANUAL, and the mode switch
            # ABORTED the rest of the program. Every PRINT had already been
            # emitted, including ROTARY FACE DONE, so the log looked like a
            # clean run while motion had executed only the opening rapids --
            # the M3 was still in the queue and was thrown away with it, so
            # the spindle never started and the VFD was never commanded.
            # Four runs died at 18 s, 16 s, 7 s and 7 s.
            # s.queue is the planner's queue depth and s.motion_type is 0
            # only when nothing is executing; together they say "the machine
            # has finished", which is what this flip actually needs.
            done = ((not interp_busy) and s.queue == 0 and s.motion_type == 0
                    and bool(s.inpos) and s.current_vel < 1e-6)
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
            if self.seq_active(now):
                # MODE INTERLOCK (operator 2026-08-06): an orchestrated MDI
                # chain owns the mode; restoring MANUAL between its steps
                # is the race that silently ate one MDI in N. Same shape as
                # the tcactive guard above. Counts only while the heartbeat
                # is alive, so a crashed GUI cannot leave the wheel dead --
                # 5 s after the beat stops, normal restore returns.
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


        # stored-home saver: forced on the just-stopped edge so the LAST jog
        # is always captured -- the 10 s timer alone lost a jog followed by a
        # quick shutdown (operator 23:5x)
        try:
            moving_now = (self.stat.current_vel > 1e-6 or
                          any(abs(self.stat.joint[j]['velocity']) > 1e-4
                              for j in (0, 1, 2, 3)))
        except Exception:
            moving_now = False
        if getattr(self, 'sh_was_moving', False) and not moving_now:
            self.sh_save(now, force=True)     # motion just ENDED
        else:
            self.sh_save(now)
        self.sh_was_moving = moving_now


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
