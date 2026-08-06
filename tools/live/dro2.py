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
WHITE = '#f0f0f0'
BLACK = '#000000'
N_SLOTS = 5                # jog increment ladder length (ned_pendant)
STRIP_H = 46               # top indicator strip height, px
NUM_W = 9                  # fixed number field: '-4042.72 ' fits (12 ft X)
NUM_INT = 4                # linear integer digits: 0000.00 .. -4042.72 (12 ft X)
NUM_INT_ROT = 3            # degrees need only 000.00 (operator 2026-08-05)


def ini_axes():
    """Axis letters from the RUNNING ini, duplicates dropped (gantry)."""
    path = os.environ.get('INI_FILE_NAME', '')
    letters = []
    try:
        ini = linuxcnc.ini(path) if path else None
        coords = (ini.find('TRAJ', 'COORDINATES') if ini else None) or ''
        for c in coords.replace(' ', '').upper():
            if c.isalpha() and c not in letters:
                letters.append(c)
    except Exception:
        pass
    return letters or ['X', 'Y', 'Z', 'A', 'C']


class JogStrip(QWidget):
    """White block on black; ONLY its position changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slot = 2
        self.setFixedHeight(STRIP_H)
        self.setAutoFillBackground(False)

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
                   int(w) - 8, self.height() - 12, QColor(WHITE))
        p.end()


class Dro2(QWidget):

    def __init__(self, windowed=False):
        super().__init__()
        self.setWindowTitle('ned DRO')
        self.setStyleSheet('background: %s;' % BLACK)
        self.axes = ini_axes()
        self.stat = linuxcnc.stat()
        self.sel = 0
        self._mm = True
        self.slot = 2
        self._hal = None
        self._hal_setup()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.strip = JogStrip()
        root.addWidget(self.strip, 0)      # stretch 0: fixed strip

        # column headers (operator 2026-08-06: "i need to know WCS vs
        # MCS") -- MCS over the left/machine column, WCS G5x over the
        # right/work column, each centered on its column. Fixed height;
        # the axis rows give up the space.
        hdr = QWidget()
        hrow = QHBoxLayout(hdr)
        hrow.setContentsMargins(14, 0, 14, 0)
        hrow.setSpacing(10)
        self.hdr_pad = QLabel('')
        h_m = QLabel('MCS')
        h_w = QLabel('WCS')
        for _h in (h_m, h_w):
            _h.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            _h.setStyleSheet('color: %s; background: transparent;' % WHITE)
        hrow.addWidget(self.hdr_pad, 0)
        hrow.addWidget(h_m, 5)
        hrow.addWidget(h_w, 5)
        self.hdr = hdr
        self.hdr_labels = (h_m, h_w)
        self.hdr_wcs = h_w
        root.addWidget(hdr, 0)

        self.rows = []
        for letter in self.axes:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(14, 0, 14, 0)
            row.setSpacing(10)
            lab = QLabel(letter)
            # letters sit RIGHT, tucked against the machine number
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            mach = QLabel('0.00')
            mach.setTextFormat(Qt.RichText)
            mach.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            work = QLabel('0.00')
            work.setTextFormat(Qt.RichText)
            work.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # colour NOW, not only in the tick: before the first poll the
            # labels inherited the default palette and were black on black
            for _w in (lab, mach, work):
                _w.setStyleSheet('color: %s; background: transparent;'
                                 % WHITE)
            row.addWidget(lab, 0)
            row.addWidget(mach, 5)
            row.addWidget(work, 5)
            # every axis row shares the remaining height equally
            root.addWidget(holder, 1)
            self.rows.append((lab, mach, work))

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
            self._hal.ready()
            for sig, pin in (('sig-mpg-axis', 'dro2.axis-in'),
                             ('sig-mpg-inc-index', 'dro2.inc-index-in')):
                subprocess.run(['halcmd', 'net', sig, pin],
                               capture_output=True, timeout=5)
        except Exception as e:
            sys.stderr.write('dro2: HAL unavailable (%s) -- numbers only\n'
                             % e)
            self._hal = None

    def _hal_read(self):
        if self._hal is None:
            return
        try:
            # BOTH values come from the machine's single publisher (the
            # pendant, same signals PB reads). No local interpretation --
            # the DRO never keeps its own record of speed or axis.
            self.sel = int(self._hal['axis-in'])
            self.slot = int(self._hal['inc-index-in'])
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
        by_height = (avail / rows) * 0.80
        # WIDTH BUDGET: NUM_W monospace glyphs per column, two columns, plus
        # the letter column. X on this machine reaches -4042.72 mm, so the
        # width is the binding constraint, not the height.
        per_col = (self.width() - 90) / 2.0
        by_width = per_col / (NUM_W * 0.62)
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
        for lab, mach, work in self.rows:
            lab.setFont(lf)
            lab.setFixedWidth(lab_w)
            mach.setFont(nf)
            work.setFont(nf)
        self._num_px = num_px

    def resizeEvent(self, ev):
        self._resize_fonts()
        super().resizeEvent(ev)

    def tick(self):
        n = getattr(self, '_beats', 0) + 1
        self._beats = n
        if n == 1 or n % 250 == 0:
            sys.stderr.write('dro2: tick %d alive\n' % n)
            sys.stderr.flush()
        self._hal_read()
        self.strip.set_slot(self.slot)
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
            name = ('G54', 'G55', 'G56', 'G57', 'G58', 'G59', 'G59.1',
                    'G59.2', 'G59.3')[g] if 0 <= g <= 8 else 'G5x'
            want = 'WCS ' + name
            if self.hdr_wcs.text() != want:
                self.hdr_wcs.setText(want)
        except Exception:
            pass
        idx = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3, 'B': 4, 'C': 5,
               'U': 6, 'V': 7, 'W': 8}
        for i, letter in enumerate(self.axes):
            j = idx.get(letter, i)
            try:
                m = self.stat.actual_position[j]
                w = (m - self.stat.g5x_offset[j] - self.stat.g92_offset[j]
                     - self.stat.tool_offset[j])
            except Exception:
                m = w = 0.0
            if letter in 'XYZUVW':
                m, w = m * conv, w * conv
            # DECIMAL POINT IS COLUMN-LOCKED (operator 2026-08-05:
            # "deg has 3 digits left of decimal and 2 right; linear has
            # 4,2 in mm and 3,3 in inch; in all cases align the dot").
            # Rows are RIGHT-aligned in a monospace face, so the dot lands
            # in one column iff everything to its RIGHT is the same width
            # on every row: same decimal count, same unit width. Integer
            # digits differ freely -- they grow leftwards.
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

            def _field(v):
                sign = '-' if v < 0 else '+'
                body = '%.*f' % (dec, abs(v))
                ip, _, fp = body.partition('.')
                return '%s%s.%s%s' % (sign, ip.rjust(int_w, '0'), fp,
                                      frac_pad)
            txt_m, txt_w = _field(m), _field(w)
            lab, mach, work = self.rows[i]
            colour = GREEN if i == self.sel else WHITE
            # unit in a smaller font, after the number
            small = int(getattr(self, '_num_px', 100) * 0.30)
            def _cell(t):
                # SMALL SIGN (operator 2026-08-05): it carries one bit and
                # was eating a whole digit cell at full height
                sign, rest = t[0], t[1:]
                # sign matches the AXIS LETTER size (operator 2026-08-05)
                sgn_px = max(24, int(getattr(self, '_num_px', 100) * 0.42))
                return ('<span style="font-size:%dpx;">%s</span>%s'
                        '<span style="font-size:%dpx;">\u00a0%s</span>'
                        % (sgn_px, sign, rest.replace(' ', '\u00a0'),
                           small, unit))
            mach.setText(_cell(txt_m))
            work.setText(_cell(txt_w))
            for wdg in (lab, mach, work):
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
