# 7i97t_7i85sd_pktuart bitfile — build recipe (FINAL STATE)

The flashed bitfile `../7i97t_7i85sd_pktuart.bin` = the stock Mesa **7i97t_7i85sd**
bitfile with a **hostmot2 PktUART added on FPGA I/O 34/35** (the 7I85 sserial
RXData1/TXData1 pins = 7I85 screw terminals **TB1-19/20**). This reads the Yaskawa head
**A/C absolute-encoder serial (PSO)** through the R4 mux — see `docs/mesa_7i85s_wiring.md`
and `docs/tracing/relays.md` → R4.

- Device: Efinix **Trion T20F256**, timing model C4.
- Built with **Efinity 2026.1** (project is stock 2021.2; 2026.1 opens/builds it fine).
- Flashable output = Efinity's `outflow/seveni97t.hex.bin` (678650 bytes) → renamed to
  `7i97t_7i85sd_pktuart.bin`. (`.bit`/`.hex` are the 2 MB intermediate format — NOT flashable.)

## Source
Base = `../source/7i97t-hm2.zip` (stock Mesa hostmot2 Efinix source, project `seveni97t.xml`).
The three files here are the **only** changes from that stock source:

### 1. `PIN_7I97_7I85SD_51.vhd` — add the PktUART, take I/O 34/35 off sserial ch1
- `ModuleID` array: two trailing `(NullTag,…)` rows → the PktUART pair:
  ```
  (PktUARTRTag, x"00", ClockLowTag, x"01", PktUARTRDataAddr&PadT, PktUARTRNumRegs, x"00", PktUARTRMPBitMask),
  (PktUARTTTag, x"00", ClockLowTag, x"01", PktUARTTDataAddr&PadT, PktUARTTNumRegs, x"00", PktUARTTMPBitMask),
  ```
- `PinDesc`, I/O 34 & 35 (were SSerial RXData1 / TXData1):
  ```
  IOPortTag & x"00" & PktUARTRTag & PktURDataPin,   -- I/O 34
  IOPortTag & x"00" & PktUARTTTag & PktUTDataPin,   -- I/O 35
  ```
- The instance count derives automatically: `hostmot2_efx.vhd` sets
  `PktUARTs := NumberOfModules(TheModuleID, PktUARTRTag)` = 1 → one RX + one TX built.
  No count constant to bump. 7I84 sserial (ch0, I/O 31/32/33) is untouched.

### 2. `TopEthernet16HostMot2_efx.vhd` — select this pinout
Stock file builds `PIN_7I97D_51` (bare 7I97). Switched the active pinout:
- comment  `use work.PIN_7I97D_51.all;`        (was line 146)
- uncomment `use work.PIN_7I97_7I85SD_51.all;` (line 149)
- card `use work.i97t_x20card.all;` (line 85) already active — leave it.

### 3. `seveni97t.xml` — P&R seed
- `place_and_route` seed `3` → **`7`** (the seed annotated `--seed 7 *` next to the
  pinout; the stock seed 3 had `last_run_state="fail"`). Seed 7 routes clean.

## Build (Efinity CLI, x86 Windows/Linux — NOT on the Pi, ARM)
```
efx_run.bat seveni97t.xml --flow compile
```
All stages must report PASS: map, interface, pnr, pgm, export_bitstream.
Result: `outflow/seveni97t.hex.bin` (678650 bytes).

## Flash (on ned's Pi)
```
mesaflash --device 7I97T --addr 10.10.10.10 --write 7i97t_7i85sd_pktuart.bin   # auto-verifies
mesaflash --device 7I97T --addr 10.10.10.10 --reload
mesaflash --device 7I97T --addr 10.10.10.10 --readhmid | grep -i uart          # → PktUARTRX/TX
```
Rollback = `../7i97t_7i85sd.bin` (stock, no UART); card also has `7i97t_16m_fallback.bin`.

## LinuxCNC
`ned.hal` hm2_eth config adds `num_pktuarts=1` → instance `hm2_7i97.0.pktuart.0`
(RX on I/O 34). Read the PSO with a component using `hm2_pktuart_config`
(baudrate 9600) + `hm2_pktuart_read` (8N1, mask parity in software → low 7 bits ASCII).
`../../../linuxcnc/src/hal/components/mesa_pktgyro_test.comp` is the read template.
