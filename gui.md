2026-08-06 01:25:29  DECLARE: home(0) missed (attempt 2), reissuing
2026-08-06 01:25:32  DECLARE: home(1) missed (attempt 1), reissuing
2026-08-06 01:25:35  DECLARE: home(1) missed (attempt 2), reissuing
2026-08-06 01:25:39  DECLARE: home(2) missed (attempt 1), reissuing
2026-08-06 01:25:39  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-06 01:25:39  ned_brain exited (atexit; normal interpreter exit)
2026-08-06 01:25:39  stored_home.json final save at exit
2026-08-06 01:30:19  ==== ned_brain start ==== (resume=False head_zero={'a': (36, 8235356), 'c': (-169, 59257275)} gears={'a': 128.25, 'c': 203.7471})
2026-08-06 01:30:19  MACHINE ON -> head read (A/C will home IN PLACE, no motion)
2026-08-06 01:30:20  DECLARE: A held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 01:30:20  DECLARE: C held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-06 01:30:20  DECLARE: STALE frame from stored_home.json (saved 2026-08-06 01:23:21): {0: -72.63, 1: -1433.236, 2: -421.8151, 3: -72.6196}
2026-08-06 01:30:22  DECLARE: A/C from the absolute read: A=NOT READ YET  C=NOT READ YET
2026-08-06 01:30:22  DECLARED HOME (zero-motion, NML 112): joints [0, 1, 2, 3] where they stand; homed=(1, 1, 1, 1, 0, 0) all6=False (STALE HOME until menu Home All)
2026-08-06 01:30:23  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 01:30:25  HEADREAD C: +0.000 deg  (mt=-169 w=59257517)
2026-08-06 01:30:25  HEADREAD -> ini.5.home_offset = +0.0000
2026-08-06 01:30:25  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-06 01:30:27  HEADREAD A: -0.009 deg  (mt=36 w=8460543)
2026-08-06 01:30:27  HEADREAD -> ini.4.home_offset = -0.0094
2026-08-06 01:30:28  HEAD READ armed: C=+0.000 A=-0.009
2026-08-06 01:30:28  IN-PLACE HOME: joint(s) [4, 5] homed where they stand (no motion): A=-0.009  C=+0.000
2026-08-06 01:30:28  IN-PLACE HOME: joint 4 homed, ini.home restored to 0
2026-08-06 01:30:28  IN-PLACE HOME: joint 5 homed, ini.home restored to 0
2026-08-06 01:30:28  SPINDLE RESTORE: T5 re-declared in spindle after reboot (sensor-confirmed clamped); tool_in_spindle=5
2026-08-06 01:30:28  TOOL GUARD ARMED (record served): record T5, LinuxCNC T5
2026-08-06 01:30:28  MODE xyzac: TOOL-TIP kins (launched as type 0), pivot base 158.351 + live tool length. XYZ means the TOOL TIP.
