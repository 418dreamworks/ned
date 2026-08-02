# Live in-config PSO reader (A/C head absolute) — design + integration plan

**Status:** offline design + comps that BUILD. **Not yet validated on the board** (deferred to a
free-board window). Opt-in: nothing here loads unless you source `pso_live.hal`. The working
board-free launch snapshot (`tools/pso_home.sh`) stays intact as the fallback.

Goal: read the Yaskawa head A/C absolute position (SEN/PSO over the Mesa 7I97 **PktUART**) LIVE
inside the running `ned5_iron` config, on HAL pins, so the GUI can show live A/C position and a
slow at-rest drift corrector can use it — WITHOUT the crash we hit before.

---

## 1. Why the naive live read crashed the machine (root cause, from source)

`tools/pso_abs.comp` / `tools/pso_sniff.comp` read the UART with **`hm2_pktuart_read()`**
(`linuxcnc/src/hal/drivers/mesa-hostmot2/pktuart.c:668`). That function issues
**`hm2->llio->read()`** — the *direct* read (pktuart.c:703, 758, 795, 810).

On an **Ethernet** board the low-level `read` is `hm2_eth_read()`
(`hm2_eth.c:787`, bound at `hm2_eth.c:1491`). Called from the realtime task it trips:

```
hm2_eth.c:800  ERROR: used llio->read in realtime task (addr=0x6800)
               This causes additional network packets which hurts performance
```

Each direct read is a whole extra UDP request/response *inside the servo cycle*. That starves the
7I84 smart-serial DoIt handshake, producing exactly what we saw:
`Smart Serial ... DoIt not cleared ... thread too fast`, `7i84.0.0 local error = (13) Communication
error / (3) Timeout`, `Watchdog has bit!`. The 7I84 drives SEN, the R4 mux, **all limit inputs**,
and tool I/O — so this is not tolerable in the live config.

## 2. The fix: the QUEUED PktUART API (RT-safe, no extra packets)

hm2_eth has two read paths (`hm2_eth.c`):
- `llio->read` = `hm2_eth_read` — **direct**, warns in RT, extra packet. (the bad one)
- `llio->queue_read` = `hm2_eth_enqueue_read` (hm2_eth.c:977, bound :1493) — **batched into the
  normal servo-cycle TRAM packet**. No extra packets, no RT warning, no sserial starvation.

PktUART exposes a queued read API built on `queue_read` (all in `pktuart.c`):
- `hm2_pktuart_get_rx_status(name)` (:928) — **free**: the RX status reg is auto-TRAM-read every
  servo cycle (registered at `pktuart.c:115`). Gives `has-data` (bit 21) and `nframes` (bits 16-20).
- `hm2_pktuart_queue_get_frame_sizes(name, fsizes)` (:849) — queues the frame-size reads.
- `hm2_pktuart_queue_read_data(name, data, bytes)` (:893) — queues the data reads.

Each queued read lands **one servo cycle later** (data already on the FPGA, no serial latency). The
canonical state machine is in `docs/src/man/man3/hm2_pktuart.3.adoc` ("Typical Usage") and the
reference user is `hm2_modbus.c` (`:765` get_rx_status, `:1018` queue_get_frame_sizes, `:1058`
queue_read_data). **This is the make-or-break fix.**

RX-only note: we never transmit (SEN is a hardware line held high in `ned5_iron.hal`, not TX), so
there is no TX handshake to manage — the state machine is just idle → sizes → fetch → data.

## 3. Architecture (three opt-in pieces)

```
 7I84 output-05 (R4 mux) <──[net]── pso_mux.r4-select        (userspace: pick A or C)
 head A/C  ──SEN/PSO──> 7I97 PktUART ──> pso_live (RT comp) ──> multiturn/within/parsed
                                                                     │
   joint.4/5.vel-cmd ─> wcomp ─> a/c-at-rest ─> pso_mux <───────────┘  (diff vs head_zero.inc,
                                                    │                    UNWRAPPED ±315)
                                                    └─> a/c-pos-deg ─> GUI label / drift corrector
```

- **`tools/live/pso_live.comp`** (RT, NEW, builds): the sserial-safe reader. Parses the streamed
  `P<±><5 mt>,<8 within>` frame to pins `multiturn, within, valid, parsed, parse_err, frames_seen,
  rxstatus, fsm`. Uses **only** the queued API above. Loaded named after the pktuart instance
  (same pattern pso_sniff/pso_abs use), so `addf hm2_7i97.0.pktuart.0.pso_live servo-thread`.
- **`tools/pso_mux`** (userspace python HAL comp, NEW, syntax-OK): drives R4 (`output-05`),
  alternates A/C, diffs the raw reading against the **only** stored zero
  (`configs/params/head_zero.inc`) using gears from `ned_params.sh`, and outputs UNWRAPPED
  per-axis degrees (`a-pos-deg`, `c-pos-deg`, `±315`, `flag` if outside). Touches no board
  register directly — only sets `r4-select` and reads `pso_live` pins.
- **GUI**: handler reads `pso_mux.a-pos-deg/.c-pos-deg` on a timer → live readout (diff below).

### Read semantics (per user) — opportunistic, at-rest, discardable
A read is wanted **only when the axis is AT REST**, purely to trim slow drift. No fixed rate, no
on-demand freshness guarantee. `pso_mux` therefore captures only while `a/c-at-rest` is TRUE and
**discards** the read if motion appears anywhere in the read window. A discarded read is harmless;
it just retries later. This is what makes the R4 alternation forgiving — mux/settle timing never has
to be exact. (If the axis moves right after a good read, LinuxCNC's own count is authoritative for
the move; the absolute read only re-anchors it again at the next rest.)

## 4. The opt-in HAL — NEW file `configs/ned5/pso_live.hal` (source it, don't inline)

Merge-safe: add ONE line at the end of `ned5_iron.hal` **or** an `[HAL]HALFILE` entry — nothing
else in the live path changes. Proposed content (verify addf order on-machine):

```hal
# ---- opt-in live PSO reader (see docs/commissioning/pso_live_reader_plan.md) ----
loadrt pso_live names=hm2_7i97.0.pktuart.0
# RT-safe queued reader: AFTER the board read, BEFORE the board write (like the hm2 sub-funcs)
addf hm2_7i97.0.pktuart.0.pso_live servo-thread   # place between hm2_7i97.0.read and .write

# at-rest windows on the commanded joint velocity (A=joint4, C=joint5)
loadrt wcomp count=2
setp wcomp.0.min -0.0005
setp wcomp.0.max  0.0005
setp wcomp.1.min -0.0005
setp wcomp.1.max  0.0005
addf wcomp.0 servo-thread
addf wcomp.1 servo-thread
net psoA-vel joint.4.vel-cmd => wcomp.0.in
net psoC-vel joint.5.vel-cmd => wcomp.1.in

# userspace mux/diff (drives R4 = output-05, currently un-netted so no conflict)
loadusr -Wn pso_mux python3 /home/brains/Documents/ned/tools/pso_mux
net pso-mt      pso_live.multiturn => pso_mux.mt
net pso-w       pso_live.within    => pso_mux.w
net pso-parsed  pso_live.parsed    => pso_mux.parsed
net psoA-rest   wcomp.0.out         => pso_mux.a-at-rest
net psoC-rest   wcomp.1.out         => pso_mux.c-at-rest
net pso-r4      pso_mux.r4-select  => hm2_7i97.0.7i84.0.0.output-05   # 1=A(NO) 0=C(NC)
```

Notes / integration diffs against current live files (do NOT hand-edit these — this documents
what the opt-in adds; they may change under us):
- `ned5_iron.hal`: **only** append `#INCLUDE`/source of `pso_live.hal` (or add its lines). Today
  `output-05` is **un-netted** (only `output-04`/SEN is driven, `ned5_iron.hal:171`) — so
  `net pso-r4 ... => output-05` is conflict-free. If a future edit nets `output-05`, remove that
  first. SEN (`output-04`) is untouched (stays held high).
- `pso_live` names the same pktuart instance as `pso_abs`/`pso_sniff` — only **one** may be loaded.
  In-config use `pso_live`; the board-free `pso_home.sh` path runs pre-launch (board free), so they
  never coexist.
- `run5.sh`: no change required. (Optionally, once live reading is trusted, `pso_home.sh` at launch
  can be dropped — but keep it until the live path is validated.)

## 5. GUI hookup — DONE (merged into the current handler)

The pre-home `absBox`/`lbl_abs_*` labels no longer exist; A/C now show directly in the main DRO
(`dro_a`/`dro_c`, driven by `_update_dro_ac`, 150 ms timer). That method was modified to PREFER the
live in-config value when present:

```python
def _live_ac(self, ax):        # NEW
    try:
        if hal.get_value('pso_mux.%s-valid' % ax):
            return hal.get_value('pso_mux.%s-pos-deg' % ax)
    except Exception:
        pass                   # pso_mux not loaded -> fall back
    return None
# in _update_dro_ac, after computing a,c (HOME_OFFSET pre-home / actual_position post-home):
la = self._live_ac('a');  a = la if la is not None else a
lc = self._live_ac('c');  c = lc if lc is not None else c
```

`_tagspan('dro_a'/'dro_c')` suffix preserved; `_number_widgets()` still skips `dro_*`. When
`pso_mux` isn't loaded (gate failed / comp not installed) `hal.get_value` raises → silent fallback.

## 5b. Integration + safety gate — DONE (offline)

- **`tools/pso_live_gate.sh`** (NEW): board-free A/B self-test. Loads hostmot2+hm2_eth+`pso_live`
  in a throwaway halrun, SEN high, R4=0, 2 s, then PASS = `parsed>0` AND zero of
  `llio->read in realtime` / `local error` / `Watchdog has bit`. On PASS it writes the active
  wiring (copy of `pso_live.hal`) into `pso_live_gen.hal`; on FAIL (incl. comp-not-installed) a
  no-op + loud warning to `lcnc.log`.
- **`tools/run5.sh`**: calls the gate AFTER `pso_home.sh`, BEFORE `linuxcnc` (board free then).
- **`ned5_iron.ini` `[HAL]`**: `HALFILE = pso_live_gen.hal` between the main HAL and postgui.
- **`configs/ned5/pso_live_gen.hal`**: shipped as a NO-OP default so a direct `linuxcnc` launch
  (not via run5) still starts; run5's gate regenerates it each launch.

So the reader reaches the live servo thread ONLY when it passed the board-free proof that same
launch; any failure silently falls back to the `pso_home` snapshot. `pso_home.sh` is untouched.

Launch → read → home → read-again flow (single `run5.sh`): pso_home writes the snapshot HOME_OFFSET
→ gate proves + activates `pso_live` → LinuxCNC starts with the live reader → the DRO shows the live
absolute (via `pso_mux`) **before** homing → operator presses HOME ALL → the DRO keeps showing the
live absolute, now matching LinuxCNC's homed count = homing confirmed.

## 6. Build / install

```
sudo halcompile --install /home/brains/Documents/ned/tools/live/pso_live.comp   # -> /usr/lib/linuxcnc/modules/pso_live.so
chmod +x /home/brains/Documents/ned/tools/pso_mux
```
(`halcompile --install` writes the module; it does NOT touch the board.)

## 7. ON-MACHINE test procedure  ⚠ NEEDS THE BOARD FREE (no linuxcnc/milltask running)

Do NOT run while the operator is using LinuxCNC. Each step: first confirm
`pgrep -f 'linuxcnc|milltask'` is empty.

1. **Board-free reader sanity** (proves queued reads work + NO sserial errors). A harness HAL that
   loads hostmot2+hm2_eth+`pso_live`, holds SEN high, sets R4=0 (C), runs ~2 s, then
   `show pin hm2_7i97.0.pktuart.0` and greps dmesg. PASS = `parsed` increments AND **no**
   `llio->read in realtime`, **no** `local error`, **no** `Watchdog has bit`. (Contrast: the same
   harness with `pso_sniff` throws those errors — that's the A/B proof.)
2. **R4 mux**: repeat with R4=1 → A frames; toggle R4=0 → C frames. Confirm each axis streams and
   that a `parsed` gap appears right after a toggle (the settle to tune `SETTLE_FRAMES`).
3. **Degrees**: at eyeball zero, `pso_mux` `a/c-pos-deg` ≈ 0; hand-move a known amount, confirm the
   unwrapped value tracks and never folds (e.g. +190 stays +190).
4. **In-config, low-risk**: source `pso_live.hal`, start LinuxCNC, watch `mesa.log`/`lcnc.log` for
   ANY sserial/watchdog error for a few minutes with the machine enabled but idle. Must be clean.
5. Only after 1-4 are clean: wire the GUI timer and (later, separate task #10) the drift corrector.

## 8. Verified offline vs needs on-machine

| Item | Status |
|---|---|
| Root cause (direct vs queued llio read) | **Verified** from source (cited above) |
| `pso_live.comp` compiles/links | **Verified** (`halcompile --compile` exit 0) |
| Queued state-machine matches the documented contract | **Verified** vs man page + `hm2_modbus.c` |
| `pso_mux` syntax | **Verified** (`py_compile`) |
| Unwrapped ±315 diff math | **Verified** (same formula as `pso_home.sh`, no fold) |
| No sserial collision at runtime | **NEEDS BOARD** (step 1 A/B) |
| Frame packing/parse from queued `rxdata[]` on real bytes | **NEEDS BOARD** (step 1) |
| R4 settle count, at-rest thresholds | **NEEDS BOARD** tuning (steps 2-3) |
| GUI live readout | proposed diff; apply after steps 1-4 |
```
