# Mesa FPGA firmware (bitfiles)

Prebuilt Mesa bitfiles for flashing the cards with `mesaflash`. Kept in-repo so a
reflash never depends on a fresh download.

## `7i97/` — downloaded 2026-06-26 from `mesanet.com/software/parallel/7i97.zip`

⚠️ **WRONG FAMILY for our card — reference only, do NOT flash.**

Our card is a **7I97T** (mesaflash `--device 7i97t`), currently running
`7i97t_7i85sd`. Its live IDROM reports **Clock High = 160 MHz**.

This `7i97.zip` is the plain **7I97** (non-T) set: the `7i97_7i85d.pin` reports
**Clock High = 200 MHz**, and it muxes encoder ch3/ch4 onto **TB3**, not TB2.
Different silicon timing + wrong pinout → not for the 7I97T.

The correct archive for this card is **`7i97t.zip`** (note the `t`):
`mesanet.com/software/parallel/7i97t.zip` — that is where the running
`7i97t_7i85sd.bin` came from (see memory `ned-7i97-firmware-mismatch`).

Variants present in `7i97/hostmot2/`: `7i97_D`, `7i97_dpd`, `7i97_fallback`,
`7i97_7i74D`, `7i97_7i76d`, `7i97_7i78D`, `7i97_7i85d` (+`.pin`).

## Card flash backup

`/tmp/7i97t_current_backup.bin` (+`.sha256`) — full backup of the 7I97T flash as
of 2026-06-26 before any reflash. (In /tmp; move somewhere durable if keeping.)
