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

# ---------------------------------------------------------------------------
# JOINT COUNT. -xyzab adds the workpiece rotary B as joint 6 (operator
# 2026-08-11), so every gate that means "all joints homed" or "any joint
# homing" has to count seven, not six. These were written when six was the
# only answer; a half-swept file is the dangerous state -- some gates would
# release while B was still unhomed and the machine cannot enter teleop
# without it, so world jogging would fail with the GUI showing ready.
# ---------------------------------------------------------------------------
NJ = 7 if os.environ.get('NED_MODE', '') == 'xyzab' else 6

STATUS = getPlugin('status')
TOOL_TABLE = getPlugin('tooltable')

INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))


def _load_ui(ui_path, parent):
    return load_runtime_ui(ui_path, parent)




class _HomeBanner(QWidget):
    """UNHOMED / STALE HOME / SESSION HOME banner (operator 2026-08-02,
    three-state 2026-08-03): sideways readable text, gentle vertical bob, in
    the strip left of the ZERO buttons.

    UNHOMED (red) at launch and until all six joints report homed -- the
    coordinates mean NOTHING yet, because the brain is still declaring the
    stored XYZ frame and waiting on the A/C absolute encoder read. That read
    lands seconds after startup, so the operator needs to see when it is done
    (operator 2026-08-03: "so i know to wait for that AC reading business").

    STALE HOME (amber) once all six are homed but the frame came from
    stored_home.json rather than a switch-seeking cycle this session.

    SESSION HOME (green) once Home All has run this session; latched, and
    still, because there is no danger any more. UNHOMED and STALE bob.

    Display only -- CLAUDE.md rule 17, nothing may gate on this."""

    UNHOMED, STALE, SESSION = 'unhomed', 'stale', 'session'
    _LOOK = {
        UNHOMED: ('UNHOMED', (215, 75, 75)),
        STALE:   ('STALE HOME', (235, 170, 40)),
        SESSION: ('SESSION HOME', (60, 200, 90)),
    }

    def __init__(self, parent=None):
        super(_HomeBanner, self).__init__(parent)
        self.setFixedWidth(26)
        self._state = self.UNHOMED
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

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        if state == self.SESSION:
            # operator 2026-08-02 12:28: SESSION HOME is green and STILL
            # ("no danger any more") -- UNHOMED and STALE bob
            self._t.stop()
        elif not self._t.isActive():
            self._t.start(80)
        self.update()

    def set_session(self, on):
        """Back-compat for the original two-state caller."""
        self.set_state(self.SESSION if on else self.STALE)

    def paintEvent(self, ev):
        import math
        from PySide6.QtGui import QPainter, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        text, rgb = self._LOOK[self._state]
        color = QColor(*rgb)
        p.setPen(color)
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        fm = p.fontMetrics()
        # glide the text up/down the full column ("a banner going up and
        # down"), never past the edges
        amp = max(0, (self.height() - fm.horizontalAdvance(text)) // 2 - 6)
        bob = (0 if self._state == self.SESSION
               else int(amp * math.sin(self._phase)))
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
    # DTG is GONE (operator 2026-08-11: "i don't use DTG at all. remove
    # it completely"), so the MPG row highlight has one less column to
    # paint. Leaving it here would just be a lookup that never matches.
    MPG_COLS = ['dro_entry_main_', 'drolabel_machine_']
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
        self._banner_state = None
        QTimer.singleShot(6000, self._add_banner)
        # DTG removed at RUNTIME rather than by cutting the .ui:
        # a .ui edit here is 6 widgets across 5 grid rows and a
        # header, and a mis-spliced layout is a dead DRO. Hiding
        # is reversible by deleting one call.
        QTimer.singleShot(1400, self._drop_dtg)
        # -xyzab: the C row is pointed at joint 6 / axis B (DRO_JOINT,
        # AXIS_IDX below), so its letter has to say B. A row labelled C
        # showing B's angle is worse than no row at all -- it is the
        # one display on the machine the operator trusts blind.
        if os.environ.get('NED_MODE', '') == 'xyzab':
            QTimer.singleShot(1200, self._xyzab_relabel)
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
            # SINGLE = LOCK, DOUBLE = the zero countdown (operator
            # 2026-08-06: "double clicks on the zero XYZ button starts the
            # zero counter, and single click is a lock"). ZERO ALL is in
            # this loop on the same terms since 2026-08-10 -- "lets have the
            # zeroall have the same lock and zero behavior as xyz" -- it
            # just carries three axes instead of one.
            # Qt's own doubleClickInterval decides: a click becomes a lock
            # toggle only if no second click follows; a click during a
            # running countdown keeps its old meaning, cancel.
            b.installEventFilter(self)
            b.clicked.connect(lambda _=False, btn=b, a=axes:
                              self._xyz_click(btn, a))
        # LOCK A / LOCK C -- the A/C ZERO buttons repurposed as checkable
        # toggles. Locked = skipped entirely in the MPG selection cycle
        # (ned_controls tab -> ned-tab.lock-*-out -> pendant.lock-*).
        self._lock_btns = {}
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
            # RED = LOCKED (operator 2026-08-06; was green)
            b.setStyleSheet(b.styleSheet() +
                            '\nMDIButton:checked { background: rgb(190,45,35); }')
            b.toggled.connect(lambda on, btn=b, a=ax: self._ac_lock(btn, a, on))
            self._lock_btns[ax] = b
        # COLOUR TRACKS STATE, NOT CLICKS (operator 2026-08-04). The green
        # came from :checked, and checked only moved when a finger moved it
        # -- so a calibration cycle locking A/C, or the startup clear, left
        # the button showing the opposite of the truth. Poll the pin the
        # pendant actually obeys and follow it. Signals blocked while
        # setting, or setChecked would call _ac_lock and write the pin back.
        from PySide6.QtCore import QTimer
        self._lock_sync_timer = QTimer(self)
        self._lock_sync_timer.timeout.connect(self._sync_lock_buttons)
        self._lock_sync_timer.start(400)
        self._sync_lock_buttons()

    def _sync_lock_buttons(self):
        # MPG-TIMER WATCHDOG (2026-08-04). During the hands-off stale-home
        # hunt the log stream suggested _mpg_timer dies a few ticks in; the
        # final evidence (screen showed STALE while the log said UNHOMED)
        # says the real fault was lcnc.log's GUI stream stalling mid-session,
        # not the timers. Kept anyway as cheap insurance: it is silent unless
        # a timer is GENUINELY dead, and its counter log is the proof either
        # way. If 'watchdog revive' never appears, the timers were fine.
        try:
            t = getattr(self, '_mpg_timer', None)
            if t is not None and not t.isActive():
                n = getattr(self, '_mpg_wd', 0) + 1
                self._mpg_wd = n
                if n <= 3 or n % 100 == 0:
                    LOG.error('mpg/banner timer DEAD -- watchdog revive #%d', n)
                t.start(300)
        except Exception:
            LOG.exception('mpg timer watchdog failed')
        win = self.window()
        tab = win.findChild(QWidget, 'ned_controls') if win else None
        if tab is None or not hasattr(tab, 'get_ac_lock'):
            return
        # BUSY = NOT CLICKABLE (operator 2026-08-10: "while homing zero
        # buttons continue to work. THEY SHOULDN'T"). The two loops below
        # used to force-re-enable these every 400 ms to beat qtpyvcp's
        # bindOk greying -- which also undid any disable WE wanted, so a
        # zero countdown could be started mid-home. _zero_run_queue only
        # deferred the G10 at the END; the click was accepted and the
        # countdown ran, which is what the operator saw.
        try:
            import linuxcnc as _lc
            _s = _lc.stat(); _s.poll()
            busy = (abs(_s.current_vel) > 0.01
                    or any(_s.joint[j]['homing'] for j in range(NJ))
                    or _s.interp_state != _lc.INTERP_IDLE
                    or _s.task_state != _lc.STATE_ON)
        except Exception:
            busy = True          # unreadable -> refuse
            return
        # XYZ lock visuals follow the same truth (advisor b), and every
        # lock button is kept ENABLED (advisor A4: issue_mdi.bindOk greys
        # them during any program/MDI -- but a lock is pure HAL, needed
        # most mid-cycle)
        for ax, b in getattr(self, '_xyz_lock_btns', {}).items():
            try:
                if b.isEnabled() == busy:
                    b.setEnabled(not busy)
                on = bool(tab.get_ac_lock(ax))
                base = getattr(b, '_ned_base_qss', None)
                if base is None:
                    base = b.styleSheet()
                    b._ned_base_qss = base
                want = (base + '\nMDIButton { %s }' % self.LOCK_RED
                        if on else base)
                if b.styleSheet() != want:
                    b.setStyleSheet(want)
            except RuntimeError:
                pass
        for ax, b in getattr(self, '_lock_btns', {}).items():
            try:
                if b.isEnabled() == busy:
                    b.setEnabled(not busy)
                state = bool(tab.get_ac_lock(ax))
                if b.isChecked() != state:
                    b.blockSignals(True)
                    b.setChecked(state)
                    b.blockSignals(False)
                    LOG.info('LOCK %s button -> %s (following the pin)',
                             ax.upper(), 'LOCKED' if state else 'unlocked')
            except Exception:
                LOG.exception('LOCK %s button sync failed', ax.upper())
    def _ac_lock(self, btn, ax, on):
        win = self.window()
        tab = win.findChild(QWidget, 'ned_controls') if win else None
        if tab is not None and hasattr(tab, 'set_ac_lock'):
            tab.set_ac_lock(ax, on)
        else:
            LOG.error('LOCK %s: ned_controls tab not found', ax.upper())

    LOCK_RED = 'background: rgb(190,45,35);'

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.MouseButtonDblClick:
            p = getattr(self, '_xyz_p1', None) or {}
            t = p.pop(obj.objectName(), None)
            if t is not None:
                t.stop()                     # cancel the single-click lock
                t.deleteLater()
            # A DOUBLE CLICK MUST NEVER LEAVE IT LOCKED (operator
            # 2026-08-10: "a double click should lock XYZ but it also zeros
            # it" / "if its a double click it should not lock"). Cancelling
            # the pending timer only wins if the timer has not fired yet --
            # doubleClickInterval is a race we cannot reliably win. So if a
            # lock DID land in the last 1.5 s on this button, put it back.
            import time as _t
            u = getattr(self, '_xyz_lock_undo', {}).pop(obj.objectName(),
                                                        None)
            if u is not None and (_t.time() - u[0]) < 1.5:
                win = self.window()
                tab = win.findChild(QWidget, 'ned_controls') if win else None
                if tab is not None and hasattr(tab, 'set_ac_lock'):
                    tab.set_ac_lock(u[1], u[2])
                    LOG.info('LOCK %s reverted to %s -- that was a double '
                             'click, not a lock', u[1].upper(),
                             'ON' if u[2] else 'OFF')
            name = obj.objectName()
            ax = {'zero_x_button': 'X', 'zero_y_button': 'Y',
                  'zero_z_button': 'Z',
                  'zero_all_button': 'X Y Z'}.get(name)
            if ax:
                self._zero_click(obj, ax)    # the zero counter
                return True
        return super().eventFilter(obj, ev)

    def _xyz_click(self, btn, axes):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        if btn.objectName() in self._zero_pending:
            self._zero_click(btn, axes)      # countdown running: cancel it
            return
        # PER-BUTTON pending (advisor A2: one shared slot let an X timer
        # fire after a Y click stole the slot) and the REAL double-click
        # interval (advisor A1: 260 ms < Qt's 400 ms default meant a slow
        # double fired the lock AND the countdown).
        key = btn.objectName()
        p = getattr(self, '_xyz_p1', None)
        if p is None:
            p = self._xyz_p1 = {}
        if key in p:
            return                           # dblclick path handles it
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda b=btn, a=axes: self._xyz_lock_toggle(b, a))
        t.timeout.connect(t.deleteLater)
        p[key] = t
        t.start(QApplication.doubleClickInterval() + 50)

    def _xyz_lock_toggle(self, btn, axes):
        # `axes` may be one axis ('X') or several ('X Y Z' from ZERO ALL,
        # operator 2026-08-10: "lets have the zeroall have the same lock and
        # zero behavior as xyz"). For a group, one click flips them all to
        # the SAME new state -- locked unless every one is already locked --
        # so the button never leaves the three disagreeing.
        axl = [a.lower() for a in axes.split()]
        ax = axl[0]
        getattr(self, '_xyz_p1', {}).pop(btn.objectName(), None)
        win = self.window()
        tab = win.findChild(QWidget, 'ned_controls') if win else None
        if tab is None or not hasattr(tab, 'set_ac_lock'):
            LOG.error('LOCK %s: ned-tab not found', axes)
            return
        cur = getattr(tab, '_ac_locked', {})
        on = not all(bool(cur.get(a)) for a in axl)
        for a in axl:
            tab.set_ac_lock(a, on)
        # NO paint here (advisor b): set_ac_lock swallows pin failures, so
        # painting on the click showed a red lock the wheel did not obey.
        # _sync_lock_buttons repaints from the tab's actual state, 400 ms.
        self._xyz_lock_btns = getattr(self, '_xyz_lock_btns', {})
        self._xyz_lock_btns[ax] = btn
        # remember it, so a double-click that raced us can put it back
        import time as _t
        self._xyz_lock_undo = getattr(self, '_xyz_lock_undo', {})
        self._xyz_lock_undo[btn.objectName()] = (_t.time(), ax, not on)
        LOG.info('LOCK %s -> %s (DRO single-click)', axes,
                 'ON' if on else 'OFF')

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
                    or any(s.joint[j]['homing'] for j in range(NJ)))
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
            if not all(s.homed[:NJ]):
                c.error_msg('ZERO needs a HOMED machine: with gantry (non-identity) kinematics, LinuxCNC refuses MDI unhomed (motion command.c:584). Home All (Homing menu) first, or launch with run5.sh resume.')
                return
            words = ' '.join(a + '0.0' for a in axes.split())

            # NEVER wait_complete() ON THE UI THREAD.
            # 2026-08-04: py-spy caught MainThread parked in wait_complete()
            # at the line after the G10 -- the zero had already been ISSUED
            # and the code then asked task "are you done?" and task never
            # answered, so Qt could not process another event and the whole
            # GUI froze. Not a crash and not a refusal: a question asked on
            # the wrong thread.
            #
            # Why task did not answer: ned_brain runs its head read on its
            # own schedule and juggles MANUAL/MDI itself, so a mode request
            # landing in that window is overwritten. _jog_issue solved this
            # on 2026-08-02 by RE-ASSERTING the mode in a poll loop and
            # never waiting on task; the fix was never carried across to the
            # zero buttons. Same race, same cure.
            import time
            c.mode(linuxcnc.MODE_MDI)
            deadline = time.time() + 4.0
            reasserts = 0
            while True:
                s.poll()
                if s.task_mode == linuxcnc.MODE_MDI:
                    break
                if time.time() >= deadline:
                    msg = ('ZERO %s REFUSED: task never reached MDI mode '
                           '(after %d re-asserts). NOTHING was changed.'
                           % (axes, reasserts))
                    LOG.error(msg)
                    try:
                        c.error_msg(msg)
                    except Exception:
                        pass
                    return
                c.mode(linuxcnc.MODE_MDI)     # brain may have taken it back
                reasserts += 1
                time.sleep(0.1)
            if reasserts:
                LOG.info('ZERO %s: MDI mode took %d re-assert(s) '
                         '(brain restore race)', axes, reasserts)

            # FIRE AND FORGET. The interpreter queues it; ned_brain restores
            # MANUAL/teleop on its own edge, which is why the old explicit
            # mode-back-and-wait was both redundant and the thing that hung.
            c.mdi('G10 L20 P0 ' + words)
            LOG.info('ZERO %s ISSUED (G10 L20 P0 %s) -- queued, not waited on',
                     axes, words)
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
            LOG.info('HOME banner column added left of %s (UNHOMED until the A/C '
                     'absolute read lands, then STALE, then SESSION)', col.objectName())
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
                homed = (self._stat is not None
                         and all(self._stat.homed[j] for j in range(NJ)))
                if not homed:
                    # the A/C absolute read has not landed yet -- the DRO
                    # numbers are not a frame at all until it does
                    state = _HomeBanner.UNHOMED
                elif clicks > 0:
                    state = _HomeBanner.SESSION
                else:
                    state = _HomeBanner.STALE
                if state != self._banner_state:
                    self._banner_state = state
                    self._banner.set_state(state)
                    LOG.info('HOME banner -> %s', state.upper())
                if state == _HomeBanner.SESSION:
                    self._banner_latch = True
            except Exception as e:
                # a silent pass here hid a stuck-UNHOMED banner for a whole
                # session (2026-08-04); log each distinct failure once
                msg = '%s: %s' % (type(e).__name__, e)
                if msg != getattr(self, '_banner_err', None):
                    self._banner_err = msg
                    LOG.error('HOME banner eval FAILED: %s', msg)

    # UNHOMED DRO: free-mode joint jogging moves only JOINT positions -- world
    # coordinates (what the DRO widgets display) FREEZE with kinstype=BOTH, so
    # MPG motion showed nothing ("the DRO does not read any movement"). While a
    # joint is unhomed, write its live joint position into the cell; the frozen
    # world channel fires no updates, so the text sticks. Once homed, the
    # widget's own binding resumes and overwrites. NML status poll -- no HAL.
    def _drop_dtg(self):
        """Hide the DTG column, header and all (operator 2026-08-11)."""
        names = ['dtg_column_header'] + ['drolabel_dtg_' + a
                                         for a in ('x', 'y', 'z', 'a', 'c')]
        gone, missing = 0, []
        for n in names:
            w = self.findChild(QWidget, n)
            if w is None:
                win = self.window()
                w = win.findChild(QWidget, n) if win else None
            if w is None:
                missing.append(n)
                continue
            # zero the minimums too: these carry a fixed 100 px width, and a
            # hidden widget with a minimum still reserves its grid column.
            try:
                w.setMinimumSize(0, 0)
                w.setMaximumSize(0, 16777215)
            except Exception:
                pass
            w.hide()
            gone += 1
        # HIDING IS ONLY HALF OF IT. Every DRO column in this .ui is
        # sizePolicy Fixed with min == max == 100, so removing one does not
        # give its width to anybody -- it just leaves a 100 px hole and the
        # two survivors stay exactly as narrow as they were (operator
        # 2026-08-11: "after taking out the DTG, the 2 cols left should take
        # up all the space").
        # 2 x 150 == the 3 x 100 the row used to occupy, so the block keeps
        # its overall footprint and the space is split evenly between the
        # two columns that are left. Fixed stays Fixed on purpose: these sit
        # in a hand-built grid alongside the axis letters and the ZERO
        # buttons, and switching them to Expanding would let them fight the
        # rest of the row for width.
        WIDE = 150
        grew = 0
        for n in (['work_column_header', 'machine_column_header']
                  + ['dro_entry_main_' + a for a in ('x', 'y', 'z', 'a', 'c')]
                  + ['drolabel_machine_' + a
                     for a in ('x', 'y', 'z', 'a', 'c')]):
            w = self.findChild(QWidget, n)
            if w is None:
                win = self.window()
                w = win.findChild(QWidget, n) if win else None
            if w is None:
                missing.append(n)
                continue
            w.setMinimumWidth(WIDE)
            w.setMaximumWidth(WIDE)
            grew += 1
        LOG.info('DTG: %d widget(s) hidden, %d column widget(s) widened to '
                 '%d px%s', gone, grew, WIDE,
                 (' -- NOT FOUND: ' + ', '.join(missing)) if missing else '')

    def _xyzab_relabel(self):
        """Rename the C row to B (-xyzab). Both DRO copies carry the label."""
        try:
            from PySide6.QtWidgets import QLabel
        except Exception:
            from PyQt5.QtWidgets import QLabel
        n = 0
        win = self.window()
        for root in (self, win):
            if root is None:
                continue
            for lab in root.findChildren(QLabel, 'axis_label_c'):
                if lab.text().strip().upper().startswith('C'):
                    lab.setText(lab.text().replace('C', 'B').replace('c', 'b'))
                    n += 1
        LOG.info('XYZAB: relabelled %d C axis label(s) to B', n)

    DRO_JOINT = {'x': 0, 'y': 1, 'z': 2, 'a': 4, 'c': 5}

    AXIS_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'c': 5}

    # -xyzab (operator 2026-08-11: "instead of controlling C, everything that
    # used to control C now controls the rotaries"). The C ROW IS REUSED
    # WHOLESALE -- same widget, same zero button, same lock, same angular
    # increment ladder -- it is simply pointed at joint 6 / axis B. postgui_b
    # .hal does exactly the same thing to the jog pins, so the row and the
    # wheel stay describing the same axis. C itself is homed to zero at
    # launch and clamped there, and has nothing left to show.
    if os.environ.get('NED_MODE', '') == 'xyzab':
        DRO_JOINT = dict(DRO_JOINT, c=6)
        AXIS_IDX = dict(AXIS_IDX, c=4)      # LinuxCNC axis order X Y Z A B C

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
                # degrees at 2 decimals like the linear axes
                # (operator 2026-08-05) -- 3 was noise, not information
                fmt = '{:+.2f}'
                if allh:
                    # UNDER -xyzab THE ROTARY ROW NEVER GOES BACK TO THE
                    # STOCK BINDING. That binding paints the letter the row
                    # was built as -- C -- which is parked at 0.0000 here,
                    # while the row is pointed at axis B. So once homed, PB
                    # showed 0 and the standalone DRO showed the real B
                    # angle, and they disagreed for the rest of the session
                    # (operator 2026-08-12: "B in SDRO and PB DRO are not
                    # aligned"). Repainting every tick from AXIS_IDX keeps
                    # the row honest; AXIS_IDX['c'] is 4 in this mode.
                    if NED_MODE == 'xyzab' and name == 'c':
                        i = self.AXIS_IDX[name]
                        if w is not None:
                            w.setText(fmt.format(
                                st.actual_position[i] - st.g5x_offset[i]
                                - st.g92_offset[i]))
                        if m is not None:
                            m.setText(fmt.format(st.actual_position[i]))
                        continue
                    if name in self._dro_overridden:
                        i = self.AXIS_IDX[name]
                        # machine cell only (advisor V6): the work value
                        # here came from stat offsets, which lie; the stock
                        # binding repaints the work cell within a tick
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