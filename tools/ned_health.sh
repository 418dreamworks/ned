#!/bin/bash
# ASSISTANT MANAGER CHECK for ned (418ops charter, 2026-09-23).
#
# The hat covers the MACHINE and the brains account, not anyone's work: is ned
# up and on the tailnet, is mailsync running and single, did a session lose its
# login, is a disk filling, did an update break something, is the control
# healthy.  GM cannot see this box from mbp.
#
# Silent when everything is fine -- prints ONLY faults, one line each, so the
# output IS the report to GM.  Read-only: touches no config, moves nothing.
#
#   tools/ned_health.sh          faults only
#   tools/ned_health.sh -v       every check, pass or fail
set -u
NED=/home/brains/Documents/ned
V=0; [ "${1:-}" = "-v" ] && V=1
FAULTS=0
ok()   { [ $V = 1 ] && printf '  ok    %s\n' "$1"; return 0; }
bad()  { printf 'ned: %s\n' "$1"; FAULTS=$((FAULTS+1)); }

# --- on the tailnet ---------------------------------------------------------
if ts=$(timeout 12 tailscale status 2>&1); then
  if echo "$ts" | grep -q '^100\..*[[:space:]]ned[[:space:]]'; then ok "on the tailnet"
  else bad "not on the tailnet -- tailscale status lists no 'ned' node"; fi
else
  bad "tailscale is not answering (login lost or daemon down)"
fi

# --- exactly one mailsync, and one checkout ---------------------------------
n=$(pgrep -fc 'mailsync\.py' 2>/dev/null || echo 0)
case "$n" in
  1) ok "one mailsync" ;;
  0) bad "mailsync is NOT running -- mail neither arrives nor leaves" ;;
  *) bad "$n mailsync processes running; there must be exactly one" ;;
esac
c=$(find /home/brains -maxdepth 3 -name '.git' -path '*418ops*' 2>/dev/null | wc -l)
[ "$c" = 1 ] && ok "one 418ops checkout" || bad "$c 418ops checkouts on this box; there must be exactly one"

# --- disk -------------------------------------------------------------------
use=$(df --output=pcent / | tail -1 | tr -dc '0-9')
[ "${use:-0}" -lt 85 ] && ok "disk ${use}% used" || bad "root filesystem ${use}% full"

# --- the modules a LinuxCNC upgrade silently clobbers (docs/update_survival) -
for m in homemod bsplit pso_live jogblock limdir; do
  f=/usr/lib/linuxcnc/modules/$m.so
  if [ ! -f "$f" ]; then bad "$m.so is MISSING from /usr/lib/linuxcnc/modules -- an upgrade wiped it"
  elif [ "$f" -ot /usr/bin/linuxcnc ]; then
    bad "$m.so is older than the installed linuxcnc -- likely overwritten by an upgrade"
  else ok "$m.so present and newer than linuxcnc"; fi
done

# --- the control ------------------------------------------------------------
if pgrep -f 'mesalog\.sh' >/dev/null 2>&1; then ok "mesalog running"
else bad "mesalog is not running -- the Mesa link is unmonitored"; fi

# --- logins that go stale ---------------------------------------------------
if timeout 15 gh auth status >/dev/null 2>&1; then ok "gh authenticated"
else bad "gh is not authenticated -- GitHub work will fail"; fi

[ $V = 1 ] && echo "  -- $FAULTS fault(s)"
exit $(( FAULTS > 0 ))
