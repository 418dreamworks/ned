"""Exercise the REAL do_inplace() logic. Definitions only -- the driver loop
(from `brain = Brain()` at line 1620) is cut, and GUI_LOG is redirected so
nothing touches the machine's gui.md. Every line of do_inplace that runs
here is the same text the machine runs."""
import sys, types

REAL = '/home/brains/Documents/ned/tools/live/ned_brain.py'
src = open(REAL).read()
cut = src.index('\nbrain = Brain()')
src = src[:cut]
src = src.replace("GUI_LOG = os.path.join(NED, 'gui.md')",
                  "GUI_LOG = '/tmp/claude-1000/-home-brains-Documents/"
                  "aac9ddb0-28ff-4868-8f14-536ddbdf1f75/scratchpad/harness_gui.md'")
assert 'harness_gui.md' in src and 'def do_inplace' in src

hal = types.ModuleType('hal')
hal.HAL_BIT='bit'; hal.HAL_S32='s32'; hal.HAL_U32='u32'; hal.HAL_FLOAT='float'
hal.HAL_IN='in'; hal.HAL_OUT='out'
class _Comp(dict):
    def newpin(self, n, t, d): self[n] = 0
    def ready(self): pass
hal.component = lambda name: _Comp()
sys.modules['hal'] = hal

lc = types.ModuleType('linuxcnc')
lc.MODE_MANUAL=1; lc.MODE_AUTO=2; lc.MODE_MDI=3
lc.STATE_ESTOP=1; lc.STATE_ESTOP_RESET=2; lc.STATE_OFF=3; lc.STATE_ON=4
lc.INTERP_IDLE=1
class _Stat(object):
    def __init__(s):
        s.homed=[1,1,1,1,0,0]; s.task_state=4; s.task_mode=1; s.interp_state=1
        s.tool_in_spindle=2; s.estop=0; s.tool_table=()
        s.joint=[{'homing':0,'min_position_limit':-9e9,'max_position_limit':9e9,
                  'output':0.0,'input':0.0} for _ in range(9)]
    def poll(s): pass
CALLS=[]
class _Cmd(object):
    def __getattr__(s, n):
        def f(*a, **k): CALLS.append((n,)+a)
        return f
lc.stat=_Stat; lc.command=_Cmd
lc.ini=lambda p: types.SimpleNamespace(find=lambda a,b: None)
sys.modules['linuxcnc'] = lc

NS = {'__name__': 'nb_harness'}
exec(compile(src, REAL, 'exec'), NS)

LOGS=[]
NS['log'] = lambda m: LOGS.append(m)
# no real halcmd: record the setp/getp shell-outs instead of running them
SHELL=[]
NS['os'] = types.SimpleNamespace(**{k: getattr(__import__('os'), k)
                                    for k in ('path','environ')})
NS['os'].system = lambda c: (SHELL.append(c), 0)[1]
class _R:  # halcmd getp read-back always agrees, so the gate passes
    returncode=0
    def __init__(s, out): s.stdout = out
def _run(args, **k):
    SHELL.append(' '.join(args))
    if 'getp' in args:
        pin = args[-1]
        return _R(str(WANT.get(pin, '0')))
    return _R('')
NS['subprocess'] = types.SimpleNamespace(run=_run)
WANT = {}
Brain = NS['Brain']

def fresh(homed, hr, pending=True, armed=True, refs=(), verify=()):
    b = Brain.__new__(Brain)
    b.stat=_Stat(); b.stat.homed=list(homed); b.cmd=_Cmd()
    b.hr_deg=dict(hr); b.inplace_pending=pending; b.read_armed=armed
    b.pending_ref=set(refs); b.verify_want=set(verify)
    b.pin_wipe=set(); b.declare_snap={}; b.hr_step=0
    del LOGS[:]; del CALLS[:]; del SHELL[:]; WANT.clear()
    for jn, ax in ((4,'a'),(5,'c')):
        if hr.get(ax) is not None:
            WANT['ini.%d.home' % jn] = '%.4f' % hr[ax]
            WANT['ini.%d.home_offset' % jn] = '%.4f' % hr[ax]
    return b

def show(t, b):
    print('\n### %s' % t)
    for l in LOGS: print('   log :', l)
    print('   cmds:', [c[0] for c in CALLS] or 'none')
    print('   pending after:', b.inplace_pending)
