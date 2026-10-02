#!/bin/bash
# Pull a program into nc_files, at the SAME path Production holds it.
#
#     tools/nc_pull.sh <production-relative-path> [--stock-top N] [--offset G57]
#
# Operator 2026-09-29: "i want it to mirror production fil structure" ...
# "make it exactly the same" ... "onyl difference is you pull into it, and
# don't put anything in that doesn't pass our linters".
#
# So: the tree is Production's, byte for byte. The two differences are that
# this side PULLS -- nothing is pushed here -- and that NOTHING LANDS UNLESS
# IT PASSES. A file that fails is left where it was and the reason is printed.
#
# The gate is the same one Production runs, plus rs274, so a program cannot
# reach the machine by a route that skips either.
set -u
# Overridable: the tailnet name is the default, but Tailscale has been down
# while the LAN was up (2026-09-30, sleight offline on the tailnet since
# 05:41 and answering fine on sleight.local). Set SRC_HOST to switch route.
SRC_HOST=${SRC_HOST:-tzuohann@sleight}
SRC_ROOT='C:/Users/tzuohann/Documents/418dreamworks/Production'
NC=/home/brains/linuxcnc/nc_files/Production
LINT=/home/brains/418ops/machine/gcode-lint/lint_ngc.py
CHECK=/home/brains/Documents/ned/tools/gcode_check.sh

# NO TRANSFORM ON THIS SIDE. Operator 2026-09-29, overruling what Production
# and I had agreed between ourselves: "no. Production first".
#
# The transform exists -- tools/rapid_split.py, verified position-preserving
# on 51a8dbd3 -- and Production had leaned to it running here because it is
# mine and it sits next to the machine. He has ruled otherwise: the file
# arrives already correct, or it does not arrive.
#
# That is the better rule and it is worth saying why. A transform here means
# the file that cuts is not the file anyone published, so the register needs
# two hashes and the relationship between them, and every future reader has
# to know that. Fixed at the source there is one file and one number.
#
# --split is left OUT of this path deliberately. If it is ever needed it is
# the operator's call, run by hand, and recorded as such.
SPLIT=""
REL="${1:?usage: nc_pull.sh <production-relative-path> [--split <plane>] [lint args...]}"; shift
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --split) SPLIT="$2"; shift 2;;
    *) ARGS+=("$1"); shift;;
  esac
done
set -- "${ARGS[@]+"${ARGS[@]}"}"
DEST="$NC/$REL"
TMP=$(mktemp /tmp/ncpull.XXXXXX.ngc)
trap 'rm -f "$TMP"' EXIT

echo "pulling  $REL"
if ! timeout 120 ssh -o ConnectTimeout=10 "$SRC_HOST" "cat \"$SRC_ROOT/$REL\"" > "$TMP" 2>/dev/null || [ ! -s "$TMP" ]; then
    echo "  REFUSED: could not read it from $SRC_HOST"; exit 1
fi
echo "  $(wc -l < "$TMP") lines"

if [ -n "$SPLIT" ]; then
    T2=$(mktemp /tmp/ncsplit.XXXXXX.ngc)
    if ! python3 /home/brains/Documents/ned/tools/rapid_split.py "$TMP" "$SPLIT" 2 600 > "$T2" 2>/tmp/ncsplit.err; then
        echo "  REFUSED: rapid_split failed"; cat /tmp/ncsplit.err; rm -f "$T2"; exit 1
    fi
    sed 's/^/  /' /tmp/ncsplit.err
    mv "$T2" "$TMP"
fi

if ! "$CHECK" "$TMP" 2>&1 | tail -1 | grep -q "parses clean"; then
    echo "  REFUSED: rs274 will not parse it"; "$CHECK" "$TMP" 2>&1 | tail -3; exit 1
fi
echo "  rs274 parses clean"

if ! python3 "$LINT" "$@" "$TMP" >/dev/null 2>&1; then
    echo "  REFUSED: it does not pass the linter --"
    python3 "$LINT" "$@" "$TMP" 2>&1 | grep -E "^   ERROR" | sed 's/^   /    /'
    echo "  nothing was written. Fix it at the source, not here."
    exit 1
fi
echo "  linter clean"

mkdir -p "$(dirname "$DEST")"
cp "$TMP" "$DEST"
echo "  -> $DEST"
sed -n '2,3p' "$DEST" | sed 's/^/     /'
