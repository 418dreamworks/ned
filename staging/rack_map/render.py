"""Offscreen render + geometry audit of the RACK MAP tab at 1660x760.

Run:  QT_QPA_PLATFORM=offscreen python3 render.py

Renders rack_map.ui (wired by the real rack_map.py against a FAKE linuxcnc
and a fixture var file -- zero NML) at the PB user-tab page size 1660x760
to render.png, then walks widget geometries programmatically:
  1. BOUNDS  -- every visible rm_* widget inside 0,0,1660,760
  2. OVERLAP -- no two visible leaf rm_* widgets intersect
  3. TEXTFIT -- label/button text fits its widget (width and height)
Exit 0 only if all checks pass.
"""
import os
import sys
import tempfile
import types

fake = types.ModuleType('linuxcnc')
fake.STATE_ON = 4
fake.STATE_OFF = 3
fake.INTERP_IDLE = 1
fake.INTERP_EXEC = 3
fake.MODE_MDI = 3
fake.MODE_MANUAL = 1
fake.MODE_AUTO = 2

TMP = tempfile.mkdtemp(prefix='rack_map_render_')
VAR = os.path.join(TMP, 'ned5_pb.var')


class SharedStat(object):
    def __init__(self):
        self.task_state = fake.STATE_ON
        self.task_mode = fake.MODE_MDI
        self.interp_state = fake.INTERP_IDLE
        self.inpos = True
        self.current_vel = 0.0
        self.homed = [1] * 16
        self.joint = [{'homing': 0} for _ in range(9)]

    def poll(self):
        pass


class SharedCommand(object):
    def error_msg(self, m):
        pass

    def mode(self, m):
        pass

    def wait_complete(self, *a):
        pass

    def mdi(self, line):
        pass


class FakeIni(object):
    def __init__(self, path):
        pass

    def find(self, sec, key):
        if (sec, key) == ('RS274NGC', 'PARAMETER_FILE'):
            return 'ned5_pb.var'
        return None


STAT = SharedStat()
CMD = SharedCommand()
fake.stat = lambda: STAT
fake.command = lambda: CMD
fake.ini = FakeIni
sys.modules['linuxcnc'] = fake
os.environ['INI_FILE_NAME'] = os.path.join(TMP, 'ned5_pb.ini')

# representative fixture: mixed taught/untaught, X and Y entries, wide values
rows = {3991: 15.0}
for n in (1, 2, 3, 4, 5):                       # taught, X entry
    b = 4100 + 4 * n
    rows[b] = -56.0 - 0.123 * n
    rows[b + 1] = -91.5 - 92.0 * n
    rows[b + 2] = -100.0
    rows[b + 3] = 6.0
    rows[4000 + n] = float(n)
for n in (6, 7):                                # taught, Y entry
    b = 4100 + 4 * n
    rows[b] = -1234.567
    rows[b + 1] = -1500.0 - n
    rows[b + 2] = -1420.001
    rows[b + 3] = 7.0
b = 4100 + 4 * 8                                # seat-only pocket 8
rows[b] = -333.333
rows[b + 1] = -444.444
rows[b + 3] = 2.0
rows[4015] = 15.0                               # sawblade lives in fork 15
with open(VAR, 'w') as f:
    for k in sorted(rows):
        f.write('%d\t%f\n' % (k, rows[k]))

sys.path.insert(0, '/home/brains/qt_pb/qtpyvcp/src')

import importlib.util
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QSpinBox,
                               QWidget)

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'rack_map_render', os.path.join(here, 'rack_map.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

W, H = 1660, 760
h = m.UserTab()
h.setFixedSize(W, H)
h.show()
app.processEvents()
app.processEvents()

png = os.path.join(here, 'render.png')
h.grab().save(png)
print('render saved: %s (%dx%d)' % (png, W, H))

fails = []


def fail(msg):
    fails.append(msg)
    print('FAIL ' + msg)


widgets = []
for w in h.findChildren(QWidget):
    n = w.objectName()
    if not n or not n.startswith('rm_') or not w.isVisible():
        continue
    r = QRect(w.mapTo(h, w.rect().topLeft()), w.size())
    widgets.append((n, w, r))
print('%d visible rm_* widgets' % len(widgets))

frame = QRect(0, 0, W, H)
for n, w, r in widgets:
    if not frame.contains(r):
        fail('BOUNDS %s %s exceeds 0,0,%dx%d' % (n, r, W, H))

names = {id(w) for n, w, r in widgets}
leaves = [(n, w, r) for n, w, r in widgets
          if not any(id(c) in names for c in w.findChildren(QWidget))]
for i in range(len(leaves)):
    for j in range(i + 1, len(leaves)):
        n1, w1, r1 = leaves[i]
        n2, w2, r2 = leaves[j]
        if r1.intersects(r2):
            fail('OVERLAP %s %s <-> %s %s' % (n1, r1, n2, r2))

for n, w, r in leaves:
    if isinstance(w, QSpinBox):
        continue
    if isinstance(w, (QLabel, QPushButton)):
        text = w.text()
        wrap = isinstance(w, QLabel) and w.wordWrap()
        pad = 10 if isinstance(w, QPushButton) else 2
    else:
        continue
    if not text:
        continue
    w.ensurePolished()
    fm = w.fontMetrics()
    lines = text.split('\n')
    if not wrap:
        widest = max(fm.horizontalAdvance(t) for t in lines)
        if widest > r.width() - pad:
            fail('TEXTFIT %s widest line %dpx > %dpx avail (%r)'
                 % (n, widest, r.width() - pad, text))
    need_h = fm.lineSpacing() * len(lines)
    if need_h > r.height():
        fail('TEXTFIT %s needs %dpx height > %dpx (%r)'
             % (n, need_h, r.height(), text))

print('---')
if fails:
    print('%d GEOMETRY FAILURES' % len(fails))
    sys.exit(1)
print('geometry audit PASS: all bounds/overlap/textfit checks clean at %dx%d'
      % (W, H))
sys.exit(0)
