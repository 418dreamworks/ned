#!/usr/bin/env python3
"""F12 = OPERATOR BLACK-SCREEN WITNESS MARK (operator 2026-08-04: "if i see
blank screen, does spamming f12 log me seeing black screen?" -- it does now).

Reads the keyboard EVENT DEVICES directly (/dev/input/by-path/*-event-kbd),
NOT the GUI, so the mark lands even when PB is dead or the screen is black --
which is the whole point. Every F12 press appends a timestamped line to
logs/screen.log, next to blackwatch's own pixel samples, so an operator
sighting can be lined up with what the pixels actually did.

Debounce: spamming F12 within 2 s collapses into one line with a count.
"""
import glob
import os
import select
import struct
import time

LOG = '/home/brains/Documents/ned/logs/screen.log'
EV_KEY, KEY_F12, PRESS = 0x01, 88, 1
FMT = 'llHHi'          # struct input_event (64-bit)
SIZE = struct.calcsize(FMT)


def mark(n):
    with open(LOG, 'a') as f:
        f.write('%s  OPERATOR F12: black screen witnessed (x%d)\n'
                % (time.strftime('%F %T'), n))


def main():
    devs = []
    for p in glob.glob('/dev/input/by-path/*-event-kbd'):
        try:
            devs.append(os.open(p, os.O_RDONLY | os.O_NONBLOCK))
        except OSError:
            pass
    if not devs:
        with open(LOG, 'a') as f:
            f.write('%s  blackmark: NO readable keyboard device -- F12 '
                    'marks are OFF\n' % time.strftime('%F %T'))
        return
    pend, last = 0, 0.0
    while True:
        r, _, _ = select.select(devs, [], [], 1.0)
        now = time.time()
        for fd in r:
            try:
                data = os.read(fd, SIZE * 64)
            except OSError:
                continue
            for i in range(0, len(data) - SIZE + 1, SIZE):
                _, _, etype, code, value = struct.unpack(
                    FMT, data[i:i + SIZE])
                if etype == EV_KEY and code == KEY_F12 and value == PRESS:
                    pend += 1
                    last = now
        if pend and now - last >= 2.0:
            mark(pend)
            pend = 0


if __name__ == '__main__':
    main()
