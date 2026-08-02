"""HOLES -- main user tab (drill a table of hole positions with G81).

- 30-row X/Y table, cells editable. Blank cell = do nothing; a row runs
  only when BOTH X and Y are non-blank floats, otherwise the row is
  skipped entirely.
- POPULATE X / POPULATE Y: per-column dialog with START, N and a third
  field the operator toggles between INCREMENT and END (button shows the
  active mode). Fills rows 0..N-1 of that column only, %.3f.
- Hovering a cell shows a small floating X button over it; clicking it
  blanks that cell.
- RETRACT Z / DEPTH Z / FEED under the table, RUN HOLES builds ONE
  deterministic MDI sequence: G0 to the first hole, then per hole
  G0 + G81 R.. Z.. F.., then G80 and G0 back to retract Z. Each line is
  issued with wait_complete() between, exactly like the MOVE panel:
  MDI mode -> command(s) -> wait -> back to MANUAL (+ teleop when homed).
  Busy-guard refuses when the machine is off, a program is running or a
  joint is homing (linuxcnc.stat only). No HAL access in this module.
- BORE mode: BORE dia blank = plain G81 drill. BORE dia set -> TOOL dia
  REQUIRED (error otherwise) and STEP = mm per depth pass; each hole is
  orbited on r=(bore-tool)/2 per pass (plunge, feed +X to r, full G3
  circle, back to center -- the proven bore_14_pairs.ngc pattern).
"""
import os

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton,
                               QTableWidgetItem, QToolButton, QVBoxLayout,
                               QWidget)

from qtpyvcp.utilities import logger
from qtpyvcp.utilities.runtime_ui_loader import load_ui as load_runtime_ui

LOG = logger.getLogger(__name__)


class _PopulateDialog(QDialog):
    """START / N / (INCREMENT|END) entry for one table column."""

    def __init__(self, col_name, parent=None):
        super(_PopulateDialog, self).__init__(parent)
        self.setWindowTitle('POPULATE ' + col_name)
        grid = QGridLayout()
        grid.addWidget(QLabel('START'), 0, 0)
        self.in_start = QLineEdit('0')
        grid.addWidget(self.in_start, 0, 1)
        grid.addWidget(QLabel('N'), 1, 0)
        self.in_n = QLineEdit('1')
        grid.addWidget(self.in_n, 1, 1)
        # The toggle button IS the third field's label (ABS/REL pattern):
        # unchecked = INCREMENT, checked = END.
        self.btn_mode = QPushButton('INCREMENT')
        self.btn_mode.setCheckable(True)
        self.btn_mode.toggled.connect(
            lambda on: self.btn_mode.setText('END' if on else 'INCREMENT'))
        grid.addWidget(self.btn_mode, 2, 0)
        self.in_val = QLineEdit('0')
        grid.addWidget(self.in_val, 2, 1)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addWidget(box)

    def values(self):
        """(start, n, end_mode, third) or None when a field won't parse."""
        try:
            start = float(self.in_start.text())
            n = int(self.in_n.text())
            third = float(self.in_val.text())
        except ValueError:
            return None
        if n < 1:
            return None
        return start, n, self.btn_mode.isChecked(), third


class UserTab(QWidget):
    ROWS = 30

    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = load_runtime_ui(ui_path, self)
        self.setObjectName('HOLES')   # tab label (main tab, NOT sidebar)

        self._w = lambda n: self.findChild(QWidget, n)
        self.tbl = self._w('tbl_holes')
        self.tbl.setRowCount(self.ROWS)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Hover-clear: one floating X ToolButton living on the table's
        # viewport; cellEntered moves it over the hovered cell, clicking it
        # blanks that cell, leaving the table hides it.
        self.tbl.setMouseTracking(True)
        self.tbl.viewport().setMouseTracking(True)
        self._xcell = None
        b = QToolButton(self.tbl.viewport())
        b.setText('✕')
        b.setFixedSize(18, 18)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet('QToolButton { border: none; background: transparent;'
                        ' color: rgb(220, 80, 80); font: bold 11pt; }')
        b.hide()
        b.clicked.connect(self._x_clicked)
        b.installEventFilter(self)
        self._xbtn = b
        self.tbl.cellEntered.connect(self._cell_entered)
        self.tbl.viewport().installEventFilter(self)
        self.tbl.verticalScrollBar().valueChanged.connect(
            lambda _v: self._xbtn.hide())

        for name, fn in (('btn_populate_x', lambda: self._populate(0)),
                         ('btn_populate_y', lambda: self._populate(1)),
                         ('btn_clear', self._clear),
                         ('btn_run', self._run)):
            w = self._w(name)
            if w is not None:
                w.clicked.connect(lambda _=False, f=fn: f())

    # ---- hover-clear ----------------------------------------------------

    def _cell_entered(self, row, col):
        r = self.tbl.visualRect(self.tbl.model().index(row, col))
        if not r.isValid():
            self._xbtn.hide()
            return
        self._xcell = (row, col)
        b = self._xbtn
        b.move(r.right() - b.width() - 2,
               r.top() + (r.height() - b.height()) // 2)
        b.raise_()
        b.show()

    def _x_clicked(self):
        if self._xcell is not None:
            row, col = self._xcell
            it = self.tbl.item(row, col)
            if it is not None:
                it.setText('')
        self._xbtn.hide()

    def eventFilter(self, obj, event):
        # Entering the X button fires Leave on the viewport (child steals the
        # mouse) -- keep the button while it is the thing under the cursor.
        if event.type() == QEvent.Leave:
            if obj is self.tbl.viewport() and not self._xbtn.underMouse():
                self._xbtn.hide()
            elif obj is self._xbtn and not self.tbl.viewport().underMouse():
                self._xbtn.hide()
        return super(UserTab, self).eventFilter(obj, event)

    # ---- table fill / clear ---------------------------------------------

    def _set_cell(self, row, col, text):
        it = self.tbl.item(row, col)
        if it is None:
            it = QTableWidgetItem()
            self.tbl.setItem(row, col, it)
        it.setText(text)

    def _populate(self, col):
        dlg = _PopulateDialog('X' if col == 0 else 'Y', self)
        if dlg.exec() != QDialog.Accepted:
            return
        vals = dlg.values()
        if vals is None:
            LOG.error('POPULATE: bad START/N/value')
            return
        start, n, end_mode, third = vals
        n = min(n, self.tbl.rowCount())
        for i in range(n):
            if end_mode:
                v = start if n == 1 else start + i * (third - start) / (n - 1)
            else:
                v = start + i * third
            self._set_cell(i, col, '%.3f' % v)

    def _clear(self):
        for r in range(self.tbl.rowCount()):
            for c in range(2):
                it = self.tbl.item(r, c)
                if it is not None:
                    it.setText('')

    # ---- run ------------------------------------------------------------

    def _holes(self):
        holes = []
        for r in range(self.tbl.rowCount()):
            vals = []
            for c in (0, 1):
                it = self.tbl.item(r, c)
                txt = it.text().strip() if it is not None else ''
                if not txt:
                    break
                try:
                    vals.append(float(txt))
                except ValueError:
                    break
            if len(vals) == 2:
                holes.append((vals[0], vals[1]))
        return holes

    def _run(self):
        holes = self._holes()
        if not holes:
            LOG.error('HOLES: no complete rows (a hole needs BOTH X and Y)')
            return
        try:
            retract = float(self._w('in_retract').text())
            depth = float(self._w('in_depth').text())
            feed = float(self._w('in_feed').text())
            if feed <= 0:
                raise ValueError(feed)
        except Exception:
            LOG.error('HOLES: bad RETRACT/DEPTH/FEED value')
            return
        # BORE mode (operator 2026-08-01): BORE dia blank = plain G81 drill.
        # BORE dia given -> TOOL dia is REQUIRED; orbit the tool center on
        # r = (bore - tool)/2 per depth STEP, the proven bore_14_pairs.ngc
        # pattern (plunge, feed +X to r, one full G3 circle, back to center).
        dia_txt = (self._w('in_dia').text().strip()
                   if self._w('in_dia') is not None else '')
        bore = None
        if dia_txt:
            try:
                bore = float(dia_txt)
                tool = float(self._w('in_tooldia').text())
                step = float(self._w('in_step').text())
                if bore <= 0 or tool <= 0 or step <= 0:
                    raise ValueError
            except Exception:
                import linuxcnc
                linuxcnc.command().error_msg(
                    'BORE needs a valid TOOL diameter and STEP: bore mode '
                    'was requested (BORE dia set) but they did not parse.')
                return
            if tool >= bore:
                import linuxcnc
                linuxcnc.command().error_msg(
                    'BORE %.3f impossible with TOOL %.3f: the tool must be '
                    'SMALLER than the bore.' % (bore, tool))
                return
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if not all(s.homed[:6]):
                c.error_msg('HOLES needs a HOMED machine: with gantry (non-identity) kinematics, LinuxCNC refuses MDI unhomed (motion command.c:584). REF ALL first, or launch with run5.sh resume.')
                return
            if (s.task_state != linuxcnc.STATE_ON
                    or s.interp_state != linuxcnc.INTERP_IDLE
                    or any(s.joint[j]['homing'] for j in range(6))):
                LOG.error('HOLES ignored: machine off, program running '
                          'or homing')
                return
            lines = ['G90 G0 X%.3f Y%.3f' % holes[0]]
            if bore is None:
                for x, y in holes:
                    lines.append('G90 G0 X%.3f Y%.3f' % (x, y))
                    lines.append('G81 R%.3f Z%.3f F%.1f' % (retract, depth, feed))
                lines.append('G80')
            else:
                r = (bore - tool) / 2.0
                engage = min(retract, 1.0)   # rapid to here, feed from here
                for x, y in holes:
                    lines.append('G90 G0 X%.3f Y%.3f' % (x, y))
                    lines.append('G0 Z%.3f' % retract)
                    lines.append('G0 Z%.3f' % engage)
                    zcut = 0.0
                    while zcut > depth + 1e-9:
                        zcut = max(zcut - step, depth)
                        lines.append('G1 Z%.3f F%.1f' % (zcut, feed))
                        lines.append('G1 X%.3f' % (x + r))
                        lines.append('G3 X%.3f Y%.3f I%.4f J0' % (x + r, y, -r))
                        lines.append('G1 X%.3f' % x)
                    lines.append('G0 Z%.3f' % retract)
            lines.append('G0 Z%.3f' % retract)
            LOG.info('HOLES: starting %d hole(s)', len(holes))
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            for line in lines:
                c.mdi(line)
                # a slow G81 easily outlives the 5 s default timeout
                c.wait_complete(120.0)
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            s.poll()
            if all(s.homed[:6]):
                c.teleop_enable(1)
            LOG.info('HOLES: completed %d hole(s)', len(holes))
        except Exception as e:
            LOG.error('HOLES failed: %s', e)
