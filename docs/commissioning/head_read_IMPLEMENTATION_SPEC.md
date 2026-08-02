# Head A/C absolute read in LinuxCNC — IMPLEMENTATION SPEC
*(read this before touching anything; it replaces re-deriving from the narrative in
`pso_live_read_findings.md`)*

## THE GOAL (unchanged, operator's requirement)
On **HOME ALL**:
1. read A and C absolute positions **inside running LinuxCNC**, BEFORE any motion
2. feed those into `ini.4.home_offset` / `ini.5.home_offset` (runtime-settable)
3. home (XYZ on switches, A/C move to their true zero)
4. **read A and C again AFTER homing to VERIFY** (should come back ~0.000)

## THE ONE HARD CONSTRAINT (this is what broke everything)
`hm2_pktuart_read()` issues a **DIRECT `llio->read`**. On this ETHERNET board (hm2_eth) that is
an extra UDP round-trip INSIDE the servo cycle. Consequences, both measured:
- called every servo cycle (1 kHz)  -> `Watchdog has bit!`, sserial `local error 13/7/3`,
  fault-count 200+, all InMux inputs freeze, homing dies
- decimated to 1-in-20 cycles       -> RX FIFO starves -> `RCFIFO Error` -> watchdog -> homing dies
**There is no decimation rate that works. The mechanism is wrong, not the tuning.**

=> **MUST use the QUEUED PktUART API** (`hm2_pktuart_get_rx_status`,
`hm2_pktuart_queue_get_frame_sizes`, `hm2_pktuart_queue_read_data`). Those batch into the normal
servo-cycle TRAM packet: no extra packets, RT-safe. That is `tools/live/pso_live.comp`.

## WHY pso_live "failed" BEFORE (both were MY bugs, not the queued API)
1. **`addf` name needs a HYPHEN.** halcompile converts `_`->`-`. The function is
   `hm2_7i97.0.pktuart.0.pso-live`, NOT `...pso_live`. With the underscore the addf silently
   failed and **the comp never executed** — that is the entire reason it reported `parsed=0`.
   (Already corrected in `tools/pso_live_gate.sh` and `configs/ned5/pso_live.hal`.)
2. **`ifdelay` was 100** -> oversized frames (see below).
It also measured **zero collision signatures** — the only board-access path all evening that did
not disturb the machine. The queued approach is sound.

## THE FACTS YOU NEED (all measured on this machine)

### PSO signal (manual 6.12.5, confirmed on the wire)
- **17-character** ASCII message: `P` <sign> <5-digit multiturn> `,` <8-digit within-turn> `CR`
- **9600 bps, 7 data bits, EVEN parity, 1 start, 1 stop**
- **data output cycle 40 ms** -> ~17.7 ms of data, then **~22 ms of IDLE LINE**
- UART is configured 8N1 (no PARITYEN), so the parity bit lands in bit 7 -> **mask `& 0x7F`**
- A SEN request produces a **finite burst** (~1.8 s of repeated messages), then silence.
  It is NOT a permanent stream, and the value is a **SNAPSHOT taken at the SEN edge** —
  it does NOT track the axis afterwards. A fresh SEN pulse is MANDATORY for a truthful read.

### ifdelay — THE critical setting (now `[PSO]IFDELAY` in ned5_iron.ini)
Measured sweep of first-frame size:
| ifdelay | frame size |
|---|---|
| 10 | 1 (splits mid-message) |
| **20** | **17** (one clean message) CORRECT |
| **40** | **17** (one clean message) CORRECT |
| 100 | 769 (glues ~46 messages together) <-- was the bug |
**Use 30.** `pso_abs` now raises an `oversize` pin + logs loudly if a frame exceeds 40 bytes,
because ifdelay being wrong produces NO error otherwise — it fails completely silently.

### SEN / R4 wiring (operator-confirmed ground truth)
- **SEN is HARDWIRED to BOTH packs.** One pulse snapshots both. (7I84 `output-04` -> CN1-42)
- **R4 muxes only the RETURN path**: `output-05` energized = **A** reaches the Mesa,
  de-energized = **C**. R4 works correctly — every "R4 didn't switch" observation was
  stale OUT-pin state, not a mux failure.
- PSO lands on **7I85 TB1-19 (SRX+) / TB1-20 (SRX-)** -> 7I97 IO Pin 034.
- Manual 6.12 p.315: hold SEN high **>=1.3 s** before dropping it. Also "SEN is not acknowledged
  while the servo is ON" — but this can NEVER block us, because taking SEN low to make a request
  itself drops the packs to BB. Ruled out permanently; do not revisit.

### Working read sequence (verified: 3 reads in one session, alternating axes)
```
set R4 (output-05) for the axis
flush (reset)                       <- clears FIFO + rolling buffer; stale other-axis bytes
SEN LOW   ~3 s                      <- suppress=1, force=0  (beats the gate even machine-ON)
SEN HIGH                            <- force=1              (works even machine-OFF)
wait ~4-5 s for the burst
parse
```
Verified results: **C = mt -143 -> +44.143 deg**, **A = mt +35 -> +3.477 deg**
(both match board-free ground truth `tools/groundtruth/pso_read.sh`).

### Parsing (already correct in pso_abs — PORT THIS INTO pso_live)
At 9600 baud only a byte or two arrives per servo cycle, so message boundaries fall anywhere.
**Accumulate into a rolling buffer across cycles and scan it for the LAST complete
`P<sign><5>,<8>` message.** Per-frame parsing does not work. `reset` clears the rolling buffer.

### Position maths
`PE = multiturn * 2^26 + within` ; `2^26 = 67108864` counts per MOTOR rev
`angle = sign * (PE - PS) / (2^26 * GEAR) * 360`
- `PS` = the ONLY stored zero, `configs/params/head_zero.inc` (A: mt 36, w 44350458;
  C: mt -168, w 4280673)
- `GEAR_A = 128.25`, `GEAR_C = 203.7471` (from `tools/live/ned_params.sh`)
- **A_SIGN = -1, C_SIGN = +1** (right-hand rule; paired with `joint_a.inc SCALE = +2918.4000`)
- UNWRAPPED — no mod-360 fold. +190 stays +190; the path to zero matters.

## GUARDS ALREADY WRITTEN (keep them — they exist because of a real incident)
In `nedgui_handler.py::_hr_report`:
1. **Stale-read reject** — if this read's raw `(mt, w)` is identical to the previous axis's read,
   it is NOT our data; log and do NOT write home_offset.
2. **Range reject** — if `|deg| >= soft limit` (A 115, C 315), log and do NOT write.
*Why:* a stale read once reported A as `mt=-143` (C's value) -> **+504 deg on a +/-115 axis** ->
written into `ini.4.home_offset` -> homing acted on it. Never let an unvalidated number reach
`home_offset`.

## CURRENT STATE — **THE PORT IS DONE AND VERIFIED (2026-07-30 evening)**
All five steps below were executed and verified without motion:
- `tools/live/pso_live.comp` rewritten: queued API + pso_abs's rolling-buffer parser +
  `enable`/`reset`/`oversize`/`buflen`/`lastsize`/`newbytes` pins + `ifdelay_p` (default 30).
  Extras found while reading pktuart.c: `hm2_pktuart_queue_reset()` (a QUEUED FIFO flush —
  reset now really flushes, RT-safely, with a 2-cycle holdoff); frame-size array grown to 32
  (the driver pops up to 31 entries — the old 16-slot array was a driver-side overflow bomb);
  IDLE gates on NFRAMES>=1, not HASDATA (queue_get_frame_sizes pops exactly NFRAMES entries).
- Installed (`sudo halcompile --install`), loaded in `ned5_iron.hal` with
  `ifdelay_p=[PSO]IFDELAY`, addf'd with the HYPHEN name between hm2 read and write.
- postgui `pso-enable`/`pso-reset` nets re-enabled; `_home_cycle` re-pointed to
  `self._hr_start('c', lambda: self._hr_start('a', self._home_issue))`.
- The abandoned gate path went to `trash/` (`configs/ned5/pso_live.hal`, `pso_live_gen.hal`,
  `tools/pso_live_gate.sh`) and its `HALFILE = pso_live_gen.hal` line left the ini — it would
  have double-loaded pso_live and revived the obsolete pso_mux R4 auto-alternator.
- **Bench proof** (board-free halrun): C read twice in one session with a verified flush
  between (buflen 265 -> 1, multiturn zeroed): mt=-143 both, within differing by 3 counts,
  lastsize=17, oversize FALSE, zero collision signatures.
- **Live proof** (inside running LinuxCNC, machine off, no motion): same double read via
  halcmd, mt=-143 / ~+44.14 deg both times, lastsize=17, parsed 121 -> 243, sserial
  fault-count 0 before AND after, zero `llio->read in realtime` / RCFIFO / watchdog in the
  session log, InMux inputs live throughout. 1356 pins (1341 + 15 pso_live pins).
- `HOME_OFFSET = 0.0` for A and C in the param files stays (the live read overrides it via
  `ini.4/5.home_offset` at every HOME). Head physically ~A +3.5, C +44.1.

**REMAINING: the operator's homing test** — HOME ALL should now do read C -> read A ->
home -> post-home verify reads (~0.000 expected). Untested only because homing moves the
machine.

## MISTAKES NOT TO REPEAT (each cost real time tonight)
- `pkill -f linuxcnc` **matches the invoking shell** — use bracket patterns (`[l]inuxcnc`).
- Do **NOT** `ipcrm` shared memory in a stop script — it destroys LinuxCNC's NML buffers and the
  next start fails `NML_NO_MASTER_ERROR`. (Removed from `tools/lcnc_stop.sh`.)
- `halrun -f` **exits** after the file; a background session needs a trailing blocking command.
- Do not hide stderr (`2>/dev/null`) on pin writes a test depends on — a silent `setp` failure
  made `sen_meter.sh` print "R4 flipped" while output-05 never moved.
- `logclean.sh` trims `lcnc.log`; it destroyed startup tracebacks mid-debug.
- LinuxCNC pops a modal error dialog when stdin is not a tty; run under
  `script -q -c "linuxcnc ..." /tmp/x.log` to get the error as text instead.

## WRONG CONCLUSIONS ALREADY DISPROVEN (do not re-chase any of these)
| # | Wrong conclusion | Reality |
|---|---|---|
| 1 | PktUART RX "wedged", RXBUSY stuck | Transient sample; receiver healthy (RXBUSY=0, RXEN=1) |
| 2 | Pack transmits once per driver session | DMM proved a burst on EVERY request |
| 3 | "SEN not acknowledged while servo ON" blocks us | Unreachable: SEN-low itself drops the servo to BB |
| 4 | PSO is a gapless continuous stream | 17-char message every 40 ms with ~22 ms gaps |
| 5 | R4 mux isn't switching | Always switched; I read stale OUT-pin state |
| 6 | Z HOME_OFFSET/MAX_LIMIT misconfigured | Correct + deliberate (zero 5mm under switch, soft limit above zero) |
| 7 | All-limits-TRUE artifact; restart clears | My code was breaking Mesa comms |
| 8 | Lost IN COMMON jumper | Wrong |
| 9 | *71 +24V bus dead | Wrong (operator could see everything lit) |
| 10 | 7I97 dead/unreachable | Wrong — LinuxCNC cannot even start if so |
| 11 | Tool release = *65 only | THREE independent solenoids, all three required |
| 12 | R4 double-booking is a trap | Benign side-effect; R11 gates the brick anyway |
| 13 | Decimating the direct read fixes the watchdog | Caused RCFIFO Error instead — mechanism wrong, not tuning |
| 14 | pso_live's queued API is broken | Never ran: addf needs HYPHEN (pso-live) |
| 15 | Pack needs a double SEN pulse | Artifact of the ifdelay=100 oversized frames |

**Root cause of nearly everything: `ifdelay=100`** — glued ~46 messages into one 769-byte frame
with NO error anywhere. Every "hardware fault" above was downstream of that silent failure.
