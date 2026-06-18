# Node Dictionary

## Nodes (3-letter codes)

| Code | Component | Description |
|------|-----------|-------------|
| XFR | GE Transformer | GE 9T51B0135, 3kVA, 480→120/240V |
| DEL | Deltrol Relay | Contactor, enables drive bus power |
| CHS | Drive Chassis | SDSM4-1625-17-3 power supply (cap, bridge, shunt, fans) |
| DRX | Drive Module X | Individual drive card, X axis |
| DY1 | Drive Module Y1 | Individual drive card, Y1 axis |
| DY2 | Drive Module Y2 | Individual drive card, Y2 axis |
| DRZ | Drive Module Z | Individual drive card, Z axis |
| DRA | Drive Module A | Future: swivel head A axis |
| DRC | Drive Module C | Future: swivel head C axis |
| D1A | Drive Module R1a | Future: rotary 1 side A |
| D1B | Drive Module R1b | Future: rotary 1 side B |
| D2A | Drive Module R2a | Future: rotary 2 side A |
| D2B | Drive Module R2b | Future: rotary 2 side B |
| CTL | Controller | Fagor 8055 (current), LinuxCNC (future) |
| SVX | Servo X | MTS30U4-42, X axis |
| SY1 | Servo Y1 | MTS30U4-42, Y1 axis |
| SY2 | Servo Y2 | MTS30U4-42, Y2 axis |
| SVZ | Servo Z | MTS30U4-42, Z axis |
| SVA | Servo A | Future: swivel head A axis |
| SVC | Servo C | Future: swivel head C axis |
| S1A | Servo R1a | Future: rotary 1 side A |
| S1B | Servo R1b | Future: rotary 1 side B |
| S2A | Servo R2a | Future: rotary 2 side A |
| S2B | Servo R2b | Future: rotary 2 side B |
| CFN | Control Fan | Control box cooling fan |
| GND | Ground | Chassis/earth ground bus |
| VFD | VFD | Future: new spindle VFD (220V single phase) |
| SPL | Spindle | Future: new spindle motor |
| LUB | Lubrication | InteLube AX2 auto lube system |

## Subnodes

### XFR (GE Transformer)
| Subnode | Description |
|---------|-------------|
| H1 | Primary terminal 1 |
| H2 | Primary tap 208V (H1-H2) |
| H3 | Primary tap 240V (H1-H3) |
| H4 | Primary tap 480V (H1-H4) |
| X1 | Secondary hot 1 (feeds drive bus) |
| X2 | Secondary center tap (ground) |
| X3 | Secondary center tap (ground) |
| X4 | Secondary hot 2 (feeds controls) |

### DEL (Deltrol Relay)
| Subnode | Description |
|---------|-------------|
| CL+ | Coil positive |
| CL- | Coil negative |
| COM | Common contact |
| NO | Normally open contact |

### CHS (Drive Chassis)
| Subnode | Description |
|---------|-------------|
| AC1 | 120V AC bus input hot |
| AC2 | 120V AC bus return |
| FNH | Fan power hot |
| FNN | Fan power neutral |
| B+ | DC bus positive (to drive modules) |
| B- | DC bus negative (to drive modules) |

### DRX / DY1 / DY2 / DRZ / DRA / DRC / D1A / D1B / D2A / D2B (Drive Modules)
| Subnode | Description |
|---------|-------------|
| B+ | DC bus in + (J2 pin 5) |
| B- | DC bus in - (J2 pin 4) |
| M+ | Motor output + (J2 pin 1) |
| M- | Motor output - (J2 pin 2) |
| S+ | Signal command + (J1 pin 4, diff invert) |
| S- | Signal command - (J1 pin 5, diff non-invert) |
| TC | Tacho input (J1 pin 6) |
| CM | Common (J1 pin 2) |
| EN | Enable/Reset (J1 pin 9) |
| FT | Fault output (J1 pin 16) |
| 12+ | +12V output (J1 pin 1) |
| 12- | -12V output (J1 pin 3) |

### CTL (Controller)
| Subnode | Description |
|---------|-------------|
| PWH | 120V AC power hot |
| PWN | 120V AC power neutral |
| xC+ | Axis x command output + (±10V) |
| xC- | Axis x command output - |
| xEN | Axis x enable output |
| xEC | Axis x enable common |
| xE5 | Axis x encoder 5V power out |
| xEG | Axis x encoder ground |
| xEA | Axis x encoder channel A input |
| xEB | Axis x encoder channel B input |

Where x = axis letter/number (X, Y1, Y2, Z, A, C, 1A, 1B, 2A, 2B)

### SVX / SY1 / SY2 / SVZ / SVA / SVC / S1A / S1B / S2A / S2B (Servos)
| Subnode | Description |
|---------|-------------|
| M+ | Motor power + |
| M- | Motor power - |
| T+ | Tacho output + (generator, 7 V/KRPM) |
| T- | Tacho output - |
| E5 | Encoder 5V power in |
| EG | Encoder ground |
| EA | Encoder channel A out |
| EB | Encoder channel B out |

### CFN (Control Fan)
| Subnode | Description |
|---------|-------------|
| HT | 120V AC hot |
| NE | Neutral |

### GND (Ground)
| Subnode | Description |
|---------|-------------|
| BUS | Ground bus bar |
