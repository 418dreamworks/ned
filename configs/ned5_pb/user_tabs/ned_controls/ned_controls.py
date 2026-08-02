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
            self.comp.ready()
            self.comp.addListener('air-ok-in', self._on_air)
            self.comp.addListener('probe-up-in', self._on_up)
            self.comp.addListener('inc-in', self._on_inc)
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
                b.setMinimumHeight(56)
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
                    c.error_msg('%s refused: could not enter MDI mode '
                                '(task busy?)' % label)
                    LOG.error('%s refused: task_mode never reached MDI after '
                              '%d re-asserts', label, reasserts)
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
            LOG.info('REF ALL: physical reset dispatched (sequences are '
                     'static: Z 0, Y 1, X pair -2, A/C 3)')
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
    def _on_inc(self, val):
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
