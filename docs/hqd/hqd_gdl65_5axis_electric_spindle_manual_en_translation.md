# GDL65 Series Electric Spindle — Installation and Operation Manual

**Manufacturer:** HQD (Han Qi Spindle Motor) — Changzhou Han Qi Spindle Motor Co., Ltd.

Source: `GDL65系列五轴头电主轴安装使用说明书.pdf` (19 pages)

---

## 1. Spindle Overview

This is a water-cooled automatic tool-change electric spindle. Suitable for machining non-ferrous metals, light alloys, composites, plastics, wood, and similar physical-property materials. Compact mechanical design with very small rotational volume; can be mounted on a 5-axis-dedicated A/C double swing head for multi-axis simultaneous machining, with wide-angle rotation covering a large machining envelope — particularly suited to molds with complex contours and cavities. Two tool-holder interface options: **HSK F63 (DIN 69893)** and **ISO 30 (DIN 69871)**. Good connection rigidity, suitable for high-speed operation and long-tool-bar precision work. Equipped with tool-clamp / tool-unclamp / axis-stop detection sensors and an overheat-protection temperature switch to ensure safe and reliable operation.

### 1.1 HSK F63 Tool Holder Interface — Dimensional Drawing
### 1.2 ISO 30 Tool Holder Interface — Dimensional Drawing

Overall length 270 mm HSK / 295 mm ISO; 6 × M6 mounting holes on 130 × 130 pattern at 40° spacing; spindle nose Ø95 / Ø86 / Ø74.

---

## 2. Installation and Commissioning

### 2.1 Initial Inspection
Before installation, please confirm:
- The exterior and parts of the spindle were not damaged in transport.
- The connectors are not damaged.

### 2.2 Site Preparation
- Prepare all installation utilities (three-phase AC power, compressed air, etc.). Supply lines must have adequate capacity. Power connection must be done by a qualified electrician.
- ⚠ The customer is responsible for the entire power supply system up to the spindle plug. Equipotential protective bonding connectors must be used. The grounding system must comply with local installation codes and be inspected periodically by a qualified electrician.
- ⚠ This product **cannot be installed in environments with explosion risk**. The installation environment must be sufficiently well lit.

### 2.3 Operating Environment Requirements
- Temperature: **+5 to +40°C**
- Maximum relative humidity: **50%**
- Operating altitude: **0 to 1000 m**. If air is colder or machine is installed above 1000 m altitude, motor power may derate. **Maximum altitude: 3000 m.**

### 2.4 Mechanical Installation
- Mount the product on a supporting structure with sufficient rigidity to support machining. See drawings for spindle dimensions.
- Consider the following fixing requirements before securing the spindle.

### 2.4.1 Spindle Mounting
This spindle is generally mounted on an A/C swing head or at the end of an industrial robot for cutting work. Mounting baseplate **flatness must be within 0.02 mm**. Two side clamp plates compress the housing's mounting feet; can also use 8 × M6 screws with large washers. Cooling water, tool clamp/unclamp, dust-removal, and air-seal lines pass into the spindle housing through the mounting baseplate via sealing rings. Power and signal cables exit through the central through-hole.

⚠ The water/air outlet positions of the mounting baseplate must align with the spindle, or water/air leakage will occur.
⚠ Spindle mounting surface flatness **must be within 0.02 mm**.

**Baseplate Layout (from the drawing):**
- Dust-seal and taper-cleaning air: **4–4.5 bar**
- Tool-unclamp air: **10.5–11.5 bar**
- Cooling liquid in / out: **max 6.0 bar**

### 2.4.2 Tool Change System
The tool magazine must satisfy concentricity requirements between tool holder and spindle centerline.

| Item | Description |
|---|---|
| 1 | Spindle center axis ISO 30 |
| 2 | Tool holder taper body ISO 30 |
| 3 | Spindle center axis HSK F63 |
| 4 | Tool holder taper body HSK F63 |

| Tool holder type | Concentricity "Z" (mm) |
|---|---|
| ISO 30 | 0.002 |
| HSK F63 | 0.002 |

---

## 3. Compressed Air and Cooling-Water Connections

⚠ Pneumatic connections must be done by trained or professional personnel.
⚠ Before pneumatic connection, valves must be closed and system gas fully vented.

### 3.1 HQD Compressed-Air Specifications
⚠ Input compressed air cleanliness must meet **ISO 8573-1, Class 2/3/4**:
- **Class 2 solid particles:** particle diameter < 1 μm
- **Class 4 humidity:** dew point < 3°C (37.4°F)
- **Class 3 oil content:** < 1 mg/m³

If compressed air does not meet the above, the spindle will be damaged — such damage is **not covered by HQD warranty**.

Recommended pre-treatment sequence (install as close to the HQD product as possible):
1. Compressed air supply line
2. First-stage filter, 5 μm
3. Oil-removal filter, 0.1 μm
4. Output to HQD spindle

Use a check valve to separate dry compressed air from any oil-mist line — the spindle requires dry compressed air.

Since filter efficiency is below 100%, the supply air must already be reasonably clean. Example: at point (1) the supply should meet at least ISO 8573-1 **Class 7/6/4**:
- Class 7 solids: diameter < 40 μm; content < 10 mg/m³
- Class 6 humidity: dew point < 10°C (50°F)
- Class 4 oil: oil content < 5 mg/m³

At end of each day, bleed the filter system / auto-clean the filters. Per the manufacturer's instructions, periodically service the filters and replace them when they no longer function (typically 1–2 times per year).

### 3.2 Compressed Air and Cooling-Liquid Ports

The spindle is fitted with a **single-acting cylinder, spring return**. The cooling water cools the spindle motor and **requires its own independent cooling loop** — pure water with antifreeze, or oil, may be used as the coolant medium.

| ID | Description | Pressure | Thread | Tube ⌀ |
|---|---|---|---|---|
| **A** | Air seal + taper-bore cleaning air inlet | 4.0–4.5 bar | G1/8 | Ø 8×6 |
| **B** | Cylinder open / tool unclamp | 10.5–11.5 bar | G1/8 | Ø 8×6 |
| **C** | Cooling-liquid inlet | 6.0 bar | G1/8 | Ø 8×6 |
| **D** | Cooling-liquid outlet | 6.0 bar | G1/8 | Ø 8×6 |

⚠ Air pressure must **never exceed** the values above — install a pressure regulator to guarantee this.

**Cooling-circuit example:** customer-supplied closed loop with fan, radiator, pump, reservoir (>5 L), pressure switch.

### Pneumatic-Circuit Example (customer-supplied)
1. Factory air supply (6–7 bar; must be strictly filtered and dried)
2. First-stage filter, 5 μm
3. Oil-removal filter, 0.1 μm
4. Pressure regulator
5. **2-position 5-way solenoid valve** (10.5–11.5 bar leg)
6. Quick exhaust valve
7. Tool-unclamp air inlet (Ø8×6)
8. Taper-cleaning + air-seal air inlet (4–4.5 bar, Ø6×4)
9. Continuous compressed air output

This pneumatic diagram is an example only.

### 3.3 Spindle Internal Pressure
The internal air-seal circuit blocks contaminants (dust, swarf) from entering the spindle. **4 bar (58 PSI)** must be supplied; air exits through the ring of seal holes at the spindle nose.

⚠ While the machine is running — **even if the spindle is stopped** — the air-seal compressed air must be supplied continuously.
⚠ During maintenance and cleaning, the air-seal air must also be live to prevent contaminants from entering the spindle.

When the spindle is stopped, confirm a steady airflow at the rotor (the air-seal flow). Otherwise, check the air circuit for integrity and tightness.

### 3.4 Cleaning the Spindle Tool-Taper Bore
During every tool change, compressed air automatically jet-cleans the taper bore. This prevents contamination at the mating surface between the spindle bore and the tool-holder taper. The condition and cleanliness of this mating surface must be checked in routine maintenance.

ℹ When the clamp is open, compressed air must also continue spraying.

---

## 4. Electrical Connections

The installed motor power is the **rated power** (see the spindle technical-spec sheet). Wiring is split into: power cable, thermal-protection switch, and sensor wiring.

⚠ Electrical work must be done by a professional electrician or trained personnel.
⚠ Electrical connections must be done with the power off.
⚠ Protect the spindle against indirect hazards (overload, overcurrent, etc.). Understand the spindle's technical characteristics and provide adequate protection.
⚠ **The spindle power supply must be connected through a VFD (frequency inverter).**

Main power cable: **3-phase + ground**, cross-section must be adequate. Before connecting:
- Verify the 3-phase AC voltage matches the motor nameplate.
- Verify conductor-to-ground resistance meets requirements.
- Compare connections against the motor nameplate.

### 4.1 Power Cable and Thermal-Protection Switch Wiring

| | Power cable color | Function |
|---|---|---|
| **Power** | White | Motor U-phase |
| | Green | Motor V-phase |
| | Red | Motor W-phase |
| | Yellow/Green | GND / motor protective earth |
| **Thermal switch** | Brown (thin) | Stator overheat protection |
| | Brown (thin) | Stator overheat protection |

**Note on the thermal switch:** it is used for stator overheat protection and **should be wired in series with the machine's safety-stop chain**. Normally closed. Opens when stator temperature ≥ **100°C**; recloses when temperature falls below 100°C. Contact rating: **250 V, 5 A**.

⚠ Connect motor power cables to **U, V, W** as shown, and ensure reliable grounding via the indicated terminal. The supply must go through a VFD; configure the VFD per the curve diagram on the terminal-box nameplate.

### 4.2 Sensor Wiring

| Sensor | Wire | Function |
|---|---|---|
| **S1 — Tool clamp (locked) detection** | Brown | +24 V DC |
| | Black | Signal output (**PNP, normally open**) |
| | Blue | 0 V DC |
| **S2 — Tool unclamp detection** | Brown | +24 V DC |
| | Black | Signal output (PNP NO) |
| | Blue | 0 V DC |
| **S3 — Axis stop (rotation stopped) detection** | Brown | +24 V DC |
| | Black | Signal output (PNP NO) |
| | Blue | 0 V DC |

⚠ S1, S2, S3 are default-configured as **PNP normally-open proximity switches**.
⚠ If sensor S1 (tool-lock detection) is not signaling, **starting the spindle is strictly forbidden** — risk of the tool holder flying out.
⚠ If sensor S3 (axis-stop detection) is not producing pulses, the spindle has not stably stopped — **do not issue a tool-unclamp command**.

---

## 7. General Post-Installation Checks

### 7.1 Pre-Start Checks

**Cooling system:**
- Verify smooth flow. If there is no flow or very little flow, troubleshoot first. The spindle must not be started under this condition — **risk of burning out the spindle**.

**Compressed air:**
- Verify correct connections, that pressure meets the spindle's requirements, and that air cleanliness meets spec.
- Compressed air **must be supplied continuously, including when the spindle is stopped**.
- With the spindle stopped and no tool inserted, confirm a stable air-seal flow at the nose.
- Throughout every tool change, the compressed air for taper-bore cleaning must be functioning.

**Electrical:**
- ⚠ The spindle's ground must be connected to the machine's ground terminal.
- ⚠ The temperature alarm must be correctly and effectively connected — it protects against winding overheat.

**VFD settings:**
- Max supply voltage on the VFD must match the spindle nameplate.
- Min frequency for max current (the rated/cutoff frequency) must match the nameplate.
- Max speed on the VFD must match the nameplate.
- Max continuous current on the VFD must match the nameplate.
- For other VFD parameters, contact Changzhou Han Qi Spindle Motor Co., Ltd.

### 7.2 Startup Checks
⚠ The spindle can only be started with a tool properly installed.
⚠ **HSK models only:** the spindle cannot start without a tool holder inserted.

- Verify that the sensor outputs match the spindle's states (clamped vs. unclamped).
- Tool changes must only be done with the spindle stopped.
- Verify the cooling system under correct operation.
- Complete the warm-up procedure before doing any machine work.

---

## 8. Operation and Adjustment

### 8.1 Environmental Conditions
Han Qi tested the spindle under standard conditions. Contact them for guidance if operating under extreme or special conditions.

### 8.2 Trial Run
Each spindle is trial-run at the factory before shipping to ensure the permanent lubrication grease is correctly distributed in the bearing races. All control signals and spindle signals are fully checked on the test bench.

### 8.3 Warm-Up
Han Qi uses high-precision angular-contact bearings, preloaded and packed with permanent special high-speed grease. The first start of each day requires a periodic warm-up so the bearings progressively reach a balanced operating temperature, and the bearing-seat rings achieve uniform expansion, preload, and rigidity.

**Recommended warm-up sequence (no load, no actual machining):**
- **50% of max rated speed for 2 min** — install a tool rated above 15,000 rpm.
- **75% of max rated speed for 2 min** — install a tool rated above 15,000 rpm.
- **100% of max rated speed for 1 min** — install a tool rated above 15,000 rpm.

If the machine has been off for a long time and has cooled to ambient, the warm-up program may also be used.

⚠ **HSK models only:** the spindle cannot start without a tool holder inserted.
⚠ During machining, the spindle can reach very high temperatures. **Do not touch the spindle** without appropriate precautions.

### 8.4 Tool-Holder Taper Body
- **ISO taper standard:** DIN 69871 (pull stud: 0804H0009)
- **HSK standard:** DIN 69893

Requirements:
- Taper geometry must follow the relevant standard (ISO 30 → DIN 69871; HSK → DIN 69893).
- ISO 30 tool tapers must meet **AT3 precision**.
- Do not use tool holders with protrusions, voids, or other shape defects — they affect dynamic balance.
- At max rated speed, dynamic balance must be **G = 2.5 or better (ISO 1940)**.
- Dynamic-balance testing must be done **after full assembly** of the tool holder (pull stud, collet, nut, tool).
- **ISO 30 pull studs must be supplied by HQD only.**

#### 8.4.1 Installing the Pull Stud on an ISO 30 / DIN 69871 Taper
- Thoroughly clean the pull stud and the ISO 30 taper.
- Apply high-strength thread-locker (**Loctite 270** or equivalent) to the pull-stud external thread.
- Torque the pull stud into the ISO 30 taper to **62 Nm**.
- Let the thread-locker cure per its instructions (Loctite 270: 12 h; others per manufacturer).

⚠ Using tools that do not meet the above conditions is forbidden. Not following this guidance, or using an incorrect tool-holder clamp, can damage the tool or spindle and create user risk.

#### 8.4.2 General Safety Precautions for Tool Holders
⚠ Correct tool-holder selection is critical for safe machining.

- The tool-holder taper surface and the spindle's internal clamp surface must be strictly clean to engage safely.
- During machining, avoid contact between rotating components and non-machining components/workpiece.
- Protect the taper seat from foreign matter — use a suitable plug or a spare tool holder to block it.
- At the end of each work day, leave a tool holder in the spindle to prevent sticking, and cover/protect the spindle nose from contamination.
- **Do not rotate the spindle with no tool holder inserted.** Especially for HSK type — rotating it empty will disturb the chuck's balance and effectiveness.

### 8.5 Tool Selection
At max rated speed, dynamic balance must be **G = 2.5 or better (ISO 1940)**.

⚠ Recommendations when choosing tools:
- Ensure the sharpest possible tools, securely locked in the holder.
- Do not use deformed, damaged, defective, or unbalanced tools.
- Before installing the tool into the collet and holder, ensure tool contact surfaces are clean and undamaged.
- High-speed tools must meet: lightweight and compact design; correct and safe installation precision; balanced and symmetric mounting in the holder; cutting edge close to rotation center.

### 8.6 Speed Limits
⚠ For each tool's max rotational speed (rpm), consult the tool manufacturer. **Do not exceed the manufacturer-stated maximum speed.**

The chart on the next page gives the relationship between max **no-load** rotational speed and the combined center-of-gravity "G" of (tool + tool holder). The spindle's max no-load speed depends on the combined weight (tool + holder, including ring nuts, collets, etc.) and the distance "G" from the spindle nose end. Note that special tool/holder combinations have special CoG positions.

ℹ The graphs are indicative only and do not account for cutting parameters. When the end user uses a tool with special features or machines special materials, **the user is responsible for understanding and clearly determining the safe max speed in each case**.

**Example:**
- Spindle is mounted with a tool + holder weighing > 4.5 kg (including ring nut, collet, etc.), with CoG distance "X" = 50 mm from the spindle nose:
  1. Assume the graph matches the spindle model (HQD951 ISO30).
  2. From the table, find the red curve where CoG distance = "X" = 50 mm. If your calculated "X" doesn't lie exactly on a curve, choose the next-higher curve.
  3. With weight = 4.5 kg, max no-load speed = **14,000 rpm**.
  4. If the weight or CoG distance exceeds the HQD-supplied data, the user must analyze and estimate the safe max speed themselves.

### Speed-Limit Chart (ISO30 tool holder)
Curves for X = 50, 70, 90, 110 mm — speed (rpm) vs. combined weight (kg), from ~24,000 rpm at low weight down toward ~8,000 rpm at 6 kg. Higher X → lower allowable speed at any given weight.

---

## 9. Maintenance

The maintenance described here is what is needed to keep the spindle running well.

⚠ For safe spindle operation on the machine, read the machine's manual.
⚠ The spindle contains a preloaded **100 kg internal spring**. The spring acts on the pull stud and can eject the tool. If insufficiently trained personnel intend to disassemble the spindle, they must follow this manual carefully and operate with care.

Before any maintenance, read this chapter through carefully. Safety requirements during every maintenance phase:
- Maintenance must be carried out by qualified technical staff, following this chapter's instructions and standards, using the relevant equipment / tools / products.
- Wear suitable clothing — tight work clothes, safety shoes, etc. Avoid loose, sharp, or bulky garments.
- Post markers or designate a maintenance zone with clearly visible "Machine under maintenance" signs.

Before any maintenance, confirm that:
- The main supply circuit is **disconnected**.
- The tools are **absolutely stationary** (not rotating).

The maintenance supervisor must coordinate good teamwork to keep all personnel safe — no one should be exposed to potential danger. Maintenance personnel must remain in sight of each other so they can signal or gesture warnings to each other in case of danger.

### 9.1 Periodic Maintenance
⚠ Maintenance per the prescribed procedure is essential to preserve the manufacturer's intended operating conditions.
ℹ Frequencies are based on **8 hours/day, 5 days/week** in a typical work environment.

#### 9.1.1 Check Cleanliness of Tool-Holder Taper and Spindle Clamp Taper
**Frequency: Daily**

Before using the spindle, make absolutely sure the tool-holder taper surfaces (black areas in figures 8.1 and 8.2) and the spindle clamp tapers (black areas in figures 8.3 and 8.4) are completely clean — free of any dust, grease, coolant, oil, metal swarf, or corrosion.

**HSK type only:** perform the same check on the tool-to-spindle mating surface (gray areas in figures 8.2 and 8.4).

At the end of each work day, clean these parts with a clean soft cloth.

⚠ **Do not inject compressed air into the spindle when no tool holder is present** — it will damage the spindle.
- Do not spray compressed air directly into the spindle — it will damage the internal air-seal device.
- Also, blowing compressed air into the spindle without a tool holder may contaminate the internal surfaces and force contaminants into the spindle.
- (1) = tool gripping surface; (2) = air-seal device.

⚠ A contaminated joint surface causes the tool holder to seat improperly, creating safety risk for the operator and wearing both spindle and tool holder, degrading machining accuracy.
⚠ Clean the tapers (black highlighted areas) with a clean soft cloth. **Never use abrasive tools or materials** — metal brushes, abrasive cloth, acid, or other corrosive chemicals.

#### 9.1.2 Drain Gas from the Air Circuit
**Frequency: Daily**

At the end of each work day, to better protect the HQD spindle, drain the compressed-air circuit, complete the filter auto-cleaning, drain water, etc.

#### 9.1.3 Protect the Spindle Taper Seat
**Frequency: Daily**

⚠ Do not allow dust into the spindle taper seat. Block the bore with a suitable plug or a spare tool holder.

⚠ At the end of each work day, remove the tool holder from the spindle to prevent sticking. To protect the spindle interior from contamination, you may plug the spindle with a clean, dry, room-temperature spare tool holder.

#### 9.1.4 Tool-Holder Cleaning
**Frequency: Every 2 weeks**

Use a clean soft cloth dampened with **ethanol** to carefully clean the tool-holder taper (black areas of figures 8.1 and 8.2).

**HSK type only:** after ethanol cleaning, spray **KLÜBER LUSIN PROTECT G 31** anti-rust onto the holder taper and spread it evenly with a cloth.

#### 9.1.5 HSK Chuck Function Test
**Frequency: Every 6 months, or after 200,000 tool changes**

Check the position/clearance of the chuck pop-out device.
- Use the tool wrench to lock the pop-out device screw.
- Check the clamping force (use measurement equipment to check, recommended). If clamping force is below **70% of the rated value**, do the following:
  - Re-apply lubricant, then recheck clamping force.
  - Replace the chuck, then recheck clamping force.
  - Replace the entire clamping assembly.

#### 9.1.6 Inspect Electrical Connectors
**Frequency: Monthly**

Verify the integrity of power and signal cables; confirm electrical connectors are tightly secured. Check pneumatic connectors and air-line seals.

#### 9.1.7 Replace Compressed-Air Circuit Filters
**Frequency: Per the filter manufacturer's specification**

For the compressed-air filters used by the HQD spindle, follow the manufacturer's instructions for periodic servicing and replacement.

#### 9.1.8 Bearings
**Frequency: Do not service**

⚠ The bearings have permanent lubrication and **do not require additional lubricant**.

---

End of translated content (19 pages). Sections 5 and 6 are not present in the source PDF; numbering jumps from §4 to §7.
