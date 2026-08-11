#!/usr/bin/env python3
# ned_pendant.py -- GUI-independent MPG pendant state machine (userspace HAL
# component). Operator-specified behavior (2026-07-31):
#   wheel                  = jog the selected axis
#   TAP                    = next axis  X -> Y -> Z -> A -> C
#   quick DOUBLE-TAP       = previous axis
#   PRESS + rotate         = jump size per detent, stepping through the SAME
#                            increment list Probe Basic shows on screen
#                            ([DISPLAY]INCREMENTS): rotate right = bigger.
#                            Jog is gated off while the button is pressed.
#   DOUBLE-TAP + HOLD + rotate = feed override -- literally moves the on-screen
#                            slider (NML EMC_TRAJ_SET_SCALE; the qtpyvcp slider
#                            follows status). 2% per detent, right = faster.
# A/C jump size is capped at 1 deg/detent regardless of the linear increment.
# Outputs: one-hot jog-en-<axis>, jog-scale-lin/-ang (per COUNT, CPD=4),
# sel-axis (0..4), increment (mm per DETENT) for any display that wants it.
import os
import re
import time

import hal
import linuxcnc

AXES = ['x', 'y', 'z', 'a', 'c']

# PER-AXIS jump ladders (operator 2026-08-04): the SELECTED SLOT is shared
# across axes -- "keep the setting the same, just number depends on the
# axis". Fastest per axis: X 2 mm, Y/Z 1 mm, A/C 0.5 deg with the top three
# rotary slots 0.1 / 0.25 / 0.5. Replaces the single [DISPLAY]INCREMENTS
# list, which could not differ per axis.
INC_TABLE = {
    'x': [0.01, 0.05, 0.1, 0.5, 2.0],
    'y': [0.01, 0.05, 0.1, 0.5, 1.0],
    'z': [0.01, 0.05, 0.1, 0.5, 1.0],
    'a': [0.01, 0.05, 0.1, 0.25, 0.5],
    'c': [0.01, 0.05, 0.1, 0.25, 0.5],
}
N_INC = 5
CPD = 4                  # counts per detent (tools/groundtruth/mpgjog.sh)
DETENT = 4               # wheel counts in one detent
INC_DETENTS = 10         # detents per JUMP-SIZE step (operator: 25 too much, 10 will do)
ANG_CAP = 1.0            # deg per detent max on A/C
SPEED_DETENTS = 10       # detents per JOG-SPEED step (3 presets, below)


def ini_increments():
    # [DISPLAY]INCREMENTS = "10 mm, 1 mm, 0.1 mm, 0.01 mm" -- the list Probe
    # Basic displays. Values parsed in INI order; cycling maps rotate-right to
    # BIGGER regardless of that order (we sort ascending internally).
    try:
        ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])
        raw = ini.find('DISPLAY', 'INCREMENTS') or ''
    except Exception:
        raw = ''
    vals = []
    for part in raw.replace(',', ' ').split():
        m = re.match(r'^([0-9.]+)$', part)
        if m:
            try:
                vals.append(float(m.group(1)))
            except ValueError:
                pass
    vals = sorted(set(v for v in vals if v > 0))
    return vals or [0.01, 0.1, 1.0, 10.0]


INCREMENTS = ini_increments()   # kept only for the startup banner

# 3 JOG SPEEDS (operator 2026-08-01, replaces the 0-100% number): SLOW =
# 1 ft/min, MED = 12 ft/min, MAX = the machine ceiling ([TRAJ]
# MAX_LINEAR_VELOCITY, written by ned_params.sh -- Z is further capped by
# its own joint limit automatically). Applied via NML maxvel (the V
# slider): that is what actually caps position-mode wheel chasing.
# A/C are ANGULAR -- maxvel does not touch them; they keep full speed.
def ini_maxv():
    try:
        ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])
        return float(ini.find('TRAJ', 'MAX_LINEAR_VELOCITY') or 200.0)
    except Exception:
        return 200.0


MAXV = ini_maxv()
# mm/s. Operator 2026-08-11: "make fast feed 8000 ... medium can be 3000"
# (mm/min). A/C are unaffected -- they are capped by MAX_ANGULAR_VELOCITY.
JOG_SPEEDS = [('SLOW', 5.08), ('MED', 50.0), ('MAX', 133.333)]  # 3000 / 8000

h = hal.component('pendant')
for _ax in AXES:
    h.newpin('jog-en-' + _ax, hal.HAL_BIT, hal.HAL_OUT)
h.newpin('jog-scale-lin', hal.HAL_FLOAT, hal.HAL_OUT)
h.newpin('jog-scale-ang', hal.HAL_FLOAT, hal.HAL_OUT)
h.newpin('button-raw', hal.HAL_BIT, hal.HAL_IN)   # TRUE = released, FALSE = pressed
h.newpin('wheel', hal.HAL_S32, hal.HAL_IN)
h.newpin('sel-axis', hal.HAL_S32, hal.HAL_OUT)    # 0..4 = X Y Z A C
h.newpin('increment', hal.HAL_FLOAT, hal.HAL_OUT)  # mm per DETENT (jump size)
# GUI <-> WHEEL SYNC (operator 2026-08-05, asked repeatedly): the on-screen
# increment row writes this index; the pendant adopts it, so clicking a
# speed on screen moves the highlight AND the applied jump size, and the
# wheel and GUI can never disagree. -1 = GUI has not spoken.
# the AUTHORITATIVE slot index (0..N_INC-1). PB and the second-monitor DRO
# both read this -- neither keeps its own idea of the jog speed
# (operator 2026-08-05: "the dro must get the speed and axis selection
# from PB and not keep its own records").
h.newpin('inc-index', hal.HAL_S32, hal.HAL_OUT)
# GUI -> wheel: PB writes the slot it was clicked on. Adopted ONLY on a
# CHANGE, and the value present at startup is never adopted -- PB's stock
# increment row emits a selection while it builds, and adopting that pinned
# the wheel to the smallest step (jogging looked dead, 2026-08-05).
h.newpin('inc-set', hal.HAL_S32, hal.HAL_IN)
h.newpin('jogspeed-out', hal.HAL_FLOAT, hal.HAL_OUT)  # pinned at 100 %
# ZERO THE SELECTED AXIS FROM THE WHEEL (operator 2026-08-11: "ive never
# actually used the speed slider. like, ever. so get rid of it. it can be at
# 100pct all the time. instead a doubleclick and then registering 100 detents
# moves in any direction zeros the selected axis"). Double-tap-and-hold was
# feed override; it is the zero gesture now. Pulsed TRUE briefly; the GUI
# issues the G10 L20 for whatever axis sel-axis names.
h.newpin('zero-axis-out', hal.HAL_BIT, hal.HAL_OUT)
# WHICH axis to zero. Not sel-axis: the first tap of the double-tap has
# already advanced sel-axis by one, so sel-axis names the wrong one.
h.newpin('zero-axis-idx', hal.HAL_S32, hal.HAL_OUT)
# TRIPLE-TAP = LOCK/UNLOCK THE SELECTED AXIS (operator 2026-08-11: "Triple
# click on mpg locks out all other inputs to that axis ... otherwise i have
# to hike back to computer to press the lock unlock"). Pulsed; the GUI
# THE MPG LOCK IS THE PENDANT'S OWN, AND IS NOT THE GUI LOCK (operator
# 2026-08-11: "the MPG lock and the gui lock are completely independent.
# The GUI lock means an axis is completely not selectable"):
#   GUI lock (lock-x..c, from the DRO buttons) -> axis is SKIPPED entirely
#   MPG lock (here, triple-tap)                -> axis is SELECTABLE but
#                                                 will not jog, so it can
#                                                 be triple-tapped free
# Published so the standalone DRO can paint the letter red.
for _a in ('x', 'y', 'z', 'a', 'c'):
    h.newpin('mpg-lock-' + _a, hal.HAL_BIT, hal.HAL_OUT)
h.newpin('lock-x', hal.HAL_BIT, hal.HAL_IN)  # per-axis MPG locks, DRO
h.newpin('lock-y', hal.HAL_BIT, hal.HAL_IN)  # single-click (operator
h.newpin('lock-z', hal.HAL_BIT, hal.HAL_IN)  # 2026-08-06); start UNLOCKED
h.newpin('lock-a', hal.HAL_BIT, hal.HAL_IN)  # LOCK A/C (DRO buttons via ned-tab):
h.newpin('lock-c', hal.HAL_BIT, hal.HAL_IN)  # locked axes are SKIPPED in the cycle
h.ready()

# LOUD DEATH (same 2026-08-01 silent-vanish incident as ned_brain): log every
# signal and exit to stdout -> lcnc.log so the killer has a name next time.
import atexit
import signal
import sys


def _death(signum, frame):
    print('ned_pendant EXIT on signal %d (%s)'
          % (signum, signal.Signals(signum).name), flush=True)
    sys.exit(128 + signum)


for _s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
    signal.signal(_s, _death)
atexit.register(lambda: print('ned_pendant exited (atexit; normal interpreter exit)', flush=True))


_hstat = {'s': None, 't': 0.0, 'h4': False, 'h5': False}


def _head_homed(jn):
    """A/C auto-lock (operator 2026-08-01: 'lock the mpg until A and C are
    auto homed'): a wheel bump during the ~10 s power-on absolute read moves
    the head mid-capture and the in-place home lands on a stale angle. The
    pendant refuses A/C until that joint's startup home is done. Cached
    0.5 s NML poll; on any stat error FAIL LOCKED (never jog blind)."""
    import time as _t
    now = _t.time()
    if now - _hstat['t'] > 0.5:
        _hstat['t'] = now
        try:
            if _hstat['s'] is None:
                _hstat['s'] = linuxcnc.stat()
            _hstat['s'].poll()
            _hstat['h4'] = bool(_hstat['s'].homed[4])
            _hstat['h5'] = bool(_hstat['s'].homed[5])
            _hstat['anyh'] = any(_hstat['s'].joint[j]['homing']
                                 for j in range(6))
        except Exception:
            _hstat['s'] = None
            _hstat['h4'] = _hstat['h5'] = False
            _hstat['anyh'] = True
    return _hstat['h4'] if jn == 4 else _hstat['h5']


def homing_active():
    _head_homed(4)          # refresh the cache
    return _hstat.get('anyh', True)


def locked(i):
    # HOMING INTERLOCK (operator 2026-08-01, in caps): when ANY homing
    # cycle is running, the WHOLE wheel is dead -- every axis. A wheel
    # bump mid-cycle injects free-mode jog targets that stall or corrupt
    # the cycle (the 22:55 A/C zero-return failure). Release when the
    # cycle ends. On top of that: A/C stay locked until their startup
    # auto-home lands (position unknown = no head jogging, ever).
    if homing_active():
        return True
    ax = AXES[i]
    # NOTE: locked axes are no longer skipped in the selection cycle
    # (operator 2026-08-11: "you can select the axis, just do nothing
    # except triple click") -- see the eviction block in the main loop.
    if ax in ('x', 'y', 'z') and h['lock-' + ax]:
        return True
    if ax == 'a' and (h['lock-a'] or not _head_homed(4)):
        return True
    if ax == 'c' and (h['lock-c'] or not _head_homed(5)):
        return True
    return False


def adv(i, step):
    # Skips GUI-LOCKED axes only. An MPG-locked axis is still selectable --
    # that is the whole point of it (operator 2026-08-11).
    for _ in range(len(AXES)):
        i = (i + step) % len(AXES)
        if not locked(i):
            break
    return i

ax_i = 0
# start at the MIDDLE slot (0.1), not the micron setting -- operator
# 2026-08-04: waking up in 0.01 meant every session began with the wheel
# doing nearly nothing
inc_i = 2
_inc_seen = None        # startup value of inc-set, never adopted
spd_i = 2                       # start at MAX = the machine's boot reality
jcmd = linuxcnc.command()       # NML maxvel = the V slider = the wheel cap
btn_prev = False
press_t = 0.0
double_hold = False             # this press is the double-tap-and-hold (zero)
zero_sent = False               # the zero gesture already fired this press
zero_pulse = 0                  # passes left holding zero-axis-out high
zero_ax = 0                     # axis the zero gesture targets
pending_double = 0.0            # a double waiting out its triple window
mpg_lock = [False] * len(AXES)  # the pendant's OWN per-axis MPG lock
refractory = 0.0                # ignore presses until this time (post-lock)
lock_sent = False               # a lock toggle fired on this press
pending_tap = 0.0               # a single tap waiting out its double window
ZERO_DETENTS = 100              # a full 100 detents -- never an accident
rotated = False                 # wheel moved during this press
wheel0 = 0
inc_i0 = 0
spd_i0 = 2


def apply(gate_off):
    # ONE speed setting (inc_i, starts at the middle slot), ONE per-axis
    # table (INC_TABLE). The wheel owns the slot; the GUI may hand it a new
    # one by CHANGING inc-set.
    global inc_i, _inc_seen
    try:
        g = int(h['inc-set'])
        if _inc_seen is None:
            _inc_seen = g                # startup value: never adopted
        elif g != _inc_seen:
            _inc_seen = g
            if 0 <= g < N_INC:
                inc_i = g
    except Exception:
        pass
    inc = INC_TABLE[AXES[ax_i]][inc_i]
    for i, ax in enumerate(AXES):
        # locked() covers the homing interlock too: the enable pin itself
        # drops for EVERY axis the moment any homing cycle starts
        h['jog-en-' + ax] = bool(i == ax_i and not gate_off
                                 and not locked(i) and not mpg_lock[i])
        h['mpg-lock-' + ax] = bool(mpg_lock[i])
    h['jog-scale-lin'] = inc / CPD
    h['jog-scale-ang'] = min(inc, ANG_CAP) / CPD
    h['sel-axis'] = ax_i
    h['increment'] = inc
    h['inc-index'] = inc_i
    # ALWAYS 100 %. The slider is gone; the increment slot is the only
    # speed control, which is the one the operator actually uses.
    h['jogspeed-out'] = 100.0


apply(False)
print('ned_pendant: ready -- increments {} (from [DISPLAY]INCREMENTS), '
      'tap=next axis, double-tap=back, press+wheel=jump size, '
      'double-tap+hold+100 detents=ZERO the selected axis'.format(INCREMENTS), flush=True)

try:
    while True:
        time.sleep(0.06)
        pressed = not h['button-raw']
        wheel = h['wheel']
        now = time.time()

        # GUI LOCK = COMPLETELY NOT SELECTABLE (operator 2026-08-11: "The
        # GUI lock means an axis is completely not selectable"). Flipped on
        # while selected, it evicts. The MPG lock is the OPPOSITE and is
        # deliberately NOT handled here: an MPG-locked axis stays selected
        # so it can be triple-tapped free without walking to the screen.
        if locked(ax_i):
            _j = adv(ax_i, 1)
            if not locked(_j):
                ax_i = _j
                print('ned_pendant: axis -> {} (previous GUI-locked)'.format(
                    AXES[ax_i].upper()), flush=True)

        if pressed and not btn_prev and now < refractory:
            btn_prev = pressed            # inside the post-lock refractory:
            apply(pressed)                # swallow the press entirely
            continue
        if pressed and not btn_prev:                      # button went down
            press_t = now
            wheel0 = wheel
            inc_i0 = inc_i
            spd_i0 = spd_i
            rotated = False
            zero_sent = False
            lock_sent = False
            # 0.36 s = 80% of the original 0.45 s (operator taps fast in
            # sequence; slower pairs must register as single taps)
            # THIRD tap: cancel the pending double-tap-back and lock
            # instead. The double's action is DEFERRED for exactly this
            # reason (operator 2026-08-11: "you have to add the same
            # listener after double click so that you dont get a
            # doubleclick then a triple click applying").
            if pending_double > 0.0:
                pending_double = 0.0
                double_hold = False
                mpg_lock[ax_i] = not mpg_lock[ax_i]
                lock_sent = True         # this press is a LOCK and nothing else
                refractory = now + 0.6   # audit D4: a 4th tap must not
                                         # navigate off the axis just locked
                print('ned_pendant: MPG LOCK {} -> {} (triple tap)'.format(
                    AXES[ax_i].upper(),
                    'LOCKED' if mpg_lock[ax_i] else 'UNLOCKED'), flush=True)
            else:
                double_hold = pending_tap > 0.0          # second of a double
                if double_hold:
                    pending_tap = 0.0    # the first tap's advance is CANCELLED
            # No compensation needed any more: the first tap no longer
            # advances anything until its double-tap window has expired,
            # so ax_i IS the axis the operator is looking at.
            zero_ax = ax_i

        if pressed:
            # TRUNCATE TOWARD ZERO, not floor (audit D2). Python's //
            # rounds DOWN, so a single reverse count gave detents = -1 and
            # -1//10 = -1 -- one count of wheel jitter dropped the jump
            # size a whole slot and, via `rotated`, swallowed the tap.
            # Forward needed 40 counts for the same step.
            _raw = wheel - wheel0
            detents = int(_raw / DETENT)
            if detents != 0:
                rotated = True
            if lock_sent or mpg_lock[ax_i]:
                # MPG LOCK SWALLOWS EVERY OTHER INPUT (operator 2026-08-11:
                # "locks out all other inputs to that axis ... for anything to
                # register, it must be unlocked first"). Covers the ZERO gesture,
                # which otherwise wrote a work offset on a locked axis, and the
                # jump-size slot. lock_sent also stops a triple's third press
                # falling through to the jump-size branch.
                pass
            elif double_hold:
                # ZERO THE MOMENT 100 DETENTS LAND (operator 2026-08-11:
                # "the zero should happen when 100 detents are detected
                # instead of at the release"). Either direction. Once per
                # press, so keeping the wheel turning cannot re-fire it.
                if abs(detents) >= ZERO_DETENTS and not zero_sent:
                    zero_sent = True
                    h['zero-axis-idx'] = zero_ax
                    h['zero-axis-out'] = True
                    zero_pulse = 5
                    print('ned_pendant: ZERO {} ({} detents)'.format(
                        AXES[zero_ax].upper(), detents), flush=True)
            else:
                # jump size: step through the on-screen increment list,
                # 25 detents per step (1/detent was too abrupt)
                new_i = max(0, min(N_INC - 1,
                                   inc_i0 + int(detents / INC_DETENTS)))
                if new_i != inc_i:
                    inc_i = new_i
                    print('ned_pendant: jump slot {} -> {}/detent on {}'.format(
                        inc_i, INC_TABLE[AXES[ax_i]][inc_i],
                        AXES[ax_i].upper()), flush=True)

        if (not pressed) and btn_prev:                    # button released
            # rotated or long-held presses select things; only CLEAN quick taps
            # switch axis. A quick second tap (double_hold armed at its press,
            # but neither held nor rotated) = the double-tap-back gesture.
            # THE WHOLE GESTURE IS JUDGED HERE, ONCE, ON RELEASE (operator
            # 2026-08-11): a double-click released with NO wheel movement =
            # previous axis; a double-click with 100+ detents turned before
            # that second release = ZERO the axis you were on. Deciding
            # mid-hold fired while the operator was still turning.
            if zero_sent or lock_sent:
                # ONCE A GESTURE HAS FIRED, THE RELEASE DOES NOTHING
                # (operator 2026-08-11: "if triple click, listen for
                # completion of triple click command only. all others,
                # ignore"). Without this the third press's release fell
                # through to pending_tap and queued an axis advance 0.36 s
                # after the lock toggle.
                pass
            # NO 0.4 s CEILING (audit D5): it required a quick release, so
            # holding tap 1 or 2 slightly long silently ate the whole gesture
            # -- no advance, no reverse, no feedback. A press that never turned
            # the wheel is a tap however long it was held.
            elif not rotated:
                if double_hold:
                    # DEFERRED, like the single tap: a third tap inside the
                    # window turns this into a lock toggle instead.
                    pending_double = now
                else:
                    # DEFERRED: a single tap advances only once the
                    # double-tap window closes. Advancing on the release
                    # made every double-tap advance first and act on the
                    # NEXT axis (operator 2026-08-11: "double click still
                    # advances").
                    pending_tap = now
            double_hold = False

        # the deferred single tap lands here, once nothing followed it
        if pending_tap and not pressed and (now - pending_tap) > 0.36:
            pending_tap = 0.0
            ax_i = adv(ax_i, 1)
            print('ned_pendant: axis -> {}'.format(AXES[ax_i].upper()),
                  flush=True)
        # and the deferred double, once no third tap followed
        if pending_double and not pressed and (now - pending_double) > 0.36:
            pending_double = 0.0
            ax_i = adv(ax_i, -1)
            print('ned_pendant: axis <- {} (double-tap back)'.format(
                AXES[ax_i].upper()), flush=True)
        if zero_pulse:
            zero_pulse -= 1
            if zero_pulse == 0:
                h['zero-axis-out'] = False
        btn_prev = pressed
        apply(pressed)
except KeyboardInterrupt:
    pass
