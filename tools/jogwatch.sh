#!/bin/bash
# JOGWATCH -- catch the axis-switch runaway in the act.
#
# Operator 2026-08-16: "as i switch from mpg jog X to mpg jog y, X continues to
# move as mpg for Y is jogged" ... "ive never noticed this before until last
# night's fixes".
#
# Static analysis says the mechanism is stock LinuxCNC -- a wheel jog banks a
# POSITION target in teleop_tp/free_tp, and axis.c:394 / control.c:1089 only
# skip ADDING new distance when jog-enable drops; neither cancels what is
# already banked. It also says no commit since 2026-08-15 touched the jog path.
# Those two statements cannot both explain "new last night", so this measures
# instead of arguing.
#
# WHAT IT ANSWERS, in one capture:
#   1. Are two jog-enables ever TRUE at the same instant? (the pendant writes
#      them one at a time in AXES order, so Y->X has a both-true window)
#   2. After X's enable drops, how much further does X actually travel, and
#      for how long? That is the banked target being paid out.
#   3. Is the wheel still feeding X counts after the switch?
#
# RUN IT, THEN REPRODUCE: select X, spin the wheel, switch to Y, keep spinning.
# Ctrl-C when done. It prints a summary and leaves the raw samples behind.

OUT=${1:-/home/brains/Documents/ned/logs/jogwatch-$(date +%H%M%S).csv}
mkdir -p "$(dirname "$OUT")"

PINS="axis.x.jog-enable axis.y.jog-enable axis.z.jog-enable \
axis.x.jog-counts axis.y.jog-counts \
axis.x.jog-scale axis.y.jog-scale \
hm2_7i97.0.encoder.04.count \
motion.jog-inhibit"

echo "jogwatch: sampling to $OUT   -- Ctrl-C to stop and summarise"
echo "t,xen,yen,zen,xcnt,ycnt,xscale,yscale,wheel,inhibit,xpos,ypos" > "$OUT"

# halcmd once per sample is far too slow; ask for every pin in ONE call and
# read positions from the NML status buffer in the same loop.
python3 - "$OUT" <<'PY' &
import subprocess, sys, time
out = open(sys.argv[1], 'a')
import linuxcnc
s = linuxcnc.stat()
pins = ("axis.x.jog-enable axis.y.jog-enable axis.z.jog-enable "
        "axis.x.jog-counts axis.y.jog-counts axis.x.jog-scale "
        "axis.y.jog-scale hm2_7i97.0.encoder.04.count "
        "motion.jog-inhibit").split()
t0 = time.monotonic()
try:
    while True:
        r = subprocess.run(['halcmd', '-s', 'show', 'pin'] + pins,
                           capture_output=True, text=True, timeout=5)
        vals = {}
        for ln in r.stdout.splitlines():
            f = ln.split()
            if len(f) >= 5:
                vals[f[4]] = f[3]
        s.poll()
        out.write('%.4f,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.4f,%.4f\n' % (
            time.monotonic() - t0,
            vals.get('axis.x.jog-enable'), vals.get('axis.y.jog-enable'),
            vals.get('axis.z.jog-enable'), vals.get('axis.x.jog-counts'),
            vals.get('axis.y.jog-counts'), vals.get('axis.x.jog-scale'),
            vals.get('axis.y.jog-scale'),
            vals.get('hm2_7i97.0.encoder.04.count'),
            vals.get('motion.jog-inhibit'),
            s.actual_position[0], s.actual_position[1]))
        out.flush()
        time.sleep(0.005)
except KeyboardInterrupt:
    pass
PY
WATCHER=$!
trap 'kill $WATCHER 2>/dev/null' INT TERM
wait $WATCHER

echo
echo "=== both enables TRUE at once? ==="
awk -F, 'NR>1 && $2=="TRUE" && $3=="TRUE" {n++} END{print (n?n" sample(s) -- BOTH X AND Y ENABLED":"never")}' "$OUT"
echo "=== X travel AFTER its enable dropped ==="
awk -F, 'NR>1{
  if (p=="TRUE" && $2=="FALSE") { t=$1; x=$11; armed=1 }
  if (armed && $2=="FALSE") { d=$11-x; if (d<0) d=-d; if (d>m) {m=d; dt=$1-t} }
  if ($2=="TRUE") armed=0
  p=$2
} END{ printf "  moved %.4f mm over %.2f s after jog-enable went FALSE\n", m, dt }' "$OUT"
echo
echo "raw samples: $OUT"
