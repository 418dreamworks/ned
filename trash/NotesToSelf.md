# Notes to Self — Fagor 8055/B Rewiring & LinuxCNC Migration

Personal notes on the process so I can remember what I did and why.

---

1. We cut the 4 black wires and these will go on the right hand side of the case. They should go back into a new conduit.
2. Green and yellow with eyelets are all grounded.
3. Fix nick on the spindle power wire. Double-check UVW to ensure direction is correct — these are NOT labelled for a reason (UVW order determines rotation direction; swap any two to reverse).
4. Yellow from the EMT with spindle power and drive power is ground for the drives. Check green.
5. White, black, and red in the power conduit. Black and white power the switch on the right side. Red goes to the top box, ends midair.
6. The switch on the right-side control box is a selector — either selects power from the machine (past the relay) or wall power. This powers the grease pump. OFF would be selecting wall power, and plugging it in would make it on from wall power. Check the relay circuit on the machine side — seems unnecessary to grease it all the damn time but why not.
7. Toolsetter (Bimba + NVZ3120 5-port solenoid valve): 00-2 is the signal to actuate the solenoid valve. Solenoid valve needs air from supply. It completes the path on wire 0_4. Research a different toolsetter.
8. 00 is the air pressure sensor.
9. Wire 91 goes to nowhere.
10. Wire 33 is the limit switch of the Z axis.
11. Wire 9 is spindle overheating. Connected to little wires 13 and 14, which go INSIDE the Colombo spindle junction box.
12. 45mys terminates in the box on top of the gantry.
13. *77 and R1A1 black are connected to the grease pump. (*77 is part of the power-common / AC neutral terminal range — see note 18.)
14. Wires 2, 3, and 4 are extras with the correct number of conductors for glass scales. They go to one of the X, Y, and Z axis respectively. Wire 1 ran from the box to the main wire control — removed for simplicity at the moment as it wasn't difficult to get another wire through the conduit.
15. 44mys goes to nothing at the top box.
16. *1 *2 is e-stop on screen.
17. Relay numbering convention: R<n> means relay n (my labelling). Terminal positions on the relay base are labelled by row letter + column number. Rows: **A = NO (normally open) contact**, **B = NC (normally closed) contact**, **C = signal/coil (cols 1 and 2 only)**, **D = COM (common)**. So e.g. R6A2 = relay 6, NO contact, column 2. R6C1 = relay 6, coil terminal 1.
18. Cabinet screw terminal block convention: `*<n>` is my symbol for screw terminal n on the cabinet's main terminal block. Ranges identified so far: **`*71` to `*76` = signal common = +24 VDC bus (from the 24 V DC transformer; this is the shared positive supply, not 0 V — note the unusual local convention where "signal common" means the +24 V rail)**, **`*77` to `*79` = power common (AC neutral)**.
