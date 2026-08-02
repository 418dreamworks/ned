"""MOVE -- sidebar user tab (replaces the useless JOG page; the MPG owns
axis jogging). Typed absolute/relative moves on X Y Z A C at a panel-local
speed, plus preset moves.

- ABS/REL toggle button (shows the active mode).
- Blank axis field = that axis does not move.
- F field: feed for THIS panel's moves only (mm/min; note F is modal in
  g-code, so the next MDI/program line without its own F inherits it --
  standard LinuxCNC behavior).
- Presets: ALL->0, XY->0, AC->0 (absolute, work coords), Z +6 (relative).

Moves are FIRE-AND-FORGET: issue the MDI and return. Waiting here is wrong
twice over -- wait_complete() gives up after ~5 s regardless, and a mode
switch ABORTS in-flight motion, so wait-then-MANUAL killed every move longer
than a few seconds partway. ned_brain restores MANUAL + teleop once the
interpreter is idle AND motion is in position. No HAL access in this module.
"""
import os

from PySide6.QtWidgets import QWidget

from qtpyvcp.utilities import logger
from qtpyvcp.utilities.runtime_ui_loader import load_ui as load_runtime_ui

LOG = logger.getLogger(__name__)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = load_runtime_ui(ui_path, self)
        self.setObjectName('MOVE')
        # Loaded as a SIDEBAR user tab (keeps us off the main tab row), then
        # MOVED INTO THE JOG PAGE: the operator wants this to live under the
        # JOG selector ("its just a very natural place for it"). Runtime
        # reparent = accepted core-touch; redo recipe if PB renames things:
        # sb_page_1 (the JOG page) has a QVBoxLayout holding only jogDisplay
        # (which ned_controls hides) -- addWidget(self) there, and hide
        # user_sb_tab (the USER selector we vacated). Deferred one shot so it
        # runs AFTER the loader's own setParent(sb_page_4).
        self.setProperty('sidebar', True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._move_into_jog_page)

    def _move_into_jog_page(self):
        try:
            win = self.window()
            page = win.findChild(QWidget, 'sb_page_1') if win else None
            if page is not None and page.layout() is not None:
                page.layout().addWidget(self)
                self.setVisible(True)
                usr = win.findChild(QWidget, 'user_sb_tab')
                if usr is not None:
                    usr.hide()
                LOG.info('MOVE panel installed into the JOG page')
            else:
                LOG.error('MOVE: JOG page (sb_page_1) not found -- staying in USER slot')
        except Exception as e:
            LOG.error('MOVE reparent failed: %s', e)

        self._btn = lambda n: self.findChild(QWidget, n)
        b = self._btn('btn_mode')
        if b is not None:
            b.toggled.connect(lambda on: b.setText('RELATIVE' if on else 'ABSOLUTE'))
        g = self._btn('btn_go')
        if g is not None:
            g.clicked.connect(self._go)
        for name, mode, words in (
                ('btn_all0', 'abs', 'X0 Y0 Z0 A0 C0'),
                ('btn_xy0', 'abs', 'X0 Y0'),
                ('btn_ac0', 'abs', 'A0 C0'),
                ('btn_zp6', 'rel', 'Z6')):
            w = self._btn(name)
            if w is not None:
                w.clicked.connect(lambda _=False, m=mode, s=words: self._move(m, s))

    def _feed(self):
        try:
            f = float(self._btn('in_f').text())
            return f if f > 0 else None
        except Exception:
            return None

    def _go(self):
        words = []
        for ax in 'xyzac':
            w = self._btn('in_' + ax)
            txt = (w.text().strip() if w is not None else '')
            if not txt:
                continue
            try:
                words.append('{}{:.4f}'.format(ax.upper(), float(txt)))
            except ValueError:
                LOG.error('MOVE: bad %s value %r', ax.upper(), txt)
                return
        if not words:
            return
        b = self._btn('btn_mode')
        rel = bool(b is not None and b.isChecked())
        self._move('rel' if rel else 'abs', ' '.join(words))

    AXIS_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'c': 5}

    def _move(self, mode, words):
        f = self._feed()
        if f is None:
            LOG.error('MOVE: bad feed')
            return
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON or \
               s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos:
                LOG.error('MOVE ignored: machine off or something is executing')
                return
            if not all(s.homed[:6]):
                c.error_msg('MOVE needs a HOMED machine: with gantry (non-identity) kinematics, LinuxCNC refuses MDI unhomed (motion command.c:584). REF ALL first, or launch with run5.sh resume.')
                return
            if mode == 'rel':
                # One absolute G90 line (current work position + delta): no
                # G91 left modal if the move is aborted partway.
                out = []
                for w in words.split():
                    i = self.AXIS_IDX[w[0].lower()]
                    cur = (s.actual_position[i] - s.g5x_offset[i]
                           - s.g92_offset[i] - s.tool_offset[i])
                    out.append('{}{:.4f}'.format(w[0], cur + float(w[1:])))
                words = ' '.join(out)
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            # Fire and forget -- no waiting, no mode flip here: wait_complete
            # returns after ~5 s regardless, and a mode switch ABORTS in-flight
            # motion (killed every long move partway). ned_brain hands back
            # MANUAL + teleop once motion truly completes.
            c.mdi('G90 G1 {} F{:.1f}'.format(words, f))
            LOG.info('MOVE %s: %s F%.1f (brain restores MANUAL when done)',
                     mode, words, f)
        except Exception as e:
            LOG.error('MOVE failed: %s', e)
