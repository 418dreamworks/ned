"""ned Homing Menu -- config-owned provider (2026-08-01).

Replaces qtpyvcp's stock HomingMenu ENTIRELY: the menubar override in
custom_config.yml points the Machine > Homing entry here, so the stock
machine.home.* actions are never constructed. The rebind-after-the-fact
approach is dead (failed twice: silent 0/6 match racked the gantry
2026-08-01 13:08; the text-walk rebind intermittently captured the wrong
QAction instances -- 3 of 4 operator Home All clicks fell through to
stock and wedged homing).

Every action resolves the ned_controls user tab AT CLICK TIME and calls
its supervised cycle. Every click is logged. A missing tab is a loud
on-screen error and NO home command -- never a silent fallthrough.

Config dir is on sys.path (qtpyvcp config_loader inserts it), so the
provider string is simply 'ned_homing_menu:NedHomingMenu'.
"""
import linuxcnc

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger
from qtpyvcp.utilities.qt_safety import safe_qt_callback

LOG = logger.getLogger(__name__)


class NedHomingMenu(QMenu):
    """Machine > Homing: six find-machine-zero actions, ned-supervised.

    Home All  -> request_homeall (XYZ switch-home, A/C read+home parallel)
    Home X    -> home_x_pair     (gantry pair, synchronized -1 ONLY)
    Home Y/Z  -> home_joint      (that joint alone)
    Home A/C  -> request_single_ref (fresh head read -> home -> verify)
    """

    ENTRIES = [
        ('Home &All', 'request_homeall', ()),
        ('Home &X', 'home_x_pair', ()),
        ('Home &Y', 'home_joint', ('Y', 1)),
        ('Home &Z', 'home_joint', ('Z', 2)),
        ('Home A', 'request_single_ref', ('a',)),
        ('Home C', 'request_single_ref', ('c',)),
    ]

    def __init__(self, parent=None, axes=None):
        super(NedHomingMenu, self).__init__(parent)
        for text, meth, args in self.ENTRIES:
            act = QAction(parent=self, text=text)
            act.triggered.connect(
                lambda _=False, t=text, m=meth, a=args: self._fire(t, m, a))
            self.addAction(act)
        # READINESS gating (operator 2026-08-02: "disable the homing option
        # until the machine is fucking READY to home"): enabled ONLY when the
        # machine is ON *and* the A/C startup in-place home has landed --
        # clicking early used to collide with the head read and wedge/error.
        # Polled (0.5 s): homed flags have no notify channel here.
        try:
            from PySide6.QtCore import QTimer
            self._status = getPlugin('status')

            self._nml = None

            def _ready_poll():
                try:
                    if self._nml is None:
                        self._nml = linuxcnc.stat()
                    self._nml.poll()
                    st = self._nml
                    ready = (st.task_state == linuxcnc.STATE_ON
                             and st.homed[4] and st.homed[5])
                    if ready != self.isEnabled():
                        self.setEnabled(ready)
                        LOG.info('NED Homing menu %s (ON=%s, A/C in-place=%s)',
                                 'ENABLED' if ready else 'disabled',
                                 st.task_state == linuxcnc.STATE_ON,
                                 bool(st.homed[4] and st.homed[5]))
                except Exception as e:
                    self._nml = None
                    if not getattr(self, '_poll_err_logged', False):
                        self._poll_err_logged = True
                        LOG.error('NED Homing menu readiness poll failed: %s', e)

            self.setEnabled(False)
            self._ready_timer = QTimer(self)
            self._ready_timer.timeout.connect(safe_qt_callback(self, _ready_poll))
            self._ready_timer.start(500)
        except Exception as e:
            LOG.error('NED Homing menu: readiness gating unavailable (%s)', e)
        LOG.info('NED Homing menu constructed: %d supervised actions '
                 '(stock HomingMenu replaced at config level)',
                 len(self.ENTRIES))

    @staticmethod
    def _tab():
        for w in QApplication.topLevelWidgets():
            t = w.findChild(QWidget, 'ned_controls')
            if t is not None:
                return t
        return None

    def _fire(self, text, meth, args):
        label = text.replace('&', '')
        LOG.info('NED Homing menu CLICK: %s -> %s%r', label, meth, args)
        tab = self._tab()
        if tab is None or not hasattr(tab, meth):
            LOG.error('NED Homing menu: ned_controls tab / method %r NOT '
                      'found -- NO home command issued', meth)
            try:
                linuxcnc.command().error_msg(
                    '%s unavailable: ned_controls tab not loaded' % label)
            except Exception:
                pass
            return
        try:
            if meth == 'request_homeall':
                # STALE/SESSION HOME banner state: a plain click counter
                # (operator 2026-08-02); the DRO banner flips to SESSION
                # HOME once clicks > 0 AND all joints report homed.
                tab._homeall_clicks = getattr(tab, '_homeall_clicks', 0) + 1
            getattr(tab, meth)(*args)
        except Exception as e:
            LOG.error('NED Homing menu: %s failed: %s', label, e)
