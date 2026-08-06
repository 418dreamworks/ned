2026-08-06 10:53:13  ==== ned_brain start ==== (resume=False head_zero={'a': (36, 17081143), 'c': (-169, 59257275)} gears={'a': 128.25, 'c': 203.7471})
2026-08-06 10:53:13  MACHINE ON -> head read (A/C will home IN PLACE, no motion)
2026-08-06 10:53:15  DECLARE: A held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 10:53:15  DECLARE: C held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 10:53:15  DECLARE: STALE frame from stored_home.json (saved 2026-08-06 10:48:03): {0: -72.655, 1: -1432.044, 2: -420.8685, 3: -72.654}
2026-08-06 10:53:16  DECLARE: A/C from the absolute read: A=NOT READ YET  C=NOT READ YET
2026-08-06 10:53:16  DECLARED HOME (zero-motion, NML 112): joints [0, 1, 2, 3] where they stand; homed=(1, 1, 1, 1, 0, 0) all6=False (STALE HOME until menu Home All)
2026-08-06 10:53:17  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 10:53:19  HEADREAD C: -0.000 deg  (mt=-169 w=59255027)
2026-08-06 10:53:19  HEADREAD -> ini.5.home_offset = -0.0001
2026-08-06 10:53:19  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 10:53:21  HEADREAD A: +0.005 deg  (mt=36 w=16971667)
2026-08-06 10:53:21  HEADREAD -> ini.4.home_offset = +0.0046
2026-08-06 10:53:22  HEAD READ armed: C=-0.000 A=+0.005
2026-08-06 10:53:22  IN-PLACE HOME: joint(s) [4, 5] homed where they stand (no motion): A=+0.005  C=-0.000
2026-08-06 10:53:22  IN-PLACE HOME: joint 4 homed, ini.home restored to 0
2026-08-06 10:53:22  IN-PLACE HOME: joint 5 homed, ini.home restored to 0
2026-08-06 10:53:22  SPINDLE RESTORE: T5 re-declared in spindle after reboot (sensor-confirmed clamped); tool_in_spindle=5
2026-08-06 10:53:22  TOOL GUARD ARMED (record served): record T5, LinuxCNC T5
2026-08-06 10:53:22  MODE xyzac: TOOL-TIP kins (launched as type 0), pivot base 155.926 + live tool length. XYZ means the TOOL TIP.
2026-08-06 10:53:29  SEQ INTERLOCK armed -- mode belongs to the sequence
2026-08-06 10:56:56  SEQ INTERLOCK released -- MANUAL restore is live
2026-08-06 10:57:24  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-06 10:57:24  ned_brain exited (atexit; normal interpreter exit)
2026-08-06 10:57:24  stored_home.json final save at exit
