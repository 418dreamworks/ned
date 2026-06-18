# The Ultimate Mesa Card Guide for LinuxCNC

Source: https://albersx.com/en/articles/mesa-card-guide-linuxcnc/

## What Are Mesa Cards?

Mesa cards function as the bridge connecting a PC running LinuxCNC control software to CNC machine electronics like motor drivers, encoders, buttons, and lights. Manufactured by Mesa Electronics (California-based), these boards use Ethernet or PCI connections to communicate with computers.

A defining feature is the integrated FPGA chip ("Field Programmable Gate Array"). This enables high-speed calculations—such as generating stepper motor signals—that would overtax standard control PCs. This real-time capability creates industrial-grade machine reliability, though it contributes to the cards' higher cost.

When combining multiple cards, one "main card" with an FPGA communicates directly with the PC. Additional "daughter cards" connect to it without requiring their own FPGA chips.

## How to Choose and Combine Mesa Cards

### Step 1: Identify Required Inputs/Outputs

Document what your machine needs: axis control signals (step/direction or analog ±10V), encoder inputs, relay outputs, button inputs, handwheel connections, and spindle controls.

### Step 2: Select PC Connection Type

**Ethernet:** Most popular option. Requires a dedicated Ethernet port on the control computer (no network switches allowed). You'll need an alternative for internet connectivity.

**PCI Port:** Less common now as modern PCs lack this slot. Offers competitive data transfer rates when available.

**SPI:** Ideal for Raspberry Pi systems using GPIO pins.

### Step 3: Choose Daughter Card Connections

**50-Pin Interface:** Direct FPGA pin connection offering high-speed communication. Supports multiple 50-pin daughter cards.

**DB25 Interface:** Similar to 50-pin but with reduced bandwidth (25 pins vs. 50). Some 26-pin variants are DB25-compatible.

**SmartSerial (SSerial):** Mesa's RS-422-based protocol using Ethernet cables without actual Ethernet switching capability. Slower than 50-pin/DB25 but excellent for general I/O (relays, buttons). Multiple SSerial connections require special hub cards like the 7i74.

## Example Configuration: 3-Axis CNC Mill

**Requirements:**
- Three axes with step/direction signals
- 0-10V spindle control
- Position feedback via glass scales (encoders)
- Four relays (lubrication, coolant, lighting, tool clamp)
- Control panel with buttons and handwheel

**Solution:**
- **Main Card (7I96S):** Ethernet connection, 5-axis step/dir outputs, analog spindle output, 11 digital inputs, 6 digital outputs
- **Daughter Card 1 (7I85S):** DB25-connected encoder interface
- **Daughter Card 2 (7I73):** SSerial-connected remote panel with button and handwheel inputs

## European Purchasing

Since Mesa Electronics operates exclusively from the USA, European buyers should use local distributors (Welectron, EUSurplus) to avoid import expenses. Note that inventory is often limited.
