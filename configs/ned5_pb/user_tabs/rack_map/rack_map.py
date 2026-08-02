"""rack map -- per-pocket rack table user tab (Probe Basic user tab).

15-row table over the PER-POCKET rack params (staging/rack_map ngc rework):
  #[4000+N]    tool assigned to pocket/fork N (existing rackatc/m13 contract)
  #[4100+N*4]  seat X (machine)     } written by o<rack_teach>, read by the
  #[4101+N*4]  seat Y (machine)     } per-pocket m21/m22
  #[4102+N*4]  clearance coordinate (entry-axis scalar)
  #[4103+N*4]  flags = entry_axis(0=X,1=Y) + 2*seat_taught + 4*clear_taught
  #3991        tool the spindle holds (persistent, toolchange.ngc contract)

FIXED HOMES: toolchange.ngc already enforces tool N -> fork N on every
put-away (aborts on a non-empty or foreign fork) -- this tab NEVER bypasses
that; assigning tool != pocket is allowed (physical reality after a
hand-load) but warned LOUDLY, and duplicate tool numbers are REFUSED.

READS are var-file only: the tab polls [RS274NGC]PARAMETER_FILE (mtime-
gated). Numbered params are not readable over NML, and hal.get_value() is
BANNED in GUI code (ned_controls.py header, 2026-07-31 UI-thread mutex
freeze). The interpreter saves the var file on program end / abort / exit,
so labels can LAG a teach; o<rack_teach>'s PRINT line is the immediate
confirmation. WRITES use the house MDI pattern (guard -> MODE_MDI ->
CONFIRM task_mode by POLLING -> fire-and-forget mdi(); never
wait_complete() around task, ned_controls.py _jog_issue).

Zero HAL pins here. UserTab pattern modeled on ned_controls.py.
"""
import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from qtpyvcp.utilities import logger
from qtpyvcp.utilities.runtime_ui_loader import load_ui as load_runtime_ui

LOG = logger.getLogger(__name__)

N_POCKETS = 15                       # [ATC]POCKETS = 15 (ned5_pb.ini:116)
VAR_POLL_MS = 2000


def pbase(n):
    """First param of pocket n's table row: 4100+4n (4104..4160)."""
    return 4100 + 4 * n


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = load_runtime_ui(ui_path, self)
        self.setObjectName('rack_map')   # PB tab title: "rack map"

        self._params = {}                # var-file image {int: float}
        self._var_path = None
        self._var_mtime = None
        self._var_warned = False
        self._tool_committed = {}        # pocket -> last value we accepted
        self._holds_committed = None

        self._wire()

        self._var_timer = QTimer(self)
        self._var_timer.timeout.connect(self._poll_var)
        self._var_timer.start(VAR_POLL_MS)
        self._poll_var()

    # ---- wiring (loud, house pattern) -------------------------------------
    def _widget_names(self):
        names = ['rm_spindle_holds', 'rm_status']
        for n in range(1, N_POCKETS + 1):
            names += ['rm_pk_%d' % n, 'rm_tool_%d' % n, 'rm_seatx_%d' % n,
                      'rm_seaty_%d' % n, 'rm_clr_%d' % n,
                      'rm_teachs_%d' % n, 'rm_teachc_%d' % n]
        return names

    def _wire(self):
        try:
            missing = []
            found = 0
            for name in self._widget_names():
                if self.findChild(QWidget, name) is None:
                    missing.append(name)
                else:
                    found += 1
            self._missing = missing
            if missing:
                LOG.error('RACK MAP: %d widgets missing: %s',
                          len(missing), ', '.join(missing))
            for n in range(1, N_POCKETS + 1):
                sp = self.findChild(QWidget, 'rm_tool_%d' % n)
                if sp is not None:
                    sp.editingFinished.connect(
                        lambda p=n: self._tool_commit(p))
                b = self.findChild(QWidget, 'rm_teachs_%d' % n)
                if b is not None:
                    b.clicked.connect(
                        lambda _=False, p=n: self._teach(p, 1))
                b = self.findChild(QWidget, 'rm_teachc_%d' % n)
                if b is not None:
                    b.clicked.connect(
                        lambda _=False, p=n: self._teach(p, 2))
            sp = self.findChild(QWidget, 'rm_spindle_holds')
            if sp is not None:
                sp.editingFinished.connect(self._holds_commit)
            LOG.info('RACK MAP: %d widgets wired (%d pockets + sync row)',
                     found, N_POCKETS)
        except Exception as e:
            LOG.error('RACK MAP wiring failed: %s', e)

    # ---- var-file read path ------------------------------------------------
    def _resolve_var_path(self):
        # [RS274NGC]PARAMETER_FILE relative to the INI dir (ned5_pb.ini:81)
        import linuxcnc
        ini_path = os.getenv('INI_FILE_NAME')
        if not ini_path:
            raise RuntimeError('INI_FILE_NAME not set')
        pf = linuxcnc.ini(ini_path).find('RS274NGC', 'PARAMETER_FILE')
        if not pf:
            raise RuntimeError('[RS274NGC]PARAMETER_FILE missing')
        if not os.path.isabs(pf):
            pf = os.path.join(os.path.dirname(os.path.abspath(ini_path)), pf)
        return pf

    def _poll_var(self):
        try:
            if self._var_path is None:
                self._var_path = self._resolve_var_path()
                LOG.info('RACK MAP: parameter file: %s', self._var_path)
            mtime = os.path.getmtime(self._var_path)
            if mtime == self._var_mtime:
                return
            params = {}
            with open(self._var_path) as f:
                for line in f:
                    parts = line.split()
                    # interp contract: exactly two numeric columns count
                    if len(parts) != 2:
                        continue
                    try:
                        params[int(parts[0])] = float(parts[1])
                    except ValueError:
                        continue
            self._params = params
            self._var_mtime = mtime
            self._refresh()
            st = self.findChild(QWidget, 'rm_status')
            if st is not None:
                st.setText('var file read %s  (%d params)  %s' % (
                    time.strftime('%H:%M:%S', time.localtime(mtime)),
                    len(params), os.path.basename(self._var_path)))
            LOG.info('RACK MAP: var file refreshed (%d params, mtime %s)',
                     len(params), time.strftime('%H:%M:%S',
                                                time.localtime(mtime)))
        except Exception as e:
            if not self._var_warned:
                self._var_warned = True
                LOG.error('RACK MAP: var file read failed (%s) -- table '
                          'shows stale/empty values until it succeeds', e)
            st = self.findChild(QWidget, 'rm_status')
            if st is not None:
                st.setText('var file UNREADABLE: %s' % e)

    def _refresh(self):
        p = self._params
        for n in range(1, N_POCKETS + 1):
            b = pbase(n)
            flags = int(p.get(b + 3, 0.0))
            seat_taught = (flags // 2) % 2 == 1
            clear_taught = (flags // 4) % 2 == 1
            axis = 'X' if flags % 2 == 0 else 'Y'
            self._set_lbl('rm_seatx_%d' % n,
                          '%.3f' % p.get(b, 0.0) if seat_taught else '—',
                          seat_taught)
            self._set_lbl('rm_seaty_%d' % n,
                          '%.3f' % p.get(b + 1, 0.0) if seat_taught else '—',
                          seat_taught)
            self._set_lbl('rm_clr_%d' % n,
                          '%s %.3f' % (axis, p.get(b + 2, 0.0))
                          if clear_taught else '—', clear_taught)
            tool = int(p.get(4000 + n, 0.0))
            self._set_spin('rm_tool_%d' % n, tool)
            self._tool_committed.setdefault(n, tool)
            if n in self._tool_committed and \
               self._tool_committed[n] != tool:
                # interpreter (toolchange/m13) moved it under us: accept
                LOG.info('RACK MAP: pocket %d tool now %d (var file)',
                         n, tool)
                self._tool_committed[n] = tool
        holds = int(p.get(3991, 0.0))
        self._set_spin('rm_spindle_holds', holds)
        if self._holds_committed is None or self._holds_committed != holds:
            self._holds_committed = holds

    # value-label colors are set per-widget HERE, not via a QSS attribute
    # selector: [rmSeat="true"] polished inconsistently under the runtime
    # loader (alternate rows stayed grey, offscreen audit 2026-08-02) --
    # a per-widget stylesheet is deterministic (house _jog_flash pattern)
    STYLE_TAUGHT = 'color: rgb(232,166,53); font: 10pt;'
    STYLE_UNTAUGHT = 'color: rgb(110,117,124); font: 10pt;'

    def _set_lbl(self, name, text, taught=True):
        w = self.findChild(QWidget, name)
        if w is None:
            return
        if w.text() != text:
            w.setText(text)
        style = self.STYLE_TAUGHT if taught else self.STYLE_UNTAUGHT
        if w.styleSheet() != style:
            w.setStyleSheet(style)

    def _set_spin(self, name, val):
        w = self.findChild(QWidget, name)
        if w is None or w.hasFocus():     # never stomp mid-edit
            return
        if w.value() != val:
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)

    # ---- house MDI pattern (guard -> confirm MDI mode -> fire) ------------
    def _mdi_fire(self, label, lines):
        """ned house pattern (ned_controls.py _jog_issue): guards refuse
        LOUDLY, MODE_MDI is CONFIRMED by polling (ned_brain restores MANUAL
        on its own edge; losing that race paints 'Must be in MDI mode'),
        then every line is ONE fire-and-forget mdi(). Never wait_complete()
        around the lines themselves."""
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON:
                c.error_msg('%s refused: machine is not ON' % label)
                LOG.error('%s refused: machine is not ON', label)
                return False
            if not all(s.homed[:6]):
                c.error_msg('%s refused: machine not fully homed' % label)
                LOG.error('%s refused: not fully homed', label)
                return False
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos \
               or any(s.joint[j]['homing'] for j in range(6)):
                c.error_msg('%s refused: machine is busy' % label)
                LOG.error('%s refused: machine busy', label)
                return False
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            deadline = time.time() + 2.0
            while True:
                s.poll()
                if s.task_mode == linuxcnc.MODE_MDI:
                    break
                if time.time() >= deadline:
                    c.error_msg('%s refused: could not enter MDI mode'
                                % label)
                    LOG.error('%s refused: task_mode never reached MDI',
                              label)
                    return False
                time.sleep(0.02)
            for line in lines:
                c.mdi(line)
                LOG.info('%s: MDI "%s" issued (fire-and-forget)',
                         label, line)
            return True
        except Exception as e:
            LOG.error('%s failed: %s', label, e)
            return False

    # ---- actions -----------------------------------------------------------
    def _tool_commit(self, n):
        try:
            sp = self.findChild(QWidget, 'rm_tool_%d' % n)
        except RuntimeError:
            return   # teardown: Qt emits editingFinished while destructing
        if sp is None:
            return
        v = int(sp.value())
        if v == self._tool_committed.get(n):
            return                        # focus-out without a change
        label = 'RACK MAP tool[%d]' % n
        # duplicate tool number anywhere else in the rack: REFUSE loudly
        if v != 0:
            for m in range(1, N_POCKETS + 1):
                if m != n and int(self._params.get(4000 + m, 0.0)) == v:
                    try:
                        import linuxcnc
                        linuxcnc.command().error_msg(
                            '%s REFUSED: tool %d already assigned to '
                            'pocket %d' % (label, v, m))
                    except Exception:
                        pass
                    LOG.error('%s REFUSED: tool %d already in pocket %d '
                              '-- spinbox reverted', label, v, m)
                    self._set_spin('rm_tool_%d' % n,
                                   self._tool_committed.get(n, 0))
                    return
        if v not in (0, n):
            # legal (hand-loaded reality) but fights the fixed-homes rack:
            # toolchange.ngc puts tool v away in fork v, not fork n
            LOG.warning('%s: assigning tool %d to pocket %d -- fixed-homes '
                        'toolchange will return tool %d to fork %d',
                        label, v, n, v, v)
        if self._mdi_fire(label, ['#%d=%d' % (4000 + n, v)]):
            self._tool_committed[n] = v
            self._params[4000 + n] = float(v)   # local echo until var save
        else:
            self._set_spin('rm_tool_%d' % n, self._tool_committed.get(n, 0))

    def _teach(self, n, mode):
        what = 'SEAT' if mode == 1 else 'CLEAR'
        label = 'RACK MAP teach %s[%d]' % (what, n)
        LOG.info('%s: operator fired (head parked at the %s position)',
                 label, what.lower())
        self._mdi_fire(label, ['o<rack_teach> call [%d] [%d]' % (n, mode)])
        # values land in the table when the interp saves the var file;
        # the rack_teach PRINT line is the immediate confirmation

    def _holds_commit(self):
        try:
            sp = self.findChild(QWidget, 'rm_spindle_holds')
        except RuntimeError:
            return   # teardown: Qt emits editingFinished while destructing
        if sp is None:
            return
        v = int(sp.value())
        if v == self._holds_committed:
            return
        label = 'RACK MAP spindle-holds'
        if self._mdi_fire(label, ['M61 Q%d' % v, '#3991=%d' % v]):
            self._holds_committed = v
            self._params[3991] = float(v)
        else:
            self._set_spin('rm_spindle_holds', self._holds_committed or 0)
