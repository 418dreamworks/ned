"""Offscreen selftest for the RACK MAP user tab (staging/rack_map).

Run:  QT_QPA_PLATFORM=offscreen python3 selftest_offscreen.py

SAFE BY CONSTRUCTION: a FAKE linuxcnc module is installed in sys.modules
BEFORE rack_map.py is imported -- zero NML, nothing launched, nothing
touched outside a temp dir. UserTab() is instantiated directly (it owns no
HAL pins and pokes no core window widgets, unlike ned_controls).

Fixture var file: pocket 1 fully taught (X entry), pocket 2 seat-only,
pocket 3 untaught with tool 7 assigned, #3991 = 5.
"""
import os
import sys
import tempfile
import time
import types

# ---- fake linuxcnc: MUST be installed before rack_map imports it ---------
fake = types.ModuleType('linuxcnc')
fake.STATE_ON = 4
fake.STATE_OFF = 3
fake.INTERP_IDLE = 1
fake.INTERP_EXEC = 3
fake.MODE_MDI = 3
fake.MODE_MANUAL = 1
fake.MODE_AUTO = 2

CALLS = []
TMP = tempfile.mkdtemp(prefix='rack_map_test_')
VAR = os.path.join(TMP, 'ned5_pb.var')


class SharedStat(object):
    def __init__(self):
        self.task_state = fake.STATE_ON
        self.task_mode = fake.MODE_MDI       # mode-confirm loop exits at once
        self.interp_state = fake.INTERP_IDLE
        self.inpos = True
        self.current_vel = 0.0
        self.homed = [1] * 16
        self.joint = [{'homing': 0} for _ in range(9)]

    def poll(self):
        pass


class SharedCommand(object):
    def error_msg(self, m):
        CALLS.append(('error_msg', m))

    def mode(self, m):
        CALLS.append(('mode', m))

    def wait_complete(self, *a):
        CALLS.append(('wait_complete',))

    def mdi(self, line):
        CALLS.append(('mdi', line))


STAT = SharedStat()
CMD = SharedCommand()


class FakeIni(object):
    def __init__(self, path):
        pass

    def find(self, sec, key):
        if (sec, key) == ('RS274NGC', 'PARAMETER_FILE'):
            return 'ned5_pb.var'   # relative -> resolved against INI dir
        return None


fake.stat = lambda: STAT
fake.command = lambda: CMD
fake.ini = FakeIni
sys.modules['linuxcnc'] = fake
os.environ['INI_FILE_NAME'] = os.path.join(TMP, 'ned5_pb.ini')

VAR_LINES = {
    3991: 5.0,
    4001: 1.0, 4003: 7.0,
    4104: -56.0, 4105: -91.5, 4106: -100.0, 4107: 6.0,   # pocket 1: full, X
    4108: -60.0, 4109: -183.5, 4111: 2.0,                # pocket 2: seat only
}


def write_var(d):
    with open(VAR, 'w') as f:
        for k in sorted(d):
            f.write('%d\t%f\n' % (k, d[k]))


write_var(VAR_LINES)

sys.path.insert(0, '/home/brains/qt_pb/qtpyvcp/src')

import importlib.util
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'rack_map_test', os.path.join(here, 'rack_map.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

h = m.UserTab()

ok = []


def check(name, cond):
    ok.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name)


def find(n):
    return h.findChild(QWidget, n)


def mdis():
    return [c[1] for c in CALLS if c[0] == 'mdi']


# 1. wiring: every declared widget found
check('all widgets wired (no missing)', h._missing == [])

# 2. table paint from the var file
check('pocket 1 seat X', find('rm_seatx_1').text() == '-56.000')
check('pocket 1 seat Y', find('rm_seaty_1').text() == '-91.500')
check('pocket 1 clearance X-entry', find('rm_clr_1').text() == 'X -100.000')
check('pocket 2 seat shown, clearance untaught',
      find('rm_seatx_2').text() == '-60.000'
      and find('rm_clr_2').text() == '—')
check('pocket 3 fully untaught rows show dashes',
      find('rm_seatx_3').text() == '—' and find('rm_clr_3').text() == '—')
check('tool spinboxes from #[4000+N]',
      find('rm_tool_1').value() == 1 and find('rm_tool_3').value() == 7
      and find('rm_tool_2').value() == 0)
check('SPINDLE HOLDS from #3991', find('rm_spindle_holds').value() == 5)

# 3. TEACH SEAT pocket 4: mode confirmed before ONE rack_teach mdi
CALLS[:] = []
find('rm_teachs_4').click()
check('teach seat mdi', mdis() == ['o<rack_teach> call [4] [1]'])
check('mode confirmed before teach mdi',
      ('mode', fake.MODE_MDI) in CALLS
      and CALLS.index(('mode', fake.MODE_MDI))
      < CALLS.index(('mdi', 'o<rack_teach> call [4] [1]')))

# 4. TEACH CLEAR pocket 4
CALLS[:] = []
find('rm_teachc_4').click()
check('teach clear mdi', mdis() == ['o<rack_teach> call [4] [2]'])

# 5. tool commit: pocket 2 -> tool 9 => #4002=9
CALLS[:] = []
find('rm_tool_2').setValue(9)
find('rm_tool_2').editingFinished.emit()
check('tool commit mdi', mdis() == ['#4002=9'])

# 6. duplicate tool REFUSED (tool 7 lives in pocket 3): no mdi, loud toast,
#    spinbox reverted
CALLS[:] = []
find('rm_tool_5').setValue(7)
find('rm_tool_5').editingFinished.emit()
errs = [c for c in CALLS if c[0] == 'error_msg']
check('duplicate tool: NO mdi', mdis() == [])
check('duplicate tool: loud toast', bool(errs) and 'REFUSED' in errs[0][1])
check('duplicate tool: spinbox reverted', find('rm_tool_5').value() == 0)

# 7. SPINDLE HOLDS commit -> M61 Qn then #3991=n, in order
CALLS[:] = []
find('rm_spindle_holds').setValue(3)
find('rm_spindle_holds').editingFinished.emit()
check('spindle holds mdi pair', mdis() == ['M61 Q3', '#3991=3'])

# 8. guard refusal when machine OFF: no mdi, loud toast
STAT.task_state = fake.STATE_OFF
CALLS[:] = []
find('rm_teachs_1').click()
check('machine-off guard: NO mdi', mdis() == [])
check('machine-off guard: loud toast',
      any(c[0] == 'error_msg' and 'not ON' in c[1] for c in CALLS))
STAT.task_state = fake.STATE_ON

# 9. var file change -> table refresh (mtime-gated poll)
VAR_LINES[4106] = -120.0
write_var(VAR_LINES)
os.utime(VAR, (time.time() + 5, time.time() + 5))
h._poll_var()
check('var refresh repaints clearance', find('rm_clr_1').text() == 'X -120.000')

n_fail = sum(1 for _, c in ok if not c)
print('---')
print('%d checks, %d failed' % (len(ok), n_fail))
sys.exit(1 if n_fail else 0)
