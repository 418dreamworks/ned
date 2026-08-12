"""ned controls -- operator's own controls tab (Probe Basic user tab).

JOG & PRESETS panel (the visible NED tab content, operator mockup
2026-08-01) + pendant->screen sync + core-section hiding + the V/F/S/R
override button clusters (operator mockup 2026-08-01 23:11, see
build_override_clusters). The TOOLPROBE button is gone from the .ui
(PB's stock controls serve the tool probe); its HAL plumbing stays for
the postgui nets.

ALL HAL access goes through our own userspace component 'ned-tab'
(qtpyvcp.hal.getComponent) whose pins are NETTED in postgui_pb.hal --
instance pin access only. NEVER hal.get_value() in GUI code: it spins on
the global HAL mutex from the UI thread, and a leaked mutex then freezes
the whole UI (2026-07-31: py-spy caught the frozen MainThread in exactly
that call; the pendant survived every wedge because it only touches its
own pins).

Pins (nets in postgui_pb.hal):
  ned-tab.toolprobe-cmd  bit out   -> sol.ts.in1 (OR'd with the M64 P3 path)
  ned-tab.air-ok-in      bit in    <- sig-air-pressure-ok
  ned-tab.probe-up-in    bit in    <- sig-toolsetter-deploy (real state, incl M64)
  ned-tab.inc-index-in   s32   in  <- pendant.inc-index (the SLOT, not the value)
"""
import os
import re
import time

from PySide6.QtCore import QTimer, QObject, QEvent
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget, QApplication

from qtpyvcp import hal as qhal
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


class _PreHomeInputGate(QObject):
    """Swallow every user input except the survivors.

    setEnabled(False) IS NOT A GATE IN THIS GUI. MDIButton and SubCallButton
    bind issue_mdi.bindOk (mdi_button.py:48, subcall_button.py:58), which
    re-runs widget.setEnabled(ok) on every task_state / interp_state / homed
    change (machine_actions.py:317, 323-329). With NO_FORCE_HOMING = 1
    (ned5_pb.ini:155) STATUS.allHomed() is hard True (status.py:717-719), so
    `ok` flips True the instant POWER is pressed and every MDI button comes
    back to life. The rules engine does the same through the Enable property
    (base_widget.py:301-307). A one-shot disable loses that race every time --
    which is exactly what the operator saw when ZERO X stayed clickable.

    This filter sits ABOVE the widgets: the event never reaches them, so what
    they do to their own enabled state is irrelevant. It also covers the
    line edits, MDIEntry boxes, sliders and combo boxes a button-only sweep
    never touched -- an MDIEntry takes typed g-code and moves the machine.
    """

    _BLOCK = frozenset((
        QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick, QEvent.Type.Wheel,
        QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
        QEvent.Type.Shortcut, QEvent.Type.ContextMenu,
        QEvent.Type.TabletPress, QEvent.Type.TabletRelease,
        QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate,
        QEvent.Type.TouchEnd, QEvent.Type.DragEnter, QEvent.Type.Drop,
    ))

    def __init__(self, parent=None):
        super(_PreHomeInputGate, self).__init__(parent)
        self._allow = []
        self._swallowed = 0
        self._last_log = 0.0

    def setSurvivors(self, widgets):
        self._allow = [w for w in widgets if w is not None]

    def swallowed(self):
        return self._swallowed

    def eventFilter(self, obj, ev):
        try:
            if ev.type() not in self._BLOCK:
                return False
        except Exception:
            return False
        try:
            # A spontaneous mouse/key event reaches the QWindow FIRST; Qt
            # then re-sends it to the widget under the cursor, which is where
            # the decision belongs. Blocking here would kill the survivors.
            if isinstance(obj, QWindow):
                return False
            if isinstance(obj, QWidget):
                # Qt modality already blocks the survivors while a modal
                # dialog is up; gating the dialog too would strand the
                # operator with a box they cannot dismiss AND no E-stop.
                modal = QApplication.activeModalWidget()
                if modal is not None and (obj is modal
                                          or modal.isAncestorOf(obj)):
                    return False
                w = obj
                while w is not None:
                    for a in self._allow:
                        if w is a:
                            return False
                    w = w.parentWidget()
        except RuntimeError:
            return True          # destroyed mid-event: fail CLOSED
        except Exception:
            LOG.exception('PRE-HOME GATE: filter fault -- swallowing anyway')
            return True
        self._swallowed += 1
        if ev.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            now = time.time()
            if now - self._last_log > 2.0:
                self._last_log = now
                try:
                    who = obj.objectName() or obj.__class__.__name__
                except Exception:
                    who = '<destroyed>'
                LOG.error('PRE-HOME GATE: input to %s BLOCKED -- only E-STOP '
                          'and POWER work until the home declaration lands',
                          who)
        return True

STYLE_UP = 'font: 75 18pt; background: rgb(30,140,30); color: white;'
STYLE_DOWN = 'font: 75 18pt; background: rgb(140,30,30); color: white;'
STYLE_NOAIR = 'font: 75 18pt; background: rgb(70,70,70); color: rgb(180,180,180);'

# JOG & PRESETS speed table: key -> (linear F mm/min, angular F deg/min).
# v2 operator spec 2026-08-01 23:14: SLOW 200 / MEDIUM 1200 / FAST 4000
# mm/min, rotary 15 / 60 / 180 deg/min. Emitted as the F word on every
# command; the selection persists between moves. All values are inside the
# machine limits (X/Y 200 mm/s, Z 169.3 mm/s, angular 30 deg/s), so the
# planner never has to clamp these.
# (linear mm/min, angular deg/min). Operator 2026-08-11: "for the jog, make
# fast feed 8000 ... medium can be 3000 ... AC speed can stay the same", so
# only the linear column moved. THIS is the table the PB jog panel's
# SLOW/MEDIUM/FAST buttons read -- ned_pendant.py has a separate one for the
# wheel, and editing that one alone changed nothing the operator could feel.
JOG_SPEEDS = {
    'slow':   (200.0,   15.0),
    'medium': (3000.0,  60.0),
    'fast':   (8000.0, 180.0),
}

# EMC 9-axis order XYZABCUVW -> stat.actual_position/g5x_offset/... index
# (same map the archived ned_moves panel and dros_xyzac use).
# THE ROTARY SLOT'S REAL AXIS LETTER. Internally the second rotary keeps the
# key 'c' everywhere -- pins, dicts, lock signals, the pendant slot -- because
# renaming it would touch a hundred call sites for no gain. What changes in
# -xyzab is what that slot RESOLVES to: axis B, index 4, and the letter that
# gets typed into g-code and painted on a button. Anything that turns the slot
# key into a letter or an index must go through here, or the GUI says C and
# the machine is handed a C word it will refuse (C is clamped in this mode).
ROT = 'b' if os.environ.get('NED_MODE', '') == 'xyzab' else 'c'


def _AXL(ax):
    """Slot key -> the axis LETTER actually commanded. Upper case."""
    return (ROT if ax == 'c' else ax).upper()


# LinuxCNC axis order is X Y Z A B C, so the rotary slot is index 4 under
# -xyzab and 5 otherwise.
JOG_AXIS_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'c': 4 if ROT == 'b' else 5}


# Core sections the operator wants GONE: the jog-button panel (the MPG owns
# axis jogs; ned_moves/ned_holes tabs archived to trash 2026-08-01) and the
# MAN/AUTO/MDI mode box (ned_brain manages the mode). Runtime hide only --
# names may drift with PB updates; a miss is a silent no-op.
HIDE_CORE = ('horizontalWidget',)   # jogDisplay restored 2026-08-01 (operator wants the jog buttons back)


def _remove_mdi_mode_gates():
    """Operator request: 'find all the buttons with that MDI mode required
    gate and remove all those gates'. The stock gate is ONE function: qtpyvcp
    base_actions.setTaskMode refuses when isRunning() -- which reads STALE
    status (it polls AFTER switching, base_actions.py:37-43), so a moment of
    residual RCS_EXEC makes every MDI-flavored button fail as 'Can't set mode
    while machine is running' followed by task's 'Must be in MDI mode to
    issue MDI command' (emctaskmain.cc:2214).

    Replaced with a LIVE gate instead of no gate: a task mode switch ABORTS
    in-flight motion (fully ungated, a stray GUI mode action killed long MDI
    moves partway -- 'returning to x0y0 stops halfway', 2026-07-31 night).
    Refuse only while the machine is ACTUALLY executing/moving, judged from a
    fresh poll; allow everything when truly idle. Patch both the module attr
    and every already-imported by-value binding.
    """
    try:
        import sys
        import linuxcnc
        from qtpyvcp.actions import base_actions

        def setTaskMode(new_mode):
            try:
                s = base_actions._get_stat()
                s.poll()
                moving = (s.interp_state != linuxcnc.INTERP_IDLE) \
                    or (not getattr(s, 'inpos', True)) \
                    or (getattr(s, 'current_vel', 0.0) > 1e-6)
                if moving and s.task_mode != new_mode:
                    LOG.info('setTaskMode refused: machine is moving '
                             '(a mode switch would abort motion)')
                    return False
            except Exception as e:
                LOG.error('setTaskMode live-gate check failed: %s', e)
            try:
                base_actions.CMD.mode(new_mode)
                base_actions.CMD.wait_complete()
                base_actions._get_stat().poll()
                return True
            except Exception as e:
                LOG.error('setTaskMode failed: %s', e)
                return False

        base_actions.setTaskMode = setTaskMode
        for name, mod in list(sys.modules.items()):
            if name.startswith('qtpyvcp') and mod is not None \
               and getattr(mod, 'setTaskMode', None) is not None \
               and mod is not base_actions:
                mod.setTaskMode = setTaskMode
        LOG.info('MDI mode gate: stale isRunning gate replaced with '
                 'live-motion gate')
    except Exception as e:
        LOG.error('MDI gate removal failed: %s', e)


_remove_mdi_mode_gates()


# ---- V/F/S/R override button clusters (operator mockup 2026-08-01 23:11) --
# Each override row becomes [-10%][<letter> <pct>% button][+10%][readout].
# The stock ActionSlider is NOT unbound: it is HIDDEN and kept as the single
# wiring point -- qtpyvcp bindWidget connects slider.valueChanged to the real
# action (qtpyvcp/actions/__init__.py:104-105; machine.max-velocity.set /
# machine.feed-override.set / spindle.override / machine.rapid-override.set),
# and the action's bindOk feeds STATUS changes back via setSliderPosition
# (machine_actions.py:501/569/637, spindle_actions.py:363). So slider.value()
# always tracks NML truth (MPG pendant and program overrides included) and
# slider.setValue() IS the stock set path, clamped to the stock INI ranges
# bindOk installed (F 0..MAX_FEED_OVERRIDE*100=150, S MIN..MAX_SPINDLE_
# OVERRIDE*100=20..200, R 0..100, V 0..[TRAJ]MAX_LINEAR_VELOCITY*60=20000
# mm/min). The center widget is the STOCK "X 100%" ActionButton MOVED into
# the cluster: its stock *.reset action (=100%) is untouched, only its text
# goes live. The right readout is the STOCK StatusLabel moved to the slot the
# center button vacated -- its rules keep painting stock semantics (V mm/min,
# F/S/R percent).
#
# Pure Qt ON PURPOSE (imports inside the function, no qtpyvcp/linuxcnc/NML):
# the offscreen bench test extracts and runs THIS function against a replica
# grid without ever touching the live channels. ALL-OR-NOTHING per rule 14 +
# the reverted 2026-08-01 cluster attempt: phase 1 validates EVERY widget and
# layout lookup and aborts with the stock rows fully intact on any miss;
# phase 2 mutations are journaled and rolled back on any exception. The
# layout is verified to be a QGridLayout and only addWidget(row, col) /
# removeWidget are called on it (QGridLayout has NO insertWidget; only the
# cluster's own QHBoxLayout gets insertWidget). Loud log lines either way.
def build_override_clusters(win, log, is_locked=None):
    """Rebuild the V/F/S/R override rows as [-10%][center][+10%][readout].

    win: widget tree root (PB main window). log: logger. is_locked:
    callable, the same UI-lock gate stock ActionSlider consults
    (qtpyvcp STATUS.isLocked); None disables the check (bench test).
    Returns {key: row dict} on success, None on abort (stock intact).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QPushButton,
                                   QSizePolicy, QWidget)

    # key, slider, right readout, center reset button, letter, percent base
    # (slider units per 100%: None = slider.maximum() -- the V slider is in
    # mm/min with max = 100%; 100 = slider value IS percent for F/S/R).
    rows_spec = (
        ('v', 'max_velocity_slider', 'max_vel_slider',
         'max_velocity_to_100_button', 'V', None),
        ('f', 'feed_override_slider', 'feed_override_status',
         'feed_override_to_100_button', 'F', 100),
        ('s', 'spindle_override_slider', 'spindle_override_status',
         'spindle_override_to_100_button', 'S', 100),
        ('r', 'rapid_override_slider', 'rapid_override_status',
         'rapid_override_to_100_button', 'R', 100),
    )

    def abort(reason):
        log.error('OVERRIDE CLUSTER ABORT -- stock sliders left intact: %s',
                  reason)
        return None

    # ---- phase 1: validate EVERY lookup, mutate NOTHING -------------------
    frame = win.findChild(QWidget, 'main_override_tool_qframe')
    if frame is None:
        return abort("frame 'main_override_tool_qframe' not found")
    grid = frame.layout()
    if not isinstance(grid, QGridLayout):
        return abort('main_override_tool_qframe layout is %s, expected '
                     'QGridLayout' % type(grid).__name__)
    plan = []
    for key, s_name, r_name, c_name, letter, pct_base in rows_spec:
        slider = win.findChild(QWidget, s_name)
        readout = win.findChild(QWidget, r_name)
        center = win.findChild(QWidget, c_name)
        for name, w in ((s_name, slider), (r_name, readout),
                        (c_name, center)):
            if w is None:
                return abort("widget '%s' not found" % name)
            if grid.indexOf(w) < 0:
                return abort("widget '%s' is not in the override grid" % name)
        if not (hasattr(slider, 'setValue') and hasattr(slider, 'maximum')
                and hasattr(slider, 'valueChanged')):
            return abort("'%s' is not a slider (%s)"
                         % (s_name, type(slider).__name__))
        srow, scol = grid.getItemPosition(grid.indexOf(slider))[:2]
        rrow, rcol = grid.getItemPosition(grid.indexOf(readout))[:2]
        crow, ccol = grid.getItemPosition(grid.indexOf(center))[:2]
        if not (srow == rrow == crow):
            return abort('%s row mismatch: slider r%d, readout r%d, '
                         'center r%d' % (letter, srow, rrow, crow))
        if not (scol < rcol < ccol):
            return abort('%s column order unexpected: slider c%d, readout '
                         'c%d, center c%d' % (letter, scol, rcol, ccol))
        base = slider.maximum() if pct_base is None else pct_base
        if base <= 0 or slider.maximum() <= slider.minimum():
            return abort("'%s' range %d..%d unusable (action bindOk never "
                         'ranged it?)' % (s_name, slider.minimum(),
                                          slider.maximum()))
        if pct_base is None and slider.maximum() < 1000:
            return abort("'%s' max %d is not a mm/min range -- "
                         'machine.max-velocity.set bindOk missed'
                         % (s_name, slider.maximum()))
        plan.append({'key': key, 'letter': letter, 'slider': slider,
                     'readout': readout, 'center': center, 'row': srow,
                     'scol': scol, 'rcol': rcol, 'ccol': ccol,
                     'base': float(base)})
        log.info('OVR %s validated: %s (r%d c%d, range %d..%d), %s (c%d), '
                 '%s (c%d)', letter, s_name, srow, scol, slider.minimum(),
                 slider.maximum(), r_name, rcol, c_name, ccol)

    # ---- phase 2: journaled mutation, full rollback on ANY exception ------
    journal = []

    def rollback():
        try:
            for tag, p in reversed(journal):
                if tag == 'wired':
                    p['slider'].valueChanged.disconnect(p['center_text'])
                    p['center'].setText(p['center_text0'])
                elif tag == 'readout_moved':
                    grid.removeWidget(p['readout'])
                    grid.addWidget(p['readout'], p['row'], p['rcol'])
                elif tag == 'center_moved':
                    p['hbox'].removeWidget(p['center'])
                    p['center'].setMaximumSize(*p['center_maxsize'])
                    p['center'].setSizePolicy(p['center_policy'])
                    grid.addWidget(p['center'], p['row'], p['ccol'])
                elif tag == 'cluster_in':
                    grid.removeWidget(p['cluster'])
                    p['cluster'].hide()
                    p['cluster'].deleteLater()
                elif tag == 'slider_out':
                    grid.addWidget(p['slider'], p['row'], p['scol'])
                    p['slider'].show()
            log.error('OVERRIDE CLUSTER rolled back %d ops -- stock rows '
                      'restored', len(journal))
        except Exception:
            log.exception('OVERRIDE CLUSTER ROLLBACK FAILED -- slider area '
                          'may be inconsistent until next launch')

    try:
        result = {}
        for p in plan:
            slider, center, readout = p['slider'], p['center'], p['readout']
            key, letter, base = p['key'], p['letter'], p['base']

            slider.hide()
            grid.removeWidget(slider)
            journal.append(('slider_out', p))

            cluster = QWidget(frame)
            cluster.setObjectName('ovr_%s_cluster' % key)
            p['cluster'] = cluster
            hbox = QHBoxLayout(cluster)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(10)
            p['hbox'] = hbox
            minus = QPushButton('-10%', cluster)
            plus = QPushButton('+10%', cluster)
            for b, n in ((minus, 'ovr_%s_minus' % key),
                         (plus, 'ovr_%s_plus' % key)):
                b.setObjectName(n)
                b.setStyleSheet(
                    'QPushButton { font: 14pt "Probe Basic Bebas Mono"; }')
                b.setMinimumSize(65, 40)
                b.setMaximumHeight(40)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setFocusPolicy(Qt.NoFocus)
            hbox.addWidget(minus, 1)
            hbox.addWidget(plus, 1)
            # spans the slider's column through the old readout column
            grid.addWidget(cluster, p['row'], p['scol'], 1,
                           p['rcol'] - p['scol'] + 1)
            journal.append(('cluster_in', p))

            p['center_maxsize'] = (center.maximumWidth(),
                                   center.maximumHeight())
            p['center_policy'] = center.sizePolicy()
            grid.removeWidget(center)
            center.setMaximumSize(16777215, 40)
            center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            hbox.insertWidget(1, center, 2)  # QHBoxLayout HAS insertWidget
            journal.append(('center_moved', p))

            grid.removeWidget(readout)
            grid.addWidget(readout, p['row'], p['ccol'])
            journal.append(('readout_moved', p))

            step = int(round(base * 10.0 / 100.0))  # 10 percentage points

            def center_text(val, letter=letter, base=base, center=center):
                center.setText('%s %.0f%%' % (letter, val * 100.0 / base))

            def on_step(sign, letter=letter, slider=slider, step=step,
                        base=base):
                if is_locked is not None and is_locked():
                    log.info('OVR %s %+d%% ignored: UI locked', letter,
                             sign * 10)
                    return
                if not slider.isEnabled():
                    log.info('OVR %s %+d%% refused: stock gate disabled '
                             '(machine off / override disabled)', letter,
                             sign * 10)
                    return
                old = slider.value()
                slider.setValue(old + sign * step)  # QSlider clamps to range
                new = slider.value()
                log.info('OVR %s: %d -> %d slider units (%.0f%% -> %.0f%%) '
                         'via hidden stock slider action', letter, old, new,
                         old * 100.0 / base, new * 100.0 / base)

            minus.clicked.connect(lambda _=False, f=on_step: f(-1))
            plus.clicked.connect(lambda _=False, f=on_step: f(+1))
            p['center_text'] = center_text
            p['center_text0'] = center.text()
            slider.valueChanged.connect(center_text)
            journal.append(('wired', p))
            center_text(slider.value())

            result[key] = {'slider': slider, 'minus': minus, 'plus': plus,
                           'center': center, 'readout': readout,
                           'cluster': cluster, 'base': base, 'step': step}
            log.info('OVR %s row rebuilt: [-10%%][%s live][+10%%][%s] '
                     '(step %d slider units = 10 pct-pts; %s hidden, still '
                     'action-bound)', letter, center.objectName(),
                     readout.objectName(), step, slider.objectName())
        log.info('OVERRIDE CLUSTER: all %d rows rebuilt per operator mockup '
                 '2026-08-01 23:11', len(result))
        return result
    except Exception:
        log.exception('OVERRIDE CLUSTER build FAILED mid-mutation')
        rollback()
        return None


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        ui_path = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = load_runtime_ui(ui_path, self)
        self.setObjectName('ned_controls')

        self.btn = self.findChild(QWidget, 'btn_toolprobe')
        self._air = False
        self._up = False
        self._stat = None

        try:
            self.comp = qhal.getComponent('ned-tab')
            self.comp.addPin('toolprobe-cmd', 'bit', 'out')
            self.comp.addPin('anon-load-out', 'bit', 'out')
            # the slot the operator clicks on the increment row; -1 until
            # they actually click (the pendant ignores the startup value)
            self.comp.addPin('inc-set-out', 's32', 'out')
            try:
                self.comp.getPin('inc-set-out').value = -1
            except Exception:
                pass

            # HEAD BUSY (brain.head-busy): TRUE from the moment the brain
            # arms ini.N.home/home_offset until POSITIVE confirmation that
            # every head joint is back at HOME_IDLE with no read, verify or
            # owed pin-wipe outstanding. stat.joint[j]['homing'] is NOT a
            # substitute -- on a zero-travel declare it can rise and fall
            # between two 500 ms polls, which is the window a second homing
            # click lands in.
            self.comp.addPin('head-busy-in', 'bit', 'in')
            # THE REAL MOTION LOCK (tool.mm.lock2 -> motion.jog-inhibit +
            # feed-inhibit). Covers BOTH reasons: a spindle/record mismatch
            # AND the tool table not being served. The GUI used to grey off
            # its own two Python flags, so with the table missing the HAL
            # was refusing motion while CYCLE START and MDI still looked
            # live -- a control that cannot act must not be clickable.
            self.comp.addPin('motion-lock-in', 'bit', 'in')
            # the TABLE half on its own: the startup gate needs to know
            # "table served", not "locked for one of two reasons"
            self.comp.addPin('table-ok-in', 'bit', 'in')
            # AIR PRESSURE, for the repurposed FLOOD button. This
            # machine has no flood (operator 2026-08-11: "make the
            # flood button an indicator for air pressure instead.
            # this machine has no flood"), and air is the one input
            # that silently prevents the machine leaving E-STOP --
            # air.permit = estop-released AND air-ok-debounced.
            # RAW is shown, not debounced: the operator is looking at
            # this while poking the switch, and a 0.5 s on-delay makes
            # a good tap look like nothing happened.
            # MPG ZERO GESTURE: double-tap + hold + 100 detents on the wheel
            # (ned_pendant.zero-axis-out). Zeroes whatever axis the wheel has
            # selected -- replaces the jog-speed slider the operator never used.
            self.comp.addPin('zero-axis-in', 'bit', 'in')
            # WHICH axis: not the live MPG selection. The first tap of the
            # double-tap already advanced it, so the pendant sends the axis
            # the operator was actually on.
            self.comp.addPin('zero-axis-idx-in', 's32', 'in')
            self.comp.addPin('air-ok-in', 'bit', 'in')
            self.comp.addPin('probe-up-in', 'bit', 'in')
            # the pendant's SLOT INDEX, never its value: the row is
            # relabelled per axis, so only the slot is comparable
            self.comp.addPin('inc-index-in', 's32', 'in')
            # axis lives HERE, not on the DRO module: PB loads user DROs
            # DEFERRED (after the UI settles = AFTER postgui), so a net onto a
            # DRO-owned pin kills postgui ("Pin 'ned-dro.axis-in' does not
            # exist"). User tabs load synchronously -> this pin exists in time;
            # the value is forwarded to the DRO widget in Qt (_on_axis).
            self.comp.addPin('axis-in', 's32', 'in')
            self.comp.addPin('jogspeed-in', 'float', 'in')
            self.comp.addPin('homeall-out', 'bit', 'out')
            self.comp.addPin('lock-a-out', 'bit', 'out')
            self.comp.addPin('lock-c-out', 'bit', 'out')
            # per-axis MPG locks for the linears too (operator 2026-08-06:
            # DRO single-click = lock). MPG-scope only: typed moves and
            # presets on XYZ are NOT gated by these.
            self.comp.addPin('lock-x-out', 'bit', 'out')
            self.comp.addPin('lock-y-out', 'bit', 'out')
            self.comp.addPin('lock-z-out', 'bit', 'out')
            # per-axis head REF (REF A / REF C buttons): pulse -> ned_brain
            # runs unhome -> fresh read -> home THAT joint only
            self.comp.addPin('refa-out', 'bit', 'out')
            self.comp.addPin('refc-out', 'bit', 'out')
            # Z JOG CLAMP: the DIRECTIONAL gate (jogblock.z.lim-neg) reads
            # these. Soft-limit-only stranded the machine when Z landed a few
            # tens of um past the floor -- LinuxCNC then refuses teleop jogs
            # in BOTH directions. jogblock only swallows DOWN detents.
            self.comp.addPin('zclamp-enable', 'bit', 'out')
            self.comp.addPin('zclamp-low', 'float', 'out')
            # the step ACTUALLY in force (jogblock's ladder output, mm/detent)
            self.comp.addPin('stepmm-in', 'float', 'in')
            # HQD S2 tool-released sensor (7I84 TB2-16 *70 -> sig-tool-released).
            # LOAD SPINDLE is meaningless unless the drawbar is actually OPEN.
            self.comp.addPin('drawbar-released-in', 'bit', 'in')
            # Tool record vs iron, computed in HAL every servo cycle.
            #   unrecorded = iron holds a tool, logic thinks empty
            #   phantom    = logic claims a tool, iron holds none
            self.comp.addPin('tool-unrecorded-in', 'bit', 'in')
            self.comp.addPin('tool-phantom-in', 'bit', 'in')
            self.comp.addPin('seq-active-out', 'bit', 'out')
            self.comp.addPin('seq-hb-out', 'u32', 'out')
            self.comp.ready()
            # A AND C START LOCKED, ALWAYS (operator 2026-08-04). A head
            # axis is the one thing a stray wheel nudge can wreck silently --
            # it moves the tool without moving a coordinate anyone is
            # watching -- so the safe default is OFF THE WHEEL, and the
            # operator unlocks deliberately when they want to turn it.
            #
            # addPin creates the pin but does not define its value, and
            # nothing wrote it at startup, so _ac_locked said unlocked while
            # the HAL pin read TRUE and the pendant obeys the PIN. That
            # disagreement -- not the lock itself -- was the original bug;
            # first fix set both to UNLOCKED, which was the wrong default.
            # set_ac_lock() writes the pin AND the dict, so they start in
            # agreement either way.
            for _ax in ('a', 'c'):
                try:
                    self.set_ac_lock(_ax, True)
                except Exception:
                    LOG.exception('startup: could not LOCK %s -- the wheel '
                                  'can still move it', _ax.upper())
            self.comp.addListener('head-busy-in', self._on_head_busy)
            self.comp.addListener('zero-axis-in', self._on_mpg_zero)
            self.comp.addListener('motion-lock-in', self._on_motion_lock)
            self.comp.addListener('air-ok-in', self._on_air)
            self.comp.addListener('drawbar-released-in', self._on_drawbar)
            self.comp.addListener('tool-unrecorded-in', self._on_tool_unrecorded)
            self.comp.addListener('tool-phantom-in', self._on_tool_phantom)
            self.comp.addListener('probe-up-in', self._on_up)
            self.comp.addListener('inc-index-in', self._on_inc_index)
            self.comp.addListener('axis-in', self._on_axis)
            self.comp.addListener('jogspeed-in', self._on_jogspeed)
            LOG.info('ned-tab HAL component ready')
        except Exception as e:
            self.comp = None
            LOG.error('ned-tab HAL component failed: %s', e)

        if self.btn is not None:
            self.btn.clicked.connect(self._click)
            self._style()
        else:
            LOG.info('TOOLPROBE button absent from ned_controls.ui '
                     '(probe served by PB stock controls)')

        # JOG & PRESETS panel -- the visible NED tab content. All widgets
        # live in ned_controls.ui (no runtime layout surgery); wire + count
        # them LOUDLY here.
        self._jog_speed = 'medium'
        self._jog_wire()
        # 6000 ms like _number_badges: a singleShot(0) reparent during
        # window construction spun Qt at 95% CPU and PB never finished
        # booting (2026-08-02 10:08 launch)
        QTimer.singleShot(6000, self._jog_page_takeover)
        # UNITS IN/MM buttons on the SETTINGS tab (operator 2026-08-02
        # 13:0x: PB has no units control; G20/G21 is the only path)
        QTimer.singleShot(6000, self._units_panel_install)
        # one-shot geometry dump: global click coords of every jp_/units
        # widget, for the click-test harness (and future ones)
        QTimer.singleShot(9000, self._jp_dump_coords)

        # UNLOAD SPINDLE (core button remove_tool_2): 5 s countdown, second
        # click cancels; then the ned unload_spindle sub (real drawbar release
        # + PB software unload). Deterministic MDI like the zero buttons.
        # Per-button: there are TWO unload buttons (TOOL tab + ATC tab) and
        # one slot cannot track both.
        self._unload_pend = {}
        QTimer.singleShot(0, self._wire_unload)

        # LOAD SPINDLE (core SubCallButtons load_spindle_button[_2]): same
        # 5 s countdown, second click cancels (operator 2026-08-02 13:5x
        # "load spindle should also have a 5 second countdown"). The
        # countdown then calls the button's OWN callSub() -- PB already
        # resolves the .ngc and pulls the tool number from the paired
        # load_spindle_tool_number[_2] field, so none of that is duplicated.
        self._load_pend = {}
        self._btn_labels = {}
        QTimer.singleShot(0, self._wire_load)
        QTimer.singleShot(0, self._relabel_buttons)
        # after the UI settles -- it inserts into a core layout it must find
        QTimer.singleShot(1500, self._build_declaration)
        QTimer.singleShot(1600, self._hide_spare_mdi)
        QTimer.singleShot(1700, self._start_homing_gate)
        QTimer.singleShot(1800, self._build_rack_table)
        QTimer.singleShot(1900, self._build_rotary_probe_tab)
        QTimer.singleShot(2100, self._wire_air_button)
        QTimer.singleShot(2000, self._init_tool_safety)
        # -xyzab only (self-checks the env and returns immediately otherwise).
        QTimer.singleShot(4000, self.xyzab_launch_start)
        if ROT == 'b':
            QTimer.singleShot(7000, self._xyzab_relabel_gui)
            # subtabs land at 6.5 s and the DRO is deferred further;
            # a widget that appears after the walk would keep the
            # design-time letter, so sweep again once it is all up.
            QTimer.singleShot(14000, self._xyzab_relabel_gui)

        # SPINDLE SECTION (operator 2026-08-01): spindle load meter ->
        # chip-load-per-flute PLACEHOLDER; left RPM readout -> live
        # COMMANDED speed (M3/M4 x override); right stays the stock S-word
        # display (baseline: 9000 in MAN, program S in MDI/AUTO).
        QTimer.singleShot(0, self._restyle_spindle_section)

        # OVERRIDE CLUSTER (operator mockup 2026-08-01 23:11): the V/F/S/R
        # slider rows become [-10%][<letter> <pct>% = click resets 100%]
        # [+10%][readout]. Stock sliders stay alive HIDDEN as the action
        # wiring (pendant/program overrides keep tracking); the stock
        # to-100 ActionButtons become the live center displays. All-or-
        # nothing with journaled rollback -- see build_override_clusters.
        self._ovr_rows = None
        QTimer.singleShot(0, self._wire_override_cluster)

        # SPINDLE FWD/REV: "Check" 3 s countdown before the spin (operator
        # 2026-08-01: the iron S1 spin gate is gone -- S1 cannot tell EMPTY
        # from tool-resting-unclamped, so the OPERATOR checks; press ->
        # button reads "Check N" -> spin at 0; second press cancels).
        self._spin_pend = {}
        QTimer.singleShot(0, self._wire_spindle_check)

        # The visible NED tab page is BACK (2026-08-01 evening): its content
        # is the JOG & PRESETS panel ("empty/removed" era over -- the earlier
        # _remove_own_tab_page call is deleted). PB's load_user_tabs adds this
        # widget to tabWidget synchronously at window construction; nothing to
        # do here but say so, loudly.
        LOG.info('NED tab page kept: JOG & PRESETS panel is its content')

        # NED CONTROLS sub-tabs (operator 2026-08-02). The jog panel reparents
        # into the stock JOG page at +6 s, leaving this page empty -- so the
        # sub-tab notebook goes here. First tab: JOG, holding the Z CLAMP.
        self._zclamp_on = False
        self._zclamp_low = None
        self._zclamp_widgets = {}
        QTimer.singleShot(6500, self._build_subtabs)

        # GUI NUMBERING: OFF by default (operator 2026-08-02: "i need all
        # the numbers gone. cos they hide shit i need" -- badges covered
        # the ATC RACK SETUP fields). To regenerate gui_map.txt for a GUI
        # work session: `touch ~/Documents/ned/gui_badges_on` and relaunch;
        # remove the file to go clean again.
        if os.path.exists('/home/brains/Documents/ned/gui_badges_on'):
            QTimer.singleShot(6000, self._number_badges)
        else:
            LOG.info('GUI numbering badges OFF (create ned/gui_badges_on to enable)')

        # Qt/NML housekeeping only -- NO HAL in this timer.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

        # WCS PUBLISH -- its OWN timer, deliberately not _tick (2026-08-10).
        # Hosting it in _tick made it impossible to tell whether the code
        # was running at all: a call counter there logged three calls while
        # other _tick output kept flowing. One timer, one job, one log line
        # per outcome, so the next boot explains itself.
        self._wcs_timer = QTimer(self)
        self._wcs_timer.timeout.connect(self._publish_wcs_once)
        self._wcs_timer.start(1000)

    # ---- NED CONTROLS sub-tabs: JOG / CLAMP ------------------------------

    ZCLAMP_ON_QSS = ('background-color: rgb(40,170,70); color: white; '
                     'font-weight: bold; border: 2px solid rgb(20,90,40); '
                     'border-radius: 5px;')
    # "nothing if Disabled" per the operator -- no colour, but the label has
    # to be legible on PB's dark panel, so plain light text on the default bar
    ZCLAMP_OFF_QSS = 'color: rgb(220,220,220); border-radius: 5px;'

    def _build_subtabs(self):
        """JOG sub-tab with the Z CLAMP section (operator spec 2026-08-02):
        enable/disable button (GREEN when enabled, plain when disabled) and
        one machine-coordinate number, Zlow. While enabled the MPG cannot jog
        Z below Zlow. If Z is ever outside the clamp while enabled that is an
        estop-class fault: loud error and the clamp reverts to DISABLED."""
        try:
            from PySide6.QtWidgets import (QTabWidget, QWidget, QVBoxLayout,
                                           QHBoxLayout, QGroupBox, QLabel,
                                           QPushButton, QLineEdit,
                                           QScrollArea, QFrame, QSizePolicy)
            from PySide6.QtWidgets import QWidget as _QW
            root = self.findChild(_QW, 'ned_controls_root') or self
            lay = root.layout()
            if lay is None:
                LOG.error('SUBTABS: ned_controls_root has no layout -- not built')
                return
            tabs = QTabWidget()
            tabs.setObjectName('ned_subtabs')
            # HARD CAP -- a user tab must never resize the main window.
            # 2026-08-03: this method runs on a 6.5 s singleShot, so PB came
            # up at the correct 1920x1200 and then GREW past the monitor the
            # moment the CALIBRATION grid was inserted: its fixed 470+560
            # columns and ~1150 px stack became a minimumSizeHint that
            # propagated root -> stacked page -> QMainWindow, shoving PB's own
            # bottom strip (MAIN/FILE/ATC + the DRO row) off the bottom edge.
            # Qt honours a child's minimum over the screen; nothing clips it.
            # PB's core pages never do this because they are .ui pages sized
            # in Designer. Ignored policy + a zero minimum is the equivalent
            # for a Python-built tab: the page gets whatever the stack gives
            # it, and the content adapts.
            for _w in (tabs, root, self):
                _w.setMinimumSize(0, 0)
                _w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            jog_page = QWidget()
            jl = QVBoxLayout(jog_page)
            jl.setContentsMargins(8, 8, 8, 8)

            box = QGroupBox('CLAMP')
            box.setObjectName('zclamp_box')
            bl = QVBoxLayout(box)

            btn = QPushButton('DISABLED')
            btn.setObjectName('zclamp_enable_btn')
            btn.setCheckable(True)
            btn.setMinimumHeight(46)
            btn.setStyleSheet(self.ZCLAMP_OFF_QSS)
            btn.clicked.connect(self._zclamp_toggle)
            bl.addWidget(btn)

            row = QHBoxLayout()
            lbl = QLabel('Zlow (machine)')
            edit = QLineEdit()
            edit.setObjectName('zclamp_low_input')
            edit.setPlaceholderText('e.g. -300.0')
            edit.setMinimumHeight(34)
            edit.editingFinished.connect(self._zclamp_low_changed)
            row.addWidget(lbl)
            row.addWidget(edit)
            bl.addLayout(row)

            note = QLabel('MPG jogging of Z is held between Zlow and the\n'
                          'machine Z ceiling. Jogging back UP always works.\n'
                          'Affects JOG only -- g-code is untouched.')
            note.setStyleSheet('color: rgb(160,160,160); font: 9pt;')
            bl.addWidget(note)

            status = QLabel('')
            status.setObjectName('zclamp_status')
            status.setWordWrap(True)
            bl.addWidget(status)
            bl.addStretch(1)

            jl.addWidget(box)

            jl.addStretch(1)
            tabs.addTab(jog_page, 'JOG')

            # CALIBRATION tab. THREE COLUMNS, no scroll area: the page is
            # landscape and the content was portrait, so ~1150 px of stack sat
            # in an ~880 px viewport with ~900 px of width unused. On a touch
            # panel a scroll area is hostile -- a 5 mm finger drift turns a
            # press into a scroll and the widget under button-up is not the
            # one under button-down. Every column and box is FIXED size, so
            # nothing reflows under a finger. Design review 2026-08-03.
            from PySide6.QtWidgets import QGridLayout, QPlainTextEdit
            from PySide6.QtGui import QFont
            cal_page = QWidget()
            cg = QGridLayout(cal_page)
            cg.setContentsMargins(8, 8, 8, 8)
            cg.setSpacing(8)

            # ---- column 0: ACTIONS, in step order -----------------------
            col0 = QWidget()
            col0.setFixedWidth(470)
            c0 = QVBoxLayout(col0)
            c0.setContentsMargins(0, 0, 0, 0)
            c0.setSpacing(8)

            def _mkbox(title):
                bx = QGroupBox(title)
                bx.setStyleSheet(self.CAL_QSS_BOX)
                bl = QVBoxLayout(bx)
                bl.setContentsMargins(10, 10, 10, 10)
                bl.setSpacing(6)
                return bx, bl

            # PUCK toggle, on EVERY calibration page (operator 2026-08-05:
            # "in all calibration pages give me a button to send the puck up
            # and down. just a toggle"). There is no deployed sensor, so the
            # button carries the state it commanded -- and the 1.5 s dwell
            # is the only proof the pneumatics had time to act.
            self._puck_btns = []
            def _mkpuck():
                pb = QPushButton('PUCK UP')
                pb.setObjectName('ned_puck_toggle')
                pb.setCheckable(True)
                pb.setMinimumHeight(46)
                pb.setStyleSheet(self.CAL_QSS['pose'])
                pb.clicked.connect(lambda ck=False: self._puck_toggle(ck))
                self._puck_btns.append(pb)
                return pb

            b1, b1l = _mkbox('1   PUCK CENTRE')
            self._cal_btn = {}
            def _mkbtn(key, cap, cls, w=None):
                b = QPushButton(cap)
                b.setMinimumHeight(62)      # 15 mm at 3.71 px/mm -- gloved
                b.setStyleSheet(self.CAL_QSS[cls])
                b.clicked.connect(lambda _=False, k=key: self._cal_run(k))
                self._cal_btn[key] = b
                if w:
                    b.setFixedWidth(w)
                return b
            b1l.addWidget(_mkbtn('puck', 'START PUCK', 'measure'))
            c0.addWidget(b1)

            b2, b2l = _mkbox('2   A / C ZERO')
            # SET C REF is a PREREQUISITE for StartC, so it goes above them.
            # Its two-press protocol used to exist only in a tooltip, which a
            # touchscreen never shows -- it is on the face now and the label
            # tracks the state.
            r = QHBoxLayout(); r.setSpacing(8)
            r.addWidget(_mkbtn('a', 'START A', 'measure'))
            r.addWidget(_mkbtn('c', 'START C', 'measure'))
            b2l.addLayout(r)
            b2l.addWidget(_mkbtn('ac', 'START AC', 'measure'))
            r = QHBoxLayout(); r.setSpacing(8)
            for k, cap in (('goto', 'ZERO'), ('cleft', 'C LEFT'),
                           ('cright', 'C RIGHT')):
                r.addWidget(_mkbtn(k, cap, 'pose'))
            b2l.addLayout(r)
            # NO RECORD BUTTON. Banking is automatic and immediate -- an
            # improvement is banked on the spot, not held for a later press.
            # That IS the point of the exercise (operator 2026-08-03), and a
            # button reading "nothing to bank" was advertising a step that
            # does not exist.
            c0.addWidget(b2)

            b3, b3l = _mkbox('3   SHOULDER')
            # "SHOULDER   spindle empty" read as one garbled phrase. The
            # requirement belongs in the box, not jammed into the label.
            # LIVE INSTRUCTION, above the four buttons (operator
            # 2026-08-11: "should update instructions as each step
            # passes"). It is derived from the MACHINE STATE, not from
            # which button was last clicked: the chain spans jogging,
            # a tool change by hand and possibly a restart, and a
            # remembered click index would be wrong after any of them.
            # Read the numbers, say what is still missing.
            self._cal_next = QLabel('')
            self._cal_next.setWordWrap(True)
            self._cal_next.setStyleSheet(
                'color: rgb(255,205,60); font: 11pt "Probe Basic Bebas'
                ' Mono"; padding: 4px;')
            b3l.addWidget(self._cal_next)
            b3l.addWidget(_mkbtn('shoulder', 'FIND NOSE', 'measure'))
            # the rest of the reset, top to bottom in the order they
            # are pressed -- the sequence IS the instruction
            b3l.addWidget(_mkbtn('probeheight', 'SET PROBE HEIGHT',
                                 'measure'))
            b3l.addWidget(_mkbtn('storeresults', 'STORE RESULTS',
                                 'measure'))
            b3l.addWidget(_mkbtn('measureall', 'MEASURE ALL TOOLS',
                                 'measure'))
            c0.addWidget(b3)
            c0.addStretch(1)
            cg.addWidget(col0, 0, 0)

            # ---- column 1: NUMBERS, one grid so columns stay aligned -----
            col1 = QWidget()
            col1.setFixedWidth(560)
            gl = QGridLayout(col1)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setHorizontalSpacing(6)
            gl.setVerticalSpacing(3)
            row = 0
            self._cal_lockchip = QLabel('A ---   C ---')
            self._cal_lockchip.setStyleSheet(
                'color: #E6E6E6; font: bold 10pt;')
            gl.addWidget(self._cal_lockchip, row, 0)
            for cc, cap in ((1, 'CURRENT'), (2, 'PREVIOUS')):
                h = QLabel(cap)
                h.setStyleSheet('color: #E6E6E6; font: bold 10pt;')
                gl.addWidget(h, row, cc)
            row += 1
            self._cal_fields = {}

            def _section(txt):
                nonlocal row
                lb = QLabel(txt)
                lb.setStyleSheet('color: #FFD08A; font: bold 10pt; '
                                 'border-top: 1px solid #5A6466; '
                                 'padding-top: 5px; margin-top: 5px;')
                gl.addWidget(lb, row, 0, 1, 3)
                row += 1

            def _readout(key, lab, prev=True):
                nonlocal row
                lw = QLabel(lab)
                lw.setStyleSheet('color: #E6E6E6; font: 10pt;')
                gl.addWidget(lw, row, 0)
                cur = QLineEdit(); prv = QLineEdit()
                for e in (cur, prv):
                    e.setReadOnly(True)
                    e.setFont(QFont('DejaVu Sans Mono', 11))
                    e.setFixedHeight(30)
                e.setPlaceholderText('')
                cur.setStyleSheet(self.CAL_QSS['read'])
                prv.setStyleSheet(self.CAL_QSS['readprev'])
                cur.setPlaceholderText('--')
                prv.setPlaceholderText('--')
                gl.addWidget(cur, row, 1)
                if prev:
                    gl.addWidget(prv, row, 2)
                self._cal_fields[key] = (cur, prv)
                row += 1

            _section('MEASURED THIS RUN')
            _readout('3045', 'Centre X  mm')
            _readout('3046', 'Centre Y  mm')
            _readout('3047', 'Top Z  mm')
            _section('BANKED  --  RECORD WRITES THESE')
            _readout('3069', 'A zero  ENC')
            _readout('3070', 'C zero  ENC')
            _section('TAUGHT C REF  (sticky across runs)')
            _readout('3061', 'C ref X  mm', prev=False)
            _readout('3058', 'C ref dy  mm', prev=False)
            _readout('3060', 'C ref depth  mm', prev=False)
            # CLEAR belongs beside the numbers it clears, not among the Start
            # buttons -- full width next to START A was asking to be hit by
            # accident. Small, off to the side, and it counts down 5 s before
            # it acts. Operator 2026-08-03.
            bclr = QPushButton('CLEAR C REF')
            bclr.setFixedHeight(34)
            bclr.setFixedWidth(150)
            bclr.setStyleSheet(self.CAL_QSS['clear'])
            bclr.clicked.connect(self._cal_clear_click)
            self._cal_btn['clear'] = bclr
            gl.addWidget(bclr, row, 1)
            row += 1
            # THE PACKET THAT CROSSES TO PROBE BASIC. Stored as parameters
            # and shown here so it is visible and verifiable in one place,
            # rather than being literals buried in the subroutine (operator
            # 2026-08-03). The first three are inputs the operator can reason
            # about; the last four are what PB actually ends up holding.
            _section('SENT TO PROBE BASIC')
            _readout('3076', 'Z clearance  mm', prev=False)
            _readout('3078', 'X offset  mm', prev=False)
            _readout('3077', 'plunge used  mm', prev=False)
            _readout('5181', 'G30 X  mm', prev=False)
            _readout('5182', 'G30 Y  mm', prev=False)
            _readout('5183', 'G30 Z  mm', prev=False)
            _readout('3010', 'SHOULDER  mm', prev=False)
            _section('DELTAS')
            # built ONCE at final geometry with dash placeholders, so a row
            # appearing mid-run cannot move anything under a finger
            self._cal_delta_rows = []
            for name, bkey, akey, unit in (
                    ('StartA   dY', '3050', '3051', 'mm'),
                    ('StartC   dX', '3055', '3056', 'mm'),
                    ('StartAC  A dY', '3062', '3063', 'mm'),
                    ('StartAC  C dX', '3064', '3065', 'mm')):
                w = QLabel('%-14s      --          --' % name)
                w.setFont(QFont('DejaVu Sans Mono', 10))
                w.setFixedHeight(30)
                w.setProperty('verdict', 'none')
                w.setStyleSheet(self.CAL_QSS['delta'])
                gl.addWidget(w, row, 0, 1, 3)
                row += 1
                self._cal_delta_rows.append((w, name, bkey, akey, unit))
            gl.setRowStretch(row, 1)
            cg.addWidget(col1, 0, 1)

            # ---- column 2: LIVE commentary ------------------------------
            self._cal_log = QPlainTextEdit()
            self._cal_log.setReadOnly(True)
            self._cal_log.setMaximumBlockCount(400)
            self._cal_log.setFont(QFont('DejaVu Sans Mono', 10))
            self._cal_log.setStyleSheet(self.CAL_QSS['log'])
            self._cal_log.setPlaceholderText(
                'Running commentary appears here once a cycle starts.')
            cg.addWidget(self._cal_log, 0, 2)
            cg.setColumnStretch(2, 1)
            self._cal_log_pos = None
            t2 = QTimer(self)
            t2.timeout.connect(self._cal_log_poll)
            t2.start(500)
            self._cal_log_timer = t2

            self._cal_var_timer = QTimer(self)
            self._cal_var_timer.timeout.connect(self._cal_fields_refresh)
            if self.CAL_REFRESH_ENABLED:
                self._cal_var_timer.start(2000)
                LOG.info('CAL: var-file refresh timer STARTED (2 s)')
            self._cal_delta_base = self._read_vars(
                ('3050', '3051', '3055', '3056',
                 '3062', '3063', '3064', '3065'))
            c0.addWidget(_mkpuck())
            tabs.addTab(cal_page, 'AC CALIBRATION')

            # ---- RACK CALIBRATION: its own page beside AC CALIBRATION ----
            rack_page = QWidget()
            rl = QVBoxLayout(rack_page)
            rl.setContentsMargins(8, 8, 8, 8)
            rbox, rbl = _mkbox('RACK CALIBRATION  --  P1..P14 fork centres')
            rbtn = QPushButton('START RACK CAL')
            rbtn.setObjectName('cal_rack_btn')
            rbtn.setMinimumHeight(62)
            rbtn.setStyleSheet(self.CAL_QSS.get('go', ''))
            rbtn.clicked.connect(lambda _=False: self._cal_run('rack'))
            self._cal_btn['rack'] = rbtn
            rbl.addWidget(rbtn)
            rnote = QLabel('Empty spindle, holders energized. Park the '
                           'spindle CENTRED 10 mm above the P1 holder top -- '
                           'that pose is the datum. Plunges 45 over the '
                           'taper, 4-side centres, verifies at 60, then '
                           'steps Y- to the next fork. Every descent is a '
                           'probe move; wrong anything = loud abort.')
            rnote.setWordWrap(True)
            rnote.setStyleSheet('color: rgb(160,160,160); font: 10pt;')
            rbl.addWidget(rnote)
            rl.addWidget(rbox)
            rl.addStretch(1)
            rbl.addWidget(_mkpuck())
            tabs.addTab(rack_page, 'RACK CALIBRATION')
            # ---- TCP CALIBRATION: the A pivot length, ONE button ---------
            # Operator 2026-08-05. Two probes of the SAME puck face at two
            # different A angles give the pivot length outright:
            #     z(A) = const + dL * cos(A)      dL = L_true - L_in_force
            #     dL   = (z1 - z2) / (cos A1 - cos A2)
            # The rod carries a NEEDLE POINT on the spindle axis, so the
            # contact IS the tool tip at any tilt and no rod-radius term
            # enters. In identity kins the pivot in force is 0, so a pair
            # yields L ABSOLUTELY -- no starting guess to correct. In
            # tool-tip kins it yields the CORRECTION to the pin, and dZ is
            # the residual that shrinks as L converges.
            # This tab NEVER touches the A/C locks. The operator's own
            # rotation between the two touches is exactly what guarantees
            # the needle still lands on the puck.
            from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem,
                                           QHeaderView, QAbstractItemView)
            tcp_page = QWidget()
            tpg = QGridLayout(tcp_page)
            tpg.setContentsMargins(8, 8, 8, 8)
            tpg.setSpacing(8)

            tcol = QWidget()
            tcol.setFixedWidth(470)
            tc = QVBoxLayout(tcol)
            tc.setContentsMargins(0, 0, 0, 0)
            tc.setSpacing(8)

            tbox, tbl = _mkbox('A PIVOT')
            abtn = QPushButton('AUTO CONVERGE')
            abtn.setObjectName('tcp_auto_btn')
            abtn.setMinimumHeight(90)
            abtn.setStyleSheet(self.CAL_QSS['measure'])
            abtn.clicked.connect(lambda _=False: self._tcp_auto_press())
            self._tcp_auto_btn = abtn
            tbl.addWidget(abtn)

            pbtn = QPushButton('PID TRACKING')
            pbtn.setObjectName('tcp_pidt_btn')
            pbtn.setMinimumHeight(52)
            pbtn.setStyleSheet(self.CAL_QSS['pose'])
            pbtn.clicked.connect(lambda _=False: self._pidt_press())
            self._pidt_btn = pbtn
            tbl.addWidget(pbtn)

            tstat = QLabel('Park over the puck. AUTO CONVERGE.')
            tstat.setObjectName('tcp_cal_status')
            tstat.setWordWrap(True)
            tstat.setStyleSheet('color: rgb(200,208,205); font: 11pt;')
            self._tcp_status = tstat
            tbl.addWidget(tstat)

            tres = QLabel('L = ---')
            tres.setObjectName('tcp_cal_result')
            tres.setStyleSheet('color: #78DC78; font: bold 20pt;')
            self._tcp_result = tres
            tbl.addWidget(tres)
            # COMMIT: the ONLY thing that writes head_pivot.inc. The sweep
            # applies to the LIVE pin; this button makes it survive the
            # relaunch (param files change only on the operator's explicit
            # action -- this press IS that action).
            cbtn = QPushButton('SAVE PIVOT TO MACHINE')
            cbtn.setObjectName('tcp_commit_btn')
            cbtn.setMinimumHeight(52)
            cbtn.setStyleSheet(self.CAL_QSS['commit'])
            cbtn.clicked.connect(lambda _=False: self._tcp_commit())
            tbl.addWidget(cbtn)
            tc.addWidget(tbox)

            tc.addStretch(1)

            hbox, hbl = _mkbox('IMPROVEMENTS')
            # TIP TERMS (operator 2026-08-05: "what i expect it to be vs
            # where it actually is in terms of the tip"). With a correct
            # pivot the tip touches at the SAME Z at every angle, so:
            #   EXPECT = the reference touch Z (where it should land)
            #   ACTUAL = where it landed at this tilt
            #   MISS   = actual - expect (0 when calibrated; + = tip high)
            # L is the pivot this pair solves to.
            tbla = QTableWidget(0, 6)
            tbla.setObjectName('tcp_cal_table')
            tbla.setHorizontalHeaderLabels(
                ['#', 'A', 'EXPECT Z', 'ACTUAL Z', 'MISS', 'L (mm)'])
            tbla.verticalHeader().setVisible(False)
            tbla.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tbla.setSelectionMode(QAbstractItemView.NoSelection)
            tbla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbla.setStyleSheet(self.CAL_QSS.get('log', ''))
            self._tcp_table = tbla
            hbl.addWidget(tbla)

            xbtn = QPushButton('CLEAR DATA')
            xbtn.setObjectName('tcp_clear_btn')
            xbtn.setMinimumHeight(40)
            xbtn.setStyleSheet(self.CAL_QSS['clear'])
            xbtn.clicked.connect(lambda _=False: self._tcp_clear_data())
            hbl.addWidget(xbtn)

            tpg.addWidget(tcol, 0, 0)
            tpg.addWidget(hbox, 0, 1)
            tpg.setColumnStretch(1, 1)
            tbl.addWidget(_mkpuck())
            tabs.addTab(tcp_page, 'TCP CALIBRATION')
            self._tcp_state = 'idle'
            self._tcp_pts = []
            self._tcp_load_hist()
            _tt = QTimer(self)
            _tt.timeout.connect(self._tcp_tick)
            _tt.start(500)
            self._tcp_timer = _tt
            LOG.info('SUBTABS: TCP CALIBRATION tab built (kins=%s, '
                     'pivot in force %.3f)', *self._tcp_kins())

            self._cal_tab_index = tabs.indexOf(cal_page)
            tabs.currentChanged.connect(self._cal_tab_changed)
            cstat = QLabel('')
            self._cal_status = cstat
            # The columns are fixed by design (touch panel: nothing may
            # reflow under a finger -- design review 2026-08-03), so when the
            # page is smaller than the content something has to give. It
            # scrolls INSIDE this viewport instead of growing the window.
            # When the page is big enough no scrollbar appears at all, so the
            # touch behaviour is unchanged in the normal case.
            scroll = QScrollArea()
            scroll.setObjectName('ned_subtabs_scroll')
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setMinimumSize(0, 0)
            scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            scroll.setWidget(tabs)
            lay.addWidget(scroll)

            self._zclamp_widgets = {'btn': btn, 'edit': edit, 'status': status}
            # the machine ceiling is the existing Z max soft limit -- the
            # operator gives ONE number (the floor); the top is what the
            # machine already enforces.
            self._zclamp_high = self._z_max_limit()
            self._zclamp_floor_default = self._z_min_limit()
            LOG.info('SUBTABS: NED CONTROLS > JOG > CLAMP built '
                     '(Z travel from INI = %s .. %s; the clamp raises the '
                     'FLOOR via ini.2.min_limit and restores it on disable)',
                     self._zclamp_floor_default, self._zclamp_high)
            t = QTimer(self)
            t.timeout.connect(self._zclamp_tick)
            t.start(300)
            self._zclamp_timer = t
        except Exception as e:
            LOG.error('SUBTABS build FAILED: %s', e)

    def _z_min_limit(self):
        try:
            import linuxcnc, os
            ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])
            return float(ini.find('JOINT_2', 'MIN_LIMIT') or -620.0)
        except Exception:
            return -620.0

    def _z_max_limit(self):
        try:
            import linuxcnc, os
            ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])
            return float(ini.find('JOINT_2', 'MAX_LIMIT') or 0.0)
        except Exception:
            return 0.0

    def _zclamp_z(self):
        try:
            import linuxcnc
            if getattr(self, '_zclamp_stat', None) is None:
                self._zclamp_stat = linuxcnc.stat()
            self._zclamp_stat.poll()
            return self._zclamp_stat.actual_position[2]
        except Exception:
            return None

    def _zclamp_say(self, msg, err=False):
        w = self._zclamp_widgets.get('status')
        if w is not None:
            w.setStyleSheet('color: rgb(235,90,90); font: 10pt; font-weight: bold;'
                            if err else 'color: rgb(160,160,160); font: 9pt;')
            w.setText(msg)

    def _zclamp_low_changed(self):
        edit = self._zclamp_widgets.get('edit')
        if edit is None:
            return
        txt = edit.text().strip()
        if not txt:
            self._zclamp_low = None
            return
        try:
            self._zclamp_low = float(txt)
        except ValueError:
            self._zclamp_low = None
            self._zclamp_say('Zlow "%s" is not a number' % txt, err=True)
            return
        # (no HAL pin: an ARMED clamp writes ini.2.min_limit directly, and the
        #  field is read-only while armed, so nothing to push here)
        if self._zclamp_on:
            os.system('timeout 3 halcmd setp ini.2.min_limit %.4f '
                      '>/dev/null 2>&1' % self._zclamp_low)
        LOG.info('ZCLAMP: Zlow set to %.4f (machine)', self._zclamp_low)
        self._zclamp_say('Zlow = %.3f, ceiling %.3f' %
                         (self._zclamp_low, self._zclamp_high))

    def _zclamp_disable(self, why, err=True):
        """Revert to DISABLED. Estop-class: the message is loud and goes to the
        error channel, not just the log."""
        try:
            self.comp.getPin('zclamp-enable').value = False
        except Exception:
            pass
        # RESTORE THE REAL FLOOR FIRST -- operator 2026-08-02: "when disabled
        # is clicked, it reverts back to default soft limits, this must happen
        # instantly". Before any UI work, and timeout-wrapped so a contended
        # HAL can never leave the machine clamped (the boot-lottery lesson:
        # every scripted halcmd gets a timeout).
        try:
            rc = os.system('timeout 3 halcmd setp ini.2.min_limit %.4f '
                           '>/dev/null 2>&1' % self._zclamp_floor_default)
            import linuxcnc as _l, time as _t
            _s = _l.stat()
            # setp lands via the ini-hal poll, not instantly -- give it up to
            # 500 ms before calling it a failure (an earlier check raced it and
            # cried "NOT RESTORED" about a floor that restored fine 20 ms later)
            back = None
            _t0 = _t.time()
            while _t.time() - _t0 < 0.5:
                _s.poll()
                back = _s.joint[2]['min_position_limit']
                if abs(back - self._zclamp_floor_default) <= 0.001:
                    break
                _t.sleep(0.02)
            if abs(back - self._zclamp_floor_default) > 0.001:
                LOG.error('ZCLAMP: FLOOR NOT RESTORED -- min_position_limit is '
                          '%.3f, wanted %.3f (rc=%s)', back,
                          self._zclamp_floor_default, rc)
                try:
                    _l.command().error_msg(
                        'Z CLAMP: soft limit NOT restored (still %.3f) -- '
                        'restart before trusting Z travel' % back)
                except Exception:
                    pass
            else:
                LOG.info('ZCLAMP: Z floor restored to %.3f', back)
        except Exception as e:
            LOG.error('ZCLAMP: floor restore failed: %s', e)

        self._zclamp_on = False
        btn = self._zclamp_widgets.get('btn')
        if btn is not None:
            btn.setChecked(False)
            btn.setText('DISABLED')
            btn.setStyleSheet(self.ZCLAMP_OFF_QSS)
        edit = self._zclamp_widgets.get('edit')
        if edit is not None:
            edit.setReadOnly(False)     # editable again once disarmed
            edit.setStyleSheet('')
        self._zclamp_say(why, err=err)
        if err:
            LOG.error('ZCLAMP DISABLED: %s', why)
            try:
                import linuxcnc
                linuxcnc.command().error_msg('Z CLAMP DISABLED: %s' % why)
            except Exception:
                pass
        else:
            LOG.info('ZCLAMP disabled: %s', why)

    # MPG wheel jogging travels at (detent rate x step size), NOT at the
    # percent slider -- so the ONLY way to bound the speed into the clamp is
    # to bound how many counts per second are read. Measured overshoot into an
    # armed floor: 5 mm/s -> 20 um, 10 mm/s -> 32 um, 20 mm/s -> 56 um.
    # We hold the demand at ZCLAMP_MAX_MMPS, which at 0.1 mm/detent means
    # 50 detents/s = 200 counts/s = half a wheel turn per second.
    # MEASURED 2026-08-02 (sweep from -25 into a -50 clamp, 0.1 mm/detent,
    # violent spin injected, only the truncation varied):
    #    800 counts/s (2 turns/s, 20 mm/s demand) -> stopped 2 um SHORT  OK
    #   1600 counts/s (4 turns/s, 40 mm/s)        -> 22 um past
    #   3200 counts/s                             -> 24 um past
    #   6400 counts/s                             -> 45 um past
    # So 20 mm/s of demand is the proven ceiling: at 0.1 mm/detent that is
    # exactly the operator's 2 turns/s. Coarser steps get scaled down to the
    # same demand so they cannot outrun the floor.
    ZCLAMP_MAX_MMPS = 20.0       # mm/s of wheel demand while armed (measured)
    MPG_CPD = 4                  # counts per detent (tools/groundtruth/mpgjog.sh:37)
    MPG_CPS_NORMAL = 800         # 2 wheel turns/s (operator-specified cap)

    ZCLAMP_MAX_STEP = 0.1        # mm/detent -- coarser steps are locked out
    ZCLAMP_MARGIN = 0.02         # mm: engage the gate this far ABOVE Zlow so
                                 # the servo settle lands AT Zlow, never under
                                 # (operator: "it shouldn't go under at all")
    ZCLAMP_BACKSTOP = 1.0        # mm BELOW Zlow where the soft limit parks;
                                 # the gate stops you at Zlow, this only
                                 # catches a runaway, and keeps a small
                                 # overshoot from stranding the machine

    def _zclamp_limit_steps(self, on):
        """While armed, only 0.01 and 0.1 mm/detent may be selected (operator
        2026-08-02: "i was able to select 5mm per detent after enabling. this
        should not have been allowed"). Coarse steps are what let a spun wheel
        demand speed the floor cannot absorb, so they are greyed out and a
        coarse selection already in force is pulled back to 0.1."""
        try:
            from PySide6.QtWidgets import QWidget as _QW
            win = self.window()
            jw = win.findChild(_QW, 'jogincrement') if win else None
            pairs = getattr(jw, '_buttons_by_value', []) if jw is not None else []
            if not pairs:
                LOG.error('ZCLAMP: jogincrement buttons not found -- coarse '
                          'steps NOT locked out')
                return
            fallback = None
            current_coarse = False
            for btn, v in pairs:
                try:
                    val = float(v)
                except (TypeError, ValueError):
                    continue
                allowed = (not on) or (val <= self.ZCLAMP_MAX_STEP + 1e-9)
                btn.setEnabled(allowed)
                if on and abs(val - self.ZCLAMP_MAX_STEP) < 1e-9:
                    fallback = btn
                if on and btn.isChecked() and val > self.ZCLAMP_MAX_STEP + 1e-9:
                    current_coarse = True
            if on and current_coarse and fallback is not None:
                fallback.click()          # pull the selection back to 0.1
                LOG.info('ZCLAMP: step was coarser than %.2f mm -- forced to '
                         '%.2f mm', self.ZCLAMP_MAX_STEP, self.ZCLAMP_MAX_STEP)
            LOG.info('ZCLAMP: coarse jog steps %s',
                     'LOCKED OUT (0.01 / 0.1 only)' if on else 'available again')
        except Exception as e:
            LOG.error('ZCLAMP: step lockout failed: %s', e)

    # BISECT SWITCH 2026-08-03. False stops the 2 s var-file poll that fills
    # the calibration fields -- it was the suspect for the SIGBUS after a
    # successful puck cycle. Inconclusive: one success crashed WITH it on,
    # one survived with it on, one survived with it off. Back on because the
    # operator needs the numbers; if a crash follows a success again, that is
    # the evidence that convicts this code.
    CAL_REFRESH_ENABLED = True

    VAR_FILE = '/home/brains/Documents/ned/configs/ned5_pb/ned5_pb.var'

    LCNC_LOG = '/home/brains/Documents/ned/lcnc.log'
    # only the calibration's own narration -- not the whole machine log
    CAL_LOG_KEYS = ('CAL A', 'CAL C', 'CAL AC', 'StartA', 'StartC',
                    'StartPuck', 'SET C REF', 'GO TO C REF', 'GOTO ZERO',
                    'CAL step', 'CAL RESULT', 'CAL edges', 'CAL pair')

    def cal_say(self, text):
        """Append one line to the commentary, from anywhere in this file."""
        w = getattr(self, '_cal_log', None)
        if w is None:
            return
        try:
            w.appendPlainText(text)
            w.verticalScrollBar().setValue(w.verticalScrollBar().maximum())
        except Exception:
            pass

    def _cal_log_poll(self):
        """Tail lcnc.log and surface the calibration narration.

        Start from the END of the file the first time: the log carries
        previous sessions, and replaying those as if they were happening now
        is exactly the confusion the stale delta rows caused.
        """
        w = getattr(self, '_cal_log', None)
        if w is None:
            return
        try:
            import re as _re
            sz = os.path.getsize(self.LCNC_LOG)
            if self._cal_log_pos is None:
                self._cal_log_pos = sz
                return
            if sz < self._cal_log_pos:      # truncated by a relaunch
                self._cal_log_pos = 0
            if sz == self._cal_log_pos:
                return
            with open(self.LCNC_LOG, 'rb') as f:
                f.seek(self._cal_log_pos)
                chunk = f.read(sz - self._cal_log_pos)
                self._cal_log_pos = f.tell()
            for raw in chunk.decode('utf-8', 'replace').split('\n'):
                line = _re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', raw).strip()
                if not line or not any(k in line for k in self.CAL_LOG_KEYS):
                    continue
                if '[qtpyvcp' in line or 'ned_controls.py' in line:
                    continue
                self.cal_say(line)
        except Exception as e:
            LOG.error('CAL commentary poll failed: %s', e)
            self._cal_log_timer.stop()

    def _cal_fields_refresh(self):
        try:
            fields = getattr(self, '_cal_fields', None)
            if not fields:
                return
            mt = os.path.getmtime(self.VAR_FILE)
            # The chain instruction is re-evaluated on EVERY tick, not only
            # when the var file changes: one of its inputs is the tool
            # lengths, which live in the tool DB and never touch this file.
            # Gating it on mtime would leave "press MEASURE ALL TOOLS" on
            # screen for the whole cycle and long after it finished.
            self._cal_chain_tick()
            if getattr(self, '_cal_var_mtime', None) == mt:
                return
            self._cal_var_mtime = mt
            vals = {}
            with open(self.VAR_FILE) as f:
                for line in f:
                    p = line.split()
                    if len(p) == 2 and p[0].isdigit() and (
                            3040 <= int(p[0]) <= 3078
                            or int(p[0]) == 3010
                            or int(p[0]) == 3007
                            or 4001 <= int(p[0]) <= 4024
                            or 5181 <= int(p[0]) <= 5183):
                        vals[p[0]] = float(p[1])
            # kept for the chain instruction: 3007/3010/5183 say how far the
            # calibration got, 4001-4024 say which tools the rack holds
            self._cal_var_cache = vals
            seen = getattr(self, '_cal_last', None)
            if seen is None:
                seen = self._cal_last = {}
            for key, (cur, prv) in fields.items():
                v = vals.get(key)
                if v is None:
                    continue
                # A/C are legitimately 0.0 (uncorrected); the puck numbers are
                # not, so only those treat 0 as "nothing measured yet"
                if key in ('3045', '3046', '3047', '3010',
                           '5181', '5182', '5183') and abs(v) < 1e-9:
                    continue
                # A and C show the ABSOLUTE ENCODER READING, not degrees:
                # #3069/#3070 hold the accumulated correction, so the count
                # at the corrected zero is the stored PS shifted by it --
                # exactly the number RECORD writes to head_zero.inc.
                if key in ('3069', '3070'):
                    # THE BANKED VALUE ONLY -- read head_zero.inc with NO
                    # pending correction added. Showing file+#3069 meant the
                    # row moved the moment a correction was applied and moved
                    # back when it was discarded, so a cycle that banked
                    # NOTHING still rewrote the display and left PREVIOUS
                    # holding a mid-cycle number that was never a zero
                    # (operator 2026-08-03: "C had no improvement, but somehow
                    # updated the POS Zero"). These rows are labelled BANKED;
                    # they now change only when a bank actually happens.
                    txt = self._enc_at_zero('A' if key == '3069' else 'C', 0.0)
                elif key in ('3058', '3060', '3061') and abs(v) < 1e-9:
                    # A DASH, NOT ZERO. These offsets drive motion, and 0.0000
                    # is a perfectly valid coordinate meaning "go there, right
                    # over the probe". An unset reference must read as a
                    # number that means nothing at all, or a cleared teach
                    # looks like an instruction. Operator 2026-08-03.
                    txt = '--'
                else:
                    txt = '%.4f' % v
                # SHIFT ON THE DISPLAYED VALUE, NOT THE RAW PARAM. The A/C
                # rows show where true zero SITS -- file value plus any
                # pending correction -- so applying a correction and then
                # banking it produce the SAME count: banking just moves the
                # amount from #3069 into head_zero.inc. Keying the shift on
                # the raw param meant the bank shifted a second time and
                # overwrote PREVIOUS with a number identical to CURRENT,
                # destroying the pre-correction zero -- the one value worth
                # comparing against. Operator 2026-08-03: "if a distance
                # improves, the zero has changed".
                if not cur.text():
                    cur.setText(txt)
                elif txt != cur.text():
                    prv.setText(cur.text())
                    LOG.info('CAL %s: %s -> %s  (param %.4f -> %.4f)',
                             key, cur.text(), txt, seen.get(key, 0.0), v)
                    cur.setText(txt)
                seen[key] = v
            for w, name, bkey, akey, unit in getattr(
                    self, '_cal_delta_rows', []):
                b, a = vals.get(bkey), vals.get(akey)
                if b is None or a is None or (abs(b) < 1e-9 and abs(a) < 1e-9):
                    continue
                base = getattr(self, '_cal_delta_base', {})
                if abs(b - base.get(bkey, 1e9)) < 1e-9 \
                   and abs(a - base.get(akey, 1e9)) < 1e-9:
                    continue
                better = abs(a) < abs(b)
                w.setText('%-14s before %+9.4f   after %+9.4f %s   %s'
                          % (name, b, a, unit,
                             'BETTER' if better else 'WORSE'))
                w.setStyleSheet('font: 10pt "DejaVu Sans Mono"; color: %s;'
                                % ('rgb(120,220,120)' if better
                                   else 'rgb(230,140,140)'))
            chip = getattr(self, '_cal_lockchip', None)
            if chip is not None:
                lk = getattr(self, '_ac_locked', {}) or {}
                chip.setText('A %s   %s %s'
                             % ('LOCKED' if lk.get('a') else '---',
                                ROT.upper(),
                                'LOCKED' if lk.get('c') else '---'))
            tw = getattr(self, '_cal_total', None)
            if tw is not None:
                ca, cc = vals.get('3066', 0.0), vals.get('3067', 0.0)
                it = vals.get('3068', 0.0)
                if abs(ca) > 1e-9 or abs(cc) > 1e-9:
                    tw.setText('pending correction:   A %+.4f deg   '
                               'C %+.4f deg   (%d iterations)'
                               % (ca, cc, int(it)))
        except Exception as e:
            LOG.error('CAL fields refresh failed: %s', e)

    # Colour classes, anchored to PB's own base rgb(46,52,54) = #2E3436.
    # Outline + tinted fill, never saturated flat: flat red/green already mean
    # ESTOP and PB's own STYLE_UP/STYLE_DOWN, and a calibration button must not
    # compete with the estop. Design review 2026-08-03.
    #   MEASURE (amber) -- long automatic probing motion
    #   POSE    (cyan)  -- motion, reversible, writes nothing
    #   COMMIT  (violet)-- writes head_zero.inc; nothing else in PB is violet
    # The title used to sit ON the border line -- half over the dark panel,
    # half over the grey page, so it was unreadable against both. Giving the
    # box a 22px top margin and the title its OWN opaque background lifts it
    # clear of the frame and puts it on one colour. Operator 2026-08-03.
    CAL_QSS_BOX = ('QGroupBox { background: #262B2D; border: 1px solid #5A6466;'
                   ' border-radius: 3px; margin-top: 22px; color: #FFD08A;'
                   ' font: bold 12pt; padding-top: 6px; }'
                   'QGroupBox::title { subcontrol-origin: margin;'
                   ' subcontrol-position: top left; left: 8px; top: 0px;'
                   ' padding: 3px 10px; background: #2E3436;'
                   ' color: #FFD08A; }')
    _BTN = ('QPushButton { background: %s; border: 2px solid %s; color: %s;'
            ' border-radius: 3px; font: bold 12pt; }'
            'QPushButton:hover { background: %s; }'
            'QPushButton:pressed { background: %s; }'
            'QPushButton:disabled { background: #22282A; border: 1px solid'
            ' #3A4244; color: #5D6567; }')
    CAL_QSS = {
        'measure': _BTN % ('#3B2E12', '#E8A33D', '#FFD08A', '#4A3A18', '#5C4718'),
        'pose':    _BTN % ('#16323A', '#4FB3C9', '#A8DEE9', '#1C4049', '#235058'),
        'commit':  _BTN % ('#3A1F3F', '#C86BE0', '#EBB8F5', '#4A2851', '#5A3163'),
        'read':    ('QLineEdit { background: #1B1F20; border: 1px solid #3A4244;'
                    ' color: #DCE3E0; border-radius: 2px; padding: 2px 4px; }'),
        'readprev': ('QLineEdit { background: #1B1F20; border: 1px solid #3A4244;'
                     ' color: #7C8482; border-radius: 2px; padding: 2px 4px; }'),
        'delta':   ('QLabel { color: #C8CFCC; padding: 2px 4px; }'
                    'QLabel[verdict="better"] { color: #78DC78;'
                    ' background: #16281A; }'
                    'QLabel[verdict="worse"] { color: #F08A6E;'
                    ' background: #2E1A16; }'),
        # CLEAR is not motion and not a commit -- it discards stored state.
        # Deliberately quiet so it does not read as a primary action.
        'clear':   ('QPushButton { background: #2A2320; border: 1px solid'
                    ' #7A6A55; color: #C8B79A; border-radius: 3px;'
                    ' font: bold 9pt; }'
                    'QPushButton:hover { background: #362D28; }'
                    'QPushButton:disabled { background: #22282A; border: 1px'
                    ' solid #3A4244; color: #5D6567; }'),
        'clearArmed': ('QPushButton { background: #5A2318; border: 2px solid'
                       ' #F08A6E; color: #FFD9CC; border-radius: 3px;'
                       ' font: bold 9pt; }'),
        'log':     ('QPlainTextEdit { background: #1B1F20; color: #DCE3E0;'
                    ' border: 1px solid #3A4244; border-radius: 2px; }'),
    }
    # the running cycle is outlined white; every other motion button greys out
    CAL_QSS_RUNNING = ('QPushButton { background: #4A3A18; border: 2px solid'
                       ' #FFFFFF; color: #FFD08A; border-radius: 3px;'
                       ' font: bold 12pt; }')

    def _cal_buttons_busy(self, busy, running=None):
        """Lock the motion set while a cycle runs.

        A 900 s StartAC used to leave eleven live-looking motion buttons, with
        a toast AFTER the press as the only feedback. Design review
        2026-08-03: disable on issue, re-enable on completion, and outline the
        one that is actually running.
        """
        try:
            for k, b in getattr(self, '_cal_btn', {}).items():
                b.setEnabled(not busy)
                if busy and k == running:
                    b.setEnabled(False)
                    b.setStyleSheet(self.CAL_QSS_RUNNING)
                elif not busy:
                    if k == 'clear':
                        cls = 'clear'
                    elif k in ('goto', 'cleft', 'cright'):
                        cls = 'pose'
                    else:
                        cls = 'measure'
                    b.setStyleSheet(self.CAL_QSS[cls])
        except Exception as e:
            LOG.error('CAL button lock failed: %s', e)

    CAL_CLEAR_COUNT = 5

    def _cal_clear_click(self):
        """Five-second countdown, and a second press cancels.

        Clearing the C reference throws away a teach that took a jog to make,
        and the button sits among live readouts -- so it must not act on a
        single stray touch. Same pattern as the spindle load/unload countdown.
        """
        b = self._cal_btn.get('clear')
        if b is None:
            return
        if getattr(self, '_cal_clear_n', 0) > 0:      # armed -> cancel
            self._cal_clear_n = 0
            b.setText('CLEAR C REF')
            b.setStyleSheet(self.CAL_QSS['clear'])
            self.cal_say('.. C ref clear cancelled')
            return
        self._cal_clear_n = self.CAL_CLEAR_COUNT
        b.setStyleSheet(self.CAL_QSS['clearArmed'])
        self._cal_clear_tick()

    def _cal_clear_tick(self):
        b = self._cal_btn.get('clear')
        if b is None or getattr(self, '_cal_clear_n', 0) <= 0:
            return
        b.setText('CLEAR in %d  (tap to stop)' % self._cal_clear_n)
        self._cal_clear_n -= 1
        if self._cal_clear_n <= 0:
            b.setText('CLEAR C REF')
            b.setStyleSheet(self.CAL_QSS['clear'])
            self._cal_clear_cref()
            return
        QTimer.singleShot(1000, self._cal_clear_tick)

    def _cal_clear_cref(self):
        """Drop the taught C reference so the next StartC re-teaches.

        Operator 2026-08-03: overload StartC and clear the params to redo it,
        rather than carry a second button whose meaning changes between
        presses. The params ARE the state.
        """
        label = 'CLEAR C REF'
        try:
            import linuxcnc
            c = linuxcnc.command()
            st = linuxcnc.stat()
            st.poll()
            if st.interp_state != linuxcnc.INTERP_IDLE or not st.inpos:
                c.error_msg('%s refused: machine is busy' % label)
                return
            if not self._take_mdi(c, label):
                return
            for p in ('3058', '3060', '3061', '3059'):
                c.mdi('#%s = 0' % p)
            self._hand_back_manual(c, label)
            LOG.info('%s: dy, depth, X offset and the pending flag zeroed -- '
                     'the next StartC will position for a fresh jog', label)
            self.cal_say('>> C reference cleared -- next StartC re-teaches')
            c.error_msg('C reference cleared. Press StartC to position for a '
                        'fresh teach.')
        except Exception as e:
            LOG.error('%s failed: %s', label, e)

    def _cal_tab_changed(self, idx):
        """Entering CALIBRATION locks A and C. It does NOT re-zero them.

        It used to fire REF A then REF C. A REF UNHOMES the joint while its
        absolute read runs -- that is how the brain forces a fresh read -- so
        for the length of two read cycles stat.homed[4]/[5] were false, which
        made _cal_gate refuse GOTO ZERO and disabled the entire homing menu
        (its condition is homed[4] and homed[5]). The operator was locked out
        of this tab's own first button for the best part of a minute.

        It was also redundant: declare_xyzw() applies the A/C absolute read
        directly now, so A and C are already right when the machine comes up.
        The REF cycle re-read values that were already correct, and its only
        visible effect was the lockout. Operator 2026-08-03.
        """
        if idx == getattr(self, '_cal_tab_index', -1):
            self._cal_lock_ac('CALIBRATION TAB')

    def _cal_lock_ac(self, label):
        """Lock A and C for the duration of the calibration.

        The lock gates the MPG (pendant.lock-a/-c makes the pendant skip the
        axis in its selection cycle) and the GUI jog path, but NOT the MDI
        moves the cycles themselves issue -- so the routines still tilt the
        head while a hand on the wheel cannot (operator 2026-08-03: "lock A
        and C so that human doesn't move them inadvertently throughout all
        this").

        Read back, because a set that did not take is worse than no lock at
        all: it is a lock the operator believes in. Loud on failure, but it
        does not refuse the cycle -- the lock protects against interference,
        it is not a machine-safety precondition.
        """
        for ax in ('a', 'c'):
            try:
                self.set_ac_lock(ax, True)
                got = bool(self.comp.getPin('lock-%s-out' % ax).value)
                if got:
                    LOG.info('%s: %s LOCKED (verified)', label, ax.upper())
                else:
                    LOG.error('%s: %s lock did NOT take -- the wheel can '
                              'still move it', label, ax.upper())
                    try:
                        import linuxcnc
                        linuxcnc.command().error_msg(
                            '%s: %s LOCK FAILED -- keep off the wheel'
                            % (label, ax.upper()))
                    except Exception:
                        pass
            except Exception as e:
                LOG.error('%s: locking %s failed: %s', label, ax.upper(), e)
        self._cal_lock_buttons(True)

    def _cal_lock_buttons(self, on):
        """Mirror the lock onto the DRO buttons. A lock the operator cannot
        SEE is a lock they will fight."""
        try:
            from PySide6.QtWidgets import QWidget as _QW
            win = self.window()
            if win is None:
                return
            for name in ('zero_a_button', 'zero_c_button'):
                b = win.findChild(_QW, name)
                if b is not None and hasattr(b, 'setChecked'):
                    b.blockSignals(True)
                    b.setChecked(bool(on))
                    b.blockSignals(False)
        except Exception as e:
            LOG.error('lock button mirror failed: %s', e)

    # cal_c_goto takes a 4th argument: which side of the puck to park on
    CAL_SUBS = {
        'puck': ('cal_probe_center', 'StartPuck', False),
        'pivot': ('cal_pivot_touch', 'PIVOT TOUCH', False),
        'a':    ('cal_a_cycle',      'StartA',    True),
        'c':    ('cal_c_cycle',      'StartC',    True),
        # no 'ac' entry: StartAC is driven from Python (_ac_start), not by a
        # g-code sub.
        'goto': ('cal_goto_zero',    'ZERO',      True),
        # Called NOSE, not SHOULDER: what it measures is the spindle
        # nose face, it hands off to probe_spindle_nose, and it writes
        # #3010 whose own definition is the nose triggering point.
        # (operator 2026-08-11: "find nose rather"). The sub file keeps
        # its name -- cal_shoulder.ngc is what the registry, the help
        # text and every past log line refer to.
        'shoulder': ('cal_shoulder', 'FIND NOSE',  True),
        # THE PROBING RESET, in the order it must be pressed (operator
        # 2026-08-11, for when the setter gets bumped). Each step
        # refuses unless the one before it has left its number behind,
        # so the sequence cannot be run out of order by accident.
        'probeheight':  ('cal_probe_height',  'SET PROBE HEIGHT', False),
        'storeresults': ('cal_store_results', 'STORE RESULTS',    False),
        'measureall':   ('cal_measure_all',   'MEASURE ALL TOOLS', False),
        'cleft':  ('cal_c_goto',     'C LEFT',    True),
        'cright': ('cal_c_goto',     'C RIGHT',   True),
        # RACK CAL takes no centre args -- the operator's start pose IS the
        # datum (spindle centred 10 mm above the P1 holder top, by eye).
        'rack':   ('rack_cal',       'RACK CAL',  False),
    }

    CAL_EXTRA = {'cleft': -1, 'cright': 1}

    # FOUR STEPS, IN ORDER, ADVANCED BY THE CLICK. Operator 2026-08-11:
    # "it should show 1/4, and then after you click the first button, it
    # should show 2/4 and so on. take out that LAST STEP bullshit."
    # An earlier version derived the step from machine state and was wrong
    # on the very first read -- it saw stale tool lengths and announced 4/4
    # before anything had been pressed. The click is the honest signal: it
    # is the thing the operator actually did.
    CAL_CHAIN_KEYS = ('shoulder', 'probeheight', 'storeresults', 'measureall')
    CAL_CHAIN_STEPS = (
        '1/4  Remove tool by hand  \u2192  FIND NOSE',
        '2/4  Jog to probe height  \u2192  SET PROBE HEIGHT',
        '3/4  STORE RESULTS  (clears all lengths)',
        '4/4  Spindle empty  \u2192  MEASURE ALL TOOLS',
    )

    def _cal_chain_advance(self, which):
        """A chain button fired: show the step AFTER it."""
        if which not in self.CAL_CHAIN_KEYS:
            return
        i = self.CAL_CHAIN_KEYS.index(which) + 1
        # the last step has no successor -- it simply stays up
        self._cal_chain_i = min(i, len(self.CAL_CHAIN_STEPS) - 1)
        self._cal_chain_tick()

    def _cal_chain_tick(self):
        lab = getattr(self, '_cal_next', None)
        if lab is None:
            return
        i = getattr(self, '_cal_chain_i', 0)
        txt = self.CAL_CHAIN_STEPS[max(0, min(i, len(self.CAL_CHAIN_STEPS) - 1))]
        if txt != getattr(self, '_cal_next_txt', None):
            self._cal_next_txt = txt
            lab.setText(txt)
            LOG.info('CAL CHAIN: %s', txt)

    def _cal_gate(self, label):
        """Shared refusal gate for every calibration cycle. Returns the
        linuxcnc command/stat pair, or None having ALREADY told the operator
        why.

        Checks LinuxCNC state only -- ON, homed, idle, in position. It does
        NOT check whether home was physically re-run this session. Declaring
        home from the stored coordinates and flying the STALE HOME banner is
        exactly so the operator can work through many restarts without
        re-homing; that is their risk to take, and a GUI gate must never
        overrule it (operator 2026-08-03). CLAUDE.md rule 17 binds MY scripted
        motion, not their button."""
        try:
            import linuxcnc
        except Exception as e:
            LOG.error('%s refused: linuxcnc import failed: %s', label, e)
            return None
        c = linuxcnc.command()
        s = linuxcnc.stat()
        s.poll()
        if s.task_state != linuxcnc.STATE_ON or not all(s.homed[:NJ]) \
           or s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos:
            c.error_msg('%s refused: machine must be ON, homed and idle' % label)
            LOG.error('%s refused: not ON/homed/idle', label)
            return None
        # RE-ASSERT, DO NOT GIVE UP ON THE FIRST TRY. ned_brain restores
        # MANUAL + teleop the instant a program ends, so a cycle issued right
        # after the previous one lands in that transition and a single
        # mode(MDI) loses the race -- StartAC died on exactly this 80 ms after
        # StartC finished (2026-08-03). Retry briefly and name the cause if it
        # still will not take.
        for attempt in range(1, 6):
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            s.poll()
            if s.task_mode == linuxcnc.MODE_MDI:
                if attempt > 1:
                    LOG.info('%s: MDI took %d attempts (brain was restoring '
                             'MANUAL)', label, attempt)
                return c, s
            time.sleep(0.2)
        why = ('not homed' if not all(s.homed[:NJ]) else
               'task is not accepting commands')
        c.error_msg('%s refused: could not enter MDI after 5 tries (%s)'
                    % (label, why))
        LOG.error('%s refused: task_mode never reached MDI after 5 re-asserts '
                  '-- %s', label, why)
        return None

    def _cal_issue_failed(self, which):
        """A cycle could not be issued. Release the lock, and if the AC
        sequence is driving, retry rather than stalling: the gate fails on
        transient states (brain restoring MANUAL, a REF still landing) and a
        silent stall leaves the operator watching a machine that will never
        move again."""
        self._cal_buttons_busy(False)
        if getattr(self, '_ac_active', False):
            n = getattr(self, '_ac_retry', 0) + 1
            self._ac_retry = n
            if n > 10:
                self._ac_stop('could not issue the %s cycle after %d tries'
                              % (which.upper(), n))
                return
            LOG.info('StartAC: %s issue refused, retry %d in 2 s',
                     which.upper(), n)
            self.cal_say('.. %s refused, retrying (%d)' % (which.upper(), n))
            QTimer.singleShot(2000, self._ac_try_issue)

    def _cal_run(self, which):
        """Every calibration cycle goes through here: same gate, same centre
        arguments, same loud failure. The g-code owns the geometry."""
        if which == 'ac':
            self._ac_start()
            return
        sub, label, need_centre = self.CAL_SUBS[which]
        try:
            gate = self._cal_gate(label)
            if gate is None:
                self._cal_issue_failed(which)
                return
            c, s = gate
            if which == 'shoulder':
                # use the stat the GATE already returned -- `linuxcnc` is
                # imported inside _cal_gate's scope, not this one, so calling
                # linuxcnc.stat() here raised NameError and the button did
                # nothing at all (2026-08-03).
                s.poll()
                tool = getattr(s, 'tool_in_spindle', 0)
                if tool not in (0, -1):
                    msg = ('SHOULDER refused: tool %s is in the spindle. This '
                           'measures the spindle NOSE -- remove the tool by '
                           'hand, then press SHOULDER again.' % tool)
                    c.error_msg(msg)
                    LOG.error(msg)
                    self.cal_say('!! %s' % msg)
                    if getattr(self, '_cal_status', None) is not None:
                        self._cal_status.setText(msg)
                    return
                self.cal_say('>> SHOULDER: spindle empty, proceeding')
            if need_centre:
                vals = {}
                for k in ('3045', '3046', '3047'):
                    t = self._cal_fields[k][0].text().strip()
                    if not t:
                        c.error_msg('%s refused: no puck centre yet -- run '
                                    'StartPuck first' % label)
                        LOG.error('%s refused: field %s empty', label, k)
                        return
                    vals[k] = float(t)
                extra = self.CAL_EXTRA.get(which)
                if which == 'shoulder':
                    extra = self._z_min_limit()   # plunge stops 1 mm above it
                args = '[%.4f] [%.4f] [%.4f]' % (vals['3045'], vals['3046'],
                                                 vals['3047'])
                if extra is not None:
                    args += ' [%.4f]' % extra
                c.mdi('o<%s> call %s' % (sub, args))
                LOG.info('%s: %s issued with centre %.4f %.4f top %.4f',
                         label, sub, vals['3045'], vals['3046'], vals['3047'])
                self.cal_say('>> %s' % label)
                # advance AFTER the cycle is actually issued, never on the
                # click: every refusal above returns without reaching here,
                # so the instruction cannot walk past a step that did not run
                self._cal_chain_advance(which)
            else:
                # Some plain cycles still take one argument. The Z soft limit
                # is READ FROM THE INI here rather than hardcoded in the sub,
                # for the same reason the shoulder does it: the sub must not
                # own a copy of a machine limit that can change.
                plain = ''
                if which == 'probeheight':
                    plain = ' [%.4f]' % self._z_min_limit()
                elif which in ('storeresults', 'measureall'):
                    plain = ' [%d]' % self.RACK_TABLE_FORKS
                c.mdi('o<%s> call%s' % (sub, plain))
                self._cal_chain_advance(which)
                LOG.info('%s: %s issued', label, sub)
            self._cal_lock_ac(label)
            self._cal_buttons_busy(True, running=which)
            # EVERY cycle arms the watcher, not just a/c. The watcher is the
            # only thing that re-enables the buttons, so arming it only for
            # a/c meant pressing ZERO, StartPuck, C LEFT, C RIGHT or SHOULDER
            # disabled the whole tab FOREVER -- one ZERO press and nothing
            # could be clicked again (2026-08-03). a/c additionally bank;
            # the others just need the lock released.
            self._cal_watch_which = which
            self._cal_watch_start()
            self._cal_watch_t0 = os.path.getmtime(self.VAR_FILE)
            if getattr(self, '_cal_status', None) is not None:
                self._cal_status.setText(self.CAL_MSG.get(which, ''))
        except Exception as e:
            LOG.error('%s failed: %s', label, e)

    # --- StartA completion watcher -------------------------------------
    # The operator's spec: probe, re-find the puck, and "if its an
    # improvement, update the parameter file". The decision needs the cycle
    # to have FINISHED, so this polls rather than guessing at issue time.
    CAL_WATCH_MS = 500
    CAL_WATCH_DEADLINE_S = 900      # 4 wall touches + a puck find

    def _cal_watch_start(self):
        self._cal_watch_seen_busy = False
        self._cal_watch_elapsed = 0.0
        self._cal_watch_said = 0.0
        t = getattr(self, '_cal_watch_timer', None)
        if t is None:
            t = self._cal_watch_timer = QTimer(self)
            t.timeout.connect(self._cal_watch_tick)
        t.start(self.CAL_WATCH_MS)
        LOG.info('StartA: watching for completion (auto-record on improvement)')

    def _cal_watch_stop(self, why):
        t = getattr(self, '_cal_watch_timer', None)
        if t is not None:
            t.stop()
        LOG.info('StartA watcher stopped: %s', why)

    def _cal_watch_tick(self):
        try:
            import linuxcnc
            s = linuxcnc.stat()
            s.poll()
            self._cal_watch_elapsed += self.CAL_WATCH_MS / 1000.0
            busy = (s.interp_state != linuxcnc.INTERP_IDLE) or (not s.inpos)
            if busy:
                self._cal_watch_seen_busy = True
            # never sit silent: say something at least every 10 s
            if self._cal_watch_elapsed - self._cal_watch_said >= 10.0:
                self._cal_watch_said = self._cal_watch_elapsed
                LOG.info('StartA: %.0f s elapsed, interp=%s inpos=%s',
                         self._cal_watch_elapsed, s.interp_state, s.inpos)
            if self._cal_watch_elapsed > self.CAL_WATCH_DEADLINE_S:
                self._cal_watch_stop('deadline %.0f s reached -- NOT recording'
                                     % self.CAL_WATCH_DEADLINE_S)
                self._cal_buttons_busy(False)
                linuxcnc.command().error_msg(
                    'StartA: %d s with no completion -- not recording. Check '
                    'the log.' % self.CAL_WATCH_DEADLINE_S)
                return
            # A SHORT CYCLE CAN FINISH BETWEEN TICKS. Waiting for
            # seen_busy meant a cycle that started and ended inside one 500 ms
            # window never satisfied it, so the watcher sat there and the
            # button lock NEVER released -- the operator pressed ZERO and was
            # locked out of the whole tab (2026-08-03). After 3 s of an idle,
            # in-position machine, it is finished whether or not we caught it
            # moving.
            if not self._cal_watch_seen_busy:
                if self._cal_watch_elapsed >= 3.0:
                    LOG.info('%s: never seen busy but idle for 3 s -- '
                             'treating as finished',
                             getattr(self, '_cal_watch_which', '?').upper())
                    self._cal_watch_seen_busy = True
                else:
                    return
            if busy:
                return
            # idle is NOT proof of completion -- it reads true between the
            # queued calls inside the cycle. Require the g-code's own marker,
            # written to the var file only by the last line of cal_a_cycle,
            # and require the file to have been rewritten since we issued it
            # so a stale marker from a previous run cannot fire.
            try:
                if os.path.getmtime(self.VAR_FILE) <= getattr(
                        self, '_cal_watch_t0', 0):
                    return
            except Exception:
                return
            which = getattr(self, '_cal_watch_which', 'a')
            if which in ('a', 'c'):
                # these set a completion marker; the rest have no bank step
                if self._read_vars(('3071',)).get('3071', 0.0) < 0.5:
                    return
            self._cal_watch_stop('cycle finished after %.0f s'
                                 % self._cal_watch_elapsed)
            if which in ('a', 'c'):
                self._cal_after_cycle(which)
            else:
                self._cal_buttons_busy(False)
                self.cal_say('.. %s finished' % which.upper())
        except Exception as e:
            self._cal_watch_stop('watcher error: %s' % e)
            self._cal_buttons_busy(False)

    # (before key, after key, "did it move" key, accumulated-correction key,
    #  axis letter, the pin whose rising edge makes the brain re-home it)
    CAL_AXIS = {
        'a': ('3050', '3051', '3072', '3069', 'A', 'refa-out'),
        'c': ('3055', '3056', '3073', '3070', 'C', 'refc-out'),
    }

    # ---- StartAC: the loop lives HERE, not in g-code ------------------
    # Operator 2026-08-03: "corrections are banked as they arrive, not at the
    # end of an AC cycle. that would defeat the entire purpose". The old
    # cal_ac_iterate.ngc ran all five A+C pairs inside ONE program and set the
    # completion marker only at the end, so banking happened once, off
    # #3069/#3070 accumulated over ten cycles. Every iteration after the first
    # measured against a stale zero, so the residuals converged on nothing.
    #
    # Banking is a Python action -- it writes head_zero.inc and pulses REF to
    # re-home the axis -- and g-code can neither do that nor pause to let it
    # happen. So the loop moves to where the banking is.
    # TERMINATION IS CONVERGENCE, not a cycle count -- operator 2026-08-03:
    # the 5-iteration limit is REPLACED by the 2-cycle condition. Four
    # consecutive discards (A, C, A, C) means two full iterations changed
    # nothing, so the residual is below what the probe can resolve. Any bank
    # resets the counter to zero.
    AC_CONVERGED = 4
    # A runaway guard ONLY, deliberately far above any real run: if the loop
    # somehow keeps banking forever, stop and say so rather than grind. It is
    # not the termination condition and reaching it means something is wrong.
    AC_RUNAWAY = 25
    AC_READY_DEADLINE_S = 120

    def _ac_start(self):
        self._ac_active = True
        self._ac_iter = 1
        self._ac_step = 'a'
        self._ac_discards = 0
        self._ac_banked = 0
        LOG.info('StartAC: runs until CONVERGED -- %d consecutive discards '
                 '(A,C,A,C) -- banking each correction as it arrives. '
                 'Runaway guard at %d iterations.',
                 self.AC_CONVERGED, self.AC_RUNAWAY)
        if getattr(self, '_cal_status', None) is not None:
            self._cal_status.setText(
                'StartAC: runs until converged (4 consecutive discards). '
                'Each correction banks immediately, so the next measurement '
                'starts from a real zero.')
        self._ac_next()

    def _ac_stop(self, why):
        self._ac_active = False
        self._cal_buttons_busy(False)
        msg = ('StartAC finished after %d iteration(s): %s. Banked %d '
               'correction(s).' % (self._ac_iter, why, self._ac_banked))
        LOG.info(msg)
        try:
            import linuxcnc
            linuxcnc.command().error_msg(msg)
        except Exception:
            pass
        if getattr(self, '_cal_status', None) is not None:
            self._cal_status.setText(msg)

    def _ac_next(self):
        if not getattr(self, '_ac_active', False):
            return
        if self._ac_discards >= self.AC_CONVERGED:
            self._ac_stop('CONVERGED -- %d consecutive discards, the residual '
                          'is below what the probe can measure'
                          % self._ac_discards)
            return
        if self._ac_iter > self.AC_RUNAWAY:
            self._ac_stop('RUNAWAY GUARD: %d iterations without converging. '
                          'That is not a calibration settling -- check the '
                          'sign and the geometry.' % self.AC_RUNAWAY)
            return
        # banking pulses REF, which UNHOMES that axis for ~15 s. Issuing the
        # next cycle then would just be refused by the gate, so wait for the
        # machine to come back rather than firing into the window.
        self._ac_wait_t0 = time.time()
        # If the last cycle BANKED, a REF was pulsed and it has not landed
        # yet: the pin is set asynchronously and the brain reacts a beat
        # later. Checking "homed and idle" right now sees the machine BEFORE
        # the re-home starts, issues the next cycle, and the REF then unhomes
        # A/C underneath it -- "StartC refused: task_mode never reached MDI"
        # (2026-08-03). So after a bank we must WATCH THE REF HAPPEN: wait to
        # see A/C go unhomed, and only then wait for them to come back.
        # Same shape as rule 17's "verify the home actually ran".
        self._ac_saw_unhomed = not getattr(self, '_ac_last_banked', False)
        self._ac_try_issue()

    def _ac_try_issue(self):
        if not getattr(self, '_ac_active', False):
            return
        try:
            import linuxcnc
            st = linuxcnc.stat()
            st.poll()
            homed_all = all(st.homed[:NJ])
            if not homed_all:
                # the REF has started -- from here, waiting for homed again
                # is waiting for it to FINISH, not for a stale "still ready"
                if not self._ac_saw_unhomed:
                    LOG.info('StartAC: REF in progress after the bank, '
                             'waiting for %s to come back',
                             self._ac_step.upper())
                self._ac_saw_unhomed = True
            ready = (st.task_state == linuxcnc.STATE_ON
                     and homed_all
                     and self._ac_saw_unhomed
                     and st.interp_state == linuxcnc.INTERP_IDLE
                     and st.inpos)
            if not ready:
                if time.time() - self._ac_wait_t0 > self.AC_READY_DEADLINE_S:
                    self._ac_stop('machine never came back ready after a bank '
                                  '(%.0f s) -- stopping rather than firing '
                                  'blind' % self.AC_READY_DEADLINE_S)
                    return
                QTimer.singleShot(1000, self._ac_try_issue)
                return
            self._ac_retry = 0
            LOG.info('StartAC: iteration %d, %s cycle (%d/%d consecutive '
                     'discards)', self._ac_iter, self._ac_step.upper(),
                     self._ac_discards, self.AC_CONVERGED)
            self._cal_run(self._ac_step)
        except Exception as e:
            self._ac_stop('sequencer error: %s' % e)

    def _ac_advance(self, banked):
        """Called once a cycle has banked or discarded."""
        if not getattr(self, '_ac_active', False):
            return
        self._ac_last_banked = bool(banked)
        if banked:
            self._ac_discards = 0
            self._ac_banked += 1
        else:
            self._ac_discards += 1
        if self._ac_step == 'a':
            self._ac_step = 'c'
        else:
            self._ac_step = 'a'
            self._ac_iter += 1
        self._ac_next()

    def _cal_after_cycle(self, which):
        if not getattr(self, '_ac_active', False):
            self._cal_buttons_busy(False)
        """Cycle finished. BANK an improvement without asking.

        Operator 2026-08-03: whenever a routine ends with an improvement --
        probe back at zero, puck re-probed if A or C actually moved -- bank
        it. There is no RECORD button in the path: head_zero.inc holds
        EYEBALLED numbers, so replacing them with measured ones is the whole
        point of running this.

        Banking is two halves and both are required:
          1. write the measured count into head_zero.inc, so it survives
          2. re-zero the axis IN THIS SESSION, so the DRO reads 0 at true
             perpendicular and the next +-45 pair is genuinely symmetric
        Doing only the first would leave the running session tilting about a
        stale zero until the next launch.
        """
        try:
            import linuxcnc
            c = linuxcnc.command()
            bkey, akey, mkey, ckey, ax, pin = self.CAL_AXIS[which]
            v = self._read_vars((bkey, akey, mkey, ckey))
            before, after = v.get(bkey), v.get(akey)
            moved = v.get(mkey, 0.0) > 0.5
            corr = v.get(ckey, 0.0)
            if before is None or after is None:
                LOG.error('Start%s: no before/after pair -- nothing banked', ax)
                self._ac_advance(False)
                return
            if not moved:
                msg = ('Start%s: %+.4f -> %+.4f mm, correction discarded, %s '
                       'unchanged -- nothing to bank' % (ax, before, after, ax))
                LOG.info(msg)
                if getattr(self, '_cal_status', None) is not None:
                    self._cal_status.setText(msg)
                self._ac_advance(False)
                return
            if abs(after) >= abs(before):
                # the g-code should already have reverted; belt and braces
                LOG.error('Start%s: %+.4f -> %+.4f mm is not better -- NOT '
                          'banking', ax, before, after)
                self._ac_advance(False)
                return
            if abs(corr) < 1e-9:
                LOG.info('Start%s: correction is zero -- nothing to bank', ax)
                self._ac_advance(False)
                return
            self._cal_bank(ax, corr, pin, ckey, before, after)
            self._ac_advance(True)
        except Exception as e:
            LOG.error('post-cycle banking failed: %s', e)

    def _cal_bank(self, ax, corr, pin, ckey, before, after):
        """Write the measured zero and make the machine adopt it now."""
        label = 'BANK %s' % ax
        try:
            import linuxcnc, shutil, time, re as _re
            c = linuxcnc.command()
            ps, new, mt_new, wi_new = self._enc_at_zero_counts(ax, corr)
            stamp = time.strftime('%Y%m%d-%H%M%S')
            shutil.copy2(self.HEAD_ZERO_INC,
                         '%s.bak-%s' % (self.HEAD_ZERO_INC, stamp))
            with open(self.HEAD_ZERO_INC) as f:
                txt = f.read()
            txt = _re.sub(r'^%s_MULTITURN\s*=.*$' % ax,
                          '%s_MULTITURN = %d' % (ax, mt_new), txt, flags=_re.M)
            txt = _re.sub(r'^%s_WITHIN\s*=.*$' % ax,
                          '%s_WITHIN    = %d' % (ax, wi_new), txt, flags=_re.M)
            with open(self.HEAD_ZERO_INC, 'w') as f:
                f.write(txt)
            LOG.info('%s: %+.4f mm -> %+.4f mm, %s corrected %+.6f deg, '
                     'head_zero.inc %s = %d / %d (was %d counts, now %d)',
                     label, before, after, ax, corr, ax, mt_new, wi_new,
                     ps, new)

            # clear the accumulator FIRST: from here on the machine's own zero
            # carries the correction, so leaving it set would double-count
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi('%s = 0' % ('#3069' if ax == 'A' else '#3070'))
            # back to MANUAL BEFORE the REF pulse: the brain re-homes the
            # joint in place, and homing only runs in MANUAL
            self._hand_back_manual(c, label)

            # re-zero the axis in this session. The brain re-reads the
            # absolute encoder against the file we just wrote, sets
            # ini.N.home_offset and re-homes the joint IN PLACE -- the same
            # path REF A/REF C uses every launch, no switch seeking.
            self.comp.getPin(pin).value = True
            QTimer.singleShot(1000, lambda p=pin: self._cal_ref_off(p))
            LOG.info('%s: REF %s pulsed -- brain will re-read and re-home %s '
                     'in place so the DRO reads 0 at true perpendicular',
                     label, ax, ax)
            # Say BOTH numbers. The cycle delta and the angle being banked are
            # different quantities -- the bank carries every bite applied
            # since the last bank -- and printing only the delta made a
            # correct 1.22 deg bank look like it had invented 1 deg from a
            # 0.156 mm measurement.
            # Say the lockout too: the REF unhomes A/C while it reads, so for
            # ~15 s every homed-gated button refuses. Unexplained, that reads
            # as a fault.
            # ANGLE FIRST. The toast clips a long message, and with the mm
            # delta leading, the banked DEGREES fell off the end -- which is
            # how a -0.318 deg C bank got read back as "2.145" (that was dX in
            # mm). The number that matters cannot be the one that gets cut.
            msg = ('%s BANKED %+.4f deg | %s zero %d / %d | this cycle '
                   '%+.4f -> %+.4f mm | re-homing %s, ~15 s unhomed'
                   % (ax, corr, ax, mt_new, wi_new, before, after, ax))
            c.error_msg(msg)
            if getattr(self, '_cal_status', None) is not None:
                self._cal_status.setText(msg)
        except Exception as e:
            LOG.error('%s failed: %s', label, e)

    def _cal_ref_off(self, pin):
        try:
            self.comp.getPin(pin).value = False
        except Exception:
            pass

    def _enc_at_zero_counts(self, ax, deg):
        """THE number, computed in ONE place.

        head_zero.inc stores PS, the absolute count at the declared zero;
        machine angle is (PE - PS) scaled by gear and 2^26 (manual 6.12.6).
        A correction of `deg` puts true zero at PS + SIGN*deg/360*R*GEAR.

        The MEASURED ZERO panel and the banker both call this, so the count on
        screen IS the count written to the parameter file. Two separate
        computations would have been free to drift apart.

        Returns (ps_old, ps_new, multiturn, within).
        """
        import re as _re
        with open(self.HEAD_ZERO_INC) as f:
            txt = f.read()
        mt = _re.search(r'^%s_MULTITURN\s*=\s*(-?\d+)' % ax, txt, _re.M)
        wi = _re.search(r'^%s_WITHIN\s*=\s*(-?\d+)' % ax, txt, _re.M)
        if not (mt and wi):
            raise RuntimeError('%s_MULTITURN/_WITHIN missing from head_zero.inc'
                               % ax)
        ps = int(mt.group(1)) * self.R_COUNTS + int(wi.group(1))
        gear = self._head_gears()[ax]
        new = int(round(ps + self.HEAD_SIGN[ax] * deg / 360.0
                        * self.R_COUNTS * gear))
        m = new // self.R_COUNTS
        return ps, new, m, new - m * self.R_COUNTS

    def _enc_at_zero(self, ax, deg):
        """Display form of _enc_at_zero_counts: multiturn / within."""
        try:
            _ps, _new, m, w = self._enc_at_zero_counts(ax, deg)
            return '%d / %d' % (m, w)
        except Exception as e:
            LOG.error('enc-at-zero %s failed: %s', ax, e)
            return '?'

    def _read_vars(self, keys):
        out = {}
        try:
            with open(self.VAR_FILE) as f:
                for line in f:
                    p = line.split()
                    if len(p) == 2 and p[0] in keys:
                        out[p[0]] = float(p[1])
        except Exception as e:
            LOG.error('var read failed: %s', e)
        return out

    CAL_MSG = {
        'puck': 'StartPuck running: top, then 8 edges. Result lands in the '
                'three boxes above when the cycle ends.',
        'a':    'StartA running: 4 wall touches at -30 and -65 with an A '
                'correction between them, then a fresh puck find so the zero '
                'matches the corrected A. If dY improved it writes '
                'head_zero.inc by itself.',
        'c':    'StartC: with no reference it parks at A-45 for you to jog; '
                'with a jog pending it captures and measures; otherwise it '
                'just measures. CLEAR C REF to re-teach.',
        'ac':   'StartAC running: A, then C, then a fresh puck find, banking '
                'each correction as it arrives so the next measurement starts '
                'from a real zero. Stops on 4 consecutive discards.',
        'goto': 'ZERO: puck centre, tip 5 mm above the top, A and C straight.',
        'probeheight': 'SET PROBE HEIGHT: jog the spindle to where every '
            'tool probe should START, then press. Records G30 and '
            'recomputes the plunge down to 1 mm above the Z limit. Any '
            'tool may be in the spindle. Moves nothing.',
        'storeresults': 'STORE RESULTS: checks PB has all four numbers -- '
            'probe XY, probe height, nose, plunge -- then CLEARS every '
            'tool length in the rack. They were measured against the old '
            'setter position and are all wrong now.',
        'measureall': 'MEASURE ALL TOOLS: fetches every tool the rack map '
            'lists and touches it off, one at a time, then leaves the '
            'spindle empty. Start empty. This one runs the changer.',
        'shoulder': 'SHOULDER: recording the setter position into G30 at puck '
                    'top +100, sending the 185 mm plunge limit, then running '
                    "PB's spindle-nose probe at X-20. Spindle must be EMPTY.",
        'cleft': 'C LEFT: parking on the A-45 probe pose, puck up. Check the '
                 'tip is in the ballpark.',
        'cright': 'C RIGHT: parking on the A+45 probe pose, puck up. Check the '
                  'tip is in the ballpark.',
    }

    HEAD_ZERO_INC = '/home/brains/Documents/ned/configs/params/head_zero.inc'
    NED_PARAMS_SH = '/home/brains/Documents/ned/tools/live/ned_params.sh'
    R_COUNTS = 67108864          # 2^26 counts per motor rev (drive absolute)
    HEAD_SIGN = {'A': -1, 'C': 1}

    def _head_gears(self):
        """Gear ratios come from ned_params.sh, the SSOT (CLAUDE.md rule 11) --
        read, never copied."""
        g = {}
        import re as _re
        with open(self.NED_PARAMS_SH) as f:
            for line in f:
                m = _re.match(r'\s*GEAR_([AC])\s*=\s*([0-9.]+)', line)
                if m:
                    g[m.group(1)] = float(m.group(2))
        if set(g) != {'A', 'C'}:
            raise RuntimeError('GEAR_A/GEAR_C not found in ned_params.sh')
        return g

    def _zclamp_apply_rate_cap(self):
        """Size the MPG count cap so a spun wheel cannot demand more than
        ZCLAMP_MAX_MMPS with the step size currently selected."""
        step = getattr(self, '_jog_inc_mm', 0.1) or 0.1
        cps = int(self.ZCLAMP_MAX_MMPS / step * self.MPG_CPD)
        cps = max(20, min(cps, self.MPG_CPS_NORMAL))
        for ax in 'xyz':
            os.system('timeout 3 halcmd setp jogblock.%s.max-cps %d '
                      '>/dev/null 2>&1' % (ax, cps))
        LOG.info('ZCLAMP: MPG rate cap %d counts/s for a %.3f mm step '
                 '(<= %.1f mm/s demand)', cps, step, self.ZCLAMP_MAX_MMPS)
        return cps

    def _zclamp_release_rate_cap(self):
        for ax in 'xyz':
            os.system('timeout 3 halcmd setp jogblock.%s.max-cps %d '
                      '>/dev/null 2>&1' % (ax, self.MPG_CPS_NORMAL))
        LOG.info('ZCLAMP: MPG rate cap back to %d counts/s (2 turns/s)',
                 self.MPG_CPS_NORMAL)

    def _zclamp_toggle(self, checked):
        btn = self._zclamp_widgets.get('btn')
        if not checked:
            self._zclamp_disable('clamp off', err=False)
            return
        self._zclamp_low_changed()
        if self._zclamp_low is None:
            self._zclamp_disable('cannot enable: Zlow is not set', err=True)
            return
        z = self._zclamp_z()
        if z is None:
            self._zclamp_disable('cannot enable: Z position unreadable', err=True)
            return
        if z < self._zclamp_low or z > self._zclamp_high:
            self._zclamp_disable(
                'cannot enable: Z is at %.3f, OUTSIDE the clamp [%.3f .. %.3f]. '
                'Jog Z back inside first.' % (z, self._zclamp_low,
                                              self._zclamp_high), err=True)
            return
        # ENFORCEMENT: hand the floor to LinuxCNC (operator 2026-08-02: "bring
        # the soft limit to the clamp so that lcnc takes over"). ini.2.min_limit
        # is writable at runtime and lands straight in joint 2's
        # min_position_limit, so LinuxCNC itself refuses jogs past it -- MPG
        # wheel, increment buttons and g-code alike -- with its own error. No
        # custom HAL gate to keep in step.
        backstop = self._zclamp_low - self.ZCLAMP_BACKSTOP
        if backstop < self._zclamp_floor_default:
            backstop = self._zclamp_floor_default
        if os.system('timeout 3 halcmd setp ini.2.min_limit %.4f '
                     '>/dev/null 2>&1' % backstop) != 0:
            self._zclamp_disable('could not write ini.2.min_limit', err=True)
            return
        try:
            # feed the comparator Zlow + margin: blocking starts just above
            # the floor so the few um of servo settle still lands at or above
            # the number the operator typed
            # the profile decelerates onto this number, so send it raw
            self.comp.getPin('zclamp-low').value = self._zclamp_low
            self.comp.getPin('zclamp-enable').value = True
        except Exception as e:
            os.system('timeout 3 halcmd setp ini.2.min_limit %.4f '
                      '>/dev/null 2>&1' % self._zclamp_floor_default)
            self._zclamp_disable('clamp HAL pins unavailable: %s' % e, err=True)
            return
        self._zclamp_on = True
        edit = self._zclamp_widgets.get('edit')
        if edit is not None:
            # the floor must not move under an armed clamp
            edit.setReadOnly(True)
            edit.setStyleSheet('background: rgb(60,60,60); color: rgb(150,150,150);')
        if btn is not None:
            btn.setText('ENABLED')
            btn.setStyleSheet(self.ZCLAMP_ON_QSS)
        self._zclamp_say('ENABLED: Z down-jog decelerates onto %.3f. Up and '
                         'all other axes stay free.' % self._zclamp_low)
        LOG.info('ZCLAMP ENABLED: Z held in [%.4f .. %.4f], Z now %.4f',
                 self._zclamp_low, self._zclamp_high, z)

    def _zclamp_tick(self):
        """STATUS ONLY -- it must NEVER disarm itself.

        Operator correction 2026-08-02: "I DIDN'T SAY DISABLE IF Z LEAVES. I
        SAID REVERT TO DISABLE IF Z starts OUTSIDE THE CLAMP AND SOMEONE
        CLICKS ENABLE ... WHEN IT IS NOT VIOLATED AT THE START, THE CLAMP HAS
        one job. TO PREVENT IT FROM LEAVING."

        The outside-the-range test belongs at ARM time and nowhere else. An
        armed clamp that disarms at the boundary would drop the guard at the
        exact moment it is doing its job. So while armed this only reports:
        the HAL gate (jogblock.z.lim-neg) does the work, and if Z ends up
        below the floor by some other means (MDI, which is deliberately not
        clamped) the gate keeps blocking DOWN jogs while UP jogs still pass,
        which is how the operator gets back out.
        """
        if not self._zclamp_on:
            return
        z = self._zclamp_z()
        if z is None:
            return
        if z < self._zclamp_low:
            self._zclamp_say('ARMED - Z %.3f is below the floor %.3f: DOWN '
                             'jogs blocked, jog UP to get back inside'
                             % (z, self._zclamp_low))
        else:
            self._zclamp_say('ARMED - Z %.3f held in [%.3f .. %.3f]'
                             % (z, self._zclamp_low, self._zclamp_high))

    def _number_badges(self):
        win = self.window()
        if win is None:
            return
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (QAbstractButton, QAbstractSlider,
                                           QComboBox, QLabel, QLineEdit)
            targets = []
            for w in win.findChildren(QWidget):
                n = w.objectName()
                if not n or n.startswith('qt_'):
                    continue
                cls = type(w).__name__
                interactive = isinstance(w, (QAbstractButton, QAbstractSlider,
                                             QLineEdit, QComboBox))
                labelish = ('Label' in cls or 'DRO' in cls or 'Entry' in cls
                            or 'Bar' in cls)
                if interactive or labelish:
                    targets.append((n, w))
            # deterministic numbering: sorted by objectName -- stable for a
            # given PB build; the map file is the per-launch truth
            targets.sort(key=lambda t: t[0])
            lines = []
            for i, (n, w) in enumerate(targets, 1):
                b = QLabel(str(i), w)
                b.setStyleSheet('background: rgba(255,200,0,190); '
                                'color: black; font: 7pt;')
                b.setAttribute(Qt.WA_TransparentForMouseEvents)
                b.adjustSize()
                b.move(0, 0)
                b.raise_()   # above sibling decorations
                b.show()
                txt = w.text().replace('\n', ' ') if hasattr(w, 'text') else ''
                lines.append('{}\t{}\t{}\t{}'.format(
                    i, n, type(w).__name__, txt))
            with open('/home/brains/Documents/ned/gui_map.txt', 'w') as f:
                f.write('# gui_map -- badge number -> widget (regenerated '
                        'every launch by ned_controls._number_badges)\n')
                f.write('\n'.join(lines) + '\n')
            LOG.info('GUI numbering: %d controls badged -> ned/gui_map.txt',
                     len(targets))
        except Exception as e:
            LOG.error('GUI numbering failed: %s', e)

    # ---- JOG & PRESETS panel ----------------------------------------------
    # House MDI pattern (from the archived ned_moves panel + dros_xyzac zero
    # buttons): guard (ON + fully homed + interp idle + inpos + no homing) ->
    # switch to MDI -> CONFIRM task_mode == MDI by POLLING (ned_brain
    # auto-restores MANUAL on an edge; losing that race paints "Must be in
    # MDI mode" toasts) -> ONE c.mdi() FIRE-AND-FORGET. NEVER wait_complete()
    # around motion: it times out silently after ~5 s and a mode switch
    # ABORTS in-flight motion. The brain hands back MANUAL + teleop ~1 s
    # after motion truly completes.
    #
    # RELATIVE strategy (typed REL moves and the Z +10 preset): this panel
    # NEVER issues G91. Relative intent is converted to an ABSOLUTE target
    # (current work position + delta, house offset math) and sent as one
    # G90 G1 line -- an abort partway can never leave G91 modal.

    _JOG_WIDGETS = ('jp_slow', 'jp_medium', 'jp_fast', 'jp_feed_readout',
                    'jp_p_xy0', 'jp_p_xyz0', 'jp_p_z0',
                    'jp_p_zp10', 'jp_p_xy0z10', 'jp_p_a0c0',
                    'jp_in_x', 'jp_in_y', 'jp_in_z', 'jp_in_a', 'jp_in_c',
                    'jp_clear', 'jp_go_abs', 'jp_go_rel',
                    'jp_status_dot', 'jp_status_text', 'jp_stop')
    # jp_stop is HIDDEN at wire time -- the main movement panel's STOP is
    # the one STOP (operator 2026-08-02 13:44: "the stop button in that jog
    # panel is redundant"). Kept wired so nothing else has to change.

    # preset -> (label, ((axis, work-target), ...) or None, zlift?)
    # All presets are ABSOLUTE work-coordinate targets except Z +10, which
    # is computed from the CURRENT work Z at click time (zlift=True).
    _JOG_PRESETS = (
        ('jp_p_xy0',    'X0 Y0',     (('x', 0.0), ('y', 0.0)),              False),
        ('jp_p_xyz0',   'X0 Y0 Z0',  (('x', 0.0), ('y', 0.0), ('z', 0.0)),  False),
        ('jp_p_z0',     'Z0',        (('z', 0.0),),                         False),
        ('jp_p_zp10',   'Z10',       None,                                  True),
        ('jp_p_xy0z10', 'X0 Y0 Z10', (('x', 0.0), ('y', 0.0), ('z', 10.0)), False),
        ('jp_p_a0c0',   'A0 ' + ROT.upper() + '0',
         (('a', 0.0), ('c', 0.0)),                                      False))

    _JOG_MOVERS = ('jp_p_xy0', 'jp_p_xyz0', 'jp_p_z0', 'jp_p_zp10',
                   'jp_p_xy0z10', 'jp_p_a0c0')   # lock these while moving

    _jp_w = {}   # class default so handlers never AttributeError pre-wire
    _ac_locked = {'a': False, 'c': False}   # LOCK A / LOCK C state


    def _jog_page_takeover(self):
        # v2 port target (operator 2026-08-02): the panel REPLACES the stock
        # jog arrow buttons in the sidebar JOG page. jogDisplay is unique
        # (probe_basic.ui:22575); its page layout is a QVBoxLayout
        # (probe_basic.ui:22561); replaceWidget per the house pattern.
        from PySide6.QtWidgets import QWidget as _QW
        win = self.window()
        jd = win.findChild(_QW, 'jogDisplay') if win else None
        panel = self.findChild(_QW, 'jp_panel')
        if jd is None or panel is None or jd.parentWidget() is None \
           or jd.parentWidget().layout() is None:
            LOG.error('JOG page takeover FAILED: jogDisplay/jp_panel/layout '
                      'not found -- stock jog page left as-is')
            return
        lay = jd.parentWidget().layout()
        if self.layout() is not None:
            self.layout().removeWidget(panel)
        lay.replaceWidget(jd, panel)
        jd.hide()
        LOG.info('JOG page takeover: jogDisplay (stock jog arrows) replaced '
                 'by jp_panel at 200x730; ned tab page now empty')

    def _jog_wire(self):
        try:
            from PySide6.QtWidgets import QButtonGroup
            w = {}
            missing = []
            for name in self._JOG_WIDGETS:
                x = self.findChild(QWidget, name)
                if x is None:
                    missing.append(name)
                else:
                    w[name] = x
            # DIRECT REFS, kept for the panel's whole life: after
            # _jog_page_takeover reparents jp_panel into the stock JOG
            # page, self.findChild() can NO LONGER see these widgets --
            # click-time lookups through it silently no-op'd (operator's
            # dead CLEAR, 2026-08-02 12:5x). Handlers use THIS dict only.
            self._jp_w = w
            if missing:
                LOG.error('JOG panel: %d missing: %s', len(missing),
                          ', '.join(missing))
            # panel state
            # MERGE, don't reset (advisor c-nit): a lock toggled before
            # the jog panel wires must survive this line
            base = {'a': False, 'c': False}
            base.update(getattr(self, '_ac_locked', {}) or {})
            self._ac_locked = base
            self._jog_go_ok = False    # >=1 typed field parses as a number
            self._jog_idle = None      # None = unknown (before first poll)
            self._jog_stat_nml = None  # status-strip stat channel
            self._jog_status_warned = False
            self._jog_last_state = None
            # SPEED toggles: exclusive group, amber = selected; every toggle
            # updates the live readout. Selection persists between moves.
            self._jog_speed_grp = QButtonGroup(self)
            self._jog_speed_grp.setExclusive(True)
            for key in ('slow', 'medium', 'fast'):
                b = w.get('jp_' + key)
                if b is None:
                    continue
                self._jog_speed_grp.addButton(b)
                b.toggled.connect(
                    lambda on, k=key: on and self._jog_set_speed(k))
            # PRESETS: execute IMMEDIATELY on click, no GO.
            for name, label, vals, zlift in self._JOG_PRESETS:
                if w.get(name) is not None:
                    w[name].clicked.connect(
                        lambda _=False, l=label, v=vals, z=zlift:
                        self._jog_preset(l, v, z))
            # TYPED MOVE: GOs gate on any-field-parses; Enter = GO ABS;
            # fields retain their values after a move (no auto-clear).
            for ax in 'xyzac':
                e = w.get('jp_in_' + ax)
                if e is None:
                    continue
                e.textChanged.connect(
                    lambda _='', s=self: s._jog_entry_changed())
                e.returnPressed.connect(
                    lambda s=self: s._jog_enter())
            if w.get('jp_clear') is not None:
                w['jp_clear'].clicked.connect(self._jog_clear)
            if w.get('jp_go_abs') is not None:
                w['jp_go_abs'].clicked.connect(
                    lambda _=False: self._jog_go(rel=False))
            if w.get('jp_go_rel') is not None:
                w['jp_go_rel'].clicked.connect(
                    lambda _=False: self._jog_go(rel=True))
            if w.get('jp_stop') is not None:
                w['jp_stop'].clicked.connect(self._jog_stop)
            # SOFT-LIMIT table: [AXIS_*] MIN/MAX_LIMIT via linuxcnc.ini at
            # panel init (house pattern, dros_xyzac.py). NOTE: LinuxCNC also
            # exposes runtime-WRITABLE ini.N.min_limit/max_limit HAL pins
            # that can override these live; those pins are not readable
            # here (no HAL in GUI code), so this table is the static INI
            # truth -- the planner still hard-rejects beyond the live pins.
            self._jog_limits = None
            self._jog_limits_load()
            # STATUS STRIP: NML-only poll (no HAL), 400 ms; drives the dot,
            # the state text, STOP arming and the moving-lockout.
            self._jog_status_timer = QTimer(self)
            self._jog_status_timer.timeout.connect(self._jog_status_tick)
            # 150 ms, not 400: the enable-lockout is driven by THIS tick,
            # so a slow tick leaves presets/GOs disabled for up to a tick
            # after motion ends and SILENTLY swallows the next click
            # (measured 2026-08-02: every click ~0.3 s after a move died).
            self._jog_status_timer.start(150)
            # init the readout from the default selection (jp_medium ships
            # checked in the .ui, so toggled won't refire it here) and the
            # GO gate from the (empty) fields
            self._jog_set_speed(self._jog_speed)
            self._jog_entry_changed()
            LOG.info('JOG panel: %d widgets wired', len(w))
        except Exception as e:
            LOG.error('JOG panel wiring failed: %s', e)

    def _jog_limits_load(self):
        try:
            import linuxcnc
            ini_path = os.getenv('INI_FILE_NAME')
            if not ini_path:
                raise RuntimeError('INI_FILE_NAME not set')
            ini = linuxcnc.ini(ini_path)
            lims = {}
            for ax in 'xyzac':
                sec = 'AXIS_' + _AXL(ax)
                lo = ini.find(sec, 'MIN_LIMIT')
                hi = ini.find(sec, 'MAX_LIMIT')
                if lo is None or hi is None:
                    raise RuntimeError('[%s] MIN/MAX_LIMIT missing' % sec)
                lims[ax] = (float(lo), float(hi))
            self._jog_limits = lims
            LOG.info('JOG panel: soft limits loaded: %s',
                     ' '.join('%s[%g..%g]' % (a.upper(), lo, hi)
                              for a, (lo, hi) in sorted(lims.items())))
        except Exception as e:
            self._jog_limits = None
            LOG.error('JOG panel: soft-limit table unavailable (%s) -- '
                      'pre-check DISABLED, planner limits still apply', e)

    def _jog_set_speed(self, key):
        self._jog_speed = key
        lin, ang = JOG_SPEEDS[key]
        lbl = self._jp_w.get('jp_feed_readout')
        if lbl is not None:
            # short face: 14pt Bebas clipped the long form at 200 px
            lbl.setText('F{:g} · {:g}°'.format(lin, ang))
        LOG.info('JOG speed -> %s (F%g mm/min, %g deg/min)',
                 key.upper(), lin, ang)

    # ==================================================================
    # AXIS-LETTER RELABEL  (generic; no widget list, no hardcoded captions)
    # ==================================================================
    # Every .ui in this config was authored for the XYZAC machine, so the
    # second rotary is spelled C throughout -- captions, placeholders,
    # tooltips, group titles, the DRO row. Which axis that slot ACTUALLY
    # drives is a launch-time fact (ROT, from NED_MODE). Rather than name
    # the widgets that need changing -- a list that goes stale the moment
    # anyone adds a button -- walk the whole tree and rewrite the letter.
    #
    # The token rule is what makes a blind rewrite safe: a C that is not
    # preceded by a letter or digit and not followed by a letter. That is
    # every axis use (C, C0, "C . deg", "A0 C0", "LOCK C") and none of the
    # words -- CLEAR, CANCEL, COOLANT, WCS, MDI keep their C.
    #
    # Reversible by construction: launch -xyzac and ROT is 'c', the pattern
    # rewrites C to C, and nothing moves.
    _AXWORD = re.compile(r'(?<![A-Za-z0-9])C(?![A-Za-z])')
    _TEXT_PROPS = ('text', 'placeholderText', 'toolTip', 'title',
                   'windowTitle')

    def _relabel_axis_letters(self, root=None):
        """Repoint every visible C at the axis the rotary slot really is."""
        want = ROT.upper()
        if want == 'C':
            return 0                       # -xyzac: the .ui is already right
        from PySide6.QtWidgets import QWidget
        root = root if root is not None else self.window()
        if root is None:
            return 0
        n = 0
        for w in [root] + root.findChildren(QWidget):
            # A control that CANNOT act keeps its original name. Those are
            # the head-C cycles: they really do mean C, they are disabled
            # because C is parked, and renaming them to B would promise a
            # calibration that does not exist. Tagged at disable time, so
            # this stays a rule rather than a list.
            if w.property('ned_keep_letter'):
                continue
            for prop in self._TEXT_PROPS:
                get, st = 'setX', None
                try:
                    cur = w.property(prop)
                except Exception:
                    continue
                if not isinstance(cur, str) or not cur:
                    continue
                new = self._AXWORD.sub(want, cur)
                if new == cur:
                    continue
                try:
                    w.setProperty(prop, new)
                    n += 1
                except Exception:
                    pass
        LOG.info('AXIS RELABEL: %d caption(s) C -> %s', n, want)
        return n

    def _xyzab_relabel_gui(self):
        # Order matters: tag-then-relabel. The disable pass marks the
        # controls whose letter must survive, so the generic walk can skip
        # them without knowing their names.
        win = self.window()
        if win is None:
            return
        d = 0
        for b in win.findChildren(QWidget):
            t = (b.property('text') or '') if hasattr(b, 'text') else ''
            if not isinstance(t, str):
                t = ''
            # head-C calibration: any control whose caption names a C cycle.
            if re.search(r'(?<![A-Za-z0-9])C(?![A-Za-z])', t) and (
                    'START' in t.upper() or 'REF' in t.upper()
                    or 'LEFT' in t.upper() or 'RIGHT' in t.upper()):
                b.setProperty('ned_keep_letter', True)
                b.setEnabled(False)
                b.setToolTip('Disabled: C is parked at zero and clamped in '
                             'this mode; the rotary is %s.' % ROT.upper())
                d += 1
        LOG.info('AXIS RELABEL: %d head-C control(s) pinned and disabled', d)
        self._relabel_axis_letters()

    def _jog_work_pos(self, s, ax):
        # current WORK coordinate of axis letter ax (house offset math)
        i = JOG_AXIS_IDX[ax]
        return (s.actual_position[i] - s.g5x_offset[i]
                - s.g92_offset[i] - s.tool_offset[i])

    def _jog_preset(self, label, vals, zlift):
        # Presets are ALWAYS absolute work-coordinate G90 G1 moves at the
        # selected speed, and execute IMMEDIATELY on click. Z +10 is
        # relative-SAFE: current work Z is read from stat and the ABSOLUTE
        # target commanded (never G91, never absolute Z10). A/C locks do
        # NOT gate any move here -- locks only remove axes from MPG cycling.
        try:
            import linuxcnc
            if zlift:
                # machine frame (advisor V2): same lie as GO REL; a false
                # base inside limits goes to the WRONG Z with no error
                s = linuxcnc.stat()
                s.poll()
                z = s.actual_position[2]
                vals = (('z', z + 10.0),)
                LOG.info('Z +10: machine Z %.4f -> G53 target Z%.4f',
                         z, z + 10.0)
            self._jog_issue(label, list(vals), g53=zlift)
        except Exception as e:
            LOG.error('%s preset failed: %s', label, e)

    def _jog_clear(self):
        n = 0
        for ax in 'xyzac':
            w = self._jp_w.get('jp_in_' + ax)
            if w is not None:
                w.clear()
                n += 1
        if n:
            LOG.info('TYPED MOVE fields cleared (%d fields)', n)
        else:
            LOG.error('TYPED MOVE clear: NO fields found -- panel refs broken')

    # ---- typed-move gating -------------------------------------------------
    def _jog_parse_fields(self):
        # (vals, bad): vals = [(axis, float)] of the parsable non-blank
        # fields; bad = [(axis, text)] of non-blank fields that do NOT
        # parse. Blank fields are OMITTED -- never sent as 0.
        vals, bad = [], []
        for ax in 'xyzac':
            w = self._jp_w.get('jp_in_' + ax)
            txt = (w.text().strip() if w is not None else '')
            if not txt:
                continue
            try:
                vals.append((ax, float(txt)))
            except ValueError:
                bad.append((ax, txt))
        return vals, bad

    def _jog_entry_changed(self):
        vals, _bad = self._jog_parse_fields()
        self._jog_go_ok = bool(vals)
        self._jog_apply_enables()

    def _jog_enter(self):
        # Enter in any field fires GO ABS -- but only when GO ABS would be
        # clickable (>=1 field parses AND the machine is not mid-move).
        b = self._jp_w.get('jp_go_abs')
        if b is not None and b.isEnabled():
            self._jog_go(rel=False)

    def _jog_apply_enables(self):
        # idle: None = unknown (status poll not landed/failed) -> leave the
        # panel USABLE; the _jog_issue guards still refuse loudly. False =
        # motion running -> presets + GOs locked, STOP armed.
        idle = self._jog_idle is not False
        for name in self._JOG_MOVERS:
            b = self._jp_w.get(name)
            if b is not None and b.isEnabled() != idle:
                b.setEnabled(idle)
        for name in ('jp_go_abs', 'jp_go_rel'):
            b = self._jp_w.get(name)
            want = idle and self._jog_go_ok
            if b is not None and b.isEnabled() != want:
                b.setEnabled(want)
        b = self._jp_w.get('jp_stop')
        if b is not None and b.isVisible():
            b.hide()          # redundant with the main movement STOP

    def _jog_flash(self, ax):
        # soft-limit reject / bad value: flash the axis field red. Setting
        # the widget's own stylesheet overrides the jp_panel QSS; clearing
        # it restores the panel look.
        w = self._jp_w.get('jp_in_' + ax)
        if w is None:
            return
        # metrics mirror the PB-native dataField QLineEdit QSS (1px border,
        # radius 4, padding-right 2px, 14pt Bebas) -- a mismatched mirror
        # makes fields resize during the flash
        w.setStyleSheet('background: rgb(120,60,60); color: white; '
                        'border: 1px solid rgb(200,80,80); '
                        'border-radius: 4px; padding-right: 2px; '
                        'font: 14pt "Probe Basic Bebas Mono";')
        QTimer.singleShot(700, lambda: w.setStyleSheet(''))

    # ---- UNITS IN/MM (settings tab) ---------------------------------------

    # PB-native active treatment: the SAME checked gradient every other
    # selection button on the SETTINGS page wears (probe_basic_dark.qss
    # :126-128); text/font cascade from the global QPushButton rules
    _UNITS_ON = ('background: qlineargradient(spread:pad, x1:0, y1:0, '
                 'x2:0, y2:1, stop:0 rgba(85, 85, 238, 255), '
                 'stop:0.544974 rgba(90, 91, 239, 255), '
                 'stop:1 rgba(126, 135, 243, 255));')

    def _units_panel_install(self):
        # PB has NO in/mm control -- units are the G20/G21 modal only
        # (status labels merely display them). Two big buttons in the
        # settings tab right column (widget_51, QVBoxLayout, verified in
        # probe_basic.ui). Active unit stays amber via a 500 ms stat poll
        # (own linuxcnc.stat channel -- NEVER hal.get_value in GUI code).
        try:
            from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout,
                                           QLabel, QPushButton)
            from PySide6.QtWidgets import QWidget as _QW
            win = self.window()
            host = win.findChild(_QW, 'widget_51') if win else None
            if host is None or host.layout() is None:
                LOG.error('UNITS panel: settings host widget_51 not found '
                          '-- NOT installed')
                return
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtWidgets import QSizePolicy as _QSP
            fr = QFrame()
            fr.setObjectName('ned_units_frame')
            # mirror rpm_type_setting_frame (probe_basic.ui:19875-19951):
            # fixed 530x100, default margins, 16pt Bebas centred header,
            # 12-spacing button row
            fr.setFixedSize(530, 100)
            v = QVBoxLayout(fr)
            lab = QLabel('UNITS')
            lab.setStyleSheet('QLabel{ color: rgb(238, 238, 236); '
                              'font: 16pt "Probe Basic Bebas Mono"; }')
            lab.setAlignment(_Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumSize(100, 25)
            lab.setMaximumHeight(25)
            v.addWidget(lab)
            row = QHBoxLayout()
            row.setSpacing(12)
            row.setContentsMargins(3, 3, 3, 3)
            self._units_btns = {}
            for key, txt in (('in', 'IN'), ('mm', 'MM')):
                b = QPushButton(txt)
                b.setObjectName('ned_units_' + key)
                b.setMaximumHeight(40)
                b.setSizePolicy(_QSP.Preferred, _QSP.Preferred)
                b.clicked.connect(lambda _=False, k=key: self._units_click(k))
                row.addWidget(b)
                self._units_btns[key] = b
            v.addLayout(row)
            host.layout().insertWidget(3, fr)
            self._units_stat = None
            self._units_timer = QTimer(self)
            self._units_timer.timeout.connect(self._units_poll)
            self._units_timer.start(500)
            LOG.info('UNITS panel installed in settings tab '
                     '(IN/MM -> G20/G21)')
        except Exception as e:
            LOG.error('UNITS panel FAILED: %s', e)

    def _units_click(self, key):
        # G20/G21 via MDI, same LOUD gate family as _jog_issue. No homed
        # requirement (units switch moves nothing), but interp must be
        # IDLE: the MDI mode switch aborts in-flight motion (house rule).
        label = 'UNITS %s' % key.upper()
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON:
                c.error_msg('%s refused: machine is not ON' % label)
                LOG.error('%s refused: machine is not ON', label)
                return
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos \
               or any(s.joint[j]['homing'] for j in range(NJ)):
                c.error_msg('%s refused: machine is busy' % label)
                LOG.error('%s refused: machine busy', label)
                return
            if not self._take_mdi(c, label):
                return
            c.mdi('G20' if key == 'in' else 'G21')
            self._hand_back_manual(c, label)
            LOG.info('UNITS -> %s issued',
                     'G20 (inch)' if key == 'in' else 'G21 (mm)')
        except Exception as e:
            LOG.error('%s failed: %s', label, e)

    def _units_poll(self):
        try:
            import linuxcnc
            if self._units_stat is None:
                self._units_stat = linuxcnc.stat()
            s = self._units_stat
            s.poll()
            active = 'in' if s.program_units == 1 else 'mm'
            for key, b in self._units_btns.items():
                style = self._UNITS_ON if key == active else ''
                if b.styleSheet() != style:
                    b.setStyleSheet(style)
        except Exception:
            self._units_stat = None   # linuxcnc down; retry next tick

    def _jp_dump_coords(self):
        # one-shot INFO dump of global click coordinates for every JOG
        # panel + UNITS widget -- feeds the click-test harness. Runs at
        # +9 s (after takeover + units install have settled).
        try:
            items = dict(self._jp_w)
            items.update(getattr(self, '_units_btns', {}))
            for name in sorted(items):
                w = items[name]
                try:
                    c = w.mapToGlobal(w.rect().center())
                    LOG.info('JPCOORD %s %d %d vis=%d', name, c.x(), c.y(),
                             int(w.isVisible()))
                except Exception as e:
                    LOG.error('JPCOORD %s FAILED: %s', name, e)
        except Exception as e:
            LOG.error('JPCOORD dump failed: %s', e)

    def _jog_go(self, rel):
        # GO ABS ("move to"): the typed values ARE the G90 work targets.
        # GO REL ("move by"): deltas from the current position, converted
        # to absolute targets (current work pos + delta) and STILL sent as
        # one G90 line -- G91 never enters the modal state (class comment).
        # Blank fields are omitted; fields RETAIN their values afterward.
        try:
            import linuxcnc
            label = 'GO REL' if rel else 'GO ABS'
            vals, bad = self._jog_parse_fields()
            if bad:
                for ax, txt in bad:
                    self._jog_flash(ax)
                linuxcnc.command().error_msg(
                    '%s: bad %s value %r' % (label, bad[0][0].upper(),
                                             bad[0][1]))
                LOG.error('%s: bad field(s): %s', label,
                          ', '.join('%s=%r' % (a.upper(), t)
                                    for a, t in bad))
                return
            if not vals:
                linuxcnc.command().error_msg(
                    '%s: no axis values entered' % label)
                LOG.error('%s: no axis values entered', label)
                return
            if rel:
                # MACHINE-frame math (advisor V1): stat's OFFSETS are
                # structurally untrustworthy -- a task mode switch aborts
                # the interp_list and eats the queued G5X status update,
                # so g5x can read zeros while G54 is live (+50 up became
                # machine -881 tonight). stat's POSITIONS are servo truth.
                # delta + actual_position, issued as G53, never touches an
                # offset anywhere.
                s = linuxcnc.stat()
                s.poll()
                vals = [(ax, s.actual_position[JOG_AXIS_IDX[ax]] + v)
                        for ax, v in vals]
            self._jog_issue(label, vals, g53=rel)
        except Exception as e:
            LOG.error('GO failed: %s', e)

    def _jog_issue(self, label, vals, g53=False):
        # vals = [(axis letter, ABSOLUTE work target)]. Guards -> soft-limit
        # pre-check (REJECT, never clamp) -> MDI mode CONFIRMED by poll ->
        # ONE fire-and-forget mdi(). Refusals are LOUD: error toast + log
        # line + red field flash for a limit hit -- never a silent no-op.
        try:
            import linuxcnc
            import time
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON:
                c.error_msg('%s refused: machine is not ON' % label)
                LOG.error('%s refused: machine is not ON', label)
                return
            if not all(s.homed[:NJ]):
                c.error_msg('%s refused: machine not fully homed -- Home All'
                            ' (Homing menu) first, or launch with run5.sh'
                            ' resume' % label)
                LOG.error('%s refused: not fully homed', label)
                return
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos \
               or any(s.joint[j]['homing'] for j in range(NJ)):
                c.error_msg('%s refused: machine is busy (program/MDI '
                            'running or homing)' % label)
                LOG.error('%s refused: machine busy', label)
                return
            # DRO locks gate the MPG ONLY (operator 2026-08-06, supersedes
            # the 2026-08-02 typed-move gate that lived here): commanded
            # moves NEVER consult them -- the locks exist to stop
            # inadvertent pendant bumps, nothing else.
            # SOFT-LIMIT PRE-CHECK, machine coordinates: limits are machine-
            # frame, targets are work-frame -> machine target = work target
            # + (g5x + g92 + tool) offset (house math; XY G5x rotation not
            # modeled, same as every other panel). A violating move is
            # REJECTED -- never clamped silently.
            # pre-check ONLY machine-frame (g53) targets: they compare
            # against machine-frame limits exactly. Work-frame targets
            # CANNOT be pre-checked here -- the only offset source (stat)
            # lies (advisor V3), and a wrong pre-check is worse than none;
            # the planner enforces limits in the interp's true frame and
            # its refusal is loud.
            if self._jog_limits and g53:
                for ax, tw in vals:
                    i = JOG_AXIS_IDX[ax]
                    mt = tw
                    lo, hi = self._jog_limits[ax]
                    if mt < lo - 1e-6 or mt > hi + 1e-6:
                        self._jog_flash(ax)
                        c.error_msg(
                            '%s REJECTED: %s target %.3f (machine %.3f) '
                            'outside soft limits [%g .. %g]'
                            % (label, _AXL(ax), tw, mt, lo, hi))
                        LOG.error('%s REJECTED: %s work %.4f -> machine '
                                  '%.4f outside [%g .. %g]',
                                  label, _AXL(ax), tw, mt, lo, hi)
                        return
            words = ' '.join('{}{:.4f}'.format(_AXL(ax), v)
                             for ax, v in vals)
            lin, ang = JOG_SPEEDS[self._jog_speed]
            # pure-rotary line: LinuxCNC reads F as deg/min there; any
            # linear word present -> F is mm/min on the linear path
            feed = ang if all(ax in 'ac' for ax, _ in vals) else lin
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            # CONFIRM the mode actually landed: ned_brain hands MANUAL back
            # on its own edge; issuing before task is really in MDI loses
            # the race and paints 'Must be in MDI mode' error toasts.
            # RE-ASSERT, don't just wait: the brain hands MANUAL back ~1 s
            # after the previous move finishes, so a click landing in that
            # window had its MDI request overwritten and the old code simply
            # gave up ("task_mode never reached MDI", caught by the
            # unattended GUI campaign 2026-08-02 16:47:50 -- an intermittent
            # dead preset, exactly the kind of thing that erodes trust).
            deadline = time.time() + 4.0
            reasserts = 0
            while True:
                s.poll()
                if s.task_mode == linuxcnc.MODE_MDI:
                    if reasserts:
                        LOG.info('%s: MDI mode took %d re-assert(s) '
                                 '(brain restore race)', label, reasserts)
                    break
                if time.time() >= deadline:
                    # SAY WHICH CAUSE. This message has two completely
                    # different meanings and they need different actions:
                    #  * not homed -> MDI is refused by LinuxCNC on non-
                    #    identity kinematics, silently. Normal for the first
                    #    seconds after boot, before the declare lands.
                    #  * homed but task not consuming -> the task/NML wedge
                    #    seen 2026-08-02 17:50 (echo_serial frozen, no error
                    #    from LinuxCNC at all). Only a restart clears it.
                    try:
                        s.poll()
                        homed = all(s.homed[:NJ])
                        echo = s.echo_serial_number
                    except Exception:
                        homed, echo = None, None
                    if homed is False:
                        why = ('machine is NOT fully homed yet -- MDI is '
                               'refused until all six joints are homed')
                    else:
                        why = ('task is not accepting commands (echo_serial '
                               'stuck at %s) -- RESTART REQUIRED' % echo)
                    c.error_msg('%s refused: %s' % (label, why))
                    LOG.error('%s refused: task_mode never reached MDI after '
                              '%d re-asserts -- homed=%s echo_serial=%s',
                              label, reasserts, homed, echo)
                    return
                if reasserts < 6 and (time.time() - (deadline - 4.0)) > \
                        0.5 * (reasserts + 1):
                    reasserts += 1
                    c.mode(linuxcnc.MODE_MDI)
                time.sleep(0.02)
            # G53: non-modal, FORCED absolute even under a stranded G91,
            # offsets never consulted (advisor part 1 verdict) -- the only
            # frame-proof one-liner for machine-frame targets
            line = ('G53 G1 {} F{:.1f}' if g53
                    else 'G90 G1 {} F{:.1f}').format(words, feed)
            c.mdi(line)   # FIRE AND FORGET -- brain restores MANUAL+teleop
            LOG.info('%s: MDI "%s" issued (fire-and-forget; brain restores '
                     'MANUAL+teleop when motion completes)', label, line)
        except Exception as e:
            LOG.error('%s failed: %s', label, e)

    # ---- status strip (dot + text + STOP) ----------------------------------
    def _jog_status_tick(self):
        # NML-only (no HAL). Drives the dot/text, the moving-lockout of
        # presets+GOs and STOP arming. Logs TRANSITIONS only (the text
        # itself updates silently -- velocity changes every tick).
        state = None
        try:
            import linuxcnc
            if self._jog_stat_nml is None:
                self._jog_stat_nml = linuxcnc.stat()
            st = self._jog_stat_nml
            st.poll()
            homing = any(st.joint[j]['homing'] for j in range(NJ))
            moving = (st.interp_state != linuxcnc.INTERP_IDLE) \
                or (not getattr(st, 'inpos', True)) \
                or (getattr(st, 'current_vel', 0.0) > 1e-6)
            if st.task_state != linuxcnc.STATE_ON:
                state, dot, txt = 'off', 'rgb(220,90,90)', \
                    'OFF — machine not on'
                self._jog_idle = True   # guards explain on click
            elif homing:
                state, dot, txt = 'homing', 'rgb(232,166,53)', 'HOMING'
                self._jog_idle = False
            elif moving:
                state, dot = 'moving', 'rgb(232,166,53)'
                txt = 'MOVING — {:.1f} mm/s'.format(
                    getattr(st, 'current_vel', 0.0))
                self._jog_idle = False
            else:
                state, dot, txt = 'idle', 'rgb(80,200,120)', 'IDLE — ready'
                self._jog_idle = True
        except Exception as e:
            state, dot, txt = 'nostat', 'rgb(120,126,132)', \
                'state unavailable'
            self._jog_idle = None
            if not self._jog_status_warned:
                self._jog_status_warned = True
                LOG.error('JOG status: stat poll failed (%s)', e)
        d = self._jp_w.get('jp_status_dot')
        t = self._jp_w.get('jp_status_text')
        if d is not None:
            style = 'color: %s; font: 11pt;' % dot
            if d.styleSheet() != style:
                d.setStyleSheet(style)
        if t is not None and t.text() != txt:
            t.setText(txt)
        if state != self._jog_last_state:
            LOG.info('JOG status: %s', txt)
            self._jog_last_state = state
        self._jog_apply_enables()

    def _jog_stop(self):
        # STOP = linuxcnc abort: kills the in-flight MDI move (and anything
        # else task is executing). The brain then restores MANUAL + teleop.
        try:
            import linuxcnc
            linuxcnc.command().abort()
            LOG.info('STOP: linuxcnc abort issued')
        except Exception as e:
            LOG.error('STOP failed: %s', e)

    # ---- the jog-speed slider is GONE (operator 2026-08-11) -------------
    # "ive never actually used the speed slider. like, ever. so get rid of
    # it. it can be at 100pct all the time." The pendant pins jogspeed-out
    # at 100 and the wheel's increment slot is the only speed control. This
    # hides the slider and its % readout, and pins the setting at 100 so
    # nothing else can wind it down.
    def _on_jogspeed(self, val):
        win = self.window()
        if win is None:
            return
        hid = []
        for name in ('linear_jog_slider', 'fr_override_dro'):
            w = win.findChild(QWidget, name)
            if w is None:
                continue
            if name == 'linear_jog_slider':
                try:
                    w.setValue(100)
                except Exception:
                    pass
            if w.isVisible():
                w.hide()
                hid.append(name)
        if hid and not getattr(self, '_jogslider_gone', False):
            self._jogslider_gone = True
            LOG.info('JOG SPEED slider removed (pinned 100%%): hid %s',
                     ', '.join(hid))


    # ---- override cluster (V/F/S/R rows -> -10%/+10% button clusters) ----
    # The first cluster attempt (2026-08-01) half-hid the FSR sliders and
    # was reverted. THIS one is all-or-nothing: build_override_clusters
    # validates every widget/layout lookup before touching anything and
    # rolls back on any mid-build exception -- an abort leaves the stock
    # slider rows fully intact and logs exactly what was missing.
    def _wire_override_cluster(self):
        win = self.window()
        if win is None:
            LOG.error('OVERRIDE CLUSTER ABORT -- stock sliders left intact: '
                      'no window')
            return
        is_locked = None
        try:
            from qtpyvcp.plugins import getPlugin
            is_locked = getPlugin('status').isLocked
        except Exception as e:
            LOG.error('OVERRIDE CLUSTER: status plugin unavailable (%s) -- '
                      'UI-lock check disabled', e)
        self._ovr_rows = build_override_clusters(win, LOG, is_locked)

    # ---- spindle section restyle (chip-load placeholder + cmd RPM) -------
    def _restyle_spindle_section(self):
        win = self.window()
        if win is None:
            return
        from PySide6.QtWidgets import QLabel
        try:
            # spindle load meter (never wired on ned, no VFD feedback) ->
            # chip-load-per-flute PLACEHOLDER (real calc from tool data later).
            # layout.replaceWidget works for BOX and GRID layouts alike --
            # insertWidget does NOT exist on QGridLayout (crashed 13:0x).
            m = win.findChild(QWidget, 'spindle_load_indicator')
            if m is not None and m.parentWidget().layout() is not None:
                # BOTH units, always (operator 2026-08-02 13:5x: "chipload
                # should always display both mm/flute and in/flute ... two
                # displays since reference values are annoying to convert").
                # Values are TBD until the feed/RPM/flute-count wiring lands
                # (operator: "put TBD for those 2 for now because we need to
                # wire it in with other stuff later on") -- the tool table
                # carries NO flute count today (columns: tool/tool_mill,
                # checked 2026-08-02), so nothing real can be computed yet.
                lbl = QLabel('CHIP LOAD\nTBD mm/flute\nTBD in/flute')
                lbl.setObjectName('ned_chipload')
                lbl.setStyleSheet('color: rgb(160,160,160); font: 9pt;')
                m.parentWidget().layout().replaceWidget(m, lbl)
                m.hide()
                self._chipload_lbl = lbl
            # left RPM readout: keep the STOCK labels and their format --
            # only the NUMBER changes ("keep the same old format, just
            # change the displayed number"). Drive every label inside the
            # source stack so it works whichever page is current.
            st = win.findChild(QWidget, 'spindle_rpm_source_widget')
            self._rpm_labels = []
            if st is not None:
                for w in st.findChildren(QWidget):
                    if hasattr(w, 'setText') and hasattr(w, 'text'):
                        self._rpm_labels.append(w)
            LOG.info('spindle section: chip-load placeholder in; commanded-'
                     'RPM drives %d stock label(s) (format untouched)',
                     len(self._rpm_labels))
        except Exception as e:
            LOG.error('spindle restyle failed: %s', e)

    def _wire_spindle_check(self):
        win = self.window()
        if win is None:
            return
        from qtpyvcp.actions import spindle_actions
        for name, fire in (('spindle_forward_button', spindle_actions.forward),
                           ('spindle_reverse_button', spindle_actions.reverse)):
            b = win.findChild(QWidget, name)
            if b is None:
                LOG.error('spindle check: %s not found', name)
                continue
            try:
                b.clicked.disconnect()
            except Exception:
                pass
            b.clicked.connect(lambda _=False, btn=b, f=fire, n=name:
                              self._spindle_check_click(btn, f, n))
        LOG.info('spindle FWD/REV wired to Check countdown (no iron S1 gate)')

    def _spindle_check_click(self, b, fire, key):
        pend = self._spin_pend.pop(key, None)
        if pend is not None:                       # second press = cancel
            pend['timer'].stop()
            pend['restore']()
            LOG.info('%s Check cancelled', key)
            return
        # two rows + smaller font so the countdown fits INSIDE the button
        pend = {'text': b.text(), 'style': b.styleSheet(), 'left': 3}
        timer = QTimer(self)
        pend['timer'] = timer
        self._spin_pend[key] = pend
        b.setStyleSheet(pend['style'] + '\nQPushButton { font: 9pt; }')

        def restore():
            b.setText(pend['text'])
            b.setStyleSheet(pend['style'])

        pend['restore'] = restore

        def tick():
            if self._spin_pend.get(key) is not pend:
                timer.stop()
                return
            pend['left'] -= 1
            if pend['left'] > 0:
                b.setText('Check\n{}'.format(pend['left']))
                return
            timer.stop()
            restore()
            self._spin_pend.pop(key, None)
            try:
                fire()
            except Exception as e:
                LOG.error('%s spin failed: %s', key, e)

        timer.timeout.connect(tick)
        b.setText('Check\n3')
        timer.start(1000)

    def _wire_unload(self):
        # TWO unload buttons exist, same label, different tabs:
        #   remove_tool_2      TOOL tab  (probe_basic.ui)
        #   remove_tool_button ATC  tab  (template_rack_atc.ui)
        # Only remove_tool_2 was ever wired, so the ATC tab's UNLOAD SPINDLE
        # had no countdown and no drawbar auto-release -- it called the stock
        # sub instantly. Found 2026-08-03 when the operator pointed out the
        # ATC tab has its own copy. Same shape as _wire_load's pair.
        win = self.window()
        wired, missing = [], []
        for name in ('remove_tool_2', 'remove_tool_button'):
            b = win.findChild(QWidget, name) if win else None
            if b is None:
                missing.append(name)
                continue
            for sig in (b.pressed, b.released, b.clicked):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            b.clicked.connect(lambda _=False, btn=b: self._unload_click(btn))
            wired.append(name)
        if wired:
            LOG.info('UNLOAD SPINDLE: 5 s countdown wired on %d button(s): %s',
                     len(wired), ', '.join(wired))
        if missing:
            # absent = deleted from the .ui by design (2026-08-04 purges);
            # a name that EXISTS but fails to wire would appear in `wired`
            # count mismatches, not here
            LOG.info('UNLOAD SPINDLE: %d name(s) confirmed deleted: %s',
                     len(missing), ', '.join(missing))

    # Stock labels that say WHERE they go, not what they are called. The pair
    # GO TO ZERO / GO TO HOME is the easy mix-up: one is the active work
    # system, the other is machine zero (operator 2026-08-03).
    RELABEL = {
        'go_to_zero_button_2': 'WCS X0Y0',
        'go_to_home_button':   'MCS HOME',
    }

    # Every MDI entry EXCEPT the one on MAIN. Four copies of the same input
    # scattered across tabs is four places to fat-finger a command from
    # (operator 2026-08-03: "there are too many MDIs all over the god damn
    # place"). main_tab keeps mdiEntry + mdihistory; these go.
    # RESURRECTION NET (operator 2026-08-04: "keep the code light... gone
    # so they do not consume resources"): every control below is DELETED
    # from the .ui files outright. This list stays so a PB update that
    # restores stock .ui files gets its spares re-hidden until the purge
    # is reapplied (docs/update_survival.md).
    SPARE_MDI = ('mdi_entry_box_4', 'mdi_entry_box_5',
                 'mdi_entry_box_6', 'mdi_entry_box_7',
                 # ATC tab had its own pair too, missed by the first sweep
                 # (they live in template_rack_atc.ui, not probe_basic.ui)
                 'mdi_entry_box_rack_tab', 'rack_mdi_2')

    # ONE M6 G43: the main panel's. The TOOL and ATC tabs each carried a
    # full copy (button + tool-number field) of the same control -- three
    # places to start a tool change from, all identical (operator
    # 2026-08-04: "i hate redundancy"). Copies hidden, never unwired: the
    # main-panel control is the same SubCallButton mechanism, so behaviour
    # is unchanged, there is just exactly one of it.
    SPARE_M6 = ('m6_tool_call_button_tool_page',
                'tool_number_entry_tool_page',
                'm6_tool_call_button_atc_page',
                'tool_number_entry_atc_page',
                # TOUCH OFF CURRENT TOOL: the TOOL tab keeps the only one;
                # the rack widget carried a full copy (operator 2026-08-04)
                                # the operator then called the WHOLE ATC loading panel
                # redundant -- hiding its frame takes the header, LOAD +
                # field, UNLOAD and STORE TOOL IN RACK in one go, no empty
                # box left behind. Per-widget hides above stay as defence.
                                # REF RACK DATA: carousel position reference -- no carousel
                # on ned, ever (operator 2026-08-04: "delete that button")
                'reference_carousel_2',
                # PROGRAMMED COOLANT CONSTANTS: whole settings frame
                # (operator 2026-08-04: "i won't be using these at all")
                'prog_coolant_setting_frame',
                # tool table persists in real time; these three are gone
                # (operator 2026-08-04: "remove save, load and update
                # loaded tool")
                'tool_table_save_button',
                'tool_table_reload_buttonold',
                'update_tool_after_reload',
                'tool_touch_off_button_atc',
                # (native spindle display + load frame RESTORED to the
                # RACK ATC page at operator request 2026-08-04 evening --
                # they are no longer spares)
                )

    def _hide_spare_mdi(self):
        win = self.window()
        gone, missing = [], []
        for name in self.SPARE_MDI + self.SPARE_M6:
            w = win.findChild(QWidget, name) if win else None
            if w is None:
                missing.append(name)
                continue
            w.hide()
            gone.append(name)
        if missing:
            # deleted from the .ui outright (operator 2026-08-04) -- absent
            # is the INTENDED state; anything in `gone` above means a PB
            # update resurrected stock spares and the purge must be reapplied
            LOG.info('REDUNDANCY: %d control(s) confirmed deleted: %s',
                     len(missing), ', '.join(missing))
        if gone:
            LOG.error('REDUNDANCY: %d STOCK SPARE(S) RESURRECTED (PB '
                      'update?) -- hidden for now, reapply the .ui purge '
                      '(update_survival): %s', len(gone), ', '.join(gone))

    # Buttons that command MOTION or issue MDI. LinuxCNC silently refuses an
    # MDI command on non-identity kinematics until every joint is homed, so
    # on an unhomed machine these cannot work -- they just emit "Must be in
    # MDI mode", which is what happened all evening. DISABLED until homed
    # (operator 2026-08-03: "ALL BUTTONS THAT NEED HOMING SHOULD NOT BE
    # CLICKABLE until we get STALE HOME").
    #
    # NOT gated, deliberately: POWER, E-STOP, the Homing menu and the jog
    # controls. Those are how you GET homed; disabling them is a trap.
    HOMING_GATED = (
        'm6_tool_call_button_main_panel',
        'remove_tool_2', 'ned_rerack_button',
        'tool_touch_off_button',
        'go_to_zero_button_2', 'go_to_g30_button', 'go_to_home_button',
    )

    # only these survive the pre-home sweep -- the two controls the
    # operator needs to recover the machine, and nothing else
    # exit_button IS THE E-STOP: ActionButton, machine.estop.toggle,
    # text "E-STOP" (probe_basic_ui.py:11912, gui_map badge 238). It is NOT
    # called estop_button -- the two estop names listed here before did not
    # exist and 'estop' does not appear in 'exit_button', so the sweep was
    # DISABLING THE E-STOP and _estop_bindOk never re-enables it (it only
    # calls setChecked, machine_actions.py:83). E-STOP was dead for the
    # whole pre-home window. Found by advisor audit 2026-08-05.
    PREHOME_ALLOW = ('exit_button', 'power_button', 'stop_button')
    PREHOME_SURVIVORS = ('exit_button', 'power_button', 'stop_button')
    # While the machine is locked for a SPINDLE/TABLE INCONSISTENCY the way
    # out is the ATC and TOOL tabs -- operator 2026-08-07: "NO BUTTONS work
    # other than going to ATC/TABLE and setting the table to correct the
    # error ... make sure that all the buttons inside of ATC and TOOL are
    # not blocked". Naming the TAB PAGES is enough: the event filter walks
    # up parents, so every control inside them passes. The tab BAR is a
    # survivor too or the pages cannot be reached.
    TOOLLOCK_SURVIVORS = ('exit_button', 'power_button', 'stop_button',
                          'atc_tab', 'tool_tab')

    def _sweep_gate(self, win, homed, keep=()):
        """Disable EVERY button until home is declared; restore after.

        Tracks exactly what it switched off so re-enabling cannot turn on a
        control that was disabled for its own reasons (drawbar, tool lock,
        machine off) -- those owners re-assert on their own ticks."""
        from PySide6.QtWidgets import QPushButton, QToolButton
        if win is None:
            return
        if not homed:
            # RE-SWEEP EVERY TICK. This used to sweep once and return early
            # forever -- and the sub-tabs are built on a 6.5 s timer, well
            # after the first sweep, so every control created later (the WCS
            # JOG presets, ZERO Y among them) was never gated at all. The
            # operator could still click it. Widgets appear late; the gate
            # has to keep looking.
            off = getattr(self, '_prehome_off', None) or []
            known = set(id(b) for b in off)
            for b in win.findChildren(QPushButton) + win.findChildren(
                    QToolButton):
                n = b.objectName()
                if n in self.PREHOME_ALLOW or 'estop' in n.lower():
                    continue
                # anything living inside a survivor stays USABLE, not just
                # un-swallowed: greying the ATC/TOOL buttons would hide the
                # only way out of a spindle/table inconsistency
                if keep:
                    _w, _skip = b, False
                    while _w is not None:
                        if any(_w is k for k in keep):
                            _skip = True
                            break
                        _w = _w.parentWidget()
                    if _skip:
                        continue
                if id(b) in known:
                    # Its owner may have re-enabled it (qtpyvcp bindOk runs
                    # on every status change). Grey it again, but do not
                    # re-record it. Without this the FIRST self-re-enable
                    # was permanent and silent.
                    if b.isEnabled():
                        b.setEnabled(False)
                    continue
                if not b.isEnabled():
                    continue                # already off; not ours to restore
                b.setEnabled(False)
                off.append(b)
            n_new = len(off) - len(known)
            self._prehome_off = off
            if n_new:
                LOG.error('PRE-HOME GATE: %d new control(s) DISABLED (%d '
                          'total) -- only E-stop and power live until the '
                          'home declaration lands', n_new, len(off))
            return
        off = getattr(self, '_prehome_off', None)
        if off is None:
            return
        n_ok = 0
        for b in off:
            try:
                b.setEnabled(True)
                n_ok += 1
            except RuntimeError:
                pass                        # widget deleted since
        self._prehome_off = None
        LOG.error('PRE-HOME GATE RELEASED: home declared, %d control(s) '
                  're-enabled', n_ok)

    def _sync_load_enabled(self):
        """LOAD needs BOTH: a homed machine and an open drawbar.

        Unhomed, the load sub cannot run at all (MDI refused); with the
        drawbar shut there is nothing to load into. Never disabled
        mid-countdown -- that would strand a pending LOAD with no way to
        cancel it.
        """
        ok = (bool(getattr(self, '_drawbar_released', False))
              and bool(getattr(self, '_homed_now', False)))
        for b in getattr(self, '_load_btns', []):
            try:
                if self._load_pend.get(b) is not None:
                    continue
                b.setEnabled(ok)
            except Exception:
                pass

    def _start_homing_gate(self):
        self._homed_now = None
        self._homing_gate_tick()
        t = self._homing_gate_timer = QTimer(self)
        t.timeout.connect(self._homing_gate_tick)
        t.start(500)

    def _sync_fork_graphic(self):
        # STARTUP SYNC (operator 2026-08-04: "the forks do not represent
        # the table"): the carousel only hears event pushes, so at boot it
        # shows blank forks while the var file knows better. Push the whole
        # rack map into it once, as soon as both exist.
        if getattr(self, '_forks_synced', False):
            return
        try:
            win = self.window()
            rack = win.findChild(QWidget, 'rackatc') if win else None
            if rack is None or not hasattr(rack, 'store_tool'):
                return
            path = ('/home/brains/Documents/ned/configs/ned5_pb/'
                    'ned5_pb.var')
            forks = {}
            with open(path) as f:
                for ln in f:
                    bits = ln.split()
                    if len(bits) == 2:
                        try:
                            pnum, val = int(bits[0]), float(bits[1])
                        except ValueError:
                            continue
                        if 4001 <= pnum <= 4024:
                            forks[pnum - 4000] = int(val)
            for fork, tool in forks.items():
                rack.store_tool(fork, tool)
            self._forks_synced = True
            LOG.info('FORK GRAPHIC synced from the var file: %s',
                     {k: v for k, v in forks.items() if v} or 'all empty')
        except Exception:
            LOG.exception('fork graphic sync failed')

    def _build_spindle_editor(self):
        # THE one way to declare the spindle tool (operator 2026-08-04:
        # "the only way to indicate a tool is in spindle is to change the
        # number in the spindle in ATC. click it and put 5"). Click the
        # badge -> type a number -> the table follows. 0 = spindle empty;
        # whoever held the record drops to the FLOOR (-1).
        try:
            from PySide6.QtCore import Qt as _Qt
            badge = self.window().findChild(QWidget, 'tool_length_6')
            if badge is None:
                LOG.error('SPINDLE EDITOR: badge tool_length_6 not found')
                return
            badge.setCursor(_Qt.PointingHandCursor)
            badge.setToolTip('Click to set which tool is in the spindle')
            badge.installEventFilter(self)
            self._spindle_badge = badge
            LOG.info('SPINDLE EDITOR: badge is click-to-declare')
        except Exception:
            LOG.exception('spindle editor build failed')

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if (obj is getattr(self, '_spindle_badge', None)
                and ev.type() == QEvent.MouseButtonRelease):
            self._spindle_badge_clicked()
            return True
        return super(UserTab, self).eventFilter(obj, ev)

    def _spindle_badge_clicked(self):
        try:
            import linuxcnc
            from PySide6.QtWidgets import QInputDialog
            st = linuxcnc.stat(); st.poll()
            # DEADLOCK BREAK (2026-08-05). The tool-state lock drives
            # motion.feed-inhibit, so any move in flight when the lock
            # engages FREEZES at zero feed and the interpreter never goes
            # back to IDLE. The idle test below then refuses the
            # declaration -- and the declaration is the ONLY thing that
            # clears the lock. Seven refused clicks proved it. Under the
            # lock a non-idle interpreter is frozen, not progressing, so
            # clear it here instead of deadlocking the operator.
            if (st.task_state == linuxcnc.STATE_ON
                    and all(st.homed[:NJ])
                    and st.interp_state != linuxcnc.INTERP_IDLE
                    and self._tool_state_locked()):
                cc = linuxcnc.command()
                cc.abort()
                cc.wait_complete(2.0)
                st.poll()
                LOG.error('SPINDLE EDITOR: a move was frozen at zero feed by '
                          'the tool-state lock -- aborted it so the '
                          'declaration can proceed')
            if (st.task_state != linuxcnc.STATE_ON
                    or st.interp_state != linuxcnc.INTERP_IDLE
                    or not all(st.homed[:NJ])):
                LOG.error('SPINDLE EDITOR refused: machine must be ON, '
                          'homed and idle')
                return
            cur = int(st.tool_in_spindle)
            n, ok = QInputDialog.getInt(
                self.window(), 'SPINDLE TOOL',
                'Tool now in the spindle (0 = empty):', cur, 0, 99)
            if not ok or n == cur:
                return
            c = linuxcnc.command()
            if not self._take_mdi(c, 'SPINDLE EDITOR'):
                return
            if n == 0:
                c.mdi('o<tool_loc_declare> call [%d] [-1]' % cur)
                LOG.info('SPINDLE EDITOR: spindle -> empty; T%d recorded '
                         'on the FLOOR', cur)
            else:
                c.mdi('o<tool_loc_declare> call [%d] [0]' % n)
                LOG.info('SPINDLE EDITOR: T%d declared in spindle%s', n,
                         ('; T%d drops to the FLOOR' % cur) if cur else '')
            # a declaration is paperwork, not a job -- give the machine back
            self._hand_back_manual(c, 'SPINDLE EDITOR')
        except Exception:
            LOG.exception('spindle editor failed')

    # ==== TCP CALIBRATION: A pivot length, one button ====================
    # z(A) = const + dL*cos(A),  dL = L_true - L_in_force
    #   ->  dL = (z1 - z2) / (cos A1 - cos A2)
    # Identity kins: L_in_force = 0, so a pair gives L outright.
    # Tool-tip kins: the pair gives the CORRECTION, and dZ is the residual.
    TCP_HIST = '/home/brains/Documents/ned/configs/ned5_pb/tcp_cal.json'

    def _gate_survivor_widgets(self, names=None):
        win = self.window()
        if win is None:
            return []
        out = []
        if names is None:
            names = self.PREHOME_SURVIVORS
        else:
            # reaching a survivor PAGE requires its tab bar to be clickable
            try:
                from PySide6.QtWidgets import QTabWidget
                for tw in win.findChildren(QTabWidget):
                    out.append(tw.tabBar())
            except Exception:
                LOG.exception('GATE: could not add the tab bar as a survivor')
        for name in names:
            try:
                w = win.findChild(QWidget, name)
            except RuntimeError:
                w = None
            if w is not None:
                out.append(w)
        return out

    def _arm_input_gate(self, names=None):
        """Make the GUI non-interactive except the named survivors."""
        gate = getattr(self, '_input_gate', None)
        if gate is None:
            gate = self._input_gate = _PreHomeInputGate(self)
        surv = self._gate_survivor_widgets(names)
        if not surv:
            # NEVER leave the operator without E-stop. If not one survivor
            # resolves, refuse to arm -- loudly -- rather than lock them out.
            if not getattr(self, '_gate_nosurv_logged', False):
                self._gate_nosurv_logged = True
                LOG.error('PRE-HOME GATE: none of %s found -- NOT ARMED '
                          '(refusing to lock the operator out of E-stop)',
                          ', '.join(self.PREHOME_SURVIVORS))
            self._release_input_gate(quiet=True)
            return
        self._gate_nosurv_logged = False
        gate.setSurvivors(surv)      # refreshed each tick: late rebuilds
        if getattr(self, '_input_gate_armed', False):
            return
        app = QApplication.instance()
        if app is None:
            LOG.error('PRE-HOME GATE: no QApplication -- NOT ARMED')
            return
        app.installEventFilter(gate)
        self._input_gate_armed = True
        LOG.error('PRE-HOME GATE ARMED: every input swallowed except %s',
                  ', '.join(w.objectName() for w in surv))

    def _release_input_gate(self, quiet=False):
        if not getattr(self, '_input_gate_armed', False):
            return
        self._input_gate_armed = False
        gate = getattr(self, '_input_gate', None)
        app = QApplication.instance()
        try:
            if app is not None and gate is not None:
                app.removeEventFilter(gate)
        except RuntimeError:
            pass
        if not quiet:
            LOG.error('PRE-HOME GATE RELEASED: home declared, input restored '
                      '(%d event(s) swallowed)',
                      gate.swallowed() if gate is not None else 0)

    def _sweep_release_force(self):
        """Unconditionally re-enable everything the gate switched off.

        Not hypothetical: 394 controls stayed disabled for a whole session
        because the tick stopped reaching the release path."""
        off = getattr(self, '_prehome_off', None) or []
        n = 0
        for b in off:
            try:
                b.setEnabled(True)
                n += 1
            except RuntimeError:
                pass
        self._prehome_off = None
        LOG.error('PRE-HOME GATE FORCE-RELEASED: %d control(s) re-enabled', n)

    def _puck_toggle(self, up):
        """Raise or drop the tool-setter puck. M64/M65 P3 -- no motion.

        Every calibration page carries one and they mirror each other. The
        dwell matters: there is no deployed sensor, so the 1.5 s IS the
        proof the puck had time to travel before anything plunges at it --
        the auto sweep shipped without a deploy at all and plunged onto a
        retracted puck (2026-08-05)."""
        up = bool(up)
        try:
            import linuxcnc
            gate = self._cal_gate('PUCK')
            if gate is None:
                self._puck_sync(not up)          # refused: leave state honest
                return
            c, _ = gate
            c.mdi('M64 P3' if up else 'M65 P3')
            c.mdi('G4 P1.5')
            self._hand_back_manual(c, 'PUCK')
            LOG.error('PUCK %s commanded (M%d P3)', 'UP' if up else 'DOWN',
                      64 if up else 65)
            self._puck_sync(up)
        except Exception:
            LOG.exception('PUCK toggle failed')
            self._puck_sync(not up)

    def _puck_sync(self, up):
        for b in getattr(self, '_puck_btns', []):
            try:
                b.blockSignals(True)
                b.setChecked(up)
                b.setText('PUCK DOWN' if up else 'PUCK UP')
                b.setStyleSheet(self.CAL_QSS['measure'] if up
                                else self.CAL_QSS['pose'])
                b.blockSignals(False)
            except RuntimeError:
                pass

    def _tcp_commit(self):
        """Write the pivot IN FORCE to head_pivot.inc -- the survivor.

        Reads arm.in0, not the last measurement: arm.in0 is what _tcp_apply
        left after the sweep converged, already in the axis-arm convention
        (live tool length is added back on top by the sum2 at every launch).
        NOTE while the touching tool records 0 length in the table, this
        number still CONTAINS that rod: it is right for THIS rod, and it
        becomes the true axis->nose machine constant only once the rod's
        stickout is measured and subtracted (nose #3010 path, task list)."""
        try:
            import time
            # FROM THE MEASUREMENT RECORD, NEVER THE LIVE PIN. The pin is a
            # transient -- any relaunch re-seeds it from head_pivot.inc, and
            # on 2026-08-05 23:52 that made this button write the STALE 157
            # back over a finished calibration whose real result (L 323.68)
            # was sitting in tcp_cal.json the whole time.
            hist = getattr(self, '_tcp_hist', []) or []
            evals = [r for r in hist if r.get('t') == 'descent-eval']
            v = None
            # head_pivot.inc = AXIS->NOSE; record L = AXIS->TIP for the
            # tool in force at MEASUREMENT time. Subtract THAT record's
            # offset, never today's.
            if evals:
                best = min(evals, key=lambda r: r['mean'])
                toff = float(best.get('tooloff', self._tcp_tooloff()))
                v = float(best['L']) - toff
                src = ('best alternate eval %d (mean|miss| %.4f; L %.3f '
                       'minus tool %.3f)'
                       % (best['n'], best['mean'], best['L'], toff))
            else:
                probes = [r for r in hist
                          if not str(r.get('t', '')).startswith('descent')]
                if probes:
                    toff = float(probes[-1].get('tooloff',
                                                self._tcp_tooloff()))
                    v = float(probes[-1]['L']) - toff
                    src = ('last measurement, A %.1f deg; L %.3f minus '
                           'tool %.3f' % (probes[-1].get('a2', 0.0),
                                          probes[-1]['L'], toff))
            if v is None:
                self._tcp_say('SAVE refused: no measurements in '
                              'tcp_cal.json -- run AUTO CONVERGE first.',
                              bad=True)
                return
            if not (50.0 < v < 1000.0):
                self._tcp_say('COMMIT refused: %.3f is not a physical '
                              'pivot' % v, bad=True)
                return
            path = ('/home/brains/Documents/ned/configs/params/'
                    'head_pivot.inc')
            with open(path, 'w') as f:
                f.write('# head pivot fed to arm.in0 at HAL load (run5 '
                        'bakes it into the tcp postgui).\n'
                        '# WRITTEN BY THE OPERATOR: TCP tab SAVE PIVOT, '
                        '%s.\n'
                        '# Source: %s.\n'
                        '# Value includes the touching rod while its tool '
                        'records 0 length --\n'
                        '# subtract the rod stickout to get the bare '
                        'axis->nose constant.\n'
                        'PIVOT_LENGTH = %.4f\n'
                        % (time.strftime('%F %T'), src, v))
            self._tcp_say('SAVED: PIVOT_LENGTH = %.4f (%s) -> '
                          'head_pivot.inc.' % (v, src))
            LOG.error('TCP COMMIT: head_pivot.inc = %.4f from %s', v, src)
            try:
                self._tcp_result.setText('PARAM (axis->nose) = %.4f' % v)
            except Exception:
                pass
            # bring the live pin along (A=0-guarded). _tcp_apply expects
            # axis->TIP and subtracts the LIVE tool itself -- handing it
            # the nose value double-subtracted the tool (advisor F1: pin
            # fell to ~158 with tool-tip kins live the moment SAVE was
            # pressed).
            self._tcp_apply(v + self._tcp_tooloff())
        except Exception:
            LOG.exception('TCP COMMIT failed -- head_pivot.inc NOT written')
            self._tcp_say('COMMIT FAILED -- head_pivot.inc not written, '
                          'see the log', bad=True)

    def _tcp_kins(self):
        """('identity'|'tcp', pivot length currently IN FORCE)."""
        try:
            import linuxcnc, os, subprocess
            ini = linuxcnc.ini(os.environ['INI_FILE_NAME'])
            if 'ned_ac_kins' not in (ini.find('KINS', 'KINEMATICS') or ''):
                return ('identity', 0.0)
            r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                'ned_ac_kins.pivot-length'],
                               capture_output=True, text=True)
            return ('tcp', float(r.stdout.strip()))
        except Exception:
            LOG.exception('TCP CAL: could not read the pivot in force')
        return ('identity', 0.0)

    def _take_mdi(self, c, label, secs=4.0):
        """Take MDI and CONFIRM it landed, re-asserting against the
        brain's MANUAL-restore race (advisor M1-M6: six single-shot
        mode() calls lost that race intermittently -- lost declarations,
        lost G20/G21, a drawbar left bleeding air)."""
        import linuxcnc, time
        s = linuxcnc.stat()
        deadline = time.time() + secs
        c.mode(linuxcnc.MODE_MDI)
        c.wait_complete(1.0)
        while True:
            s.poll()
            if s.task_mode == linuxcnc.MODE_MDI:
                return True
            if time.time() > deadline:
                LOG.error('%s: task never reached MDI in %.0fs', label, secs)
                return False
            c.mode(linuxcnc.MODE_MDI)
            time.sleep(0.15)

    def _hand_back_manual(self, c, label, wait=2.0):
        """Return the machine to MANUAL after a BOOKKEEPING MDI.

        Jogging only exists in MANUAL, so an MDI left parked kills the wheel
        silently: 2026-08-05 the operator declared T5, the tool-state lock
        cleared, every inhibit read FALSE -- and nothing moved, because
        task_mode was still MDI. There is no visible MAN button to recover
        with, so whatever parks the machine has to un-park it.

        NEVER call this with MOTION in flight -- a mode switch ABORTS motion.
        Bookkeeping only, or from an idle-completion poll."""
        try:
            import linuxcnc
            c.wait_complete(wait)
            c.mode(linuxcnc.MODE_MANUAL)
            LOG.info('%s: MDI handed back -- jogging is live', label)
        except Exception:
            LOG.exception('%s: could not restore MANUAL -- jogging may be '
                          'dead until the mode is changed', label)

    def _tool_state_locked(self):
        """TRUE while the spindle record and the drawbar disagree.

        The lock drives motion.jog-inhibit AND motion.feed-inhibit
        (ned5_iron.hal:383), so a move issued under it does not fail -- it
        STALLS at zero feed and the interpreter never returns to IDLE."""
        try:
            import subprocess
            r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                'tool.mm.lock.out'],
                               capture_output=True, text=True)
            return r.stdout.strip().upper().startswith('TRUE')
        except Exception:
            LOG.exception('could not read the tool-state lock')
            return False

    def _tcp_work(self, s, i):
        """Work-frame coordinate -- the frame #5063/#5064 report in."""
        return (s.actual_position[i] - s.g5x_offset[i] - s.g92_offset[i]
                - s.tool_offset[i])

    def _tcp_field(self, w, dflt, lo, hi):
        try:
            v = abs(float(w.text()))
        except Exception:
            v = dflt
        return min(max(v, lo), hi)

    # ---- AUTOMATED CONVERGENCE (operator spec 2026-08-05) --------------
    # "user parks roughly 10mm above probe. hits start. the entire sequence
    #  can be automated. if the delta A is small, the probe is guaranteed to
    #  be above the puck... the maximum one can rotate before the radius
    #  hits instead of the tip is 35deg."
    # Steps grow as confidence grows, never by more than 5 deg, ceiling 35.
    # The A=0 reference Z is taken ONCE -- "that number never changes" --
    # and every later step returns to the ORIGINAL start pose before
    # probing, which is what corrects drift in Y.
    # Operator 2026-08-05: "like 1 deg, 2 deg, 2deg, then 5deg 5 deg until
    # get to 35" -- increments of +1, +2, +2, then +5, so the absolute
    # angles below. 35 is the ceiling: past it the rod RADIUS touches
    # before the needle tip. The old 0.1/0.2 steps were useless anyway --
    # at 0.1 deg the leverage (1-cos A) is 1.5e-6 and the solve is pure
    # noise.
    TCP_ANGLES = [5.0, 15.0, 25.0, 35.0]
    TCP_TOL = 0.02          # mm of residual dZ (manual cycle display)
    # convergence is judged on |dL|, NOT the raw residual: at 1 deg the
    # leverage is 1/(1-cos A) = 6566 mm of pivot per mm of residual, so
    # residuals under 0.02 mm at the small angles certify nothing. 0.5 mm
    # of pivot is what the operator is converging (advisor S9).
    # 0.05 mm = the noise floor: 0.01 mm of probe scatter maps to
    # 0.055 mm of L at 35 deg (1/(1-cosA) leverage). Operator 2026-08-05:
    # 0.1 already "seems quite large". Early exit now only fires on an
    # exceptionally clean run; otherwise the sweep runs to the 35 deg
    # verification, which is the point.
    TCP_DL_TOL = 0.05

    def _tcp_auto_press(self):
        if getattr(self, '_tcp_auto_on', False):
            self._tcp_auto_stop('STOPPED by the operator')
            return
        if self._tool_state_locked():
            self._tcp_say('TOOL-STATE LOCK is engaged -- declare the tool '
                          'in the spindle first.', bad=True)
            return
        gate = self._cal_gate('TCP AUTO')
        if gate is None:
            return
        c0, s0 = gate
        s0.poll()
        # no stat-offset guard here (advisor V4): stat's offsets lie, so
        # the old test false-passed exactly when a real A offset existed.
        # The straighten block below IS the honest guard -- after G1 A0,
        # servo feedback still off zero = an offset exists, refuse there.
        kind, L_set = self._tcp_kins()
        if kind != 'tcp':
            self._tcp_say('AUTO needs tool-tip kins running -- relaunch with '
                          '-tcp. In identity there is nothing to converge.',
                          bad=True)
            self._hand_back_manual(c0, 'TCP AUTO')
            return
        # every rerun starts with an empty table (operator 2026-08-06:
        # "clear up that data on next rerun") -- old rows go to trash/
        self._tcp_clear_data()
        # ARM FIRST (advisor D1): the straighten + G43 preamble below is
        # MDI too -- unarmed, it sat in exactly the race this interlock
        # exists to kill.
        self._seq_flag(True)
        # G43 HERE, not at boot: applying it from the brain's restore ran
        # MDI during the declare and every home() missed (2026-08-06).
        # The tool length must be in force or every L is off by the tool.
        try:
            s0.poll()
            if self._tcp_tooloff() < 1.0 and s0.tool_in_spindle > 0:
                import subprocess
                r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                    'joint.4.pos-fb'],
                                   capture_output=True, text=True)
                if abs(float(r.stdout.strip())) > 0.05:
                    # straighten it ourselves -- pressing the button IS
                    # consent to motion (it probes). Refusing here made
                    # the button dead after any zero re-bank (2026-08-06).
                    c0.mdi('G1 A0 F300')
                    c0.wait_complete(30.0)
                    r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                        'joint.4.pos-fb'],
                                       capture_output=True, text=True)
                    if abs(float(r.stdout.strip())) > 0.05:
                        self._tcp_say('refused: could not straighten A '
                                      'for G43', bad=True)
                        self._seq_flag(False)
                        self._hand_back_manual(c0, 'TCP SURVEY')
                        return
                c0.mdi('G43 H%d' % s0.tool_in_spindle)
                c0.wait_complete(4.0)
                LOG.error('TCP SURVEY: G43 H%d applied (tool length %.3f)',
                          s0.tool_in_spindle, self._tcp_tooloff())
        except Exception:
            LOG.exception('TCP SURVEY: G43 check failed')
            self._seq_flag(False)
            return
        import random, time as _t
        self._tcp_auto_on = True
        self._tcp_auto_phase = 'survey'
        self._svy = {'n': 0, 'step': 'ref-issue', 'z0': None, 'zp': None,
                     'best_L': 0.0, 'best_sum': None,
                     'L': 0.0, 'ofs': 0.0,
                     'log': ('/home/brains/Documents/ned/logs/'
                             'tcp_survey_%s.ndjson'
                             % _t.strftime('%Y%m%d-%H%M%S'))}
        random.seed()
        try:
            self._svy['arm0_saved'] = self._tcp_tooloff() * 0 + float(
                __import__('subprocess').run(
                    ['timeout', '5', 'halcmd', 'getp', 'arm.in0'],
                    capture_output=True, text=True).stdout.strip())
            self._tcp_result.setText('PARAM (axis->nose) = %.4f'
                                     % self._svy['arm0_saved'])
            self._svy['best_L'] = (self._svy['arm0_saved']
                                   + self._tcp_tooloff())
        except Exception:
            LOG.exception('SURVEY: could not read arm.in0 at press')
            self._svy['arm0_saved'] = None
        self._tcp_auto_i = -1          # -1 = the one-off A=0 reference
        self._tcp_auto_ref = None
        self._tcp_auto_start = None
        self._tcp_auto_rows = []
        # phase stays 'survey' -- the stale 'ladder' assignment here
        # OVERWROTE the survey seed three lines up, so every press of the
        # new button ran the OLD ladder+descent all night and the survey
        # never executed once (found 2026-08-06 08:45)
        self._tcp_desc = None
        self._tcp_auto_pending_L = None
        self._tcp_auto_go_next = False
        self._tcp_auto_idle_t0 = None
        # advisor D3: a leftover manual-cycle pending would fire
        # _hand_back_manual mid-survey and clobber arm.in0
        self._tcp_manual_pending = False
        self._tcp_set_face()
        self._tcp_say('SURVEY: %d pairs, draws +-%.1f%% around the '
                      'running best (start %.3f), ofs %s. Data -> %s'
                      % (self.SVY_N, self.SVY_HALF_PCT,
                         self._svy['best_L'], self.SVY_OFS,
                         self._svy['log']))
        self._tcp_survey_next()   # step 'ref': puck up + reference probe

    def _tcp_auto_issue(self, targa, repos, puck=0):
        import time
        gate = self._cal_gate('TCP AUTO')
        if gate is None:
            self._tcp_auto_stop('gate refused')
            return
        c, s = gate
        # OPERATOR SPEC (2026-08-05): the REFERENCE plunges the full field
        # value -- the operator parks about an inch above the puck, so
        # "before that, it should be 30mm". Once the start pose is banked
        # 5 mm above the found contact, every later step plunges 6 mm
        # ("after the first return to +5mm, sure, we can amend the plunge
        # to 6mm"). No rotation lift: "the whole point is not to move 15
        # at one go with a bad calibration, its to go in little stages so
        # by the time you move 15, you are not off by much any more" --
        # the ladder of applies IS the safety mechanism.
        # 30 free-park reference, 10 for every step (operator spec; the
        # BOUNDS fields are gone -- these ARE the numbers)
        plunge = 30.0 if not repos else 10.0
        st = self._tcp_auto_start or (0.0, 0.0, 0.0)
        c.mdi('o<tcp_auto_step> call [%.4f] [%d] [%.4f] [%.4f] [%.4f] '
              '[%.4f] [%d]'
              % (targa, repos, st[0], st[1], st[2], plunge, puck))
        self._tcp_auto_t0 = time.time()
        self._tcp_auto_want = targa
        self._tcp_auto_idle_t0 = None
        LOG.error('TCP AUTO: step issued A=%.3f repos=%d start=%.4f/%.4f/'
                  '%.4f plunge=%.1f puck=%d', targa, repos, st[0], st[1],
                  st[2], plunge, puck)

    def tcp_auto_point(self, xt, yt, zt, at):
        """Called BY THE G-CODE at every probe trip in the auto sequence."""
        import math
        x, y, z, a = float(xt), float(yt), float(zt), float(at)
        LOG.error('TCP AUTO probe LANDED: X=%.4f Y=%.4f Z=%.4f A=%.4f',
                  x, y, z, a)
        if not getattr(self, '_tcp_auto_on', False):
            return
        if getattr(self, '_tcp_auto_phase', '') == 'survey':
            v = self._svy
            st = v['step']
            # STRICT issue/wait split: this callback acts ONLY on -wait
            # states, _tcp_survey_next only on -issue/'apply'. A stale
            # go_next then lands in a -wait state and no-ops -- without
            # this, a late-delivered zero touch could be recorded as the
            # +35 reading (delivery lags idle by up to 200 ms).
            v['retry'] = 0
            if st == 'ref-wait':
                self._tcp_auto_ref = (z, a)
                # 3 mm hover (operator 2026-08-06): 1 mm was inside the
                # end-of-rotation tip-jerk envelope
                self._tcp_auto_start = (x, y, z + 3.0)
                self._svy_out({'t': 'ref', 'z': z, 'a': a})
                v['step'] = 'apply'
            elif st == 'z0-wait':
                v['z0'] = z
                v['step'] = 'p-issue'
            elif st == 'p-wait':
                v['zp'] = z
                v['step'] = 'm-issue'
            elif st == 'm-wait':
                v['n'] += 1
                mp, mn = v['zp'] - v['z0'], z - v['z0']
                _to = self._tcp_tooloff()
                self._svy_out({'t': 'pair', 'n': v['n'],
                               'nose': round(v['L'] - _to, 4),
                               'L': round(v['L'], 4),
                               'ofs': round(v['ofs'], 4),
                               'z0': round(v['z0'], 4),
                               'zp': round(v['zp'], 4), 'zm': round(z, 4),
                               'mp': round(mp, 4), 'mn': round(mn, 4),
                               'sum': round(abs(mp) + abs(mn), 4),
                               'diff': round(mp - mn, 4),
                               'tooloff': round(_to, 4)})
                # the number the OPERATOR refers to is the one the param
                # file gets: nose = L - tool (operator 2026-08-06)
                self._tcp_say('pair %d/%d: nose %.3f ofs %+.3f  sum %.4f '
                              'diff %+.4f' % (v['n'], self.SVY_N,
                                              v['L'] - _to, v['ofs'],
                                              abs(mp) + abs(mn), mp - mn))
                # GUI rows AFTER the file write -- a widget failure must
                # never cost data. Two rows per pair, one per side; the
                # last column carries the PARAM number (nose).
                try:
                    nose = v['L'] - _to
                    self._tcp_add_row(v['n'], {
                        'a1': v['ofs'], 'a2': 35.0 + v['ofs'],
                        'z1': v['z0'], 'z2': v['zp'], 'L': nose}, None)
                    self._tcp_add_row(v['n'], {
                        'a1': v['ofs'], 'a2': -35.0 + v['ofs'],
                        'z1': v['z0'], 'z2': z, 'L': nose}, None)
                except Exception:
                    LOG.exception('SURVEY: table row failed -- data is in '
                                  'the ndjson regardless')
                sm = abs(mp) + abs(mn)
                if v.get('best_sum') is None or sm < v['best_sum']:
                    v['best_sum'] = sm
                    v['best_L'] = v['L']
                    self._svy_out({'t': 'best', 'n': v['n'],
                                   'L': round(v['L'], 4),
                                   'nose': round(v['L'] - _to, 4),
                                   'sum': round(sm, 4)})
                v['step'] = 'apply'
            self._tcp_auto_go_next = True
            return
        if self._tcp_auto_ref is None:
            # the one-off A=0 reference, and the start pose every later step
            # returns to -- both in the interpreter's own frame
            self._tcp_auto_ref = (z, a)
            # 5 mm of lift (operator: "raise 5mm, rotate a bit, reprobe")
            self._tcp_auto_start = (x, y, z + 5.0)
            self._tcp_say('reference: Z %.4f at A %.3f. Start pose banked '
                          '5 mm above it -- every step lifts here, rotates, '
                          'and comes back down to probe.' % (z, a))
            # DO NOT issue the next step from inside this callback: it is
            # delivered on the notification poll at an arbitrary moment, and
            # _cal_gate refusing here killed the whole sweep with the puck
            # left up (advisor S8). The tick issues it once genuinely idle.
            self._tcp_auto_go_next = True
            return
        z0, a0 = self._tcp_auto_ref
        if getattr(self, '_tcp_auto_phase', 'ladder') == 'descent':
            # MODEL-LESS (operator 2026-08-05): record the miss, nothing
            # else. No cos, no leverage -- the descent only ever asks
            # "did the tip miss shrink?"
            d = self._tcp_desc
            if d.get('reffing'):
                # zero was nudged -- THIS probe is the fresh reference at
                # the new zero (operator 2026-08-06: "remeasure Z touch
                # with A at zero whenever the A zero is nudged. if not...
                # all the math is wrong" -- the sum metric compares
                # against this Z, and the old one is off by L*(1-cos ofs),
                # 49 um at the 1 deg cap).
                d['reffing'] = False
                self._tcp_auto_ref = (z, a)
                d['ref_ofs'] = d['Acum']
                hist = getattr(self, '_tcp_hist', [])
                hist.append({'t': 'descent-ref', 'z': z, 'a': a,
                             'Acum': d['Acum']})
                self._tcp_hist = hist
                try:
                    self._tcp_save_hist()
                except Exception:
                    LOG.exception('TCP ALT: ref record not saved')
                LOG.error('TCP ALT: reference re-probed at A %+.4f: Z %.4f',
                          a, z)
                self._tcp_auto_go_next = True
                return
            miss = z - z0
            d['probes'][1 if a < 0 else 0] = miss
            _, L_now = self._tcp_kins()
            row = {'t': 'descent', 'a1': a0, 'a2': a, 'z1': z0, 'z2': z,
                   'dz': miss, 'L': L_now, 'kins': 'tcp', 'L_set': L_now}
            hist = getattr(self, '_tcp_hist', [])
            hist.append(row)
            self._tcp_hist = hist
            try:
                self._tcp_save_hist()
                self._tcp_add_row(len(hist), row, None)
            except Exception:
                LOG.exception('TCP DESCENT: display update failed -- '
                              'measurement banked, continuing')
            LOG.error('TCP DESCENT probe: A=%+.2f miss=%+.4f (L in force '
                      '%.4f)', a, miss, L_now)
            # next action decided from the tick, never from this callback
            self._tcp_auto_go_next = True
            return
        den = math.cos(math.radians(a0)) - math.cos(math.radians(a))
        if abs(den) < 1e-6:
            self._tcp_auto_next()
            return
        kind, L_set = self._tcp_kins()
        dL = (z0 - z) / den
        L = L_set + dL
        resid = z - z0
        self._tcp_auto_rows.append((a, resid, L, dL))
        # BANK THE STATE FIRST (advisor S7): a RuntimeError from any widget
        # below would otherwise lose the measurement and stall the sweep --
        # the row would be in the history file but pending_L never set.
        self._tcp_auto_pending_L = L
        import time as _t
        self._tcp_auto_apply_t0 = _t.time()
        LOG.error('TCP AUTO: A=%.3f residual dZ=%+.4f -> dL=%+.4f, L=%.4f',
                  a, resid, dL, L)
        row = {'t': 'auto', 'a1': a0, 'a2': a, 'z1': z0, 'z2': z,
               'dz': resid, 'L': L, 'kins': kind, 'L_set': L_set,
               'tooloff': self._tcp_tooloff()}
        hist = getattr(self, '_tcp_hist', [])
        prev = hist[-1]['L'] if hist else None
        hist.append(row)
        self._tcp_hist = hist
        try:
            self._tcp_save_hist()
            self._tcp_add_row(len(hist), row, prev)
            self._tcp_result.setText('L = %.3f mm' % L)
            # The apply is DEFERRED to the tick. Measured in pb.log
            # 2026-08-05 23:17: this callback is delivered on the 200 ms
            # notification poll AFTER the queued motion (including G1 A0)
            # has physically drained -- but delivery timing is arbitrary,
            # so the tick's own idle + servo-feedback check is what decides
            # when the pivot write is safe, never this callback.
            self._tcp_say('A %.2f deg: residual %+.4f mm -> L %.3f mm -- '
                          'applying once the head is confirmed straight'
                          % (a, resid, L))
        except Exception:
            LOG.exception('TCP AUTO: display update failed -- measurement '
                          'already banked, sweep continues')

    def _svy_out(self, rec):
        import json, time
        rec['ts'] = time.strftime('%F %T')
        try:
            with open(self._svy['log'], 'a') as f:
                f.write(json.dumps(rec) + '\n')
        except Exception:
            LOG.exception('SURVEY: data line NOT saved')

    def _tcp_survey_next(self):
        import random
        v = self._svy
        st = v['step']
        if st == 'ref-issue':
            v['step'] = 'ref-wait'
            self._tcp_auto_issue(0.0, repos=0, puck=1)
            self._puck_sync(True)
            return
        if st == 'apply':
            if v['n'] >= self.SVY_N:
                self._tcp_auto_stop('SURVEY complete: %d pairs -> %s'
                                    % (v['n'], v['log']))
                return
            b = v['best_L']
            h = b * self.SVY_HALF_PCT / 100.0
            v['L'] = random.uniform(b - h, b + h)
            v['ofs'] = random.uniform(*self.SVY_OFS)
            # the sub ended the last touch at A0; the pivot write goes
            # through the guarded tick path, which calls back here
            v['step'] = 'z0-issue'
            self._tcp_apply_queue(v['L'])
            return
        if st == 'z0-issue':
            v['step'] = 'z0-wait'
            self._tcp_auto_issue(v['ofs'], repos=1)
            return
        if st == 'p-issue':
            v['step'] = 'p-wait'
            self._tcp_auto_issue(self.SVY_TILT + v['ofs'], repos=1)
            return
        if st == 'm-issue':
            v['step'] = 'm-wait'
            self._tcp_auto_issue(-self.SVY_TILT + v['ofs'], repos=1)
            return
        # -wait states: a stale go_next lands here; the callback owns them

    def _tcp_auto_next(self):
        if not getattr(self, '_tcp_auto_on', False):
            # STOP must mean stop: without this, a pending apply landing
            # after the operator's stop re-issued a 30 mm plunge onto the
            # puck the park had just RETRACTED (advisor S2).
            LOG.error('TCP AUTO: next step SUPPRESSED -- sweep is stopped')
            return
        i = getattr(self, '_tcp_auto_i', -1) + 1
        self._tcp_auto_i = i
        rows = getattr(self, '_tcp_auto_rows', [])
        if getattr(self, '_tcp_auto_phase', 'ladder') == 'survey':
            self._tcp_survey_next()
            return
        if getattr(self, '_tcp_auto_phase', 'ladder') == 'descent':
            self._tcp_descent_next()
            return
        if len(rows) >= 3 and all(abs(r[3]) < self.TCP_DL_TOL
                                  for r in rows[-3:]):
            self._tcp_descent_begin('ladder CONVERGED early')
            return
        if i >= len(self.TCP_ANGLES):
            self._tcp_descent_begin('ladder swept to 35 deg')
            return
        self._tcp_auto_issue(self.TCP_ANGLES[i], repos=1)

    # ---- FINAL STAGE: alternating secant descent at +-35 deg -----------
    # Operator 2026-08-06, final form: "with one variable each time, you
    # just need 2 numbers to do newton gradient descent... 2 pairs of reads
    # to get a new L, and 2 pairs of reads to get a new A0 and keep
    # alternating... apply annealing. don't move in huge jumps, change
    # values by a quarter of the prescribed change."
    #   L turn: error = |miss(+35)| + |miss(-35)|  (sum of ABSOLUTE errors)
    #   A turn: signed error = miss(+35) - miss(-35)   (the difference)
    # Two evals per turn -- at x and at x+h -- give the secant slope; the
    # Newton step -e/slope is taken at ONE QUARTER, capped. No kinematic
    # formula anywhere: both slopes come from the machine's own reads.
    # A-zero moves bank through _cal_bank (head_zero.inc + REF A in-place
    # re-home, ~15 s each, backed up every write).
    TCP_H_L = 0.30       # mm probe perturbation for the L secant
    TCP_H_A = 0.03       # deg probe perturbation for the A secant
    TCP_ANNEAL = 0.25    # quarter of the prescribed Newton change
    TCP_CAP_L_PCT = 0.5  # never move L more than this per update
    TCP_CAP_A = 0.10     # deg, never move A zero more than this per update
    TCP_E_NOISE = 0.005  # mm; slope smaller than this over h = no update
    TCP_DESC_MAX_EVALS = 200
    # SURVEY (operator 2026-08-06: "just make autoconverge do the random
    # draws, and save the data. that's it"): N pairs, each = random L and
    # random A offset, THREE touches (zero at A=ofs, +35+ofs, -35+ofs),
    # everything to logs/tcp_survey_<stamp>.ndjson.
    SVY_N = 500
    # ADAPTIVE (operator 2026-08-06): draws are ALWAYS +-0.5% around the
    # RUNNING BEST -- start at the banked parameter, recenter on every
    # pair that beats the best sum. A fixed bracket went stale the moment
    # the parameter improved (it sampled 156-160 while truth sat at 155.7).
    # 0.25 (operator 2026-08-06): the optimum is known to ~0.01 mm now;
    # +-0.8 mm of draw brackets it without wasting pairs in the wings
    SVY_HALF_PCT = 0.25
    # 20, not 35 (operator 2026-08-06): jerk persists at soft accel, so
    # the tilt comes down while backlash is chased
    SVY_TILT = 30.0
    SVY_OFS = (-0.30, 0.30)      # A offset draw, deg

    def _tcp_tooloff(self):
        """motion.tooloffset.z in force NOW (0 when no G43 / identity).
        Recorded with every measurement: a record's L is axis->TIP for the
        tool in force THEN, and head_pivot.inc holds axis->NOSE. Tonight's
        records mix sessions at 164.85 and 0 -- a raw record L saved as
        the nose constant double-counts the tool (operator caught it)."""
        try:
            import subprocess
            r = subprocess.run(['timeout', '5', 'halcmd', 'getp', 'arm.in1'],
                               capture_output=True, text=True)
            return float(r.stdout.strip())
        except Exception:
            return 0.0

    def _tcp_descent_begin(self, how):
        _, L0 = self._tcp_kins()
        self._tcp_auto_phase = 'descent'
        self._tcp_desc = {
            'var': 'L', 'stage': 'a',
            'xa': None, 'ea': None,
            'L': L0, 'Acum': 0.0, 'ref_ofs': 0.0, 'reffing': False,
            'Lstep': 0.30, 'Ldir': 0.0,
            'evals': 0, 'probes': [None, None], 'data': [],
            'refwait': False, 'ref_t0': 0.0,
        }
        self._tcp_say('ALTERNATE (%s): 2 pairs -> new L (sum), 2 pairs -> '
                      'new A0 (difference), quarter-step, from L %.3f.'
                      % (how, L0))
        LOG.error('TCP ALT begin (%s): L=%.4f', how, L0)
        self._tcp_auto_issue(35.0, repos=1)

    def _tcp_descent_next(self):
        import time
        d = self._tcp_desc
        if d is None:
            self._tcp_auto_stop('descent state lost')
            return
        if d['probes'][0] is None:
            if d.get('ref_ofs', 0.0) != d['Acum'] and not d.get('reffing'):
                d['reffing'] = True
                self._tcp_say('zero nudged to %+.4f -- re-probing the '
                              'reference there first' % d['Acum'])
                self._tcp_auto_issue(d['Acum'], repos=1)
                return
            # the A variable is a COMMAND OFFSET (operator 2026-08-06:
            # "just offset it so that +35 is +35.01") -- nothing physical
            # changes mid-run, the probes simply target 35+ofs / -35+ofs.
            self._tcp_auto_issue(35.0 + d['Acum'], repos=1)
            return
        if d['probes'][1] is None:
            self._tcp_auto_issue(-35.0 + d['Acum'], repos=1)
            return
        mp, mn = d['probes']
        d['probes'] = [None, None]
        d['evals'] += 1
        # L: ABSOLUTE errors summed (operator 2026-08-06) -- the signed
        # sum would leak the +-asymmetry into the L turn and make L fight
        # the A variable. A: the difference stays SIGNED, its zero
        # crossing IS the target ("makes the error of +-35 EQUAL").
        e = (abs(mp) + abs(mn)) if d['var'] == 'L' else (mp - mn)
        x = d['L'] if d['var'] == 'L' else d['Acum']
        rec = {'t': 'descent-eval', 'n': d['evals'], 'var': d['var'],
               'tooloff': self._tcp_tooloff(),
               'stage': d['stage'], 'L': d['L'], 'Acum': d['Acum'],
               'miss_p35': mp, 'miss_m35': mn,
               'mean': (abs(mp) + abs(mn)) / 2.0,
               'sum': mp + mn, 'diff': mp - mn}
        d['data'].append(rec)
        hist = getattr(self, '_tcp_hist', [])
        hist.append(rec)
        self._tcp_hist = hist
        try:
            self._tcp_save_hist()
        except Exception:
            LOG.exception('TCP ALT: eval record not saved')
        LOG.error('TCP ALT eval %d/%d [%s/%s]: L=%.4f A0+=%.4f  sum=%+.4f '
                  'diff=%+.4f', d['evals'], self.TCP_DESC_MAX_EVALS,
                  d['var'], d['stage'], d['L'], d['Acum'],
                  rec['sum'], rec['diff'])
        self._tcp_say('%s/%s %d: sum %+.4f  diff %+.4f'
                      % (d['var'], d['stage'], d['evals'],
                         rec['sum'], rec['diff']))
        if d['evals'] >= self.TCP_DESC_MAX_EVALS:
            data = d['data']
            best = min(data, key=lambda r: r['mean'])
            # NOT _tcp_apply_queue: _tcp_auto_stop clears that slot two
            # lines later and the "applied" in the message was a lie
            # (advisor F3). The manual slot is consumed after the park
            # lands, through the same guard.
            self._tcp_pending_L = float(best['L'])
            self._tcp_auto_stop(
                'ALTERNATE complete: %d evals in tcp_cal.json. Best '
                'observed: L %.3f (mean|miss| %.4f, eval %d) applied; A0 '
                'net %+.4f deg banked.' % (len(data), best['L'],
                                           best['mean'], best['n'],
                                           d['Acum']))
            return
        if d['stage'] == 'a':
            # first point of the turn banked; perturb by h for the second
            d['xa'], d['ea'] = x, e
            d['stage'] = 'b'
            if d['var'] == 'L':
                d['L'] = d['L'] + self.TCP_H_L
                self._tcp_apply_queue(d['L'])
            else:
                d['Acum'] += self.TCP_H_A     # retarget only, no banking
                self._tcp_auto_issue(35.0 + d['Acum'], repos=1)
            return
        # stage b: decide the move, then switch variable.
        # L: PLAIN GRADIENT DESCENT (operator 2026-08-06: "we cannot do
        # newton on the L step. just gradient descent in the direction of
        # minimizing the abs sum") -- |m+|+|m-| is non-negative, Newton
        # has no zero crossing to aim at. Two evals give the slope's SIGN;
        # step against it; the step HALVES whenever the direction flips
        # (the annealing), floor 0.05 mm, cap 0.5%.
        # A: secant Newton at a quarter step -- the signed difference
        # genuinely crosses zero, so the prescription is meaningful.
        xa, ea, xb, eb = d['xa'], d['ea'], x, e
        de = eb - ea
        if abs(de) < self.TCP_E_NOISE or abs(xb - xa) < 1e-9:
            move = 0.0
            LOG.error('TCP ALT %s: slope below noise (de=%+.4f over '
                      '%+.4f) -- no update this turn', d['var'], de,
                      xb - xa)
        elif d['var'] == 'L':
            gdir = -1.0 if de > 0 else 1.0     # against the slope
            if d['Ldir'] and gdir != d['Ldir']:
                d['Lstep'] = max(0.05, d['Lstep'] / 2.0)
            d['Ldir'] = gdir
            cap = d['L'] * self.TCP_CAP_L_PCT / 100.0
            move = gdir * min(d['Lstep'], cap)
        else:
            newton = -eb * (xb - xa) / de
            move = self.TCP_ANNEAL * newton
            move = max(-self.TCP_CAP_A, min(self.TCP_CAP_A, move))
        d['stage'] = 'a'
        d['xa'] = d['ea'] = None
        # REBASE TO THE TURN'S BASE xa (advisor F2): stepping from
        # xb = xa+h made a downhill turn land exactly back on xa -- zero
        # net progress, all 200 evals burned in place -- and a
        # below-noise turn ratcheted the perturbation in permanently.
        # move == 0 now restores xa exactly, for both variables.
        if d['var'] == 'L':
            d['var'] = 'A'
            d['L'] = xa + move
            self._tcp_say('L -> %.3f (step %+.3f); now A0'
                          % (d['L'], move))
            self._tcp_apply_queue(d['L'])
            return
        d['var'] = 'L'
        d['Acum'] = max(-1.0, min(1.0, xa + move))
        if move != 0.0:
            self._tcp_say('A0 offset -> %+.4f deg; now L' % d['Acum'])
        # through descent_next, NOT a direct issue: the re-reference
        # check lives there, and bypassing it judged the first L pair
        # after an A nudge against the stale reference (advisor F4)
        self._tcp_descent_next()

    def _tcp_apply_queue(self, L):
        """Queue an L write through the ONE guarded path: the tick applies
        at confirmed A=0 + idle, then calls _tcp_auto_next."""
        import time
        self._tcp_auto_pending_L = L
        self._tcp_auto_apply_t0 = time.time()

    def _tcp_auto_stop(self, why):
        self._seq_flag(False)
        self._tcp_auto_on = False
        self._tcp_auto_pending_L = None     # a stop discards the pending
        self._tcp_auto_go_next = False      # apply AND the queued next step
        self._tcp_auto_idle_t0 = None
        self._tcp_set_face()
        rows = getattr(self, '_tcp_auto_rows', [])
        kind, L_now = self._tcp_kins()
        worst = max((abs(r[1]) for r in rows), default=0.0)
        LOG.error('TCP AUTO STOPPED (%s): %d step(s), pivot now %.4f, worst '
                  'residual %.4f mm', why, len(rows), L_now, worst)
        self._tcp_say('AUTO %s. %d step(s), pivot now %.3f mm, worst '
                      'residual %.4f mm. head_pivot.inc is NOT written.'
                      % (why, len(rows), L_now, worst))
        # park A back at zero, tip back over the puck
        # the net A0 offset banks ONCE, at the very end, through the AC
        # tab's proven path (_cal_bank: head_zero.inc + REF A encoder
        # read + in-place re-home). Mid-run banking is what wedged on the
        # unpowered PSO. Deferred until the park has landed -- REF unhomes
        # A, and the park still has to move.
        st = getattr(self, '_tcp_auto_start', None)
        try:
            gate = self._cal_gate('TCP AUTO park')
            if gate:
                c, _ = gate
                # bank flag only ONCE the park is really issued -- set
                # earlier, a refused gate stranded it and the stale bank
                # fired on some LATER run's park (advisor F5a)
                d0 = getattr(self, '_tcp_desc', None)
                if (getattr(self, '_tcp_auto_phase', '') == 'descent'
                        and d0 and abs(d0.get('Acum', 0.0)) > 0.005):
                    self._tcp_bank_after_park = d0['Acum']
                import time
                if st:
                    # plunge 0 = MOVE ONLY; puck -1 retracts it
                    c.mdi('o<tcp_auto_step> call [0] [1] [%.4f] [%.4f] '
                          '[%.4f] [0] [-1]' % (st[0], st[1], st[2]))
                else:
                    # no start pose yet (stopped before the reference
                    # landed): no motion, but the puck must still come down
                    # -- an energised solenoid bleeds the air (advisor S13)
                    c.mdi('M65 P3')
                # feed override was pinned by M50 P0 in the sub; an abort
                # skips its own restore (advisor S12)
                c.mdi('M50 P1')
                self._puck_sync(False)
                self._tcp_manual_pending = True
                self._tcp_manual_t0 = time.time()
        except Exception:
            LOG.exception('TCP AUTO: final park failed')

    def _tcp_apply(self, L):
        """Push the measured pivot into the LIVE kins.

        This is what closes the operator's loop: "applying the updated
        parameter, and repeat until the deltaZ is sufficiently close to
        zero". Without it every pair re-measures the same error and the
        residual never moves.

        WRITES arm.in0 = L - live tool length, NOT L. arm.in0 is the
        MACHINE constant (A axis -> spindle nose); the arm sum2 adds
        motion.tooloffset.z on top, so a different tool gets its own L for
        free. Storing L itself would bake THIS rod's stickout into the
        number that has to serve every tool.

        RUNTIME ONLY. head_pivot.inc is the operator's to commit, and it
        should receive the axis->nose constant, not L.

        REFUSES OFF ZERO: pivot length only cancels out of the Z solution
        at A=0. Changing it at a tilt would step the world position under
        the machine."""
        try:
            import subprocess
            # A FROM HAL, NOT FROM stat. This guard is the only thing
            # standing between a pivot write and a servo jerk, and stat has
            # already been caught lying tonight -- it reported g5x_offset as
            # zeros while the interpreter held G54 at -512.205, which sent a
            # probe to machine -959. joint.4.pos-fb is the servo's own
            # feedback and cannot be stale.
            r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                'joint.4.pos-fb'],
                               capture_output=True, text=True)
            try:
                a_live = float(r.stdout.strip())
            except ValueError:
                LOG.error('TCP APPLY REFUSED: could not read joint.4.pos-fb '
                          '-- refusing to write the pivot blind')
                return None
            if abs(a_live) > 0.05:
                LOG.error('TCP APPLY REFUSED: A is at %.4f deg (servo '
                          'feedback). Pivot length is a kinematics term: '
                          'writing it here steps the solution by '
                          'dL*sin(A) in Y and faults the joints. Pin left '
                          'alone.', a_live)
                return None
            r = subprocess.run(['timeout', '5', 'halcmd', 'getp', 'arm.in1'],
                               capture_output=True, text=True)
            try:
                tlen = float(r.stdout.strip())
            except ValueError:
                LOG.error('TCP APPLY: no arm sum2 (identity kins, or the '
                          'tcp postgui did not load) -- nothing to apply')
                return None
            D = L - tlen
            subprocess.run(['timeout', '5', 'halcmd', 'setp', 'arm.in0',
                            '%.4f' % D], capture_output=True)
            v = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                'ned_ac_kins.pivot-length'],
                               capture_output=True, text=True)
            LOG.error('TCP APPLY: axis->nose %.4f written to arm.in0 '
                      '(L %.4f - tool length %.4f); pivot-length now reads '
                      '%s. RUNTIME ONLY -- head_pivot.inc still holds the '
                      'old value until you commit it.',
                      D, L, tlen, v.stdout.strip())
            return D
        except Exception:
            LOG.exception('TCP APPLY failed -- pivot NOT updated')
            return None

    def _tcp_set_face(self):
        auto = getattr(self, '_tcp_auto_on', False)
        ab = getattr(self, '_tcp_auto_btn', None)
        if ab is not None:
            ab.setText('STOP AUTO' if auto else 'AUTO CONVERGE')
            ab.setStyleSheet(self.CAL_QSS['clearArmed'] if auto
                             else self.CAL_QSS['measure'])
        st = getattr(self, '_tcp_state', 'idle')
        b = getattr(self, '_tcp_btn', None)
        if b is None:
            return
        if auto:
            b.setText('AUTO RUNNING')
            b.setEnabled(False)
            return
        if st == 'rotate':
            b.setText('PLUNGE')
            b.setStyleSheet(self.CAL_QSS.get('measure', ''))
            b.setEnabled(True)
        elif st in ('wait1', 'wait2'):
            b.setText('PROBING...')
            b.setEnabled(False)
        else:
            b.setText('START')
            b.setStyleSheet(self.CAL_QSS['pose'])
            b.setEnabled(True)

    def _tcp_say(self, msg, bad=False):
        (LOG.error if bad else LOG.info)('TCP CAL: %s', msg)
        self.cal_say(('!! ' if bad else '>> ') + msg)
        w = getattr(self, '_tcp_status', None)
        if w is not None:
            w.setText(msg)

    def _tcp_press(self):
        if getattr(self, '_tcp_state', 'idle') == 'rotate':
            self._tcp_touch(2)
        else:
            self._tcp_touch(1)

    def _tcp_touch(self, which):
        import math, time
        gate = self._cal_gate('TCP CAL')
        if gate is None:
            return
        if self._tool_state_locked():
            self._tcp_say('TOOL-STATE LOCK is engaged -- feed is inhibited, '
                          'so this cycle would STALL at zero feed instead of '
                          'failing. Declare the tool in the spindle first.',
                          bad=True)
            # the gate above switched to MDI; leaving it there kills the MPG
            self._hand_back_manual(gate[0], 'TCP CAL')
            return
        c, s = gate
        s.poll()
        a_now = self._tcp_work(s, 3)
        # FIXED PLUNGE, both touches, straight down from wherever the
        # operator parked (operator 2026-08-05: "just plunge 30mm. user
        # will put probe so that it will contact on plunge").
        # NO ABSOLUTE TARGET IS COMPUTED HERE ANY MORE. It used to send
        # z_now - plunge, with z_now from stat.actual_position minus
        # stat.g5x_offset -- and stat reported zero offsets while the
        # interpreter had G54 live at Z -512.205, so the "work" target of
        # -447 arrived as machine -959 and motion refused it instantly:
        # "Probe move on line 44 would exceed Z's negative limit", no
        # movement at all. The sub is incremental now; G91 has no frame to
        # get wrong, and every absolute it does use is derived from #5063.
        plunge = self._tcp_field(self._tcp_plunge, 30.0, 2.0, 80.0)
        if which == 1:
            self._tcp_pts = []
            self._tcp_result.setText('L = ---')
            self._tcp_say('touch 1: plunging %.1f mm from here. Puck goes '
                          'UP and STAYS up until the pair is done.' % plunge)
        else:
            z1, a1 = self._tcp_pts[0]
            den = (math.cos(math.radians(a1)) - math.cos(math.radians(a_now)))
            if abs(den) < 0.005:
                self._tcp_say('A has moved only %.2f deg from touch 1 -- '
                              'cos separation %.4f is too small to solve. '
                              'Rotate further and press again.'
                              % (a_now - a1, den), bad=True)
                return
            self._tcp_say('touch 2 at A %.2f deg: plunging %.1f mm from '
                          'here.' % (a_now, plunge))
        self._tcp_state = 'wait%d' % which
        self._tcp_t0 = time.time()
        self._tcp_set_face()
        c.mdi('o<tcp_touch> call [%.4f] [%d] [%.4f]'
              % (plunge, 1 if which == 1 else 0, 15.0))
        LOG.error('TCP CAL touch %d ISSUED: plunge %.1f mm INCREMENTAL, '
                  'hover 15.0 above contact (A now %.3f)',
                  which, plunge, a_now)

    def tcp_cal_point(self, zt, at):
        """Called BY THE G-CODE at the probe trip -- the only place the
        measurement enters. Loud on every landing: a silent probe is
        indistinguishable from a missed one."""
        import time
        pts = getattr(self, '_tcp_pts', [])
        pts.append((float(zt), float(at)))
        self._tcp_pts = pts
        n = len(pts)
        LOG.error('TCP CAL touch %d LANDED: Z=%.4f  A=%.3f deg', n, zt, at)
        self.cal_say('   touch %d: Z %.4f   A %.3f' % (n, zt, at))
        if n == 1:
            self._tcp_state = 'rotate'
            self._tcp_set_face()
            # HAND THE MACHINE BACK. The next thing the operator does is
            # rotate A on the MPG, and the MPG is dead in MDI. _tcp_tick
            # does it once the retract has genuinely finished -- switching
            # mode here would abort the move still in flight.
            self._tcp_manual_pending = True
            self._tcp_manual_t0 = time.time()
            self._tcp_say('touch 1 banked. ROTATE A on the MPG until the '
                          'needle still sits over the puck, then PLUNGE.')
            return
        self._tcp_solve()

    def _tcp_solve(self):
        import math, time
        (z1, a1), (z2, a2) = self._tcp_pts[0], self._tcp_pts[1]
        den = math.cos(math.radians(a1)) - math.cos(math.radians(a2))
        if abs(den) < 0.005:
            self._tcp_say('angles too close to solve (den %.5f)' % den,
                          bad=True)
            self._tcp_state = 'rotate'
            self._tcp_set_face()
            return
        kind, L_set = self._tcp_kins()
        dL = (z1 - z2) / den
        L = L_set + dL
        hist = getattr(self, '_tcp_hist', [])
        prev = hist[-1]['L'] if hist else None
        row = {'t': time.strftime('%F %T'), 'a1': a1, 'a2': a2,
               'z1': z1, 'z2': z2, 'dz': z2 - z1, 'L': L, 'kins': kind,
               'L_set': L_set}
        hist.append(row)
        self._tcp_hist = hist
        self._tcp_save_hist()
        self._tcp_add_row(len(hist), row, prev)
        self._tcp_result.setText('L = %.3f mm' % L)
        self._tcp_pending_L = L
        chg = ('' if prev is None else '   change %+.3f mm' % (L - prev))
        self._tcp_say('L = %.3f mm  [%s kins, pivot in force %.3f, dZ '
                      '%+.4f over %.2f deg]%s'
                      % (L, kind, L_set, z2 - z1, a2 - a1, chg))
        LOG.error('TCP CAL RESULT: L=%.4f mm (dL=%+.4f on %.4f in force); '
                  'z1=%.4f a1=%.3f  z2=%.4f a2=%.3f  den=%.5f -- NOT '
                  'written to head_pivot.inc, that stays the operator call',
                  L, dL, L_set, z1, a1, z2, a2, den)
        self._tcp_park(z1)

    def _tcp_park(self, z1):
        """Safe Z, puck down, A to 0, then dead centre 10 mm over the puck."""
        try:
            import linuxcnc
            gate = self._cal_gate('TCP PARK')
            if gate is None:
                self._tcp_state = 'idle'
                self._tcp_set_face()
                return
            c, s = gate
            s.poll()
            clear = self._tcp_field(self._tcp_clear, 30.0, 10.0, 150.0)
            # z1 IS #5063, the interpreter's own reading, so a clearance
            # measured from it lands in the same frame no matter which WCS
            # is live. Do NOT re-introduce a stat-derived limit here: that
            # is exactly the arithmetic that sent the probe to machine -959.
            zsafe = z1 + clear
            # XY comes from G30 (#5181/#5182, MACHINE coords) inside the
            # sub, NOT from #3045/#3046: those are written from #5061/#5062
            # and so are WORK-frame numbers, valid only in the frame that
            # was active when the puck was measured. They currently equal
            # G30 exactly, which means they were taken with a zero offset --
            # G54 is offset by tens of mm today, so a G90 move to them would
            # park somewhere else entirely (2026-08-05).
            c.mdi('o<tcp_park> call [%.4f] [%.4f]' % (z1, zsafe))
            # The park is MOTION, so MANUAL cannot be restored here -- a mode
            # switch aborts motion mid-move. _tcp_tick does it once the park
            # has genuinely finished, which matters: the next iteration needs
            # the MPG to rotate A, and the MPG is dead in MDI.
            import time as _t
            self._tcp_manual_pending = True
            self._tcp_manual_t0 = _t.time()
            LOG.error('TCP PARK issued: safe Z %.4f, then G30 XY (machine) '
                      'and finish 10 mm over the touch-1 contact %.4f',
                      zsafe, z1)
        except Exception:
            LOG.exception('TCP PARK failed to issue')
        self._tcp_state = 'idle'
        self._tcp_pts = []
        self._tcp_set_face()

    def _tcp_tick(self):
        """A probe that aborts never calls back. Without this the button
        would sit on PROBING... forever (the exact failure mode the AC tab
        hit in 2026-08-03 when only a/c armed the watcher)."""
        import time
        if getattr(self, '_tcp_manual_pending', False):
            if time.time() - getattr(self, '_tcp_manual_t0', 0) > 2.0:
                try:
                    import linuxcnc
                    s2 = linuxcnc.stat()
                    s2.poll()
                    if s2.interp_state == linuxcnc.INTERP_IDLE and s2.inpos:
                        self._tcp_manual_pending = False
                        self._hand_back_manual(linuxcnc.command(), 'TCP CAL')
                        v0 = getattr(self, '_svy', None)
                        _fb = 99.0
                        try:
                            import subprocess as _sp
                            _fb = abs(float(_sp.run(
                                ['timeout', '5', 'halcmd', 'getp',
                                 'joint.4.pos-fb'], capture_output=True,
                                text=True).stdout.strip()))
                        except Exception:
                            LOG.exception('SURVEY: restore fb read failed')
                        if (v0 and v0.get('arm0_saved') is not None
                                and _fb <= 0.05):
                            import subprocess as _sp
                            _sp.run(['timeout', '5', 'halcmd', 'setp',
                                     'arm.in0', '%.4f' % v0['arm0_saved']],
                                    capture_output=True)
                            LOG.error('SURVEY: arm.in0 RESTORED to the '
                                      'saved parameter %.4f',
                                      v0['arm0_saved'])
                            v0['arm0_saved'] = None
                        ab = getattr(self, '_tcp_bank_after_park', None)
                        if ab is not None:
                            self._tcp_bank_after_park = None
                            self._tcp_say('banking net A0 %+.4f deg via '
                                          'REF A (the proven AC path)' % ab)
                            self._cal_bank('A', ab, 'refa-out', '3069',
                                           0.0, 0.0)
                        # the park has landed and A is back at 0: the one
                        # moment the pivot can change without stepping the
                        # world position
                        L = getattr(self, '_tcp_pending_L', None)
                        if L is not None:
                            self._tcp_pending_L = None
                            D = self._tcp_apply(L)
                            if D is not None:
                                self._tcp_say(
                                    'APPLIED: axis->nose %.3f mm is live. '
                                    'Next pair is a NULL test -- with L '
                                    'right, the touch Z is the SAME at '
                                    'every A and dZ collapses to zero.' % D)
                except Exception:
                    LOG.exception('TCP PARK: hand-back poll failed')
        # AUTO: apply the pending pivot as soon as the head is genuinely
        # straight and the interpreter is idle, and only then take the next
        # step. Serialising it this way is what makes each larger tilt
        # compensate with the improved pivot.
        if getattr(self, '_tcp_auto_pending_L', None) is not None:
            # the 45 s deadline lives OUTSIDE the try: a halcmd that keeps
            # failing used to raise BEFORE the elif, so the deadline was
            # unreachable and the sweep hung forever (advisor S5)
            ok, a_live = False, float('nan')
            try:
                import linuxcnc, subprocess
                s4 = linuxcnc.stat()
                s4.poll()
                r = subprocess.run(['timeout', '5', 'halcmd', 'getp',
                                    'joint.4.pos-fb'],
                                   capture_output=True, text=True)
                a_live = float(r.stdout.strip())
                ok = (s4.interp_state == linuxcnc.INTERP_IDLE and s4.inpos
                      and abs(a_live) <= 0.05)
            except Exception:
                LOG.exception('TCP AUTO: deferred-apply poll failed')
            if ok:
                L = self._tcp_auto_pending_L
                self._tcp_auto_pending_L = None
                D = self._tcp_apply(L)
                if D is None:
                    if getattr(self, '_tcp_auto_on', False):
                        self._tcp_auto_stop('pivot apply failed -- '
                                            'continuing would mislabel L '
                                            'in every later record')
                    return
                self._tcp_say('APPLIED at A %.4f: axis->nose %.3f mm'
                              % (a_live, D))
                self._tcp_auto_next()
            elif time.time() - getattr(self, '_tcp_auto_apply_t0',
                                       0) > 45.0:
                self._tcp_auto_pending_L = None
                self._tcp_auto_stop('head never returned to zero, so the '
                                    'pivot could not be applied safely')
            return
        if getattr(self, '_tcp_auto_go_next', False):
            # the reference probe's next step, issued from HERE and not from
            # the notification callback: the callback arrives at an
            # arbitrary moment and _cal_gate refusing there killed the sweep
            # with the puck left up (advisor S8)
            try:
                import linuxcnc
                s5 = linuxcnc.stat()
                s5.poll()
                if s5.interp_state == linuxcnc.INTERP_IDLE and s5.inpos:
                    self._tcp_auto_go_next = False
                    self._tcp_auto_next()
            except Exception:
                LOG.exception('TCP AUTO: first-step poll failed')
            return
        if getattr(self, '_tcp_auto_on', False):
            # A STEP THAT ABORTED NEVER CALLS BACK -- that is the ONLY
            # failure visible from here. Do NOT test A against the target:
            # the sub ends every step with G1 A0, so a SUCCESSFUL step
            # leaves A at zero and the old test fired on success. Proven in
            # pb.log 2026-08-05 23:17:08.733 -- aborted 79 ms BEFORE the
            # reading arrived, and a good measurement at A=1.0000 was
            # thrown away (advisor S1). Instead: 2 s of continuous idle
            # with nothing pending and no callback = the step died.
            if time.time() - getattr(self, '_tcp_auto_t0', 0) > 5.0:
                quiet = False
                try:
                    import linuxcnc
                    s3 = linuxcnc.stat()
                    s3.poll()
                    quiet = (s3.interp_state == linuxcnc.INTERP_IDLE
                             and s3.inpos)
                except Exception:
                    LOG.exception('TCP AUTO: watchdog poll failed')
                if not quiet:
                    self._tcp_auto_idle_t0 = None
                else:
                    t = getattr(self, '_tcp_auto_idle_t0', None)
                    if t is None:
                        self._tcp_auto_idle_t0 = time.time()
                    elif time.time() - t > 2.0:
                        v = getattr(self, '_svy', None)
                        if (getattr(self, '_tcp_auto_phase', '') == 'survey'
                                and v
                                and str(v.get('step', '')).endswith('-wait')
                                and v.get('retry', 0) < 2):
                            v['retry'] = v.get('retry', 0) + 1
                            v['step'] = v['step'].replace('-wait', '-issue')
                            self._tcp_auto_idle_t0 = None
                            LOG.error('SURVEY: step lost (MDI refused or no '
                                      'callback) -- RETRY %d', v['retry'])
                            self._tcp_survey_next()
                        else:
                            self._tcp_auto_stop('the step ended with no '
                                                'probe trip -- aborted')
        st = getattr(self, '_tcp_state', 'idle')
        if st not in ('wait1', 'wait2'):
            return
        if time.time() - getattr(self, '_tcp_t0', 0) < 3.0:
            return
        try:
            import linuxcnc
            s = linuxcnc.stat()
            s.poll()
            if s.interp_state != linuxcnc.INTERP_IDLE:
                return
        except Exception:
            return
        n = len(getattr(self, '_tcp_pts', []))
        want = 1 if st == 'wait1' else 2
        if n >= want:
            return
        self._tcp_state = 'rotate' if n == 1 else 'idle'
        self._tcp_set_face()
        self._tcp_say('touch %d did NOT land -- the cycle ended with no '
                      'probe trip. The needle was most likely not over the '
                      'puck. Puck is still UP.' % want, bad=True)

    def _tcp_add_row(self, n, row, prev):
        try:
            from PySide6.QtWidgets import QTableWidgetItem
            t = getattr(self, '_tcp_table', None)
            if t is None:
                return
            r = t.rowCount()
            t.insertRow(r)
            for col, txt in enumerate(
                    (str(n), '%.2f' % row['a2'], '%.4f' % row['z1'],
                     '%.4f' % row['z2'], '%+.4f' % (row['z2'] - row['z1']),
                     '%.3f' % row['L'])):
                t.setItem(r, col, QTableWidgetItem(txt))
            t.scrollToBottom()
        except Exception:
            LOG.exception('TCP CAL: could not add the improvement row')

    def _tcp_clear_data(self):
        """Empty the table AND the memory AND the file -- the file goes to
        trash/ (never rm), and the in-memory history is reset too, or the
        next eval would silently resurrect everything from RAM (watched
        that happen 2026-08-06 00:23: file trashed on disk, sweep re-wrote
        it from memory within seconds)."""
        try:
            import os, shutil, time
            if os.path.exists(self.TCP_HIST):
                dst = ('/home/brains/Documents/ned/trash/configs/ned5_pb/'
                       'tcp_cal.json.%s' % time.strftime('%Y%m%d-%H%M%S'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(self.TCP_HIST, dst)
            self._tcp_hist = []
            d = getattr(self, '_tcp_desc', None)
            if d:
                d['data'] = []
            t = getattr(self, '_tcp_table', None)
            if t is not None:
                t.setRowCount(0)
            self._tcp_result.setText('L = ---')
            self._tcp_say('DATA CLEARED -- history trashed, table empty.')
            LOG.error('TCP CAL: data cleared by the operator (trashed)')
        except Exception:
            LOG.exception('TCP CAL: clear failed')

    def _tcp_save_hist(self):
        try:
            import json
            with open(self.TCP_HIST, 'w') as f:
                json.dump(getattr(self, '_tcp_hist', []), f, indent=1)
        except Exception:
            LOG.exception('TCP CAL: history not saved')

    def _tcp_load_hist(self):
        import json
        self._tcp_hist = []
        try:
            with open(self.TCP_HIST) as f:
                self._tcp_hist = json.load(f)
        except Exception:
            return
        prev = None
        for i, row in enumerate(self._tcp_hist):
            if str(row.get('t', '')).startswith('descent-'):
                continue        # bookkeeping rows: in the file, not the table
            self._tcp_add_row(i + 1, row, prev)
            prev = row['L']
        rows = [r for r in self._tcp_hist if 'L' in r]
        if rows:
            # not hist[-1]: a descent-ref record carries no 'L', and the
            # KeyError here took down the entire subtab build (advisor F7)
            self._tcp_result.setText('L = %.3f mm' % rows[-1]['L'])
            LOG.info('TCP CAL: %d earlier measurement(s) restored, last '
                     'L=%.3f', len(rows), rows[-1]['L'])

    def cal_pivot_point(self, zt, at):
        # CAL PIVOT collector (operator 2026-08-05): each PIVOT TOUCH press
        # probes the puck and lands here with the trigger Z and the REAL A
        # angle. 2 touches = L from the pair (first-order exposed to A-axis
        # tilt vs bed); 3 touches (-theta, 0, +theta order free) = the
        # symmetric solve that cancels axis tilt and A-zero error. Touches
        # more than 10 min apart start a fresh set.
        import time, math
        now = time.time()
        pts = getattr(self, '_pivot_pts', [])
        if pts and now - pts[-1][2] > 600:
            pts = []
        pts.append((float(zt), float(at), now))
        self._pivot_pts = pts
        n = len(pts)
        LOG.error('CAL PIVOT touch %d: Z=%.4f A=%.3f deg', n, zt, at)
        if n < 2:
            return
        if n == 2:
            (z1, a1, _), (z2, a2, _) = pts
            den = (math.cos(math.radians(a1)) - math.cos(math.radians(a2)))
            if abs(den) < 0.01:
                LOG.error('CAL PIVOT: angles too close (den=%.4f) -- tilt '
                          'more and touch again', den)
                return
            # SIGN (verified against ned_ac_kins.c 2026-08-05): the tip
            # RISES with tilt, so the machine must descend FURTHER and z2 is
            # BELOW z1. z(a) = const + L*cos(a)  =>  L = (z1-z2)/(cosA1-cosA2).
            # This read (z2-z1) and every measurement came out NEGATIVE, so
            # _pivot_write's positivity guard silently refused all of them.
            L = (z1 - z2) / den
            LOG.error('CAL PIVOT (2-touch): L=%.3f mm -- one more touch at '
                      'the OPPOSITE tilt upgrades accuracy', L)
            self._pivot_write(L, '2-touch')
            return
        # 3 touches: least-squares fit of z = z0 - L*cos(a) over all three
        # (the symmetric solve; also tolerant of any touch order)
        import statistics
        zs = [p[0] for p in pts[:3]]
        cs = [math.cos(math.radians(p[1])) for p in pts[:3]]
        cbar = sum(cs) / 3.0
        zbar = sum(zs) / 3.0
        num = sum((c - cbar) * (z - zbar) for c, z in zip(cs, zs))
        den = sum((c - cbar) ** 2 for c in cs)
        if den < 1e-6:
            LOG.error('CAL PIVOT: three touches but no angle spread')
            return
        # slope of z on cos(a) IS +L (see the 2-touch note above)
        L = num / den
        LOG.error('CAL PIVOT (3-touch symmetric): L=%.3f mm', L)
        self._pivot_write(L, '3-touch')
        self._pivot_pts = []

    def _pivot_write(self, L, how):
        try:
            if L <= 0 or L > 1000:
                LOG.error('CAL PIVOT: L=%.3f is not physical -- NOT '
                          'written', L)
                return
            path = ('/home/brains/Documents/ned/configs/params/'
                    'head_pivot.inc')
            import time
            with open(path, 'w') as f:
                f.write('# head pivot length (A axis centerline -> tool '
                        'tip at touch)\n'
                        '# measured %s by CAL PIVOT (%s); tool length of '
                        'the touching tool INCLUDED --\n'
                        '# the arm sum2 subtracts/adds the live tool '
                        'offset around the base value\n'
                        'PIVOT_LENGTH = %.4f\n'
                        % (time.strftime('%F %T'), how, L))
            LOG.error('CAL PIVOT: head_pivot.inc written: %.4f (%s)', L, how)
        except Exception:
            LOG.exception('CAL PIVOT: write failed')

    def _heal_banned_locs(self):
        # P RESTRICTS LOC (operator 2026-08-04: "any ambiguous change drops
        # LOC to TABLE. the table is the ground truth"): a rack-map record
        # in a fork that is not the tool's assigned home is ambiguous and
        # gets swept to TABLE automatically, through the same atomic sub
        # every declaration uses. One heal per pass, loudly logged.
        import time
        if time.time() < getattr(self, '_heal_next', 0):
            return
        self._heal_next = time.time() + 5.0
        try:
            import linuxcnc, sqlite3
            st = linuxcnc.stat(); st.poll()
            if (st.task_state != linuxcnc.STATE_ON
                    or st.interp_state != linuxcnc.INTERP_IDLE
                    or not all(st.homed[:NJ])):
                return
            con = sqlite3.connect(
                'file:/home/brains/Documents/ned/configs/ned5_pb/'
                'tool_table.db?mode=ro', uri=True)
            homes = {}
            for tno, pk in con.execute('SELECT tool_no, pocket FROM tool'):
                try:
                    homes[int(tno)] = int(float(pk))
                except (TypeError, ValueError):
                    continue
            con.close()
            occ = {}
            with open('/home/brains/Documents/ned/configs/ned5_pb/'
                      'ned5_pb.var') as f:
                for ln in f:
                    bits = ln.split()
                    if len(bits) == 2:
                        try:
                            p, v = int(bits[0]), int(float(bits[1]))
                        except ValueError:
                            continue
                        if 4001 <= p <= 4024 and v:
                            occ[p - 4000] = v
            for fork, tool in occ.items():
                if homes.get(tool) != fork:
                    LOG.error('AMBIGUOUS LOC: T%d recorded in fork %d but '
                              'its home is %s -- dropping to TABLE (the '
                              'table is the ground truth)', tool, fork,
                              homes.get(tool, 'unset'))
                    c = linuxcnc.command()
                    if not self._take_mdi(c, 'AMBIGUOUS LOC heal'):
                        return
                    c.mdi('o<tool_loc_declare> call [%d] [-1]' % tool)
                    self._hand_back_manual(c, 'AMBIGUOUS LOC heal')

                    return          # one per pass; next pass rechecks
        except Exception:
            LOG.exception('LOC healer failed')

    def _update_spindle_remark(self):
        # ATC spindle label shows the loaded tool's REMARK (operator
        # 2026-08-04: "populate it with remark in the tool col"); DB read
        # only on tool-number change, read-only connection
        try:
            import linuxcnc
            st = linuxcnc.stat(); st.poll()
            tno = int(st.tool_in_spindle)
            if tno == getattr(self, '_remark_tool', None):
                return
            self._remark_tool = tno
            if tno > 0:
                self._anon_clear('T%d declared' % tno)
            lab = self.window().findChild(QWidget,
                                          'loaded_spindle_tool_number')
            if lab is None:
                return
            if tno <= 0:
                lab.setText('NO TOOL LOADED')
                return
            import sqlite3
            con = sqlite3.connect(
                'file:/home/brains/Documents/ned/configs/ned5_pb/'
                'tool_table.db?mode=ro', uri=True)
            row = con.execute('SELECT remark FROM tool WHERE tool_no=?',
                              (tno,)).fetchone()
            con.close()
            rem = (row[0] or '').strip() if row else ''
            lab.setText('T%d · %s' % (tno, rem) if rem else 'T%d' % tno)
        except Exception:
            LOG.exception('spindle remark update failed')

    # PER-AXIS JOG STEPS ON SCREEN (operator 2026-08-05, asked repeatedly):
    # the wheel has always used a per-axis ladder (ned_pendant.INC_TABLE);
    # the stock increment row showed one global list, so screen and wheel
    # disagreed. Relabel the row for the SELECTED axis every time it
    # changes. DISPLAY ONLY -- the wheel owns the slot.
    # THE LADDER LIVES IN ned_pendant.INC_TABLE -- imported, never copied,
    # so screen and wheel can never drift apart (X tops out at 2 mm, Y/Z at
    # 1 mm, rotaries at 0.25/0.5 deg). The SLOT index is shared across axes:
    # pick "fastest" once and every axis applies its own fastest value.
    @property
    def _INC_LADDER(self):
        t = getattr(self, '_inc_ladder_cache', None)
        if t is None:
            try:
                src = open('/home/brains/Documents/ned/tools/live/'
                           'ned_pendant.py').read()
                ns = {}
                exec(src[src.index('INC_TABLE = {'):
                         src.index('N_INC =')], ns)
                t = ns['INC_TABLE']
            except Exception:
                LOG.exception('JOG STEPS: could not read the pendant ladder')
                t = {'x': [0.01, 0.05, 0.1, 0.5, 2.0],
                     'y': [0.01, 0.05, 0.1, 0.5, 1.0],
                     'z': [0.01, 0.05, 0.1, 0.5, 1.0],
                     'a': [0.01, 0.05, 0.1, 0.25, 0.5],
                     'c': [0.01, 0.05, 0.1, 0.25, 0.5],
                     # B is the workpiece rotary (-xyzab). Same ladder
                     # as the head rotaries -- also degrees, also a
                     # worm drive. Defined in every mode so a lookup
                     # can never KeyError on a mode switch.
                     'b': [0.01, 0.05, 0.1, 0.25, 0.5]}
            # The rotary slot's letter is a launch-time fact, but the
            # ladder is read from a file written for the XYZAC
            # machine. If the mode's letter is missing, mirror the
            # one it replaces rather than KeyError in a jog handler.
            if ROT not in t and 'c' in t:
                t = dict(t, **{ROT: list(t['c'])})
            self._inc_ladder_cache = t
        return t
    # Slot 4 is the second rotary. In -xyzab the wheel's 4th slot,
    # its jog pins and its DRO row all point at B (postgui_b.hal,
    # dros_xyzac.DRO_JOINT), so the increment row and the MPG zero
    # must say B too -- otherwise a wheel-zero on the rotary would
    # emit G10 L20 P0 C0 and set the offset of the axis that is
    # parked and clamped, silently doing nothing the operator asked.
    _INC_AXES = (('x', 'y', 'z', 'a', 'b')
                 if os.environ.get('NED_MODE', '') == 'xyzab'
                 else ('x', 'y', 'z', 'a', 'c'))

    def _sync_inc_row(self):
        try:
            from PySide6.QtWidgets import QAbstractButton
            w = self.window().findChild(QWidget, 'jogincrement')
            if w is None:
                return
            btns = w.findChildren(QAbstractButton)
            if len(btns) < 5:
                return
            ax = self._INC_AXES[int(getattr(self, '_mpg_axis_now', 0)) % 5]
            lad = self._INC_LADDER[ax]
            unit = 'MM' if ax in 'xyz' else 'DEG'
            if getattr(self, '_inc_row_ax', None) != ax:
                self._inc_row_ax = ax
                for b, v in zip(btns[-5:], lad):
                    b.setText(('%g %s' % (v, unit)))
                if not getattr(self, '_inc_row_wired', False):
                    self._inc_row_wired = True
                    for i, b in enumerate(btns[-5:]):
                        b.clicked.connect(
                            lambda _=False, k=i: self._inc_pick(k))
                LOG.info('JOG STEPS: row relabelled for %s: %s',
                         ax.upper(), lad)
        except Exception:
            if not getattr(self, '_incrow_err', False):
                self._incrow_err = True
                LOG.exception('JOG STEPS: row sync failed')

    def _inc_pick(self, idx):
        # operator clicked a step: hand the slot to the wheel, which is the
        # single publisher of the applied value (and of the DRO's block)
        try:
            self.comp.getPin('inc-set-out').value = int(idx)
            LOG.info('JOG STEPS: slot %d selected on screen', idx)
        except Exception:
            LOG.exception('JOG STEPS: could not hand the slot to the wheel')

    # ---- PID TRACKING = the A+C random survey (operator 2026-08-06:
    # "make this the PID tracking button"). One press: verify the FULL
    # +-90/+-180 ball fits the soft limits from the parked pose, then
    # PIDT_LEGS random simultaneous (A, C, F) legs, direct pose-to-pose,
    # NO zero-returns, 2 s settle each stop (tcp_pidt_ac.ngc), ends AT
    # the last pose. STOP = press again (aborts mid-leg, stays put).
    # Data: logs/ac_survey_*.ndjson (a, c, F, timestamps per leg); the
    # external 6 Hz HAL logger supplies the error traces.
    # Prior single-axis waypoint version retired same day -- its
    # accel/feed results are banked in
    # docs/commissioning/ac_motion_tuning_2026-08-06.md.
    PIDT_LEGS = 100000   # effectively endless; STOP is the end
    PIDT_A_BALL = 90.0
    PIDT_C_BALL = 180.0
    PIDT_F_RANGE = (600.0, 600.0)   # 800 tripped joint 2 ferror

    def _pidt_press(self):
        import math, random, time as _t
        if getattr(self, '_pidt_on', False):
            self._pidt_stop('STOPPED by the operator')
            return
        if getattr(self, '_tcp_auto_on', False):
            self._tcp_say('AUTO CONVERGE is running -- stop it first.',
                          bad=True)
            return
        if self._tool_state_locked():
            self._tcp_say('TOOL-STATE LOCK is engaged -- declare the tool '
                          'first (feeds run at zero velocity locked).',
                          bad=True)
            return
        gate = self._cal_gate('PID TRACK')
        if gate is None:
            return
        c0, s0 = gate
        kind, _L = self._tcp_kins()
        if kind != 'tcp':
            self._tcp_say('PID TRACK needs tool-tip kins (-tcp).', bad=True)
            self._hand_back_manual(c0, 'PID TRACK')
            return
        # G43 preamble -- without the tool length the kins holds a point
        # one tool-length up the shank and the tip sweeps arcs
        try:
            s0.poll()
            if self._tcp_tooloff() < 1.0 and s0.tool_in_spindle > 0:
                c0.mdi('G43 H%d' % s0.tool_in_spindle)
                c0.wait_complete(4.0)
                LOG.error('PIDT: G43 H%d applied (tool length %.3f)',
                          s0.tool_in_spindle, self._tcp_tooloff())
            if self._tcp_tooloff() < 1.0:
                self._tcp_say('PID TRACK refused: no tool length in force '
                              '(G43).', bad=True)
                self._hand_back_manual(c0, 'PID TRACK')
                return
        except Exception:
            LOG.exception('PIDT: G43 preamble failed')
            self._hand_back_manual(c0, 'PID TRACK')
            return
        # envelope: needs the parked pose (tip banked at A0 C0), then the
        # whole ball must fit -- covers every intermediate pose of every
        # leg (the planner does not police joints under world moves)
        try:
            import subprocess
            def _gp(pin):
                return float(subprocess.run(
                    ['timeout', '5', 'halcmd', 'getp', pin],
                    capture_output=True, text=True).stdout.strip())
            L = _gp('ned_ac_kins.pivot-length')
            ja, jc = _gp('joint.4.pos-fb'), _gp('joint.5.pos-fb')
            jx, jy, jz = (_gp('joint.0.pos-fb'), _gp('joint.1.pos-fb'),
                          _gp('joint.2.pos-fb'))
            xlo = _gp('ini.0.min_limit') + 5.0
            xhi = _gp('ini.0.max_limit') - 5.0
            ylo = _gp('ini.1.min_limit') + 5.0
            yhi = _gp('ini.1.max_limit') - 5.0
            zlo = _gp('ini.2.min_limit') + 5.0
        except Exception:
            LOG.exception('PIDT: envelope readback failed')
            self._tcp_say('PID TRACK refused: could not read joints/'
                          'limits.', bad=True)
            self._hand_back_manual(c0, 'PID TRACK')
            return
        # The ball is an XYZ question, not an A/C one (operator 2026-08-07:
        # "its just a fucking abs encoder position"). Compute where the TIP
        # is from whatever pose the head is in, then check the swing around
        # THAT point. No A/C parking required.
        import math as _m
        _az = _m.radians(jc + 90.0)        # NOT _t: that is the time alias
        _pol = _m.radians(180.0 - ja)
        jx = jx + L * _m.sin(_pol) * _m.cos(_az)
        jy = jy + L * _m.sin(_pol) * _m.sin(_az)
        jz = jz + L + L * _m.cos(_pol)
        prob = []
        if jx - L < xlo or jx + L > xhi:
            prob.append('X ball out of limits')
        if jy - L < ylo or jy + L > yhi:
            prob.append('Y ball out of limits')
        if jz - L < zlo:
            prob.append('Z headroom short %.0f mm -- park the tip at '
                        'least that much higher' % (zlo - (jz - L)))
        if prob:
            self._tcp_say('PID TRACK refused: ' + '; '.join(prob),
                          bad=True)
            LOG.error('PIDT REFUSED: L=%.1f pose=(%.1f,%.1f,%.1f) '
                      'A=%.2f C=%.2f', L, jx, jy, jz, ja, jc)
            self._hand_back_manual(c0, 'PID TRACK')
            return
        self._seq_flag(True)
        self._pidt = {'legs': 0, 'targ': None, 'retry': 0, 't0': 0.0,
                      'tip': (jx, jy, jz), 'L': L,
                      'lim': (xlo, xhi, ylo, yhi, zlo),
                      'pa': 0.0, 'pc': 0.0,
                      'log': ('/home/brains/Documents/ned/logs/'
                              'ac_survey_%s.ndjson'
                              % _t.strftime('%Y%m%d-%H%M%S'))}
        random.seed()
        self._pidt_on = True
        self._pidt_go_next = False
        self._pidt_idle_t0 = None
        self._pidt_manual_pending = False
        if getattr(self, '_pidt_timer', None) is None:
            t = QTimer(self)
            t.timeout.connect(self._pidt_tick)
            t.start(500)
            self._pidt_timer = t
            LOG.error('PIDT: tick timer started (500 ms)')
        self._pidt_out({'t': 'start', 'L': round(L, 4),
                        'jx': round(jx, 4), 'jy': round(jy, 4),
                        'jz': round(jz, 4)})
        self._pidt_set_face()
        self._tcp_say('PID TRACK: %d random A/C legs, A +-%.0f C +-%.0f '
                      'F %s, ball verified. Legs -> %s'
                      % (self.PIDT_LEGS, self.PIDT_A_BALL,
                         self.PIDT_C_BALL, list(self.PIDT_F_RANGE),
                         self._pidt['log']))
        self._pidt_next()

    def _pidt_out(self, rec):
        import json, time
        rec['ts'] = round(time.time(), 3)
        try:
            with open(self._pidt['log'], 'a') as f:
                f.write(json.dumps(rec) + '\n')
        except Exception:
            LOG.exception('PIDT: data line NOT saved')

    def _pidt_ok(self, a, cdeg):
        import math
        v = self._pidt
        jx, jy, jz = v['tip']
        L = v['L']
        xlo, xhi, ylo, yhi, zlo = v['lim']
        t = math.radians(cdeg + 90.0)
        p = math.radians(180.0 - a)
        rx = L * math.sin(p) * math.cos(t)
        ry = L * math.sin(p) * math.sin(t)
        rz = L * math.cos(p)
        return (xlo <= jx - rx <= xhi and ylo <= jy - ry <= yhi
                and jz - L - rz >= zlo)

    def _pidt_next(self):
        import random, time
        v = self._pidt
        if v['legs'] >= self.PIDT_LEGS:
            self._pidt_stop('survey COMPLETE: %d legs -> %s'
                            % (v['legs'], v['log']))
            return
        if v.get('retry', 0) == 0 or v['targ'] is None:
            for _ in range(200):
                a = random.uniform(-self.PIDT_A_BALL, self.PIDT_A_BALL)
                cd = random.uniform(-self.PIDT_C_BALL, self.PIDT_C_BALL)
                F = random.uniform(*self.PIDT_F_RANGE)
                if self._pidt_ok(a, cd) and (abs(a - v['pa']) > 5
                                             or abs(cd - v['pc']) > 5):
                    break
            else:
                self._pidt_stop('no valid draw -- envelope too tight')
                return
            v['targ'] = (a, cd, F)
        a, cd, F = v['targ']
        gate = self._cal_gate('PID TRACK')
        if gate is None:
            self._pidt_stop('gate refused')
            return
        c, _s = gate
        c.mdi('o<tcp_pidt_ac> call [%.3f] [%.3f] [%.0f]' % (a, cd, F))
        v['t0'] = time.time()
        self._pidt_idle_t0 = None
        self._pidt_out({'t': 'issue', 'a': round(a, 2), 'c': round(cd, 2),
                        'F': round(F, 0), 'leg': v['legs']})
        LOG.error('PIDT: leg %d issued A%+.2f C%+.2f F%.0f',
                  v['legs'], a, cd, F)

    def tcp_pidt_point(self, at):
        """Called BY THE G-CODE (tcp_pidt_ac.ngc) after each leg's
        settle dwell."""
        if not getattr(self, '_pidt_on', False):
            return
        v = self._pidt
        v['retry'] = 0
        v['legs'] += 1
        a, cd, F = v['targ']
        v['pa'], v['pc'] = a, cd
        v['targ'] = None
        self._pidt_out({'t': 'leg', 'a': round(a, 2), 'c': round(cd, 2),
                        'F': round(F, 0), 'leg': v['legs']})
        LOG.error('PIDT: leg %d LANDED (A%+.2f C%+.2f)', v['legs'], a, cd)
        if v['legs'] % 5 == 0:
            self._tcp_say('PID TRACK: %d/%d legs, data -> %s'
                          % (v['legs'], self.PIDT_LEGS, v['log']))
        self._pidt_go_next = True

    def _pidt_tick(self):
        import time
        if getattr(self, '_pidt_manual_pending', False):
            if time.time() - getattr(self, '_pidt_manual_t0', 0) > 2.0:
                try:
                    import linuxcnc
                    s2 = linuxcnc.stat()
                    s2.poll()
                    if s2.interp_state == linuxcnc.INTERP_IDLE and s2.inpos:
                        self._pidt_manual_pending = False
                        self._hand_back_manual(linuxcnc.command(),
                                               'PID TRACK')
                except Exception:
                    LOG.exception('PIDT: hand-back poll failed')
            return
        if not getattr(self, '_pidt_on', False):
            return
        if getattr(self, '_pidt_go_next', False):
            try:
                import linuxcnc
                s5 = linuxcnc.stat()
                s5.poll()
                if s5.interp_state == linuxcnc.INTERP_IDLE and s5.inpos:
                    self._pidt_go_next = False
                    self._pidt_next()
            except Exception:
                LOG.exception('PIDT: go-next poll failed')
            return
        # WATCHDOG: an aborted leg never calls back -- 2 s of continuous
        # idle after the 5 s issue grace = the leg died. Retry re-issues
        # the SAME target (retry budget 2), then stop-in-place.
        v = getattr(self, '_pidt', None)
        if not v or v.get('targ') is None:
            return
        if time.time() - v.get('t0', 0) < 5.0:
            return
        try:
            import linuxcnc
            s6 = linuxcnc.stat()
            s6.poll()
            if s6.interp_state == linuxcnc.INTERP_IDLE and s6.inpos:
                if self._pidt_idle_t0 is None:
                    self._pidt_idle_t0 = time.time()
                elif time.time() - self._pidt_idle_t0 > 2.0:
                    self._pidt_idle_t0 = None
                    v['retry'] += 1
                    if v['retry'] <= 2:
                        LOG.error('PIDT: leg lost -- RETRY %d', v['retry'])
                        self._pidt_next()
                    else:
                        self._pidt_stop('leg ended with no callback -- '
                                        'aborted')
            else:
                self._pidt_idle_t0 = None
        except Exception:
            LOG.exception('PIDT: watchdog poll failed')

    def _pidt_stop(self, why):
        self._seq_flag(False)
        self._pidt_on = False
        self._pidt_go_next = False
        self._pidt_idle_t0 = None
        self._pidt_set_face()
        v = getattr(self, '_pidt', None) or {}
        LOG.error('PIDT STOPPED (%s): %d leg(s), data %s', why,
                  v.get('legs', 0), v.get('log', '-'))
        self._tcp_say('PID TRACK %s. %d leg(s). Data: %s'
                      % (why, v.get('legs', 0), v.get('log', '-')))
        # abort any in-flight leg and STAY at the resulting pose
        # (operator 2026-08-06: no zero-returns, no end park)
        try:
            import linuxcnc, time
            ca = linuxcnc.command()
            ca.abort()
            ca.wait_complete(2.0)
        except Exception:
            LOG.exception('PIDT: abort at stop failed')
        try:
            gate = self._cal_gate('PID TRACK stop')
            if gate:
                c, _ = gate
                import time
                # an abort skips the sub's own M50 P1 restore
                c.mdi('M50 P1')
                self._pidt_manual_pending = True
                self._pidt_manual_t0 = time.time()
        except Exception:
            LOG.exception('PIDT: M50 restore failed')

    def _pidt_set_face(self):
        b = getattr(self, '_pidt_btn', None)
        if b is None:
            return
        on = getattr(self, '_pidt_on', False)
        b.setText('STOP PID TRACK' if on else 'PID TRACKING')
        b.setStyleSheet(self.CAL_QSS['clearArmed'] if on
                        else self.CAL_QSS['pose'])

    def _seq_flag(self, on):
        """MODE INTERLOCK: while TRUE (and the heartbeat lives), ned_brain
        will not restore MANUAL between our MDI steps -- the race that
        silently ate one MDI in N. Brain ignores a stale flag 5 s after
        the heartbeat stops, so a GUI crash cannot kill the wheel."""
        try:
            if self.comp is not None:
                self.comp.getPin('seq-active-out').value = bool(on)
                LOG.error('SEQ INTERLOCK %s', 'ARMED' if on else 'RELEASED')
        except Exception:
            LOG.exception('SEQ INTERLOCK flag write failed')

    def _homing_gate_tick(self):
        # heartbeat FIRST (advisor D2): anything below that raises must not
        # starve the beat, or the brain declares the armed flag STALE
        # mid-survey and the race silently returns
        try:
            if self.comp is not None:
                p = self.comp.getPin('seq-hb-out')
                p.value = (int(p.value) + 1) & 0x7FFFFFFF
        except Exception:
            pass
        # THE GATE RUNS FIRST, AND ALONE. It used to run at the BOTTOM of
        # this tick, after five other calls -- so anything raising earlier
        # left 394 controls disabled with no way back. That is exactly what
        # happened: the gate engaged at startup, the tick stopped reaching
        # it, and the entire GUI stayed dead after home was declared, which
        # is why AUTO CONVERGE did nothing when pressed. A gate that can
        # brick the machine must never depend on unrelated code succeeding.
        try:
            import linuxcnc
            _st = linuxcnc.stat()
            _st.poll()
            _declared = all(_st.homed[:NJ])
        except Exception:
            _declared = None        # unknown: neither engage nor strand
        # THE STARTUP WINDOW CLOSES ON TWO FACTS, NOT ONE (operator
        # 2026-08-07: "until machine is stale homed, AND the tool table is
        # loaded, user cannot press ANY button"). Fail closed: an
        # unreadable pin counts as NOT served.
        try:
            _table_ok = bool(self.comp.getPin('table-ok-in').value)
        except Exception:
            _table_ok = False
        if _declared and not _table_ok:
            if not getattr(self, '_gate_tbl_logged', False):
                self._gate_tbl_logged = True
                LOG.error('PRE-HOME GATE: home is declared but the TOOL '
                          'TABLE is not served -- gate stays SHUT')
        _declared = bool(_declared) and _table_ok
        if _declared and not getattr(self, '_prehome_done', False):
            self._prehome_done = True
            LOG.error('PRE-HOME GATE: startup window CLOSED for this '
                      'session (homed + tool table served) -- later '
                      'transient unhomes (REF A/C reads) no longer swallow '
                      'input')
        if getattr(self, '_prehome_done', False):
            _declared = True     # one-shot: the gate exists for the window
                                 # before the FIRST declaration only. It
                                 # re-armed during a mid-session REF read
                                 # and ATE 18 operator clicks (2026-08-06
                                 # 14:0x, 'autoconverge not working').
        if _declared is not None:
            try:
                # ENFORCEMENT is the event filter -- it cannot be defeated
                # by a widget re-enabling itself, and it covers line edits,
                # MDIEntry, sliders and combo boxes the button sweep never
                # touched. The sweep below is now COSMETIC: it greys things
                # so the operator can see the gate. Safety does not depend
                # on it any more.
                _cd = self.countdown_button()
                import time as _t
                _uw = _t.time() < getattr(self, '_unload_window_until', 0)
                if not _declared:
                    # startup: only E-STOP / POWER / EXIT
                    self._arm_input_gate()
                    self._sweep_gate(self.window(), False)
                elif _uw and _cd is None:
                    _names = self.PREHOME_SURVIVORS + tuple(
                        b.objectName() for b in getattr(self, '_load_btns', []))
                    self._arm_input_gate(_names)
                    self._sweep_gate(self.window(), False,
                                     keep=self._gate_survivor_widgets(_names))
                elif _cd is not None:
                    # a countdown is running: everything dead but E-STOP,
                    # POWER, EXIT and the counting button (its own cancel)
                    _names = self.PREHOME_SURVIVORS + (_cd.objectName(),)
                    self._arm_input_gate(_names)
                    self._sweep_gate(self.window(), False,
                                     keep=self._gate_survivor_widgets(_names))
                    if not getattr(self, '_cd_logged', False):
                        self._cd_logged = True
                        LOG.error('COUNTDOWN GATE ARMED on %s -- everything '
                                  'else is dead until it finishes or is '
                                  'cancelled', _cd.objectName())
                elif self._motion_lock_on():
                    # SPINDLE/TABLE INCONSISTENCY: same total block, but the
                    # ATC and TOOL tabs stay fully usable -- that is where
                    # the operator corrects the record. Everything inside
                    # them stays enabled as well as un-swallowed.
                    self._arm_input_gate(self.TOOLLOCK_SURVIVORS)
                    _keep = self._gate_survivor_widgets(
                        self.TOOLLOCK_SURVIVORS)
                    self._sweep_gate(self.window(), False, keep=_keep)
                    if not getattr(self, '_toolgate_logged', False):
                        self._toolgate_logged = True
                        LOG.error('TOOL GATE ARMED: spindle/table '
                                  'inconsistency -- only E-STOP, POWER, '
                                  'EXIT and the ATC/TOOL tabs are live')
                else:
                    if getattr(self, '_cd_logged', False):
                        self._cd_logged = False
                        LOG.error('COUNTDOWN GATE RELEASED')
                    if getattr(self, '_toolgate_logged', False):
                        self._toolgate_logged = False
                        LOG.error('TOOL GATE RELEASED: spindle and table '
                                  'agree -- the GUI is live again')
                    self._release_input_gate()
                    self._sweep_gate(self.window(), True)
            except Exception:
                LOG.exception('PRE-HOME GATE failed -- forcing RELEASE so '
                              'the GUI cannot stay stranded')
                self._release_input_gate(quiet=True)
                self._sweep_release_force()
        self._sync_inc_row()
        # TOOL-STATE LOCK: POLL, don't trust edges (2026-08-05). The lock
        # engaged during boot -- in the second before the brain restored
        # the spindle record -- and never released, because the listener
        # only fires on transitions and that FALSE edge landed before/while
        # the handler was wiring. Read the pins every tick: the lock then
        # tracks the truth and can never latch on a boot transient.
        try:
            if self.comp is not None:
                u = bool(self.comp.getPin('tool-unrecorded-in').value)
                p = bool(self.comp.getPin('tool-phantom-in').value)
                self._tool_unrecorded = u
                self._tool_phantom = p
                # UNCONDITIONAL: recompute the lock from the pins every
                # tick. Change-detection let a boot-transient lock latch
                # (2026-08-05) -- the pins ARE the truth, so just apply
                # them; _tool_lock_update is a no-op when nothing moved.
                self._tool_lock_update()
                self._tool_alarm_repeat()
        except Exception:
            if not getattr(self, '_lockpoll_err', False):
                self._lockpoll_err = True
                LOG.exception('TOOL LOCK poll failed -- lock may latch')
        self._update_spindle_remark()
        self._sync_fork_graphic()
        self._heal_banned_locs()
        try:
            import linuxcnc
            st = linuxcnc.stat()
            st.poll()
            homed = all(st.homed[:NJ])
        except Exception:
            homed = False            # unreadable -> assume NOT homed, refuse
        # DECLARED is the real home state and drives the pre-home sweep.
        # `homed` below additionally folds in the tool-state lock for the
        # narrow HOMING_GATED list. They must NOT be the same variable: the
        # tool lock forcing homed=False would fire the full sweep and kill
        # the declaration controls -- the exact deadlock fixed earlier
        # today, where the only way out of the lock was disabled by it.
        declared = homed
        if getattr(self, '_tool_locked', False):
            homed = False       # tool-state lock deads the same buttons
        # ...AND NOTHING IN THIS LIST WHILE THE MACHINE IS BUSY (operator
        # 2026-08-10: "while homing zero buttons continue to work. THEY
        # SHOULDN'T" / "touch off tool button also worked"). `homed` alone
        # is true all the way THROUGH a homing cycle, so it never gated
        # them. joint['homing'] is FALSE during ac_to_zero's joint jog, so
        # velocity has to be in the test too.
        try:
            if (abs(st.current_vel) > 0.01
                    or any(st.joint[j]['homing'] for j in range(NJ))
                    or st.interp_state != linuxcnc.INTERP_IDLE):
                homed = False
        except Exception:
            homed = False        # unreadable -> refuse
        win = self.window()
        if homed == getattr(self, '_homed_now', None):
            return
        self._homed_now = homed
        hit, missing = [], []
        # BEFORE THE DECLARATION LANDS, EVERYTHING IS DEAD except E-stop and
        # power (operator 2026-08-05: "the only buttons that can work are
        # estop, and power. nothing else"). This is NOT rule 17's forbidden
        # gate: rule 17 protects the DECLARED stale home from gating the
        # operator. This covers the window BEFORE it applies, when the
        # machine has no valid position at all -- "stale home doesn't apply
        # instantly. before it applies, GATE EVERYTHING". An enumerated list
        # of 7 names used to stand here, which is why ZERO was clickable on
        # a fresh launch.
        for name in self.HOMING_GATED:
            w = win.findChild(QWidget, name) if win else None
            if w is None:
                missing.append(name)
                continue
            try:
                w.setEnabled(homed)
                hit.append(name)
            except Exception:
                missing.append(name)
        LOG.info('HOMING GATE: machine %s -> %d motion button(s) %s',
                 'HOMED' if homed else 'NOT homed', len(hit),
                 'ENABLED' if homed else 'DISABLED')
        if missing:
            LOG.error('HOMING GATE: %d button(s) NOT found, still live on an '
                      'unhomed machine: %s', len(missing), ', '.join(missing))
        self._sync_load_enabled()

    RACK_TABLE_FORKS = 14

    # ---- per-tool SAFETY X/Y (operator 2026-08-04) -----------------------
    # Stored as DB custom fields (columns appear in the tool table editor
    # automatically); mirrored into params #[4200 + 2*T] (X) / +1 (Y) so the
    # rack subs can read them for ANY tool, not just the loaded one. The
    # mirror flushes via MDI only when ON + homed + idle -- the same gate
    # every param write on this machine respects.
    TOOL_SAFETY_BASE = 4200

    def _init_tool_safety(self):
        try:
            from qtpyvcp.plugins import getPlugin
            tt = getPlugin('tooltable')
            # FLUTES is back (operator 2026-08-05 00:3x): chipload =
            # feed / (rpm * flutes) needs the count machine-side after all
            for name, label in (('safety_x', 'SAFETY X'),
                                ('safety_y', 'SAFETY Y'),
                                ('flutes', 'FLUTES')):
                try:
                    tt.addCustomField(name, label, 'float', 'mm')
                    LOG.info('TOOL SAFETY: column %s created', label)
                except ValueError:
                    pass            # already exists
                except Exception:
                    LOG.exception('TOOL SAFETY: could not create %s', label)
            self._tool_safety_sent = {}
            self._tool_safety_timer = QTimer(self)
            self._tool_safety_timer.timeout.connect(self._sync_tool_safety)
            self._tool_safety_timer.start(3000)
            LOG.info('TOOL SAFETY: sync armed (params %d+)',
                     self.TOOL_SAFETY_BASE)
        except Exception:
            LOG.exception('TOOL SAFETY: init failed -- columns/params absent')

    def _sync_tool_safety(self):
        """Mirror safety_x/safety_y into the 4200 block, changed values only."""
        try:
            import sqlite3, linuxcnc
            st = linuxcnc.stat()
            st.poll()
            if (st.task_state != linuxcnc.STATE_ON
                    or st.interp_state != linuxcnc.INTERP_IDLE
                    or not all(st.homed[:NJ])):
                return
            con = sqlite3.connect(
                'file:/home/brains/Documents/ned/configs/ned5_pb/'
                'tool_table.db?mode=ro', uri=True)
            rows = con.execute(
                "SELECT t.tool_no, d.name, v.value FROM custom_field_value v"
                " JOIN custom_field_def d ON d.id = v.field_id"
                " JOIN tool t ON t.id = v.tool_id"
                " WHERE d.name IN ('safety_x','safety_y')").fetchall()
            # HOME FORK mirror (operator 2026-08-04: "a specific tool always
            # going back to a specific P and I assign which"): DB pocket =
            # the assigned home, g-code reads #[4400+T]
            homes = con.execute(
                'SELECT tool_no, pocket FROM tool').fetchall()
            con.close()
            for tno, pk in homes:
                if not (1 <= int(tno) <= 30):
                    continue
                try:
                    pk = float(int(float(pk)))
                except (TypeError, ValueError):
                    continue
                # P0 MEANS "IN THE SPINDLE", NOT "NO HOME" (2026-08-11).
                # Mirroring it wiped #[4400+T] the moment a tool was picked
                # up, so the put-away then aborted with "T13 has no
                # assigned home fork" and the spindle stayed down. The home
                # is the last fork the tool actually sat in; keep it.
                if pk <= 0:
                    continue
                rows.append((tno, 'home_p', pk))
            pend = []
            for tno, name, val in rows:
                # safety block is sized 1..14; home_p mirrors up to T30
                # (T15 the sawblade MUST keep its assigned home)
                cap = 30 if name == 'home_p' else 14
                if not (1 <= int(tno) <= cap):
                    continue
                try:
                    f = float(val)
                except (TypeError, ValueError):
                    continue
                if name == 'home_p':
                    p = 4400 + int(tno)
                else:
                    p = self.TOOL_SAFETY_BASE + 2 * int(tno)                         + (0 if name == 'safety_x' else 1)
                if self._tool_safety_sent.get(p) != f:
                    pend.append((p, f))
            if not pend:
                return
            c = linuxcnc.command()
            c.mode(linuxcnc.MODE_MDI)
            deadline = time.time() + 2.0
            while True:
                st.poll()
                if st.task_mode == linuxcnc.MODE_MDI:
                    break
                if time.time() >= deadline:
                    return              # busy; retry next tick
                c.mode(linuxcnc.MODE_MDI)
                time.sleep(0.05)
            for p, f in pend:
                c.mdi('#%d=%.4f' % (p, f))
                self._tool_safety_sent[p] = f
            LOG.info('TOOL SAFETY: %d value(s) mirrored to params', len(pend))
            # HAND MDI BACK, ONCE, HERE (2026-08-05). This mirror runs at
            # every launch (the sent-cache starts empty), and leaving the
            # machine in MDI silently refuses every jog -- no wheel, no
            # error message. One restore at this exact point is safe: the
            # wait_complete above means the machine is idle. Do NOT retry
            # this on a timer -- a mode change during a jog is refused and
            # each refusal is an error toast in the operator's face.
            try:
                c.wait_complete(2.0)
                c.mode(linuxcnc.MODE_MANUAL)
                LOG.info('TOOL SAFETY: MDI handed back -- jogging is live')
            except Exception:
                LOG.exception('TOOL SAFETY: could not restore MANUAL')
            # BACK TO MANUAL (2026-08-05): this timer left the machine
            # parked in MDI, where jogging is silently refused -- no wheel,
            # no error. Borrow MDI, hand it back when the machine is quiet.
            try:
                c.wait_complete(2.0)
            except Exception:
                pass

        except Exception:
            LOG.exception('TOOL SAFETY: sync failed')

    ROTARY_PROBE_FIELDS = (
        ('bar_dia', 'BAR DIA', '31.75', 'mm - the 1.25in calibration bar'),
        ('depth',   'PROBE DEPTH', '25.4', 'mm below the crown for the flanks'),
        ('yspan',   'STATION GAP', '300.0', 'mm of Y between the two stations'),
    )

    def _build_rotary_probe_tab(self):
        """ROTARY page on the PROBING tab (operator 2026-08-11: "this should be
        written in the rotary axis tab under probing").

        A PAGE, not a .ui edit. probe_basic.ui is core -- cutting a tab into it
        is wiped by the next PB update and has to be re-applied from
        update_survival, whereas addTab() at runtime survives untouched. Same
        pattern as RACK TABLE on the ATC tab.

        The button is a stock SubCallButton, so the call itself is qtpyvcp's
        own tested path: it reads the arg lines out of rotary_zero.ngc, takes
        each value from the field of the same name if one exists, and issues
        the o-call. The three fields below are named to match those args --
        that name IS the binding, there is no wiring to get wrong.
        """
        from PySide6.QtWidgets import (QTabWidget, QVBoxLayout, QHBoxLayout,
                                       QLabel, QLineEdit)
        try:
            win = self.window()
            host = win.findChild(QTabWidget, 'tabWidget_2') if win else None
            if host is None:
                LOG.error('ROTARY PROBE: tabWidget_2 not found -- page not '
                          'built. Nothing else is affected.')
                return
            from qtpyvcp.widgets.button_widgets.subcall_button import (
                SubCallButton)
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(12, 12, 12, 12)
            lay.setSpacing(10)
            head = QLabel('ROTARY AXIS ZERO  --  round bar, tool at hand')
            head.setStyleSheet('color: rgb(238,238,236); font: 14pt '
                               '"Probe Basic Bebas Mono";')
            lay.addWidget(head)
            why = QLabel(
                'Three touches here, then +Y to a second station and three '
                'more.\nX zero is the midpoint of the flanks, Z zero is the '
                'crown less one bar radius.\nThe two stations give the axis '
                'yaw and droop -- printed to the log.\n'
                'The bar must be on the toolsetter probe lead.')
            why.setStyleSheet('color: rgb(200,200,200); font: 10pt;')
            lay.addWidget(why)
            self._rp_fields = {}
            for name, label, default, hint in self.ROTARY_PROBE_FIELDS:
                row = QHBoxLayout()
                lb = QLabel(label)
                lb.setFixedWidth(150)
                lb.setStyleSheet('color: rgb(238,238,236); font: 11pt '
                                 '"Probe Basic Bebas Mono";')
                ed = QLineEdit()
                # THE NAME IS THE BINDING: SubCallButton searches every widget
                # in the app for one matching the arg name in the .ngc.
                ed.setObjectName(name)
                ed.setText(default)
                ed.setFixedWidth(120)
                ed.setStyleSheet('background: rgb(128,128,128); color: white; '
                                 'font: 12pt "Probe Basic Bebas Mono";')
                hn = QLabel(hint)
                hn.setStyleSheet('color: rgb(170,170,170); font: 10pt;')
                row.addWidget(lb, 0)
                row.addWidget(ed, 0)
                row.addWidget(hn, 1)
                lay.addLayout(row)
                self._rp_fields[name] = ed
            btn = SubCallButton(page, filename='rotary_zero.ngc')
            btn.setObjectName('ned_rotary_zero_button')
            btn.setText('ROTARY ZERO')
            btn.setMinimumHeight(56)
            lay.addWidget(btn)
            lay.addStretch(1)
            host.addTab(page, 'ROTARY')
            self._rotary_probe_page = page
            LOG.info('ROTARY PROBE: page added to tabWidget_2 with %d field(s)'
                     ' bound by name to rotary_zero.ngc',
                     len(self.ROTARY_PROBE_FIELDS))
        except Exception:
            LOG.exception('ROTARY PROBE: page not built')

    def _build_rack_table(self):
        """RACK TABLE page on the ATC tab: per-fork PosX / PosY (PosZ later).

        Lives as a page of rack_tab_widget (beside RACK ATC / RACK SETUP) and
        shows the 4100 block the RACK CALIBRATION cycle writes -- the same
        params a per-fork changer would read. Read-only: the LOCATOR is the
        writer; a hand-editable copy is how the map starts lying. Styled by
        the app-wide QSS the tool table already wears (class-based, so a
        plain QTableWidget picks it up). Var file only saves on program end/
        abort/exit, so values can lag a running cycle -- the PRINT lines are
        the live confirmation, this table is the record.
        """
        from PySide6.QtWidgets import (QTabWidget, QTableWidget,
                                       QTableWidgetItem, QVBoxLayout,
                                       QAbstractItemView)
        from PySide6.QtCore import Qt
        try:
            win = self.window()
            host = win.findChild(QTabWidget, 'rack_tab_widget') if win else None
            if host is None:
                LOG.error('RACK TABLE: rack_tab_widget not found -- not '
                          'built. Nothing else is affected.')
                return
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(8, 8, 8, 8)
            t = QTableWidget(self.RACK_TABLE_FORKS, 4)
            t.setObjectName('ned_rack_table')
            # match the TOOL tab table: grey cells, white figures, dark grid
            # (the app QSS styles the headers but leaves a plain
            # QTableWidget's body light)
            t.setStyleSheet(
                'QTableWidget { background: rgb(60,63,65);'
                ' gridline-color: rgb(40,42,44); }'
                ' QTableWidget::item { background: rgb(128,128,128);'
                ' color: white; font: 12pt "Probe Basic Bebas Mono"; }')
            t.setHorizontalHeaderLabels(['P', 'POS X', 'POS Y', 'POS Z'])
            t.verticalHeader().setVisible(False)
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            t.setSelectionMode(QAbstractItemView.NoSelection)
            for r in range(self.RACK_TABLE_FORKS):
                it = QTableWidgetItem(str(r + 1))
                it.setTextAlignment(Qt.AlignCenter)
                t.setItem(r, 0, it)
                for ccol in (1, 2, 3):
                    v = QTableWidgetItem('\u2014')
                    v.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    t.setItem(r, ccol, v)
            t.setColumnWidth(0, 60)
            for ccol in (1, 2, 3):
                t.setColumnWidth(ccol, 150)
            lay.addWidget(t)
            host.addTab(page, 'RACK TABLE')
            self._rack_table = t
            self._rack_table_mtime = None
            self._rack_table_timer = QTimer(self)
            self._rack_table_timer.timeout.connect(self._rack_table_poll)
            self._rack_table_timer.start(2000)
            self._rack_table_poll()
            LOG.info('RACK TABLE: page added to rack_tab_widget '
                     '(%d forks, PosZ placeholder)', self.RACK_TABLE_FORKS)
        except Exception:
            LOG.exception('RACK TABLE: not built')

    def _rack_table_poll(self):
        """mtime-gated re-read of the 4100 block into the table."""
        t = getattr(self, '_rack_table', None)
        if t is None:
            return
        try:
            mt = os.path.getmtime(self.VAR_FILE)
            if mt == self._rack_table_mtime:
                return
            self._rack_table_mtime = mt
            vals = {}
            with open(self.VAR_FILE) as fh:
                for line in fh:
                    b = line.split()
                    if len(b) >= 2:
                        try:
                            vals[int(b[0])] = float(b[1])
                        except ValueError:
                            pass
            for r in range(self.RACK_TABLE_FORKS):
                base = 4100 + 4 * (r + 1)
                ok = vals.get(base + 3, 0.0) > 0
                x = ('%.3f' % vals.get(base, 0.0)) if ok else '\u2014'
                y = ('%.3f' % vals.get(base + 1, 0.0)) if ok else '\u2014'
                t.item(r, 1).setText(x)
                t.item(r, 2).setText(y)
                # PosZ: the shoulder-touch ends + linear interpolation fill
                # +2 once a full cycle completes; 0.0 means never written
                zv = vals.get(base + 2, 0.0)
                t.item(r, 3).setText(('%.3f' % zv) if (ok and zv != 0.0)
                                     else '\u2014')
        except Exception:
            LOG.exception('RACK TABLE: poll failed')

    def _build_declaration(self, *a, **k):
        # DECLARE row DELETED (operator 2026-08-04: "get rid of the
        # declaration button and number. we are replacing it with the
        # forks") -- fork circles own declaration once the audited logic
        # ships; LOAD SPINDLE remains the spindle-record path meanwhile.
        LOG.info('DECLARATION: the spindle badge owns it now')
        self._build_spindle_editor()

    def _relabel_buttons(self):
        """Retext core buttons at RUNTIME, never by editing probe_basic.ui.

        A .ui edit is wiped by the next PB update and has to be re-applied
        from update_survival; this does not, and it is reversible by deleting
        one dict entry. Only the visible text changes -- no binding, no
        geometry, no behaviour.
        """
        win = self.window()
        done, missing = [], []
        for name, text in self.RELABEL.items():
            b = win.findChild(QWidget, name) if win else None
            if b is None or not hasattr(b, 'setText'):
                missing.append(name)
                continue
            b.setText(text)
            done.append('%s -> %r' % (name, text))
        if done:
            LOG.info('RELABEL: %d button(s): %s', len(done), '; '.join(done))
        if missing:
            LOG.error('RELABEL: %d button(s) NOT found, stock label still '
                      'showing: %s', len(missing), ', '.join(missing))

    def _wire_load(self):
        win = self.window()
        self._load_btns = []
        self._load_labels = {}
        wired, missing = [], []
        for name in ('load_spindle_button', 'load_spindle_button_2'):
            b = win.findChild(QWidget, name) if win else None
            if b is None or not hasattr(b, 'callSub'):
                missing.append(name)
                continue
            try:
                b.clicked.disconnect()      # severs SubCallButton.callSub
            except Exception:
                pass
            b.clicked.connect(lambda _=False, btn=b: self._load_click(btn))
            self._load_btns.append(b)
            self._load_labels[b] = b.text()
            wired.append(name)
        if wired:
            LOG.info('LOAD SPINDLE: 5 s countdown wired on %d button(s): %s',
                     len(wired), ', '.join(wired))
        if missing:
            LOG.info('LOAD SPINDLE: %d name(s) confirmed deleted: %s',
                     len(missing), ', '.join(missing))

    DRAWBAR_WINDOW_S = 10

    def _drawbar_window_start(self):
        """After an unload, give LOAD a 10 s window -- then close the drawbar.

        unload_spindle.ngc ends with the release solenoid ENERGISED and says
        so: "Open until LOAD SPINDLE / M65 P0". An energised release solenoid
        bleeds the air supply, which is how the machine lost pressure on
        2026-08-02 after repeated unloads. If nobody loads a tool, nothing
        should be holding it open.

        This does NOT load anything -- it only stops holding the drawbar down.
        """
        self._drawbar_left = self.DRAWBAR_WINDOW_S
        t = getattr(self, '_drawbar_timer', None)
        if t is None:
            t = self._drawbar_timer = QTimer(self)
            t.timeout.connect(self._drawbar_window_tick)
        t.start(1000)
        LOG.info('DRAWBAR: open, %d s for LOAD SPINDLE before it is released',
                 self.DRAWBAR_WINDOW_S)

    def _drawbar_window_cancel(self, why):
        t = getattr(self, '_drawbar_timer', None)
        if t is not None and t.isActive():
            t.stop()
            LOG.info('DRAWBAR: window cancelled (%s)', why)
        self._drawbar_left = 0
        for b in getattr(self, '_load_btns', []):
            try:
                if b.text().startswith('LOAD?'):
                    b.setText(self._load_labels.get(b, 'LOAD SPINDLE'))
            except Exception:
                pass

    def _drawbar_window_tick(self):
        self._drawbar_left -= 1
        for b in getattr(self, '_load_btns', []):
            try:
                if self._load_pend.get(b) is None:
                    b.setText('LOAD?  %d' % max(self._drawbar_left, 0))
            except Exception:
                pass
        if self._drawbar_left > 0:
            return
        self._drawbar_timer.stop()
        self._drawbar_window_cancel('expired')
        try:
            import linuxcnc
            c = linuxcnc.command()
            st = linuxcnc.stat()
            st.poll()
            if st.interp_state != linuxcnc.INTERP_IDLE or not st.inpos:
                LOG.error('DRAWBAR: window expired but the machine is busy -- '
                          'NOT touching the solenoid')
                return
            if not self._take_mdi(c, 'DRAWBAR'):
                return
            # o<clamptool> = M65 P0 PLUS M66 P0 L3 Q2, which waits up to 2 s
            # for the tool-LOCKED sensor and aborts if it never confirms. A
            # bare M65 P0 de-energises the solenoid and assumes it worked.
            # No tool bookkeeping here: unload_spindle.ngc already did
            # M61 Q0 / G49 / #3991 = 0, so the spindle is on record as empty
            # from the moment it was unloaded (operator 2026-08-03: "if user
            # doesn't reload after unloading, quite simply, spindle is empty").
            c.mdi('o<clamptool> call')
            c.wait_complete(5.0)
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            st.poll()
            if all(st.homed[:NJ]):
                c.teleop_enable(1)
            msg = ('DRAWBAR RELEASED: no LOAD within %d s. Nothing was '
                   'loaded -- the solenoid is de-energised so it stops '
                   'bleeding air.' % self.DRAWBAR_WINDOW_S)
            LOG.info(msg)
            c.error_msg(msg)
        except Exception as e:
            LOG.error('DRAWBAR: could not release: %s', e)

    # Faces a countdown writes, which must NEVER be adopted as a base label.
    _TRANSIENT_FACES = ('CANCEL', 'LOAD?')

    def _load_tool_ok(self, b):
        """Is the number in this button's field actually a loadable tool?

        load_spindle_safety_2.ngc runs o<clamptool> FIRST and only reaches
        M61/G43 afterwards, with "#3991 = <n>" on the line AFTER the G43. So
        a tool that is not in the table aborts at G43 with the drawbar
        already clamped and NOTHING recorded -- which is exactly what
        happened on 2026-08-03 ("Requested tool 1 not found in the tool
        table"). Checking here means a doomed call is never issued at all.

        Reads stat().tool_table, not tool.tbl, because the interpreter's
        LOADED table is what G43 consults -- rows added in the GUI but never
        saved are present, and a saved-but-not-reloaded file is not.
        """
        try:
            import linuxcnc
            name = b.objectName().replace('button', 'tool_number')
            w = self.window().findChild(QWidget, name)
            if w is None or not hasattr(w, 'text'):
                LOG.error('LOAD SPINDLE: field %s not found -- cannot verify '
                          'the tool; refusing rather than clamping blind', name)
                return False
            raw = (w.text() or '').strip()
            n = int(float(raw))
            if n <= 0:
                LOG.error('LOAD SPINDLE refused: tool number %r is not valid. '
                          'To record an EMPTY spindle just let the drawbar '
                          'window run out.', raw)
                return False
            st = linuxcnc.stat(); st.poll()
            if any(getattr(t, 'id', -1) == n for t in st.tool_table):
                return True
            msg = ('LOAD SPINDLE refused: T%d is not in the loaded tool table. '
                   'Add it and press SAVE TABLE, then RELOAD TABLE. Nothing '
                   'was clamped.' % n)
            LOG.error(msg)
            try:
                linuxcnc.command().error_msg(msg)
            except Exception:
                pass
            return False
        except Exception as e:
            LOG.error('LOAD SPINDLE: could not verify the tool (%s) -- '
                      'refusing rather than clamping blind', e)
            return False

    def _btn_base_label(self, b, default):
        """The button's REAL name, remembered once and never re-read live.

        2026-08-03: both countdowns recorded b.text() as the label to restore.
        A click landing while the face said "CANCEL  1" adopted that string,
        so every later restore wrote "CANCEL  1" back -- and because a click
        on a pending button is the CANCEL path, LOAD SPINDLE became
        unreachable until relaunch. Self-perpetuating: the corrupt label
        survived every cycle. Refusing transient faces here means the label
        cannot be poisoned no matter when a click lands.
        """
        lbl = self._btn_labels.get(b)
        if lbl is None:
            t = (b.text() or '').strip()
            lbl = default if t.startswith(self._TRANSIENT_FACES) or not t else t
            self._btn_labels[b] = lbl
        return lbl

    def _load_click(self, b):
        # GATE FIRST. Loading is only meaningful while the drawbar is OPEN.
        # Until 2026-08-03 the button accepted the click and ran the whole 5 s
        # countdown with the drawbar shut, then fired a load that could not
        # mean anything -- operator: "right now it can be clicked, and the
        # countdown starts". Refuse before any timer exists, and only when no
        # countdown is already pending, so a CANCEL press always gets through.
        if self._load_pend.get(b) is None and not self._drawbar_released:
            msg = ('LOAD SPINDLE refused: the drawbar is closed. Press UNLOAD '
                   'SPINDLE first -- there is nothing to load into.')
            LOG.error(msg)
            try:
                import linuxcnc
                linuxcnc.command().error_msg(msg)
            except Exception:
                pass
            return
        self._drawbar_window_cancel('LOAD pressed')
        pend = self._load_pend.get(b)
        if pend is not None:                     # second click = cancel
            pend['timer'].stop()
            b.setText(self._btn_base_label(b, 'LOAD SPINDLE'))
            self._load_pend.pop(b, None)
            LOG.info('LOAD SPINDLE cancelled')
            return
        base = self._btn_base_label(b, 'LOAD SPINDLE')
        pend = {'text': base, 'left': 5}
        timer = QTimer(self)
        pend['timer'] = timer
        self._load_pend[b] = pend

        def tick():
            if self._load_pend.get(b) is not pend:
                timer.stop()
                return
            pend['left'] -= 1
            if pend['left'] > 0:
                b.setText('CANCEL  {}'.format(pend['left']))
                return
            timer.stop()
            b.setText(pend['text'])
            self._load_pend.pop(b, None)
            try:
                # DECOUPLED (operator 2026-08-04): load is a PURE clamp --
                # no tool number, no records; the table declares locations.
                # Latch the ANON excuse: an unknown tool clamped on purpose
                # is not an inconsistency (cleared on release/declaration).
                b.callSub()
                try:
                    self.comp.getPin('anon-load-out').value = True
                    LOG.info('ANON LOAD: unknown tool clamped by intent -- '
                             'UNRECORDED excused until release/declaration')
                except Exception:
                    LOG.exception('anon-load latch failed')
                # NOT proof of success -- callSub is fire-and-forget, so the
                # sub can still abort ("Requested tool 1 not found in the
                # tool table") long after this returns. The old wording said
                # "executed" on a run that aborted, 2026-08-03.
                LOG.info('LOAD SPINDLE: sub call ISSUED (countdown elapsed) '
                         '-- not a success; watch for an abort')
            except Exception as e:
                LOG.error('LOAD SPINDLE failed to issue: %s', e)

        timer.timeout.connect(tick)
        b.setText('CANCEL  5')
        timer.start(1000)

    def _unload_click(self, b):
        if self._unload_pend.get(b) is not None:   # second click = cancel
            self._unload_pend[b]['timer'].stop()
            b.setText(self._btn_base_label(b, 'UNLOAD SPINDLE'))
            self._unload_pend.pop(b, None)
            LOG.info('UNLOAD SPINDLE cancelled')
            return
        base = self._btn_base_label(b, 'UNLOAD SPINDLE')
        pend = {'text': base, 'left': 5}
        timer = QTimer(self)
        pend['timer'] = timer
        self._unload_pend[b] = pend

        def tick():
            if self._unload_pend.get(b) is not pend:
                timer.stop()
                return
            pend['left'] -= 1
            if pend['left'] > 0:
                b.setText('CANCEL  {}'.format(pend['left']))
                return
            timer.stop()
            b.setText(pend['text'])
            self._unload_pend.pop(b, None)
            self._unload_run()
            # DRAWBAR IS NOW OPEN. For 10 s the operator may load a tool and
            # NOTHING ELSE (operator 2026-08-10: "during the 10 second, LOAD
            # spindle becomes useable. everything else stays unused").
            import time as _t
            self._unload_window_until = _t.time() + 10.0
            LOG.error('UNLOAD WINDOW: drawbar released -- LOAD SPINDLE only, '
                      '10 s')

        timer.timeout.connect(tick)
        b.setText('CANCEL  5')
        timer.start(1000)

    def _unload_run(self):
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON or \
               s.interp_state != linuxcnc.INTERP_IDLE:
                c.error_msg('UNLOAD SPINDLE ignored: machine off or program running')
                return
            if not all(s.homed[:NJ]):
                c.error_msg('UNLOAD SPINDLE needs a HOMED machine (MDI is '
                            'homed-gated on gantry kinematics). Home All (Homing menu) or resume first.')
                return
            if not self._take_mdi(c, 'UNLOAD SPINDLE'):
                return
            c.mdi('o<unload_spindle> call')
            # the sub's M66 sensor waits outlive the 5 s default timeout;
            # a mode switch on a timed-out wait would abort it mid-sequence
            c.wait_complete(30.0)
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            s.poll()
            if all(s.homed[:NJ]):
                c.teleop_enable(1)
            LOG.info('UNLOAD SPINDLE executed (drawbar released if sensors agreed)')
            self._drawbar_window_start()
        except Exception as e:
            LOG.error('UNLOAD SPINDLE failed: %s', e)

    # ---- toolprobe -------------------------------------------------------
    def _click(self):
        if self.comp is None or not self._air:
            return
        try:
            pin = self.comp.getPin('toolprobe-cmd')
            pin.value = not pin.value
        except Exception as e:
            LOG.error('toolprobe click failed: %s', e)

    # False until the pin says otherwise: an unwired or unread sensor must
    # refuse the load, never permit it.
    _drawbar_released = False

    # ONE LINE, the operator's words (2026-08-07): "just say CHECK SPINDLE
    # RACK TABLE CONSISTENCY". The old text spelled out which way round the
    # mismatch was and was read as its own opposite -- "TOOL IN SPINDLE, NOT
    # IN LOGIC" was reported back as "an error saying tool not in spindle".
    # Which side is wrong belongs in the log, not on the operator's screen.
    TOOL_ALARM_MSG = 'CHECK TOOL CONFIGURATION'

    def _tool_fault_detail(self):
        """The concrete fault and the exact way out, from live state."""
        import linuxcnc
        try:
            st = linuxcnc.stat(); st.poll()
            have = int(st.tool_in_spindle)
        except Exception:
            have = -1
        rec = 0
        try:
            with open('/home/brains/Documents/ned/configs/ned5_pb/'
                      'ned5_pb.var') as f:
                for ln in f:
                    p = ln.split()
                    if len(p) == 2 and p[0] == '3991':
                        rec = int(float(p[1]))
                        break
        except Exception:
            pass
        if getattr(self, '_tool_unrecorded', False):
            return ('T%d is clamped but LinuxCNC has no record of it '
                    '(it says T%d). Go to the TOOL tab and press LOAD '
                    'SPINDLE for T%d.' % (rec, have, rec)) if rec else (
                    'a tool is clamped but LinuxCNC has no record of it. '
                    'Go to the TOOL tab and press LOAD SPINDLE.')
        if getattr(self, '_tool_phantom', False):
            return ('LinuxCNC thinks T%d is loaded but the spindle is '
                    'empty. Go to the TOOL tab and press UNLOAD SPINDLE.'
                    % have)
        return 'the tool table has not been served yet.'

    def _tool_alarm_repeat(self):
        """Say it again while the lock holds. A toast that self-dismisses
        after 1 s is not a message -- the operator arrived to a machine
        locked on UNRECORDED and never saw a word of it (2026-08-11)."""
        import time as _t
        if not self._motion_lock_on():
            self._tool_nag_at = 0.0
            return
        if _t.time() < getattr(self, '_tool_nag_at', 0.0):
            return
        self._tool_nag_at = _t.time() + 10.0
        msg = '%s: %s' % (self.TOOL_ALARM_MSG, self._tool_fault_detail())
        LOG.error(msg)
        # THROTTLE THE TOAST, NOT THE CHECK. The lock, the gate and the
        # detection are untouched -- this only decides how many times the
        # SAME sentence is put on screen. Three is enough to be seen by
        # someone walking up to the machine (the reason the repeat exists at
        # all: a toast that self-dismisses after 1 s is not a message), and
        # after that it is noise sitting on top of whatever is really wrong
        # (operator 2026-08-11: "its annoying as shit"). The counter is keyed
        # to the message TEXT, so if the fault changes -- different tool,
        # different cause -- it is a new message and gets its own three.
        # The log line above is unconditional, so nothing is ever lost.
        if msg != getattr(self, '_tool_nag_msg', None):
            self._tool_nag_msg = msg
            self._tool_nag_n = 0
        self._tool_nag_n = getattr(self, '_tool_nag_n', 0) + 1
        if self._tool_nag_n > 3:
            return
        try:
            import linuxcnc
            linuxcnc.command().error_msg(msg)
        except Exception as e:
            LOG.error('could not surface the tool alarm: %s', e)

    def _tool_alarm(self, detail):
        """One short line to the operator; the direction of the mismatch to
        the log.

        The popup self-dismisses after 1 s (native_notification.py) and
        nothing persists it -- the STATUS-tab red-title patch was removed
        2026-08-07 at the operator's direction. lcnc.log is the durable
        record, which is why the detail must land there.
        """
        LOG.error('%s -- %s', self.TOOL_ALARM_MSG, detail)
        try:
            import linuxcnc
            linuxcnc.command().error_msg(self.TOOL_ALARM_MSG)
        except Exception as e:
            LOG.error('could not surface the tool alarm to the operator: %s',
                      e)

    def _on_tool_unrecorded(self, val):
        # Iron holds a tool the logic does not know about. Informational --
        # the geometry is simply unknown, so nothing downstream is wrong yet.
        if bool(val) == getattr(self, '_tool_unrecorded', False):
            return
        self._tool_unrecorded = bool(val)
        if self._tool_unrecorded:
            self._tool_alarm('UNRECORDED: something is clamped but the '
                             'machine has no record of it (LOAD SPINDLE '
                             'sets the tool number)')
        else:
            LOG.info('tool record agrees with the spindle again (was '
                     'unrecorded)')
        self._tool_lock_update()

    def _on_tool_phantom(self, val):
        # Logic claims a tool the iron does not hold. This one is ACTIONABLE:
        # offsets are being applied for a tool that is not there, and a change
        # would try to park a tool that does not exist.
        if bool(val) == getattr(self, '_tool_phantom', False):
            return
        self._tool_phantom = bool(val)
        if self._tool_phantom:
            self._tool_alarm('PHANTOM: the machine believes a tool is '
                             'loaded but the spindle is empty, so its length '
                             'offset is being applied to nothing (UNLOAD '
                             'SPINDLE clears it)')
        else:
            LOG.info('tool record agrees with the spindle again (was phantom)')
        self._tool_lock_update()

    def _tool_lock_update(self):
        # TOOL-STATE LOCK (operator 2026-08-04): while the spindle record
        # and the drawbar sensor disagree, HAL already inhibits jog+feed
        # (tool.mm.lock -> motion.*-inhibit). Here: flash the TOOL tab and
        # dead the motion buttons + MDI + CYCLE START so the GUI cannot
        # even try. DECLARE / LOAD / UNLOAD stay live -- they are the way
        # out.
        # Follow the HAL lock, not just our own two flags -- tool.mm.lock2
        # also holds for "tool table not served", which the Python side
        # never sees.
        try:
            hal_locked = bool(self.comp.getPin('motion-lock-in').value)
        except Exception:
            hal_locked = bool(getattr(self, '_motion_locked', False))
        locked = (hal_locked
                  or getattr(self, '_tool_unrecorded', False)
                  or getattr(self, '_tool_phantom', False))
        if locked == getattr(self, '_tool_locked', False):
            return
        self._tool_locked = locked
        win = self.window()
        tw = win.findChild(QWidget, 'tabWidget') if win else None
        try:
            from PySide6.QtCore import QTimer
            from PySide6.QtGui import QColor
            if locked:
                if getattr(self, '_tool_flash_timer', None) is None:
                    t = QTimer(self)
                    t.timeout.connect(self._tool_lock_flash)
                    self._tool_flash_timer = t
                self._tool_flash_on = False
                self._tool_flash_timer.start(500)
                LOG.error('TOOL-STATE LOCK ENGAGED: no movements until the '
                          'spindle record matches the drawbar sensor')
            else:
                if getattr(self, '_tool_flash_timer', None) is not None:
                    self._tool_flash_timer.stop()
                if tw is not None:
                    idx = self._tool_tab_index(tw)
                    if idx >= 0:
                        tw.tabBar().setTabTextColor(idx, QColor())
                LOG.error('TOOL-STATE LOCK RELEASED -- jogging is live')
        except Exception:
            LOG.exception('tool lock UI failed (HAL inhibit still holds)')
        for name in ('cycle_start_button', 'mdi_entry_box'):
            w2 = win.findChild(QWidget, name) if win else None
            if w2 is not None:
                w2.setEnabled(not locked)
        self._homed_now = None      # force the homing gate to re-evaluate
        self._homing_gate_tick()

    def _tool_tab_index(self, tw):
        for i in range(tw.count()):
            if tw.widget(i) is not None                     and tw.widget(i).objectName() == 'tool_tab':
                return i
        return -1

    def _tool_lock_flash(self):
        try:
            from PySide6.QtGui import QColor
            win = self.window()
            tw = win.findChild(QWidget, 'tabWidget') if win else None
            if tw is None:
                return
            idx = self._tool_tab_index(tw)
            if idx < 0:
                return
            self._tool_flash_on = not getattr(self, '_tool_flash_on', False)
            tw.tabBar().setTabTextColor(
                idx, QColor(230, 60, 60) if self._tool_flash_on
                else QColor(255, 255, 255))
        except Exception:
            pass

    def _declare_say(self, w, msg):
        """Loud where it counts: the log, and error_msg so STATUS goes red.

        The box carries no status label -- it matches the header+button boxes
        above it (operator 2026-08-03).
        """
        LOG.error(msg)
        try:
            import linuxcnc
            linuxcnc.command().error_msg(msg)
        except Exception:
            pass

    def _spindle_holds_declare(self):
        """M61 + G43/G49 + #3991, and nothing else.

        Deliberately does NOT call clamptool/unclamptool: the tool is already
        physically where it is, and the only thing wrong is the record.
        """
        w = getattr(self, '_sh_widgets', None)
        if not w:
            return
        raw = (w['edit'].text() or '').strip()
        try:
            n = int(float(raw))
            if n < 0:
                raise ValueError
        except ValueError:
            self._declare_say(w, 'DECLARE: %r is not a tool number '
                                 '(0 = empty)' % raw)
            return
        try:
            import linuxcnc
            c = linuxcnc.command()
            st = linuxcnc.stat()
            st.poll()
            if st.task_state != linuxcnc.STATE_ON:
                self._declare_say(w, 'DECLARE refused: machine is not ON')
                return
            if st.interp_state != linuxcnc.INTERP_IDLE:
                self._declare_say(w, 'DECLARE refused: interpreter is busy')
                return
            # NOT FULLY HOMED = MDI IS REFUSED, SILENTLY. LinuxCNC will
            # not accept an MDI command on non-identity kinematics until
            # every joint is homed -- see _jog_issue's note. On 2026-08-03
            # A/C were blocked by a failed head read, so DECLARE fired into
            # "Must be in MDI mode" and still reported success. Say the real
            # reason instead of retrying something that cannot work.
            if not all(st.homed[:NJ]):
                self._declare_say(w, 'DECLARE refused: the machine is not '
                                     'fully homed, so LinuxCNC will not '
                                     'accept an MDI command. A/C must home '
                                     'first.')
                return
            # RE-ASSERT the mode, do not just wait for it: ned_brain hands
            # MANUAL back on its own edge, and a request landing in that
            # window is overwritten. Same loop _jog_issue uses.
            import time
            c.mode(linuxcnc.MODE_MDI)
            deadline = time.time() + 4.0
            while True:
                st.poll()
                if st.task_mode == linuxcnc.MODE_MDI:
                    break
                if time.time() >= deadline:
                    self._declare_say(w, 'DECLARE refused: task never '
                                         'reached MDI mode. Nothing was '
                                         'changed.')
                    return
                c.mode(linuxcnc.MODE_MDI)
                time.sleep(0.1)
            # One sub, not three MDI lines: it also takes the tool out of
            # whatever fork claimed it, and doing that as one call means the
            # record can never end up half-updated.
            c.mdi('o<spindle_declare> call [%d]' % n)
            c.wait_complete(10.0)
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            st.poll()
            if all(st.homed[:NJ]):
                c.teleop_enable(1)
            st.poll()
            # VERIFY. The previous version printed "DECLARED T1" beside
            # "reports tool 0" on a run whose MDI had been refused. A claim
            # of success has to be checked against the machine.
            if int(st.tool_in_spindle) != n:
                self._declare_say(w, 'DECLARE FAILED: asked for T%d, LinuxCNC '
                                     'still reports tool %d. Nothing was '
                                     'changed.' % (n, st.tool_in_spindle))
                return
            msg = ('DECLARED T%d. LinuxCNC reports tool %d, offset %.4f'
                   % (n, st.tool_in_spindle, st.tool_offset[2]))
            LOG.info(msg)
            # Back to 0, so pressing DECLARE again declares the spindle EMPTY
            # -- operator 2026-08-03. Anything removed from the rack or the
            # spindle is assumed to have gone back to the table; nothing tries
            # to guess a new home for it.
            w['edit'].setText('0')
        except Exception as e:
            self._declare_say(w, 'DECLARE failed: %s' % e)

    def _on_drawbar(self, val):
        self._drawbar_released = bool(val)
        if self._drawbar_released:
            self._anon_clear('drawbar released')
        self._sync_load_enabled()

    def _anon_clear(self, why):
        try:
            pin = self.comp.getPin('anon-load-out')
            if pin.value:
                pin.value = False
                LOG.info('ANON LOAD latch cleared (%s)', why)
        except Exception:
            pass

    def _on_air(self, val):
        self._air = bool(val)
        if not self._air and self.comp is not None:
            try:
                self.comp.getPin('toolprobe-cmd').value = False
            except Exception:
                pass
        self._style()

    def _on_up(self, val):
        self._up = bool(val)
        self._style()

    def _style(self):
        if self.btn is None:
            return
        if not self._air:
            self.btn.setEnabled(False)
            self.btn.setText('TOOLPROBE (NO AIR)')
            self.btn.setStyleSheet(STYLE_NOAIR)
        else:
            self.btn.setEnabled(True)
            self.btn.setText('TOOLPROBE')
            self.btn.setStyleSheet(STYLE_UP if self._up else STYLE_DOWN)

    # ---- REF ALL (called by dros_xyzac's rebound ref_all_button) ---------
    # Deterministic order: unhome A/C FIRST (HOME_NO_REHOME makes homing an
    # already-homed absolute-encoder joint a silent no-op -- "clicking HOMED
    # did not home the swivel head"), pulse homeall-out so ned_brain arms the
    # fresh read, then start the normal HOME ALL sequence (A/C are seq 2,
    # last; brain's guard aborts them if the read hasn't landed in time).
    def get_ac_lock(self, ax):
        """The REAL lock state: the HAL pin the pendant obeys.

        Not the remembered dict -- if the two ever disagree the pin is what
        actually gates the wheel, and the display must show that rather than
        what the GUI believes.
        """
        try:
            return bool(self.comp.getPin('lock-' + ax + '-out').value)
        except Exception:
            return bool(getattr(self, '_ac_locked', {}).get(ax, False))

    def set_ac_lock(self, ax, on):
        # LOCK A / LOCK C (DRO buttons, repurposed A/C zeros): the pendant
        # skips locked axes in the MPG selection cycle (pendant.lock-a/-c
        # via the postgui sig-lock-a/-c nets).
        try:
            self.comp.getPin('lock-' + ax + '-out').value = bool(on)
            # remembered so typed moves / presets can REFUSE loudly instead
            # of quietly turning a locked head (operator 2026-08-02 13:43)
            self._ac_locked[ax] = bool(on)
            LOG.info('LOCK %s -> %s', ax.upper(), 'ON' if on else 'OFF')
        except Exception as e:
            LOG.error('set_ac_lock failed: %s', e)


    # HOME A / HOME C (Homing menu) = adopt the encoder, then drive that
    # joint to zero in JOINT MODE (operator 2026-08-10: "all I want is to
    # move A and C to zero without TCP whether or not its TCP mode").
    #
    # Joint mode matters: in world mode with ned_ac_kins the controller
    # holds the TOOL TIP still while the head swings, so A0 C0 demands a
    # huge XYZ excursion and is refused -- "Linear move would exceed joint
    # 0's positive limit" (observed 2026-08-10 11:5x). teleop_enable(0)
    # commands the joint directly; the kins module is untouched, so this
    # needs no switchkins.
    #
    # ORDER IS THE SAFETY PROPERTY. The coordinate is adopted FIRST (the
    # home, which under HOME_ABSOLUTE_ENCODER=2 cannot move anything), and
    # only then is a move commanded to a known destination with soft limits
    # live. A bad read now yields a wrong move that is bounded and
    # watchable -- never the unannounced 100 deg swing that homing itself
    # used to produce when a bad offset became travel.
    AC_ZERO_VEL = 5.0          # deg/s, HOME_FINAL_VEL's old value

    def ac_to_zero(self, ax):
        """Adopt the encoder for this head axis, then joint-jog it to 0."""
        import linuxcnc
        jn = 4 if ax == 'a' else 5
        label = 'HOME %s' % ax.upper()
        c, s = linuxcnc.command(), linuxcnc.stat()
        s.poll()
        if s.task_state != linuxcnc.STATE_ON:
            c.error_msg('%s refused: machine is not ON' % label)
            LOG.error('%s refused: not ON', label)
            return
        if any(s.joint[j]['homing'] for j in range(NJ)):
            c.error_msg('%s refused: a homing cycle is running' % label)
            LOG.error('%s refused: homing in progress', label)
            return
        # motion.jog-inhibit SWALLOWS JOGS SILENTLY. command.c reads it in
        # every jog handler and simply returns -- no error, no NML reply, the
        # caller cannot tell a completed jog from a discarded one. So this
        # has to be asked BEFORE the jog, not discovered afterwards by the
        # axis not having moved (2026-08-11: the -xyzab launch sequence sent
        # C to zero, nothing happened, and it blamed the head -- the real
        # cause was the tool-state lock, T13 clamped against a T0 record).
        if self._motion_lock_on():
            c.error_msg('%s refused: motion is locked (%s)'
                        % (label, self._tool_fault_detail()))
            LOG.error('%s refused: motion.jog-inhibit is set', label)
            return
        # (the 2026-08-10 stale-offset guard is gone: pso_live drives
        #  ini.N.home_offset every servo cycle now, so there is no wiped pin
        #  left to adopt. Nothing writes it, so nothing can blank it.)
        # 1. adopt. Under =2 this sets the coordinate and moves nothing.
        #    NO_REHOME is implied by =2 (taskintf.cc:326-336), so an
        #    already-homed joint must be unhomed first or home() is a
        #    silent no-op (homing.c:766-770).
        c.mode(linuxcnc.MODE_MANUAL)
        c.wait_complete(2.0)
        if s.homed[jn]:
            c.unhome(jn)
            c.wait_complete(2.0)
        c.home(jn)
        c.wait_complete(2.0)
        for _ in range(40):                 # <=4 s for homed to latch
            s.poll()
            if s.homed[jn] and not s.joint[jn]['homing']:
                break
            time.sleep(0.1)
        s.poll()
        if not s.homed[jn]:
            c.error_msg('%s: joint %d did not adopt the encoder -- NOT '
                        'moving' % (label, jn))
            LOG.error('%s: adopt failed, joint %d still unhomed', label, jn)
            return
        here = s.joint[jn]['output']
        LOG.info('%s: adopted %+.4f deg (no motion); now joint-jogging to 0',
                 label, here)
        if abs(here) < 0.001:
            LOG.info('%s: already at zero, nothing to move', label)
            return
        # 2. move, in JOINT mode so XYZ is not dragged into it
        c.teleop_enable(0)
        c.wait_complete(2.0)
        c.jog(linuxcnc.JOG_INCREMENT, True, jn, self.AC_ZERO_VEL, -here)
        LOG.info('%s: joint jog %+.4f deg at %.1f deg/s issued',
                 label, -here, self.AC_ZERO_VEL)

    # ==================================================================
    # -xyzab LAUNCH SEQUENCE  (operator 2026-08-11)
    # ==================================================================
    # "if C is not already at zero, it automatically does the physical
    #  homing for XYZ and C. XYZ so that we get to a safe place to home C
    #  automatically. A is left where it is."
    #
    # It lives HERE and not in ned_brain on purpose: ned_controls already
    # owns every motion command on this machine, and the brain's standing
    # rule is that stale home is a declaration and the brain issues no
    # motion at all. Moving C is motion, so it belongs to the GUI layer
    # and goes out through the same ac_to_zero / request_homeall paths the
    # buttons use -- no second, less-tested route to the same iron.
    #
    # A is untouched throughout. request_homeall unhomes A and C so the
    # brain re-adopts both from the absolute encoder (HOME_ABSOLUTE_ENCODER
    # = 2 -- sets the coordinate, no final move exists), and only C is then
    # driven anywhere.
    #
    # Polled, never blocking: this runs on the GUI thread.
    XYZAB_C_TOL = 0.05          # deg. Inside this, C counts as "at zero".

    def xyzab_launch_start(self):
        if os.environ.get('NED_MODE', '') != 'xyzab':
            return
        self._ab_step = 'wait_ready'
        self._ab_t = QTimer(self)
        self._ab_t.timeout.connect(self._ab_tick)
        self._ab_t.start(500)
        LOG.info('XYZAB: launch sequence armed (waiting for ON + homed + '
                 'tool table)')

    def _ab_done(self, why):
        self._ab_step = 'done'
        try:
            self._ab_t.stop()
        except Exception:
            pass
        LOG.info('XYZAB: launch sequence finished -- %s', why)

    def _ab_tick(self):
        import linuxcnc
        s = linuxcnc.stat()
        s.poll()
        step = getattr(self, '_ab_step', 'done')
        if step == 'done':
            return
        moving = (abs(s.current_vel) > 0.01
                  or any(s.joint[j]['homing'] for j in range(NJ)))
        if step == 'wait_ready':
            # The same two gates the whole GUI waits on: the machine is ON
            # and the stale-home declare has landed. Adding the tool table
            # here would be redundant -- _PreHomeInputGate already holds
            # every control shut until both are served.
            # B'S DECLARATION HAS NO PREREQUISITES AND MUST NOT WAIT FOR
            # ONE. It used to sit behind all(homed[:6]) -- i.e. behind the
            # A/C absolute read -- and on 2026-08-11 that read failed three
            # times ("HEADREAD A NO NEW FRAME since the SEN rise"). A and C
            # stayed unhomed, so B was never declared either; B unhomed
            # means MDI refuses "all joints must be homed", so the brain
            # could not re-declare the spindle tool, so tool.mm.lock2 held
            # motion.jog-inhibit, and the wheel would not even select the
            # rotary. One flaky serial frame took the whole machine down,
            # including the one axis that needs nothing from it.
            #
            # So: B is declared the moment the machine is ON. It is a
            # zero-length home on an axis with no switch and no encoder.
            # Only the C decision waits for the head.
            if s.task_state != linuxcnc.STATE_ON:
                return
            if moving:
                return
            if not s.homed[6]:
                self.home_b_inplace()
                return                      # re-enter next tick to confirm
            if not all(s.homed[:6]):
                if not getattr(self, '_ab_head_said', False):
                    self._ab_head_said = True
                    LOG.error('XYZAB: B is declared and usable; still waiting '
                              'on the A/C absolute read before C can be '
                              'checked (homed=%s)', tuple(s.homed[:6]))
                return
            # B IS DECLARED FIRST, and that ordering is load-bearing.
            # It used to be last, which deadlocked the whole launch
            # (2026-08-11): M61 -- the brain's spindle-tool re-declare --
            # goes through MDI, MDI refuses with "all joints must be homed",
            # and joint 6 was the one joint still unhomed. No tool record
            # means tool.mm.lock2 holds motion.jog-inhibit, which silently
            # discards the very jog that drives C to zero, which is the step
            # that was supposed to reach the B home. Nothing in that loop
            # reports anything; it just sits.
            # Declaring B first costs nothing -- it is a zero-length home
            # with no prerequisites -- and it makes the machine fully homed
            # before anything else is asked of it.
            self._ab_step = 'check_c'
            self._ab_deadline = time.time() + 30.0
            return
        if step == 'check_c':
            if moving:
                return
            if not s.homed[6]:
                if time.time() > self._ab_deadline:
                    self._ab_done('B never reported homed -- STOPPING before '
                                  'C is touched; nothing else will work '
                                  'until every joint is homed')
                return
            cpos = s.joint[5]['output']
            if abs(cpos) <= self.XYZAB_C_TOL:
                LOG.info('XYZAB: C is already at zero (%+.4f) -- nothing to '
                         'home', cpos)
                self._ab_done('B declared, C already at zero')
                return
            LOG.info('XYZAB: C reads %+.4f -- physical XYZ homing first so '
                     'the head has room, then C to zero', cpos)
            self.request_homeall()
            self._ab_step = 'wait_xyz'
            self._ab_deadline = time.time() + 180.0
            return
        if step == 'wait_xyz':
            # XYZ is a real switch-seeking cycle: it takes as long as it
            # takes. A deadline still exists because a sequence that never
            # finishes must not leave this timer spinning in silence.
            if time.time() > self._ab_deadline:
                self._ab_done('TIMED OUT waiting for the XYZ home -- C was '
                              'NOT moved, nothing is assumed')
                return
            if moving or not all(s.homed[:4]):
                return
            # Homing is NOT jog-inhibited (it drives free_tp directly), so
            # XYZ homes happily with the tool lock on -- but the jog that
            # follows would be discarded without a word. Wait for the lock
            # rather than spend the one attempt.
            if self._motion_lock_on():
                if not getattr(self, '_ab_lock_said', False):
                    self._ab_lock_said = True
                    LOG.error('XYZAB: XYZ is homed but motion is LOCKED (%s)'
                              ' -- holding before C is driven to zero',
                              self._tool_fault_detail())
                self._ab_deadline = time.time() + 120.0
                return
            LOG.info('XYZAB: XYZ homed; driving C to zero from %+.4f',
                     s.joint[5]['output'])
            self.ac_to_zero('c')
            self._ab_step = 'wait_c'
            self._ab_deadline = time.time() + 120.0
            return
        if step == 'wait_c':
            if time.time() > self._ab_deadline:
                self._ab_done('TIMED OUT waiting for C to reach zero')
                return
            if moving:
                return
            cpos = s.joint[5]['output']
            if abs(cpos) > self.XYZAB_C_TOL:
                if self._motion_lock_on():
                    # the jog was discarded, not attempted -- go round again
                    self._ab_step = 'wait_xyz'
                    self._ab_deadline = time.time() + 120.0
                    return
                self._ab_done('C stopped at %+.4f, not zero -- NOT declaring '
                              'B. Motion is not locked, so this is the head '
                              'or the C drive' % cpos)
                return
            self._ab_done('C driven to zero (%+.4f); B was declared '
                           'before the cycle' % cpos)
            return

    def home_b_inplace(self):
        """Declare B where it stands. -xyzab only.

        B has no switch and no encoder. Its home is in-place: HOME_SEARCH_VEL
        and HOME_LATCH_VEL are 0 and HOME == HOME_OFFSET == 0, so the cycle
        sets the coordinate and the final move is zero length. Wherever the
        chuck happens to be sitting becomes B0. This is the menu's Home B and
        the last step of the launch sequence -- one implementation, so the
        button and the automatic path cannot drift apart.
        """
        import linuxcnc
        c, s = linuxcnc.command(), linuxcnc.stat()
        s.poll()
        if s.task_state != linuxcnc.STATE_ON:
            c.error_msg('HOME B refused: machine is not ON')
            return
        if abs(s.current_vel) > 0.01 or any(s.joint[j]['homing']
                                            for j in range(7)):
            c.error_msg('HOME B refused: the machine is moving')
            LOG.error('HOME B refused: moving')
            return
        try:
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete(2.0)
            c.teleop_enable(0)
            c.wait_complete(2.0)
            # KEEP THE POSITION, DO NOT ZERO IT (operator 2026-08-11: "DO NOT
            # home B. I rather keep the work coordinate if MCS is meaningless
            # anyway"). [TRAJ]POSITION_FILE has already restored joint 6 by
            # now, so whatever it reads IS last session's angle. Feed that
            # straight back as the home offset: under HOME_ABSOLUTE_ENCODER=2
            # the cycle sets position := ini.6.home_offset and jumps to
            # HOME_FINISHED with no final move (homing.c:1139-1146), so the
            # declare is exactly a no-op on the number and cannot turn the
            # chuck. Homed still becomes true, which is the part MDI needs.
            here = s.joint[6]['output']
            # os.system, matching the other scripted halcmd in this file
            # (subprocess is deliberately not imported here) -- and always
            # timeout-wrapped: an unwrapped scripted halcmd is what deadlocked
            # the boot on the qtpyvcp PIPE bug.
            rc = os.system('timeout 3 halcmd setp ini.6.home_offset %.6f '
                           '>/dev/null 2>&1' % here)
            if rc != 0:
                LOG.error('HOME B: could not set ini.6.home_offset (rc=%d) '
                          '-- NOT homing; a declare against the wrong offset '
                          'silently moves the coordinate', rc)
                return
            # HOME_NO_REHOME is implied by =2 (taskintf.cc:326-336), so an
            # already-homed joint must be unhomed or home() is a silent no-op
            # (homing.c:766-770).
            if s.homed[6]:
                c.unhome(6)
                c.wait_complete(2.0)
            c.home(6)
            LOG.info('HOME B: joint 6 declared AT %+.4f (position kept, not '
                     'zeroed -- the work offset stays meaningful)', here)
        except Exception as e:
            LOG.error('HOME B failed: %s', e)

    def ac_to_zero_both(self):
        """HOME AC: A to zero, then C, one after the other."""
        LOG.info('HOME AC: A first, then C')
        self.ac_to_zero('a')
        self._ac_chain = QTimer(self)
        self._ac_chain.setSingleShot(True)
        self._ac_chain.timeout.connect(self._ac_zero_c_when_still)
        self._ac_chain.start(500)

    def _ac_zero_c_when_still(self):
        """Wait for A to stop before starting C -- never two head joints at
        once (operator 2026-08-10: clicking Home C during a Home A jog
        corrupted the C DRO)."""
        import linuxcnc
        s = linuxcnc.stat()
        s.poll()
        if abs(s.current_vel) > 0.01 or s.joint[4]['homing']:
            self._ac_chain.start(500)          # still moving; look again
            return
        LOG.info('HOME AC: A settled, starting C')
        self.ac_to_zero('c')

    def request_single_ref(self, ax):
        # REF A / REF C: one-axis REF ALL (operator 2026-08-01). Pulse the
        # per-axis pin; ned_brain does unhome -> fresh read -> home THAT
        # joint only -> verify that axis only. The other head axis is
        # untouched.
        try:
            import linuxcnc
            s = linuxcnc.stat()
            s.poll()
            if any(s.joint[j]['homing'] for j in range(NJ)):
                linuxcnc.command().error_msg(
                    'REF %s ignored: homing already in progress' % ax.upper())
                return
            pin = 'ref' + ax + '-out'
            self.comp.getPin(pin).value = True
            QTimer.singleShot(1000, lambda: self._pin_off(pin))
            LOG.info('REF %s requested (brain: unhome -> read -> home %s only)',
                     ax.upper(), ax.upper())
        except Exception as e:
            LOG.error('REF %s request failed: %s', ax.upper(), e)

    def _pin_off(self, pin):
        try:
            if self.comp is not None:
                self.comp.getPin(pin).value = False
        except Exception:
            pass

    def request_homeall(self):
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if any(s.joint[j]['homing'] for j in range(NJ)):
                LOG.error('REF ALL ignored: homing already in progress')
                return
            # X pair synchronized (-1). Y stays +1 in the same |1| phase and
            # LinuxCNC pulls it into the synchronized set during HOME ALL
            # (homing.c HOME_SEQUENCE_START rewrites same-|value| joints
            # negative) -- desired here: operator choreography is Z first,
            # then Y and X TOGETHER, A/C in parallel via the head read.
            # VERIFIED flip: never issue a home against unconfirmed sequence
            # state (the old async setp + 0.2 s sleep raced the sequencer's
            # group arming -- the 2026-08-01 wedge family).
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            # homing acts on JOINTS -- leave world/teleop first, like the
            # stock _home_joint ("must be in joint mode" otherwise)
            c.teleop_enable(0)
            c.wait_complete()
            for jn in (4, 5):
                if s.homed[jn]:
                    c.unhome(jn)
            c.wait_complete()
            if self.comp is not None:
                self.comp.getPin('homeall-out').value = True
                QTimer.singleShot(1000, self._homeall_pin_off)
            c.home(-1)
            # DISPLAY ONLY: the DRO's STALE/SESSION HOME banner turns green
            # once this is > 0 and all six joints report homed. It is counted
            # here rather than at the menu click so it means "a home really
            # went out", not "a menu item was clicked". NOTHING may gate on
            # it -- CLAUDE.md rule 17 binds my scripted motion, not the
            # operator's buttons.
            self._homeall_clicks = getattr(self, '_homeall_clicks', 0) + 1
            LOG.info('REF ALL: XYZ sequences dispatched (Z 0, Y 1, X pair '
                     '-2); A/C brain-homed read-gated after XYZ; '
                     'homeall_clicks=%d', self._homeall_clicks)
        except Exception as e:
            LOG.error('REF ALL failed: %s', e)

    def _homeall_pin_off(self):
        try:
            if self.comp is not None:
                self.comp.getPin('homeall-out').value = False
        except Exception:
            pass

    # ---- pendant axis -> DRO row highlight (forwarded in Qt) -------------
    def _find_dro(self):
        win = self.window()
        if win is None:
            return None
        w = win.findChild(QWidget, 'dros_xyzac')
        if w is not None and hasattr(w, 'set_mpg_axis'):
            return w
        # fallback: the UserDRO widget's objectName is not guaranteed --
        # duck-type on the method instead
        for w in win.findChildren(QWidget):
            if hasattr(w, 'set_mpg_axis'):
                return w
        return None

    def _on_mpg_zero(self, val):
        """Wheel asked to zero the selected axis. Rising edge only."""
        if not bool(val):
            return
        import linuxcnc
        try:
            idx = int(self.comp.getPin('zero-axis-idx-in').value)
        except Exception:
            idx = int(getattr(self, '_mpg_axis_now', 0))
        ax = self._INC_AXES[idx % 5].upper()
        c, s = linuxcnc.command(), linuxcnc.stat()
        s.poll()
        if (s.task_state != linuxcnc.STATE_ON
                or s.interp_state != linuxcnc.INTERP_IDLE
                or abs(s.current_vel) > 0.01
                or any(s.joint[j]['homing'] for j in range(NJ))):
            c.error_msg('ZERO %s refused: machine is busy' % ax)
            LOG.error('MPG ZERO %s refused: busy', ax)
            return
        if not self._take_mdi(c, 'MPG ZERO %s' % ax):
            return
        c.mdi('G10 L20 P0 %s0' % ax)
        LOG.error('MPG ZERO: %s set to 0 (G10 L20 P0 %s0) from the wheel',
                  ax, ax)
        self._hand_back_manual(c, 'MPG ZERO %s' % ax)

    AIR_GOOD = ('background: rgb(40,150,60); color: white; '
                'font: 12pt "Probe Basic Bebas Mono";')
    AIR_BAD = ('background: rgb(190,45,35); color: white; '
               'font: 12pt "Probe Basic Bebas Mono";')

    def _wire_air_button(self):
        """FLOOD -> AIR PRESSURE indicator (operator 2026-08-11: "make the
        flood button an indicator for air pressure instead. this machine has
        no flood").

        mist_button lives in OUR config -- user_buttons/template_user_buttons
        -- not in probe_basic.ui, so this touches nothing core. The operator
        wants MIST replaced outright ("repale MIST button with an indicator.
        so i can see if air is fine"): this machine has neither mist nor
        flood, and air is the input that silently stops it leaving E-STOP.

        NO NEW HAL PIN. ned-tab.air-ok-in already exists and is already netted
        to sig-air-pressure-ok, the RAW switch. Adding a second pin for this
        is what broke the previous attempt: a duplicate addPin aborts the
        WHOLE component, every ned-tab pin disappears, and postgui then dies
        on the first net that names one. Raw is also the right signal here --
        the operator is watching this while adjusting the regulator, and the
        0.5 s debounce on-delay would make a good adjustment look like
        nothing happened.

        Air matters more than any coolant button ever did on this machine:
        air.permit = estop-released AND air-ok, so without it the machine
        cannot leave E-STOP and every other symptom is downstream.
        """
        win = self.window()
        b = win.findChild(QWidget, 'mist_button') if win else None
        if b is None:
            LOG.error('AIR BUTTON: mist_button not found -- indicator NOT '
                      'built. Nothing else is affected.')
            return
        # FLOOD becomes CHIPBLOW in the same pass: the blower solenoid moves
        # off coolant-mist onto coolant-flood in postgui, so the button that
        # still DOES something keeps a label that matches what it does. Doing
        # it here rather than in RELABEL keeps the pair together -- rename one
        # without re-netting the other and the machine lies to the operator.
        fb = win.findChild(QWidget, 'flood_button')
        if fb is not None and hasattr(fb, 'setText'):
            fb.setText('CHIPBLOW')
            LOG.info('CHIPBLOW: flood_button relabelled; it drives '
                     'sol.blow via iocontrol coolant-flood')
        else:
            LOG.error('CHIPBLOW: flood_button not found -- it still says '
                      'FLOOD while driving the blower')
        for sig in ('clicked', 'pressed', 'released', 'toggled'):
            try:
                getattr(b, sig).disconnect()
            except Exception:
                pass
        try:
            b.setCheckable(False)
        except Exception:
            pass
        self._air_btn = b
        self._air_shown = None
        self._air_paint()
        # repainted on a timer, not only on the pin edge: qtpyvcp restyles its
        # own widgets on state changes and stomps the stylesheet, the same
        # reason the MPG row highlight is reapplied rather than set once.
        self._air_timer = QTimer(self)
        self._air_timer.timeout.connect(self._air_paint)
        self._air_timer.start(300)
        LOG.info('AIR BUTTON: FLOOD is now the air-pressure indicator '
                 '(reads ned-tab.air-ok-in = the raw switch)')

    def _air_paint(self):
        b = getattr(self, '_air_btn', None)
        if b is None:
            return
        ok = bool(getattr(self, '_air', False))
        want = ('AIR OK', self.AIR_GOOD) if ok else ('NO AIR', self.AIR_BAD)
        if want == getattr(self, '_air_shown', None):
            return
        self._air_shown = want
        b.setText(want[0])
        b.setStyleSheet(want[1])
        LOG.info('AIR: switch %s -> button reads %s', ok, want[0])

    def _on_head_busy(self, val):
        # One flag, one publisher (the brain). The homing menu polls
        # head_busy() and greys every entry while it is TRUE.
        self._head_busy = bool(val)
        LOG.info('HEAD BUSY -> %s (homing controls %s)',
                 self._head_busy, 'LOCKED' if self._head_busy else 'released')

    def _motion_lock_on(self):
        """The HAL motion lock, read from the pin. Unreadable = LOCKED."""
        try:
            return bool(self.comp.getPin('motion-lock-in').value)
        except Exception:
            return True

    def _on_motion_lock(self, val):
        self._motion_locked = bool(val)
        LOG.info('MOTION LOCK -> %s (HAL jog/feed inhibit)',
                 self._motion_locked)
        self._tool_lock_update()

    def head_busy(self):
        """TRUE while any head homing work is outstanding.

        Read from the HAL pin, not the remembered flag, so a missed listener
        callback cannot leave a homing control live during a cycle.
        """
        try:
            return bool(self.comp.getPin('head-busy-in').value)
        except Exception:
            return bool(getattr(self, '_head_busy', False))

    def _on_axis(self, val):
        # the GUI increment row is PER AXIS (operator, repeatedly):
        # remember which axis the wheel is on so the row can relabel
        self._mpg_axis_now = int(val)
        self._inc_row_ax = None          # force a relabel on the next tick
        self._apply_inc_slot()           # same slot, this axis's value
        w = self._find_dro()
        if w is not None:
            try:
                w.set_mpg_axis(int(val))
            except Exception:
                pass


    # NO LIVE-STEP OUTLINE (operator 2026-08-05: "the red outline around
    # the step speed is still there. remove it"). The clamp itself is
    # untouched -- jogblock still downshifts the effective step and still
    # publishes it on ned-tab.stepmm-in; nothing in the GUI paints it.

    def _on_inc_index(self, idx):
        # MIRROR BY SLOT, NEVER BY VALUE (operator 2026-08-07: the top
        # rotary step could not be selected -- "it highlights and drops
        # back to 0.25"). The old code matched the applied increment
        # against jogincrement._buttons_by_value, which is built from the
        # STOCK [DISPLAY]INCREMENTS mm ladder (0.01/0.05/0.1/0.5/1). On
        # A and C slot 4 is 0.5 DEG, and 0.5 collides with the stock
        # 0.5 mm button at index 3 -- so picking the top slot clicked
        # button 3, which wrote slot 3 back to the wheel. The slot index
        # is the only thing the two ladders share.
        try:
            i = int(idx)
        except (TypeError, ValueError):
            LOG.error('JOG STEPS: slot %r is not an index', idx)
            return
        self._inc_slot = i
        self._apply_inc_slot()

    def _apply_inc_slot(self):
        # the slot means whatever THIS axis's ladder says it means, so the
        # value is re-derived on every axis change as well
        i = getattr(self, '_inc_slot', None)
        if i is None:
            return
        ax = self._INC_AXES[int(getattr(self, '_mpg_axis_now', 0)) % 5]
        lad = self._INC_LADDER[ax]
        if not 0 <= i < len(lad):
            LOG.error('JOG STEPS: slot %d outside the %s ladder %s',
                      i, ax.upper(), lad)
            return
        # the jogblock approach profile handles speed at any step size;
        # nothing here may touch the increment or the rate cap
        self._jog_inc_mm = float(lad[i])
        win = self.window()
        if win is None:
            return
        jw = win.findChild(QWidget, 'jogincrement')
        if jw is None:
            LOG.error('JOG STEPS: jogincrement row not found -- no mirror')
            return
        from PySide6.QtWidgets import QAbstractButton
        btns = jw.findChildren(QAbstractButton)[-len(lad):]
        if len(btns) < len(lad):
            LOG.error('JOG STEPS: row has %d buttons, ladder %s has %d',
                      len(btns), ax.upper(), len(lad))
            return
        # setChecked, NOT click: the buttons are autoExclusive so this
        # moves the highlight on its own, and it does not re-emit clicked
        # (which would run qtpyvcp setJogIncrement on our relabelled text
        # and echo the slot straight back at the wheel)
        if not btns[i].isChecked():
            btns[i].setChecked(True)
            LOG.info('JOG STEPS: row mirrored to slot %d = %g on %s',
                     i, lad[i], ax.upper())

    # ---- Qt-only housekeeping --------------------------------------------
    def countdown_button(self):
        """The button whose countdown is running, or None.

        A COUNTDOWN EXISTS TO MAKE THE OPERATOR STOP AND THINK (operator
        2026-08-10: "the whole point of the countdown is that the user has
        to pause and think if he was sure about the task"). So while one
        runs, the ONLY live controls are E-STOP, POWER, EXIT and the
        counting button itself -- which is also how you cancel it.

        UNLOAD SPINDLE is NOT exempt during its 5 s countdown (operator
        2026-08-10: "during the 5 second countdown, NOTHING is useable").
        Its exception comes AFTER, once the drawbar has released.
        """
        for b, pend in list(getattr(self, '_unload_pend', {}).items()):
            if pend is not None:
                return b
        for b, pend in list(getattr(self, '_load_pend', {}).items()):
            if pend is not None:
                return b
        for b, pend in list(getattr(self, '_cal_pend', {}).items()):
            if pend is not None:
                return b
        dro = self._find_dro()
        for key in list(getattr(dro, '_zero_pending', {}) or {}):
            w = self.window().findChild(QWidget, key) if self.window() else None
            if w is not None:
                return w
        return None

    def _publish_wcs_once(self):
        """Get the active WCS into the status buffer, once per session.

        THE FAULT. After a fresh start stat.g5x_index reads 0 and
        stat.g5x_offset reads zeros, while the interpreter actually holds
        the right numbers -- an MDI `(debug, #5221)` prints -3730.005. The
        DRO renders those status fields, so the SCREEN shows machine
        coordinates while the MACHINE would cut in the right place. The
        screen lies and the iron does not, which is the dangerous way
        round. It is INTERMITTENT: some boots report correctly unaided.

        WHY. The field has one producer, SET_G5X_OFFSET (emccanon.cc:490 ->
        emctaskmain.cc:1901). Interp::init() calls it (rs274ngc_pre.cc:1103)
        but only by appending to interp_list (emccanon.cc:436) -- a queue
        that is flushed if anything aborts before task consumes it, which
        is what makes this a race. Re-commanding G54 does not help:
        convert_coordinate_system returns early when the origin is already
        active (interp_convert.cc:1793) and emits nothing.

        THE FIX. Select another system, then come back, as TWO SEPARATE
        BLOCKS. Measured by hand: `G55` -> index 2, then `G54` -> index 1
        with the correct offsets published. `G55 G54` in ONE block does
        nothing -- two codes from the same modal group net to no change,
        which is how iteration 1 failed.

        Settings words only, so no motion. G55 is active for the moment
        between the two blocks and nothing is commanded in that gap.
        """
        if getattr(self, '_wcs_published', False):
            return
        try:
            import linuxcnc
            s = linuxcnc.stat(); s.poll()
            # ...and NOT while a joint is still homing. all(homed) flickers
            # True mid-declare (A/C are declared one at a time), and firing
            # in that window put the MDI in during the cycle: the drain
            # timed out and it logged FAILED (2026-08-10 17:1x).
            if (not all(s.homed[:NJ])
                    or any(s.joint[j]['homing'] for j in range(NJ))
                    or s.interp_state != linuxcnc.INTERP_IDLE):
                n = getattr(self, '_wcs_wait', 0) + 1
                self._wcs_wait = n
                if n == 1 or n % 30 == 0:
                    LOG.error('WCS PUBLISH waiting: homed=%s interp=%d',
                              all(s.homed[:NJ]), s.interp_state)
                return
            if s.g5x_index != 0:
                self._wcs_published = True
                self._wcs_timer.stop()
                LOG.error('WCS PUBLISH not needed: LinuxCNC reported G%d '
                          '%.4f %.4f %.4f by itself', 53 + s.g5x_index,
                          s.g5x_offset[0], s.g5x_offset[1], s.g5x_offset[2])
                return
            self._wcs_published = True
            self._wcs_timer.stop()
            LOG.error('WCS PUBLISH: index 0 with offsets in the var file -- '
                      'republishing via G55 then G54')
            c = linuxcnc.command()
            c.mode(linuxcnc.MODE_MDI); c.wait_complete(3.0)
            c.mdi('G55'); c.wait_complete(3.0)
            c.mdi('G54'); c.wait_complete(3.0)
            # DO NOT LEAVE MDI UNTIL THE MESSAGE HAS LANDED. wait_complete
            # returns on command ACCEPTANCE, not when interp_list drains,
            # and SET_G5X rides that queue (emccanon.cc:436). Switching the
            # task mode discards what is still queued -- which is exactly
            # how the startup publication is lost in the first place, and
            # why iteration 3 logged "FAILED: index still 0" here while the
            # identical two blocks worked by hand (by hand I read the index
            # BEFORE going back to MANUAL). So poll the thing we actually
            # care about, then hand the mode back.
            import time as _t
            _dead = _t.time() + 3.0
            while _t.time() < _dead:
                s.poll()
                if s.g5x_index != 0:
                    break
                _t.sleep(0.05)
            c.mode(linuxcnc.MODE_MANUAL); c.wait_complete(2.0)
            s.poll()
            if s.g5x_index == 0:
                # A FAILED ATTEMPT MUST NOT LATCH. Un-arm and let the timer
                # try again -- the first attempt can land in a window the
                # guards did not catch, and a permanent give-up leaves the
                # DRO showing machine coordinates for the whole session.
                self._wcs_published = False
                self._wcs_timer.start(1000)
                LOG.error('WCS PUBLISH retrying: index still 0 after G55/G54')
            else:
                LOG.error('WCS PUBLISH OK: G%d active, offsets %.4f %.4f '
                          '%.4f', 53 + s.g5x_index, s.g5x_offset[0],
                          s.g5x_offset[1], s.g5x_offset[2])
        except Exception:
            LOG.exception('WCS PUBLISH errored -- DRO may show machine coords')

    def _gcode_freshness(self):
        """THE G-CODE ON SCREEN MUST BE THE G-CODE THAT RUNS.

        Two independent latches let them diverge (advisor 2026-08-10):

        1. qtpyvcp arms a QFileSystemWatcher on the loaded program
           (status.py:739) and `updateFile` (status.py:261) is the only
           thing that refreshes the view for an UNCHANGED path. Qt drops
           the watch after ONE atomic save -- write-temp + os.replace, what
           vim/gedit/VSCode do by default -- and it is never re-added. From
           then on no disk edit is ever noticed.
        2. RELOAD PGM does re-open the interpreter (program_actions.py:87
           -> emcTaskPlanOpen -> rs274ngc_pre.cc:1403 fopen, a genuine
           fresh read) but STATUS.file only emits when the filename STRING
           changes (status.py:774), so the VIEW is not refreshed.

        Together: screen shows the old program, Cycle Start executes the
        new one. The operator hit exactly that today -- 20 mm slots and
        F600 on screen, 19 mm and F4000 on disk.

        So: poll. stat() beats inotify here -- it survives atomic saves,
        editors on other hosts and NFS. Re-emitting the file signal
        re-populates the text view AND the backplot; it does NOT call
        program_open, so it cannot disturb the interpreter (RELOAD already
        owns that side).
        """
        try:
            import linuxcnc, os as _os
            from qtpyvcp.plugins import getPlugin
            st = getattr(self, '_nml_stat', None) or linuxcnc.stat()
            st.poll()
            path = st.file
            if not path or st.interp_state != linuxcnc.INTERP_IDLE:
                return
            sig = (path,) + tuple(
                getattr(_os.stat(path), a) for a in ('st_mtime_ns', 'st_size'))
        except Exception:
            return
        if sig == getattr(self, '_gc_sig', None):
            return
        first = getattr(self, '_gc_sig', None) is None
        self._gc_sig = sig
        if first:
            return                     # first sighting is the baseline
        # BOTH SIDES, ALWAYS, OR NOT AT ALL. Refreshing only the view would
        # just invert the divergence -- new on screen, old in the
        # interpreter. This is exactly what qtpyvcp's own watcher does when
        # it works (status.py:261-268): emit for the display, program_open
        # for the interpreter. Idle-only, so it can never disturb a run.
        try:
            import linuxcnc as _lc
            getPlugin('status').file.signal.emit(path)
            _lc.command().program_open(path)
            LOG.error('G-CODE REFRESHED (view + interpreter): %s changed on '
                      'disk -- screen, backplot and what Cycle Start runs '
                      'are back in agreement', path)
        except Exception:
            LOG.exception('G-CODE REFRESH FAILED for %s -- screen and '
                          'interpreter may disagree, reload by hand', path)

    def _tick(self):
        # BELT AND BRACES. _publish_wcs_once is one-shot and idempotent, so
        # driving it from both its own timer and here costs an attribute
        # test. Worth it: during this investigation each timer in turn
        # appeared to stop after one call, and a WCS that silently stays
        # unpublished shows the operator machine coordinates on a DRO they
        # are about to cut from.
        self._publish_wcs_once()
        self._gcode_freshness()
        win = self.window()
        if win is None:
            return
        # left spindle number = COMMANDED speed: the live M3/M4 command x
        # override (nonzero exactly while the spindle is told to turn --
        # "when it spins up ... it should display the commanded speed")
        try:
            import linuxcnc
            if getattr(self, '_nml_stat', None) is None:
                self._nml_stat = linuxcnc.stat()
            st = self._nml_stat
            st.poll()
            cmd = abs(st.spindle[0]['speed']) * st.spindle[0]['override']
            cmd = min(cmd, 18000.0)       # VFD ceiling, spindle_0.inc truth
            txt = '{:.0f}'.format(cmd)
            for lbl in getattr(self, '_rpm_labels', []):
                if lbl.text() != txt:
                    lbl.setText(txt)
        except Exception:
            pass
        for name in HIDE_CORE:
            w = win.findChild(QWidget, name)
            if w is not None and w.isVisible():
                w.hide()
        # Flood is unused on this machine (mist = chip blower); hide its menu
        # entry, and rename Mist -> CHIPBLOW (what it actually drives)
        try:
            from PySide6.QtGui import QAction
            a = win.findChild(QAction, 'action_Flood_toggle')
            if a is not None and a.isVisible():
                a.setVisible(False)
            m = win.findChild(QAction, 'action_Mist_toggle')
            if m is not None and m.text() != 'CHIP':
                m.setText('CHIP')
            # The HOMING MENU (menubar.yml -> qtpyvcp HomingMenu provider,
            # homing_menu.py: dynamic QActions bound to machine.home.all /
            # machine.home.axis:*) is the machine's ONLY homing interface
            # (operator 2026-08-01: REF buttons removed, "keep the menu
            # homing"). The stock bindings bypass every ned safeguard:
            # home.all homes the gantry sides CONCURRENTLY BUT INDIVIDUALLY
            # (the racking/ferror mode of 2026-07-31 16:11) and skips the
            # A/C unhome + fresh head read; home.axis:x homes ONE side;
            # home.axis:a|c is a NO_REHOME no-op when homed. Rebind every
            # entry to the safe ned cycle.
            # V units label RETIRED (2026-08-01 mockup): the override
            # cluster's center button shows "V <pct>%" and the readout is
            # mm/min (contract in docs/gui_button_spec.md). The old block
            # also called insertWidget on the QGridLayout -- the exact
            # rule-14(c) trap the cluster build avoids.
            # override cluster -10%/+10% buttons mirror the hidden stock
            # slider's enabled state (the action bindOk drives
            # slider.setEnabled from task_state / override-enabled).
            for row in (getattr(self, '_ovr_rows', None) or {}).values():
                en = row['slider'].isEnabled()
                if row['minus'].isEnabled() != en:
                    row['minus'].setEnabled(en)
                    row['plus'].setEnabled(en)
            if not getattr(self, '_homing_menu_fixed', False):
                # RETIRED (2026-08-01 evening): the rebind-after-the-fact
                # approach failed TWICE (silent 0/6 match racked the gantry
                # 13:08; the text-walk version intermittently rebound the
                # wrong QAction instances -- operator's Home All fell through
                # to stock on 3 of 4 clicks). The Homing menu is now OWNED at
                # the config level: custom_config.yml menubar override ->
                # ned_homing_menu:NedHomingMenu builds the six supervised
                # actions directly. Stock HomingMenu is never constructed,
                # so there is nothing to rebind and nothing to race.
                self._homing_menu_fixed = True
                LOG.info('Homing menu rebind RETIRED: config-owned '
                         'NedHomingMenu provider is the single homing path')
        except Exception as e:
            LOG.error('_tick core-touch block failed: %s', e)

    # ---- safe per-axis homing (Homing menu entries) ----------------------
    def home_x_pair(self):
        # Gantry law: the X sides home ONLY synchronized (pair -> -1, one
        # home(0) homes both, ini-homing.adoc:265). Operator spec: Home X
        # homes X ONLY -- but LinuxCNC groups synchronized joints by
        # ABS(sequence) (homing.c sync_ready + HOME_SEQUENCE_START), so Y
        # (+1) would be swept in (watchdog save #1, 2026-08-01 21:32).
        # Therefore Y's sequence is PARKED at 4 for the duration; ned_brain
        # (sequences permanent since 2026-08-02: Z 0, Y 1, pair -2, A/C 3)
        # All flips are VERIFIED before any home command is issued.
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if any(s.joint[j]['homing'] for j in range(NJ)):
                c.error_msg('Home X ignored: homing already in progress')
                return
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos:
                c.error_msg('Home X refused: machine is busy')
                return
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            c.teleop_enable(0)
            c.wait_complete()
            c.home(0)
            LOG.info('Home X -> synchronized pair homing (permanent seq -2)')
        except Exception as e:
            LOG.error('Home X failed: %s', e)

    def home_joint(self, label, jn):
        # Home Y / Home Z: THAT joint only. Normalize the X pair to +1
        # (permanent -2 pair: home(0) always homes both sides, only both)
        try:
            import linuxcnc
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if any(s.joint[j]['homing'] for j in range(NJ)):
                c.error_msg('Home %s ignored: homing already in progress' % label)
                return
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos:
                c.error_msg('Home %s refused: machine is busy' % label)
                return
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            c.teleop_enable(0)
            c.wait_complete()
            c.home(jn)
            LOG.info('Home %s -> home joint %d only', label, jn)
        except Exception as e:
            LOG.error('Home %s failed: %s', label, e)
