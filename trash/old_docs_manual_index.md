# Manual Index

## Yaskawa Sigma-X Servopack (SGDXS) — Analog/Pulse Train
- **File:** `SIEPC71081203i_8_0.pdf` (40.9MB)
- **Manual No:** SIEP C710812 03I
- **Covers:** SGDXS-□□□□00□ (Σ-XS servopack with analog voltage/pulse train)
- **Key pages:**
  - p.50: Σ-X series overview (Σ-XS single-axis, Σ-XW dual-axis, Σ-XT triple-axis)
  - p.51: Nameplate interpretation. Input: 1PH/3PH AC200-240V 50/60Hz
  - p.54: Model number breakdown (SGDXS). Capacity codes, voltage, interface (00=analog/pulse train), hardware options (0008=single-phase 200VAC input)
  - p.55: Servomotor model number breakdown (SGMXJ/SGMXA/SGMXP/SGMXG)
  - p.57-59: Motor/servopack combination tables. SGMXJ-04A → SGDXS-2R8A
  - p.128: Main circuit terminal wiring
  - p.144: Servomotor terminals and encoder connector (CN2)
  - p.154: I/O signal connector (CN1)
  - p.167: Safety connector (CN8)

## Yaskawa Sigma-X Rotary Servomotor
- **File:** `siepc23021000h_7_0.pdf` (20.5MB)
- **Manual No:** SIEP C230210 00H
- **Covers:** SGMXJ, SGMXA, SGMXP, SGMXG rotary servomotors
- **Key pages:**
  - p.52: SGMXJ model designations. 7th digit options: 1=none, C=holding brake, E=oil seal+brake, S=oil seal
  - p.53: SGMXJ specifications (200V)
  - p.54: SGMXJ ratings. 04A: 400W, 1.27 Nm rated, 4.46 Nm peak, 2.5A rated, 9.3A peak, 3000 RPM rated, 6000 RPM max
  - p.61-69: SGMXJ external dimensions
- **Motor decode (SGMXJ-04AUA6SC2):**
  - 04 = 400W, A = 200VAC, U = 26-bit absolute encoder, A = rev A, 6 = straight w/key+tap, S = oil seal (NO brake), C = destination, 2 = Σ-7 compatible

## Yaskawa Sigma-7 Servopack (SGD7S) — Analog/Pulse Train
- **File:** `sieps80000126w_25_0.pdf` (10.5MB)
- **Manual No:** SIEP S800001 26W
- **Covers:** SGD7S-□□□□00A□□□□□□□□ (Σ-7S servopack with analog voltage/pulse train)
- **Key pages:**
  - p.1-6 (page 44): Model number breakdown. Capacity codes, 4th digit A=200VAC/F=100VAC, 5th-6th=00 analog/pulse train
  - p.1-7 (page 45): Servomotor model number breakdown (SGM7J/SGM7A/SGM7P etc.)
  - p.1-9 (page 47): Motor/servopack combination tables. SGM7J-04A → SGD7S-2R8A or 2R8F

## Yaskawa Machine Control Products Catalog
- **File:** `docs/mesa/yaskawa_sigma7_catalog.pdf` (4.3MB)
- **Manual No:** BL.MTN.01
- **Key pages:**
  - p.26-27: System configuration diagram (Sigma-X 200V, Sigma-7 400V, servopacks lineup)
  - p.32-33: Servo motor portfolio and servopack combinations overview

## Servo Dynamics SDSMB 1625-17 (Brushless)
- **File:** `docs/servo_dynamics_sdsm_manual.pdf` (21.1MB)
- **Covers:** SDSMB 1625-17 and SDSMB(ET) 1625-17 brushless servo drives
- **Note:** Our drives are SDSM (brushed), NOT SDSMB (brushless). Pinouts differ.
- **Key pages:**
  - p.9-10: J1 connector pinout (brushless version — NOT our drives)
  - p.11: J2 connector (motor power + bus power), J3 low gain jumper, J4 encoder inputs
  - p.13: Test points and LED indicators (RUN green, BUS/RMS/SURGE red)
  - p.18-21: Installation drawings (Figure 3B, 3C, 3H, 3I — all brushless)

## Mesa Cards
- **7i77 manual:** `docs/mesa/7i77_manual.pdf` — 6-axis analog servo + I/O daughter card
  - p.7-8: Encoder connector pinouts (TB3/TB4, 8 pins per encoder: QA,/QA,GND,QB,/QB,+5V,IDX,/IDX)
  - p.9: Analog drive connector (TB5, 4 pins per axis: ENA-,ENA+,GND,AOUT)
- **7C81 manual:** `docs/mesa/7c81_manual.pdf` — RPi SPI FPGA motherboard, 3x 26-pin headers
- **7i76 manual:** `docs/mesa/7i76_manual.pdf` — 5-axis step/dir + I/O daughter card
