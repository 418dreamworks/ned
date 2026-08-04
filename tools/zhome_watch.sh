#!/bin/bash
# zhome_watch.sh -- watch what Z actually does while you press Home Z.
#
# Run this, THEN press Home Z. Ctrl-C to stop.
#
# The question it answers: when the following error fired, was Z being
# DRIVEN and failing to move, or was it never driven at all? The log records
# only the outcome, so this reads the pins on the way through.
#
# Columns:
#   ena2   joint.2.amp-enable-out      motion wants Z enabled
#   pwm0   pwmgen.00.enable            GROUP MASTER -- ch 0-3 are dead
#                                      without it, whatever ch2 says
#   pwm2   pwmgen.02.enable            Z channel enable
#   mm/s   sig-z-vel-volts             MISNAMED signal: this is the velocity
#                                      command in mm/s, not volts
#                                      (docs/motion_quickref.md:15)
#   V      the same figure as volts: mm/s / 178.2 * 10
#   cmd    joint.2.motor-pos-cmd       where motion says Z should be
#   fb     joint.2.motor-pos-fb        where the encoder says Z is
#   ferr   joint.2.f-error             cmd - fb
#   lim    joint.2.f-error-lim         the trip threshold at this speed
#   homing joint.2.homing
#   botlim sig-limit-z-bottom          TRUE = sitting on the bottom switch
#
# Read it like this:
#   cmd MOVES, fb FLAT, ferr GROWS  -> commanded but not moving: drive,
#                                      brake or mechanical stop
#   cmd FLAT from the start         -> motion never issued the search
#   pwm0 FALSE                      -> the group master is gating Z off
#                                      (ned quirk: ch0 enable gates ch0-3)

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

PINS="joint.2.amp-enable-out hm2_7i97.0.pwmgen.00.enable hm2_7i97.0.pwmgen.02.enable \
joint.2.motor-pos-cmd joint.2.motor-pos-fb joint.2.f-error joint.2.f-error-lim \
joint.2.homing"

ZSCALE=178.2      # [JOINT_2]OUTPUT_SCALE: mm/s at full-scale 10 V out

printf '%-12s %5s %5s %5s %9s %6s %10s %10s %8s %7s %7s %7s\n' \
       TIME ena2 pwm0 pwm2 mm/s V cmd fb ferr lim homing botlim

while true; do
  # one halcmd per sample, timeout-wrapped: an unwrapped scripted halcmd can
  # deadlock on the PIPE (ned boot-lottery root cause, update_survival B3a)
  OUT=$(timeout 5 halcmd -s show pin $PINS 2>/dev/null)
  SIG=$(timeout 5 halcmd -s show sig sig-z-vel-volts sig-limit-z-bottom 2>/dev/null)
  [ -z "$OUT" ] && { echo "$(date +%H:%M:%S.%2N)  -- no HAL session --"; sleep 1; continue; }

  # Value is the field immediately BEFORE the pin name. Matching on an exact
  # field -- not a regex over the line -- because "joint.2.f-error" is a
  # prefix of "joint.2.f-errored" and a loose match silently reads the wrong
  # pin (it reported ferr=FALSE from f-errored on the first run).
  get() { echo "$OUT" | awk -v p="$1" '{for(i=1;i<=NF;i++) if($i==p){print $(i-1); exit}}'; }
  gets() { echo "$SIG" | awk -v s="$1" '{for(i=1;i<=NF;i++) if($i==s){print $2; exit}}'; }

  ena2=$(get joint.2.amp-enable-out)
  pwm0=$(get hm2_7i97.0.pwmgen.00.enable)
  pwm2=$(get hm2_7i97.0.pwmgen.02.enable)
  cmd=$(get  joint.2.motor-pos-cmd)
  fb=$(get   joint.2.motor-pos-fb)
  ferr=$(get joint.2.f-error)
  lim=$(get  joint.2.f-error-lim)
  hom=$(get  joint.2.homing)
  volts=$(gets sig-z-vel-volts)
  bot=$(gets sig-limit-z-bottom)

  V=$(awk -v v="${volts:-0}" -v s="$ZSCALE" 'BEGIN{printf "%.2f", v/s*10}')
  printf '%-12s %5s %5s %5s %9.9s %6s %10.10s %10.10s %8.8s %7.7s %7s %7s\n' \
         "$(date +%H:%M:%S.%2N)" "$ena2" "$pwm0" "$pwm2" \
         "$volts" "$V" "$cmd" "$fb" "$ferr" "$lim" "$hom" "$bot"
  sleep 0.2
done
