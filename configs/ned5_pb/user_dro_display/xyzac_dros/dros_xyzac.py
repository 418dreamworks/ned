import os
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages/probe_basic")
from probe_basic_rc import *
import linuxcnc

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger
from qtpyvcp.utilities.runtime_ui_loader import load_ui as load_runtime_ui

LOG = logger.getLogger(__name__)

STATUS = getPlugin('status')
TOOL_TABLE = getPlugin('tooltable')

INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))


def _load_ui(ui_path, parent):
    return load_runtime_ui(ui_path, parent)




class _HomeBanner(QWidget):
    """STALE HOME / SESSION HOME banner (operator 2026-08-02): sideways
    readable text, gentle vertical bob, in the strip left of the ZERO
    buttons. STALE (amber) until the Machine>Homing>Home All click counter
    is > 0 AND all six joints report homed; then SESSION (green), latched
    for the rest of the session. Nothing special -- just a banner."""

    def __init__(self, parent=None):
        super(_HomeBanner, self).__init__(parent)
        self.setFixedWidth(26)
        self._session = False
        self._phase = 0.0
        from PySide6.QtCore import QTimer
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(80)

    def _tick(self):
        import math
        self._phase += 0.12
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi
        self.update()

    def set_session(self, on):
        self._session = bool(on)
        if self._session:
            # operator 2026-08-02 12:28: SESSION HOME is green and STILL
            # ("no danger any more") -- only STALE bobs
            self._t.stop()
        self.update()

    def paintEvent(self, ev):
        import math
        from PySide6.QtGui import QPainter, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        text = 'SESSION HOME' if self._session else 'STALE HOME'
        color = QColor(60, 200, 90) if self._session else QColor(235, 170, 40)
        p.setPen(color)
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        fm = p.fontMetrics()
        # glide the text up/down the full column ("a banner going up and
        # down"), never past the edges
        amp = max(0, (self.height() - fm.horizontalAdvance(text)) // 2 - 6)
        bob = 0 if self._session else int(amp * math.sin(self._phase))
        p.translate(self.width() - 6, self.height() // 2 + bob)
        p.rotate(-90)
        p.drawText(-fm.horizontalAdvance(text) // 2, 0, text)
        p.end()



class UserDRO(QWidget):
    # MPG highlight: the WHOLE ROW (work + dtg + machine) of the axis the
    # pendant will jog goes yellow. The axis arrives on OUR OWN netted pin
    # ned-dro.axis-in (<= pendant.sel-axis, postgui_pb.hal) via a qtpyvcp
    # QPin listener -- instance access only, NEVER hal.get_value() in GUI
    # code (it spins on the global HAL mutex; a leaked mutex froze the whole
    # UI, py-spy-confirmed 2026-07-31). Style is reapplied on a Qt timer:
    # the DRO widgets restyle themselves on state changes (e.g. homed) and
    # stomp our stylesheet -- an on-change-only highlight froze after homing.
    MPG_AXES = ['x', 'y', 'z', 'a', 'c']
    MPG_COLS = ['dro_entry_main_', 'drolabel_dtg_', 'drolabel_machine_']
    MPG_HL = 'color: rgb(255, 220, 0);'

    def __init__(self, parent=None):
        super(UserDRO, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = _load_ui(ui_path, self)
        self.setObjectName('dros_xyzac')   # the tab finds us by this name
        from PySide6.QtCore import QTimer
        # NO HAL here at all: this module loads DEFERRED (after the UI settles,
        # AFTER postgui), so it cannot own netted pins. The axis arrives from
        # the ned_controls tab (ned-tab.axis-in listener -> set_mpg_axis).
        self._mpg_ax = 0
        self._mpg_rows = None
        self._mpg_timer = QTimer(self)
        self._mpg_timer.timeout.connect(self._mpg_apply)
        self._mpg_timer.start(300)
        # STALE/SESSION HOME banner: added after the window settles (the
        # 6 s house delay -- early reparenting spun Qt, 2026-08-02 10:08)
        self._banner = None
        self._banner_latch = False
        QTimer.singleShot(6000, self._add_banner)
        # NO REF BUTTONS (operator 2026-08-01: "i really do not need the REF
        # buttons because those things are done very rarely") -- homing lives
        # in Settings > Homing (menu entries rebound to the safe ned cycles
        # by ned_controls). Hide all six; their stock actions are wrong for
        # this machine anyway (one-sided gantry home, NO_REHOME no-ops).
        for name in ('ref_x_button_3', 'ref_y_button', 'ref_z_button',
                     'ref_a_button', 'ref_c_button', 'ref_all_button'):
            btn = self.findChild(QWidget, name)
            if btn is not None:
                for sig in (btn.pressed, btn.released, btn.clicked):
                    try:
                        sig.disconnect()
                    except Exception:
                        pass
                btn.hide()
        # ZERO buttons: deterministic + a 3 s countdown, second click cancels
        # (operator spec). At zero: switch to MDI, run G10 L20, wait, back to
        # MANUAL -- no mode preconditions.
        self._zero_pending = {}
        # A/C are NOT zeroable (operator 2026-08-01: "i can't imagine ever
        # needing to zero A and C other than at its regular zero" -- REF
        # owns the A/C datum). Their buttons become LOCK toggles below, and
        # ZERO ALL only touches X Y Z.
        for name, axes in (('zero_x_button', 'X'), ('zero_y_button', 'Y'),
                           ('zero_z_button', 'Z'),
                           ('zero_all_button', 'X Y Z')):
            b = self.findChild(QWidget, name)
            if b is None:
                continue
            for sig in (b.pressed, b.released, b.clicked):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            b.clicked.connect(lambda _=False, btn=b, a=axes: self._zero_click(btn, a))
        # LOCK A / LOCK C -- the A/C ZERO buttons repurposed as checkable
        # toggles. Locked = skipped entirely in the MPG selection cycle
        # (ned_controls tab -> ned-tab.lock-*-out -> pendant.lock-*).
        for name, ax in (('zero_a_button', 'a'), ('zero_c_button', 'c')):
            b = self.findChild(QWidget, name)
            if b is None:
                continue
            for sig in (b.pressed, b.released, b.clicked):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            # LITERALLY the stock Zero button with the 4 characters swapped
            # (operator): everything untouched except the wordmark icon --
            # zero.png replaced by lock.png, rendered in the identical
            # Bebas white style/size. Locked = green background.
            from PySide6.QtGui import QIcon
            b.setCheckable(True)
            b.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'lock.png')))
            b.setStyleSheet(b.styleSheet() +
                            '\nMDIButton:checked { background: rgb(25,120,45); }')
            b.toggled.connect(lambda on, btn=b, a=ax: self._ac_lock(btn, a, on))
    def _ac_lock(self, btn, ax, on):
        win = self.window()
        tab = win.findChild(QWidget, 'ned_controls') if win else None
        if tab is not None and hasattr(tab, 'set_ac_lock'):
            tab.set_ac_lock(ax, on)
        else:
            LOG.error('LOCK %s: ned_controls tab not found', ax.upper())

    def _zero_click(self, btn, axes):
        # Countdowns are per-button and fully PARALLEL; expiries feed a merge
        # queue so simultaneous zeros become ONE G10 and never interleave MDI
        # sequences (KeyError + "Can't set mode while machine is running"
        # when buttons were pressed without waiting for each other).
        from PySide6.QtCore import QTimer
        key = btn.objectName()
        pend = self._zero_pending.pop(key, None)
        if pend is not None:                      # second click = cancel
            pend['timer'].stop()
            btn.setText(pend['text'])
            LOG.info('ZERO %s cancelled', axes)
            return
        pend = {'text': btn.text(), 'left': 3, 'axes': axes}
        timer = QTimer(self)
        pend['timer'] = timer
        self._zero_pending[key] = pend

        def tick():
            if self._zero_pending.get(key) is not pend:
                timer.stop()          # cancelled/superseded -- nothing to do
                return
            pend['left'] -= 1
            if pend['left'] > 0:
                btn.setText(str(pend['left']))
                return
            timer.stop()
            btn.setText(pend['text'])
            self._zero_pending.pop(key, None)
            self._zero_enqueue(pend['axes'])

        timer.timeout.connect(tick)
        btn.setText('3')
        timer.start(1000)

    def _zero_enqueue(self, axes):
        from PySide6.QtCore import QTimer
        q = getattr(self, '_zero_queue', None)
        if q is None:
            q = self._zero_queue = set()
        q.update(axes.split())
        QTimer.singleShot(0, self._zero_run_queue)

    def _zero_run_queue(self):
        from PySide6.QtCore import QTimer
        q = getattr(self, '_zero_queue', None)
        if not q:
            return
        try:
            import linuxcnc
            s = linuxcnc.stat()
            s.poll()
            busy = (s.task_state != linuxcnc.STATE_ON
                    or s.interp_state != linuxcnc.INTERP_IDLE
                    or any(s.joint[j]['homing'] for j in range(6)))
        except Exception:
            busy = True
        if busy:
            QTimer.singleShot(300, self._zero_run_queue)   # defer, don't error
            return
        axes = ' '.join(a for a in 'X Y Z A C'.split() if a in q)
        q.clear()
        self._zero(axes)

    def _zero(self, axes):
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON or \
               s.interp_state != linuxcnc.INTERP_IDLE:
                LOG.error('ZERO %s ignored: machine off or program running', axes)
                return
            if not all(s.homed[:6]):
                c.error_msg('ZERO needs a HOMED machine: with gantry (non-identity) kinematics, LinuxCNC refuses MDI unhomed (motion command.c:584). Home All (Homing menu) first, or launch with run5.sh resume.')
                return
            words = ' '.join(a + '0.0' for a in axes.split())
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi('G10 L20 P0 ' + words)
            c.wait_complete()
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            s.poll()
            if all(s.homed[:6]):
                c.teleop_enable(1)
            LOG.info('ZERO %s done (G10 L20 P0)', axes)
        except Exception as e:
            LOG.error('ZERO %s failed: %s', axes, e)

    def _add_banner(self):
        # operator 2026-08-02 12:16: banner = its own COLUMN, direct left of
        # ZERO ALL..LOCK C, spanning top to bottom. widget_xyzac (the
        # buttons' container, header..C rows exactly) sits in a VERTICAL
        # box, so a slot-insert stacks ABOVE it (the 11:5x mistake). Wrap
        # instead: HBox [banner | widget_xyzac] takes widget_xyzac's slot.
        try:
            from PySide6.QtWidgets import QBoxLayout, QHBoxLayout
            zb = self.findChild(QWidget, 'zero_x_button')
            if zb is None or zb.parentWidget() is None:
                LOG.error('HOME banner: zero_x_button not found -- no banner')
                return
            col = zb.parentWidget()                     # widget_xyzac
            outer = col.parentWidget().layout() if col.parentWidget() else None
            if not isinstance(outer, QBoxLayout):
                LOG.error('HOME banner: parent layout is %s, not a box '
                          'layout -- no banner', type(outer).__name__)
                return
            idx = outer.indexOf(col)
            wrap = QWidget(col.parentWidget())
            hb = QHBoxLayout(wrap)
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(2)
            self._banner = _HomeBanner()
            hb.addWidget(self._banner)
            hb.addWidget(col)          # reparents col out of outer into wrap
            outer.insertWidget(idx, wrap)
            LOG.info('HOME banner column added left of %s (STALE HOME until '
                     'menu Home All completes this session)', col.objectName())
        except Exception as e:
            LOG.error('HOME banner failed: %s', e)

    def set_mpg_axis(self, val):
        self._mpg_ax = int(val)
        self._mpg_apply()

    def _mpg_apply(self):
        if self._mpg_rows is None:
            rows = []
            for name in self.MPG_AXES:
                rows.append([w for w in
                             (self.findChild(QWidget, c + name) for c in self.MPG_COLS)
                             if w is not None])
            self._mpg_rows = rows
        for i, row in enumerate(self._mpg_rows):
            style = self.MPG_HL if i == self._mpg_ax else ''
            for w in row:
                if w.styleSheet() != style:
                    w.setStyleSheet(style)
        self._unhomed_dro()
        if self._banner is not None and not self._banner_latch:
            try:
                win = self.window()
                tab = win.findChild(QWidget, 'ned_controls') if win else None
                clicks = getattr(tab, '_homeall_clicks', 0) if tab else 0
                if clicks > 0 and self._stat is not None \
                   and all(self._stat.homed[j] for j in range(6)):
                    self._banner_latch = True
                    self._banner.set_session(True)
                    LOG.info('HOME banner -> SESSION HOME (physical home '
                             'completed this session)')
            except Exception:
                pass

    # UNHOMED DRO: free-mode joint jogging moves only JOINT positions -- world
    # coordinates (what the DRO widgets display) FREEZE with kinstype=BOTH, so
    # MPG motion showed nothing ("the DRO does not read any movement"). While a
    # joint is unhomed, write its live joint position into the cell; the frozen
    # world channel fires no updates, so the text sticks. Once homed, the
    # widget's own binding resumes and overwrites. NML status poll -- no HAL.
    DRO_JOINT = {'x': 0, 'y': 1, 'z': 2, 'a': 4, 'c': 5}

    AXIS_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'c': 5}

    def _unhomed_dro(self):
        # WORLD-FREEZE HONESTY (operator 2026-08-01: "A and C's position
        # should be reported at startup, EVERY TIME. they are homed.
        # always."): with gantry kins LinuxCNC freezes the ENTIRE world
        # channel until ALL joints are homed -- including already-homed
        # A/C, whose absolute angles are known and moving. So until all
        # six are homed, BOTH the work and machine cells of every axis
        # show the live JOINT position (for A/C that IS the true angle;
        # machine==work==joint by design). On the all-homed edge every
        # cell is released to its stock world-fed binding with one honest
        # final write.
        try:
            import linuxcnc
            if getattr(self, '_stat', None) is None:
                self._stat = linuxcnc.stat()
                self._dro_overridden = set()
            self._stat.poll()
        except Exception:
            return
        st = self._stat
        try:
            allh = all(st.homed[j] for j in (0, 1, 2, 3, 4, 5))
        except Exception:
            return
        for name, jn in self.DRO_JOINT.items():
            try:
                w = self.findChild(QWidget, 'dro_entry_main_' + name)
                m = self.findChild(QWidget, 'drolabel_machine_' + name)
                fmt = '{:+.2f}' if name in 'xyz' else '{:+.3f}'
                if allh:
                    if name in self._dro_overridden:
                        i = self.AXIS_IDX[name]
                        work = (st.actual_position[i] - st.g5x_offset[i]
                                - st.g92_offset[i] - st.tool_offset[i])
                        if w is not None:
                            w.setText(fmt.format(work))
                        if m is not None:
                            m.setText(fmt.format(st.actual_position[i]))
                        self._dro_overridden.discard(name)
                    continue
                jpos = st.joint_actual_position[jn]
                if w is not None:
                    w.setText(fmt.format(jpos))
                if m is not None:
                    m.setText(fmt.format(jpos))
                self._dro_overridden.add(name)
            except Exception:
                pass