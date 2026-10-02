#!/usr/bin/env python3
"""PROTECTS the A/C head-read sequence. No machine, no HAL, about 0.1 s.

Operator 2026-10-01: "take notes on this. protect this code." On 2026-10-01
21:13-21:17 this exact code took SEVEN drive reads of A and C in one PB
session, each following a jog (ned 8c9bba3). What makes a back-to-back read
truthful is one short sequence, and every part of it has been broken before
(docs/commissioning/pso_live_read_findings.md, now ~/Documents/controls/):

  1  r4-select set for the axis BEFORE SEN is touched
  2  pso-reset rising edge: PktUART FIFO flushed, multiturn/within zeroed
  3  SEN LOW (sen-suppress) for >= 1.3 s   (Yaskawa manual 6.12 p.315)
  4  hr_p1 = parsed counter, sampled AT the rise
  5  SEN HIGH (sen-force): the rising edge makes the pack latch a NEW snapshot
  6  accepted ONLY if parsed > hr_p1 -- a frame that arrived after THIS rise
  7  hr_p1 poisoned, pso-enable off, R4 parked off

The pack repeats its last snapshot until the next SEN edge, so a read without
steps 3-6 returns the OLD angle with no error. This test reads the source and
fails the commit if any step is gone or reordered. Run by .git/hooks/pre-commit
on any commit touching ned_brain.py, pso_live.comp or ned5_iron.hal.
The iron proof is tools/live/head_multi_read_test.py.
"""
import ast
import os
import re
import sys

NED = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRAIN = os.path.join(NED, 'tools/live/ned_brain.py')
COMP = os.path.join(NED, 'tools/live/pso_live.comp')
IRON = os.path.join(NED, 'configs/ned5/ned5_iron.hal')
INI = os.path.join(NED, 'configs/ned5_pb/ned5_pb_tcp_gen.ini')

fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


def code_only(text):
    """Source with comment lines dropped, so prose cannot satisfy a check."""
    return '\n'.join(l for l in text.split('\n') if not l.strip().startswith('#'))


src = open(BRAIN).read()
tree = ast.parse(src)
funcs = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        funcs.setdefault(node.name, code_only(ast.get_source_segment(src, node)))


def const(name):
    m = re.search(r'^%s\s*=\s*([\d.]+)' % name, src, re.M)
    return float(m.group(1)) if m else None


def before(body, a, b):
    """a and b both present and a comes first."""
    return a in body and b in body and body.index(a) < body.index(b)


print('ned_brain.py  hr_start')
b = funcs.get('hr_start', '')
check("h['r4-select'] = (axis == 'a')" in b, 'step 1: R4 selects the axis (A energised, C not)')
check(before(b, "h['r4-select']", "h['pso-reset'] = True"), 'step 1 before step 2: R4 set before the flush')
check("h['pso-enable'] = True" in b, 'reader enabled for the read')
check('self.hr_deg[axis] = None' in b and 'self.hr_lastraw = None' in b,
      'stateless start: the degree slot and raw-frame memory are blanked')
check('if self.hr_step:' in b and 'return' in b, 'a read in flight is never restarted')

print('ned_brain.py  hr_tick')
b = funcs.get('hr_tick', '')
low = b[b.index('if st == 1:'):b.index('elif st == 2:')] if 'if st == 1:' in b and 'elif st == 2:' in b else ''
check("h['sen-suppress'] = True" in low and "h['sen-force'] = False" in low, 'step 3: tick 1 takes SEN LOW')
check("h['pso-reset'] = True" in low, 'step 2: tick 1 holds the flush')
rise = b[b.index('elif st == HR_ST_RISE:'):b.index('elif st >= HR_ST_TIMEOUT:')] \
    if 'elif st == HR_ST_RISE:' in b and 'elif st >= HR_ST_TIMEOUT:' in b else ''
check("self.hr_p1 = int(h['parsed-in'])" in rise, 'step 4: the frame counter is sampled at the rise')
check(before(rise, "self.hr_p1 = int(h['parsed-in'])", "h['sen-force'] = True"),
      'step 4 before step 5: counter sampled BEFORE SEN goes high')
check('self.hr_p1 = 1 << 32' in rise, 'unreadable counter at the rise poisons hr_p1 (read must fail)')
done = b[b.index('elif st >= HR_ST_TIMEOUT:'):] if 'elif st >= HR_ST_TIMEOUT:' in b else ''
check('self.hr_report()' in done, 'the result is judged by hr_report')
check(before(done, 'self.hr_report()', 'self.hr_p1 = 1 << 32'), 'step 7: hr_p1 poisoned after use')
check("h['sen-force'] = False" in done and "h['sen-suppress'] = False" in done, 'step 7: SEN lines released')
check("h['pso-enable'] = False" in done, 'step 7: reader stops touching the board')
check("int(h['parsed-in']) > self.hr_p1" in b, 'early exit only on a frame newer than the rise')
tick, st_rise = const('HR_TICK'), const('HR_ST_RISE')
check(tick is not None and st_rise is not None and (st_rise - 1) * tick >= 1.3,
      'step 3: SEN low window (HR_ST_RISE-1)*HR_TICK = %s s >= 1.3 s' % (None if tick is None or st_rise is None else (st_rise - 1) * tick))

print('ned_brain.py  hr_report')
b = funcs.get('hr_report', '')
check('if p <= self.hr_p1:' in b, 'step 6: a frame not newer than the SEN rise is REFUSED')
check(before(b, 'if p <= self.hr_p1:', 'deg = SIGN[ax]'), 'step 6 comes before any angle is computed')
check('self.hr_lastraw == (mt, w)' in b, 'a raw frame identical to the previous read is rejected (other-axis data)')
check('abs(deg) >= LIM[ax]' in b, 'an angle outside the axis range is rejected')
check(before(b, 'abs(deg) >= LIM[ax]', 'self.hr_deg[ax] = deg'), 'the value is stored only after every rejection')

print('ned_brain.py  trigger')
code = code_only(src)
check("self.hr_start('c', lambda: self.hr_start('a', self.read_done))" in code,
      'one request reads C then A, each with its own SEN edge, then read_done')
check(re.search(r"if self\.want_read and .*self\.hr_step == 0", code, re.S) is not None,
      'a new read starts only when no read is in flight')
b = funcs.get('read_done', '')
check("self.hr_deg.get('a') is not None and self.hr_deg.get('c') is not None" in b,
      'a read is armed only when BOTH axes were accepted')

print('pso_live.comp')
c = open(COMP).read()
c = c.split('\n;;', 1)[-1]                         # the C body only, not the description text
c = re.sub(r'/\*.*?\*/', '', c, flags=re.S)      # drop C comments: prose must not satisfy
c = re.sub(r'//[^\n]*', '', c)                     # or fail a check
check('hm2_pktuart_queue_reset(pname)' in c, 'reset edge queues a FIFO flush')
m = re.search(r'if \(reset && !prev_reset\) \{(.*?)\n    \}', c, re.S)
blk = m.group(1) if m else ''
check('multiturn = 0' in blk and 'within = 0' in blk and 'rlen = 0' in blk,
      'reset edge zeroes multiturn, within and the rolling buffer')
check(re.search(r'if \(newbytes > 0\) \{.*?parsed\+\+', c, re.S) is not None
      and c.count('parsed++') == 1, 'parsed counts ONLY on new bytes (the freshness counter)')
check('hm2_pktuart_queue_read_data' in c and 'hm2_pktuart_read(' not in c,
      'queued PktUART reads only (a direct read in the servo thread killed the link)')
check(re.search(r'int ifdelay_p = (\d+);', c) is not None
      and 20 <= int(re.search(r'int ifdelay_p = (\d+);', c).group(1)) <= 40, 'ifdelay default within 20..40 bit times')

print('ned5_iron.hal / ini')
hal = [l.split('#')[0].strip() for l in open(IRON)]
hal = [l for l in hal if l]
addf = [l for l in hal if l.startswith('addf')]


def pos(prefix):
    for i, l in enumerate(addf):
        if l.startswith(prefix):
            return i
    return -1


r, p, w = pos('addf hm2_7i97.0.read '), pos('addf hm2_7i97.0.pktuart.0.pso-live '), pos('addf hm2_7i97.0.write ')
check(p >= 0, 'addf hm2_7i97.0.pktuart.0.pso-live (HYPHEN; an underscore fails silently)')
check(0 <= r < p < w, 'pso-live runs in the servo thread BETWEEN hm2 read and hm2 write')
check(not any('hm2_7i97.0.read-request' in l for l in addf),
      'read-request is NOT addf\'d (0f71aed: it stops the PSO frames arriving)')
check(any(l.startswith('loadrt pso_live') and 'ifdelay_p=[PSO]IFDELAY' in l for l in hal), 'pso_live loaded with [PSO]IFDELAY')
m = re.search(r'^\[PSO\].*?^IFDELAY\s*=\s*(\d+)', open(INI).read(), re.S | re.M)
check(m is not None and 20 <= int(m.group(1)) <= 40, '[PSO]IFDELAY = %s within 20..40' % (m.group(1) if m else None))

print()
if fails:
    print('%d CHECK(S) FAILED -- the head-read sequence is broken:' % len(fails))
    for f in fails:
        print('   ' + f)
    sys.exit(1)
print('all checks pass -- every A/C read still gets its own SEN edge and is judged fresh')
