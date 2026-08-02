#!/bin/bash
# pso_offset.sh -- STAGE A, REPORT ONLY, MOVES NOTHING.
# Reads head A & C absolute via the PSO/SEN request and computes each axis's offset from
# the parameterized zero (configs/params/head_zero.inc, manual 6.12.6: PM = PE - PS).
#
# Run with LinuxCNC CLOSED (uses halrun; needs the board free). Requires:
#   - pso_abs comp installed once:   sudo halcompile --install tools/pso_abs.comp
#   - Pn515=8882 (SEN mode) on both head drives.
#
# Read sequence per axis is COPIED VERBATIM from tools/pso_read.sh (order is crucial --
# else C leaks in):  RX listening -> set R4 (output-05: 1=A, 0=C) -> SEN (output-04) OFF->ON
# LAST. PSO trails PAO/PBO, so SEN is held on with a long (8 s) listen window.
set -u
NED="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZERO="$NED/configs/params/head_zero.inc"
source "$NED/tools/ned_params.sh"          # GEAR_A, GEAR_C (motor:axis)
R=67108864                                  # 2^26 counts/motor-rev

num(){ grep -E "^$1" "$ZERO" | grep -oE '[-0-9]+' | head -1; }
A_MT=$(num A_MULTITURN); A_W=$(num A_WITHIN)
C_MT=$(num C_MULTITURN); C_W=$(num C_WITHIN)

read_one(){   # $1=R4 (1=A, 0=C)  -> echoes "multiturn within parsed"
  local R4=$1 HAL LOG
  HAL=$(mktemp /tmp/pso_off_XXXX.hal); LOG=$(mktemp /tmp/pso_off_XXXX.log)
  cat > "$HAL" <<EOF
loadrt hostmot2
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=10 num_pwmgens=6 num_stepgens=4 num_inmuxs=1 num_pktuarts=1 sserial_port_0=0xxxxxxx"
loadrt pso_abs names=hm2_7i97.0.pktuart.0
loadrt threads name1=servo period1=1000000
addf hm2_7i97.0.read              servo
addf hm2_7i97.0.pktuart.0.receive servo
addf hm2_7i97.0.write             servo
setp hm2_7i97.0.7i84.0.0.output-04 0
setp hm2_7i97.0.7i84.0.0.output-05 $R4
start
loadusr -w sleep 2
setp hm2_7i97.0.7i84.0.0.output-04 1
loadusr -w sleep 8
setp hm2_7i97.0.7i84.0.0.output-04 0
loadusr -w sleep 2
setp hm2_7i97.0.7i84.0.0.output-04 1
loadusr -w sleep 8
show pin hm2_7i97.0.pktuart.0
setp hm2_7i97.0.7i84.0.0.output-04 0
setp hm2_7i97.0.7i84.0.0.output-05 0
exit
EOF
  halrun -U >/dev/null 2>&1 || true
  timeout 70 halrun -f "$HAL" > "$LOG" 2>&1 || true
  halrun -U >/dev/null 2>&1 || true
  local mt w parsed
  mt=$(grep -E 'pktuart\.0\.multiturn$' "$LOG" | awk '{print $(NF-1)}' | tail -1)
  w=$(grep -E 'pktuart\.0\.within$'     "$LOG" | awk '{print $(NF-1)}' | tail -1)
  parsed=$(grep -E 'pktuart\.0\.parsed$' "$LOG" | awk '{print $(NF-1)}' | tail -1)
  rm -f "$HAL" "$LOG"
  echo "${mt:-} ${w:-} ${parsed:-0}"
}

report(){   # $1=LABEL $2=R4 $3=MT0 $4=W0 $5=GEAR
  local mt w parsed
  read -r mt w parsed < <(read_one "$2")
  if [ "${parsed:-0}" = 0 ] || [ -z "$mt" ]; then
    echo "$1: NO DATA (parsed=${parsed:-?}) -- Pn515=8882 on the drive? R4 routing? pso_abs installed?"
    return
  fi
  awk -v mt="$mt" -v w="$w" -v MT0="$3" -v W0="$4" -v G="$5" -v R="$R" -v L="$1" 'BEGIN{
    dc  = (mt-MT0)*R + (w-W0);
    deg = dc/(R*G)*360.0;
    cpd = R*G/360.0;
    printf "%s: live(mt=%d, w=%d)  zero(mt=%d, w=%d)  ->  offset = %+.4f axis-deg   [%.1f counts/axis-deg]\n", \
           L, mt, w, MT0, W0, deg, cpd;
  }'
}

{
  echo "==== $(date '+%F %T')  pso_offset (Stage A -- REPORT ONLY, nothing moves) ===="
  echo "  parameterized zero: A(mt=$A_MT, w=$A_W)   C(mt=$C_MT, w=$C_W)    gears A=$GEAR_A C=$GEAR_C"
  report A 1 "$A_MT" "$A_W" "$GEAR_A"
  report C 0 "$C_MT" "$C_W" "$GEAR_C"
  echo "  NOTE: offset SIGN vs axis-positive is UNVERIFIED -- check it against how far you hand-moved A/C."
} 2>&1 | tee -a "$NED/pso_offset.log"
