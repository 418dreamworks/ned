# Mesa Product Details (fetched live in conversation)

Stock figures as of fetch date (2026-06-14).

## FPGA Cards (Main)

### 7I97T (id 397) — $279 — **5 in stock**
- Ethernet motion control, analog servo focused
- 6 analog ±10V outputs
- 6 encoder inputs
- 16 isolated digital inputs
- 6 isolated digital outputs
- 1 Smart Serial port
- 1 25-pin (DB25) expansion port
- Universal output (sourcing/sinking/push-pull selectable)
- Manual: http://www.mesanet.com/pdf/parallel/7i97tman.pdf

### 7I96S (id 374) — $149 — **222 in stock**
- Ethernet motion control, step/dir focused
- 5 step/dir outputs
- 1 encoder input
- 11 digital inputs
- 6 digital outputs
- 1 analog spindle output
- 1 RS-422/485 serial interface (sserial)
- 1 25-pin DB25 expansion port (compatible with Mesa 25-pin daughter cards or parallel port BOBs)

### 7I80HDT (id 386) — $149 — **5 in stock**
- Ethernet (100 BaseT) bare FPGA
- 3× 50-pin slots for daughter cards
- 72 raw I/O bits (5V tolerant, 24mA sink, with pullups for optos/contacts)
- Supports firmware modules: step gen, encoder, PWM, digital I/O, serial
- Bulk discount at 10+ units

## Analog Daughter Cards (PWM/step → ±10V converters)

### 7I77U (id 422) — $229 — **Out of Stock**
- DB25 daughter card, universal output version
- 6 analog ±10V servo outputs
- 6 encoder inputs
- 32 isolated inputs
- 16 isolated outputs (universal sourcing/sinking/push-pull)
- 1 Smart Serial port
- Compatible with 25-pin FPGA cards: 6I25, 7I92TM, 7I96 (presumed 7I96S too)
- Field wiring via 3.5mm pluggable screw terminals

### 7I77 (id 120) — $229 — **Out of Stock**
- Older sourcing-output version of 7I77U
- Same 6 analog + 6 encoder + 32 in + 16 out spec
- DB25 to 25-pin FPGA cards (5I25, etc.)
- External diodes required on inductive loads (vs 7I77U universal)

### 7I48 (id 100) — $99 — **Out of Stock**
- 6-axis analog servo interface
- Converts complementary PWM signals from FPGA to ±10V
- Conditions encoder inputs (TTL or RS-422)
- 50-pin connector

### 7I33 (id 92) — $69 — **Out of Stock (obsolete)**
- 4-axis analog servo interface
- Replaced by 7I36

### 7I33TA (id 74) — $79 — **Out of Stock (obsolete)**
- 4-axis analog servo interface
- Replaced by 7I36

### 7I36 (id 366) — $149 — **30 in stock**
- 4-axis analog servo interface
- 4 analog ±10V outputs (from PWM)
- 4 encoder inputs
- **50-pin header connector**
- Matches Mesa Anything I/O 50-pin pinout

### 7I65 (id 109) — $279 — **Out of Stock**
- 8-axis analog servo interface
- 8× 16-bit DAC ±10V outputs
- 8× 12-bit analog inputs
- 50-pin header

## Step/Dir Daughter Cards (50-pin)

### 7I52S (id 106) — $69 — **10 in stock**
- 12 differential outputs = 6 step/dir pairs (or PWM/dir)
- 6 encoder inputs
- 50-pin header

### 7I52 (id 105) — $69 — **7 in stock**
- 6 channel RS-422 serial + 6 encoder
- Not direct step/dir (use 7I52S for that)
- 50-pin header

### 7I47 (id 98) — $69 — **Out of Stock**
- 12 channel RS-422 interface
- Step/dir capable (up to 6 step+dir)
- 50-pin header

### 7I47S (id 99) — $79 — **Out of Stock**
- 12 input, 8 output RS-422 interface
- Step/dir capable
- Isolated 5-15V analog out (potentiometer-style, for spindle)
- 50-pin header

## Step/Dir Daughter Cards (DB25)

### 7I85S (id 125) — $69 — **8 in stock**
- 4 encoder inputs (with index)
- 8 differential outputs (configurable as 4 step/dir pairs OR PWM)
- 1 RS-422 serial interface
- DB25 connector

## Digital I/O Daughter Cards

### 7I84U (id 410) — $79 — **24 in stock**
- 32 isolated digital inputs
- 16 isolated outputs (universal sourcing/sinking, 5-28VDC, 500mA per output)
- Sserial RJ45 interface
- Daisy-chain up to 32 cards (=1024 in, 512 out max)
- 3.5mm screw terminals

### 7I37TA (id 395) — $89 — **35 in stock**
- 8 isolated outputs (48VDC, 2A, MOSFET)
- 16 opto-isolated inputs (6-36V, reverse polarity protection)
- 50-pin connector
- Compatible with 4I24M, 4I24H, and other 50-pin Anything I/O cards

## Sserial Gateway

### 7I44 (id 96) — $69 — **39 in stock**
- 8 RJ45 channels (sserial output to daughter cards)
- 50-pin connector to FPGA card
- Independent receive/transmit with drive enable per channel
- Supplies 5V on RJ45
- Bulk discount: $55 at 10+, $50 at 100+

## Summary by Availability

**In stock:**
- 7I96S (222), 7I44 (39), 7I37TA (35), 7I36 (30), 7I84U (24), 7I52S (10), 7I85S (8), 7I52 (7), 7I80HDT (5), 7I97T (5)

**Out of stock:**
- 7I77U, 7I77, 7I48, 7I33 (obsolete), 7I33TA (obsolete), 7I65, 7I47, 7I47S
