# Mesa / LinuxCNC Shopping List

**Architecture decision (2026-06-17):** going with the **7I97T + 7I85S + 7I84U
Ethernet route**. The earlier RPi5 + 7C81 + 7i77U + 7i76U **SPI plan is dropped**
— do not order those cards. See `docs/wiring_to_hal_guide.md` "Mesa Hardware
Target" for the I/O surface this provides.

**Build order:** Phase 1 is a LinuxCNC config that reproduces *everything the
existing Fagor machine does today* — X-gantry (X + W tandem), Y cross, Z, the
spindle/VFD, and the full drawbar tool-change + toolsetter + sensors. The swivel
head (A/C) and workholding rotaries are later phases and are parked at the bottom
of this list.

## Confirmed / Already Have
- ISO30 spindle (3.2 kW, ER20) — ordered
- Mollom G75-2T-7R5-G-B spindle VFD — replacing the Saftronics VG5 (see `docs/mollom_facts.md`)
- Yaskawa analog drives — vendor confirmed availability (swivel-head phase)

## Mesa Cards — Ethernet Route (Phase 1)
| Item | Price | Role |
|------|-------|------|
| **7I97T** | $279 | Main Ethernet FPGA card (`hm2_eth`). 6× analog ±10 V out (pwmgen→analog), 6× encoder in, 16 isolated DI, 6 isolated DO, 1 Smart Serial port, 1 DB25 expansion port. Carries the 4 axis velocity commands + spindle. |
| **7I85S** | $69 | Step/dir daughter card on the 7I97T's DB25 port. +4 encoder inputs, 8 differential outputs (= 4 step/dir pairs) for the future workholding rotaries, 1 RS-422. |
| **7I84U** | $79 | Digital I/O expansion over Smart Serial (RJ45). +32 isolated DI, +16 universal isolated DO (5–28 VDC, 500 mA). Carries the bulk of the cabinet's sensor/solenoid I/O. |

**~$427** for the three cards.

**I/O surface:** 6 analog ±10 V (4 axes + spindle + spare), 10 encoder inputs,
4 step/dir, 48 digital inputs, 22 digital outputs.

## Control PC
| Item | Notes |
|------|-------|
| LinuxCNC PC + dedicated NIC | `hm2_eth` needs a dedicated Ethernet port to the 7I97T (no switch in between). The existing Pi can serve as the control PC if a dedicated wired link is given to the Mesa card and networking moves to WiFi; otherwise a small x86 PC with two NICs. **Decide before wiring.** |

## Spindle VFD
| Item | Notes |
|------|-------|
| Mollom G75-2T-7R5-G-B | Already on hand. ±10 V speed ref on AI2, FWD/REV on S1/S2, fault on RY1, running on Y1. Full migration wiring + parameters in `docs/mollom_facts.md`. No HAL change vs the VG5 if the R1 polarity-translator relay is in place. |

---

## Later Phases (parked — not Phase 1)

### Swivel Head Drives — Yaskawa Sigma-X (analog ±10 V, no brake)
| Item | Model | Notes |
|------|-------|-------|
| 2× Servo motors | SGMXJ-04AUA6SC2 (400 W) or SGMXJ-08AUA6SC2 (750 W) | 200 V, 26-bit encoder, key+tap shaft, oil seal, NO brake, Σ-7 compatible. Capacity by swivel-head flange (60 mm/400 W, 80 mm/750 W). |
| 2× Servo drives | SGDXS-2R8A00A0008 (400 W) or SGDXS-5R5A00A0008 (750 W) | 200 V single-phase, analog/pulse interface. Analog velocity mode. A/C axes → 7I97T analog ch5/ch6 ±10 V. |

### Workholding Rotaries (steppers included)
| Item | Notes |
|------|-------|
| 2× NEMA 34 worm gear + 4-jaw chuck | 20:1 self-locking worm, ~70–85 Nm, 100 RPM max output, dual-shaft for future encoder. |
| 2× Stepper drives | Included. step/dir interface → 7I85S step/dir pairs 1–2. |

### Future LinuxCNC Kinematics (with swivel head)
- Phase 1: `trivkins coordinates=XYZX` — X is a gantry (joints 0 + 3 = X1 + W), Y, Z. 4 analog servos closed-loop on encoders.
- Later: add A + C swivel-head servos (analog ±10 V on 7I97T ch5/ch6), enable RTCP for tool-tip following.
- Later: 2 workholding rotaries on 7I85S step/dir, open-loop (self-locking worm + torque margin).
