#!/usr/bin/env python3
"""Sequester every program that breaks the current g-code rules.

Operator 2026-08-16: "all programs that violate the most current set of rules
must be seqeuestered immediately."

WHAT IT DOES. Lints every program under [DISPLAY]PROGRAM_PREFIX against
docs/gcode_rules.md (via tools/live/gcode_lint.py) and MOVES any file with a
HARD finding out of the runnable tree.

WHERE THEY GO. /home/brains/linuxcnc/nc_files_quarantine, which is OUTSIDE
PROGRAM_PREFIX on purpose: a subfolder of nc_files would still be reachable
from PB's file browser, so a sequestered program would stay one double-click
from running. Relative paths are preserved inside the quarantine.

NOT DELETED -- MOVED, and recorded. Every move is appended to
MANIFEST.md in the quarantine with the findings that caused it and the
original path, so anything can be put back by hand once it is fixed. Nothing
here removes a file (ned house rule: "delete" means move, never rm).

WHAT IT REFUSES TO DO. It will not move the program the interpreter currently
has loaded unless the machine is idle -- pulling a file out from under a
running cycle is a way to turn a lint finding into a crash. It says so and
leaves that one file alone.

    tools/gcode_quarantine.py [--dry-run]
"""

import os
import re
import shutil
import subprocess
import sys
import time

NED = '/home/brains/Documents/ned'
LINT = os.path.join(NED, 'tools/live/gcode_lint.py')
INI = os.path.join(NED, 'configs/ned5_pb/ned5_pb_ab_gen.ini.expanded')
QUAR = '/home/brains/linuxcnc/nc_files_quarantine'
FALLBACK_PREFIX = '/home/brains/linuxcnc/nc_files'


def program_prefix():
    """PROGRAM_PREFIX from the ini, so this follows the config rather than a
    re-typed path."""
    try:
        with open(INI, encoding='utf-8', errors='replace') as fh:
            for ln in fh:
                ln = ln.split('#')[0].strip()
                if ln.upper().startswith('PROGRAM_PREFIX'):
                    return ln.split('=', 1)[1].strip()
    except OSError:
        pass
    return FALLBACK_PREFIX


def extensions():
    """[FILTER]PROGRAM_EXTENSION lists what this machine will actually run."""
    ex = set()
    try:
        with open(INI, encoding='utf-8', errors='replace') as fh:
            for ln in fh:
                if ln.strip().upper().startswith('PROGRAM_EXTENSION'):
                    for tok in re.findall(r'\.[A-Za-z0-9]+', ln.split('=', 1)[1]):
                        ex.add(tok.lower())
    except OSError:
        pass
    return ex or {'.ngc', '.nc', '.tap'}


def loaded_and_busy():
    """(currently loaded file, machine is busy). Both are needed: the loaded
    file is only untouchable while something is actually running."""
    try:
        import linuxcnc
        s = linuxcnc.stat()
        s.poll()
        busy = (s.interp_state != linuxcnc.INTERP_IDLE) or (not s.inpos)
        return (s.file or ''), busy
    except Exception:
        # No session at all -- nothing can be mid-cycle.
        return '', False


def hard_findings(path):
    """The linter's own HARD/WARN split decides. A line without the 'warn '
    prefix is a hard finding; exit code 1 means at least one."""
    r = subprocess.run([sys.executable, LINT, path],
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        return []
    return [ln for ln in r.stdout.splitlines()
            if ln.startswith(path + ':')]


def main(argv):
    dry = '--dry-run' in argv
    prefix = program_prefix()
    exts = extensions()
    loaded, busy = loaded_and_busy()

    progs = []
    for root, dirs, files in os.walk(prefix):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fn in files:
            if os.path.splitext(fn)[1].lower() in exts:
                progs.append(os.path.join(root, fn))
    progs.sort()

    print('scanning %d program(s) under %s' % (len(progs), prefix))
    print('rules: %s/docs/gcode_rules.md' % NED)
    if busy:
        print('machine is BUSY -- the loaded program will be left in place')

    moved, skipped, clean = [], [], 0
    for p in progs:
        bad = hard_findings(p)
        if not bad:
            clean += 1
            continue
        if p == loaded and busy:
            skipped.append((p, bad))
            continue
        rel = os.path.relpath(p, prefix)
        dest = os.path.join(QUAR, rel)
        if not dry:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            # never clobber an earlier quarantine of the same name
            if os.path.exists(dest):
                dest = '%s.%s' % (dest, time.strftime('%Y%m%d-%H%M%S'))
            shutil.move(p, dest)
        moved.append((p, dest, bad))

    if moved and not dry:
        os.makedirs(QUAR, exist_ok=True)
        with open(os.path.join(QUAR, 'MANIFEST.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n## sequestered %s\n\n'
                     % time.strftime('%Y-%m-%d %H:%M:%S'))
            fh.write('Rules: %s/docs/gcode_rules.md\n'
                     'Put a file back by fixing it and moving it to %s.\n\n'
                     % (NED, prefix))
            for src, dest, bad in moved:
                fh.write('### %s\n\n' % os.path.basename(src))
                fh.write('- was: `%s`\n- now: `%s`\n\n' % (src, dest))
                for ln in bad:
                    fh.write('      %s\n' % ln)
                fh.write('\n')

    print()
    for src, dest, bad in moved:
        print('%s %s' % ('WOULD SEQUESTER' if dry else 'SEQUESTERED',
                         os.path.basename(src)))
        for ln in bad[:4]:
            print('    %s' % ln.split(': ', 1)[-1])
        if len(bad) > 4:
            print('    ... %d more finding(s)' % (len(bad) - 4))
    for src, bad in skipped:
        print('LEFT IN PLACE (loaded and machine busy) %s -- %d finding(s)'
              % (os.path.basename(src), len(bad)))

    print()
    print('%d clean, %d %s, %d left in place'
          % (clean, len(moved), 'would move' if dry else 'sequestered',
             len(skipped)))
    if moved and not dry:
        print('manifest: %s/MANIFEST.md' % QUAR)
    # non-zero when anything runnable still violates
    return 1 if skipped else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
