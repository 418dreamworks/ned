#!/usr/bin/env python3
"""Mechanical checks from docs/gcode_rules.md, run before rs274 ever sees
the file.

WHY THIS EXISTS: rs274 catches these too, but only when the operator presses
Cycle Start, and its message names no line number. "Unclosed comment found"
was handed to the operator three times on this project, twice in one
afternoon, each time costing a run. Every rule below is one that has
actually broken a cycle here.

    tools/live/gcode_lint.py FILE [FILE...]

Exit 0 clean, 1 if anything failed. Prints file:line for every finding.
"""
import re
import sys


def strip_semicolon_comment(line):
    """Remove a `;` comment, but only when the `;` is not inside parens.

    `;` runs to end of line and may legally contain unbalanced parentheses,
    so it has to come off before the paren check or every explanatory
    comment in the tree reads as an error.
    """
    depth = 0
    for i, ch in enumerate(line):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == ';' and depth == 0:
            return line[:i]
    return line


def check(path):
    bad = []
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
    except Exception as e:
        return [(0, 'UNREADABLE', str(e))]

    owords = {}
    subs = []
    for n, raw in enumerate(lines, 1):
        code = strip_semicolon_comment(raw)

        # RULE 1.1 -- a (...) comment opens and closes on its own line
        if code.count('(') != code.count(')'):
            bad.append((n, 'UNCLOSED COMMENT',
                        'rule 1.1: a (...) comment must open AND close on its '
                        'own line -- rs274 says "Unclosed comment found" and '
                        'names no line'))
            continue

        # RULE 1.2 -- no parens inside a comment
        for m in re.finditer(r'\(([^()]*)\)', code):
            inner = m.group(1)
            if '(' in inner or ')' in inner:
                bad.append((n, 'NESTED PAREN',
                            'rule 1.2: the first ) ends the comment and the '
                            'rest of the line becomes g-code'))

        # RULE 2.1 -- % truncates an operator message
        for m in re.finditer(r'\((?:PRINT|DEBUG|abort|msg)\s*,([^)]*)\)',
                             code, re.I):
            if '%' in m.group(1):
                bad.append((n, 'PERCENT IN MESSAGE',
                            'rule 2.1: PRINT/DEBUG substitute #<var> only; a '
                            '%% ends the message at that point'))

        # RULE 3.5 -- an o-word is oNNN or o<name>, never a digit-letter mix
        # (2026-08-12: o41a reached the machine and LinuxCNC answered
        # "Unknown control command in o", which names neither the line nor
        # the word. It parses o41, then chokes on the a.)
        m = re.match(r'\s*o(\d+[A-Za-z_]\w*)\b', code)
        if m:
            bad.append((n, 'MALFORMED O-WORD',
                        'rule 3.5: "o%s" is neither oNNN nor o<name> -- '
                        'LinuxCNC says "Unknown control command in o" and '
                        'names no line' % m.group(1)))

        # RULE 3.2 -- o-word numbers unique per file
        m = re.match(r'\s*o(\d+)\s+(if|while|sub|repeat|do)\b', code, re.I)
        if m:
            num, kind = m.group(1), m.group(2).lower()
            # A do-while CLOSES with `oN while`, so that pairing is legal
            # and is not a duplicate. Only a second OPENER on the same
            # number is.
            if num in owords and not (kind == 'while'
                                      and owords[num][0] == 'do'):
                bad.append((n, 'DUPLICATE O-WORD',
                            'rule 3.2: o%s already opened a %s at line %d -- '
                            'the interpreter pairs the wrong endif silently'
                            % (num, owords[num][0], owords[num][1])))
            else:
                owords[num] = (kind, n)

        m = re.match(r'\s*o<([^>]+)>\s+sub\b', code, re.I)
        if m:
            subs.append((m.group(1), n))

    # RULE 3.1 -- one sub per file
    if len(subs) > 1:
        for name, n in subs[1:]:
            bad.append((n, 'SECOND SUB IN FILE',
                        'rule 3.1: LinuxCNC resolves o-words one per file; '
                        'o<%s> belongs in its own file (first sub o<%s> is at '
                        'line %d)' % (name, subs[0][0], subs[0][1])))
    return bad


# HARD = the file will not run. WARN = it runs but says the wrong thing.
# Split because a whole-tree sweep that fails on every legacy style finding
# blocks every edit and gets switched off, which is worse than no linter.
HARD = {'UNCLOSED COMMENT', 'NESTED PAREN', 'DUPLICATE O-WORD',
        'MALFORMED O-WORD',
        'SECOND SUB IN FILE', 'UNREADABLE'}


def main(argv):
    files = [a for a in argv[1:] if not a.startswith('-')]
    warn_only = '--warn-only' in argv
    if not files:
        print(__doc__)
        return 2
    rc = 0
    nwarn = 0
    for path in files:
        for n, kind, why in check(path):
            hard = kind in HARD and not warn_only
            if hard:
                rc = 1
            else:
                nwarn += 1
            print('%s%s:%d: %s -- %s'
                  % ('' if hard else 'warn ', path, n, kind, why))
    if rc == 0:
        print('gcode_lint: %d file(s) pass (%d warning(s))' % (len(files), nwarn))
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
