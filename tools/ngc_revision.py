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
    """The generator version, and whether it is the COMMITTED one.

    Operator 2026-09-29, quoting a header back at me:

        (REVISION 2026-09-29 12:24:17  gen_cbore_grid.py @ 48a9840)

    48a9840 was the last commit touching that generator -- and it had been
    edited since and not committed, so the line named a version that does
    NOT contain the change which produced the file. A sha pointing at the
    wrong source is worse than no sha: it reads as traceable and is not.
    Same failure as an md5 slot carrying a placeholder, and the whole
    reason rule 3.7 exists.
    """
    root = '/home/brains/Documents/ned'
    try:
        r = subprocess.run(['git', '-C', root, 'log', '-1', '--format=%h',
                            '--', path],
                           capture_output=True, text=True, timeout=10)
        sha = r.stdout.strip() or 'uncommitted'
        d = subprocess.run(['git', '-C', root, 'status', '--porcelain',
                            '--', path],
                           capture_output=True, text=True, timeout=10)
        if d.stdout.strip():
            return sha + '+UNCOMMITTED-EDITS'
        return sha
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
