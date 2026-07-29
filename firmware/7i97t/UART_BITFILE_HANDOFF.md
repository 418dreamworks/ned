# HANDOFF — build a 7I97T bitfile with a UART (to read the Yaskawa absolute encoder)

> ## ✅ DONE (2026-07-29)
> Built + flashed. Bitfile = `hostmot2/7i97t_7i85sd_pktuart.bin`; exact recipe =
> `hostmot2/pktuart_build/BUILD_NOTES.md`. A full **PktUART** landed on **I/O 34** (RX) /
> I/O 35 (TX) — confirmed by `mesaflash --readhmid` (PktUARTRX/TX present) and a LinuxCNC
> load (`created PktUART Interface hm2_7i97.0.pktuart.0`, no version rejection). `ned.hal`
> now has `num_pktuarts=1`. The "confirm with Mesa/PCW" open question below was resolved
> empirically: the PktUART builds and loads on I/O 34. Plan kept for record.

**Do this on an x86 Windows/Linux box with Efinix Efinity installed.** It cannot be built on ned's
Raspberry Pi 5 (ARM; Efinity is x86-only). Deliverable: a `.bin` to flash onto the 7I97T.

---

## Goal
Add a **hostmot2 PktUART (async serial *receiver*)** on **FPGA I/O 34** — the 7I85S sserial `RXData1`
pin = screw terminals **TB1-19 (SRX+) / TB1-20 (SRX−)**. This is the last piece needed for
**reboot-surviving absolute homing** of the head **A** and **C** axes (no home switch, no re-homing
each session).

## Why
- Head A/C are Yaskawa **SGDXS-2R8A00A** step/dir servos with **26-bit battery-backed absolute
  encoders** but **no home switch**. The drive re-emits absolute position as an **async serial stream
  (PSO)**; read it once at boot → home; the battery retains it across power cycles.
- The 7I85's encoder inputs are all **2:1 hardware-muxed** — useless for a continuous UART. The **only
  free non-muxed RS-422 receiver** on the whole stack is the 7I85 sserial **RXData1 = I/O 34 = TB1-19/20**.
- Both drives' PSO are wired through **relay R4** (a DPDT mux) onto that one pin — read A at boot, flip
  R4, read C. So **one UART RX covers both axes.** (See `docs/tracing/relays.md` → R4.)

## The signal it must read
- **RS-422 differential**, async, **9600 baud, 7 data / even parity / 1 stop (7E1)**, ASCII.
- Frame = **17 chars**: `P ± NNNNN , PPPPPPPP <CR>` (status, sign, 5-digit turns, comma, 8-digit
  within-turn, CR). No checksum. ~40 ms cycle. Continuous (drive `Pn515=7`, no-SEN mode).
- **PktUART is 8-bit** → configure **8N1** and mask/verify the parity bit in software; the ASCII char
  is the **low 7 bits**.

## Toolchain
- **Efinix Efinity** (free, efinixinc.com). The 7I97**T** is an **Efinix Trion** FPGA — the hostmot2
  source is all `_efx`. Windows or x86-Linux.

## Source (in this repo)
- **`firmware/7i97t/hostmot2/source/7i97t-hm2.zip`** (also `7i97t25-hm2.zip`) — hostmot2 VHDL + pinout
  files + the Efinity project. Copy it to the build box and unzip.
- Reference (current pin map): `firmware/7i97t/hostmot2/7i97t_7i85sd.pin` — shows
  `TB1-19,20  34  IOPort SSerial 0 RXData1 (In)` (the pin we're repurposing).

## The edit — `PIN_7I97_7I85SD_51.vhd`
Copy the UART pattern from the ready-made example **`PIN_UA2_34.vhd`** (same source dir):

1. **Module list** (top of the file) — add a UART Receiver instance:
   ```
   (UARTRTag,  x"00",  ClockLowTag,  x"02",  UARTRDataAddr&PadT,  UARTRNumRegs,  x"10",  UARTRMPBitMask),
   ```
   (RX only; a UARTTTag transmitter is not needed.)

2. **Pin assignment** — find the line that assigns **I/O 34** to the sserial RX (`...SSerialTag...RXData1... -- I/O 34`)
   and replace it with a UART RX:
   ```
   IOPortTag & x"00" & UARTRTag & URDataPin,      -- I/O 34  (was SSerial RXData1; now PktUART RX = TB1-19/20)
   ```
   (See `PIN_UA2_34.vhd` lines `IOPortTag & x"00" & UARTRTag & URDataPin` for exact syntax.)

3. **Leave everything else intact** — especially the **7I84's sserial on `RXData0` / I/O 31 / TB4**
   (different channel, keep it), the 4 StepGens, the MuxedQCount encoders, the 6 PWMs, SSR, InMux, LED.

4. Regen the IDROM / module count if the build flow needs it (the hostmot2 build scripts + Efinity
   project handle this).

## Build → flash
- In Efinity: open the project, synthesize / place & route, generate the **`.bin`**.
- Sanity: the module list should now include a PktUART/UART.
- Copy the `.bin` to ned's Pi, then:
  ```
  mesaflash --device 7I97T --addr 10.10.10.10 --write <new>.bin --verify
  mesaflash --device 7I97T --addr 10.10.10.10 --reload      # or power-cycle
  mesaflash --device 7I97T --addr 10.10.10.10 --readhmid | grep -i uart   # confirm it's there
  ```
  (mesaflash write/verify is reliable on this board; realtime halrun loads have wedged with exit 144 —
  reboot if needed.)

## ⚠ Open question — confirm with Mesa (PCW) BEFORE building
Whether a hostmot2 **PktUART RX can actually be placed on I/O 34** (the sserial pin) in a buildable
7i97t bitfile is the **one unproven assumption**. Peter Wallace at Mesa can confirm the pin placement —
or just build the correct bitfile for you. Ask him first; it may save the whole build effort.

## Not part of the bitfile (LinuxCNC side, do after)
- HAL: a component reads the pktuart RX FIFO, frames on CR, parses the 17-char frame → A/C absolute,
  sets joint 5/6 home offset at startup.
- HAL: drive R4 coil for the boot read (`OUTPUT5 = sig-rotary-power OR boot-mux-read`): read C (coil
  off) → flip to A (coil on) → read → home.

## If the FPGA build is too much
Skip the reflash: read PSO with a **Pi GPIO UART** (2× RS-422 receiver → Pi UART RX @ 7E1) or a small
**MCU** (Pi Pico). Same R4 mux, same HAL parse. See `docs/mesa_7i85s_wiring.md`.

## Repo references
- `docs/mesa_7i85s_wiring.md` — head feedback + PSO/R4-mux wiring (the TB1-19/20 landing)
- `docs/tracing/relays.md` → **R4** — the DPDT PSO mux (poles 3 & 4)
- `docs/servo/yaskawa_params_quickref.md` — PSO protocol + params (9600 7E1, 17-char frame, Pn515=7)
- `firmware/7i97t/hostmot2/7i97t_7i85sd.pin` — current pin map (I/O 34 = SSerial RXData1)
