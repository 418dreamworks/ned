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
    Home A/C  -> ac_to_zero (adopt the encoder, then joint-jog that
                 joint to 0 -- joint mode, so TCP does not drag XYZ in)
    """

    ENTRIES = [
        ('Home &All', 'request_homeall', ()),
        ('Home &X', 'home_x_pair', ()),
        ('Home &Y', 'home_joint', ('Y', 1)),
        ('Home &Z', 'home_joint', ('Z', 2)),
        ('Home A', 'ac_to_zero', ('a',)),
        ('Home C', 'ac_to_zero', ('c',)),
        ('Home A&C', 'ac_to_zero_both', ()),
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
                    # Not just "A/C are homed": that goes true the instant
                    # declare_xyzw() finishes, while the machine-ON head read
                    # is still in flight. Clicking Home All in that window let
                    # do_inplace fire into the running cycle and wedge Z
                    # (2026-08-03). Also require the machine to be idle and no
                    # joint mid-homing, so the menu cannot invite a click into
                    # a window where the answer is "not yet".
                    # ...and NOT while the brain still owns the head. A
                    # zero-travel declare can raise and drop joint['homing']
                    # inside one 500 ms poll, so this flag -- held from the
                    # first pin write until every head joint is confirmed
                    # back at HOME_IDLE -- is what actually closes the window
                    # (operator 2026-08-07: "positive confirmation of
                    # whatever process is required to end before another
                    # homing can take place").
                    tab = self._tab()
                    _hb = getattr(tab, 'head_busy', None) if tab else None
                    busy = bool(_hb()) if callable(_hb) else True
                    if not callable(_hb) and not getattr(
                            self, '_hb_missing_logged', False):
                        self._hb_missing_logged = True
                        LOG.error('NED Homing menu: ned_controls.head_busy() '
                                  'not reachable (tab=%r) -- menu held '
                                  'DISABLED (fail closed)', tab)
                    # NOTHING IN THIS MENU WHILE ANYTHING MOVES (operator
                    # 2026-08-10: Home C clicked during a Home A jog corrupted
                    # the C DRO). joint['homing'] is FALSE during ac_to_zero's
                    # jog, so velocity is the only honest 'machine is busy'.
                    ready = (abs(st.current_vel) < 0.01
                             and st.task_state == linuxcnc.STATE_ON
                             and st.homed[4] and st.homed[5]
                             and st.interp_state == linuxcnc.INTERP_IDLE
                             and not busy
                             and not any(st.joint[j]['homing']
                                         for j in range(6)))
                    # NAME THE BLOCKER. This used to log only ON /
                    # A-C-homed / head-busy, so a menu greyed by velocity,
                    # interp state or a homing joint looked identical to a
                    # healthy one and the operator could not tell why the
                    # entries were dead (2026-08-10: "check why i can't
                    # reach the clicking to home").
                    _why = []
                    if abs(st.current_vel) >= 0.01:
                        _why.append('moving (vel %.3f)' % st.current_vel)
                    if st.task_state != linuxcnc.STATE_ON:
                        _why.append('machine not ON (state %d)'
                                    % st.task_state)
                    if not (st.homed[4] and st.homed[5]):
                        _why.append('A/C not homed (%d,%d)'
                                    % (st.homed[4], st.homed[5]))
                    if st.interp_state != linuxcnc.INTERP_IDLE:
                        _why.append('interp not IDLE (%d)' % st.interp_state)
                    if busy:
                        _why.append('head busy')
                    _hj = [j for j in range(6) if st.joint[j]['homing']]
                    if _hj:
                        _why.append('joint(s) %s homing' % _hj)
                    if ready != self.isEnabled():
                        self.setEnabled(ready)
                        if not ready:
                            LOG.error('NED Homing menu DISABLED because: %s',
                                      '; '.join(_why) or 'unknown')
                        LOG.info('NED Homing menu %s (ON=%s, A/C in-place=%s,'
                                 ' head-busy=%s)',
                                 'ENABLED' if ready else 'disabled',
                                 st.task_state == linuxcnc.STATE_ON,
                                 bool(st.homed[4] and st.homed[5]), busy)
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
        # Second, independent refusal at click time: the 500 ms poll can be
        # up to half a second stale, and a click is never silently swallowed.
        if tab is not None and tab.head_busy():
            LOG.error('NED Homing menu REFUSED %s: the head is mid-cycle '
                      '(head-busy) -- no home issued', label)
            try:
                linuxcnc.command().error_msg(
                    '%s refused: head homing still in progress' % label)
            except Exception as _e:
                LOG.error('NED Homing menu: could not surface the refusal '
                          'to the operator: %s', _e)
            return
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
            # _homeall_clicks is counted inside request_homeall itself, at
            # the point c.home(-1) is actually dispatched -- counting the
            # menu CLICK here as well double-counted, and credited a home
            # that request_homeall may have refused ("homing already in
            # progress"). One owner, and it means "a home really went out".
            getattr(tab, meth)(*args)
        except Exception as e:
            LOG.error('NED Homing menu: %s failed: %s', label, e)
