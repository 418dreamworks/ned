#!/bin/bash
# pb_fit_check.sh -- does the Probe Basic GUI actually FIT the monitor?
#
# WHY THIS EXISTS (2026-08-03). PB came up correctly sized and then, seconds
# later, grew past the monitor. The top-level window still measured a correct
# 1920x1200 the whole time -- what overflowed were its CHILD widgets, laid out
# to roughly 3840x2400, which pushed PB's own bottom strip (MAIN/FILE/ATC and
# the DRO row) off the bottom edge. A check that only looked at the window
# size would have reported "fine". So this measures the child extents.
#
# Cause was a user tab: ned_controls builds its sub-tabs on a 6.5 s
# singleShot, and the CALIBRATION grid's fixed columns became a
# minimumSizeHint that propagated up into the QMainWindow. Qt honours a
# child's minimum over the screen -- nothing clips it for you.
#
# Runs in the BACKGROUND from run5.sh and never blocks the launch. It only
# ever REPORTS -- it does not resize or restyle anything, because a GUI that
# is silently corrected still ships the bug to the next launch.
#
# Samples repeatedly: the failure appears LATE, so one early look is useless.

NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="$NED/lcnc.log"
export DISPLAY="${DISPLAY:-:0}"

say() { echo "[pb_fit_check] $*" >> "$LOG"; }

command -v xdotool >/dev/null 2>&1 || { say "xdotool missing -- CANNOT CHECK GUI FIT"; exit 0; }

# screen size from the connected output
read -r SW SH < <(xrandr 2>/dev/null | awk '/ connected /{if (match($0,/[0-9]+x[0-9]+\+/)) {s=substr($0,RSTART,RLENGTH-1); split(s,a,"x"); print a[1], a[2]; exit}}')
[ -n "$SW" ] || { say "could not read screen size from xrandr -- CANNOT CHECK GUI FIT"; exit 0; }
say "screen is ${SW}x${SH}"

# wait for the PB window (up to 120 s -- a cold VTK start is slow)
WID=""
for _ in $(seq 1 120); do
  WID=$(xdotool search --name '^Probe Basic$' 2>/dev/null | head -1)
  [ -n "$WID" ] && break
  sleep 1
done
[ -n "$WID" ] || { say "Probe Basic window never appeared -- no fit check performed"; exit 0; }

# geometry of one window id -> "X Y W H"
geom() {
  xdotool getwindowgeometry "$1" 2>/dev/null | awk '
    /Position:/ {split($2,p,","); x=p[1]; y=p[2]}
    /Geometry:/ {split($2,g,"x"); w=g[1]; h=g[2]}
    END {if (w != "") print x, y, w, h}'
}

# the deepest extent any child of the app reaches
extent() {
  local maxx=0 maxy=0 x y w h id
  for id in $(xdotool search --all --pid "$(xdotool getwindowpid "$WID" 2>/dev/null)" 2>/dev/null); do
    read -r x y w h < <(geom "$id"); [ -n "$h" ] || continue
    [ "$w" -le 1 ] && continue
    (( x + w > maxx )) && maxx=$((x + w))
    (( y + h > maxy )) && maxy=$((y + h))
  done
  echo "$maxx $maxy"
}

BAD=0
for T in 8 16 30 50; do
  sleep "$T"
  read -r WX WY WW WH < <(geom "$WID"); [ -n "$WH" ] || continue
  read -r EX EY < <(extent)

  if (( WW > SW || WH > SH )); then
    say "FAIL t+${T}s: WINDOW ${WW}x${WH} is bigger than the ${SW}x${SH} screen"
    BAD=1
  fi
  if (( EX > SW || EY > SH )); then
    say "FAIL t+${T}s: CONTENT reaches ${EX}x${EY}, past the ${SW}x${SH} screen -- \
a child widget's minimum size is forcing the layout wider/taller than the monitor. \
Window itself measures ${WW}x${WH}. Suspect the most recently built user tab \
(configs/ned5_pb/user_tabs/*) -- see this file's header."
    BAD=1
  fi
  (( BAD == 0 )) && say "ok t+${T}s: window ${WW}x${WH}, content ${EX}x${EY}, screen ${SW}x${SH}"
done

(( BAD == 0 )) && say "GUI FIT OK -- nothing exceeded the screen through t+104s"
exit 0
