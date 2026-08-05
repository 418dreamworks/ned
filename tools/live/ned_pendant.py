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
JOG_SPEEDS = [('SLOW', 5.08), ('MED', 60.96), ('MAX', MAXV)]  # mm/s

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
h.newpin('jogspeed-out', hal.HAL_FLOAT, hal.HAL_OUT)  # 0..100 % -> linear_jog_slider
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
    if ax == 'a' and (h['lock-a'] or not _head_homed(4)):
        return True
    if ax == 'c' and (h['lock-c'] or not _head_homed(5)):
        return True
    return False


def adv(i, step):
    # next axis in the cycle direction, skipping locked ones (X/Y/Z can
    # never lock, so this always terminates on an unlocked axis)
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
last_release = 0.0
double_hold = False             # this press is the double-tap-and-hold (jog speed)
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
        h['jog-en-' + ax] = bool(i == ax_i and not gate_off and not locked(i))
    h['jog-scale-lin'] = inc / CPD
    h['jog-scale-ang'] = min(inc, ANG_CAP) / CPD
    h['sel-axis'] = ax_i
    h['increment'] = inc
    h['inc-index'] = inc_i
    h['jogspeed-out'] = JOG_SPEEDS[spd_i][1] / MAXV * 100.0


apply(False)
print('ned_pendant: ready -- increments {} (from [DISPLAY]INCREMENTS), '
      'tap=next axis, double-tap=back, press+wheel=jump size, '
      'double-tap+hold+wheel=feed override'.format(INCREMENTS), flush=True)

try:
    while True:
        time.sleep(0.06)
        pressed = not h['button-raw']
        wheel = h['wheel']
        now = time.time()

        if locked(ax_i):                 # LOCK flipped on while selected
            ax_i = adv(ax_i, 1)
            print('ned_pendant: axis -> {} (previous locked)'.format(
                AXES[ax_i].upper()), flush=True)

        if pressed and not btn_prev:                      # button went down
            press_t = now
            wheel0 = wheel
            inc_i0 = inc_i
            spd_i0 = spd_i
            rotated = False
            # 0.36 s = 80% of the original 0.45 s (operator taps fast in
            # sequence; slower pairs must register as single taps)
            double_hold = (now - last_release) < 0.36     # second tap of a double

        if pressed:
            detents = (wheel - wheel0) // DETENT
            if detents != 0:
                rotated = True
            if double_hold:
                # jog speed: 3 presets (SLOW/MED/MAX), right = faster.
                # Takes effect through NML maxvel -- caps the wheel chase.
                new_i = max(0, min(len(JOG_SPEEDS) - 1,
                                   spd_i0 + detents // SPEED_DETENTS))
                if new_i != spd_i:
                    spd_i = new_i
                    name, v = JOG_SPEEDS[spd_i]
                    try:
                        jcmd.maxvel(v)
                    except Exception as e:
                        print('ned_pendant: maxvel failed: {}'.format(e), flush=True)
                    print('ned_pendant: jog speed -> {} ({} mm/s)'.format(
                        name, v), flush=True)
            else:
                # jump size: step through the on-screen increment list,
                # 25 detents per step (1/detent was too abrupt)
                new_i = max(0, min(N_INC - 1, inc_i0 + detents // INC_DETENTS))
                if new_i != inc_i:
                    inc_i = new_i
                    print('ned_pendant: jump slot {} -> {}/detent on {}'.format(
                        inc_i, INC_TABLE[AXES[ax_i]][inc_i],
                        AXES[ax_i].upper()), flush=True)

        if (not pressed) and btn_prev:                    # button released
            # rotated or long-held presses select things; only CLEAN quick taps
            # switch axis. A quick second tap (double_hold armed at its press,
            # but neither held nor rotated) = the double-tap-back gesture.
            if not rotated and (now - press_t) < 0.4:
                if double_hold:
                    # quick double-tap = previous axis (first tap advanced +1)
                    ax_i = adv(adv(ax_i, -1), -1)
                    print('ned_pendant: axis <- {} (double-tap back)'.format(
                        AXES[ax_i].upper()), flush=True)
                else:
                    ax_i = adv(ax_i, 1)
                    print('ned_pendant: axis -> {}'.format(AXES[ax_i].upper()),
                          flush=True)
            last_release = now
            double_hold = False

        btn_prev = pressed
        apply(pressed)
except KeyboardInterrupt:
    pass
