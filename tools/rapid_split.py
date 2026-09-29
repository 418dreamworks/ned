#!/usr/bin/env python3
"""Split every rapid that ends below the stock top into rapid-across, feed-down.

    rapid_split.py <in.ngc> <stock_top> [clearance] [plunge_feed] > out.ngc

WHY THIS EXISTS. Production, 2026-09-29, after measuring five CAM levers one
at a time: "a swarf has no plane between retract and cut, so its link descends
at rapid to wherever the next pass begins -- and that face starts 6 mm below
the stock top" ... "either that toolpath gets restructured in a way we have
not found, or D3 and a 5-axis swarf are incompatible on a face that starts
below the stock top."

They are not incompatible. The CAM cannot express the move, but the move is
expressible -- it is two moves instead of one:

    G0 X.. Y.. A.. C.. Z<plane+clearance>     across, in the clear
    G1 Z<target> F<plunge>                    down, at feed

D3 asks that a RAPID not end inside the material. It does not ask the tool to
stay out; it asks the tool to arrive under control. Feeding the last few
millimetres costs seconds and removes the whole class.

WHAT IT DOES NOT TOUCH. Only G0 blocks whose Z ends below the plane. Every
cutting move is passed through byte for byte, which is the thing to verify:
run rs274 before and after and diff the canonical output -- the feeds must be
identical and only the approaches may differ.

MODAL SAFETY. Emitting a G1 changes the modal group. Any following motion
block that carried no G-word was relying on the old modal G0, so it is given
an explicit G0. Nothing is left to inference.
"""
import os
import re
import sys


def split(lines, plane, clear, plunge):
    out, mode, cur = [], None, {"X": None, "Y": None, "Z": None}
    pending_restore = False
    n_split = 0
    for raw in lines:
        code = re.sub(r"\([^)]*\)", "", raw.split(";")[0]).strip().upper()
        g = re.search(r"\bG0?([0123])\b", code)
        has_gword = g is not None
        if has_gword:
            mode = int(g.group(1))
        mz = re.search(r"\bZ(-?\d*\.?\d+)", code)
        is_g53 = bool(re.search(r"\bG53\b", code))
        moves = bool(re.search(r"\b[XYZ](-?\d|#|\[)", code))

        # A MOTION BLOCK THAT LOST ITS MODAL G0 TO A SPLIT WE JUST MADE.
        # It is restored ONLY if it carries no G-word of its own, and the
        # flag is cleared on the first motion block either way. The first
        # version cleared it only in the no-G-word case, so once a G1 came
        # past it kept prefixing G0 onto later blocks and turned 739 cutting
        # moves into rapids -- D3 went from 6 errors to 745. Caught by
        # running the check after the transform instead of trusting it.
        if pending_restore and moves and not is_g53:
            if not has_gword:
                raw = re.sub(r"^(\s*)", r"\1G0 ", raw, count=1)
            pending_restore = False

        # A CANNED CYCLE'S Z IS THE HOLE BOTTOM, NOT A RAPID TARGET.
        # G81/G83 and friends descend at feed by definition and carry their
        # own R retract plane. Splitting one destroys the cycle -- the first
        # version of this rewrote a G83 into nonsense. Leave them alone; D3
        # does not fire on them either, because the motion word is G8x.
        canned = bool(re.search(r"\bG(7[3-6]|8[0-9])\b", code))

        if (mode == 0 and mz and not is_g53 and not canned
                and float(mz.group(1)) < plane - 1e-9):
            # THE ORIGINAL Z STRING, NOT A REFORMATTED FLOAT. Writing
            # "%.4f" would silently round a post that emits five decimals,
            # and Design's question is exactly this: does the feed-down END
            # WHERE THE RAPID ENDED, or merely somewhere below the plane?
            # Carrying the characters through makes it the same number by
            # construction rather than by tolerance. 2026-09-29.
            target = mz.group(1)
            body = raw.rstrip("\n")
            # the same line, but held at the clear height
            across = re.sub(r"\bZ-?\d*\.?\d+", "Z%.4f" % (plane + clear),
                            body, flags=re.I)
            if not re.search(r"\bG0?0\b", across, re.I):
                # after any N word, never before it
                across = re.sub(r"^(\s*(?:N\d+\s*)?)", r"\1G0 ", across,
                                count=1)
            out.append(across + "\n")
            out.append("G1 Z%s F%.1f\n" % (target, plunge))
            n_split += 1
            pending_restore = True
            continue
        out.append(raw)
    return out, n_split


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path = sys.argv[1]
    plane = float(sys.argv[2])
    clear = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    plunge = float(sys.argv[4]) if len(sys.argv) > 4 else 600.0
    lines = open(path).read().splitlines(True)
    out, n = split(lines, plane, clear, plunge)
    sys.stderr.write("rapid_split: %d rapid(s) below Z%.4f split into "
                     "across-at-Z%.4f + feed-down at F%.1f\n"
                     % (n, plane, plane + clear, plunge))
    # A HEADER OF ITS OWN. Rule 3.7 -- and a transformed file is not the
    # file that was delivered, so it has to say so on its own first page.
    # Operator 2026-09-29: 'i need to know what is at the top of the file i
    # know thats the one you intend for me to run'.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ngc_revision import revision_lines
    changed = ('rapid_split from %s: %d rapids below Z%.4f split into '
               'across-at-Z%.4f + feed-down at F%.1f'
               % (os.path.basename(path), n, plane, plane + clear, plunge))
    hdr = revision_lines(out, 'rapid_split.py', changed)
    body = ''.join(out)
    if body.lstrip().startswith('%'):
        first, rest = body.split('\n', 1)
        sys.stdout.write(first + '\n' + '\n'.join(hdr) + '\n' + rest)
    else:
        sys.stdout.write('\n'.join(hdr) + '\n' + body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
