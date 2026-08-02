#!/bin/bash
# pso_home.sh -- LAUNCH-TIME capture of the head's absolute position. Runs board-FREE,
# BEFORE LinuxCNC (tools/pso_read.sh uses its own halrun).
#
# The ONLY stored number is the encoder position at zero (PS) in the parameter file
# configs/params/head_zero.inc  (A/C _MULTITURN + _WITHIN). Nothing else is persisted.
# At startup this script:
#   1. reads the absolute encoder position PE (multiturn,within) for A and C,
#   2. diffs against the param-file zero:  position = PE - PS  (manual 6.12.6: PM = PE - PS),
#        * UNWRAPPED -- no mod-360 fold. +190 stays +190; the path to zero is preserved.
#        * range +/-315; a value OUTSIDE that is flagged (lost/extra full turn), never folded.
#   3. writes that DERIVED position into HOME_OFFSET of joint_{a,c}.inc -- regenerated every
#      launch from the param-file zero (NOT an independent stored zero; SSOT = head_zero.inc).
# The GUI reads HOME_OFFSET to show the position pre-home; HOME_ABSOLUTE_ENCODER homing
# (later) drives it to 0. Skip the read with RUN5_SKIP_PSO=1 (keeps the last HOME_OFFSET).
set -u
NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZERO="$NED/configs/params/head_zero.inc"
JA="$NED/configs/params/joint_a.inc"
JC="$NED/configs/params/joint_c.inc"
LOG="$NED/pso_home.log"
source "$NED/tools/ned_params.sh" >/dev/null 2>&1     # GEAR_A, GEAR_C (motor:axis)
R=67108864                                            # 2^26 counts/motor-rev
RANGE=315                                             # soft-limit display range

if [ "${RUN5_SKIP_PSO:-}" = 1 ]; then
  echo "$(date '+%F %T')  pso_home skipped (RUN5_SKIP_PSO=1)" >> "$LOG"; exit 0
fi

num(){ grep -E "^$1" "$ZERO" | grep -oE '[-0-9]+' | head -1; }
A_MT0=$(num A_MULTITURN); A_W0=$(num A_WITHIN)
C_MT0=$(num C_MULTITURN); C_W0=$(num C_WITHIN)

read_raw(){   # $1=A|C -> "mt w" or "NODATA"
  local out mt w
  out=$("$NED/tools/pso_read.sh" "$1" 2>/dev/null)
  mt=$(printf '%s\n' "$out" | grep -oE 'multiturn=[+-]?[0-9]+' | grep -oE '[+-]?[0-9]+$')
  w=$( printf '%s\n' "$out" | grep -oE 'within-turn=[0-9]+'    | grep -oE '[0-9]+$')
  { [ -n "$mt" ] && [ -n "$w" ] && echo "$mt $w"; } || echo NODATA
}

pos_deg(){   # $1=mt $2=w $3=mt0 $4=w0 $5=gear $6=sign(+1/-1, axis-positive convention) -> UNWRAPPED deg
  awk -v mt="$1" -v w="$2" -v m0="$3" -v w0="$4" -v G="$5" -v S="$6" -v R="$R" \
      'BEGIN{ printf "%+.2f", S*((mt-m0)*R+(w-w0))/(R*G)*360.0 }'
}

emit(){   # $1=A|C $2=mt0 $3=w0 $4=gear $5=LABEL $6=joint_inc $7=sign(+1/-1)
  local raw mt w p flag=""
  raw=$(read_raw "$1")
  if [ "$raw" = NODATA ]; then
    echo "  $5: NO DATA -> HOME_OFFSET=0"
    sed -i "s/^HOME_OFFSET = .*/HOME_OFFSET = 0.0/" "$6"
    return
  fi
  read -r mt w <<<"$raw"
  p=$(pos_deg "$mt" "$w" "$2" "$3" "$4" "$7")
  awk -v p="$p" -v r="$RANGE" 'BEGIN{exit !(p<=-r || p>=r)}' && flag="   *** OUTSIDE +/-${RANGE} (lost/extra turn?)"
  echo "  $5: raw(mt=$mt w=$w)  position = ${p} deg${flag}"
  sed -i "s/^HOME_OFFSET = .*/HOME_OFFSET = ${p}/" "$6"   # derived: read - param-zero
}

{
  echo "==== $(date '+%F %T')  pso_home (startup absolute, unwrapped +/-${RANGE}) ===="
  echo "  zero A(mt=$A_MT0,w=$A_W0)  C(mt=$C_MT0,w=$C_W0)   gears A=$GEAR_A C=$GEAR_C"
  emit A "$A_MT0" "$A_W0" "$GEAR_A" A "$JA" -1   # A: negate to match right-hand rule (paired with joint_a.inc SCALE flip)
  emit C "$C_MT0" "$C_W0" "$GEAR_C" C "$JC" +1   # C: right-hand-rule correct as-is
} 2>&1 | tee -a "$LOG"
