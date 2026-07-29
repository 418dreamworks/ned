#!/bin/bash
# ned_params.sh -- SINGLE SOURCE OF TRUTH for ned's motion-scale constants.
# Change a ratio HERE ONLY. Two kinds of consumer:
#   1. bench scripts SOURCE this file (move.sh, mpgjog.sh) -> use $GEAR_A / $SCALE_A / ...
#   2. run `ned_params.sh apply [ini ...]` to WRITE the derived SCALEs into the INI(s).
# LinuxCNC INI can't do arithmetic, so `apply` propagates the computed values into the
# [JOINT_*] SCALE lines (defaults to ~/linuxcnc/configs/ned/ned.ini; pass mode INIs too).

# =================== EDIT THESE (physical constants) ===================
DRIVE_PPR=8192          # head Yaskawa servo: reference pulses per MOTOR rev (Pn20E)
GEAR_A=128.25           # head A (tilt) reduction motor:axis  -- HQD AC-D90-65 spec 1:128.25
GEAR_C=203.7471         # head C (spin) reduction motor:axis  -- HQD AC-D90-65 spec 1:203.7471
ROT_FULLSTEPS=200       # rotary-table stepper full steps/rev
ROT_MICROSTEP=2         # rotary drive microstep
ROT_GEAR=20             # rotary table reduction stepper:chuck (1:20 worm)

# =================== derived (do not edit) ===================
SCALE_A=$(awk "BEGIN{printf \"%.4f\", $DRIVE_PPR*$GEAR_A/360}")                    # head A pulses/axis-deg
SCALE_C=$(awk "BEGIN{printf \"%.4f\", $DRIVE_PPR*$GEAR_C/360}")                    # head C pulses/axis-deg
SCALE_ROT=$(awk "BEGIN{printf \"%.3f\", $ROT_FULLSTEPS*$ROT_MICROSTEP*$ROT_GEAR/360}")  # rotary B
export DRIVE_PPR GEAR_A GEAR_C ROT_FULLSTEPS ROT_MICROSTEP ROT_GEAR SCALE_A SCALE_C SCALE_ROT

# INI joint map:  J4 = B(+),  J5 = A(tilt),  J6 = C(spin),  J7 = B(-, counter-rotating)
SELF="${BASH_SOURCE[0]}"                              # this params file (mtime = the "source" timestamp)
CFGDIR="${NED_CFGDIR:-$HOME/linuxcnc/configs/ned}"   # where the INI(s) live
_ned_show(){
  printf 'ned_params:\n  DRIVE_PPR=%s  GEAR_A=%s  GEAR_C=%s  ROT=%s*%s*%s\n' \
    "$DRIVE_PPR" "$GEAR_A" "$GEAR_C" "$ROT_FULLSTEPS" "$ROT_MICROSTEP" "$ROT_GEAR"
  printf '  SCALE_A (J5) = %s\n  SCALE_C (J6) = %s\n  SCALE_ROT (J4 / J7) = %s / -%s\n' \
    "$SCALE_A" "$SCALE_C" "$SCALE_ROT" "$SCALE_ROT"
}
_ned_apply(){
  local ini
  for ini in "$@"; do
    [ -f "$ini" ] || { echo "skip (missing): $ini"; continue; }
    awk -v s4="$SCALE_ROT" -v s5="$SCALE_A" -v s6="$SCALE_C" -v s7="-$SCALE_ROT" '
      /^\[JOINT_4\]/{j=4;print;next} /^\[JOINT_5\]/{j=5;print;next}
      /^\[JOINT_6\]/{j=6;print;next} /^\[JOINT_7\]/{j=7;print;next}
      /^\[/{j=0;print;next}
      (j && $0 ~ /^SCALE[ \t]*=/){ v=(j==4?s4:(j==5?s5:(j==6?s6:s7))); print "SCALE = " v; next }
      {print}
    ' "$ini" > "$ini.tmp" && mv "$ini.tmp" "$ini" && echo "applied SCALEs -> $ini"
  done
}

# make-style rebuild: re-apply into any INI OLDER than this params file (params edited -> INI stale).
_ned_sync(){
  local ini rebuilt=0
  for ini in "$@"; do
    [ -f "$ini" ] || { echo "skip (missing): $ini"; continue; }
    if [ "$SELF" -nt "$ini" ]; then _ned_apply "$ini"; rebuilt=1
    else echo "up to date: $ini"; fi
  done
  [ $rebuilt = 0 ] && echo "(nothing stale -- no rebuild needed)"
  return 0
}

# Run directly (not sourced): show | apply | sync.  Default target = every *.ini in CFGDIR.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  cmd="${1:-show}"; shopt -s nullglob
  inis=("${@:2}"); [ ${#inis[@]} -gt 0 ] || inis=("$CFGDIR"/*.ini)
  case "$cmd" in
    show)  _ned_show ;;
    apply) _ned_apply "${inis[@]}"; echo; _ned_show ;;
    sync)  _ned_sync "${inis[@]}" ;;
    *) echo "usage: ned_params.sh [show | apply [ini...] | sync [ini...]]"; exit 2 ;;
  esac
fi
