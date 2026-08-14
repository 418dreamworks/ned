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
    # RULE 6.1 state: has an M3/M4 been issued with no M5 since?
    spin_on = 0          # line number that started it, 0 = stopped
    for n, raw in enumerate(lines, 1):
        code = strip_semicolon_comment(raw)

        # RULE 1.1 -- a (...) comment opens and closes on its own line
        if code.count('(') != code.count(')'):
            bad.append((n, 'UNCLOSED COMMENT',
                        'rule 1.1: a (...) comment must open AND close on its '
                        'own line -- rs274 says "Unclosed comment found" and '
                        'names no line'))
            continue

        # RULE 1.2 -- no parens inside a comment.
        # DEPTH-COUNTED, not pair-matched (2026-08-13). The old version
        # scanned for innermost (...) pairs, so "(A (B) C)" -- balanced
        # counts, genuinely nested -- passed clean and reached the machine,
        # where LinuxCNC answered "Nested comment found". Any '(' seen while
        # already inside a comment is the fault, whatever the totals say.
        depth = 0
        for ch in code:
            if ch == '(':
                if depth > 0:
                    bad.append((n, 'NESTED PAREN',
                                'rule 1.2: a ( inside a comment -- the first '
                                ') ends the comment and the rest of the line '
                                'becomes g-code'))
                    break
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)

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

        # RULE 6.1 -- THE SPINDLE IS STOPPED BEFORE ANY M6.
        # Operator 2026-08-13: "when a tool change is issued, the spindle
        # continues spinning all the way as it moves from the work area to
        # the tool change area. this is not acceptable. the first thing that
        # happens is stopping the tool BEFORE the tool change" ... "i also
        # want it as part of the final lint checked here. before m6, there
        # must be a stop spindle command".
        bare = re.sub(r'\([^)]*\)', '', code)
        spin = re.findall(r'(?<![A-Za-z0-9.])M0?([345])(?![0-9])', bare, re.I)
        has_m6 = re.search(r'(?<![A-Za-z0-9.])M0?6(?![0-9])', bare, re.I)
        if has_m6:
            # SAME-BLOCK FIRST: it is the more precise diagnosis, and the M5
            # on this line has not been consumed yet so spin_on still reads
            # as running. Checking spin_on first reported the wrong fault.
            if '5' in spin:
                # An M5 in the SAME block is not "the first thing that
                # happens": within one line the interpreter runs the block's
                # words in ITS order, not left-to-right, and the shipped
                # manual on this machine does not state where M6 sits in
                # that order. Put the M5 on its own earlier line, where the
                # sequencing is not in question.
                bad.append((n, 'M5 IN THE SAME BLOCK AS M6',
                            'rule 6.1: M5 and M6 share this line -- their '
                            'order within one block is not left-to-right. '
                            'Put the M5 on its own line before it.'))
            elif spin_on:
                bad.append((n, 'SPINDLE RUNNING AT M6',
                            'rule 6.1: M3/M4 at line %d has no M5 before this '
                            'tool change -- the spindle keeps turning all the '
                            'way to the rack' % spin_on))
        for d in spin:
            spin_on = 0 if d == '5' else n

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
        'MALFORMED O-WORD', 'SPINDLE RUNNING AT M6',
        'M5 IN THE SAME BLOCK AS M6',
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
