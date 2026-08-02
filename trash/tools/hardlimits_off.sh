#!/bin/bash
# hardlimits_off.sh -- SESSION-SCOPED: stop ALL hard-limit switches from
# faulting the machine. Soft limits stay enforced; homing is unaffected
# (home-sw-in reads the raw switches). Re-run after every LinuxCNC restart.
# (The X POSITIVE limit is already auto-ignored after homing by ned_brain --
# this script is for the rest, when riding other switches on purpose.)
if ! timeout 3 halcmd getp joint.0.neg-lim-sw-in >/dev/null 2>&1; then
  echo "ERROR: no LinuxCNC session is running."
  echo "This script does not START anything -- it modifies the LIVE session."
  echo "Order: tools/run5.sh  ->  POWER  ->  REF ALL  ->  then run this."
  exit 1
fi
for j in 0 1 2 3; do
  for d in neg pos; do
    halcmd unlinkp joint.$j.$d-lim-sw-in 2>/dev/null
    halcmd setp   joint.$j.$d-lim-sw-in 0 2>/dev/null
  done
done
# also release the MPG wheel gates (jogblock swallows detents toward a tripped
# switch -- pointless when the switches are being ignored on purpose)
for ax in x y z; do
  for d in neg pos; do
    halcmd unlinkp jogblock.$ax.lim-$d 2>/dev/null
    halcmd setp   jogblock.$ax.lim-$d 0 2>/dev/null
  done
done
echo "hard limits OFF (session): joints 0-3 lim-sw-in + jogblock gates unlinked + forced 0"
echo "soft limits + homing unaffected. Restarting LinuxCNC restores them."
