#!/usr/bin/env python3
"""gen_params.py -- ned MASTER parameter file system (task #16).

ONE authoritative file, configs/params/MASTER.params, holds every value
that used to live scattered across configs/params/*.inc. This generator
emits those .inc files from it (LinuxCNC reads the .inc via #INCLUDE
exactly as before -- nothing at runtime changes).

Format ("TOML-ish", COMMENT-PRESERVING -- tomllib drops comments, so a
20-line parser keeps them):
    [section.name]          one per generated .inc file
    # comments and blank lines are preserved verbatim into the .inc
    KEY = VALUE
    KEY = @DERIVED_NAME     substituted from [drivetrain] formulas below

Derived values (mirror tools/live/ned_params.sh -- the bench-script
source of the same primitives; --check cross-checks the two):
    SCALE_A   = DRIVE_PPR * GEAR_A / 360
    SCALE_C   = DRIVE_PPR * GEAR_C / 360
    SCALE_ROT = ROT_FULLSTEPS * ROT_MICROSTEP * ROT_GEAR / 360
    MAX_VEL_LIN, MAXV_DISPLAY used verbatim where referenced.

EXCLUDED from generation: head_zero.inc -- ned_brain WRITES it at head
zero capture; a generated copy would clobber machine state.

Commands:
    gen_params.py extract   bootstrap MASTER.params FROM the current .inc
                            files (one-time; refuses if MASTER exists)
    gen_params.py check     regenerate to temp, byte-compare each .inc,
                            cross-check drivetrain vs ned_params.sh
    gen_params.py write     regenerate the .inc files IN PLACE (only
                            after check passes; prints a per-file diffstat)
"""
import os
import re
import sys
import subprocess

NED = '/home/brains/Documents/ned'
PDIR = os.path.join(NED, 'configs/params')
MASTER = os.path.join(PDIR, 'MASTER.params')
NED_PARAMS_SH = os.path.join(NED, 'tools/live/ned_params.sh')

# section name <-> .inc file map. head_zero.inc deliberately absent.
FILES = [
    ('head_gear', 'head_gear.inc'),
    ('emcmot', 'emcmot.inc'),
    ('traj', 'traj_common.inc'),
    ('spindle0', 'spindle_0.inc'),
    ('display', 'display_common.inc'),
    ('rs274ngc', 'rs274ngc.inc'),
    ('puck', 'puck.inc'),
    ('axis.x', 'axis_x.inc'),
    ('axis.y', 'axis_y.inc'),
    ('axis.z', 'axis_z.inc'),
    ('axis.a', 'axis_a.inc'),
    ('axis.c', 'axis_c.inc'),
    ('joint.x1', 'joint_x1.inc'),
    ('joint.x2', 'joint_x2.inc'),
    ('joint.y', 'joint_y.inc'),
    ('joint.z', 'joint_z.inc'),
    ('joint.a', 'joint_a.inc'),
    ('joint.c', 'joint_c.inc'),
]

GEN_HEADER = ('# GENERATED from configs/params/MASTER.params by '
              'tools/live/gen_params.py -- DO NOT HAND-EDIT.\n'
              '# Edit MASTER.params, then run: gen_params.py check && '
              'gen_params.py write\n')


def parse_master(path):
    """-> (drivetrain: dict, sections: {name: [lines]}), comments intact."""
    drivetrain = {}
    sections = {}
    cur = None
    with open(path) as f:
        for raw in f:
            line = raw.rstrip('\n')
            m = re.match(r'^\[([A-Za-z0-9_.]+)\]\s*$', line)
            if m:
                cur = m.group(1)
                sections.setdefault(cur, [])
                continue
            if cur is None:
                continue          # preamble comments stay in MASTER only
            sections[cur].append(line)
    for ln in sections.get('drivetrain', []):
        m = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*([^#;]+?)\s*(?:[#;].*)?$', ln)
        if m:
            drivetrain[m.group(1)] = m.group(2).strip()
    return drivetrain, sections


def derived(dt):
    f = lambda k: float(dt[k])
    return {
        'SCALE_A': '%.4f' % (f('DRIVE_PPR') * f('GEAR_A') / 360.0),
        'SCALE_C': '%.4f' % (f('DRIVE_PPR') * f('GEAR_C') / 360.0),
        'SCALE_ROT': '%.3f' % (f('ROT_FULLSTEPS') * f('ROT_MICROSTEP')
                               * f('ROT_GEAR') / 360.0),
        # exposed so HAL can setp pso_live's per-axis gear from the SSOT
        # instead of anyone re-typing it (CLAUDE.md rule 11)
        'GEAR_A': dt['GEAR_A'],
        'GEAR_C': dt['GEAR_C'],
        'MAX_VEL_LIN': dt['MAX_VEL_LIN'],
        'MAXV_DISPLAY': dt['MAXV_DISPLAY'],
    }


def render(section_lines, dv):
    out = []
    for ln in section_lines:
        m = re.match(r'^(\s*[A-Z_][A-Z0-9_]*\s*=\s*[+-]?)@([A-Z_]+)\s*$', ln)
        if m:
            if m.group(2) not in dv:
                raise SystemExit('unknown derived token @%s' % m.group(2))
            ln = m.group(1) + dv[m.group(2)]
        out.append(ln)
    # drop trailing blank lines, keep exactly one newline at EOF
    while out and out[-1] == '':
        out.pop()
    return '\n'.join(out) + '\n'


def cmd_extract():
    if os.path.exists(MASTER):
        raise SystemExit('MASTER.params already exists -- refusing to overwrite')
    dt_lines = []
    with open(NED_PARAMS_SH) as f:
        for ln in f:
            m = re.match(r'^([A-Z_][A-Z0-9_]*)=([0-9.]+)\s*(#.*)?$', ln.strip())
            if m and m.group(1) in ('DRIVE_PPR', 'GEAR_A', 'GEAR_C',
                                    'ROT_FULLSTEPS', 'ROT_MICROSTEP',
                                    'ROT_GEAR', 'MAXV_DISPLAY', 'MAX_VEL_LIN'):
                c = ('  ' + m.group(3)) if m.group(3) else ''
                dt_lines.append('%s = %s%s' % (m.group(1), m.group(2), c))
    parts = [
        '# ================================================================',
        '# ned MASTER PARAMETER FILE -- the single authoritative source for',
        '# every configs/params/*.inc value (task #16, 2026-08-02).',
        '# Edit HERE; then: tools/live/gen_params.py check && ... write',
        '# NOT here: head_zero.inc (written by ned_brain at zero capture).',
        '# [drivetrain] primitives mirror tools/live/ned_params.sh (bench',
        '# scripts still source that file; `check` cross-checks the two).',
        '# ================================================================',
        '',
        '[drivetrain]',
    ] + dt_lines + ['']
    for sec, fname in FILES:
        parts.append('[%s]' % sec)
        with open(os.path.join(PDIR, fname)) as f:
            body = f.read().rstrip('\n')
        parts.append(body)
        parts.append('')
    with open(MASTER, 'w') as f:
        f.write('\n'.join(parts) + '\n')
    print('MASTER.params extracted: %d sections + drivetrain' % len(FILES))


def regen(tmpdir=None):
    dt, sections = parse_master(MASTER)
    dv = derived(dt)
    out = {}
    for sec, fname in FILES:
        if sec not in sections:
            raise SystemExit('MASTER.params missing section [%s]' % sec)
        out[fname] = render(sections[sec], dv)
    return dt, dv, out


def cmd_check():
    dt, dv, out = regen()
    ok = True
    for _, fname in FILES:
        live = open(os.path.join(PDIR, fname)).read()
        gen = out[fname]
        # generated files carry the header once written; compare bodies
        body = gen if not live.startswith(GEN_HEADER) else GEN_HEADER + gen
        if live == gen or live == GEN_HEADER + gen:
            print('  identical: %s' % fname)
        else:
            ok = False
            print('  DIFFERS:   %s' % fname)
            import difflib
            live_l = live.splitlines()
            gen_l = (GEN_HEADER + gen).splitlines() if live.startswith('# GENERATED') else gen.splitlines()
            for d in list(difflib.unified_diff(live_l, gen_l, lineterm=''))[:12]:
                print('    ' + d)
    # cross-check drivetrain vs ned_params.sh
    sh = {}
    with open(NED_PARAMS_SH) as f:
        for ln in f:
            m = re.match(r'^([A-Z_][A-Z0-9_]*)=([0-9.]+)', ln.strip())
            if m:
                sh[m.group(1)] = m.group(2)
    for k, v in dt.items():
        if k in sh and float(sh[k]) != float(v):
            ok = False
            print('  DRIVETRAIN DRIFT: %s master=%s ned_params.sh=%s' % (k, v, sh[k]))
    print('check: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def cmd_write():
    dt, dv, out = regen()
    for _, fname in FILES:
        path = os.path.join(PDIR, fname)
        new = GEN_HEADER + out[fname]
        old = open(path).read()
        if old != new:
            open(path, 'w').write(new)
            print('  wrote: %s' % fname)
        else:
            print('  unchanged: %s' % fname)
    print('write done -- .inc files now carry the GENERATED header')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'extract':
        cmd_extract()
    elif cmd == 'check':
        sys.exit(cmd_check())
    elif cmd == 'write':
        cmd_write()
    else:
        print(__doc__)
        sys.exit(2)
