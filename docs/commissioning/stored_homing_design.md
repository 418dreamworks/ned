# Stored homing for XYZ/W (skip the switch search at startup)

*Commissioning note: mechanism, sources, what is implemented, what remains. 2026-07-30.*

## Problem
XYZ scales are incremental. The 7I97 FPGA counter free-runs while the board is powered,
but the hm2 driver re-bases its software zero from the live count at every driver load
(`src/hal/drivers/mesa-hostmot2/encoder.c:744`) — so the position reference dies with
every LinuxCNC session, and any power-down kills the count itself. Result: switch homing
was needed every startup. A/C are unaffected (Yaskawa battery-backed absolute, PSO read).

## Why the obvious routes don't exist (all verified in 2.9.8 source)
- Python/task offer ONLY `home(j)` / `unhome(j)` (`emcmodule.cc:1468,1472`) — there is
  no "declare homed" command.
- A `home` command on a switch-configured joint ALWAYS runs the physical search:
  the no-motion path requires `HOME_SEARCH_VEL == 0 && HOME_LATCH_VEL == 0`
  ("both vels == 0 means home at current position", `homing.c:807-811`).
- Search/latch vels are CONFIG-TIME only. The runtime ini pins are exactly
  `ini.N.home`, `ini.N.home_offset`, `ini.N.home_sequence` (`src/emc/ini/inihal.cc:159-161`),
  applied via `EMCMOT_UPDATE_JOINT_HOMING_PARAMS` (`taskintf.cc:352`) — no search vel.
- `[TRAJ]POSITION_FILE` (`taskintf.cc:1677`) restores positions but not homed state, and
  is unnecessary here: the stored number enters through `ini.N.home_offset` instead.

## Mechanism
1. **Save**: while joints 0-3 are all homed AND at rest (traj + joint velocities zero),
   the GUI writes their `joint_actual_position` to `configs/ned5/stored_home.json`
   (atomic tmp+rename; on change > 5 µm or every 10 min). A crash mid-move leaves the
   last at-rest snapshot.
2. **Resume launch**: `tools/run5.sh resume` generates `configs/ned5/ned5_resume_gen.ini`
   from `ned5_iron.ini`, inserting into each `[JOINT_0..3]` — between the section header
   and the `#INCLUDE`, because `IniFile::Find` returns the FIRST match in a section
   (`src/libnml/inifile/inifile.cc`, same first-match trick the ini already uses for
   SUBROUTINE_PATH):
   `HOME_SEARCH_VEL = 0`, `HOME_LATCH_VEL = 0`, `HOME_USE_INDEX = NO`.
   Params files are untouched; the normal config is untouched.
3. **Restore**: HOME ALL in a resume session first runs `_resume_prep()`:
   - joints 0-3 unhomed → load stored_home.json, range-check every value against the
     joint limits, show a Yes/No dialog (saved timestamp + all four positions,
     default **No**: "ONLY if the machine has NOT been moved"), then arm
     `ini.N.home_offset = ini.N.home = stored` via halcmd (stderr visible; any setp
     failure aborts).
   - joints 0-3 already homed (re-home in a resume session) → re-arm from CURRENT
     positions instead, otherwise the in-place home would relabel the machine with the
     stale stored numbers.
   - any failure / decline → the WHOLE cycle is refused (red statusbar + gui.md line);
     an un-armed in-place home would silently declare wherever-it-is as machine zero.
   Then the normal cycle proceeds unchanged: read C → read A → `home(-1)` → verify.
   With the overrides, joints 0-3 home immediately in place: position becomes
   `home_offset` (`homing.c` HOME_SET_SWITCH_POSITION: `offset = home_offset - pos_fb`),
   final move to `home` = same value = zero length. A/C keep their absolute
   read → home → verify flow, including the physical move to zero.

## Implemented (py_compile-clean, offline-tested generator)
- `tools/run5.sh` — `resume` argument + ini generator (dry-run verified: overrides land
  under JOINT_0-3 only, before the includes; JOINT_4/5 untouched).
- `nedgui_handler.py` — `_wire_storedhome` (mode detect via INI_FILE_NAME basename,
  10 s saver timer), `_sh_save`, `_resume_prep`, `_sh_fail`, `_home_cycle` gate.
- Data file: `configs/ned5/stored_home.json` (NOT a param file; created at first homed
  at-rest save).

## Limits / operator notes
- Nothing can PROVE the machine wasn't moved while off — the confirmation dialog is the
  guard. The dialog shows the saved positions: compare against physical reality first.
- After a crash DURING motion, the file holds the last at-rest positions (up to 10 min
  old if the machine had been parked long) — do not resume after a mid-move crash;
  switch-home normally.
- Gantry pair J0/J3 (HOME_SEQUENCE -2) home together; both are armed from the same file.
- First use requires one normally-homed session so stored_home.json exists.

## Remaining for operator (nothing pending in code)
- Test sequence when convenient: normal session → home → verify stored_home.json
  appears; restart with `tools/run5.sh resume` → HOME ALL → confirm dialog → DROs show
  the stored positions with zero motion; A/C read/home/verify as usual; then jog a bit,
  re-click HOME ALL in the same session and confirm coordinates do NOT jump (re-home
  re-arms from current positions).
- No param-file changes are needed or proposed.
