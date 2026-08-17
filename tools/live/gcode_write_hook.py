#!/usr/bin/env python3
"""PostToolUse hook: lint every g-code file the generator writes.

Operator 2026-08-16: "we need to make sure gcode claude follows the rule."

WHY A HOOK AND NOT AN INSTRUCTION. nc_files/CLAUDE.md already tells the
generator to read docs/gcode_rules.md and to run gcode_check.sh before
handover. It was told, and its next edit still started the spindle before the
XY resume at BOTH tool changes (alu_square.ngc:76 and :201, rule 6.3). An
instruction is a request; this is a gate.

It is the same lesson cfg_edit.sh exists for on the controls side, written in
this project's own CLAUDE.md rule 21: "A separate check I have to remember is
not a check. The gate must be part of the write."

WHAT IT DOES. Reads the PostToolUse JSON on stdin, and if the tool just wrote
a program file, runs tools/live/gcode_lint.py over it. On a HARD finding it
exits 2 with the findings on stderr, which Claude Code feeds back to the
agent that made the write -- so the generator is told, in its own loop, every
single time, and cannot hand over a violating file believing it is clean.

It does NOT silently repair the file. The generator fixes its own work; a
hook that edits g-code behind the author's back is a worse problem than the
one it solves.

Exit 0 = clean or not our business. Exit 2 = HARD findings, fed back.
"""

import json
import os
import re
import subprocess
import sys

NED = '/home/brains/Documents/ned'
LINT = os.path.join(NED, 'tools/live/gcode_lint.py')
EXTS = ('.ngc', '.nc', '.tap')


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0                      # never break the agent on a parse slip

    ti = data.get('tool_input') or {}
    path = ti.get('file_path') or ti.get('path') or ''
    if not path or not path.lower().endswith(EXTS):
        return 0
    if not os.path.exists(path):
        return 0

    try:
        r = subprocess.run([sys.executable, LINT, path],
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        sys.stderr.write('gcode rules: linter did not run (%s) -- '
                         'treat this file as UNCHECKED\n' % e)
        return 2

    if r.returncode == 0:
        return 0

    hard = [ln for ln in r.stdout.splitlines()
            if ln.startswith(path + ':')]
    sys.stderr.write(
        'G-CODE RULES VIOLATION -- %s\n\n' % os.path.basename(path))
    for ln in hard:
        sys.stderr.write('  %s\n' % ln[len(path) + 1:])
    sys.stderr.write(
        '\nThese are the machine safety rules in %s/docs/gcode_rules.md.\n'
        'You do not own that file and must not edit it. Fix the PROGRAM so it\n'
        'complies, then write it again. Do not hand this file to the operator\n'
        'until this hook passes.\n' % NED)
    return 2


if __name__ == '__main__':
    sys.exit(main())
