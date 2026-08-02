#!/bin/bash
# watch_encoders.sh
# Live stream of ALL SIX encoder raw counters (pre-scale FPGA quadrature counts).
# HOLDS until Ctrl-C. Turn ONE axis (or spin the MPG handwheel) by hand and watch
# which enc.NN column changes — that is the channel that input is physically read on.
# rawcounts is the raw FPGA counter: the truest "is this input alive" read.
#   enc0=X  enc1=Y  enc2=Z  enc3=W  enc4=MPG  enc5=spare   (current HAL labels)
P=hm2_7i97.0
trap 'echo; echo "stopped"; exit' INT TERM
[ "$(halcmd getp $P.io_error 2>/dev/null)" = "TRUE" ] && { echo "io_error TRUE -> restart LinuxCNC"; exit 1; }
echo "Spin the MPG / turn one axis. Watch which enc.NN 'd=' moves. Ctrl-C to stop."
echo "  enc0=X  enc1=Y  enc2=Z  enc3=W  enc4=MPG  enc5=spare"
for n in 0 1 2 3 4 5; do b[$n]=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null); done
while true; do
  line=""
  for n in 0 1 2 3 4 5; do
    r=$(halcmd getp $P.encoder.0$n.rawcounts 2>/dev/null)
    line+=$(printf "e%s d=%-7s " "$n" "$(( r - ${b[$n]:-0} ))")
  done
  printf "\r%s" "$line"
  sleep 0.2
done
