# Question for PCW — PktUART RX receives only the FIRST burst after driver load (7I97T / hm2_eth)

**Setup:** 7I97T over Ethernet (hm2_eth), PktUART **RX only** (we never transmit). Source is a
Yaskawa servopack's PSO absolute-position output: **9600 baud, 7E1** (parity masked in software),
RS-422 into the PktUART RX pin via a relay that muxes two drives onto the one UART.

The drive transmits **one burst per request** (we pulse its SEN line). A burst is ~786 bytes: the
same 16-char message `P-00143,03117264` repeated back-to-back with **no interframe gap**, so the
whole burst arrives as ONE oversized frame.

## What we measured
- **The signal is confirmed present on the wire for EVERY request** -- verified with a meter
  directly on the RS-422 pair at the Mesa input, alternating the mux between the two drives and
  issuing repeated requests. Every request produces line activity. The drives are not the issue.
- **The PktUART receives only the FIRST burst after the hostmot2 driver loads.** Every subsequent
  burst yields `hm2_pktuart_read()` = **0 bytes, 0 frames**, indefinitely, even though the meter
  shows the data arriving.
- RX mode register at that point reads **0x16006408** = RXEN set, **RXBUSY clear**, HASDATA clear,
  NFRAMES 0 -- i.e. it looks like a perfectly healthy idle receiver. It simply never receives again.
- **Only unloading/reloading the driver restores it.** A fresh `halrun` always works -- and the
  servopack cannot observe a driver reload, so the asymmetry is on the Mesa side.

## Tried, none of which restores reception
`hm2_pktuart_reset()`; `hm2_pktuart_config()` with `FLUSH|RXEN`; the same with `FORCECONFIG` to
guarantee the register writes are not skipped; a full RXEN off->on cycle; gating reads on HASDATA;
clearing our own buffers; long gaps (15 s) between requests.

## Questions
1. After a large frame with no interframe gap (a continuous ~786-byte burst at 9600 baud), is the
   RX block expected to stop receiving until re-initialised? Is there an overrun/oversize state
   that `hm2_pktuart_reset()` / `hm2_pktuart_config()` do not clear?
2. **What does driver load do to the PktUART RX that the runtime API does not?** That write is
   presumably our fix.
3. Is `max_frame_length` (we pass 1024, `num_frames` 4) relevant here -- i.e. can an oversized
   frame wedge the receiver rather than simply being truncated?
4. A forum post mentions `mesaflash --wpo 0x6800=0x00010000` clearing the RX FIFOs. Note that is
   `0x00010000`, whereas `HM2_PKTUART_CLEAR` is `0x80010000`. Is the bit-31 difference significant,
   and is the plain FIFO-clear exposed anywhere callable from a realtime component?
