#!/bin/bash
# claim.sh -- record WHO is using the machine so the GUI can show it.
#   tools/claim.sh claude "running homing test -- please don't touch"
#   tools/claim.sh user   "yours"
#   tools/claim.sh free   "idle"
# The nedgui Session tab + the banner on the left panel read ned/session.txt.
NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
who="${1:-free}"; shift 2>/dev/null; note="${*:-}"
{ echo "OWNER=${who}"
  echo "SINCE=$(date '+%F %H:%M:%S')"
  echo "NOTE=${note}"
} > "$NED/session.txt"
echo "claim: ${who} -- ${note}"
