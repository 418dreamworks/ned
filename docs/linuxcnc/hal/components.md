<!-- Mirror of https://linuxcnc.org/docs/html/hal/components.html -->
<!-- LinuxCNC HAL Manual. Downloaded 2026-06-18. Source of truth is the URL above. -->

# HAL Component List



Table of Contents

**JavaScript must be enabled in your browser to display the table of contents.**





## 1. Components



Most of the commands in the following list have their own dedicated man pages. Some will have expanded descriptions, some will have limited descriptions. From this list you know what components exist, and you can use `man` *name* on your UNIX command line to get additional information. To view the information in the man page, in a terminal window type:





```
man axis
```


The one or other setup of a UNIX system may require to explicitly specify the section of the man page. If you do not find the man page or the name of the man page is already taken by another UNIX tool with the LinuxCNC man page residing in another section, then try to explicitly specify the section, as in `man _sectionno_ axis`, with *sectionno* = 1 for non-realtime and 9 for realtime components.


|

Note  |  See also the *Man Pages* section of the docs main page or the directory listing. To search in the man pages, use the UNIX tool `apropos`. |



### 1.1. User Interfaces (non-realtime)



#### 1.1.1. Machine Control


|

**axis** |

AXIS LinuxCNC (The Enhanced Machine Controller) GUI |

 |

 |
|

**axis-remote** |

AXIS Remote Interface |

 |

 |
|

**gmoccapy** |

Touchy LinuxCNC Graphical User Interface |

 |

 |
|

**gscreen** |

Touchy LinuxCNC Graphical User Interface |

 |

 |
|

**halui** |

Observe HAL pins and command LinuxCNC through NML |

 |

 |
|

**mdro** |

manual only Digital Read Out (DRO) |

 |

 |
|

**ngcgui** |

Framework for conversational G-code generation on the controller |

 |

 |
|

**panelui** |

Short description |

 |

 |
|

**pyngcgui** |

Python implementation of NGCGUI |

 |

 |
|

**touchy** |

AXIS - TOUCHY LinuxCNC Graphical User Interface |

 |

 |



#### 1.1.2. Virtual Control Panels (VCP)


|

**gladevcp** |

Virtual Control Panel for LinuxCNC based on Glade, Gtk and HAL widgets |

 |

 |
|

**gladevcp_demo** |

GladeVCP - used by sample configs to deonstrate Glade Virtual_demo |

 |

 |
|

**gremlin_view** |

G-code graphical preview |

 |

 |
|

**moveoff_gui** |

GUI for the moveoff component |

 |

 |
|

**pyui** |

Utility for panelui |

 |

 |
|

**pyvcp** |

Virtual Control Panel for LinuxCNC |

 |

 |
|

**pyvcp_demo** |

Python Virtual Control Panel demonstration component |

 |

 |
|

**qtvcp** |

Qt based virtual control panel |

 |

 |



#### 1.1.3. Vismach Virtual Machines


|

**5axisgui** |

Vismach Virtual Machine GUI |

 |

 |
|

**hbmgui** |

Vismach Virtual Machine GUI |

 |

 |
|

**hexagui** |

Vismach Virtual Machine GUI |

 |

 |
|

**lineardelta** |

Vismach Virtual Machine GUI |

 |

 |
|

**maho600gui** |

hexagui - Vismach Virtual Machine GUI |

 |

 |
|

**max5gui** |

hexagui - Vismach Virtual Machine GUI |

 |

 |
|

**puma560gui** |

puma560agui - Vismach Virtual Machine GUI |

 |

 |
|

**pumagui** |

Vismach Virtual Machine GUI |

 |

 |
|

**rotarydelta** |

Vismach Virtual Machine GUI |

 |

 |
|

**scaragui** |

Vismach Virtual Machine GUI |

 |

 |
|

**xyzac-trt-gui** |

Vismach Virtual Machine GUI |

 |

 |
|

**xyzbc-trt-gui** |

Vismach Virtual Machine GUI |

 |

 |



### 1.2. Motion (non-realtime)


|

**io** |

iocontrol - interacts with HAL or G-code in non-realtime |

 |

 |
|

**iocontrol** |

Interacts with HAL or G-code in non-realtime |

 |

 |
|

**iov2** |

Interacts with HAL or G-code in non-realtime |

 |

 |
|

**mdi** |

Send G-code commands from the terminal to the running LinuxCNC instance |

 |

 |
|

**milltask** |

Non-realtime task controller for LinuxCNC |

 |

 |



### 1.3. Hardware Drivers



#### 1.3.1. VFD & Communication Interfaces (non-realtime)


|

**elbpcom** |

Communicate with Mesa ethernet cards |

 |

 |
|

**gs2_vfd** |

HAL non-realtime component for Automation Direct GS2 VFDs |

 |

 |
|

**hy_gt_vfd** |

HAL non-realtime component for Huanyang GT-series VFDs |

 |

 |
|

**hy_vfd** |

HAL non-realtime component for Huanyang VFDs |

 |

 |
|

**mb2hal** |

MB2HAL is a generic non-realtime HAL component to communicate with one or more Modbus devices. Modbus RTU and Modbus TCP are supported. |

 |

 |
|

**mitsub_vfd** |

HAL non-realtime component for Mitsubishi A500 F500 E500 A500 D700 E700 F700-series VFDs (others may work) |

 |

 |
|

**monitor-xhc-hb04** |

Monitors the XHC-HB04 pendant and warns of disconnection |

 |

 |
|

**pi500_vfd** |

Powtran PI500 modbus driver |

 |

 |
|

**pmx485** |

Modbus communications with a Powermax Plasma Cutter |

 |

 |
|

**pmx485-test** |

Modbus communications testing with a Powermax Plasma Cutter |

 |

 |
|

**shuttle** |

control HAL pins with the ShuttleXpress, ShuttlePRO, and ShuttlePRO2 device made by Contour Design |

 |

 |
|

**svd-ps_vfd** |

HAL non-realtime component for SVD-P(S) VFDs |

 |

 |
|

**vfdb_vfd** |

HAL non-realtime component for Delta VFD-B Variable Frequency Drives |

 |

 |
|

**vfs11_vfd** |

HAL non-realtime component for Toshiba-Schneider VF-S11 Variable Frequency Drives |

 |

 |
|

**wj200_vfd** |

Hitachi wj200 modbus driver |

 |

 |
|

**xhc-hb04** |

Non-realtime HAL component for the xhc-hb04 pendant |

 |

 |
|

**xhc-hb04-accels** |

Obsolete script for jogging wheel |

 |

 |
|

**xhc-whb04b-6** |

Non-realtime jog dial HAL component for the wireless XHC WHB04B-6 USB device |

 |

 |



### 1.4. Mesa and other I/O Cards (Realtime)


|

**hal_ppmc** |

Pico Systems driver for analog servo, PWM and Stepper controller |

 |

 |
|

**hal_bb_gpio** |

Driver for beaglebone GPIO pins |

 |

 |
|

**hal_parport** |

Realtime HAL component to communicate with one or more PC parallel ports |

 |

 |
|

**hm2_7i43** |

Mesa Electronics driver for the 7I43 EPP Anything IO board with HostMot2. (See the man page for more information) |

 |

 |
|

**hm2_7i90** |

LinuxCNC HAL driver for the Mesa Electronics 7I90 EPP Anything IO board with HostMot2 firmware |

 |

 |
|

**hm2_eth** |

LinuxCNC HAL driver for the Mesa Electronics Ethernet Anything IO boards, with HostMot2 firmware |

 |

 |
|

**hm2_pci** |

Mesa Electronics driver for the 5I20, 5I22, 5I23, 4I65, and 4I68 Anything I/O boards, with HostMot2 firmware. (See the man page for more information) |

 |

 |
|

**hm2_rpspi** |

LinuxCNC HAL driver for the Mesa Electronics SPI Anything IO boards, with HostMot2 firmware |

 |

 |
|

**hm2_spi** |

LinuxCNC HAL driver for the Mesa Electronics SPI Anything IO boards, with HostMot2 firmware |

 |

 |
|

**hostmot2** |

Mesa Electronics driver for the HostMot2 firmware. |

 |

 |
|

**max31855** |

Support for the MAX31855 Thermocouple-to-Digital converter using bitbanged SPI |

 |

 |
|

**mesa_7i65** |

Mesa Electronics driver for the 7I65 eight-axis servo card. (See the man page for more information) |

 |

 |
|

**mesa_pktgyro_test** |

PktUART simple test with Microstrain 3DM-GX3-15 gyro |

 |

 |
|

**opto_ac5** |

Realtime driver for opto22 PCI-AC5 cards |

 |

 |
|

**pluto_servo** |

Pluto-P driver and firmware for the parallel port FPGA, for servos |

 |

 |
|

**pluto_step** |

Pluto-P driver for the parallel port FPGA, for steppers |

 |

 |
|

**serport** |

Hardware driver for the digital I/O bits of the 8250 and 16550 serial port |

 |

 |
|

**sserial** |

hostmot2 - Smart Serial LinuxCNC HAL driver for the Mesa Electronics HostMot2 Smart-Serial remote cards |

 |

 |
|

**thc** |

Torch Height Control using a Mesa THC card or any analog to velocity input |

 |

 |



### 1.5. Utilities (non-realtime)


|

**hal-histogram** |

Plots the value of a HAL pin as a histogram |

 |

 |
|

**halcompile** |

Build, compile and install LinuxCNC HAL components |

 |

 |
|

**halmeter** |

Observe HAL pins, signals, and parameters |

 |

 |
|

**halcmd** |

Manipulate the LinuxCNC HAL from the command line |

 |

 |
|

**halcmd_twopass** |

Short description |

 |

 |
|

**halreport** |

Creates a report on the status of the HAL |

 |

 |
|

**halrmt** |

Short description |

 |

 |
|

**halrun** |

Manipulate the LinuxCNC HAL from the command line |

 |

 |
|

**halsampler** |

Sample data from HAL in realtime |

 |

 |
|

**halscope** |

Software oscilloscope for viewing real time waveforms of HAL pins and signals |

 |

 |
|

**halshow** |

Show HAL parameters, pins and signals |

 |

 |
|

**halstreamer** |

Stream file data into HAL in real time |

 |

 |
|

**haltcl** |

Manipulates the LinuxCNC HAL from the command line using Tcl |

 |

 |
|

**image-to-gcode** |

Converts bitmap images to G-code |

 |

 |
|

**latency-histogram** |

Plots histogram of machine latency |

 |

 |
|

**latency-plot** |

Another way to view latency numbers |

 |

 |
|

**latency-test** |

Tests the realtime system latency |

 |

 |
|

**pncconf** |

Configuration wizard for Mesa cards |

 |

 |
|

**setsserial** |

Utility for setting Smart Serial NVRAM parameters. NOTE: This rather clunky utility is no longer needed except for flashing new smart-serial remote firmware. Smart-serial remote parameters can now be set in the HAL file in the normal way. |

 |

 |
|

**sim_pin** |

GUI for displaying and setting one or more HAL inputs |

 |

 |
|

**stepconf** |

Configuration wizard for parallel-port based machines |

 |

 |



### 1.6. Signal processing (Realtime)



#### 1.6.1. Logic and Bitwise


|

**and2** |

Two-input AND gate. For out to be true both inputs must be true. (and2) |

 |

 |
|

**bitwise** |

Computes various bitwise operations on the two input values |

 |

 |
|

**dbounce** |

Filter noisy digital inputs Details |

 |

 |
|

**debounce** |

Filter noisy digital inputs Details Description |

 |

 |
|

**demux** |

Select one of several output pins by integer and/or or individual bits |

 |

 |
|

**edge** |

Edge detector |

 |

 |
|

**estop_latch** |

E-stop latch |

 |

 |
|

**flipflop** |

D-type flip-flop |

 |

 |
|

**logic** |

General logic function component |

 |

 |
|

**lut5** |

5-input logic function based on a look-up table Description |

 |

 |
|

**match8** |

8-bit binary match detector |

 |

 |
|

**multiclick** |

Single-, double-, triple-, and quadruple-click detector |

 |

 |
|

**multiswitch** |

Toggles between a specified number of output bits |

 |

 |
|

**not** |

Inverter |

 |

 |
|

**oneshot** |

One-shot pulse generator |

 |

 |
|

**or2** |

Two-input OR gate |

 |

 |
|

**select8** |

8-bit binary match detector. |

 |

 |
|

**tof** |

IEC TOF timer - delay falling edge on a signal |

 |

 |
|

**toggle** |

Push-on, push-off from momentary pushbuttons |

 |

 |
|

**toggle2nist** |

Toggle button to nist logic |

 |

 |
|

**ton** |

IEC TON timer - delay rising edge on a signal |

 |

 |
|

**timedelay** |

Equivalent of a time-delay relay. |

 |

 |
|

**tp** |

IEC TP timer - generate a high pulse of defined duration on rising edge |

 |

 |
|

**tristate_bit** |

Places signal on an I/O pin only when enabled, similar to a tristate buffer in electronics |

 |

 |
|

**tristate_float** |

Places signal on an I/O pin only when enabled, similar to a tristate buffer in electronics |

 |

 |
|

**xor2** |

Two-input XOR (exclusive OR) gate |

 |

 |



#### 1.6.2. Arithmetic and float


|

**abs_s32** |

Computes the absolute value and sign of the input signal |

 |

 |
|

**abs** |

Computes the absolute value and sign of the input signal |

 |

 |
|

**biquad** |

Biquad IIR filter |

 |

 |
|

**blend** |

Perform linear interpolation between two values |

 |

 |
|

**comp** |

Two input comparator with hysteresis |

 |

 |
|

**constant** |

Uses parameter to set the value of a pin |

 |

 |
|

**counter** |

Counts input pulses (deprecated). Use the encoder component. |

 |

 |
|

**ddt** |

Computes the derivative of the input function. |

 |

 |
|

**deadzone** |

Returns the center if within the threshold. |

 |

 |
|

**div2** |

Quotient of two floating point inputs. |

 |

 |
|

**hypot** |

Three-input hypotenuse (Euclidean distance) calculator. |

 |

 |
|

**ilowpass** |

Low-pass filter with integer inputs and outputs |

 |

 |
|

**integ** |

Integrator |

 |

 |
|

**invert** |

Computes the inverse of the input signal. |

 |

 |
|

**filter_kalman** |

Unidimensional Kalman filter, also known as linear quadratic estimation (LQE) |

 |

 |
|

**knob2float** |

Converts counts (probably from an encoder) to a float value. |

 |

 |
|

**lowpass** |

Low-pass filter |

 |

 |
|

**limit1** |

Limits the output signal to fall between min and max.
[When the input is a position, this means that the *position* is limited.]
 |

 |

 |
|

**limit2** |

Limits the output signal to fall between min and max.  Limit its slew rate to less than maxv per second.
[When the input is a position, this means that *position* and *velocity* are limited.]
 |

 |

 |
|

**limit3** |

Limit the output signal to fall between min and max. Limit its slew rate to less than maxv per second. Limit its second derivative to less than MaxA per second squared
[When the input is a position, this means that the *position*, *velocity*, and *acceleration* are limited.]
. |

 |

 |
|

**lincurve** |

One-dimensional lookup table |

 |

 |
|

**maj3** |

Compute the majority of 3 inputs |

 |

 |
|

**minmax** |

Tracks the minimum and maximum values of the input to the outputs. |

 |

 |
|

**mult2** |

Product of two inputs. |

 |

 |
|

**mux16** |

Select from one of 16 input values (multiplexer). |

 |

 |
|

**mux2** |

Select from one of two input values (multiplexer). |

 |

 |
|

**mux4** |

Select from one of four input values (multiplexer). |

 |

 |
|

**mux8** |

Select from one of eight input values (multiplexer). |

 |

 |
|

**mux_generic** |

Select one from several input values (multiplexer). |

 |

 |
|

**near** |

Determine whether two values are roughly equal. |

 |

 |
|

**offset** |

Adds an offset to an input, and subtracts it from the feedback value. |

 |

 |
|

**sample_hold** |

Sample and Hold. |

 |

 |
|

**scale** |

Applies a scale and offset to its input. |

 |

 |
|

**sum2** |

Sum of two inputs (each with a gain) and an offset. |

 |

 |
|

**timedelta** |

Component that measures thread scheduling timing behavior. |

 |

 |
|

**updown** |

Counts up or down, with optional limits and wraparound behavior. |

 |

 |
|

**wcomp** |

Window comparator. |

 |

 |
|

**weighted_sum** |

Convert a group of bits to an integer. |

 |

 |
|

**xhc_hb04_util** |

xhc-hb04 convenience utility |

 |

 |



#### 1.6.3. Type conversion


|

**bin2gray** |

Converts a number to the gray-code representation |

 |

 |
|

**bitslice** |

Converts an unsigned-32 input into individual bits |

 |

 |
|

**conv_bit_float** |

Converts from bit to float |

 |

 |
|

**conv_bit_s32** |

Converts from bit to s32 |

 |

 |
|

**conv_bit_u32** |

Converts from bit to u32 |

 |

 |
|

**conv_float_s32** |

Converts from float to s32 |

 |

 |
|

**conv_float_u32** |

Converts from float to u32 |

 |

 |
|

**conv_s32_bit** |

Converts from s32 to bit |

 |

 |
|

**conv_s32_float** |

Converts from s32 to float |

 |

 |
|

**conv_s32_u32** |

Converts from s32 to u32 |

 |

 |
|

**conv_u32_bit** |

Converts from u32 to bit |

 |

 |
|

**conv_u32_float** |

Converts from u32 to float |

 |

 |
|

**conv_u32_s32** |

Converts from u32 to s32 |

 |

 |
|

**gray2bin** |

Converts gray-code input to binary |

 |

 |



### 1.7. Kinematics (Realtime)


|

**corexy_by_hal** |

CoreXY kinematics |

 |

 |
|

**differential** |

Kinematics for a differential transmission |

 |

 |
|

**gantry** |

LinuxCNC HAL component for driving multiple joints from a single axis |

 |

 |
|

**gantrykins** |

Kinematics module that maps one axis to multiple joints. |

 |

 |
|

**genhexkins** |

Gives six degrees of freedom in position and orientation (XYZABC). The location of the motors is defined at compile time. |

 |

 |
|

**genserkins** |

Kinematics that can model a general serial-link manipulator with up to 6 angular joints. |

 |

 |
|

**gentrivkins** |

See trivkins |

 |

 |
|

**kins** |

Kinematics definitions for LinuxCNC. |

 |

 |
|

**lineardeltakins** |

Kinematics for a linear delta robot |

 |

 |
|

**maxkins** |

Kinematics for a tabletop 5 axis mill named *max* with tilting head (B axis) and horizontal rotary mounted to the table (C axis). Provides UVW motion in the rotated coordinate system. The source file, maxkins.c, may be a useful starting point for other 5-axis systems. |

 |

 |
|

**millturn** |

Switchable kinematics for a mill-turn machine |

 |

 |
|

**pentakins** |

 |

 |

 |
|

**pumakins** |

Kinematics for PUMA-style robots. |

 |

 |
|

**rosekins** |

Kinematics for a rose engine |

 |

 |
|

**rotatekins** |

The X and Y axes are rotated 45 degrees compared to the joints 0 and 1. |

 |

 |
|

**scarakins** |

Kinematics for SCARA-type robots. |

 |

 |
|

**tripodkins** |

The joints represent the distance of the controlled point from three predefined locations (the motors), giving three degrees of freedom in position (XYZ). |

 |

 |
|

**trivkins** |

1:1 correspondence between joints and axes. Most standard milling machines and lathes use the trivial kinematics module. |

 |

 |
|

**userkins** |

Template for user-built kinematics |

 |

 |



### 1.8. Motion control (Realtime)


|

**motion** |

Accepts NML motion commands, interacts with HAL in realtime |

 |

 |



### 1.9. Motor control (Realtime)


|

**at_pid** |

Proportional/integral/derivative controller with auto tuning. |

 |

 |
|

**bldc** |

BLDC and AC-servo control component |

 |

 |
|

**clarke2** |

Two input version of Clarke transform |

 |

 |
|

**clarke3** |

Clarke (3 phase to cartesian) transform |

 |

 |
|

**clarkeinv** |

Inverse Clarke transform |

 |

 |
|

**encoder** |

Software counting of quadrature encoder signals, see Description. |

 |

 |
|

**pid** |

Proportional/integral/derivative controller, Description. |

 |

 |
|

**pwmgen** |

Software PWM/PDM generation, see Description. |

 |

 |
|

**stepgen** |

Software step pulse generation, see Description. |

 |

 |



### 1.10. Other (Realtime)


|

**comp** |

Build, compile and install LinuxCNC HAL components. |

 |

 |
|

**classicladder** |

Realtime software PLC based on ladder logic. See ClassicLadder chapter for more information. |

 |

 |
|

**threads** |

Creates hard realtime HAL threads. |

 |

 |
|

**charge_pump** |

Creates a square-wave for the *charge pump* input of some controller boards. The *Charge Pump* should be added to the base thread function. When enabled, the output is on for one period and off for one period. To calculate the frequency [Hz] of the output: 1/(period time in seconds x 2). For example, if you have a base period of 100,000 ns that is 0.0001 seconds and the formula would be 1/(0.0001 x 2) = 5,000 Hz or 5 kHz. |

 |

 |
|

**encoder_ratio** |

Electronic gear to synchronize two axes. |

 |

 |
|

**feedcomp** |

Multiply the input by the ratio of current velocity to the feed rate. |

 |

 |
|

**gladevcp (Realtime)** |

displays Virtual control Panels built with GTK / GLADE |

 |

 |
|

**gearchange** |

Select from one of two speed ranges. |

 |

 |
|

**joyhandle** |

Sets nonlinear joypad movements, deadbands and scales. |

 |

 |
|

**sampler** |

Sample data from HAL in real time. |

 |

 |
|

**siggen** |

Signal generator, see Description. |

 |

 |
|

**sim_encoder** |

Simulated quadrature encoder, see Description. |

 |

 |
|

**sphereprobe** |

Probe a pretend hemisphere. |

 |

 |
|

**steptest** |

Used by StepConf to allow testing of acceleration and velocity values for an axis. |

 |

 |
|

**streamer** |

Stream file data into HAL in real time. |

 |

 |
|

**supply** |

Set output pins with values from parameters (deprecated). |

 |

 |
|

**threadtest** |

Component for testing thread behavior. |

 |

 |
|

**time** |

Accumulated run-time timer counts HH:MM:SS of *active* input. |

 |

 |
|

**watchdog** |

Monitor one to thirty-two inputs for a *heartbeat*. |

 |

 |



### 1.11. Not categorized (auto generated from man pages)


|

**anglejog** |

Jog two axes (or joints) at an angle |

 |

 |
|

**axis** |

 |

 |

 |
|

**axistest** |

Used to allow testing of an axis. Used IN PnCconf. |

 |

 |
|

**carousel** |

Orient a toolchanger carousel using various encoding schemes |

 |

 |
|

**debuglevel** |

sets the debug level for the non-realtime part of LinuxCNC |

 |

 |
|

**emccalib** |

Adjust ini tuning variables on the fly with save option |

 |

 |
|

**enum** |

enumerate integer values into bits |

 |

 |
|

**eoffset_per_angle** |

Compute External Offset Per Angle |

 |

 |
|

**hal_input** |

control HAL pins with any Linux input device, including USB HID devices |

 |

 |
|

**hal_manualtoolchange** |

HAL non-realtime component to enable manual tool changes. |

 |

 |
|

**histobins** |

histogram bins utility for scripts/hal-histogram |

 |

 |
|

**hm2_modbus** |

A hostmot2 driver that implements the Modbus protocol using the PktUART ports&. |

 |

 |
|

**hm2_spix** |

LinuxCNC HAL driver for the Mesa Electronics Anything IO boards with SPI enabled HostMot2 firmware&. |

 |

 |
|

**homecomp** |

homing module template |

 |

 |
|

**inivar** |

Query an INI file |

 |

 |
|

**latencybins** |

comp utility for scripts/latency-histogram |

 |

 |
|

**lcd** |

Stream HAL data to an LCD screen |

 |

 |
|

**limit_axis** |

Dynamic range based axis limits |

 |

 |
|

**linuxcnc** |

LinuxCNC (The Enhanced Machine Controller) |

 |

 |
|

**linuxcnc_info** |

collects information about the LinuxCNC version and the host |

 |

 |
|

**linuxcnc_module_helper** |

controls root access for system hardware |

 |

 |
|

**linuxcnc_var** |

retrieves LinuxCNC variables |

 |

 |
|

**linuxcnclcd** |

LinuxCNC Graphical User Interface for LCD character display |

 |

 |
|

**linuxcncmkdesktop** |

create a desktop icon for LinuxCNC |

 |

 |
|

**linuxcncrsh** |

text-mode interface for commanding LinuxCNC over the network |

 |

 |
|

**linuxcncsvr** |

Allows network access to LinuxCNC internals via NML |

 |

 |
|

**linuxcnctop** |

live LinuxCNC status description |

 |

 |
|

**matrix_kb** |

Convert integers to HAL pins. Optionally scan a matrix of IO ports to create those integers. |

 |

 |
|

**melfagui** |

Vismach Virtual Machine GUI |

 |

 |
|

**mesa_uart** |

An example component demonstrating how to access the Hostmot2 UART |

 |

 |
|

**mesambccc** |

Utility for compiling hm2_modbus command control description files |

 |

 |
|

**message** |

Display a message |

 |

 |
|

**millturn** |

millturngui - Vismach Virtual Machine GUI |

 |

 |
|

**modcompile** |

Utility for compiling Modbus drivers |

 |

 |
|

**motion-logger** |

log motion commands sent from LinuxCNC’s Task module |

 |

 |
|

**moveoff** |

Component for HAL-only offsets |

 |

 |
|

**mqtt-publisher** |

send HAL pin data to MQTT broker periodically |

 |

 |
|

**ohmic** |

LinuxCNC HAL component that uses a Mesa THCAD for ohmic sensing |

 |

 |
|

**orient** |

Provide a PID command input for orientation mode based on current spindle position, target angle and orient mode |

 |

 |
|

**plasmac** |

A plasma cutter controller |

 |

 |
|

**qtplasmac-cfg2prefs** |

Convert plasma parameters. |

 |

 |
|

**qtplasmac-materials** |

Create a plasma materials file. |

 |

 |
|

**qtplasmac-plasmac2qt** |

Migrate a PlasmaC configuration. |

 |

 |
|

**qtplasmac-setup** |

Switch a QtPlasmaC installation type. |

 |

 |
|

**qtplasmac_gcode** |

A python script that is part of Plasmac, a Plasma cutting system. |

 |

 |
|

**rs274** |

standalone G-code interpreter |

 |

 |
|

**rtapi_app** |

creates a simulated real time environment |

 |

 |
|

**scaled_s32_sums** |

Sum of four inputs (each with a scale) |

 |

 |
|

**schedrmt** |

telnet based scheduler for LinuxCNC |

 |

 |
|

**scorbot-er-3** |

to link the Intellitek Scorbot educational robot to LinuxCNC |

 |

 |
|

**sendkeys** |

send input events based on pins or scancodes from HAL |

 |

 |
|

**setup_designer** |

A script to configure the system for use of QTdesigner |

 |

 |
|

**sim-torch** |

A simulated plasma torch |

 |

 |
|

**sim_axis_hardware** |

A component to simulate home and limit switches |

 |

 |
|

**sim_home_switch** |

Home switch simulator |

 |

 |
|

**sim_matrix_kb** |

convert HAL pin inputs to keycodes |

 |

 |
|

**sim_parport** |

A component to simulate the pins of the hal_parport component |

 |

 |
|

**sim_spindle** |

Simulated spindle with index pulse |

 |

 |
|

**simple_tp** |

This component is a single axis simple trajectory planner, same as used for jogging in LinuxCNC. |

 |

 |
|

**simulate_probe** |

simulate a probe input |

 |

 |
|

**spindle** |

Control a spindle with different acceleration and deceleration and optional gear change scaling |

 |

 |
|

**spindle_monitor** |

spindle at-speed and underspeed detection |

 |

 |
|

**teach-in** |

jog the machine to a position, and record the state |

 |

 |
|

**thcud** |

Torch Height Control Up/Down Input |

 |

 |
|

**thermistor** |

compute temperature indicated by a thermistor |

 |

 |
|

**tool_mmap_read** |

A component of the tool database system (an alternative to the classic tooltable) |

 |

 |
|

**tool_watch** |

A component of the tool database system (an alternative to the classic tooltable) |

 |

 |
|

**tooledit** |

tool table editor |

 |

 |
|

**tpcomp** |

Trajectory Planning (tp) module skeleton |

 |

 |
|

**update_ini** |

converts 2.7 format INI files to 2.8 format |

 |

 |
|

**xyzab-tdr-gui** |

Vismach Virtual Machine GUI |

 |

 |
|

**xyzab_tdr_kins** |

Switchable kinematics for 5 axis machine with rotary table A and B |

 |

 |



### 1.12. Without man page or broken link (auto generated from component list)


|

**hal_ppmc** |

 |

 |

 |
|

**pluto_servo** |

 |

 |

 |
|

**pluto_step** |

 |

 |

 |



## 2. HAL API calls







```
hal_add_funct_to_thread.3hal
hal_bit_t.3hal
hal_create_thread.3hal
hal_del_funct_from_thread.3hal
hal_exit.3hal
hal_export_funct.3hal
hal_float_t.3hal
hal_get_lock.3hal
hal_init.3hal
hal_link.3hal
hal_malloc.3hal
hal_param_bit_new.3hal
hal_param_bit_newf.3hal
hal_param_float_new.3hal
hal_param_float_newf.3hal
hal_param_new.3hal
hal_param_s32_new.3hal
hal_param_s32_newf.3hal
hal_param_u32_new.3hal
hal_param_u32_newf.3hal
hal_parport.3hal
hal_pin_bit_new.3hal
hal_pin_bit_newf.3hal
hal_pin_float_new.3hal
hal_pin_float_newf.3hal
hal_pin_new.3hal
hal_pin_s32_new.3hal
hal_pin_s32_newf.3hal
hal_pin_u32_new.3hal
hal_pin_u32_newf.3hal
hal_ready.3hal
hal_s32_t.3hal
hal_set_constructor.3hal
hal_set_lock.3hal
hal_signal_delete.3hal
hal_signal_new.3hal
hal_start_threads.3hal
hal_type_t.3hal
hal_u32_t.3hal
hal_unlink.3hal
intro.3hal
undocumented.3hal
```




## 3. RTAPI calls







```
EXPORT_FUNCTION.3rtapi
MODULE_AUTHOR.3rtapi
MODULE_DESCRIPTION.3rtapi
MODULE_LICENSE.3rtapi
RTAPI_MP_ARRAY_INT.3rtapi
RTAPI_MP_ARRAY_LONG.3rtapi
RTAPI_MP_ARRAY_STRING.3rtapi
RTAPI_MP_INT.3rtapi
RTAPI_MP_LONG.3rtapi
RTAPI_MP_STRING.3rtapi
intro.3rtapi
rtapi_app_exit.3rtapi
rtapi_app_main.3rtapi
rtapi_clock_set_period.3rtapi
rtapi_delay.3rtapi
rtapi_delay_max.3rtapi
rtapi_exit.3rtapi
rtapi_get_clocks.3rtapi
rtapi_get_msg_level.3rtapi
rtapi_get_time.3rtapi
rtapi_inb.3rtapi
rtapi_init.3rtapi
rtapi_module_param.3rtapi
RTAPI_MP_ARRAY_INT.3rtapi
RTAPI_MP_ARRAY_LONG.3rtapi
RTAPI_MP_ARRAY_STRING.3rtapi
RTAPI_MP_INT.3rtapi
RTAPI_MP_LONG.3rtapi
RTAPI_MP_STRING.3rtapi
rtapi_mutex.3rtapi
rtapi_outb.3rtapi
rtapi_print.3rtap
rtapi_prio.3rtapi
rtapi_prio_highest.3rtapi
rtapi_prio_lowest.3rtapi
rtapi_prio_next_higher.3rtapi
rtapi_prio_next_lower.3rtapi
rtapi_region.3rtapi
rtapi_release_region.3rtapi
rtapi_request_region.3rtapi
rtapi_set_msg_level.3rtapi
rtapi_shmem.3rtapi
rtapi_shmem_delete.3rtapi
rtapi_shmem_getptr.3rtapi
rtapi_shmem_new.3rtapi
rtapi_snprintf.3rtapi
rtapi_task_delete.3rtpi
rtapi_task_new.3rtapi
rtapi_task_pause.3rtapi
rtapi_task_resume.3rtapi
rtapi_task_start.3rtapi
rtapi_task_wait.3rtapi
```






 Last updated 2025-12-15 07:42:37 MST
