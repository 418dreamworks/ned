#!/bin/bash
# pso_live_gate.sh -- SAFETY GATE for the (unproven) live in-config PSO reader.
# Runs BOARD-FREE (called by run5.sh after pso_home.sh, before linuxcnc launches -- board is
# free then). It A/B-proves tools/pso_live.comp on the real board WITHOUT the risk of it going
# into the live servo thread first: it loads hostmot2+hm2_eth+pso_live in a throwaway halrun,
# holds SEN high, points R4 at C, runs ~2 s, and checks the result.
#
#   PASS  = pso_live parsed >0 frames  AND  ZERO occurrences of the sserial-collision signatures
#           ("llio->read in realtime", "local error", "Watchdog has bit").
#           -> writes the ACTIVE wiring (copy of configs/ned5/pso_live.hal) into $1.
#   FAIL / comp-not-installed / any error
#           -> writes a NO-OP $1 and echoes a loud warning (stdout is tee'd to lcnc.log by run5).
#
# So the live reader is active in a session ONLY if it passed this proof that same launch;
# otherwise the config silently falls back to the board-free pso_home snapshot. Never touches
# the board while LinuxCNC is running (run5 guarantees the board is free at call time).
set -u
NED="/home/brains/Documents/ned"
GEN="${1:-$NED/configs/ned5/pso_live_gen.hal}"
SRC="$NED/configs/ned5/pso_live.hal"
STAMP="$(date '+%F %T')"

noop(){  # $1 = reason
  { echo "# pso_live_gen.hal -- GENERATED $STAMP : NO-OP (live reader OFF)"
    echo "# reason: $1"
  } > "$GEN"
  echo "!!!! PSO-LIVE GATE: live reader DISABLED this launch -- $1"
  echo "!!!! Falling back to the board-free pso_home snapshot (safe)."
}

# comp must be installed (needs a one-time: sudo halcompile --install tools/pso_live.comp)
if ! ls /usr/lib/linuxcnc/modules/pso_live.so >/dev/null 2>&1 \
   && ! ls /usr/lib/linuxcnc/uspace/modules/pso_live.so >/dev/null 2>&1; then
  noop "pso_live.so not installed (run: sudo halcompile --install $NED/tools/pso_live.comp)"
  exit 0
fi

HAL=$(mktemp /tmp/pso_gate_XXXX.hal); OUT=$(mktemp /tmp/pso_gate_XXXX.log)
cat > "$HAL" <<'EOF'
loadrt hostmot2
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=10 num_pwmgens=6 num_stepgens=4 num_inmuxs=1 num_pktuarts=1 sserial_port_0=0xxxxxxx"
loadrt pso_live names=hm2_7i97.0.pktuart.0
loadrt threads name1=servo period1=1000000
addf hm2_7i97.0.read               servo
addf hm2_7i97.0.pktuart.0.pso-live servo
addf hm2_7i97.0.write              servo
# SEN must go LOW->HIGH *after* the threads are running: the rising edge is what makes the
# pack emit its absolute frame. (Setting it high before `start` gives no edge -> parsed=0.)
setp hm2_7i97.0.7i84.0.0.output-04 0
setp hm2_7i97.0.7i84.0.0.output-05 0
start
loadusr -w sleep 1
setp hm2_7i97.0.7i84.0.0.output-04 1
loadusr -w sleep 8
show pin hm2_7i97.0.pktuart.0.parsed
stop
exit
EOF

halrun -U >/dev/null 2>&1 || true
timeout 40 halrun -f "$HAL" > "$OUT" 2>&1 || true
# best-effort kernel ring buffer too (uspace rtapi msgs also land on stderr, captured above)
dmesg 2>/dev/null | tail -80 >> "$OUT" || true
halrun -U >/dev/null 2>&1 || true

PARSED=$(grep -E 'pktuart\.0\.parsed' "$OUT" | awk '{print $(NF-1)}' | tail -1)
[ -n "$PARSED" ] || PARSED=0
BAD=$(grep -cE 'llio->read in realtime|local error|Watchdog has bit' "$OUT")

echo "==== $STAMP  pso_live gate: parsed=$PARSED  collision-signatures=$BAD ===="
if [ "$PARSED" -gt 0 ] 2>/dev/null && [ "$BAD" -eq 0 ]; then
  { echo "# pso_live_gen.hal -- GENERATED $STAMP : ACTIVE (A/B self-test PASSED: parsed=$PARSED, 0 errors)"
    echo "# source: configs/ned5/pso_live.hal  (do not hand-edit -- regenerated every launch)"
    cat "$SRC"
  } > "$GEN"
  echo "==== PSO-LIVE GATE: PASSED -> live reader ACTIVE this launch."
else
  noop "A/B self-test FAILED (parsed=$PARSED, collision-signatures=$BAD)"
fi
rm -f "$HAL" "$OUT"
