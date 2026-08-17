#!/usr/bin/env python3
"""dro2 -- the second-monitor DRO (operator 2026-08-05).

Deliberately NOT a Probe Basic extension: a self-contained process that
reads LinuxCNC directly, so a GUI fault can never take the numbers away
and a DRO change can never destabilise the GUI.

WHAT IS ON SCREEN, and nothing else:
  - top strip: the jog-speed indicator. A white block on black that only
    CHANGES POSITION -- one slot per increment step. No text, no scale.
  - one row per configured axis: a small letter (it carries no
    information) and two BIG numbers, machine then work.
  - the selected MPG axis row -- letter and both numbers -- is bright
    green. Everything else is white.
  - numbers occupy ~80% of the screen height, split evenly across rows.

DATA, all read straight from LinuxCNC:
  - positions: linuxcnc.stat (actual_position = machine; work subtracts
    g5x/g92/tool offsets, the same arithmetic the main DRO uses)
  - axes: [TRAJ]COORDINATES from the running ini, duplicates dropped
    (ned's X gantry twin is one axis on screen)
  - selected axis + jog increment: our own HAL pins, netted to the
    pendant's signals at startup via halcmd. Instance access only, never
    hal.get_value (that spins the global HAL mutex). If HAL is not up the
    numbers still run -- only the highlight and the strip go idle.

RUN:  tools/live/dro2.py            (fullscreen on the second screen)
      tools/live/dro2.py --screen 0 (force a screen index)
      tools/live/dro2.py --window   (windowed, for a look on one monitor)
"""

import os
import signal
import subprocess
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PySide6.QtCore import Qt, QTimer                       # noqa: E402
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QColor  # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QLabel,    # noqa: E402
                               QVBoxLayout, QHBoxLayout)

import linuxcnc                                             # noqa: E402

GREEN = '#2ee62e'          # selected row
PROBE_RED = '#ff2020'      # toolsetter is touching -- visible across the shop
LOCK_RED = '#ff4040'       # this axis is MPG-locked: selectable, will not jog
WHITE = '#f0f0f0'
BLACK = '#000000'
N_SLOTS = 5                # jog increment ladder length (ned_pendant)
STRIP_H = 46               # top indicator strip height, px
# ---- VERSION: bump on EVERY PB / LinuxCNC edit. 'vNNN:' + <=30 chars ----
VERSION = 'v025:GUI ROW RED'
NUM_W = 9                  # fixed number field: '-4042.72 ' fits (12 ft X)
NUM_INT = 4                # linear integer digits: 0000.00 .. -4042.72 (12 ft X)
NUM_INT_ROT = 3            # degrees need only 000.00 (operator 2026-08-05)


# -xyzab (operator 2026-08-11): the workpiece rotary B takes over every
# control that used to drive C -- including the pendant's 5th slot and its
# lock. The pendant still publishes those on sig-mpg-lock-c / sig-lock-c
# (one pin set, remapped in HAL), so the DRO has to bind them to the row
# they now describe. Colouring C red while the operator locked B would be a
# lie on the one display that is trusted at a glance.
def _rotary_slot_letter():
    """Which axis does the pendant's rotary slot ACTUALLY drive?

    Ask HAL, not the environment. The pendant publishes that slot on
    pendant.jog-en-c -> signal mpg-sel-c no matter what it drives, and the
    postgui overlay nets that signal to the real axis:

        mpg-sel-c  ==> axis.b.jog-enable   (-xyzab)
        mpg-sel-c  ==> axis.c.jog-enable   (-xyzac)

    So the wiring itself is the answer, and it cannot be got wrong by a
    launch that forgets to export something. It WAS got wrong that way
    (2026-08-11): dro2 read NED_MODE, a restart that did not pass it fell
    back to 'c', the lock pins were bound to a row that is not on screen,
    and B stayed white while the operator had it locked in PB.
    """
    try:
        out = subprocess.run(['timeout', '5', 'halcmd', 'show', 'sig',
                              'mpg-sel-c'], capture_output=True,
                             text=True).stdout
        for ln in out.splitlines():
            ln = ln.strip()
            if ln.startswith('==> axis.') and ln.endswith('.jog-enable'):
                return ln.split('axis.', 1)[1].split('.', 1)[0].lower()
    except Exception:
        pass
    # HAL unreachable: fall back to the launch mode, then to the old default
    return 'b' if os.environ.get('NED_MODE', '') == 'xyzab' else 'c'


ROT = _rotary_slot_letter()


def ini_axes():
    """Axis letters the operator can actually command, asked of the RUNNING
    machine rather than assumed.

    Two things were wrong with taking this from a hardcoded fallback list:
    dro2 is a separate process that was never handed INI_FILE_NAME, so it
    ALWAYS used the fallback -- the standalone DRO showed a C row and no B
    at all under -xyzab -- and a fixed list cannot follow a mode change.

    So: letters come from [TRAJ]COORDINATES, and any axis whose joint has
    been clamped to a point is dropped. That clamp is how every mode parks
    an un-spelled rotary (ned_brain.apply_mode), so this needs no knowledge
    of which mode is running: -xyzac drops nothing, -xyzab drops the parked
    C, -xyz drops both. Nothing here names an axis.
    """
    path = os.environ.get('INI_FILE_NAME', '')
    letters, coords = [], ''
    try:
        ini = linuxcnc.ini(path) if path else None
        coords = (ini.find('TRAJ', 'COORDINATES') if ini else None) or ''
        for c in coords.replace(' ', '').upper():
            if c.isalpha() and c not in letters:
                letters.append(c)
    except Exception:
        pass
    if not letters:
        # no ini: the axis mask is the config's own answer, always there
        try:
            st = linuxcnc.stat(); st.poll()
            letters = [L for i, L in enumerate('XYZABCUVW')
                       if st.axis_mask & (1 << i)]
        except Exception:
            return ['X', 'Y', 'Z', 'A', 'C']
    # drop what cannot move. COORDINATES is positional, so its Nth letter is
    # joint N; a gantry letter appears twice and keeps its first joint.
    try:
        st = linuxcnc.stat(); st.poll()
        seq = [c for c in coords.replace(' ', '').upper() if c.isalpha()]
        jn = {}
        for i, c in enumerate(seq):
            jn.setdefault(c, i)
        live = []
        for L in letters:
            j = jn.get(L)
            if j is not None and j < st.joints:
                span = (st.joint[j]['max_position_limit']
                        - st.joint[j]['min_position_limit'])
                if span < 0.01:
                    continue          # clamped to a point: parked, not shown
            live.append(L)
        if live:
            letters = live
    except Exception:
        pass
    return letters


class JogStrip(QWidget):
    """White block on black; ONLY its position changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slot = 2
        self.probe = False
        self.setFixedHeight(STRIP_H)
        self.setAutoFillBackground(False)

    def set_probe(self, on):
        on = bool(on)
        if on != self.probe:
            self.probe = on
            self.update()

    def set_slot(self, i):
        i = max(0, min(N_SLOTS - 1, int(i)))
        if i != self.slot:
            self.slot = i
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BLACK))
        w = self.width() / float(N_SLOTS)
        p.fillRect(int(self.slot * w) + 4, 6,
                   int(w) - 8, self.height() - 12,
                   QColor(PROBE_RED if self.probe else WHITE))
        # VERSION MARKER (operator 2026-08-07): the end-of-edit marker.
        # BUMP IT on every PB or LinuxCNC change -- it is the cheapest,
        # most instant signal that a launch carries the new code.
        # Blue reads on both the black strip and the white jog block.
        f = p.font()
        f.setPointSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor('#3AA0FF'))
        p.drawText(self.rect().adjusted(10, 0, -10, 0),
                   Qt.AlignVCenter | Qt.AlignLeft, VERSION)
        p.end()


class Dro2(QWidget):

    def __init__(self, windowed=False):
        super().__init__()
        self.setWindowTitle('ned DRO')
        self.setStyleSheet('background: %s;' % BLACK)
        self.axes = ini_axes()
        # RE-ASK, don't assume. The axis set is not fixed at startup:
        # a parked rotary is clamped by ned_brain.apply_mode only once
        # the launch sequence has put it where it belongs, which is
        # seconds AFTER this window exists. Sampling once left the
        # parked C on screen for the whole session. Re-checking costs
        # one NML poll every few seconds and needs no idea of which
        # mode is running.
        self._axes_timer = QTimer(self)
        self._axes_timer.timeout.connect(self._recheck_axes)
        self._axes_timer.start(4000)
        self.stat = linuxcnc.stat()
        self.sel = 0
        self._mm = True
        self.slot = 2
        self.probe = False
        self.locks = {}
        self.guilocks = {}
        self._hal = None
        self._hal_setup()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.strip = JogStrip()
        root.addWidget(self.strip, 0)      # stretch 0: fixed strip

        # column headers (operator 2026-08-06: "i need to know WCS vs
        # MCS"). WORK on the LEFT, MCS on the RIGHT, so the two DROs read
        # the same way round (operator 2026-08-11: "put work on left and
        # MCS on right to line it up with guiDRO") -- reading a machine
        # number as a work number is the kind of mistake that ends in a
        # crash. Fixed height; the axis rows give up the space.
        hdr = QWidget()
        hrow = QHBoxLayout(hdr)
        hrow.setContentsMargins(14, 0, 14, 0)
        hrow.setSpacing(10)
        self.hdr_pad = QLabel('')
        h_m = QLabel('MCS')
        h_w = QLabel('WCS')
        # THIRD COLUMN: TARGET, not DTG. Operator 2026-08-16: "i want DTG back,
        # but instead of DTG, I want is as 'Target' where we jog to instead of
        # how far to go. make it 3 cols in both DROs, use the current workplace
        # coordinate." Same order as the PB DRO -- WCS, TARGET, MCS -- so the
        # two still read the same way round.
        h_t = QLabel('TARGET')
        for _h in (h_m, h_w, h_t):
            # CENTRED, and the numbers below are centred too -- see the note
            # on the row labels. Both halves then carry their content in the
            # middle, so the header and its column cannot be out of step
            # (operator 2026-08-11: "get the dro so that both columns take up
            # the space ... following the banner above").
            _h.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            _h.setStyleSheet('color: %s; background: transparent;' % WHITE)
        hrow.addWidget(self.hdr_pad, 0)
        hrow.addWidget(h_w, 5)
        hrow.addWidget(h_t, 5)
        hrow.addWidget(h_m, 5)
        self.hdr = hdr
        self.hdr_labels = (h_m, h_w, h_t)
        self.hdr_wcs = h_w
        root.addWidget(hdr, 0)

        self.rows = []
        self._holders = {}
        self._all_axes = list(self.axes)
        for letter in self.axes:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(14, 0, 14, 0)
            row.setSpacing(10)
            lab = QLabel(letter)
            # letters sit RIGHT, tucked against the machine number
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # CENTRED IN THE HALF, not right-aligned. Right alignment pools
            # every bit of slack on the LEFT of each column, which is what
            # left a dead gap after the axis letter and another between the
            # two columns while the far right sat hard against the edge. The
            # slack is real and unavoidable -- with six rows the number font
            # is limited by ROW HEIGHT, not by width, so it cannot grow to
            # fill the half -- but centred it splits evenly either side and
            # each column sits under its own banner.
            # The decimal point stays column-locked WITHIN a scale, which is
            # what it was always for: every linear row renders the same
            # character count and every rotary row renders the same count, so
            # each group still lines up with itself.
            mach = QLabel('0.00')
            mach.setTextFormat(Qt.RichText)
            mach.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            work = QLabel('0.00')
            work.setTextFormat(Qt.RichText)
            work.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            targ = QLabel('0.00')
            targ.setTextFormat(Qt.RichText)
            targ.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            # colour NOW, not only in the tick: before the first poll the
            # labels inherited the default palette and were black on black
            for _w in (lab, mach, work, targ):
                _w.setStyleSheet('color: %s; background: transparent;'
                                 % WHITE)
            row.addWidget(lab, 0)
            # work first: same order as the headers above and as PB
            row.addWidget(work, 5)
            row.addWidget(targ, 5)
            row.addWidget(mach, 5)
            # every axis row shares the remaining height equally
            root.addWidget(holder, 1)
            # the holder is kept so a row can be HIDDEN when its axis
            # stops being commandable -- rebuilding a live layout to
            # drop one line is all risk and no benefit.
            self.rows.append((lab, mach, work, targ))
            self._holders[letter] = holder

        # flash state: frames left, and the last flash-in value seen
        self._flash_left = 0
        self._flash_seen = None
        self.t = QTimer(self)
        self.t.timeout.connect(self.tick)
        self.t.start(80)
        self._windowed = windowed

    # ---- HAL: our own pins, netted to the pendant's signals -------------
    def _hal_setup(self):
        try:
            import hal
            self._hal = hal.component('dro2')
            self._hal.newpin('axis-in', hal.HAL_S32, hal.HAL_IN)
            self._hal.newpin('inc-index-in', hal.HAL_S32, hal.HAL_IN)
            # TOOLSETTER CONTACT (operator 2026-08-11: "i want that white
            # speed indicator to be red if the tool setter pin detects
            # continuity to ground. it lets me use tool probe from far").
            # sig-tool-probe is 7i84.0.0.input-28 (TB2-13, *54, via R10),
            # the same signal that feeds motion.probe-input.
            self._hal.newpin('probe-in', hal.HAL_BIT, hal.HAL_IN)
            # COUNTDOWN FLASH (operator 2026-08-14: "have the code make the
            # SDRO flash white 3 times right before the steppers are asked
            # to move, that way i know what to expect"). B is open loop:
            # nothing on this machine can tell a turning motor from a
            # stalled one, so the ONLY instrument is the operator's eyes and
            # they have to be looking at the right moment. Any change to
            # this number -- not a particular value -- fires the flash, so a
            # caller just increments it.
            self._hal.newpin('flash-in', hal.HAL_S32, hal.HAL_IN)
            # PER-AXIS MPG LOCK -- the PENDANT's lock (triple tap), NOT the GUI
            # lock. GUI-locked axes are unselectable and never reach the
            # wheel at all. (operator 2026-08-11: "color it red on the
            # standalone dro when it is locked"). A locked axis is still
            # selectable -- it just does not jog until it is triple-tapped
            # unlocked -- so the screen has to say which ones are dead.
            for _a in ('x', 'y', 'z', 'a', ROT):
                self._hal.newpin('lock-%s-in' % _a, hal.HAL_BIT, hal.HAL_IN)
                # ...and the GUI lock, which is a DIFFERENT thing: that axis
                # is not selectable at all, so the WHOLE ROW goes red
                # (operator 2026-08-11). MPG lock reds the letter only.
                self._hal.newpin('gui-%s-in' % _a, hal.HAL_BIT, hal.HAL_IN)
            self._hal.ready()
            for sig, pin in (('sig-mpg-axis', 'dro2.axis-in'),
                             ('sig-mpg-inc-index', 'dro2.inc-index-in'),
                             ('sig-tool-probe', 'dro2.probe-in'),
                             ('sig-mpg-lock-x', 'dro2.lock-x-in'),
                             ('sig-mpg-lock-y', 'dro2.lock-y-in'),
                             ('sig-mpg-lock-z', 'dro2.lock-z-in'),
                             ('sig-mpg-lock-a', 'dro2.lock-a-in'),
                             ('sig-mpg-lock-c', 'dro2.lock-%s-in' % ROT),
                             ('sig-lock-x', 'dro2.gui-x-in'),
                             ('sig-lock-y', 'dro2.gui-y-in'),
                             ('sig-lock-z', 'dro2.gui-z-in'),
                             ('sig-lock-a', 'dro2.gui-a-in'),
                             ('sig-lock-c', 'dro2.gui-%s-in' % ROT)):
                subprocess.run(['halcmd', 'net', sig, pin],
                               capture_output=True, timeout=5)
        except Exception as e:
            sys.stderr.write('dro2: HAL unavailable (%s) -- numbers only\n'
                             % e)
            self._hal = None

    def _recheck_axes(self):
        """Rebuild if the commandable axis set has changed."""
        try:
            now = ini_axes()
        except Exception:
            return
        if now == self.axes:
            return
        old = self.axes
        self.axes = now
        for letter, holder in self._holders.items():
            holder.setVisible(letter in now)
        print('dro2: commandable axes %s -> %s' % (old, now), flush=True)

    def _sel_letter(self):
        """The axis letter the pendant has selected, or '' if unknown.

        The pendant cycles x y z a <rotary>; the rotary slot is whichever
        axis HAL says it drives (ROT), so this follows a mode change with
        nothing hardcoded.
        """
        pend = ['X', 'Y', 'Z', 'A', ROT.upper()]
        i = getattr(self, 'sel', 0)
        return pend[i] if 0 <= i < len(pend) else ''

    def _hal_read(self):
        if self._hal is None:
            return
        try:
            # BOTH values come from the machine's single publisher (the
            # pendant, same signals PB reads). No local interpretation --
            # the DRO never keeps its own record of speed or axis.
            self.sel = int(self._hal['axis-in'])
            self.slot = int(self._hal['inc-index-in'])
            self.probe = bool(self._hal['probe-in'])
            self.locks = {a: bool(self._hal['lock-%s-in' % a])
                          for a in ('x', 'y', 'z', 'a', ROT)}
            self.guilocks = {a: bool(self._hal['gui-%s-in' % a])
                             for a in ('x', 'y', 'z', 'a', ROT)}
        except Exception:
            pass

    # ---- fonts: numbers fill ~80% of the screen ------------------------
    def _resize_fonts(self):
        rows = max(1, len(self.rows))
        hdr_px = max(18, int(self.height() * 0.030))
        hf = QFont('DejaVu Sans')
        hf.setPixelSize(hdr_px)
        hf.setBold(True)
        for _h in self.hdr_labels:
            _h.setFont(hf)
        self.hdr.setFixedHeight(int(hdr_px * 1.5))
        # rows squeezed by the header height (operator: make space)
        avail = self.height() - STRIP_H - self.hdr.height()
        # 0.92, not 0.80. The font is sized by whichever of height or width
        # binds first, and at 0.80 HEIGHT always won on this screen -- the
        # digits ended up ~160 px narrower than their half, which is the
        # empty space the operator kept pointing at ("both columns take up
        # the space"). Letting the glyphs use more of the row lets WIDTH
        # become the binding constraint, which is the one that actually
        # fills the column. The width guard below is untouched, so the
        # 12 ft X reading still cannot overflow.
        by_height = (avail / rows) * 0.86
        # WIDTH BUDGET: NUM_W monospace glyphs per column, across however many
        # value columns the row was built with, plus the letter column. X on this machine reaches -4042.72 mm, so the
        # width is the binding constraint, not the height.
        # MEASURE THE WIDTH, DO NOT GUESS IT. `NUM_W * 0.62` was a guess at
        # how wide the rendered cell would be, and it is not what gets drawn:
        # the cell is a sign at 0.84x, the digits at 1x, and the unit at
        # 0.30x. Guessing low wastes the column; guessing high OVERFLOWS it,
        # which is what raising the height factor exposed -- the mm ran off
        # the right edge and the two columns touched.
        # Width is linear in the pixel size, so measure the real string once
        # at a reference size and scale. The widest thing this ever draws is
        # a negative linear reading with its unit.
        # COUNT THE COLUMNS, DO NOT HARDCODE THEM. This divided by a literal
        # 2 and stayed that way when the TARGET column was added on
        # 2026-08-16, so every cell was sized for half the width while only a
        # third was available and MCS was pushed clean off the right edge of
        # the screen. Each row is (letter, mach, work, targ), so the value
        # columns are len(row) - 1 and adding a fourth needs no edit here.
        ncol = max(1, len(self.rows[0]) - 1) if self.rows else 2
        per_col = (self.width() - 90) / float(ncol)
        REF = 100
        _digits = '0' * NUM_INT + '.00'
        _w_ref = (QFontMetrics(QFont('DejaVu Sans Mono', REF)
                               ).horizontalAdvance(_digits)
                  + QFontMetrics(QFont('DejaVu Sans Mono', int(REF * 0.84))
                                 ).horizontalAdvance('-')
                  + QFontMetrics(QFont('DejaVu Sans Mono', int(REF * 0.30))
                                 ).horizontalAdvance('mm'))
        # 0.94: leave a hair of breathing room so a rounding difference
        # between measurement and render cannot clip the last glyph.
        by_width = REF * (per_col * 0.94) / max(1.0, _w_ref)
        num_px = int(max(40, min(by_height, by_width)))
        # letters BOLD and +5 (operator 2026-08-06)
        lab_px = max(24, int(num_px * 0.42)) + 5
        nf = QFont('DejaVu Sans Mono')
        nf.setPixelSize(num_px)
        nf.setBold(True)
        lf = QFont('DejaVu Sans')
        lf.setPixelSize(lab_px)
        lf.setBold(True)
        # FIXED LETTER COLUMN: 'Y' is narrower than 'X', so a natural-width
        # label handed that row 3 px more number space and slid its decimal
        # point out of column. One width for every letter (2026-08-05).
        lm = QFontMetrics(lf)
        lab_w = max([lm.horizontalAdvance(a) for a in self.axes] or [lab_px])
        self.hdr_pad.setFixedWidth(lab_w)   # headers align with the columns
        for _h in self.hdr_labels:
            _h.setContentsMargins(0, 0, 0, 0)
        for lab, mach, work, targ in self.rows:
            lab.setFont(lf)
            lab.setFixedWidth(lab_w)
            mach.setFont(nf)
            work.setFont(nf)
            targ.setFont(nf)
        self._num_px = num_px

    def resizeEvent(self, ev):
        self._resize_fonts()
        super().resizeEvent(ev)

    FLASH_TICKS_PER_HALF = 2      # 2 x 80 ms = 160 ms lit, 160 ms dark
    FLASH_COUNT = 3               # three white flashes

    def _flash_step(self):
        """Run the countdown flash. Called first thing every tick.

        The whole window goes white and back, three times, in about a
        second. Every child widget already paints on a transparent
        background, so repainting the window is enough and nothing has to
        know about the individual rows.
        """
        h = getattr(self, '_hal', None)
        if h is not None:
            try:
                v = h['flash-in']
                if self._flash_seen is None:
                    self._flash_seen = v          # do not flash on startup
                elif v != self._flash_seen:
                    self._flash_seen = v
                    self._flash_left = self.FLASH_COUNT * 2 * self.FLASH_TICKS_PER_HALF
            except Exception:
                pass
        if self._flash_left > 0:
            self._flash_left -= 1
            half = self._flash_left // self.FLASH_TICKS_PER_HALF
            self.setStyleSheet('background: %s;'
                               % (WHITE if half % 2 else BLACK))
            if self._flash_left == 0:
                self.setStyleSheet('background: %s;' % BLACK)

    def tick(self):
        self._flash_step()
        n = getattr(self, '_beats', 0) + 1
        self._beats = n
        if n == 1 or n % 250 == 0:
            sys.stderr.write('dro2: tick %d alive\n' % n)
            sys.stderr.flush()
        self._hal_read()
        self.strip.set_slot(self.slot)
        self.strip.set_probe(self.probe)
        try:
            self.stat.poll()
        except Exception:
            return
        # UNITS FROM THE MACHINE: program_units 1=inch, 2=mm, 3=cm. It was
        # hardcoded mm, so an inch session would have shown mm numbers
        # labelled 'in' (operator 2026-08-05: "make sure it can accommodate
        # inches"). Positions are always in machine units, so inch display
        # divides the LINEAR axes only.
        try:
            self._mm = int(self.stat.program_units) != 1
        except Exception:
            self._mm = True
        conv = 1.0 if self._mm else (1.0 / 25.4)
        # header shows the ACTIVE work system, not a generic G5x
        # (operator 2026-08-06): g5x_index 1..9 -> G54..G59.3
        try:
            # this binding is 0-BASED: measured live, g5x_index reads 0
            # with G54 active (2026-08-06)
            g = int(self.stat.g5x_index)
            # stat.g5x_index is ONE-BASED: G54 is 1, G59.3 is 9. Indexing
            # the tuple with it directly read one system too far, so the
            # standalone DRO said G55 while PB said G54 on the same machine
            # (operator 2026-08-11).
            name = ('G54', 'G55', 'G56', 'G57', 'G58', 'G59', 'G59.1',
                    'G59.2', 'G59.3')[g - 1] if 1 <= g <= 9 else 'G5x'
            want = 'WCS ' + name
            if self.hdr_wcs.text() != want:
                self.hdr_wcs.setText(want)
        except Exception:
            pass
        idx = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3, 'B': 4, 'C': 5,
               'U': 6, 'V': 7, 'W': 8}
        # self.rows was built from _all_axes and is indexed by BUILD
        # position. Iterating self.axes here would slide every row up
        # by one the moment an axis is hidden -- B would be painted
        # into C's line. Walk the build order and skip what is hidden.
        for i, letter in enumerate(getattr(self, '_all_axes',
                                           self.axes)):
            if letter not in self.axes:
                continue
            j = idx.get(letter, i)
            try:
                m = self.stat.actual_position[j]
                off = (self.stat.g5x_offset[j] + self.stat.g92_offset[j]
                       + self.stat.tool_offset[j])
                w = m - off
                # TARGET = the COMMANDED position in the same work frame the
                # WCS column uses. stat.position is where motion is heading;
                # subtracting the identical offsets means WCS and TARGET read
                # directly against each other -- where it is, where it is going.
                t = self.stat.position[j] - off
            except Exception:
                m = w = 0.0
            if letter in 'XYZUVW':
                m, w = m * conv, w * conv
            # DECIMAL POINT IS COLUMN-LOCKED (operator 2026-08-05:
            # "deg has 3 digits left of decimal and 2 right; linear has
            # 4,2 in mm and 3,3 in inch; in all cases align the dot").
            # THE DOT LANDS IN ONE COLUMN IFF EVERY ROW IS THE SAME TOTAL
            # WIDTH. That used to be true for a weaker reason: the rows were
            # RIGHT-aligned, so only everything to the RIGHT of the dot had
            # to match and the integer digits could differ freely, growing
            # leftwards. Centring the cells to spread them across the half
            # killed that -- a rotary row is one integer digit narrower than
            # a linear one, so centred it sits half a glyph over and its
            # decimal misses the column.
            # So pad the integer side as well and make every row identical
            # in width. Then the dot is in the same place whether the cell
            # is centred or right-aligned, and it cannot drift again the
            # next time the alignment is touched.
            lin = letter in 'XYZUVW'
            dec = 3 if (lin and not self._mm) else 2
            int_w = 4 if (lin and self._mm) else 3
            # widest decimal count on screen in THIS unit mode
            max_dec = 2 if self._mm else 3
            # NBSP, not figure space: Qt collapses a run of ordinary
            # spaces, and in inch mode the rotary pad swallowed the
            # separator, shifting deg rows one cell right. NBSP is never
            # collapsed and is digit-wide in this monospace face.
            frac_pad = '\u00a0' * (max_dec - dec)
            unit = ('mm' if self._mm else 'in') if lin else 'deg'
            unit = unit.ljust(3, '\u00a0')           # 'mm.' == 'deg' == 'in.'

            # widest integer field on screen in THIS unit mode: linear mm
            # uses 4, everything else 3
            int_pad = 4 if self._mm else 3

            def _field(v):
                sign = '-' if v < 0 else '+'
                body = '%.*f' % (dec, abs(v))
                ip, _, fp = body.partition('.')
                # zero-fill to this row's own width, then NBSP-pad out to the
                # widest row's width so all rows measure the same
                ips = ip.rjust(int_w, '0').rjust(int_pad, '\u00a0')
                return '%s%s.%s%s' % (sign, ips, fp, frac_pad)
            txt_m, txt_w, txt_t = _field(m), _field(w), _field(t)
            lab, mach, work, targ = self.rows[i]
            # THE LETTER carries the lock, the NUMBERS carry the
            # selection (operator 2026-08-11: "lets just apply the red lock
            # to the letter only. that way, what is highlighted is always
            # clear"). Red on the whole row hid which axis the wheel was on.
            # `letter`, NOT self.axes[i]. i indexes the BUILD order
            # (_all_axes) so it lines up with self.rows; self.axes is
            # the filtered, visible set. Once the parked C was hidden
            # the two diverged and self.axes[5] raised IndexError on
            # the B row -- the paint threw, so B froze on whatever
            # colour it last had and stopped following its lock
            # (operator 2026-08-11: "when i unlock B in GUI, it stays
            # locked ... on the standalone DRO").
            _ax = letter.lower()
            if self.guilocks.get(_ax):
                # GUI LOCK: the axis cannot even be SELECTED -- the whole
                # row is red so that reads at a glance.
                colour = lab_colour = LOCK_RED
            else:
                # TWO DIFFERENT NUMBERINGS. pendant.sel-axis indexes the
                # PENDANT's list -- x y z a <rotary>, five entries -- while
                # i here indexes the DRO's rows, which come from
                # [TRAJ]COORDINATES: X Y Z A C B, six. They agree for the
                # first four and diverge after: the pendant selecting the
                # rotary sends 4, and row 4 is C, not B. Under -xyzab the
                # C row is also HIDDEN, so the highlight vanished entirely
                # and the wheel looked like it had skipped straight back to
                # X (operator 2026-08-11: "it hits Z and goes back to X").
                # Compare LETTERS, never indices.
                colour = GREEN if letter == self._sel_letter() else WHITE
                # MPG LOCK: selectable, just will not jog -- letter only,
                # so the green selection stays readable.
                lab_colour = LOCK_RED if self.locks.get(_ax) else colour
            # unit in a smaller font, after the number
            small = int(getattr(self, '_num_px', 100) * 0.30)
            def _cell(t):
                # SMALL SIGN (operator 2026-08-05): it carries one bit and
                # was eating a whole digit cell at full height
                sign, rest = t[0], t[1:]
                # DOUBLE SIZE, VERTICALLY CENTRED (operator 2026-08-11:
                # "lets have the + and - signs be centered instead of at
                # the bottom of the numbers, and double in size"). A small
                # inline span sits on the text BASELINE, which put the sign
                # down at the foot of the digits; vertical-align:middle
                # lifts it to the middle of the number's own line box.
                sgn_px = max(48, int(getattr(self, '_num_px', 100) * 0.84))
                return ('<span style="font-size:%dpx;'
                        'vertical-align:middle;">%s</span>%s'
                        '<span style="font-size:%dpx;">\u00a0%s</span>'
                        % (sgn_px, sign, rest.replace(' ', '\u00a0'),
                           small, unit))
            mach.setText(_cell(txt_m))
            work.setText(_cell(txt_w))
            targ.setText(_cell(txt_t))
            lab.setStyleSheet('color: %s; background: transparent;'
                              % lab_colour)
            for wdg in (mach, work, targ):
                wdg.setStyleSheet('color: %s; background: transparent;'
                                  % colour)


def main():
    args = sys.argv[1:]
    windowed = '--window' in args
    screen_idx = None
    if '--screen' in args:
        try:
            screen_idx = int(args[args.index('--screen') + 1])
        except Exception:
            screen_idx = None

    app = QApplication(sys.argv)
    w = Dro2(windowed=windowed)
    # SIGTERM MUST KILL US (2026-08-05): hal.component() installs its own
    # SIGTERM handler that only sets a flag, so a plain `kill` was ignored
    # and run5.sh's pre-launch pkill would have left a stale DRO holding
    # the 'dro2' HAL name -- the next session then falls back to
    # numbers-only. Our handler runs because the 80 ms tick keeps giving
    # Python a chance to service signals inside the Qt loop.
    def _bye(signum, _frame):
        sys.stderr.write('dro2: signal %d -- exiting\n' % signum)
        sys.stderr.flush()
        app.quit()
    for _s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(_s, _bye)
        except Exception:
            pass
    screens = app.screens()
    if screen_idx is None:
        screen_idx = 1 if len(screens) > 1 else 0
    screen_idx = min(screen_idx, len(screens) - 1)
    geo = screens[screen_idx].geometry()
    if windowed:
        w.resize(900, 600)
        w.move(geo.left() + 60, geo.top() + 60)
        w.show()
    else:
        w.setGeometry(geo)
        w.setWindowFlag(Qt.FramelessWindowHint, True)
        w.showFullScreen()
        w.windowHandle().setScreen(screens[screen_idx])
        w.setGeometry(geo)
    sys.stderr.write('dro2: screen %d %dx%d at %d,%d  axes %s\n'
                     % (screen_idx, geo.width(), geo.height(),
                        geo.left(), geo.top(), ''.join(w.axes)))
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
