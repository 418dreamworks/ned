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
BEFORE=$(cd "$NED" && git status --porcelain configs/ | md5sum)
python3 -
RC=$?
[ $RC -ne 0 ] && { echo "edit script failed (rc=$RC) -- check the tree" >&2; exit $RC; }

# a write is only finished when it still parses
if ! "$NED/tools/gcode_check.sh" --all >/tmp/cfg_edit_check.$$ 2>&1; then
    echo "=== SCANNER FAILED AFTER THE EDIT ===" >&2
    grep -E 'LINT|FAULT' /tmp/cfg_edit_check.$$ >&2 || cat /tmp/cfg_edit_check.$$ >&2
    rm -f /tmp/cfg_edit_check.$$
    exit 1
fi
rm -f /tmp/cfg_edit_check.$$
AFTER=$(cd "$NED" && git status --porcelain configs/ | md5sum)
[ "$BEFORE" = "$AFTER" ] && echo "(no files changed)" || echo "OK: gate passed, edit applied, scanner green"
