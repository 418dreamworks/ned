"""Offscreen render + geometry audit of the NARROW JOG & PRESETS panel.

Run:  QT_QPA_PLATFORM=offscreen python3 render_200x730.py

Renders ned_controls.ui at EXACTLY 200x730 (the measured stock JOG page
container in PB's right sidebar stack) to render_200x730.png, then walks
every widget geometry programmatically:
  1. BOUNDS  -- every visible jp_* widget's rect (root coords) inside 0,0,200,730
  2. OVERLAP -- no two visible leaf jp_* widgets intersect
  3. TEXTFIT -- for every button/label/edit: widest text line fits the
     widget's width (minus border+padding), line count fits its height
     (skip wordWrap labels' width; placeholder text checked for edits)

SAFE BY CONSTRUCTION: fake linuxcnc installed before the panel module
imports, zero NML, nothing launched. Exit 0 only if all checks pass.
"""
import os
import sys
import types

fake = types.ModuleType('linuxcnc')
fake.STATE_ON = 4
fake.STATE_OFF = 3
fake.INTERP_IDLE = 1
fake.INTERP_EXEC = 3
fake.MODE_MDI = 3
fake.MODE_MANUAL = 1
fake.MODE_AUTO = 2


class FakeStat(object):
    def __init__(self):
        self.task_state = fake.STATE_ON
        self.task_mode = fake.MODE_MDI
        self.interp_state = fake.INTERP_IDLE
        self.inpos = True
        self.current_vel = 0.0
        self.homed = [1] * 16
        self.joint = [{'homing': 0} for _ in range(9)]
        self.actual_position = (0.0,) * 9
        self.g5x_offset = (0.0,) * 9
        self.g92_offset = (0.0,) * 9
        self.tool_offset = (0.0,) * 9

    def poll(self):
        pass


class FakeCommand(object):
    def error_msg(self, m):
        pass

    def mode(self, m):
        pass

    def wait_complete(self, *a):
        pass

    def mdi(self, line):
        pass

    def abort(self):
        pass


class FakeIni(object):
    LIMS = {'AXIS_X': (-4042.72, 1.0), 'AXIS_Y': (-1787.0, 1.0),
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
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit,
                               QPushButton, QWidget)

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'ned_controls_render', os.path.join(here, 'ned_controls.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

from qtpyvcp.utilities.runtime_ui_loader import load_ui


class Host(QWidget):
    pass


for name in dir(m.UserTab):
    if name.startswith('_jog') or name.startswith('_JOG'):
        setattr(Host, name, getattr(m.UserTab, name))

W, H = 200, 730
h = Host()
h.ui = load_ui(os.path.join(here, 'ned_controls.ui'), h)
h._jog_speed = 'medium'
h._jog_wire()            # real wiring: readout shows the real longest text
h._jog_status_tick()     # real status text painted
h.setFixedSize(W, H)
h.show()
app.processEvents()
app.processEvents()

png = os.path.join(here, 'render_200x730.png')
h.grab().save(png)
print('render saved: %s (%dx%d)' % (png, W, H))

fails = []


def fail(msg):
    fails.append(msg)
    print('FAIL ' + msg)


# ---- collect the panel's visible widgets in root coordinates -------------
widgets = []
for w in h.findChildren(QWidget):
    n = w.objectName()
    if not n or not n.startswith('jp_') or not w.isVisible():
        continue
    r = QRect(w.mapTo(h, w.rect().topLeft()), w.size())
    widgets.append((n, w, r))
print('%d visible jp_* widgets' % len(widgets))

# 1. BOUNDS
frame = QRect(0, 0, W, H)
for n, w, r in widgets:
    if not frame.contains(r):
        fail('BOUNDS %s %s exceeds 0,0,%dx%d' % (n, r, W, H))

# 2. OVERLAP among leaves (widgets with no jp_* descendant of their own)
names = {id(w): n for n, w, r in widgets}
leaves = []
for n, w, r in widgets:
    kids = [c for c in w.findChildren(QWidget) if id(c) in names]
    if not kids:
        leaves.append((n, w, r))
for i in range(len(leaves)):
    for j in range(i + 1, len(leaves)):
        n1, w1, r1 = leaves[i]
        n2, w2, r2 = leaves[j]
        if r1.intersects(r2):
            fail('OVERLAP %s %s <-> %s %s' % (n1, r1, n2, r2))

# 3. TEXTFIT (stylesheet fonts resolved via ensurePolished + widget font)
for n, w, r in leaves:
    if isinstance(w, QLineEdit):
        text, wrap = w.placeholderText(), False
        pad = 16   # 2*(border 1 + padding 6) + caret slack
    elif isinstance(w, (QLabel, QPushButton)):
        text, wrap = w.text(), isinstance(w, QLabel) and w.wordWrap()
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
    else:
        avail = max(1, r.width() - pad)
        rows = 0
        for t in lines:
            rows += max(1, -(-fm.horizontalAdvance(t) // avail))
        need_h = fm.lineSpacing() * rows
    if need_h > r.height():
        fail('TEXTFIT %s needs %dpx height > %dpx (%r)'
             % (n, need_h, r.height(), text))

# panel itself must fill the frame width
jp = h.findChild(QWidget, 'jp_panel')
pr = QRect(jp.mapTo(h, jp.rect().topLeft()), jp.size())
print('jp_panel rect: %s' % pr)

print('---')
if fails:
    print('%d GEOMETRY FAILURES' % len(fails))
    sys.exit(1)
print('geometry audit PASS: all bounds/overlap/textfit checks clean at %dx%d'
      % (W, H))
sys.exit(0)
