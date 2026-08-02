#!/bin/bash
# limits_off.sh -- SESSION-scoped: kill hard-limit switch inputs AND open every soft
# limit, joints and axes. Operator-requested for unhomed bring-up / probe testing.
# Lasts only until LinuxCNC restarts (touches pins, never files). NO PROTECTION after
# this runs -- the operator owns every stop.
set -u
if ! halcmd getp ini.0.min_limit >/dev/null 2>&1; then
  echo "limits_off: no LinuxCNC session running"; exit 1
fi
for j in 0 1 2 3 4 5; do
  # unlinkp leaves the pin at its LAST value, so force each switch input to 0 after.
  halcmd unlinkp joint.$j.neg-lim-sw-in >/dev/null 2>&1
  halcmd unlinkp joint.$j.pos-lim-sw-in >/dev/null 2>&1
  halcmd setp joint.$j.neg-lim-sw-in 0
  halcmd setp joint.$j.pos-lim-sw-in 0
  halcmd setp ini.$j.min_limit -1e9
  halcmd setp ini.$j.max_limit  1e9
done
for a in x y z a c; do
  halcmd setp ini.$a.min_limit -1e9 2>/dev/null
  halcmd setp ini.$a.max_limit  1e9 2>/dev/null
done
echo "limits_off: ALL limit switches + soft limits DISABLED until LinuxCNC restarts"
