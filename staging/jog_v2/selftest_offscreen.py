"""Offscreen selftest for the JOG & PRESETS v2 panel (staging/jog_v2).

Run:  QT_QPA_PLATFORM=offscreen python3 selftest_offscreen.py

SAFE BY CONSTRUCTION: a FAKE linuxcnc module is installed in sys.modules
BEFORE the panel module is imported, so nothing here can attach NML or
touch the live session. Exercises: wiring count, speed readout, GO
enable-gating, Enter->GO ABS, GO REL delta->absolute conversion, soft-limit
reject (incl. work->machine offset math) + field flash, accept path (mode
confirm + single G90 G1 line), Z +10 zlift, status strip idle/moving
lockout, STOP->abort.

Fixture frame (machine coords):
  limits  X[-400..400] Y[-1787..1] Z[-620..1] A[-115..115] C[-315..315]
  offsets g5x: X+100  Z-30  A+5   (g92/tool zero)
  actual  X150 Y20 Z-80 A10 C40 -> work X50 Y20 Z-50 A5 C40
"""
import os
import sys
import types

# ---- fake linuxcnc: MUST be installed before the panel module imports it --
fake = types.ModuleType('linuxcnc')
fake.STATE_ON = 4
fake.STATE_OFF = 3
fake.INTERP_IDLE = 1
fake.INTERP_EXEC = 3
fake.MODE_MDI = 3
fake.MODE_MANUAL = 1
fake.MODE_AUTO = 2

CALLS = []


class FakeStat(object):
    def __init__(self):
        self.task_state = fake.STATE_ON
        self.task_mode = fake.MODE_MDI      # mode-confirm loop exits at once
        self.interp_state = fake.INTERP_IDLE
        self.inpos = True
        self.current_vel = 0.0
        self.homed = [1, 1, 1, 1, 1, 1] + [0] * 10
        self.joint = [{'homing': 0} for _ in range(9)]
        self.actual_position = (150.0, 20.0, -80.0, 10.0, 0.0, 40.0, 0, 0, 0)
        self.g5x_offset = (100.0, 0.0, -30.0, 5.0, 0.0, 0.0, 0, 0, 0)
        self.g92_offset = (0.0,) * 9
        self.tool_offset = (0.0,) * 9

    def poll(self):
        pass


class FakeCommand(object):
    def error_msg(self, m):
        CALLS.append(('error_msg', m))

    def mode(self, m):
        CALLS.append(('mode', m))

    def wait_complete(self, *a):
        CALLS.append(('wait_complete',))

    def mdi(self, line):
        CALLS.append(('mdi', line))

    def abort(self):
        CALLS.append(('abort',))


class FakeIni(object):
    LIMS = {'AXIS_X': (-400.0, 400.0), 'AXIS_Y': (-1787.0, 1.0),
            'AXIS_Z': (-620.0, 1.0), 'AXIS_A': (-115.0, 115.0),
            'AXIS_C': (-315.0, 315.0)}

    def __init__(self, path):
        pass

    def find(self, sec, key):
        lo, hi = self.LIMS[sec]
        return str(lo) if key == 'MIN_LIMIT' else str(hi)


fake.stat = FakeStat
fake.command = FakeCommand
fake.ini = FakeIni
sys.modules['linuxcnc'] = fake
os.environ['INI_FILE_NAME'] = '/fake/ned5_pb.ini'

sys.path.insert(0, '/home/brains/qt_pb/qtpyvcp/src')

import importlib.util
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'ned_controls_v2_test', os.path.join(here, 'ned_controls.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)          # module import only -- NO UserTab()

from qtpyvcp.utilities.runtime_ui_loader import load_ui


class Host(QWidget):
    pass


# borrow every _jog/_JOG member so the REAL methods run against the fake
for name in dir(m.UserTab):
    if name.startswith('_jog') or name.startswith('_JOG'):
        setattr(Host, name, getattr(m.UserTab, name))

h = Host()
h.ui = load_ui(os.path.join(here, 'ned_controls.ui'), h)
h._jog_speed = 'medium'
h._jog_wire()

ok = []


def check(name, cond):
    ok.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name)


def find(n):
    return h.findChild(QWidget, n)


# 1. limits table + readout per speed
check('limits loaded from INI', h._jog_limits == {
    'x': (-400.0, 400.0), 'y': (-1787.0, 1.0), 'z': (-620.0, 1.0),
    'a': (-115.0, 115.0), 'c': (-315.0, 315.0)})
check('readout medium', find('jp_feed_readout').text()
      == 'F1200 mm/min · 60 deg/min')
find('jp_slow').click()
check('readout slow', find('jp_feed_readout').text()
      == 'F200 mm/min · 15 deg/min')
find('jp_fast').click()
check('readout fast', find('jp_feed_readout').text()
      == 'F4000 mm/min · 180 deg/min')
find('jp_medium').click()

# 2. GO gating on field parse
check('GOs start disabled', not find('jp_go_abs').isEnabled()
      and not find('jp_go_rel').isEnabled())
find('jp_in_x').setText('10')
check('GOs enable on parse', find('jp_go_abs').isEnabled()
      and find('jp_go_rel').isEnabled())
find('jp_in_x').setText('abc')
check('GOs disable on garbage-only', not find('jp_go_abs').isEnabled())
find('jp_in_x').setText('10')

# 3. GO ABS accept path: X work 10 -> machine 110, inside [-400..400]
CALLS[:] = []
find('jp_go_abs').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('GO ABS single mdi', len(mdis) == 1)
check('GO ABS line', bool(mdis)
      and mdis[0][1] == 'G90 G1 X10.0000 F1200.0')
check('mode confirmed before mdi', bool(mdis)
      and ('mode', fake.MODE_MDI) in CALLS
      and CALLS.index(('mode', fake.MODE_MDI)) < CALLS.index(mdis[0]))
check('fields retained after move', find('jp_in_x').text() == '10')

# 4. GO REL: work X = actual 150 - g5x 100 = 50; +10 -> one G90 X60 line
CALLS[:] = []
find('jp_go_rel').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('GO REL delta->absolute (50+10=60, one G90 line, no G91)',
      bool(mdis) and mdis[0][1] == 'G90 G1 X60.0000 F1200.0')

# 5. Enter in a field fires GO ABS
CALLS[:] = []
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
QTest.keyClick(find('jp_in_x'), Qt.Key_Return)
mdis = [c for c in CALLS if c[0] == 'mdi']
check('Enter fires GO ABS', bool(mdis)
      and mdis[0][1] == 'G90 G1 X10.0000 F1200.0')

# 6a. soft-limit reject, plain (no offset): Y -2000 < min -1787
find('jp_in_x').clear()
find('jp_in_y').setText('-2000')
CALLS[:] = []
find('jp_go_abs').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
errs = [c for c in CALLS if c[0] == 'error_msg']
check('Y reject: NO mdi issued', not mdis)
check('Y reject: loud toast', bool(errs)
      and 'REJECTED' in errs[0][1] and 'Y' in errs[0][1])
check('Y reject: field flashed red',
      'rgb(220,80,80)' in find('jp_in_y').styleSheet())

# 6b. soft-limit reject via OFFSET math: X work 350 alone looks fine, but
# machine = 350 + 100 = 450 > 400 -> must be rejected
find('jp_in_y').clear()
find('jp_in_x').setText('350')
CALLS[:] = []
find('jp_go_abs').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('X reject through work->machine offset (350+100=450 > 400)',
      not mdis)
find('jp_in_x').setText('10')

# 7. presets: A0 C0 pure rotary -> angular F; XY 0 -> linear F, immediate
CALLS[:] = []
find('jp_p_a0c0').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('A0 C0 angular feed', bool(mdis)
      and mdis[0][1] == 'G90 G1 A0.0000 C0.0000 F60.0')
CALLS[:] = []
find('jp_p_xy0').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('XY 0 preset immediate', bool(mdis)
      and mdis[0][1] == 'G90 G1 X0.0000 Y0.0000 F1200.0')

# 8. Z +10 zlift: work Z = -80 - (-30) = -50 -> absolute target Z-40
CALLS[:] = []
find('jp_p_zp10').click()
mdis = [c for c in CALLS if c[0] == 'mdi']
check('Z +10 incremental from current work Z (one absolute line)',
      bool(mdis) and mdis[0][1] == 'G90 G1 Z-40.0000 F1200.0')

# 9. status strip: idle -> moving lockout -> STOP -> idle recovery
h._jog_status_tick()
check('idle strip', find('jp_status_text').text() == 'IDLE — ready'
      and not find('jp_stop').isEnabled()
      and find('jp_p_xy0').isEnabled())
h._jog_stat_nml.interp_state = fake.INTERP_EXEC
h._jog_stat_nml.current_vel = 33.3
h._jog_status_tick()
check('moving strip text', find('jp_status_text').text()
      == 'MOVING — 33.3 mm/s')
check('moving lockout', not find('jp_p_xy0').isEnabled()
      and not find('jp_go_abs').isEnabled()
      and find('jp_stop').isEnabled())
CALLS[:] = []
find('jp_stop').click()
check('STOP -> abort', ('abort',) in CALLS)
h._jog_stat_nml.interp_state = fake.INTERP_IDLE
h._jog_stat_nml.current_vel = 0.0
h._jog_status_tick()
check('recover to idle re-enables', find('jp_p_xy0').isEnabled()
      and find('jp_go_abs').isEnabled()
      and not find('jp_stop').isEnabled())

n_fail = sum(1 for _, c in ok if not c)
print('---')
print('%d checks, %d failed' % (len(ok), n_fail))
sys.exit(1 if n_fail else 0)
