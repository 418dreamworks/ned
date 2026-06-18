# Mesa / LinuxCNC Shopping List

## Confirmed Orders
- ISO30 spindle (3.2 kW, ER20) — ordered
- Yaskawa analog drives — vendor confirmed availability

## Mesa Cards — To Order
| Item | Source | Price | Stock | Notes |
|------|--------|-------|-------|-------|
| 7C81 | mesanet.com | $89 | In stock (24) | SPI FPGA motherboard for RPi 5 |
| 7i77U | mesanet.com / mesaus.com | $229 | Out of stock — check restock | Analog servo daughter card for slot 1. 6x ±10V, 6x encoder, 32 in, 16 out. U version has universal outputs (500mA, built-in flyback) |
| 7i76U | mesanet.com | $149 | TBD | Step/dir daughter card for slot 2. 5x step/dir for workholding rotaries + future stepper expansion |
| 1.5" RPI GPIO cable (x2) | mesanet.com | TBD | TBD | SPI cable from RPi to 7C81. Must be under 2 inches. One per daughter card connection |

## RPi 5 Setup
| Item | Source | Price | Notes |
|------|--------|-------|-------|
| RPi 5 | Amazon/etc | ~$80 | 8GB recommended |
| NVMe hat for RPi 5 | Amazon/etc | ~$15-25 | M.2 adapter board |
| NVMe SSD (128GB+) | Amazon/etc | ~$15-25 | M.2 2230 or 2242 |
| Standoffs | Amazon/etc | ~$5 | For stacking 7C81 + RPi + NVMe |

## Swivel Head Drives — Yaskawa Sigma-X (analog ±10V, no brake)
| Item | Model | Notes |
|------|-------|-------|
| 2x Servo motors | SGMXJ-04AUA6SC2 (400W) or SGMXJ-08AUA6SC2 (750W) | 200V, 26-bit encoder, key+tap shaft, oil seal, NO brake, Σ-7 compatible. Pick capacity based on swivel head flange pattern (60mm for 400W, 80mm for 750W). No brake = simpler wiring |
| 2x Servo drives | SGDXS-2R8A00A0008 (for 400W) or SGDXS-5R5A00A0008 (for 750W) | 200V single-phase input, analog/pulse train interface. Configure for analog velocity mode. Connects to Mesa 7i77U ch5+ch6 via ±10V |

## Workholding Rotaries (comes with steppers)
| Item | Notes |
|------|-------|
| 2x NEMA 34 worm gear + 4-jaw chuck assembly | 20:1 self-locking worm, ~70-85 Nm output, 100 RPM max output, dual-shaft preferred for future encoder option |
| 2x Stepper drives | Included with assembly, step/dir interface |
| Control | Connects to Mesa 7i76U ch1+ch2 via step/dir/enable |

## Spindle VFD
| Item | Source | Price | Notes |
|------|--------|-------|-------|
| 240V single-phase input VFD | TBD | TBD | Matched to 3.2 kW spindle. Must accept 240V single-phase |

## Architecture
```
RPi 5
├── GPIO (SPI) → 7C81 FPGA motherboard
│   ├── Slot 1 (P1): 7i77U — analog servo (6 axes)
│   │   ├── Ch1 ±10V → SDSM (X)
│   │   ├── Ch2 ±10V → SDSM (Y1)
│   │   ├── Ch3 ±10V → SDSM (Y2)
│   │   ├── Ch4 ±10V → SDSM (Z)
│   │   ├── Ch5 ±10V → SGDXS (A — swivel head)
│   │   ├── Ch6 ±10V → SGDXS (C — swivel head)
│   │   ├── Enc 1-4 ← SDSM encoders (X, Y1, Y2, Z)
│   │   ├── Enc 5-6 ← Yaskawa encoders (A, C)
│   │   ├── MPG encoder ← pendant handwheel
│   │   ├── 32 digital inputs ← limits, e-stop, pendant switches
│   │   └── 16 digital outputs → drive enables, relays, VFD
│   ├── Slot 2 (P2): 7i76U — step/dir (5 channels)
│   │   ├── Ch1 step/dir/ena → Stepper drive (Rotary 1 — workholding)
│   │   ├── Ch2 step/dir/ena → Stepper drive (Rotary 2 — workholding)
│   │   └── Ch3-5: spare (future stepper axes)
│   └── Slot 3 (P7): free — future expansion
└── WiFi → network file transfer from CAM computer
```

## LinuxCNC Kinematics
- 6 main machine axes on 7i77U ±10V closed-loop via encoders (X, Y1, Y2, Z, A, C)
- Y1/Y2 configured as gantry slave pair
- 2 workholding rotaries on 7i76U step/dir, open-loop (self-locking worm + massive torque margin)
- RTCP enabled for swivel head (A, C) tool tip following

## Questions for Mesa (call)
1. Do 7i77U/7i76U plug directly into 7C81's 26-pin headers? Any adapter cables needed?
2. When will 7i77U be back in stock?
3. RPi 5 compatibility confirmed with 7C81?
4. Can 7i77U + 7i76U run simultaneously on same 7C81 without issues?
