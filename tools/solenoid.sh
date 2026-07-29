#!/bin/bash
# solenoid.sh -- fire the pneumatic solenoid outputs for bench testing. TESTING ONLY, nothing
# moves (air only). STANDALONE: kills LinuxCNC + any HAL session, loads its own solenoid.hal,
# owns the board, and drops every solenoid output on exit.
#
#   solenoid.sh unclamp <delay> <secs>   HQD DRAWBAR UNCLAMP. Waits <delay>s (walk over + HOLD
#                                  the tool), then fires all 3 solenoids out-13/14/15 (BIGGREEN
#                                  pink/yellow/bluered) for <secs>. Collet OPENS -> tool DROPS
#                                  if not held. default: delay 5, secs 10.
#   solenoid.sh pulse  [secs]      CHIP CLEARANCE (out-11): pulse 1 s ON / 1 s OFF for secs.
#   solenoid.sh blowoff [secs]     chip clearance (out-11) ON STEADY for secs.
#   solenoid.sh probe  [secs]      TOOL PROBE (out-12): RAISE (deploy) for secs, then LOWER.
#   solenoid.sh raise              tool probe UP (out-12 ON), hold until Ctrl-C.
#   solenoid.sh lower              tool probe DOWN (out-12 OFF) and exit.
#   solenoid.sh alloff             drop every solenoid output and exit.
#   [secs] default 10 (probe: 5), max 60.   (Air curtain is always-on -- not switched here.)
# e.g.:  bash ned/tools/solenoid.sh unclamp 5 10   ·   solenoid.sh pulse 10   ·   solenoid.sh probe

P=hm2_7i97.0
HAL="$(dirname "$(readlink -f "$0")")/solenoid.hal"
PNEU="output-11 output-12 output-13 output-14 output-15"     # every output this script can drive

usage(){ awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "$0"; exit 1; }
case "$1" in ""|-h|--help|help) usage ;; esac
what="$1"
case "$what" in
  unclamp|toolrelease|release)
    DELAY="${2:-5}"; DUR="${3:-10}"
    awk "BEGIN{exit !($DELAY>=0 && $DELAY<=60 && $DUR>0 && $DUR<=60)}" 2>/dev/null \
      || { echo "usage: solenoid.sh unclamp <delay-secs 0..60> <unclamp-secs 0..60>"; exit 1; } ;;
  pulse|blowoff|probe)
    SECS="$2"; [ "$what" = probe ] && SECS="${SECS:-5}" || SECS="${SECS:-10}"
    awk "BEGIN{exit !($SECS>0 && $SECS<=60)}" 2>/dev/null || { echo "seconds must be 0..60"; exit 1; } ;;
  raise|lower|alloff) ;;
  *) echo "unknown: $what"; usage ;;
esac

# --- own the board: kill LinuxCNC + any HAL session, load our own ---
pgrep -f linuxcnc >/dev/null 2>&1 && { echo "killing running LinuxCNC..."; pkill -9 -f linuxcnc 2>/dev/null; sleep 2; }
halrun -U >/dev/null 2>&1
halrun -f "$HAL" >/dev/null 2>&1 & HALPID=$!
echo "starting the board (a few seconds)..."; sleep 5
kill -0 "$HALPID" 2>/dev/null || { echo "FAILED to start -- Mesa powered? cable in? (10.10.10.10)"; exit 1; }

# --- air-pressure warning (input-12 / *37; active-high: TRUE=OK, FALSE=low; fail-safe NC switch) ---
air=$(halcmd getp $P.inmux.00.input-12 2>/dev/null)
case "$air" in
  TRUE)  echo "  air pressure: OK (*37)" ;;
  FALSE) echo "  ⚠️  WARNING: LOW AIR PRESSURE (*37/input-12) -- unclamp/blow-off air not pressurized" ;;
  *)     echo "  ⚠️  air pressure UNREADABLE (input-12=${air:-?})" ;;
esac

on(){  for o in "$@"; do halcmd setp $P.7i84.0.0.$o 1 2>/dev/null; done; }
off(){ for o in "$@"; do halcmd setp $P.7i84.0.0.$o 0 2>/dev/null; done; }
alloff(){ off $PNEU; }
teardown(){ echo; echo ">>> all solenoids OFF"; alloff; sleep 0.3; kill "$HALPID" 2>/dev/null; halrun -U >/dev/null 2>&1; echo "done."; }
trap 'teardown; exit' EXIT INT TERM

loops(){ awk "BEGIN{printf \"%d\",($1/0.5)+0.5}"; }   # 0.5 s ticks

case "$what" in

  unclamp|toolrelease|release)
    echo ">>> DRAWBAR UNCLAMP -- ${DELAY}s to get to the tool, then air ON for ${DUR}s ($(date +%H:%M:%S))."
    echo "    !! HOLD THE TOOL before the air fires -- collet opens and it DROPS otherwise."
    for ((k=DELAY;k>=1;k--)); do printf '  ...firing in %2ds  (get to the tool + hold it)\n' "$k"; sleep 1; done
    echo "  >>> UNCLAMP AIR ON -- collet OPEN. seat/swap the tool."
    on output-13 output-14 output-15
    n=$(loops $DUR); for ((k=1;k<=n;k++)); do printf '  +%.1fs  unclamp air ON\n' "$(awk "BEGIN{print $k*0.5}")"; sleep 0.5; done
    echo ">>> ${DUR}s up -- dropping air (clamps)." ;;

  pulse)
    echo ">>> CHIP CLEARANCE (out-11) -- pulsing 1 s ON / 1 s OFF for ${SECS}s ($(date +%H:%M:%S))."
    end=$(awk "BEGIN{printf \"%d\", $SECS+0.5}"); t=0
    while [ "$t" -lt "$end" ]; do
      on  output-11; printf '  +%2ds  ON\n'  "$t"; sleep 1; t=$((t+1)); [ "$t" -ge "$end" ] && break
      off output-11; printf '  +%2ds  off\n' "$t"; sleep 1; t=$((t+1))
    done
    echo ">>> ${SECS}s up." ;;

  blowoff)
    echo ">>> CHIP CLEARANCE (out-11) -- STEADY ON for ${SECS}s ($(date +%H:%M:%S))."
    on output-11
    n=$(loops $SECS); for ((k=1;k<=n;k++)); do printf '  +%.1fs  blow-off ON\n' "$(awk "BEGIN{print $k*0.5}")"; sleep 0.5; done ;;

  probe)
    echo ">>> TOOL PROBE (out-12) -- RAISE (deploy), hold ${SECS}s, then LOWER ($(date +%H:%M:%S))."
    on output-12; echo "  probe UP (deployed)"
    n=$(loops $SECS); for ((k=1;k<=n;k++)); do sleep 0.5; done
    off output-12; echo "  probe DOWN (retracted)" ;;

  raise)
    echo ">>> TOOL PROBE UP (out-12 ON) -- holding. Ctrl-C to drop (lowers)."
    on output-12; while true; do sleep 1; done ;;

  lower)
    echo ">>> TOOL PROBE DOWN (out-12 OFF)."
    off output-12 ;;

  alloff)
    echo ">>> all solenoid outputs dropped." ;;   # teardown does the drop

esac
exit 0   # EXIT trap runs teardown (all solenoids off + session down)
