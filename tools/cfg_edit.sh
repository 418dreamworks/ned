#!/bin/bash
# The ONLY sanctioned way to modify anything under configs/. CLAUDE.md rule 21.
#
# Gate -> apply -> verify, as ONE command, so the gate cannot be skipped by
# forgetting a separate step. On 2026-08-03 I wrote three C subroutines during
# a live StartC (parse error mid-cycle), plunged Z through the puck, and then
# made two more writes with no gate at all -- minutes after hardening the rule.
# A rule I have to remember is not a rule; this makes the check part of the act.
#
# Usage:  tools/cfg_edit.sh <<'PY'
#           ...python that edits files under configs/...
#         PY
set -euo pipefail
NED=/home/brains/Documents/ned

if ! "$NED/tools/machine_idle.sh"; then
    echo "REFUSED: not writing under configs/ -- see above." >&2
    exit 1
fi
# hash the CONTENT, not `git status` -- porcelain output does not change when
# a file was already modified, so it reported "no files changed" after a real
# edit (2026-08-03). A verification that can say "nothing happened" when
# something did is worse than none.
BEFORE=$(cd "$NED" && git diff --stat configs/ | md5sum)
python3 -
RC=$?
[ $RC -ne 0 ] && { echo "edit script failed (rc=$RC) -- check the tree" >&2; exit $RC; }

# CLASS-ATTRIBUTE / METHOD CHECK. py_compile cannot see a deleted class
# attribute -- it is an AttributeError at runtime. On 2026-08-03 a regex that
# removed one method also swallowed CAL_SUBS, which sat between it and the
# next def, and StartAC died instantly with "no attribute 'CAL_SUBS'". The
# scanner said green because the g-code was fine.
python3 - <<'ATTRCHK'
import re, sys, glob
bad = 0
for f in glob.glob('/home/brains/Documents/ned/configs/ned5_pb/**/*.py',
                   recursive=True):
    src = open(f).read()
    defined = set()
    for lhs in re.findall(r'^\s{4}([A-Z][A-Z0-9_, ]+?)\s*=[^=]', src, re.M):
        defined.update(n.strip() for n in lhs.split(','))
    used = set(re.findall(r'self\.([A-Z][A-Z0-9_]+)\b', src))
    defs = set(re.findall(r'^\s*def (\w+)\(', src, re.M))
    calls = set(re.findall(r'self\.(_\w+)\(', src))
    for n in sorted(used - defined):
        print('  MISSING class attr %s in %s' % (n, f.split('/')[-1])); bad = 1
    for n in sorted(c for c in calls if c not in defs):
        print('  MISSING method %s in %s' % (n, f.split('/')[-1])); bad = 1
sys.exit(bad)
ATTRCHK
if [ $? -ne 0 ]; then
    echo "=== SELF-REFERENCE CHECK FAILED AFTER THE EDIT ===" >&2
    exit 1
fi

# a write is only finished when it still parses
if ! "$NED/tools/gcode_check.sh" --all >/tmp/cfg_edit_check.$$ 2>&1; then
    echo "=== SCANNER FAILED AFTER THE EDIT ===" >&2
    grep -E 'LINT|FAULT' /tmp/cfg_edit_check.$$ >&2 || cat /tmp/cfg_edit_check.$$ >&2
    rm -f /tmp/cfg_edit_check.$$
    exit 1
fi
rm -f /tmp/cfg_edit_check.$$
AFTER=$(cd "$NED" && git diff --stat configs/ | md5sum)
[ "$BEFORE" = "$AFTER" ] && echo "(no files changed)" || echo "OK: gate passed, edit applied, scanner green"
