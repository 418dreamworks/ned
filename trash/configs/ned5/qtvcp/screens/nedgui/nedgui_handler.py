#!/usr/bin/env python3
# nedgui -- minimal ProbeBasic-style QtVCP screen for the ned 5-axis case.
#
# The whole point of this screen is the TAB/PAGE mechanism below: every extra
# screen is just a .ui file dropped in pages/ and one line in the PAGES list.

import os
import time
import hal
from PyQt5 import QtCore, QtWidgets, uic

from qtvcp.widgets.widget_baseclass import _HalWidgetBase
from qtvcp.core import Status, Action
from qtvcp import logger

LOG = logger.getLogger(__name__)
STATUS = Status()
ACTION = Action()

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, 'pages')

# ============================================================================
#  PAGES  --  ADD A TAB IN ONE LINE.
#
#  To add a page:
#    1. Drop  yourpage.ui  into the  pages/  folder (root widget = a QWidget).
#    2. Add   ("Your Tab", "yourpage.ui"),   to this list. Order = tab order.
#
#  RULES:
#    * Every widget objectName must be UNIQUE across ALL pages AND nedgui.ui.
#      A qtvcp HAL widget makes a HAL pin from its objectName, so a duplicate
#      name = duplicate HAL pin = the whole screen fails to load.
#    * Pages may use plain Qt widgets OR any qtvcp widget (declare the qtvcp
#      widget in the file's <customwidgets> block, same as nedgui.ui does).
#    * A page that fails to load does NOT crash the GUI -- it becomes a "!Tab"
#      showing the error, and the other pages still load.
# ============================================================================
PAGES = [
    ("Overview",  "page_01_overview.ui"),
    ("Session",   "page_session.ui"),
    ("Programs",  "page_programs.ui"),
    ("Solenoids", "page_solenoids.ui"),
    ("MPG",       "page_mpg.ui"),
    ("Limits",    "page_limits.ui"),
    ("IO",        "page_io.ui"),
]


class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.PATHS = paths

    # Called after the main .ui widgets exist and their HAL pins are built,
    # but BEFORE the HAL component is set 'ready' -- so pages loaded here can
    # still create HAL pins.
    def initialized__(self):
        self._setup_event_log()
        self._load_pages()
        self._set_dro_units()
        self._kill_annoyances()
        self._wire_override()
        self._number_widgets()
        self._start_dro_ac()
        self._mpg_setup()
        self._wire_io()
        self._wire_headread()
        self._wire_storedhome()
        self._wire_mpgreason()
        self._wire_solenoids()
        self._wire_toolrel()
        self._log_buttons()
        self._hook_status()

    # ---- widget lookup ---------------------------------------------------
    # Pages are built by uic.loadUi() into their OWN tree and added as tabs, so their
    # widgets are NOT attributes of self.w. getattr(self.w, name) raises for anything on
    # a page -- which silently killed every page button/label hookup. Search the tree.
    def _wg(self, name):
        w = getattr(self.w, name, None)
        if w is not None:
            return w
        try:
            found = self.w.findChildren(QtWidgets.QWidget, name)
            return found[0] if found else None
        except Exception:
            return None

    # ---- the page loader -------------------------------------------------
    def _load_pages(self):
        tabs = self.w.mainTabs
        for title, filename in PAGES:
            path = os.path.join(PAGES_DIR, filename)
            try:
                page = uic.loadUi(path)          # build the page widget tree
            except Exception as e:
                LOG.error("nedgui: page '{}' ({}) FAILED to load: {}".format(title, filename, e))
                err = QtWidgets.QLabel("Page '{}' failed to load:\n  {}\n\n{}".format(title, filename, e))
                err.setWordWrap(True)
                err.setStyleSheet("color:#ff6060; padding:12px;")
                tabs.addTab(err, "!" + title)
                continue
            # give the page's qtvcp HAL widgets their HAL pins (screen not 'ready' yet)
            self._hal_init_page(page)
            tabs.addTab(page, title)
        LOG.info("nedgui: {} page(s) loaded.".format(tabs.count()))

    def _hal_init_page(self, page):
        for widget in page.findChildren(QtWidgets.QWidget):
            if isinstance(widget, _HalWidgetBase):
                try:
                    widget.hal_init()
                except Exception as e:
                    LOG.error("nedgui: hal_init failed on '{}': {}".format(widget.objectName(), e))

    # ---- event logging (Claude monitors ~/Documents/ned/gui.md) ----------
    # Every button press + every important machine event (esp. error/message
    # popups) is timestamped into gui.md so Claude reads what happened instead
    # of asking the operator to paste anything.
    def _setup_event_log(self):
        self._logpath = os.path.expanduser('~/Documents/ned/gui.md')
        self._log('==== nedgui session start ====')

    def _log(self, msg):
        try:
            with open(self._logpath, 'a') as f:
                f.write('{}  {}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), msg))
        except Exception:
            pass

    def _log_buttons(self):
        # hook every button in the whole screen (main window + all loaded pages)
        try:
            btns = self.w.findChildren(QtWidgets.QAbstractButton)
        except Exception:
            return
        for btn in btns:
            try:
                name = btn.objectName() or '<unnamed>'
                btn.clicked.connect(
                    lambda checked=False, n=name, b=btn:
                    self._log('BUTTON  {}  "{}"'.format(n, (b.text() or '').strip())))
            except Exception:
                pass

    def _hook_status(self):
        # log machine events -- crucially the error/message popups (so Claude sees them)
        def hook(sig, fmt):
            try:
                STATUS.connect(sig, lambda *a: self._log(fmt(a)))
            except Exception:
                pass
        hook('error',             lambda a: 'ERROR   ' + ' | '.join(str(x) for x in a[1:]))
        hook('general-message',   lambda a: 'MSG     ' + ' | '.join(str(x) for x in a[1:]))
        hook('state-estop',       lambda a: 'STATE   estop')
        hook('state-estop-reset', lambda a: 'STATE   estop-reset')
        hook('state-on',          lambda a: 'STATE   machine ON')
        hook('state-off',         lambda a: 'STATE   machine OFF')
        hook('all-homed',         lambda a: 'STATE   all-homed')
        hook('not-all-homed',     lambda a: 'STATE   NOT-all-homed ' + (str(a[1]) if len(a) > 1 else ''))
        hook('mode-manual',       lambda a: 'MODE    manual')
        hook('mode-mdi',          lambda a: 'MODE    mdi')
        hook('mode-auto',         lambda a: 'MODE    auto')
        hook('interp-idle',       lambda a: 'INTERP  idle')
        hook('interp-run',        lambda a: 'INTERP  running')
        # After estop -> POWER, task comes back in FREE (joint) mode and the axis.N.jog-*
        # pins the MPG drives are dead until teleop is re-entered. Nothing re-entered it,
        # so the MPG died after every estop. Re-enter teleop whenever the machine comes ON
        # with all joints still homed.
        try:
            STATUS.connect('state-on',
                           lambda w: QtCore.QTimer.singleShot(800, self._ensure_teleop))
        except Exception:
            pass
        # A finished program/MDI o-call left task in AUTO/MDI mode -- axis wheel jog
        # dead until the operator estop-cycled ("zprobe does not give control back to
        # the mpg"). When the interpreter goes idle, hand control back: MANUAL + teleop.
        try:
            STATUS.connect('interp-idle',
                           lambda w: QtCore.QTimer.singleShot(400, self._auto_back_to_manual))
        except Exception:
            pass

    def _auto_back_to_manual(self):
        try:
            import linuxcnc
            s = linuxcnc.stat(); s.poll()
            if s.task_state == linuxcnc.STATE_ON \
               and s.interp_state == linuxcnc.INTERP_IDLE \
               and s.task_mode in (linuxcnc.MODE_AUTO, linuxcnc.MODE_MDI):
                c = linuxcnc.command()
                c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
                self._log('PROGRAM done -> MANUAL + teleop (MPG back)')
                self._ensure_teleop()
        except Exception as e:
            self._log('auto->manual failed: {}'.format(e))

    def _ensure_teleop(self):
        try:
            import linuxcnc
            s = linuxcnc.stat(); s.poll()
            if s.task_state == linuxcnc.STATE_ON and all(s.homed[:6]):
                linuxcnc.command().teleop_enable(1)
                self._log('TELEOP re-entered (machine ON + homed) -> MPG live')
            # unhomed: joint-mode jog nets (postgui) carry the MPG; teleop would be refused
        except Exception as e:
            self._log('TELEOP re-enter failed: {}'.format(e))

    # ---- units on the DROs (mm for linear, degrees for angular) ----------
    def _set_dro_units(self):
        try:
            labels = self.w.findChildren(QtWidgets.QLabel)
        except Exception:
            return
        for wdg in labels:
            if hasattr(wdg, 'angular_text_template'):
                try:
                    wdg.metric_text_template = '%10.3f mm'
                    wdg.imperial_text_template = '%9.4f in'
                    wdg.angular_text_template = '%9.2f °'
                    wdg.update_units()
                except Exception:
                    pass

    # ---- kill the black-screen (audio) + the MDI on-screen keyboard --------
    def _kill_annoyances(self):
        # audio is broken (no gst python binding) and its gst-launch playbin
        # grabs the Pi framebuffer -> black screen. Neuter EVERY play entry point --
        # jump/os_jump alone was not enough: the play_*/beep*/os_speak paths still
        # spawned subprocesses, and an error-heavy session blanked the screen on
        # every alert (operator: "blanked out SO MANY times").
        try:
            from qtvcp.lib import audio_player
            for meth in ('jump', 'os_jump', 'play_error', 'play_ready', 'play_attention',
                         'play_ring', 'play_done', 'play_login', 'play_logout', 'play_bell',
                         'beep_ring', 'beep_start', 'beep', 'os_speak', 'speak_cancel'):
                try:
                    setattr(audio_player.Player, meth, lambda *a, **k: None)
                except Exception:
                    pass
        except Exception:
            pass
        # no on-screen keyboard on the MDI (it steals focus / disables typing)
        try:
            for wdg in self.w.findChildren(QtWidgets.QWidget):
                if hasattr(wdg, 'soft_keyboard'):
                    try:
                        wdg.soft_keyboard = False
                    except Exception:
                        pass
                if hasattr(wdg, 'dialog_keyboard'):
                    try:
                        wdg.dialog_keyboard = False
                    except Exception:
                        pass
        except Exception:
            pass

    # ---- reliable limit override -----------------------------------------
    # override-limits is a TASK command (NOT a HAL pin -- motion.override-limits
    # doesn't exist). Call it directly. Press OVR LIMITS, then POWER, to enable
    # with a limit tripped; it clears once you jog off the limit.
    def _wire_override(self):
        try:
            self.w.btn_override.setCheckable(False)
            self.w.btn_override.clicked.connect(self._do_override)
        except Exception:
            pass

    def _do_override(self, *a):
        try:
            import linuxcnc
            linuxcnc.command().override_limits()
            self._log('OVERRIDE-LIMITS  sent')
        except Exception as e:
            self._log('OVERRIDE-LIMITS  FAILED: {}'.format(e))

    # ---- pre-home head absolute position ---------------------------------
    # HOME_OFFSET for A(JOINT_4)/C(JOINT_5) is DERIVED at launch by tools/pso_home.sh
    # = (startup encoder read) - (zero in head_zero.inc), UNWRAPPED. Show it at startup
    # so the head's true position is visible BEFORE homing takes place.
    def _fmt_deg(self, v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 'not read'      # never invent a position we have not measured
        s = '{:+.2f} deg'.format(f)
        if abs(f) >= 315:
            s += '  !! >315 (lost turn?)'
        return s

    def _read_home_offset(self, joint_inc):
        # read HOME_OFFSET straight from the param .inc (pso_home.sh wrote it at launch);
        # avoids depending on linuxcnc.ini resolving #INCLUDE files.
        try:
            p = os.path.expanduser('~/Documents/ned/configs/params/' + joint_inc)
            with open(p) as f:
                for ln in f:
                    if ln.startswith('HOME_OFFSET'):
                        return ln.split('=', 1)[1].strip()
        except Exception:
            return None
        return None

    # A/C DRO: absolute encoder position (HOME_OFFSET = read - zero) BEFORE homing, live
    # machine position AFTER -- so the 5-number DRO is never a lie of 0.000 pre-home.
    def _start_dro_ac(self):
        # Do NOT seed from joint_{a,c}.inc HOME_OFFSET. run5.sh no longer runs pso_home, so
        # that value is a stale leftover from an earlier session and would be displayed as if
        # it were the head's real position (seen: -3.98/-45.00 while the head was ~+3.5/+44).
        # Show nothing until a genuine read happens.
        self._ho_a = None
        self._ho_c = None
        try:
            import linuxcnc
            self._stat = linuxcnc.stat()
        except Exception:
            self._stat = None
        self._dro_timer = QtCore.QTimer()
        self._dro_timer.timeout.connect(self._update_dro_ac)
        self._dro_timer.start(300)
        self._update_dro_ac()
        # probe result: filesystem check, so keep it OFF the DRO tick (2 s is plenty)
        self._ztop_timer = QtCore.QTimer()
        self._ztop_timer.timeout.connect(self._poll_ztop)
        self._ztop_timer.start(2000)
        self._sess_timer = QtCore.QTimer()
        self._sess_timer.timeout.connect(self._poll_session)
        self._sess_timer.start(2000)
        self._poll_session()
        # ERROR CHANNEL: nothing else on this screen reads it (no ScreenOptions/Notify
        # widget), so ferrors/aborts were completely invisible -- no popup, no log.
        # Poll it here: every message goes to gui.md AND the status bar.
        try:
            import linuxcnc
            self._err_chan = linuxcnc.error_channel()
        except Exception:
            self._err_chan = None
        self._err_timer = QtCore.QTimer()
        self._err_timer.timeout.connect(self._poll_errors)
        self._err_timer.start(500)

    def _poll_errors(self):
        if self._err_chan is None:
            return
        try:
            m = self._err_chan.poll()
        except Exception:
            return
        if not m:
            return
        kind, text = m
        text = str(text).strip()
        self._log('ERROR   {}'.format(text))
        try:
            self.w.statusbar.setStyleSheet('color: rgb(255,80,80); font: 75 11pt;')
            self.w.statusbar.showMessage(text, 15000)
        except Exception:
            pass

    def _update_dro_ac(self):
        # A = joint 4 / axis idx 3 ; C = joint 5 / axis idx 5.
        # Pre-home: the last accepted absolute read (_ho_a/_ho_c; 'not read' until one lands).
        # DURING homing: actual_position -- the absolute homing sets the internal position to
        # the read the instant it starts, so the DRO visibly MOVES from the read value to
        # zero as the head travels. After homed: actual_position as normal.
        try:
            if self._stat is not None:
                self._stat.poll()

                def pick(jn, axidx, held):
                    homing = False
                    try:
                        homing = bool(self._stat.joint[jn]['homing'])
                    except Exception:
                        pass
                    if self._stat.homed[jn] or homing:
                        return self._stat.actual_position[axidx]
                    return held
                a = pick(4, 3, self._ho_a)
                c = pick(5, 5, self._ho_c)
            else:
                a, c = self._ho_a, self._ho_c
            # plain text on purpose: a RichText span here would re-parse HTML every tick
            self.w.dro_a.setText(self._fmt_deg(a))
            self.w.dro_c.setText(self._fmt_deg(c))
        except Exception:
            pass

    # Probe result: find_puck_top logs Z_TOP to puck_result.txt as it runs, so read
    # that (numbered params aren't reachable live from the GUI).
    def _poll_ztop(self):
        try:
            for d in (os.path.expanduser('~/Documents/ned/configs/ned5'),
                      os.path.expanduser('~/Documents/ned')):
                p = os.path.join(d, 'puck_result.txt')
                if not os.path.exists(p):
                    continue
                m = os.path.getmtime(p)
                if m == getattr(self, '_ztop_mtime', None):
                    return
                self._ztop_mtime = m
                for ln in open(p):
                    if 'Z_TOP' in ln:
                        v = ln.split('=', 1)[1].strip()
                        lz = self._wg('lbl_ztop_result')
                        if lz is not None: lz.setText('Z_top: {}'.format(v))
                        self._log('PROBE Z_TOP = {}'.format(v))
                return
        except Exception:
            pass

    # ---- numeric _NN tags on every text/box so elements can be named precisely ----
    def _tagspan(self, objname):
        tag = getattr(self, '_wtag', {}).get(objname, '')
        return ' <span style="font-size:7pt;color:#888">{}</span>'.format(tag) if tag else ''

    def _number_widgets(self):
        # walk widgets in construction order (stable), tag each Label/Button/GroupBox with
        # a small _NN, and log the map so both the operator and Claude can name things.
        self._wtag = {}
        n = 0
        for wdg in self.w.findChildren(QtWidgets.QWidget):
            if not isinstance(wdg, (QtWidgets.QLabel, QtWidgets.QAbstractButton, QtWidgets.QGroupBox)):
                continue
            name = wdg.objectName()
            if not name:
                continue
            n += 1
            tag = '_{:02d}'.format(n)
            self._wtag[name] = tag
            base = wdg.title() if isinstance(wdg, QtWidgets.QGroupBox) else wdg.text()
            self._log('WIDGET {} = {} "{}"'.format(tag, name, (base or '')[:30]))
            try:
                if isinstance(wdg, QtWidgets.QGroupBox):
                    wdg.setTitle('{}  {}'.format(base, tag))
                elif name.startswith('dro_'):
                    continue  # value fields: A/C driven by _update_dro_ac, X/Y/Z by qtvcp
                elif isinstance(wdg, QtWidgets.QLabel):
                    wdg.setTextFormat(QtCore.Qt.RichText)
                    wdg.setText('{}<span style="font-size:7pt;color:#888"> {}</span>'.format(base, tag))
                elif isinstance(wdg, QtWidgets.QAbstractButton):
                    wdg.setText('{}  {}'.format(base, tag))
            except Exception:
                pass

    # ---- SESSION: who is driving the machine (tools/claim.sh -> ned/session.txt) ----
    SESS_STYLE = {
        'claude':  ('CLAUDE IS USING THE MACHINE', 'rgb(20,20,20)', 'rgb(255,150,40)'),
        'waiting': ('WAITING ON YOU',              'rgb(20,20,20)', 'rgb(255,230,0)'),
        'user':    ('MACHINE IS YOURS',            'rgb(20,20,20)', 'rgb(80,200,80)'),
        'free':    ('MACHINE FREE',                'rgb(20,20,20)', 'rgb(80,200,80)'),
    }

    def _poll_session(self):
        try:
            p = os.path.expanduser('~/Documents/ned/session.txt')
            m = os.path.getmtime(p)
            if m == getattr(self, '_sess_mtime', None):
                return
            self._sess_mtime = m
            d = {}
            for ln in open(p):
                if '=' in ln:
                    k, v = ln.split('=', 1)
                    d[k.strip()] = v.strip()
        except Exception:
            return
        owner = (d.get('OWNER') or 'free').lower()
        note = d.get('NOTE') or ''
        title, fg, bg = self.SESS_STYLE.get(owner, self.SESS_STYLE['free'])
        for name, txt in (('lbl_session_banner', title), ('sess_state', title)):
            w = self._wg(name)
            if w is not None:
                try:
                    w.setText(txt)
                    w.setStyleSheet('font: 75 {}; padding: 4px; color: {}; background: {};'.format(
                        '11pt' if name.startswith('lbl_') else '26pt', fg, bg))
                except Exception:
                    pass
        for name, txt in (('sess_note', note), ('sess_since', 'since ' + (d.get('SINCE') or '-'))):
            w = self._wg(name)
            if w is not None:
                try: w.setText(txt)
                except Exception: pass

    # ---- HEAD ABSOLUTE READ (live, inside LinuxCNC) --------------------------
    # Ground truth (tools/pso_read.sh) needs a SEN double-pulse: a LOW window primes
    # the pack, the RISING edge makes it emit the absolute frame. SEN low also drops
    # both head packs to BB, so A/C physically CANNOT move during a read -- the read
    # is only ever taken with the head dead, which is exactly what we want.
    #   r4-select: 1 = A (NO), 0 = C (NC)   pso_abs pins carry multiturn/within.
    HEAD_ZERO = {'a': (36, 44350458, 128.25, -1), 'c': (-168, 4280673, 203.7471, 1)}
    R_COUNTS = 67108864          # 2^26 counts per motor rev

    def _wire_headread(self):
        for pin in ('sen-suppress', 'r4-select', 'sen-force', 'pso-enable', 'pso-reset'):
            try:
                self.hal.newpin(pin, hal.HAL_BIT, hal.HAL_OUT)
            except Exception as e:
                self._log('HEADREAD pin {} failed: {}'.format(pin, e))
        self._hr_step = 0
        self._hr_axis = 'c'
        self._hr_timer = QtCore.QTimer()
        self._hr_timer.timeout.connect(self._hr_tick)
        self._hr_cb = None
        self._hr_deg = {}      # per-axis result of the LAST read: deg, or None = no/rejected read
        self._hv_attempt = 0   # post-home verify correction attempts this cycle
        # No read buttons by design: the read runs automatically around a homing cycle.
        # HOME ALL is intercepted so it becomes: read A/C -> home -> read A/C to verify.
        # qtvcp's ActionButton wires its built-in action to the PRESSED signal
        # (action_button.py:436), not just clicked -- disconnecting clicked alone left the
        # built-in home firing at the instant of the click, racing (and beating) the reads:
        # A/C homed with stale offsets ~10 s before the fresh read landed.
        for sig in (self.w.btn_home.pressed, self.w.btn_home.released,
                    self.w.btn_home.clicked):
            try:
                sig.disconnect()
            except Exception:
                pass
        try:
            self.w.btn_home.clicked.connect(self._home_cycle)
        except Exception:
            pass
        # Display-only absolute read at startup: the operator wants the true A/C position
        # on the DRO without having to home (the read works machine-off via SEN force).
        QtCore.QTimer.singleShot(8000, self._startup_read)

    def _startup_read(self):
        if self._hr_step:
            return
        self._log('STARTUP READ: C then A (display only, no homing)')
        self._hr_start('c', lambda: self._hr_start('a'))

    # The HOME button is the cycle's progress display: READ C -> READ A -> HOMING ->
    # (verify) READ C/A -> HOME ALL. Without this the ~15 s of silent pre-reads made
    # the button look dead (operator mashed it 8x then quit 3 s before motion).
    def _home_btn(self, txt=None, busy=None):
        b = getattr(self.w, 'btn_home', None)
        if b is None:
            return
        try:
            if txt is not None:
                b.setText(txt)
            if busy is not None:
                b.setEnabled(not busy)
        except Exception:
            pass

    def _hr_start(self, axis, cb=None):
        if self._hr_step:
            return
        self._hr_cb = cb
        self._hr_axis = axis
        self._hr_step = 1
        self._hr_deg[axis] = None      # stays None unless a read is ACCEPTED
        self._home_btn('READ {}…'.format(axis.upper()), True)
        try:
            self.hal['r4-select'] = (axis == 'a')     # settle R4 BEFORE touching SEN
            self.hal['pso-enable'] = True             # reader may touch the board now
            self.hal['pso-reset'] = True              # flush: only 1 read works per session otherwise
            self._hr_p0 = int(hal.get_value('hm2_7i97.0.pktuart.0.parsed'))
        except Exception:
            self._hr_p0 = 0
        self._log('HEADREAD {} start (R4 set, SEN about to drop -> A/C locked)'.format(axis.upper()))
        self._hr_timer.start(self.HR_TICK_MS)

    # Read timing. The only HARD delay is the manual's: hold SEN low >= 1.3 s before the
    # rising edge (Yaskawa 6.12 p.315); the burst then starts within ~0.1 s and every
    # message is the complete snapshot. Ticks are 250 ms; SEN is low from st1 (0.25 s)
    # until the rise at HR_ST_RISE (1.75 s) = 1.5 s of low window.
    HR_TICK_MS    = 250
    HR_ST_RISE    = 7    # tick that raises SEN (low window 1.5 s > manual's 1.3 s)
    HR_ST_TIMEOUT = 28   # ~5 s after the rise with no parse -> report (-> no-frame path)

    def _hr_tick(self):
        # Proven bench sequence (3 reads in one session, alternating axes):
        #   R4 set -> flush -> SEN LOW (>=1.3 s) -> SEN HIGH -> parse the burst.
        # SEN LOW  = suppress 1 + force 0 (beats the gate even with the machine ON).
        # SEN HIGH = force 1 (works even with the machine OFF).
        # SEN low also drops both packs to BB, so A/C cannot move during a read.
        st = self._hr_step
        try:
            if self.HR_ST_RISE < st < self.HR_ST_TIMEOUT:
                # EARLY EXIT: each burst message is the complete snapshot, so the first
                # parse after the SEN rise IS the answer -- no need to sit out the window.
                try:
                    if int(hal.get_value('hm2_7i97.0.pktuart.0.parsed')) > self._hr_p1:
                        st = self.HR_ST_TIMEOUT
                except Exception:
                    pass
            if st == 1:
                self.hal['pso-reset'] = True      # flush FIFO + our buffer (stale other-axis bytes)
                self.hal['sen-suppress'] = True   # SEN LOW
                self.hal['sen-force'] = False
            elif st == 2:
                self.hal['pso-reset'] = False
            elif st == self.HR_ST_RISE:
                # snapshot parsed JUST before the rise: anything above this is burst data
                # (the reset-time snapshot _hr_p0 would also count stale pre-flush drain)
                try:
                    self._hr_p1 = int(hal.get_value('hm2_7i97.0.pktuart.0.parsed'))
                except Exception:
                    self._hr_p1 = self._hr_p0
                self.hal['sen-force'] = True      # rising edge -> pack bursts
            elif st >= self.HR_ST_TIMEOUT:        # burst captured (early exit) or timed out
                self._hr_timer.stop()
                self._hr_step = 0
                self._hr_report()
                cb = self._hr_cb; self._hr_cb = None
                if cb:
                    QtCore.QTimer.singleShot(300, cb)
                else:
                    self._home_btn('HOME ALL', False)   # bare read chain ends here
                try:
                    self.hal['sen-force'] = False
                    self.hal['sen-suppress'] = False
                    self.hal['pso-enable'] = False   # stop touching the board (servo timing)
                    # PARK R4 DE-ENERGIZED. Read cycles end on A, which left r4-select
                    # (= OUTPUT5 = R4 coil) energized for the REST OF THE SESSION -- and
                    # R4 also gates the 70 V rotary-brick mains (relays.md R4). The brick
                    # sat live all session; operator correlates that with screen blanking.
                    self.hal['r4-select'] = False
                except Exception:
                    pass
                return
        except Exception as e:
            self._hr_timer.stop(); self._hr_step = 0
            self._log('HEADREAD failed: {}'.format(e))
            self._home_btn('HOME ALL', False)
            return
        self._hr_step = st + 1

    def _hr_report(self):
        try:
            p = int(hal.get_value('hm2_7i97.0.pktuart.0.parsed'))
            mt = int(hal.get_value('hm2_7i97.0.pktuart.0.multiturn'))
            w = int(hal.get_value('hm2_7i97.0.pktuart.0.within'))
        except Exception as e:
            self._log('HEADREAD read failed: {}'.format(e)); return
        if p == self._hr_p0:
            self._log('HEADREAD {} NO NEW FRAME (parsed still {})'.format(self._hr_axis.upper(), p))
            txt = '{}: no frame'.format(self._hr_axis.upper())
        else:
            m0, w0, gear, sign = self.HEAD_ZERO[self._hr_axis]
            deg = sign * ((mt - m0) * self.R_COUNTS + (w - w0)) / (self.R_COUNTS * gear) * 360.0
            # GUARD 1 -- STALE-READ DETECTION. The mux may not have switched, or the buffer may
            # still hold the other axis's bytes. If this read's raw counts are identical to the
            # PREVIOUS axis's read, it is not our data. (Seen: A reported mt=-143, which was C's
            # value, giving +504 deg on an axis whose soft limit is +/-115.)
            prev = getattr(self, '_hr_lastraw', None)
            if prev is not None and prev == (mt, w):
                self._log('HEADREAD {} REJECTED: raw (mt={} w={}) identical to previous read '
                          '-- stale/other-axis data, NOT writing home_offset'.format(
                              self._hr_axis.upper(), mt, w))
                return
            self._hr_lastraw = (mt, w)
            # GUARD 2 -- RANGE CHECK. Never write an offset outside the axis soft limits.
            lim = 115.0 if self._hr_axis == 'a' else 315.0
            if abs(deg) >= lim:
                self._log('HEADREAD {} REJECTED: {:+.3f} deg is outside +/-{} soft limit '
                          '-- NOT writing home_offset (homing would command a huge move)'.format(
                              self._hr_axis.upper(), deg, lim))
                try:
                    lb = self._wg('lbl_head_read')
                    if lb is not None:
                        lb.setText('{}: {:+.1f} deg REJECTED (outside +/-{})'.format(
                            self._hr_axis.upper(), deg, lim))
                except Exception:
                    pass
                return
            txt = '{}: {:+.3f} deg  (mt={} w={})'.format(self._hr_axis.upper(), deg, mt, w)
            self._log('HEADREAD ' + txt)
            self._hr_deg[self._hr_axis] = deg
            # Feed the DRO: the read value shows immediately, and once homing starts the
            # DRO follows the live move down to zero (see _update_dro_ac).
            if self._hr_axis == 'a':
                self._ho_a = deg
            else:
                self._ho_c = deg
            # Feed the LIVE value into homing. ini.N.home_offset is settable at runtime,
            # so every HOME uses a fresh read instead of the stale launch-time INI value.
            jn = 4 if self._hr_axis == 'a' else 5
            try:
                os.system("halcmd setp ini.{}.home_offset {:.4f} >/dev/null 2>&1".format(jn, deg))
                self._log('HEADREAD -> ini.{}.home_offset = {:+.4f}'.format(jn, deg))
            except Exception as e:
                self._log('HEADREAD home_offset set failed: {}'.format(e))
        lb = self._wg('lbl_head_read')
        if lb is not None:
            try: lb.setText(txt)
            except Exception: pass

    # ---- STORED HOMING (XYZ/W, joints 0-3) -----------------------------------
    # The XYZ scales are incremental: the FPGA counter free-runs, but the hm2 driver
    # re-bases its zero at every load (encoder.c:744), so the reference dies with every
    # LinuxCNC session and every power-down. Scheme: while joints 0-3 are homed and at
    # rest, keep writing their positions to stored_home.json; a session launched with
    # `tools/run5.sh resume` uses a generated ini whose JOINT_0-3 home IN PLACE
    # (HOME_SEARCH_VEL/LATCH = 0 -> homing.c:807 immediate path: position becomes
    # ini.N.home_offset, zero-length final move to ini.N.home). HOME ALL arms those
    # runtime pins from the file after an operator confirmation. In the NORMAL config
    # this cannot be offered as a button: search vel is config-time only (inihal.cc
    # exposes only home/home_offset/home_sequence at runtime).
    SH_FILE = os.path.expanduser('~/Documents/ned/configs/ned5/stored_home.json')

    def _wire_storedhome(self):
        self._resume_mode = 'resume' in os.path.basename(os.environ.get('INI_FILE_NAME', ''))
        self._sh_last = None
        self._sh_last_t = 0.0
        self._sh_timer = QtCore.QTimer()
        self._sh_timer.timeout.connect(self._sh_save)
        self._sh_timer.start(10000)
        if self._resume_mode:
            self._log('STORED HOMING: RESUME config active -- HOME ALL restores joints 0-3 '
                      'from stored_home.json (no motion) after confirmation')

    def _sh_save(self):
        # Persist only when joints 0-3 are homed AND nothing moves: the file then always
        # holds a trustworthy at-rest snapshot (a crash mid-move leaves the pre-move one).
        try:
            if self._stat is None:
                return
            self._stat.poll()
            if not all(self._stat.homed[jn] for jn in (0, 1, 2, 3)):
                return
            if self._stat.current_vel > 1e-6:
                return
            if any(abs(self._stat.joint[jn]['velocity']) > 1e-4 for jn in (0, 1, 2, 3)):
                return
            pos = [round(self._stat.joint_actual_position[jn], 4) for jn in (0, 1, 2, 3)]
            now = time.time()
            if self._sh_last is not None and now - self._sh_last_t < 600 \
               and max(abs(a - b) for a, b in zip(pos, self._sh_last)) < 0.005:
                return
            import json
            tmp = self.SH_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'saved': time.strftime('%Y-%m-%d %H:%M:%S'),
                           'joints': {str(j): p for j, p in zip((0, 1, 2, 3), pos)}}, f)
            os.replace(tmp, self.SH_FILE)
            self._sh_last = pos
            self._sh_last_t = now
        except Exception:
            pass

    def _resume_prep(self):
        # RESUME config: joints 0-3 home IN PLACE at ini.N.home_offset. NEVER let that
        # run un-armed (it would silently relabel wherever-the-machine-is as machine
        # zero). Arm the pins from a validated source or refuse the whole cycle.
        try:
            self._stat.poll()
            homed = all(self._stat.homed[jn] for jn in (0, 1, 2, 3))
        except Exception:
            self._sh_fail('cannot read machine status')
            return False
        if homed:
            # Re-home within a resume session: re-arm with CURRENT positions, else the
            # in-place home would relabel the machine with the stale stored numbers.
            vals = {jn: self._stat.joint_actual_position[jn] for jn in (0, 1, 2, 3)}
            src = 'current positions (re-home in place)'
        else:
            import json
            try:
                with open(self.SH_FILE) as f:
                    d = json.load(f)
                saved = d.get('saved', '?')
                vals = {jn: float(d['joints'][str(jn)]) for jn in (0, 1, 2, 3)}
            except Exception as e:
                self._sh_fail('stored_home.json missing/unreadable ({})'.format(e))
                return False
            for jn, v in vals.items():
                try:
                    lo = self._stat.joint[jn]['min_position_limit']
                    hi = self._stat.joint[jn]['max_position_limit']
                except Exception:
                    self._sh_fail('joint limits unavailable')
                    return False
                if not (lo - 0.001 <= v <= hi + 0.001):
                    self._sh_fail('joint {} stored {:+.3f} outside limits [{:.1f}, {:.1f}]'
                                  .format(jn, v, lo, hi))
                    return False
            msg = ('Restore stored XYZ/W homing?\n\nSaved: {}\n'
                   'X {:+.3f}   Y {:+.3f}   Z {:+.3f}   X2 {:+.3f}\n\n'
                   'ONLY if the machine has NOT been moved since then.\n'
                   'Joints 0-3 will be declared homed AT these positions -- no motion.'
                   ).format(saved, vals[0], vals[1], vals[2], vals[3])
            r = QtWidgets.QMessageBox.question(
                self.w, 'RESTORE STORED HOMING', msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No)
            if r != QtWidgets.QMessageBox.Yes:
                self._sh_fail('operator declined')
                return False
            src = 'stored_home.json (saved {})'.format(saved)
        for jn, v in vals.items():
            # stderr NOT hidden: a silent setp failure here would home to garbage
            rc = os.system('halcmd setp ini.{}.home_offset {:.4f}'.format(jn, v))
            rc |= os.system('halcmd setp ini.{}.home {:.4f}'.format(jn, v))
            if rc:
                self._sh_fail('halcmd setp failed for joint {}'.format(jn))
                return False
        self._log('STORED HOMING: armed joints 0-3 from {}: {}'.format(
            src, '  '.join('J{}={:+.3f}'.format(jn, vals[jn]) for jn in (0, 1, 2, 3))))
        return True

    def _sh_fail(self, why):
        txt = ('STORED HOMING refused: {} -- NOT homing. '
               'Relaunch with tools/run5.sh for normal switch homing.').format(why)
        self._log(txt)
        try:
            self.w.statusbar.setStyleSheet('color: rgb(255,80,80); font: 75 11pt;')
            self.w.statusbar.showMessage(txt, 15000)
        except Exception:
            pass

    # ---- HOMING CYCLE: read A/C -> home -> read A/C (verify) -----------------
    # The absolute read must be FRESH at every homing, otherwise a second home in one
    # power cycle re-applies a stale offset and commands an unearned move. The read
    # feeds ini.N.home_offset live, so re-homing is always correct.
    def _home_cycle(self, *a):
        # Machine must be ON or the final home command is silently rejected AFTER the
        # ~10 s of reads ("command (EMC_JOINT_HOME) cannot be executed until the machine
        # is out of E-stop and turned on") -- refuse loudly up front instead.
        try:
            import linuxcnc
            s = linuxcnc.stat(); s.poll()
            if s.task_state != linuxcnc.STATE_ON:
                txt = 'HOME refused: machine is OFF -- press POWER first'
                self._log(txt)
                try:
                    self.w.statusbar.setStyleSheet('color: rgb(255,80,80); font: 75 11pt;')
                    self.w.statusbar.showMessage(txt, 8000)
                except Exception:
                    pass
                self._home_btn('PRESS POWER', False)
                QtCore.QTimer.singleShot(2500, lambda: self._home_btn('HOME ALL', False))
                return
        except Exception:
            pass
        if getattr(self, '_resume_mode', False) and not self._resume_prep():
            return
        self._log('HOME CYCLE: pre-read C then A, then home')
        self._hv_attempt = 0
        # Fresh absolute read of BOTH axes (pso_live, queued reads) feeds
        # ini.4/5.home_offset BEFORE any motion; _home_poll re-reads both
        # afterwards to VERIFY (each should come back ~0.000).
        self._hr_start('c', lambda: self._hr_start('a', self._home_issue))

    def _home_issue(self):
        try:
            import linuxcnc
            c = linuxcnc.command()
            c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
            # HOME_NO_REHOME (auto-set with HOME_ABSOLUTE_ENCODER) makes a home command
            # on an already-homed joint a SILENT no-op (homing.c:765). Unhome A/C first
            # so every HOME ALL re-applies the fresh read, not the offset of the last one.
            try:
                s = linuxcnc.stat(); s.poll()
                for jn in (4, 5):
                    if s.homed[jn]:
                        c.unhome(jn)
                c.wait_complete()
            except Exception:
                pass
            c.home(-1)
            self._log('HOME CYCLE: home-all issued (offsets from live read)')
            self._home_btn('HOMING…', True)
        except Exception as e:
            self._log('HOME CYCLE: home failed: {}'.format(e))
            self._home_btn('HOME ALL', False)
            return
        self._home_wait = 0
        self._home_timer = QtCore.QTimer()
        self._home_timer.timeout.connect(self._home_poll)
        self._home_timer.start(1000)

    def _home_poll(self):
        self._home_wait += 1
        done = False
        try:
            if self._stat is not None:
                self._stat.poll()
                done = all(self._stat.homed[:6])
        except Exception:
            pass
        if done or self._home_wait > 90:
            self._home_timer.stop()
            self._log('HOME CYCLE: {} -> post-read verify'.format('homed' if done else 'TIMEOUT'))
            QtCore.QTimer.singleShot(500, self._post_verify)

    # ---- POST-HOME VERIFY: re-read both axes; off = NOT actually homed ---------
    # A joint that verifies off truly did not home (it carries a wrong zero), so the
    # correction is a real re-home: unhome it (clears the homed flag) and home again
    # with the fresh read already sitting in ini.N.home_offset. One correction round;
    # if it STILL verifies off, the joint is left UNHOMED and an error dialog says so.
    HR_VERIFY_TOL = 0.05   # deg; read repeatability measured ~0.0002, homing residual ~0

    def _post_verify(self):
        self._hr_start('c', lambda: self._hr_start('a', self._verify_eval))

    def _verify_eval(self):
        bad, msgs = [], []
        for ax in ('c', 'a'):
            d = self._hr_deg.get(ax)
            if d is None:
                bad.append(ax); msgs.append('{}: verify read FAILED'.format(ax.upper()))
            elif abs(d) > self.HR_VERIFY_TOL:
                bad.append(ax); msgs.append('{}: {:+.3f} deg after homing'.format(ax.upper(), d))
        if not bad:
            self._log('HOME VERIFY OK: C={:+.3f} A={:+.3f} deg'.format(
                self._hr_deg.get('c'), self._hr_deg.get('a')))
            self._home_btn('HOME ALL', False)
            return
        if self._hv_attempt < 1:
            self._hv_attempt += 1
            self._log('HOME VERIFY: {} -- NOT actually homed, correcting '
                      '(unhome + rehome with the fresh read)'.format('; '.join(msgs)))
            try:
                import linuxcnc
                c = linuxcnc.command()
                c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
                for ax in bad:
                    c.unhome(4 if ax == 'a' else 5)
                c.wait_complete()
                c.home(-1)
            except Exception as e:
                self._verify_fail(bad, msgs, 'correction failed: {}'.format(e))
                return
            self._home_btn('RE-HOMING…', True)
            self._home_wait = 0
            self._home_timer.start(1000)      # re-poll homed -> _post_verify re-runs
        else:
            self._verify_fail(bad, msgs, 'still off after one correction')

    def _verify_fail(self, bad, msgs, why):
        # The homed flag must not lie: leave the offending joints unhomed.
        try:
            import linuxcnc
            c = linuxcnc.command()
            c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
            for ax in bad:
                c.unhome(4 if ax == 'a' else 5)
        except Exception:
            pass
        txt = 'HOMING VERIFY FAILED ({}): {}. Joint(s) {} left UNHOMED.'.format(
            why, '; '.join(msgs), ', '.join(ax.upper() for ax in bad))
        self._log(txt)
        self._home_btn('HOME ALL', False)
        try:
            QtWidgets.QMessageBox.critical(self.w, 'HOMING VERIFY FAILED', txt)
        except Exception:
            pass

    # ---- IO tab: every field I/O pin live, with a last-change banner ----------
    # The point: touch the probe (or trip anything) and SEE which pin flipped,
    # without hunting -- the banner names the last pin that changed and when.
    IO_ANNOT = {'hm2_7i97.0.7i84.0.0.input-28': 'PROBE',
                'motion.probe-input': 'PROBE->MOTION'}

    def _wire_io(self):
        holder = self._wg('io_grid_holder')
        if holder is None:
            self._log('IO tab: grid holder not found')
            return
        grid = holder.layout()
        import subprocess, re
        try:
            out = subprocess.run(['halcmd', '-s', 'show', 'pin'],
                                 capture_output=True, text=True, timeout=5).stdout
        except Exception as e:
            self._log('IO tab: halcmd enumerate failed: {}'.format(e))
            return
        names = []
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) < 5:
                continue
            name = parts[4]
            if re.match(r'hm2_7i97\.0\.(7i84\.0\.0\.(input|output)-\d+$|inmux\.00\.input-\d+$|ssr\.00\.out-\d+$)', name):
                # the netted SIGNAL is the pin's PROPER NAME (sig-tool-probe, ...) --
                # taken live from HAL so the display can never drift from the wiring
                sig = parts[6] if len(parts) >= 7 and parts[5] in ('==>', '<==', '<=>') else None
                names.append((name, sig))
        names.append(('motion.probe-input', None))
        # named signals first (alphabetical), unnetted pins after
        names.sort(key=lambda t: (t[1] is None, t[1] or t[0]))
        self._io_pins = {}
        cols = 4
        for i, (name, sig) in enumerate(names):
            short = (name.replace('hm2_7i97.0.', '').replace('7i84.0.0.', '84.')
                         .replace('inmux.00.', 'mux.').replace('ssr.00.', 'ssr.'))
            if sig:
                short = '{}  [{}]'.format(sig.replace('sig-', '', 1), short)
            note = self.IO_ANNOT.get(name)
            if note:
                short += '  <' + note + '>'
            lb = QtWidgets.QLabel(short)
            self._io_sig = getattr(self, '_io_sig', {}); self._io_sig[name] = sig
            lb.setStyleSheet(self._io_css(False))
            grid.addWidget(lb, i // cols, i % cols)
            self._io_pins[name] = [lb, None]      # widget, last value (None = not read yet)
        self._io_timer = QtCore.QTimer()
        self._io_timer.timeout.connect(self._io_tick)
        self._io_timer.start(200)
        self._log('IO tab: {} pins live'.format(len(self._io_pins)))

    def _io_css(self, val):
        if val:
            return ('font: 75 10pt "Courier 10 Pitch"; padding: 2px; '
                    'color: rgb(20,20,20); background: rgb(80,220,80);')
        return ('font: 75 10pt "Courier 10 Pitch"; padding: 2px; '
                'color: rgb(170,170,170); background: rgb(45,45,45);')

    def _io_tick(self):
        for name, rec in self._io_pins.items():
            try:
                v = bool(hal.get_value(name))
            except Exception:
                continue
            if v != rec[1]:
                first = rec[1] is None
                rec[1] = v
                try:
                    rec[0].setStyleSheet(self._io_css(v))
                except Exception:
                    pass
                if not first:
                    sig = getattr(self, '_io_sig', {}).get(name)
                    disp = sig.replace('sig-', '', 1) if sig else name.replace('hm2_7i97.0.', '')
                    lb = self._wg('io_lastchange')
                    if lb is not None:
                        try:
                            lb.setText('{}   {}  ->  {}'.format(
                                time.strftime('%H:%M:%S'), disp, 'TRUE' if v else 'FALSE'))
                        except Exception:
                            pass
                    self._log('IO      {} ({}) -> {}'.format(disp, name, 'TRUE' if v else 'FALSE'))

    # ---- SOLENOIDS: drive HAL directly, independent of MDI/mode/homing --------
    # ActionButton MDI buttons grey out unless machine-ON + all-homed + idle, which
    # makes them useless for checking wiring. These set a HAL pin OR'd into each
    # solenoid signal instead, so they work any time.
    def _wire_solenoids(self):
        self._sol = {'ts': 'sol-ts-force', 'blow': 'sol-blow-force', 'trel': 'sol-trel-force'}
        for pin in self._sol.values():
            try:
                self.hal.newpin(pin, hal.HAL_BIT, hal.HAL_OUT)
            except Exception as e:
                self._log('SOL pin {} failed: {}'.format(pin, e))
        pairs = [('btn_sol_ts_on','ts',True), ('btn_sol_ts_off','ts',False),
                 ('btn_sol_blow_on','blow',True), ('btn_sol_blow_off','blow',False),
                 ('btn_sol_trel_off','trel',False)]
        for bname, key, val in pairs:
            b = self._wg(bname)
            if b is None:
                self._log('SOL button {} NOT FOUND'.format(bname)); continue
            try:
                b.clicked.connect(lambda c=False, k=key, v=val: self._sol_set(k, v))
            except Exception as e:
                self._log('SOL connect {} failed: {}'.format(bname, e))

    def _sol_set(self, key, val):
        try:
            self.hal[self._sol[key]] = bool(val)
            self._log('SOLENOID {} -> {}'.format(key, 'ON' if val else 'OFF'))
        except Exception as e:
            self._log('SOLENOID {} failed: {}'.format(key, e))

    # ---- TOOL RELEASE: mandatory 5 s countdown before it fires ---------------
    # Dropping a tool is destructive, so the ON button always counts down 5 s and
    # can be cancelled by pressing again. (The release is ALSO e-stop gated in
    # ned5_iron.hal via toolrel.permit -- e-stop drops it mid-release.)
    def _wire_toolrel(self):
        self._trel_btn = self._wg('btn_sol_trel_on')
        if self._trel_btn is None:
            self._log('TOOL-RELEASE button not found'); return
        try:
            self._trel_btn.clicked.connect(self._toolrel_click)
        except Exception:
            return
        self._trel_left = 0
        self._trel_timer = QtCore.QTimer()
        self._trel_timer.timeout.connect(self._toolrel_tick)

    def _toolrel_click(self, *a):
        if self._trel_left > 0:                       # already counting -> cancel
            self._trel_timer.stop()
            self._trel_left = 0
            self._trel_btn.setText('ON (5s)')
            self._log('TOOL-RELEASE countdown CANCELLED')
            return
        self._trel_left = 5
        self._trel_btn.setText('CANCEL  5')
        self._log('TOOL-RELEASE countdown started (5 s)')
        self._trel_timer.start(1000)

    def _toolrel_tick(self):
        self._trel_left -= 1
        if self._trel_left > 0:
            self._trel_btn.setText('CANCEL  {}'.format(self._trel_left))
            return
        self._trel_timer.stop()
        self._trel_btn.setText('ON (5s)')
        self._sol_set('trel', True)
        self._log('TOOL-RELEASE FIRED (estop-gated via toolrel.permit)')

    # ---- MPG pendant jog (handwheel encoder.04 + one button input-00) --------
    # Wheel jogs the SELECTED axis through LinuxCNC's own jog (axis.N.jog-counts,
    # wired in postgui) -> accel/decel + soft limits for free. Button: TAP = next
    # axis (X Y Z A C); HOLD+wheel = speed (left=1x / mid=5x / right=10x); jog is
    # gated OFF during the hold so the wheel selects speed instead of moving.
    def _mpg_setup(self):
        self._mpg_axes = ['x', 'y', 'z', 'a', 'c']
        self._mpg_ax = 0
        # CPD = 4 counts/detent (tools/mpgjog.sh). Per-count = per-detent / 4.
        # LINEAR  X/Y/Z : 0.01 / 0.05 / 0.5 mm per detent (1 mm/detent was too fast)
        # ANGULAR A/C   : 0.01 / 0.05 / 0.1 deg per detent (1 deg/detent is way too coarse)
        self._mpg_scales_lin = [0.0025, 0.0125, 0.125]
        self._mpg_scales_ang = [0.0025, 0.0125, 0.025]
        self._mpg_spnames = ['1x', '5x', '10x']
        self._mpg_sp = 0
        self._mpg_ok = False
        try:
            for ax in self._mpg_axes:
                self.hal.newpin('jog-en-' + ax, hal.HAL_BIT, hal.HAL_OUT)
            self.hal.newpin('jog-scale-lin', hal.HAL_FLOAT, hal.HAL_OUT)
            self.hal.newpin('jog-scale-ang', hal.HAL_FLOAT, hal.HAL_OUT)
        except Exception as e:
            self._log('MPG pin-create failed: {}'.format(e))
            return
        self._mpg_btn_prev = False
        self._mpg_press_t = 0.0
        self._mpg_held = False
        self._mpg_wheel0 = 0
        self._mpg_last_tap = 0.0
        self._mpg_ok = True
        self._mpg_apply(False)
        self._mpg_timer = QtCore.QTimer()
        self._mpg_timer.timeout.connect(self._mpg_poll)
        self._mpg_timer.start(60)
        self._log('MPG jog ready: wheel=encoder.04, button=inmux.00.input-00, axes XYZAC')

    def _mpg_poll(self):
        if not getattr(self, '_mpg_ok', False):
            return
        try:
            raw = hal.get_value('hm2_7i97.0.inmux.00.input-00')       # TRUE=released, FALSE=pressed
            wheel = int(hal.get_value('hm2_7i97.0.encoder.04.count'))
        except Exception:
            return
        pressed = not bool(raw)
        now = time.time()
        if pressed and not self._mpg_btn_prev:
            self._mpg_press_t = now
            self._mpg_held = False
            self._mpg_wheel0 = wheel
        if pressed and not self._mpg_held and (now - self._mpg_press_t) >= 0.4:
            self._mpg_held = True
            self._mpg_wheel0 = wheel
        if pressed and self._mpg_held:
            d = wheel - self._mpg_wheel0
            newsp = 1
            if d <= -6:
                newsp = 0
            elif d >= 6:
                newsp = 2
            if newsp != self._mpg_sp:
                self._mpg_sp = newsp
                self._log('MPG speed -> {}'.format(self._mpg_spnames[newsp]))
        if (not pressed) and self._mpg_btn_prev and not self._mpg_held:
            n = len(self._mpg_axes)
            if (now - self._mpg_last_tap) < 0.45:
                # DOUBLE-CLICK = step BACKWARDS. The first tap already advanced +1, so
                # go back 2 to land one before where we started.
                self._mpg_ax = (self._mpg_ax - 2) % n
                self._log('MPG axis <- {} (double-click back)'.format(self._mpg_axes[self._mpg_ax].upper()))
            else:
                self._mpg_ax = (self._mpg_ax + 1) % n
                self._log('MPG axis -> {}'.format(self._mpg_axes[self._mpg_ax].upper()))
            self._mpg_last_tap = now
        self._mpg_btn_prev = pressed
        self._mpg_apply(pressed and self._mpg_held)

    def _mpg_apply(self, gate_off):
        try:
            for i, ax in enumerate(self._mpg_axes):
                self.hal['jog-en-' + ax] = bool((i == self._mpg_ax) and not gate_off)
            self.hal['jog-scale-lin'] = self._mpg_scales_lin[self._mpg_sp]
            self.hal['jog-scale-ang'] = self._mpg_scales_ang[self._mpg_sp]
        except Exception:
            pass
        try:
            ax = self._mpg_axes[self._mpg_ax].upper()
            # Show what ONE DETENT actually moves, in the units of the axis being jogged
            # (CPD = 4 counts/detent, tools/mpgjog.sh), not an abstract 1x/5x/10x.
            if ax in ('A', 'C'):
                sp = '{:.3f} deg'.format(self._mpg_scales_ang[self._mpg_sp] * 4)
            else:
                sp = '{:.3f} mm'.format(self._mpg_scales_lin[self._mpg_sp] * 4)
            big = self._wg('lbl_mpg_now')
            if big is not None:
                big.setText('MPG  {}  {}'.format(ax, sp))
            la = self._wg('lbl_mpg_axis'); ls = self._wg('lbl_mpg_speed')
            if la is not None: la.setText(self._mpg_axes[self._mpg_ax].upper())
            if ls is not None: ls.setText(self._mpg_spnames[self._mpg_sp])
        except Exception:
            pass

    # ---- MPG-blocked reason (MPG tab) -----------------------------------
    # WHY the wheel does nothing, shown on the MPG tab: machine state reasons
    # from task, direction-blocked reasons from the jogblock comp's latched
    # blocked-* pins (a detent toward a depressed limit switch was swallowed).
    MPG_BLOCK_NAMES = {
        ('x', 'neg'): 'X- blocked: X aft limit switch',
        ('x', 'pos'): 'X+ blocked: X fore limit switch',
        ('y', 'neg'): 'Y- blocked: Y starboard limit switch',
        ('y', 'pos'): 'Y+ blocked: Y port limit switch',
        ('z', 'neg'): 'Z- blocked: Z bottom limit switch',
        ('z', 'pos'): 'Z+ blocked: Z top limit switch',
    }

    def _wire_mpgreason(self):
        self._mr_last = None
        self._mr_timer = QtCore.QTimer()
        self._mr_timer.timeout.connect(self._mpg_reason_tick)
        self._mr_timer.start(250)

    def _mpg_reason_tick(self):
        lab = self._wg('lbl_mpg_reason')
        if lab is None:
            return
        txt = ''
        try:
            import linuxcnc
            if self._stat is None:
                return
            s = self._stat
            s.poll()
            if s.task_state in (linuxcnc.STATE_ESTOP, linuxcnc.STATE_ESTOP_RESET):
                txt = 'E-STOP -- release, then POWER'
            elif s.task_state != linuxcnc.STATE_ON:
                txt = 'MACHINE OFF -- press POWER'
            elif s.interp_state != linuxcnc.INTERP_IDLE:
                txt = 'PROGRAM RUNNING -- wheel disabled'
            elif s.task_mode == linuxcnc.MODE_AUTO:
                txt = 'returning to MANUAL...'
            elif s.feedrate < 0.0001:
                txt = 'FEED OVERRIDE 0% -- wheel disabled'
            else:
                for (ax, d) in self.MPG_BLOCK_NAMES:
                    try:
                        if hal.get_value('jogblock.{}.blocked-{}'.format(ax, d)):
                            txt = self.MPG_BLOCK_NAMES[(ax, d)]
                            break
                    except Exception:
                        pass
        except Exception:
            return
        if txt == self._mr_last:
            return
        self._mr_last = txt
        base = 'font: 75 13pt "Courier 10 Pitch"; background: rgb(40,40,40); padding: 6px;'
        if txt:
            lab.setText(txt)
            lab.setStyleSheet('color: rgb(255,80,80); ' + base)
            self._log('MPG blocked: ' + txt)
        else:
            lab.setText('MPG OK')
            lab.setStyleSheet('color: rgb(80,220,80); ' + base)

    # ---- required boilerplate -------------------------------------------
    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        setattr(self, item, value)


def get_handlers(halcomp, widgets, paths):
    return [HandlerClass(halcomp, widgets, paths)]
