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
  ned-tab.inc-in         float in  <- pendant.increment
"""
import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from qtpyvcp import hal as qhal
from qtpyvcp.utilities import logger
from qtpyvcp.utilities.runtime_ui_loader import load_ui as load_runtime_ui

LOG = logger.getLogger(__name__)

STYLE_UP = 'font: 75 18pt; background: rgb(30,140,30); color: white;'
STYLE_DOWN = 'font: 75 18pt; background: rgb(140,30,30); color: white;'
STYLE_NOAIR = 'font: 75 18pt; background: rgb(70,70,70); color: rgb(180,180,180);'

# JOG & PRESETS speed table: key -> (linear F mm/min, angular F deg/min).
# v2 operator spec 2026-08-01 23:14: SLOW 200 / MEDIUM 1200 / FAST 4000
# mm/min, rotary 15 / 60 / 180 deg/min. Emitted as the F word on every
# command; the selection persists between moves. All values are inside the
# machine limits (X/Y 200 mm/s, Z 169.3 mm/s, angular 30 deg/s), so the
# planner never has to clamp these.
JOG_SPEEDS = {
    'slow':   (200.0,   15.0),
    'medium': (1200.0,  60.0),
    'fast':   (4000.0, 180.0),
}

# EMC 9-axis order XYZABCUVW -> stat.actual_position/g5x_offset/... index
# (same map the archived ned_moves panel and dros_xyzac use).
JOG_AXIS_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'c': 5}


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
            self.comp.addPin('air-ok-in', 'bit', 'in')
            self.comp.addPin('probe-up-in', 'bit', 'in')
            self.comp.addPin('inc-in', 'float', 'in')
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
            self.comp.ready()
            self.comp.addListener('air-ok-in', self._on_air)
            self.comp.addListener('probe-up-in', self._on_up)
            self.comp.addListener('inc-in', self._on_inc)
            self.comp.addListener('axis-in', self._on_axis)
            self.comp.addListener('jogspeed-in', self._on_jogspeed)
            self.comp.addListener('stepmm-in', self._on_stepmm)
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
        self._unload_pend = None
        QTimer.singleShot(0, self._wire_unload)

        # LOAD SPINDLE (core SubCallButtons load_spindle_button[_2]): same
        # 5 s countdown, second click cancels (operator 2026-08-02 13:5x
        # "load spindle should also have a 5 second countdown"). The
        # countdown then calls the button's OWN callSub() -- PB already
        # resolves the .ngc and pulls the tool number from the paired
        # load_spindle_tool_number[_2] field, so none of that is duplicated.
        self._load_pend = {}
        QTimer.singleShot(0, self._wire_load)

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
                                           QScrollArea, QFrame)
            from PySide6.QtWidgets import QWidget as _QW
            root = self.findChild(_QW, 'ned_controls_root') or self
            lay = root.layout()
            if lay is None:
                LOG.error('SUBTABS: ned_controls_root has no layout -- not built')
                return
            tabs = QTabWidget()
            tabs.setObjectName('ned_subtabs')
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
            b3l.addWidget(_mkbtn('shoulder', 'SHOULDER   spindle empty',
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
            tabs.addTab(cal_page, 'CALIBRATION')
            self._cal_tab_index = tabs.indexOf(cal_page)
            tabs.currentChanged.connect(self._cal_tab_changed)
            cstat = QLabel('')
            self._cal_status = cstat
            lay.addWidget(tabs)

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
            if getattr(self, '_cal_var_mtime', None) == mt:
                return
            self._cal_var_mtime = mt
            vals = {}
            with open(self.VAR_FILE) as f:
                for line in f:
                    p = line.split()
                    if len(p) == 2 and p[0].isdigit() and \
                       3040 <= int(p[0]) <= 3070:
                        vals[p[0]] = float(p[1])
            seen = getattr(self, '_cal_last', None)
            if seen is None:
                seen = self._cal_last = {}
            for key, (cur, prv) in fields.items():
                v = vals.get(key)
                if v is None:
                    continue
                # A/C are legitimately 0.0 (uncorrected); the puck numbers are
                # not, so only those treat 0 as "nothing measured yet"
                if key in ('3045', '3046', '3047') and abs(v) < 1e-9:
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
                chip.setText('A %s   C %s'
                             % ('LOCKED' if lk.get('a') else '---',
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
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            for p in ('3058', '3060', '3061', '3059'):
                c.mdi('#%s = 0' % p)
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
        'a':    ('cal_a_cycle',      'StartA',    True),
        'c':    ('cal_c_cycle',      'StartC',    True),
        # no 'ac' entry: StartAC is driven from Python (_ac_start), not by a
        # g-code sub.
        'goto': ('cal_goto_zero',    'ZERO',      True),
        'shoulder': ('cal_shoulder', 'SHOULDER',  True),
        'cleft':  ('cal_c_goto',     'C LEFT',    True),
        'cright': ('cal_c_goto',     'C RIGHT',   True),
    }

    CAL_EXTRA = {'cleft': -1, 'cright': 1}

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
        if s.task_state != linuxcnc.STATE_ON or not all(s.homed[:6]) \
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
        why = ('not homed' if not all(s.homed[:6]) else
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
                s2 = linuxcnc.stat()
                s2.poll()
                tool = getattr(s2, 'tool_in_spindle', 0)
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
                args = '[%.4f] [%.4f] [%.4f]' % (vals['3045'], vals['3046'],
                                                 vals['3047'])
                if extra is not None:
                    args += ' [%d]' % extra
                c.mdi('o<%s> call %s' % (sub, args))
                LOG.info('%s: %s issued with centre %.4f %.4f top %.4f',
                         label, sub, vals['3045'], vals['3046'], vals['3047'])
                self.cal_say('>> %s' % label)
            else:
                c.mdi('o<%s> call' % sub)
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
            homed_all = all(st.homed[:6])
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
        ('jp_p_xy0',    'XY 0',    (('x', 0.0), ('y', 0.0)),              False),
        ('jp_p_xyz0',   'XYZ 0',   (('x', 0.0), ('y', 0.0), ('z', 0.0)),  False),
        ('jp_p_z0',     'Z 0',     (('z', 0.0),),                         False),
        ('jp_p_zp10',   'Z +10',   None,                                  True),
        ('jp_p_xy0z10', 'XY0 Z10', (('x', 0.0), ('y', 0.0), ('z', 10.0)), False),
        ('jp_p_a0c0',   'A0 C0',   (('a', 0.0), ('c', 0.0)),              False))

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
            self._ac_locked = {'a': False, 'c': False}
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
                sec = 'AXIS_' + ax.upper()
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
            lbl.setText('F{:g} mm/min · {:g} deg/min'.format(lin, ang))
        LOG.info('JOG speed -> %s (F%g mm/min, %g deg/min)',
                 key.upper(), lin, ang)

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
                s = linuxcnc.stat()
                s.poll()
                z = self._jog_work_pos(s, 'z')
                vals = (('z', z + 10.0),)
                LOG.info('Z +10: work Z %.4f -> absolute target Z%.4f',
                         z, z + 10.0)
            self._jog_issue(label, list(vals))
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
        # metrics mirror the narrow-panel QLineEdit QSS (padding 2px 6px,
        # 10pt) so the flash never changes the field's height at 200 px
        w.setStyleSheet('background: rgb(96,28,28); color: white; '
                        'border: 1px solid rgb(220,80,80); '
                        'border-radius: 5px; padding: 2px 6px; font: 10pt;')
        QTimer.singleShot(700, lambda: w.setStyleSheet(''))

    # ---- UNITS IN/MM (settings tab) ---------------------------------------

    _UNITS_ON = ('background-color: rgb(235,170,40); color: black; '
                 'font-weight: bold;')   # house amber = active/selected

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
            fr = QFrame()
            fr.setObjectName('ned_units_frame')
            v = QVBoxLayout(fr)
            v.setContentsMargins(4, 4, 4, 4)
            v.setSpacing(4)
            lab = QLabel('UNITS')
            v.addWidget(lab)
            row = QHBoxLayout()
            row.setSpacing(6)
            self._units_btns = {}
            for key, txt in (('in', 'IN'), ('mm', 'MM')):
                b = QPushButton(txt)
                b.setObjectName('ned_units_' + key)
                b.setMinimumHeight(62)
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
               or any(s.joint[j]['homing'] for j in range(6)):
                c.error_msg('%s refused: machine is busy' % label)
                LOG.error('%s refused: machine busy', label)
                return
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi('G20' if key == 'in' else 'G21')
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
                s = linuxcnc.stat()
                s.poll()
                vals = [(ax, self._jog_work_pos(s, ax) + v)
                        for ax, v in vals]
            self._jog_issue(label, vals)
        except Exception as e:
            LOG.error('GO failed: %s', e)

    def _jog_issue(self, label, vals):
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
            if not all(s.homed[:6]):
                c.error_msg('%s refused: machine not fully homed -- Home All'
                            ' (Homing menu) first, or launch with run5.sh'
                            ' resume' % label)
                LOG.error('%s refused: not fully homed', label)
                return
            if s.interp_state != linuxcnc.INTERP_IDLE or not s.inpos \
               or any(s.joint[j]['homing'] for j in range(6)):
                c.error_msg('%s refused: machine is busy (program/MDI '
                            'running or homing)' % label)
                LOG.error('%s refused: machine busy', label)
                return
            # A/C LOCK GATE (operator 2026-08-02): a locked head axis must
            # never be turned by a typed move or a preset, and the refusal
            # must SAY SO -- silently dropping the axis would be worse.
            locked = [ax.upper() for ax, _t in vals
                      if ax in ('a', 'c') and self._ac_locked.get(ax)]
            if locked:
                names = ' and '.join(locked)
                c.error_msg('%s refused: %s axis is LOCKED -- click LOCK %s '
                            'in the DRO to unlock it first'
                            % (label, names, locked[0]))
                LOG.error('%s refused: %s LOCKED', label, names)
                for ax, _t in vals:
                    if ax.upper() in locked:
                        self._jog_flash(ax)
                return

            # SOFT-LIMIT PRE-CHECK, machine coordinates: limits are machine-
            # frame, targets are work-frame -> machine target = work target
            # + (g5x + g92 + tool) offset (house math; XY G5x rotation not
            # modeled, same as every other panel). A violating move is
            # REJECTED -- never clamped silently.
            if self._jog_limits:
                for ax, tw in vals:
                    i = JOG_AXIS_IDX[ax]
                    off = (s.g5x_offset[i] + s.g92_offset[i]
                           + s.tool_offset[i])
                    mt = tw + off
                    lo, hi = self._jog_limits[ax]
                    if mt < lo - 1e-6 or mt > hi + 1e-6:
                        self._jog_flash(ax)
                        c.error_msg(
                            '%s REJECTED: %s target %.3f (machine %.3f) '
                            'outside soft limits [%g .. %g]'
                            % (label, ax.upper(), tw, mt, lo, hi))
                        LOG.error('%s REJECTED: %s work %.4f -> machine '
                                  '%.4f outside [%g .. %g]',
                                  label, ax.upper(), tw, mt, lo, hi)
                        return
            words = ' '.join('{}{:.4f}'.format(ax.upper(), v)
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
                        homed = all(s.homed[:6])
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
            line = 'G90 G1 {} F{:.1f}'.format(words, feed)
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
            homing = any(st.joint[j]['homing'] for j in range(6))
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

    # ---- pendant double-tap+hold -> the 0-100% jog speed slider ----------
    def _on_jogspeed(self, val):
        win = self.window()
        if win is None:
            return
        slider = win.findChild(QWidget, 'linear_jog_slider')
        if slider is not None:
            try:
                slider.setValue(int(round(float(val))))
            except Exception:
                pass


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
        win = self.window()
        b = win.findChild(QWidget, 'remove_tool_2') if win else None
        if b is None:
            LOG.error('UNLOAD: remove_tool_2 button not found')
            return
        for sig in (b.pressed, b.released, b.clicked):
            try:
                sig.disconnect()
            except Exception:
                pass
        b.clicked.connect(lambda _=False: self._unload_click(b))

    def _wire_load(self):
        win = self.window()
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
            wired.append(name)
        if wired:
            LOG.info('LOAD SPINDLE: 5 s countdown wired on %d button(s): %s',
                     len(wired), ', '.join(wired))
        if missing:
            LOG.error('LOAD SPINDLE: %d button(s) NOT wired (no countdown, '
                      'stock instant call still live): %s',
                      len(missing), ', '.join(missing))

    def _load_click(self, b):
        pend = self._load_pend.get(b)
        if pend is not None:                     # second click = cancel
            pend['timer'].stop()
            b.setText(pend['text'])
            self._load_pend.pop(b, None)
            LOG.info('LOAD SPINDLE cancelled')
            return
        pend = {'text': b.text(), 'left': 5}
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
                b.callSub()          # PB's own sub call (tool no. from field)
                LOG.info('LOAD SPINDLE executed (countdown elapsed)')
            except Exception as e:
                LOG.error('LOAD SPINDLE failed: %s', e)

        timer.timeout.connect(tick)
        b.setText('CANCEL  5')
        timer.start(1000)

    def _unload_click(self, b):
        if self._unload_pend is not None:          # second click = cancel
            self._unload_pend['timer'].stop()
            b.setText(self._unload_pend['text'])
            self._unload_pend = None
            LOG.info('UNLOAD SPINDLE cancelled')
            return
        pend = {'text': b.text(), 'left': 5}
        timer = QTimer(self)
        pend['timer'] = timer
        self._unload_pend = pend

        def tick():
            if self._unload_pend is not pend:
                timer.stop()
                return
            pend['left'] -= 1
            if pend['left'] > 0:
                b.setText('CANCEL  {}'.format(pend['left']))
                return
            timer.stop()
            b.setText(pend['text'])
            self._unload_pend = None
            self._unload_run()

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
            if not all(s.homed[:6]):
                c.error_msg('UNLOAD SPINDLE needs a HOMED machine (MDI is '
                            'homed-gated on gantry kinematics). Home All (Homing menu) or resume first.')
                return
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi('o<unload_spindle> call')
            # the sub's M66 sensor waits outlive the 5 s default timeout;
            # a mode switch on a timed-out wait would abort it mid-sequence
            c.wait_complete(30.0)
            c.mode(linuxcnc.MODE_MANUAL)
            c.wait_complete()
            s.poll()
            if all(s.homed[:6]):
                c.teleop_enable(1)
            LOG.info('UNLOAD SPINDLE executed (drawbar released if sensors agreed)')
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


    def request_single_ref(self, ax):
        # REF A / REF C: one-axis REF ALL (operator 2026-08-01). Pulse the
        # per-axis pin; ned_brain does unhome -> fresh read -> home THAT
        # joint only -> verify that axis only. The other head axis is
        # untouched.
        try:
            import linuxcnc
            s = linuxcnc.stat()
            s.poll()
            if any(s.joint[j]['homing'] for j in range(6)):
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
            if any(s.joint[j]['homing'] for j in range(6)):
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
            LOG.info('REF ALL: physical reset dispatched (sequences are '
                     'static: Z 0, Y 1, X pair -2, A/C 3); homeall_clicks=%d',
                     self._homeall_clicks)
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

    def _on_axis(self, val):
        w = self._find_dro()
        if w is not None:
            try:
                w.set_mpg_axis(int(val))
            except Exception:
                pass


    # ---- pendant jump size -> on-screen increment button -----------------
    # RED DOT = the step the ladder is ACTUALLY using right now (operator
    # 2026-08-02: "as you change the interpretation, highlight the one that is
    # used with a red dot or something so you can see the original scale, but
    # also the one in effect"). The operator's own selection keeps the stock
    # checked look; the in-force rung gets a red ring. Same button = both.
    STEP_LIVE_QSS = 'border: 3px solid rgb(230,60,60); border-radius: 6px;'

    def _on_stepmm(self, val):
        try:
            self._step_live_mm = float(val)
        except (TypeError, ValueError):
            return
        win = self.window()
        if win is None:
            return
        jw = win.findChild(QWidget, 'jogincrement')
        pairs = getattr(jw, '_buttons_by_value', []) if jw is not None else []
        if not pairs and not getattr(self, '_stepdot_warned', False):
            self._stepdot_warned = True
            LOG.error('STEP DOT: jogincrement buttons not found -- live-step '
                      'indicator dead')
            return
        for btn, v in pairs:
            try:
                live = abs(float(v) - self._step_live_mm) < 1e-9
            except (TypeError, ValueError):
                continue
            want = self.STEP_LIVE_QSS if live else ''
            if btn.styleSheet() != want:
                btn.setStyleSheet(want)

    def _on_inc(self, val):
        try:
            self._jog_inc_mm = float(val)
            # the jogblock approach profile handles speed at any step size;
            # nothing here may touch the increment or the rate cap
        except Exception:
            pass
        win = self.window()
        if win is None:
            return
        jw = win.findChild(QWidget, 'jogincrement')
        for btn, v in getattr(jw, '_buttons_by_value', []):
            try:
                if abs(float(v) - float(val)) < 1e-9:
                    if not btn.isChecked():
                        btn.click()
                    break
            except Exception:
                pass

    # ---- Qt-only housekeeping --------------------------------------------
    def _tick(self):
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
            if any(s.joint[j]['homing'] for j in range(6)):
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
            if any(s.joint[j]['homing'] for j in range(6)):
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
