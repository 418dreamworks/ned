<!-- Mirror of https://linuxcnc.org/docs/html/hal/canonical-devices.html -->
<!-- LinuxCNC HAL Manual. Downloaded 2026-06-18. Source of truth is the URL above. -->

# Canonical Device Interfaces



Table of Contents

**JavaScript must be enabled in your browser to display the table of contents.**





## 1. Introduction



The following sections show the pins, parameters, and functions that are supplied by "canonical devices". All HAL device drivers should supply the same pins and parameters, and implement the same behavior.

Note that only the `_<io-type>_` and `_<specific-name>_` fields are defined for a canonical device. The `_<device-name>`, `_<device-num>_`, and `_<chan-num>_` fields are set based on the characteristics of the real device.



## 2. Digital Input



The canonical digital input (I/O type field: `digin`) is quite simple.



### 2.1. Pins

  (bit) **in**

 State of the hardware input.    (bit) **in-not**

 Inverted state of the input.



### 2.2. Parameters

None



### 2.3. Functions

  (funct) **read**

 Read hardware and set `in` and `in-not` HAL pins.



## 3. Digital Output



The canonical digital output (I/O type field: `digout`) is also very simple.



### 3.1. Pins

  (bit) **out**

 Value to be written (possibly inverted) to the hardware output.



### 3.2. Parameters

  (bit) **invert**

 If TRUE, **out** is inverted before writing to the hardware.



### 3.3. Functions

  (funct) **write**

 Read **out** and **invert**, and set hardware output accordingly.



## 4. Analog Input



The canonical analog input (I/O type: `adcin`). This is expected to be used for analog to digital converters, which convert e.g. voltage to a continuous range of values.



### 4.1. Pins

  (float) **value**

 The hardware reading, scaled according to the **scale** and **offset** parameters.
 **value** = ((input reading, in hardware-dependent units) * **scale**) - **offset**



### 4.2. Parameters

  (float) **scale**

 The input voltage (or current) will be multiplied by **scale** before being output to **value**.    (float) **offset**

 This will be subtracted from the hardware input voltage (or current) after the scale multiplier has been applied.    (float) **bit_weight**

 The value of one least significant bit (LSB). This is effectively the granularity of the input reading.    (float) **hw_offset**

 The value present on the input when 0 Volts is applied to the input pin(s).



### 4.3. Functions

  (funct) **read**

 Read the values of this analog input channel.  This may be used for individual channel reads, or it may cause all channels to be read.



## 5. Analog Output



The canonical analog output (I/O Type: **adcout**). This is intended for any kind of hardware that can output a more-or-less continuous range of values. Examples are digital to analog converters or PWM generators.



### 5.1. Pins

  (float) **value**

 The value to be written. The actual value output to the hardware will depend on the scale and offset parameters.    (bit) **enable**

 If false, then output 0 to the hardware, regardless of the **value** pin.



### 5.2. Parameters

  (float) **offset**

 This will be added to the **value** before the hardware is updated.    (float) **scale**

 This should be set so that an input of 1 on the **value** pin will cause the analog output pin to read 1 volt.    (float) **high_limit** (optional)

 When calculating the value to output to the hardware, if **value** + **offset** is greater than **high_limit**, then **high_limit** will be used instead.    (float) **low_limit** (optional)

 When calculating the value to output to the hardware, if **value** + **offset** is less than **low_limit**, then **low_limit** will be used instead.    (float) **bit_weight** (optional)

 The value of one least significant bit (LSB), in volts (or mA, for current outputs).    (float) **hw_offset**  (optional)

 The actual voltage (or current) that will be output if 0 is written to the hardware.



### 5.3. Functions

  (funct) **write**

 This causes the calculated value to be output to the hardware. If enable is false, then the output will be 0, regardless of **value**, **scale**, and **offset**. The meaning of "0" is dependent on the hardware. For example, a bipolar 12-bit A/D may need to write 0x1FF (mid scale) to the D/A get 0 volts from the hardware pin. If enable is true, read scale, offset and value and output to the adc (**scale** * **value**) + **offset**. If enable is false, then output 0.





 Last updated 2025-12-15 07:42:37 MST
