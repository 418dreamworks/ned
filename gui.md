2026-08-06 01:38:41  program/MDI done (motion complete) -> MANUAL + teleop (MPG live)
2026-08-06 01:38:41  TELEOP re-entered (machine ON + homed) -> MPG live
2026-08-06 01:39:26  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-06 01:39:26  ned_brain exited (atexit; normal interpreter exit)
2026-08-06 01:39:26  stored_home.json final save at exit
2026-08-06 01:39:43  ==== ned_brain start ==== (resume=False head_zero={'a': (36, 8235356), 'c': (-169, 59257275)} gears={'a': 128.25, 'c': 203.7471})
2026-08-06 01:39:43  MACHINE ON -> head read (A/C will home IN PLACE, no motion)
2026-08-06 01:39:45  DECLARE: A held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 01:39:45  DECLARE: C held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 01:39:45  DECLARE: STALE frame from stored_home.json (saved 2026-08-06 01:39:26): {0: -72.645, 1: -1433.28, 2: -421.8214, 3: -72.647}
2026-08-06 01:39:47  DECLARE: A/C from the absolute read: A=NOT READ YET  C=NOT READ YET
2026-08-06 01:39:47  DECLARED HOME (zero-motion, NML 112): joints [0, 1, 2, 3] where they stand; homed=(1, 1, 1, 1, 0, 0) all6=False (STALE HOME until menu Home All)
2026-08-06 01:39:47  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 01:39:49  HEADREAD C: +0.000 deg  (mt=-169 w=59257558)
2026-08-06 01:39:49  HEADREAD -> ini.5.home_offset = +0.0000
2026-08-06 01:39:50  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 01:39:52  HEADREAD A: -0.013 deg  (mt=36 w=8550891)
2026-08-06 01:39:52  HEADREAD -> ini.4.home_offset = -0.0132
2026-08-06 01:39:52  HEAD READ armed: C=+0.000 A=-0.013
2026-08-06 01:39:52  IN-PLACE HOME: joint(s) [4, 5] homed where they stand (no motion): A=-0.013  C=+0.000
2026-08-06 01:39:53  IN-PLACE HOME: joint 4 homed, ini.home restored to 0
2026-08-06 01:39:53  IN-PLACE HOME: joint 5 homed, ini.home restored to 0
2026-08-06 01:39:53  SPINDLE RESTORE: T5 re-declared in spindle after reboot (sensor-confirmed clamped); tool_in_spindle=5
2026-08-06 01:39:53  TOOL GUARD ARMED (record served): record T5, LinuxCNC T5
2026-08-06 01:39:53  MODE xyzac: TOOL-TIP kins (launched as type 0), pivot base 158.351 + live tool length. XYZ means the TOOL TIP.
2026-08-06 01:40:28  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-06 01:40:28  ned_brain exited (atexit; normal interpreter exit)
2026-08-06 01:40:28  stored_home.json final save at exit
