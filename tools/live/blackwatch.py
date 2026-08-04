#!/usr/bin/env python3
"""blackwatch -- catch the screen going black, by looking at actual pixels.

Every 0.5 s grab the X root window and sample 1000 random pixels. All-black
sample = BLACK SCREEN; log the transition in and out with timestamps to
ned/screen.log (same file screenlog.sh writes, so the DRM/window evidence
and the pixel truth line up by timestamp). Operator 2026-08-04: "just grab
1000 random pixels directly from screen every half a second. when all are
black its black screen."

Sampling detail: one full-frame XGetImage per tick (a Pi 5 does this in tens
of ms) then 1000 random points from it -- 1000 individual round-trips would
be slower than the frame grab. 'Black' means RGB all below 10, not exactly
zero, so a dim backlight or compositor fade still counts.
"""
import os, random, time, subprocess

LOG = '/home/brains/Documents/ned/screen.log'
os.environ.setdefault('DISPLAY', ':0')

def say(msg):
    with open(LOG, 'a') as f:
        f.write('%s %s\n' % (time.strftime('%F %T'), msg))

try:
    from PIL import Image
except ImportError:
    say('blackwatch: PIL missing -- NOT monitoring'); raise SystemExit(1)

say('blackwatch start (1000 px / 0.5 s)')
black = False
fails = 0
while True:
    t0 = time.time()
    try:
        # scrot to shared memory: no disk wear, fresh file each tick
        p = '/dev/shm/blackwatch.png'
        subprocess.run(['scrot', '-o', '-z', p], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        im = Image.open(p).convert('RGB')
        w, h = im.size
        px = im.load()
        dark = 0
        for _ in range(1000):
            r, g, b = px[random.randrange(w), random.randrange(h)]
            if r < 10 and g < 10 and b < 10:
                dark += 1
        now_black = (dark == 1000)
        fails = 0
        if now_black and not black:
            say('blackwatch: SCREEN WENT BLACK (1000/1000 dark)')
            black = True
        elif black and not now_black:
            say('blackwatch: screen back (%d/1000 dark)' % dark)
            black = False
    except Exception as e:
        fails += 1
        if fails == 5:
            say('blackwatch: 5 consecutive grab failures (%s) -- X gone?' % e)
    time.sleep(max(0.0, 0.5 - (time.time() - t0)))
