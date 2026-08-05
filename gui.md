2026-08-04 23:53:13  ned_brain EXIT on signal 15 (SIGTERM)
2026-08-04 23:53:13  ned_brain exited (atexit; normal interpreter exit)
2026-08-04 23:53:13  stored_home.json final save at exit
2026-08-04 23:53:31  ==== ned_brain start ==== (resume=False head_zero={'a': (36, 14929465), 'c': (-169, 59257275)} gears={'a': 128.25, 'c': 203.7471})
2026-08-04 23:53:31  MACHINE ON -> head read (A/C will home IN PLACE, no motion)
2026-08-04 23:53:33  DECLARE: A held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-04 23:53:33  DECLARE: C held back -- no absolute read yet, banner stays UNHOMED until it lands
2026-08-04 23:53:33  DECLARE: STALE frame from stored_home.json (saved 2026-08-04 23:53:13): {0: -58.415, 1: -92.528, 2: -457.9619, 3: -58.4138}
2026-08-04 23:53:35  DECLARE: A/C from the absolute read: A=NOT READ YET  C=NOT READ YET
2026-08-04 23:53:35  DECLARED HOME (zero-motion, NML 112): joints [0, 1, 2, 3] where they stand; homed=(1, 1, 1, 1, 0, 0) all6=False (STALE HOME until menu Home All)
2026-08-04 23:53:35  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 23:53:37  HEADREAD C: -0.001 deg  (mt=-169 w=59222848)
2026-08-04 23:53:37  HEADREAD -> ini.5.home_offset = -0.0009
2026-08-04 23:53:37  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 23:53:39  HEADREAD A: -0.009 deg  (mt=36 w=15145314)
2026-08-04 23:53:39  HEADREAD -> ini.4.home_offset = -0.0090
2026-08-04 23:53:40  HEAD READ armed: C=-0.001 A=-0.009
2026-08-04 23:53:40  IN-PLACE HOME: joint(s) [4, 5] homed where they stand (no motion): A=-0.009  C=-0.001
2026-08-04 23:53:40  IN-PLACE HOME: joint 4 homed, ini.home restored to 0
2026-08-04 23:53:40  IN-PLACE HOME: joint 5 homed, ini.home restored to 0
2026-08-04 23:53:48  program/MDI done (motion complete) -> MANUAL + teleop (MPG live)
2026-08-04 23:53:48  TELEOP re-entered (machine ON + homed) -> MPG live
2026-08-04 23:54:14  HOME ALL -> parallel head read (A/C home last in the sequence)
2026-08-04 23:54:52  HOME CYCLE: A+C homed -> post-read verify
2026-08-04 23:54:52  HEADREAD C start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 23:54:54  HEADREAD C: +0.000 deg  (mt=-169 w=59263958)
2026-08-04 23:54:54  HEADREAD -> ini.5.home_offset = +0.0002
2026-08-04 23:54:55  HEADREAD A start (R4 set, SEN about to drop -> A/C locked)
2026-08-04 23:54:57  HEADREAD A: +0.000 deg  (mt=36 w=14923889)
2026-08-04 23:54:57  HEADREAD -> ini.4.home_offset = +0.0002
2026-08-04 23:54:57  HOME VERIFY OK (A+C): C=+0.000 A=+0.000 deg
2026-08-04 23:54:57  TELEOP re-entered (machine ON + homed) -> MPG live
