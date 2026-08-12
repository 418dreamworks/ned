#!/bin/bash
# STAGED 2026-08-12 -- apply at idle, then restart PB.
# Gate the CHECK TOOL CONFIGURATION alarm and the TOOL GATE on the brain's
# new tool-settled pin, so the boot race stops shouting. 12 of today's 26
# operator toasts were this one false alarm.
set -e
cd /home/brains/Documents/ned
tools/cfg_edit.sh <<'PYEOF'
import io
p='configs/ned5_pb/postgui_pb.hal'
s=io.open(p,encoding='utf-8').read()
a="net sig-tool-table-ok  brain.tool-table-ok\n"
assert s.count(a)==1, 'table-ok anchor'
if 'tool-settled' not in s:
    s=s.replace(a, a + """
# HAS THE TOOL RECORD BEEN DECIDED THIS SESSION? The GUI compares the drawbar
# sensor with iocontrol.0.tool-number; that number is 0 for the first seconds
# of every launch because LinuxCNC has not run its DB handshake and the brain
# has not run its restore. Comparing against it then produces a false CHECK
# TOOL CONFIGURATION on every single launch, which then withdraws itself.
net sig-tool-settled   brain.tool-settled => ned-tab.tool-settled-in
""")
io.open(p,'w',encoding='utf-8').write(s)

q='configs/ned5_pb/user_tabs/ned_controls/ned_controls.py'
t=io.open(q,encoding='utf-8').read()
a2="            self.comp.addPin('table-ok-in', 'bit', 'in')"
assert t.count(a2)==1, 'addPin anchor'
if "tool-settled-in" not in t:
    t=t.replace(a2, a2 + "\n            self.comp.addPin('tool-settled-in', 'bit', 'in')")
b2="""            if self.comp is not None:
                u = bool(self.comp.getPin('tool-unrecorded-in').value)
                p = bool(self.comp.getPin('tool-phantom-in').value)"""
assert t.count(b2)==1, 'poll anchor'
c2="""            if self.comp is not None:
                u = bool(self.comp.getPin('tool-unrecorded-in').value)
                p = bool(self.comp.getPin('tool-phantom-in').value)
                # NOT A VERDICT UNTIL THE RECORD IS DECIDED. iocontrol's tool
                # number is 0 for the first seconds of every launch, so this
                # comparison used to raise CHECK TOOL CONFIGURATION on every
                # boot and then withdraw it -- 12 of 26 operator toasts in one
                # day. brain.tool-settled goes TRUE the moment the brain's
                # restore reaches ANY decision, including "nothing to restore".
                # A fault that outlives boot is still caught: the pin latches
                # TRUE and never goes back.
                try:
                    if not bool(self.comp.getPin('tool-settled-in').value):
                        u = False
                        p = False
                except Exception:
                    pass"""
t=t.replace(b2,c2)
io.open(q,'w',encoding='utf-8').write(t)
print('gated CHECK TOOL CONFIGURATION on brain.tool-settled')
PYEOF
python3 -m py_compile configs/ned5_pb/user_tabs/ned_controls/ned_controls.py
echo "APPLIED -- restart PB"
