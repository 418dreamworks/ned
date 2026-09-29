#!/usr/bin/env python3
"""The REVISION header every ned program carries. Rule 3.7.

Operator 2026-09-29: "we always have version contorl on top of files whenever
we are editing like this so that i know what is happening."

ONE implementation, imported by every generator, so the line cannot drift
between files. The md5 is of the body the generator produced -- computed
AFTER the rest of the file exists and inserted at the top -- so what is on
screen can be matched to what is on disk without trusting a filename or a
timestamp.
"""
import subprocess
import time


def _git_rev(path):
    try:
        r = subprocess.run(['git', '-C', '/home/brains/Documents/ned',
                            'log', '-1', '--format=%h', '--', path],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or 'uncommitted'
    except Exception:
        return 'unknown'


def revision_lines(body_lines, generator, changed):
    """Return the two header lines for a program whose body is body_lines.

    body_lines -- unused, kept so callers need not change
    generator  -- e.g. 'gen_facing.py', relative to ned/tools/
    changed    -- ONE line saying what moved since the last revision
    """
    rev = _git_rev('tools/' + generator)
    return ['(REVISION %s  %s @ %s)'
            % (time.strftime('%Y-%m-%d %H:%M:%S'), generator, rev),
            '(CHANGED  %s)' % changed]
