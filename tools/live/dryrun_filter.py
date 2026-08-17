#!/usr/bin/env python3
"""Build a DRY RUN copy of a g-code program.

Operator 2026-08-16: "i would like 3 options. XY only, no Z. XYZ, and a
toggle for programmed feeds and maximum speed" ... "thats actually 2 toggles
so 4 options".

    TOGGLE 1   Z         SUPPRESSED (XY only)  |  ACTIVE (XYZ)
    TOGGLE 2   FEEDS     PROGRAMMED            |  MAXIMUM

Four combinations, all from these two independent flags.

WHY A FILE REWRITE AND NOT A RUNTIME SETTING. Neither toggle can be done
live. LinuxCNC has no axis inhibit, so "no Z" only exists by removing the Z
words. And MAX_FEED_OVERRIDE is 2.0 on this machine
(configs/params/display_common.inc:11), so the override caps at twice the
programmed feed -- a 100 mm/min finishing pass would still crawl. Maximum
speed has to be written into the moves.

WHAT IS ALWAYS REMOVED, IN BOTH MODES: spindle start (M3/M4) and coolant
(M7/M8). A dry run that spins a cutter is not a dry run. M5 and M9 are kept,
so any explicit stop in the program still lands.

WHAT XY-ONLY ADDITIONALLY REMOVES: every Z word; tool length offsets
(G43/G43.1/G44 -- with no Z words they would still shift Z on the next move);
tool changes (M6 -- the ATC drives Z the length of the column); and canned
cycles (G73/G76/G81..G89 ARE Z motion by definition), which become a plain
G0 to the same X Y so the pattern is still traced. Z holds wherever the
operator parked it.

XYZ mode keeps all of that: with the part off the table it is a true air
cut, and the geometry is only correct if G43 and M6 are honoured.

EXPRESSIONS ARE HANDLED, NOT REFUSED. `G0 Z#<clear>` and
`G1 Z[0 - #<hdepth>]` are ordinary here -- alu_square.ngc alone has 37 such
lines -- so scan_words() consumes a balanced [...] or a #<name> as the word's
value and the whole word is cut out. Parameter ASSIGNMENTS (`#<z> = -5.0`)
pass through untouched, because X and Y lines may still reference them.

REFUSES rather than guesses: a COMPUTED g/m code (`M#<x>`) cannot be
classified, so the file is refused with the line numbers named. Silently
passing one through could leave a spindle start in a dry run.

    dryrun_filter.py IN.ngc OUT.ngc [--no-z] [--max-speed] [--ini FILE]
"""

import os
import re
import sys

# G-code words. Value may be signed, decimal, and G/M codes may carry a
# fractional part (G43.1, G59.3).
WORD = re.compile(r'([A-Za-z])\s*([-+]?[0-9]*\.?[0-9]+)')

# Motion that a stripped Z would leave with no axis word at all.
MOTION = ('G0', 'G00', 'G1', 'G01', 'G2', 'G02', 'G3', 'G03')
CANNED = ('G73', 'G76', 'G81', 'G82', 'G83', 'G84', 'G85', 'G86',
          'G87', 'G88', 'G89')
TLO    = ('G43', 'G43.1', 'G43.2', 'G44')

DEFAULT_MAX_FEED = 20000.0      # mm/min, only if the ini cannot be read


def split_comment(line):
    """Return (code, comment). ';' starts a comment; so does an unmatched '('.

    G-code comments are '(...)' inline and ';' to end of line. Only the part
    outside a paren is code -- a Z inside a comment is prose, not motion.
    """
    out, com, depth, i = [], [], 0, 0
    while i < len(line):
        ch = line[i]
        if ch == '(':
            depth += 1
            com.append(ch)
        elif ch == ')' and depth:
            depth -= 1
            com.append(ch)
        elif depth:
            com.append(ch)
        elif ch == ';':
            com.append(line[i:])
            return ''.join(out), ''.join(com)
        else:
            out.append(ch)
        i += 1
    return ''.join(out), ''.join(com)


def scan_words(code):
    """Tokenise into [(letter, value_text, start, end)].

    A word's value is NOT always a number on this machine. ned's programs are
    hand-written and parametric -- `G0 Z#<clear>`, `G1 Z[0 - #<hdepth>]` --
    and the first version of this filter refused all 37 such lines in
    alu_square.ngc, which made XY-only useless on exactly the files it was
    wanted for. So the value is read as one of:

        #<name> / #123 / ##5       a parameter reference
        [ ... ]                    a balanced expression, nesting allowed
        -1.5 / +.5 / 20            a plain number

    Returning the span lets a word be cut out whole, expression and all.
    """
    words, i, n = [], 0, len(code)
    while i < n:
        ch = code[i]
        if not ch.isalpha():
            i += 1
            continue
        letter, start, j = ch, i, i + 1
        while j < n and code[j] in ' \t':
            j += 1
        if j < n and code[j] == '[':
            depth, j = 0, j
            while j < n:
                if code[j] == '[':
                    depth += 1
                elif code[j] == ']':
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
        elif j < n and code[j] == '#':
            while j < n and code[j] == '#':
                j += 1
            if j < n and code[j] == '<':
                while j < n and code[j] != '>':
                    j += 1
                j += 1 if j < n else 0
            else:
                while j < n and (code[j].isdigit() or code[j] == '.'):
                    j += 1
        else:
            if j < n and code[j] in '+-':
                j += 1
            seen = False
            while j < n and (code[j].isdigit() or code[j] == '.'):
                j += 1
                seen = True
            if not seen:
                # a bare letter with no value -- leave it alone
                i = start + 1
                continue
        words.append((letter, code[start + 1:j].strip(), start, j))
        i = j
    return words


def cut_words(code, letters, also=None):
    """Remove every word whose letter is in `letters`, expression and all.

    `also` is an optional predicate (letter, value) -> bool for removing only
    specific G/M codes rather than every G or M on the line.
    """
    spans = []
    for letter, val, a, b in scan_words(code):
        up = letter.upper()
        if up in letters and (also is None or also(up, val)):
            spans.append((a, b))
    for a, b in reversed(spans):
        code = code[:a] + ' ' + code[b:]
    return code


def has_word(code, letters):
    return any(l.upper() in letters for l, _v, _a, _b in scan_words(code))


def codes(code):
    """Every G/M code on the line, normalised: 'G43.1', 'M6', 'G0'.

    Only literal G/M values count. `M#<x>` is a computed code -- it cannot be
    classified here, so it is left for the caller's refusal path rather than
    guessed at.
    """
    found, computed = [], []
    for letter, val, _a, _b in scan_words(code):
        if letter.upper() not in 'GM':
            continue
        try:
            f = float(val)
        except ValueError:
            computed.append('%s%s' % (letter.upper(), val))
            continue
        v = ('%g' % f)
        found.append('%s%s' % (letter.upper(), v))
    return found, computed


def read_max_feed(ini_path):
    """Machine max feed in mm/min, from the ini's own numbers (CLAUDE.md
    rule 11 -- never a re-typed literal). [TRAJ]MAX_LINEAR_VELOCITY is in
    machine units per SECOND."""
    if not ini_path or not os.path.exists(ini_path):
        return DEFAULT_MAX_FEED, 'default (no ini given)'
    best = None
    try:
        with open(ini_path, encoding='utf-8', errors='replace') as fh:
            for ln in fh:
                ln = ln.split('#')[0].strip()
                if ln.upper().startswith('MAX_LINEAR_VELOCITY'):
                    try:
                        v = float(ln.split('=', 1)[1])
                    except (IndexError, ValueError):
                        continue
                    best = v if best is None else min(best, v)
    except OSError:
        return DEFAULT_MAX_FEED, 'default (ini unreadable)'
    if best is None:
        return DEFAULT_MAX_FEED, 'default (no MAX_LINEAR_VELOCITY)'
    return best * 60.0, '%s MAX_LINEAR_VELOCITY=%g units/s' % (
        os.path.basename(ini_path), best)


def filter_program(lines, no_z, max_speed, max_feed):
    """Return (out_lines, stats, refusals)."""
    out, refusals = [], []
    st = {'z': 0, 'tlo': 0, 'm6': 0, 'canned': 0, 'spindle': 0,
          'coolant': 0, 'g1_to_g0': 0, 'feed': 0, 'dropped': 0}

    for n, raw in enumerate(lines, 1):
        line = raw.rstrip('\n')
        code, com = split_comment(line)

        if not code.strip():
            out.append(line)
            continue

        # o-words are flow control; never rewrite them.
        # THE ANCHOR MATTERS. This was `\s*[Oo]\b`, which does not match `o5`
        # -- 'o' and '5' are both word characters, so there is no boundary
        # between them -- and every numbered o-word line fell through to the
        # word scanner. There, `o100 if [#<x> GT 1]` tokenises the `f` of
        # `if` as an F word whose value is the balanced `[...]`, so the
        # max-speed branch rewrote the F and left `i`, and rs274 said
        # "Left bracket missing after 'if'". Match the digit or '<' instead.
        if re.match(r'\s*[Oo][0-9<]', code):
            out.append(line)
            continue

        # A parameter ASSIGNMENT is not motion -- `#<z> = -5.0` must survive
        # untouched in XY-only mode, because X and Y lines may still use it.
        if code.lstrip().startswith('#'):
            out.append(line)
            continue

        cs, computed = codes(code)
        if computed:
            # A computed G/M code cannot be classified, so it cannot be
            # honestly filtered. Name it rather than pass it through.
            refusals.append((n, line.strip(), 'computed code %s'
                             % ' '.join(computed)))
            out.append(line)
            continue

        new = code
        note = []

        # --- always: no spindle, no coolant ---------------------------
        if 'M3' in cs or 'M4' in cs:
            new = cut_words(new, 'M', lambda l, v: v.strip('0 ') in ('3', '4'))
            st['spindle'] += 1
            note.append('spindle start removed')
        if 'M7' in cs or 'M8' in cs:
            new = cut_words(new, 'M', lambda l, v: v.strip('0 ') in ('7', '8'))
            st['coolant'] += 1
            note.append('coolant removed')

        # --- XY only ---------------------------------------------------
        if no_z:
            if any(c in cs for c in CANNED):
                # A canned cycle IS Z motion. Keep the X Y so the pattern is
                # still traced, at rapid, and drop the rest of the cycle.
                xy = [(l, v) for l, v, _a, _b in scan_words(new)
                      if l.upper() in 'XY']
                st['canned'] += 1
                if xy:
                    new = 'G0 ' + ' '.join('%s%s' % (l.upper(), v) for l, v in xy)
                    note.append('canned cycle -> G0 X Y')
                else:
                    new = ''
                    st['dropped'] += 1
                    note.append('canned cycle dropped, no X Y on the line')
            else:
                if any(c in cs for c in TLO):
                    new = cut_words(new, 'GH',
                                    lambda l, v: l == 'H' or v.startswith('4'))
                    st['tlo'] += 1
                    note.append('tool length offset removed')
                if 'M6' in cs:
                    new = cut_words(new, 'M', lambda l, v: v.strip('0 ') == '6')
                    st['m6'] += 1
                    note.append('tool change removed')
                if has_word(new, 'Z'):
                    new = cut_words(new, 'Z')
                    st['z'] += 1
                    note.append('Z removed')
                    # A motion word with every axis stripped is an error, not
                    # a no-op: "G53 G0 Z0" becomes "G53 G0".
                    if (any(c in cs for c in MOTION)
                            and not has_word(new, 'XYABCUVW')):
                        new = ''
                        st['dropped'] += 1
                        note[-1] = 'Z-only move dropped'

        # --- maximum speed ---------------------------------------------
        if max_speed and new.strip():
            if 'G1' in cs:
                # A straight feed move at maximum speed IS a rapid. G0 uses
                # the machine's own rapid rate, which is the real ceiling --
                # a large F would still be clipped per axis.
                new = cut_words(new, 'GF', lambda l, v: l == 'F' or v == '1')
                new = 'G0 ' + new.strip()
                st['g1_to_g0'] += 1
                note.append('G1 -> G0 (rapid)')
            elif has_word(new, 'F'):
                # Arcs have no rapid form, so they get the max feed instead.
                new = cut_words(new, 'F') + ' F%.1f' % max_feed
                st['feed'] += 1
                note.append('F -> %.1f' % max_feed)

        new = re.sub(r'\s+', ' ', new).strip()
        if note:
            tag = '(DRY RUN: %s)' % ', '.join(note)
            out.append(('%s %s %s' % (new, com, tag)).strip())
        else:
            out.append(line)

    return out, st, refusals


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    flags = [a for a in argv[1:] if a.startswith('--')]
    if len(args) < 2:
        sys.stderr.write(__doc__)
        return 2
    src, dst = args[0], args[1]
    no_z = '--no-z' in flags
    max_speed = '--max-speed' in flags
    ini = None
    for f in flags:
        if f.startswith('--ini='):
            ini = f.split('=', 1)[1]

    max_feed, feed_src = read_max_feed(ini)

    with open(src, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().splitlines()

    out, st, refusals = filter_program(lines, no_z, max_speed, max_feed)

    if refusals:
        sys.stderr.write(
            'REFUSED: %d line(s) could not be filtered honestly. '
            'Nothing written.\n' % len(refusals))
        for n, t, why in refusals[:10]:
            sys.stderr.write('  line %d: %s   [%s]\n' % (n, t, why))
        return 1

    head = [
        '(DRY RUN COPY -- generated, do not edit. Source: %s)'
        % os.path.basename(src),
        '(Z %s   FEEDS %s)'
        % ('SUPPRESSED - XY only, Z holds where it is' if no_z else 'ACTIVE - full XYZ',
           'MAXIMUM - G1 became G0' if max_speed else 'PROGRAMMED - as posted'),
        '(Spindle start and coolant are removed in every dry run.)',
        '(Changed: %s)' % ', '.join('%s=%d' % (k, v)
                                    for k, v in sorted(st.items()) if v),
        '(Max feed for arcs: %.1f mm/min, from %s)' % (max_feed, feed_src),
        '',
    ]
    with open(dst, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(head + out) + '\n')

    print('wrote %s' % dst)
    print('  Z %s, feeds %s'
          % ('SUPPRESSED' if no_z else 'ACTIVE',
             'MAXIMUM' if max_speed else 'PROGRAMMED'))
    for k, v in sorted(st.items()):
        if v:
            print('  %-10s %d' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
