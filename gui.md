2026-08-04 14:42:35  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-04 14:42:35  ned_brain exited (atexit; normal interpreter exit)
2026-08-04 14:42:35  stored_home.json final save at exit
2026-08-04 14:43:58  ==== ned_brain start ==== (resume=False head_zero={'a': (36, 14929465), 'c': (-169, 59257275)} gears={'a': 128.25, 'c': 203.7471})
2026-08-04 14:43:58  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 14:44:00  HEADREAD C: -0.001 deg  (mt=-169 w=59227165)
2026-08-04 14:44:00  HEADREAD -> ini.5.home_offset = -0.0008
2026-08-04 14:44:01  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 14:44:03  HEADREAD A: -0.008 deg  (mt=36 w=15132032)
2026-08-04 14:44:03  HEADREAD -> ini.4.home_offset = -0.0085
2026-08-04 14:44:03  HEAD READ armed: C=-0.001 A=-0.008
2026-08-04 14:44:03  PRE-POWER DECLARE: canary home, joint 0, machine OFF
2026-08-04 14:44:03  DECLARE: STALE frame from stored_home.json (saved 2026-08-04 14:42:35): {0: -58.795, 1: -91.324, 2: -508.5052, 3: -58.7948}
2026-08-04 14:44:07  DECLARE: home(0) missed (attempt 1), reissuing
2026-08-04 14:44:10  DECLARE: home(0) missed (attempt 2), reissuing
2026-08-04 14:44:13  DECLARE: home(1) missed (attempt 1), reissuing
2026-08-04 14:44:16  DECLARE: home(1) missed (attempt 2), reissuing
2026-08-04 14:44:20  DECLARE: home(2) missed (attempt 1), reissuing
2026-08-04 14:44:23  DECLARE: home(2) missed (attempt 2), reissuing
2026-08-04 14:44:23  DECLARE: A/C from the absolute read: A=-0.0085  C=-0.0008
2026-08-04 14:44:23  DECLARED HOME (zero-motion, NML 112): joints [0] where they stand; homed=(0, 0, 0, 0, 0, 0) all6=False (STALE HOME until menu Home All)
2026-08-04 14:44:24  PRE-POWER DECLARE: LinuxCNC refuses homing before POWER (task gate) -- declare stays on the ON edge; the one refusal toast above is the canary
2026-08-04 14:44:40  MACHINE ON -> head read (A/C will home IN PLACE, no motion)
2026-08-04 14:44:42  DECLARE: STALE frame from stored_home.json (saved 2026-08-04 14:42:35): {0: -58.795, 1: -91.324, 2: -508.5052, 3: -58.7948}
2026-08-04 14:44:45  DECLARE: A/C from the absolute read: A=-0.0085  C=-0.0008
2026-08-04 14:44:45  DECLARED HOME (zero-motion, NML 112): joints [0, 1, 2, 3, 4, 5] where they stand; homed=(1, 1, 1, 1, 1, 1) all6=True (STALE HOME until menu Home All)
2026-08-04 14:44:45  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 14:44:47  HEADREAD C: -0.001 deg  (mt=-169 w=59227305)
2026-08-04 14:44:47  HEADREAD -> ini.5.home_offset = -0.0008
2026-08-04 14:44:47  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 14:44:49  HEADREAD A: -0.008 deg  (mt=36 w=15131957)
2026-08-04 14:44:49  HEADREAD -> ini.4.home_offset = -0.0085
2026-08-04 14:44:50  HEAD READ armed: C=-0.001 A=-0.008
2026-08-04 14:46:20  program/MDI done (motion complete) -> MANUAL + teleop (MPG live)
2026-08-04 14:46:20  TELEOP re-entered (machine ON + homed) -> MPG live
2026-08-04 14:47:03  program/MDI done (motion complete) -> MANUAL + teleop (MPG live)
2026-08-04 14:47:03  TELEOP re-entered (machine ON + homed) -> MPG live
