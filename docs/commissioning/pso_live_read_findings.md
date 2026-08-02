# Fast in-LinuxCNC head absolute read — WORKING

**Goal met.** The read now runs INSIDE the live, running LinuxCNC and matches the ground-truth
board-free slow read exactly.

| | multiturn | within-turn | C angle |
|---|---|---|---|
| ground truth `tools/groundtruth/pso_read.sh` (slow, board-free, ~40 s) | -194 | 40086587 | **-44.9966 deg** |
| **in-LinuxCNC** (`pso_abs` live in the servo thread, ~5 s) | -194 | 40086646 | **-44.9966 deg** |

Delta **0.00000 deg** (59 encoder counts of servo dither). ~40 s -> ~5 s.

## How it works
1. **`pso_abs` runs in-config**, `addf hm2_7i97.0.pktuart.0.receive servo-thread`, placed BETWEEN
   `hm2...read` and `hm2...write` (placement is mandatory — a slower/other thread reads nothing).
2. **SEN must be DOUBLE-PULSED**: the pack emits the absolute frame only on a RISING edge, and the
   first edge after settling is swallowed. Pattern: `HIGH -> LOW -> HIGH`, ~1 s each.
   SEN held permanently high (the old wiring) yields NOTHING — 20 s produced zero frames.
3. **SEN low is the interlock, not a cost:** with SEN low both head packs drop to BB, so A/C
   physically cannot move. A read is therefore only ever taken with the head dead. No junk values.
4. `sen.or` OR-gates a GUI `sen-force` pin into SEN, so a read works even with the machine OFF —
   the safest state.
5. The result is pushed live into **`ini.4/5.home_offset`** (runtime-settable), so every homing
   uses a FRESH offset. This is what makes repeated homing safe: the old launch-time snapshot
   re-applied a stale offset on a second home and commanded an unearned move.

## Automatic, no buttons
The read runs **before and after a homing cycle, nowhere else**. HOME ALL is intercepted:
`read C -> read A -> home-all -> read C -> read A (verify)`.

## Bugs found and fixed en route
- **`addf` silently failed**: halcompile converts `_`->`-`, so the function is
  `hm2_7i97.0.pktuart.0.pso-live`, not `..._live`. The comp never ran; every "parsed=0" for
  `pso_live` was this, not a queued-API bug.
- `pso_live` also wedged in IDLE gating on `nframes > 0` while the register reads HASDATA=1 /
  NFRAMES=0. `hm2_pktuart_read()` deliberately does not bail on a zero count.
- `receive` in a 20 ms thread -> `total=0`. Servo thread only.
- `logclean.sh` was truncating `lcnc.log` and destroying tracebacks mid-debug.
- LinuxCNC pops a modal `wish` error dialog when stdin is not a tty (`/usr/bin/linuxcnc:203`).
  Run under `script -q -c ...` to get a pty so errors print instead of blocking on a dialog.
- `pkill -f linuxcnc` matches the invoking shell itself — use bracket patterns (`[l]inuxcnc`).

## Clean shutdown
`tools/lcnc_stop.sh` — SIGTERM first, escalate only if it hangs, then clear stale lock/shm.
`kill -9` leaves the lock behind and causes the "already running / restart?" dialog.

## Still open
- Not yet exercised through a real homing cycle (that moves the machine — operator to run).
- `Pn515 = n.□□□7` ("always active", manual §6.12 p.313) would remove the SEN handshake entirely
  and let the reader free-run. Not needed now, and NOT applied.

---

# UPDATE — in-config read works, but only ONCE per LinuxCNC session

## Works
- **First read of a session matches ground truth exactly** (C: mt=-143; A: mt=+35, identical to
  `tools/groundtruth/pso_read.sh`). Confirmed repeatedly, in the live running config.
- **`enable` gate added to `pso_abs`** — CRITICAL. `hm2_pktuart_read()` does a direct `llio->read`,
  an extra UDP round-trip INSIDE the 1 ms servo period. Left running every cycle it added enough
  jitter to throw following errors on the analog PID joints (X/Y/W = joints 0/1/3) during homing:
  `taskintf.cc 976: Error on joint 0/1/3, command number 126`. That was MY regression, not a
  parameter problem — `joint_z.inc` (HOME_OFFSET 5.0 / MAX_LIMIT 1.0) is CORRECT and deliberate:
  zero sits 5 mm below the hard switch, the soft limit sits above zero so encoder noise near zero
  cannot trip it, and it stays below the hard switch so it still trips first. DO NOT "fix" it.
  The reader now only touches the board while a read is deliberately in progress.

## Broken: second read in the same session
After the first successful burst the RX block wedges:
`rx-status = 0x16006488` -> **RXBUSY=1, HASDATA=0**, and it is byte-identical before/after every
recovery attempt. `rxbytes=0, frames=0` forever after.

Tried and did NOT clear it:
- `hm2_pktuart_reset(pname)`
- `hm2_pktuart_config(... FLUSH|RXEN)` re-arm
- full RXEN **off -> on** cycle (two configs)
- SEN held low 10 s to re-arm the pack; R4 settle 2-3 s; ground-truth 8 s windows
- same axis twice, and A-then-C ordering

**The servopack is NOT at fault:** board-free `pso_read.sh A`, `C`, `A` back-to-back all succeed.
Each of those does a fresh hostmot2 driver load, which is the only thing that clears the wedge.

## Consequence
Homing needs BOTH A and C, so it currently gets only the first axis (C reads, A logs
`NO NEW FRAME`) and A falls back to a stale offset. Do not trust A's homing yet.

## Next avenues
1. Compare what `hm2_pktuart` does at DRIVER LOAD vs `hm2_pktuart_config` — find the register
   write that actually clears RXBUSY (likely a full instance re-init, not exposed by the config API).
2. Try the QUEUED path (`pso_live`, now that its `addf` name bug is fixed: the function is
   `hm2_7i97.0.pktuart.0.pso-live`, hyphen) — it may not wedge the same way.
3. **Most promising:** `Pn515 = n.□□□7` ("signal always active", manual 6.12 p.313) + `Pn50A = n.□□□1`.
   PSO then free-runs with no SEN handshake, so the RX never sits idle waiting for a burst and the
   wedge likely never happens. Operator/SigmaWin change, both head packs. NOT applied.

---

# UPDATE 2 — the real mechanism (corrects everything above)

## Wiring ground truth (USER-CONFIRMED, authoritative)
- **SEN is HARDWIRED to BOTH A and C servopacks.** One pulse snapshots both.
- **R4 muxes the RETURN (PSO) path only:** R4 energized (output-05=1) -> **A** reaches the Mesa;
  de-energized -> **C**. R4 does NOT gate which pack receives SEN.

## How the pack actually behaves (measured)
A SEN pulse makes the pack **latch a snapshot and then repeat that same message continuously**
until the NEXT SEN pulse. Proven by the raw dump:
`PSO frame[786]: P-00143,03117264. P-00143,031177263 0. ...` (one 786-byte frame, same value
repeated). Consequences:
- The value is **NOT live**. Pulse SEN, move the axis for an hour, and you still read the
  hour-old snapshot. A fresh SEN pulse is MANDATORY for a truthful reading.
- Because the stream is continuous there is **no interframe gap**, so the whole burst arrives as
  ONE oversized frame.

## THE ACTUAL BUG behind "only one read per session"
`pso_abs` passed `max_frame_length = 80`. The real frame is ~786 bytes, so after the stream
started the oversized frame yielded no usable frame and the parse loop never ran. Nothing was
ever "wedged": `rx-status = 0x16006408` = RXEN set, **RXBUSY CLEAR**, HASDATA clear = a clean idle
receiver, and `rxbytes = 786` proved bytes were arriving fine. The earlier "RXBUSY stuck" reading
was a transient sample caught mid-burst -- a wrong conclusion I built too much on.

**Fixed:** `pso_abs` now uses `max_frame_length = 1024`, `num_frames = 4`, `buf[4*1024]`, and the
parser SCANS the whole buffer for the **LAST** complete `P<sign><5>,<8>` message (freshest value)
instead of walking per-frame. Verified reading C repeatedly in one session.

## STILL OPEN
After flipping R4 mid-stream (+ FIFO flush via the `reset` pin) the reader still returns C's
value, while `within` keeps updating -- i.e. fresh data flows but it is still C. Since SEN reaches
both packs, A should be streaming too. Next step: confirm the R4 relay actually switches the
return path while a stream is active (scope/meter, or read with R4 set BEFORE the SEN pulse and
compare), and check whether the FIFO flush (`HM2_PKTUART_CLEAR` 0x80010000) is really clearing --
a forum post suggests **0x00010000** is the value that clears the RX FIFOs
(`mesaflash --wpo 0x6800=0x00010000`); mesaflash cannot run while the driver owns the board.

## Also fixed this session
- `pso_abs` gained an **`enable`** pin. Its `hm2_pktuart_read()` does a direct `llio->read` = an
  extra UDP round-trip inside the 1 ms servo period. Running it every cycle added enough jitter to
  cause following errors on the analog PID joints (X/Y/W = joints 0/1/3) during homing
  (`taskintf.cc 976: Error on joint 0/1/3, command number 126`). It now touches the board ONLY
  while a read is deliberately in progress. `joint_z.inc` was NEVER at fault.

---

# UPDATE 3 — parser fixed; R4 mux is the remaining blocker

## Fixed and verified
`pso_abs` now accumulates the stream in a **rolling buffer** across servo cycles and scans it for
the LAST complete `P<sign><5>,<8>` message. At 9600 baud only a byte or two arrives per servo
cycle, so message boundaries fall anywhere -- per-frame parsing could never work. The `reset` pin
clears the rolling buffer as well as the FIFO. **C now reads reliably and repeatedly in one
session** (this was the original "one read per session" defect -- it was the 80-byte
`max_frame_length` plus per-frame parsing, never a wedged receiver).

## The remaining blocker: R4 does not switch mid-session
| condition | result |
|---|---|
| R4=1 set BEFORE the driver/threads start | **A reads correctly** (mt=+35) |
| R4=1 set mid-session, buffer flushed, fresh SEN double-pulse | **still returns C** (mt=-143) |
| R4=1 set mid-session, no flush / flush only | still returns C |

`hm2_7i97.0.7i84.0.0.output-05` reads back TRUE in every mid-session case, and `output-04` (SEN)
on the SAME 7I84 toggles fine mid-session -- so the sserial write path is working. Yet the return
path never changes to A.

## It is the RECEIVE side, not the relay (operator-confirmed)
R4 is a relay: the copper contacts physically transfer, so the signal presented to the Mesa
genuinely changes. Do NOT chase the relay. The defect is that our RX side fails to pick up the
newly-selected pack after a LIVE transfer.

Why that is plausible: the contacts transfer *while a 9600-baud stream is mid-byte*. The UART is
left mid-character and mis-framed, and because the pack repeats its snapshot with no interframe
gap there is never a quiet period for the receiver to re-frame on. It only ever re-syncs at driver
load -- which is exactly the one case where R4=1 works.

Next things to try (all receive-side):
1. Hold **SEN LOW across the transfer** so BOTH packs are silent while the contacts move, let the
   line settle, flush, and only THEN pulse SEN. This gives the UART a genuine quiet gap to
   re-frame on -- the most likely fix and cheap to test.
2. If that is not enough, force a real re-sync after the switch: full `hm2_pktuart_config`
   (off -> on with FORCECONFIG) AFTER the line is quiet, not during the transfer.
3. Check whether the forum value `0x00010000` (vs the driver's `0x80010000`) is what actually
   clears the RX FIFO -- would need a raw register write from inside the comp, since mesaflash
   cannot run while the driver owns the board.

---

# UPDATE 4 — after an R4 switch, ZERO bytes arrive (not a parsing problem)

Operator ground truth: once R4 is energized, **C's signal physically cannot reach the Mesa**.
Therefore any C value read after energizing R4 is **stale OUT-pin state**, not received data --
`multiturn`/`within` are OUT pins and simply keep their last value when nothing new parses.
That is what every "the mux didn't switch" observation actually was. The mux DID switch.

Decisive measurement (rolling-buffer build, reset clearing only our own buffer):
`parsed` was **identical (0x0F97) before and after** the R4 switch, across 7+ seconds, with the
buffer cleared. No new parse => **no bytes received at all** after the switch. So it is NOT
mis-framing and NOT the parser: nothing arrives.

=> The remaining question is why the pack does not transmit on the SECOND SEN pulse within one
driver session, given that it happily transmits on the first, and transmits again in a fresh
board-free `pso_read.sh` run (which the pack cannot distinguish -- it only sees SEN and power).
Things already ruled out: SEN low for 10 s, R4 settle delays, ground-truth 8 s windows, both
axis orderings, FIFO flush, RXEN cycling, FORCECONFIG.

## Known defect to fix in pso_abs (minor)
The scan block runs every servo cycle and re-parses the ring buffer, so `parsed` increments even
with no new data (3991 counts). It is therefore useless as a freshness indicator. Only increment
`parsed`/set `valid` when NEW bytes were appended this cycle.

## State of the code
- Parser: rolling buffer + scan for last complete message. **C reads reliably and repeatedly.**
- `enable` gate: reader touches the board ONLY during a deliberate read (fixes the servo-jitter
  regression that broke homing on joints 0/1/3).
- `reset`: clears our rolling buffer only (an off->on config cycle appeared to kill RX).

---

# UPDATE 5 — manual SEN rules found, but they do NOT explain the failure

Manual 6.12 p.315 ("Important"):
- **"Maintain the SEN signal at the high level for at least 1.3 seconds when you turn it OFF
  before you turn it ON again."**
- **"The SEN signal is not acknowledged while the servo is ON."**

Both are real constraints and MUST be honoured in the final design (drop /S-ON before a read;
hold SEN high >=1.3 s before dropping it). BUT neither is the cause of our failure:
a manual-compliant sequence (SEN high 2 s -> low 2 s -> high, flush between, /S-ON never
asserted so the servo was OFF the whole time) still gives **one read only**:
C = -143 on the first, nothing on the second.

## The single surviving fact
**Exactly one burst per hostmot2 driver session**, independent of: SEN timing (1.3 s compliant,
15 s low, double pulses), servo ON/OFF, R4 position, FIFO flush, buffer clear, axis order.
Only a driver reload restores it -- and the servopack cannot see a driver reload. So the
asymmetry lives on the **Mesa/receiver side at init**, not in the Yaskawa pack.

Note the earlier "RXBUSY wedged" claim was WRONG (transient sample), and so was
"pack ignores later SEN pulses because servo is ON" (servo was off). Do not re-run those.

## Next
Find what the hostmot2 driver does to the PktUART RX at LOAD that it never does again --
that write is the fix. Compare the register writes in the pktuart setup/parse_md path against
what `hm2_pktuart_config()` emits at runtime. This is now the ONLY open thread.


---

# UPDATE 6 — METER PROOF: drives transmit on EVERY request; fault is 100% Mesa receive side

Measured on the RS-422 pair at **7I85 TB1-19 (SRX+) / TB1-20 (SRX-)** with
`tools/sen_meter.sh both` (holds R4 ON -> 2 SEN requests -> R4 OFF -> 2 requests -> repeat,
R6 clicked as an audible cue):

- **Every SEN request produces line activity, on BOTH A and C, every repeat.** The drives are
  transmitting reliably. The mux works. The signal reaches the Mesa every time.
- **The `silent` flag (/S-ON asserted) makes NO difference** -- identical readings. Reason:
  taking SEN low to make a request drops both packs to BB, so the servo is never actually on at
  the moment of the request. The manual's "SEN is not acknowledged while the servo is ON"
  (6.12 p.315) can therefore NEVER block us. Permanently ruled out; do not revisit.

**Conclusion: the PktUART receives only the first burst after driver load and ignores every
later burst that is demonstrably present on the wire.** All remaining work is on the Mesa
receive side. See `pcw_question.md` (rewritten around this evidence).

Also fixed: `tools/sen_meter.sh` was NOT actually flipping R4 -- `2>/dev/null` on the halcmd
writes hid the failure, so it printed "R4 flipped" while output-05 stayed FALSE for 44 s. It now
prints a live readback of output-05 on every line. Lesson: never hide stderr on the pin writes
that a test depends on.


---

# UPDATE 7 — GUI fixes made while the operator was away (no machine motion)

1. **Spindle-overtemp LED was inverted-by-omission.** `sig-spindle-overtemp` was netted straight
   to `input-14` (*39 = e-stop chain BEFORE the thermostat), so the LED lit whenever the machine
   was HEALTHY. The `overtemp` and2 gate was loaded and addf'd but never wired. Now correct:
   `overtemp = input-14 AND NOT input-04` (chain up before the thermostat, dropped after it).
   Verified live: reads FALSE on a healthy machine (was TRUE).
2. **A/C DRO no longer shows a stale HOME_OFFSET as if it were the head position.** Since
   run5.sh stopped running pso_home, joint_{a,c}.inc HOME_OFFSET are leftovers from an earlier
   session (seen: -3.98 / -45.00 while the head was actually ~+3.5 / ~+44). The DRO now shows
   **"not read"** until a genuine read happens. Never invent a position we have not measured.
3. **`pso_abs.parsed` no longer climbs every servo cycle.** It re-scanned the rolling buffer
   unconditionally, so it counted ~4000 "parses" with no new data and was useless as a freshness
   signal (it made several earlier readings ambiguous). Now only counts when new bytes arrived.
4. **R4 double-booking documented** (docs/tracing/relays.md, top). OUTPUT5 gates the rotary-B
   brick AND muxes the head PSO return. A rotary-power toggle would silently pin the mux to A and
   make head reads return the wrong axis with no error. Task #7 description updated with this.

Verified after each change: config loads, 1355 pins, zero widget-hookup failures.


---

# UPDATE 8 — **SOLVED.** Root cause was `ifdelay=100`

**Manual 6.12.5 transmission spec (this is the key fact I missed for hours):**
PSO = **17-character** message (`P` + sign + 5-digit multiturn + `,` + 8-digit within-turn + **CR**),
**ASCII 7-bit, even parity, 1 start, 1 stop, 9600 bps**, **data output cycle 40 ms**.
So: ~17.7 ms of data, then **~22 ms of IDLE LINE** between messages. The gaps were always there.

**The bug:** we configured the PktUART with `ifdelay = 100` bit times (10.4 ms)... but measured
behaviour shows that value glued ~46 messages into ONE 769-byte frame. Oversized frames then
produced every downstream symptom: no usable frame count, apparent "wedge", one-read-per-session.

**Measured sweep (frame size vs ifdelay):**

| ifdelay | first frame size |
|---|---|
| 10 | 1  (splits mid-message -- too short) |
| **20** | **17** (one clean message) |
| **40** | **17** (one clean message) |
| 100 | 769 (concatenated blob) -- the bug |

**Fix:** `ifdelay_p = 30` (default in `pso_abs.comp`, settable at loadrt for future tuning).

**Verified: THREE reads in ONE session, alternating the mux:  C=-143, A=+35, C=-143.**
Repeated reads and both axes now work. No firmware rebuild, no drive-parameter change, no
mesaflash poke, no PCW involvement needed.

## Things I wrongly concluded along the way (do not revisit)
- "RXBUSY wedged" -- it was a transient sample; the receiver was healthy (RXBUSY=0, RXEN=1).
- "Pack transmits once per session" -- false; the meter proved bursts on EVERY request.
- "SEN not acknowledged while servo ON blocks us" -- unreachable: taking SEN low to make a
  request drops the pack to BB, so the servo is never on at request time.
- "PSO is a gapless continuous stream" -- false; it is periodic with 22 ms gaps. This is what
  made me send PCW a question whose central claim was wrong.
- "R4 does not switch" -- it always switched; I was reading stale OUT-pin state.

`docs/commissioning/pcw_question.md` is now MOOT -- its premise ("no gaps") is wrong.

## Update 9 (2026-07-30 evening): the queued port is DONE — read restored inside LinuxCNC
Executed `head_read_IMPLEMENTATION_SPEC.md` "THE PORT" end to end:
- `tools/live/pso_live.comp` rewritten: queued-API state machine kept, pso_abs's proven
  rolling-buffer parser + `enable`/`reset`/`oversize`/`buflen`/`lastsize`/`newbytes` pins +
  `ifdelay_p` (default 30) merged in. No decimation (queued reads ride the TRAM packet —
  there is nothing to decimate).
- Three new findings from reading `pktuart.c` (linuxcnc source at
  `~/Documents/linuxcnc/src/hal/drivers/mesa-hostmot2/pktuart.c`):
  1. `hm2_pktuart_queue_reset()` exists — a QUEUED FIFO clear (`llio->queue_write`). The
     reset pin now genuinely flushes the FIFO RT-safely (plus a 2-cycle holdoff so the
     clear lands before the FSM acts on stale status).
  2. `hm2_pktuart_queue_get_frame_sizes()` pops exactly NFRAMES (5 bits, up to 31) entries
     into the caller's array — the old `fsizes[16]` was a driver-side buffer overflow
     waiting for a >16-frame backlog (a full SEN burst is ~45 frames). Now `fsizes[32]`.
  3. It pops per the SAME cached status the comp reads, so IDLE must gate on NFRAMES>=1 —
     gating on HASDATA alone (the old "fix") would fetch a stale size mid-message.
- Config: `loadrt pso_live ... ifdelay_p=[PSO]IFDELAY` + hyphen addf live in
  `ned5_iron.hal`; postgui `pso-enable`/`pso-reset` nets restored; `_home_cycle` re-pointed
  to read C -> read A -> home (post-home verify reads were already in `_home_poll`).
- Abandoned A/B-gate path moved to `trash/` (`configs/ned5/pso_live.hal`,
  `pso_live_gen.hal`, `tools/pso_live_gate.sh`) and `HALFILE = pso_live_gen.hal` removed
  from the ini: it would have double-loaded pso_live and revived the obsolete pso_mux
  R4 auto-alternator. (The gate's last failure, `parsed=0`, was the comp's own hardcoded
  ifdelay=100 — the same silent glue-bug, one layer deeper.)
- **Bench (board-free)**: C read twice in one session, flush verified between
  (buflen 265 -> 1, multiturn zeroed): mt=-143 / lastsize=17 / oversize FALSE both times,
  within differing by 3 counts (genuinely fresh), zero collision signatures.
- **Live (inside running LinuxCNC, machine off, NO motion)**: same double read driven by
  halcmd with the GUI nets temporarily unlinked (restored + verified after):
  mt=-143 (~+44.14 deg) twice, parsed 121 -> 243, sserial fault-count 0 -> 0, zero
  `llio->read in realtime` / RCFIFO / watchdog in the session log, InMux live throughout.
  1356 HAL pins (1341 + 15 reader pins). Clean shutdown, board free.
- Side fixes: `tools/live/mesalog.sh` had lost its execute bit (logger was dead since 15:47) —
  restored + relaunched; `tools/lcnc_stop.sh` now ignores ZOMBIE processes (two defunct
  rtapi_app husks made it cry "STILL RUNNING" after a perfectly clean stop).

**Remaining:** operator homing test — HOME ALL = read C -> read A -> home -> verify reads
(~0.000 expected). Machine notes pointer: wiring/params unchanged; reader config lives in
`configs/ned5/ned5_iron.hal`, `[PSO]` in `ned5_iron.ini`, `tools/live/ned_params.sh` untouched.

## Update 10 (2026-07-30 late): homing cycle VERIFIED end-to-end + three GUI root causes
- **Homing works**: 21:17 session — pre-read C/A -> home (A physically moved ~-5.4 to zero)
  -> post-verify C=-0.000 / A=+0.000. Earlier failure was qtvcp's ActionButton firing its
  built-in home on the PRESSED signal (action_button.py:436) in parallel with the read
  cycle; all btn_home signals now disconnected, handler owns the cycle. Verify now
  auto-corrects (unhome+rehome, HOME_NO_REHOME makes plain re-home a silent no-op,
  homing.c:765) and leaves joints UNHOMED + error dialog if still off.
- **MPG "crash" = joint 1 following error** (recovered from the unread error channel):
  10x wheel spin commanded ~100 mm/s on Y, PWM saturated -100%, ferror -> machine OFF.
  No limit/e-stop involved (mesa.log). Task #3 (jog safeguard) is the fix.
- **Screen blanking = qtvcp audio player**: gst playbin grabs the Pi framebuffer on every
  alert; error-heavy session = constant blanking. X screensaver/DPMS were already off.
  ALL Player entry points now stubbed in _kill_annoyances (jump/os_jump alone was not enough).
- **Probe programs' "Named parameter #<_ini[probe]...> not defined" = INLINE # COMMENTS**
  on [PROBE] value lines. IniFile's number conversion rejects "KEY = 5  # text" for
  #<_ini[...]> reads (bisected with rs274 + INI_FILE_NAME env; trailing space on the
  section header and lowercase names are both harmless; INI_VARS defaults ON). [PROBE]
  rewritten comments-above-values; all params verified resolving (ft=5 ff=50 rt=0.5 sd=15).
  NOTE: configs/params/puck.inc still has 4 inline-comment value lines — harmless while
  no g-code reads [puck], but the same landmine if one ever does (param file: not edited).
- Errors are now VISIBLE: handler polls linuxcnc.error_channel (nothing else on this
  screen reads it) -> red statusbar 15 s + gui.md 'ERROR' lines.
- CP1 speeds per operator: FEED_FIND=50 find, RETRACT=0.5 back-off, FEED_TOUCH=5 re-touch.
