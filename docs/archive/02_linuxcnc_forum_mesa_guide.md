# LinuxCNC Forum: Which Mesa Card Should I Buy?

Source: https://forum.linuxcnc.org/27-driver-boards/51605-which-mesa-card-should-i-buy?start=0
Author: spumco

## TLDR Version

**Minimum Hardware Required:**
- One FPGA 'main' card
- Screw terminal connections for drives and IO (on card or daughter card)
- Power supply

**No network switch or other 'stuff' required.**

### Simple Stepper Machine Example:
**7i96S card features:**
- 5 step/direction axes
- 11 inputs
- 6 outputs
- 1 analog spindle output
- 1 encoder input
- 1 Smart Serial port
- 1 25-pin expansion port

### Analog Servo Machine - Option 1:
**7i97T card features:**
- 6 +/-10v analog axes
- 6 encoder inputs
- 16 inputs
- 6 outputs
- 1 Smart Serial port
- 1 25-pin expansion port

### Analog Servo Machine - Option 2:
Combination approach:
- **7i92TH FPGA card:** 2x26-pin headers (no screw terminals)
- **7i77 daughter card:** DB25 input via adapter cable, provides:
  - 6 +/-10v analog axes
  - 6 encoder inputs
  - 32 inputs
  - 16 outputs
  - 1 Smart Serial port

## Background

Mesa cards are not motion controllers. They function as "extremely capable and fast breakout boards for LCNC with onboard FPGA chips that take care of high-speed timing and signal management."

Minimum requirement: An FPGA card (the 'main' card). Optionally, daughter cards connect to the FPGA card.

## FPGA Cards

### PC Connection Types

**Ethernet:**
- Direct Ethernet cable from LCNC computer to Mesa FPGA card
- No network switches allowed
- Need second NIC for internet

**SPI (Raspberry Pi):**
- Direct GPIO plug-in
- Examples: 7C80 & 7C81
- NOTE: rpi 5 is not supported for direct plug-in (SPI) as of 2/2024

**Plug-N-Go Kits:** PCI/PCIe with external second card

### Onboard IO

**All-in-One:** Onboard screw terminals + expansion (e.g. 7i76EU)
**No-Onboard IO:** Just expansion connectors (e.g. 7i80DB, 7i92TH)

No performance difference between all-in-one vs. equivalent no-IO + daughter card combo.

### Expansion Ports

**All-in-one:** One or two 26-pin expansion connectors
**No onboard IO may have:**
- Two or more 26-pin connectors
- Two or more DB25 connectors
- Combination of 26-pin and DB25
- Two or more 50-pin IDC connectors

**Compatibility rule:** DB25 daughter cards can adapt to 26-pin FPGA ports with special cable. 50-pin daughter cards cannot plug into DB25/26-pin (and vice-versa).

## Daughter Cards

### 50-Pin Cards
- High-speed (step/dir, encoders)
- Also general purpose IO
- Can act as gateways for more daughter cards
- More pins/features than DB25

### DB25 Cards
- Similar capabilities, fewer pins
- Can act as gateways

### Smart Serial (sserial) Cards
- RS-422 over RJ45 connector (NOT ethernet protocol)
- Cut off one RJ45 end, terminate at RS-422 port
- One sserial card per RS-422 port, NO daisy chaining
- Network switches do not work

### Sserial Gateway Cards
- Dedicated sserial gateways (e.g. 7i44)
- Up to 8 sserial daughter cards per gateway

**Extreme example (7i80HDT):**
- 3× 50-pin slots
- 2× 7i44 gateway cards
- 16× 7iA0 sserial IO cards
- **Total: 768 inputs and 384 outputs**

## Drive Signal Types

**Common types:** step/dir, PWM, analog (±10V)

**Retrofit:** Older drives often analog or PWM
**New build:** Choice of drive type

**Mesa "stepgens":** Step and direction signal generators. Each stepgen = one axis.

**PWM:** Stepgens can be converted to PWM with modified firmware.

**Analog:** Cannot be created from stepgens. Must use an analog-out card.

**Counting examples:**
- Stepper gantry router: 4 motors (X, Y1, Y2, Z) = at least 4 stepgens
- 2-axis lathe with analog servos + spindle: 3 motors = at least 3 analog outputs

## IO Considerations

For each input/output, document:
- Voltage supplied/required
- Current/amps
- Sink or source
- Analog? (potentiometer, transducer)

**Modern Mesa cards** can be configured for both sinking and sourcing inputs/outputs.

**Other considerations:**
- Spindle control type (on/off, 0-10V, PWM, analog servo)
- Encoder feedback (linear encoders, motor encoders, spindle encoder)
- Operator console complexity (buttons, switches, lights)
- Plasma (use THCAD series)
- Future expansion needs

## Selection Process

1. **Host connection type:** Ethernet / Plug-N-Go / Direct plug-in (Pi)
2. **Drive signal type and count:** Step/dir, PWM, analog
3. **IO type & quantity:** Digital, analog, sink/source, voltage
4. **Additional features:** Encoders, spindle control, expansion
5. **Physical mounting:** Space, operator console location

**Card selection:**
1. Pick an FPGA card
2. Pick compatible daughter card(s) if needed
3. Pick sserial daughter cards if needed
4. Verify drive count, IO count, expansion ports

**Editor's note on MPG:** "MPG column refers to dedicated MPG inputs which are pre-configured for use with typical handwheel encoders. Even if a board shows '0' for MPG inputs in the table if there are enough free inputs a board & LCNC can usually be configured to accept low-speed A/B encoder inputs - it just may not be as easy as with those boards with dedicated MPG inputs."

## Example 1: Manual Lathe to CNC Conversion

**Machine:**
- 2 axes, closed-loop stepper motors
- 2 drive alarms
- 2 home switches
- 1 spindle via VFD
- 1 spindle encoder

**Operator station:**
- 2 MPGs
- 1 axis selector (2 positions)
- 1 jog increment switch (3 positions)
- 1 spindle override pot
- 1 feed override pot
- 1 e-stop
- 2 buttons (start & feed-hold)

**IO Summary:**
- Drives: 2 step/dir
- Digital inputs: 10
- MPG inputs: 2
- Analog inputs: 2
- Analog outputs: 1
- Digital outputs: 2 (spindle FWD/REV)

**Suggested cards:** 7i96S + 7i73 for operator station

## Example 2: Self-Built CNC Router

**Machine:**
- 4 axes step/dir servo
- 4 drive alarms
- 4 drive enables
- 4 home switches
- 1 spindle via VFD

**Operator station:**
- 1 MPG
- 1 axis selector (2 positions)
- 1 jog increment switch (3 positions)
- 1 feed override encoder with reset
- 1 e-stop
- 8 buttons

**IO Summary:**
- Drives: 4 step/dir
- Digital inputs (main enclosure): 8
- Digital inputs (operator station): 13
- MPG inputs: 4
- Analog outputs: 1
- Digital outputs: 6

**Suggested cards:** 7i96S + 7i73 with 4×8 matrix for operator station

## Mesa Cards Referenced

| Card | Type | Primary Use |
|------|------|-------------|
| 7i96S | Ethernet FPGA | Simple stepper, 5 step/dir |
| 7i97T | Ethernet FPGA | Analog servo, 6 ±10V axes |
| 7i92TH | Ethernet FPGA (no onboard IO) | Base for daughter card systems |
| 7i77 | DB25 daughter card | Analog drives, 6 ±10V axes, 32 in, 16 out |
| 7i76EU | Ethernet FPGA | All-in-one with onboard IO |
| 7i80DB | FPGA (no onboard IO) | Base for daughter card systems |
| 7i80HDT | FPGA | 3× 50-pin connectors |
| 7i44 | 50-pin daughter | Sserial gateway, 8 connections |
| 7iA0 | Sserial daughter | 48 in, 24 out per card |
| 7i73 | Sserial daughter | Operator panel (buttons, MPG) |
| 7C80, 7C81 | SPI FPGA | Raspberry Pi direct (rpi5 not supported as of 2/2024) |
| THCAD series | Specialty | Plasma arc sensing |

## Comment from jmelson

Pico Systems is an alternative to Mesa — parallel port connected motion boards, used with LinuxCNC since the beginning. Pico maintains a "Pico Systems FAQ" in Driver Boards section. Pico sells PCIe parallel port cards for machines without built-in parallel ports.
