#!/bin/bash
# On-demand absolute read of head A or C via the SEN request line (NO servopack power-cycle).
# Requires Pn515=8882 (SEN mode) on both head drives.  Usage:  tools/pso_read.sh A|C
#
# Sequence (order is crucial -- else C leaks in):
#   RX listening  ->  R4 to target (OUTPUT5: 0=C via NC, 1=A via NO)  ->  SEN OFF->ON pulse.
# PSO trails PAO/PBO (manual 6.12.4), so we hold SEN on with a long (8 s) listen window.
set -e
DRIVE=${1:-C}
case "$DRIVE" in
  A|a) R4=1; LABEL=A ;;
  C|c) R4=0; LABEL=C ;;
  *) echo "usage: $0 A|C"; exit 1 ;;
esac
HAL=$(mktemp /tmp/pso_read_XXXX.hal); LOG=$(mktemp /tmp/pso_read_XXXX.log)
cat > "$HAL" <<EOF
loadrt hostmot2
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=10 num_pwmgens=6 num_stepgens=4 num_inmuxs=1 num_pktuarts=1 sserial_port_0=0xxxxxxx"
loadrt pso_sniff names=hm2_7i97.0.pktuart.0
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
python3 - "$LOG" "$LABEL" <<'PY'
import re,sys
log,drive=sys.argv[1],sys.argv[2]; frames=[]
for ln in open(log):
    if "PSO frame" in ln:
        s="".join(chr(int(h,16)&0x7f) for h,_ in re.findall(r'([0-9a-f]{2})(.)', ln.split(":",1)[1]))
        frames+=re.findall(r'P[+-]\d{5},\d{8}', s)
if not frames:
    print(f"{drive}: NO DATA  (check Pn515=8882 on the drive + R4 routing)"); sys.exit(1)
f=frames[-1]; m=re.match(r'P([+-])(\d{5}),(\d{8})',f)
print(f"{drive}: {f}   multiturn={m.group(1)}{int(m.group(2))}  within-turn={int(m.group(3))}  ({len(frames)} frames)")
PY
rm -f "$HAL" "$LOG"
