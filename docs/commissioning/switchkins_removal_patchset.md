# Switchkins-removal patch set — DRAFT, apply at machine-down only

Repo edits go through tools/cfg_edit.sh where they touch configs/; the
files below are docs/tools/src — plain edits, but still machine-down only
(operator is driving). The .so install and these edits land in ONE window,
followed by a -tcp launch verification.

## 1. docs/update_survival.md §A1b (lines 342–350) — REPLACE ENTIRE SECTION

OLD (current, now wrong in two places: objs list, sparm= ini line):

    ### A1b. ned_ac_kins.so — the swivel-head switchable kins (2026-08-05)
    Source `~/Documents/linuxcnc/src/emc/kinematics/ned_ac_kins.c` (tree commit
    47dc37aadd) + Makefile entries (objs list MUST include sincos/kins_util/
    switchkins/$(USERKFUNCS) or the .so exports nothing and ld dies on an empty
    version script). Build: `make ../rtlib/ned_ac_kins.so` in the tree's src/.
    Install (root): copy to /usr/lib/linuxcnc/modules/ like homemod (§A1).
    A LinuxCNC package update DELETES it; rebuild+reinstall, then verify with
    ned/tools/kins/kins_check.py (math lockstep) and an identity-mode launch.
    INI (when wired): KINEMATICS = ned_ac_kins coordinates=XYZXAC sparm=identityfirst

NEW:

    ### A1b. ned_ac_kins.so — the swivel-head tool-tip kins (NON-SWITCHABLE)
    Source `~/Documents/linuxcnc/src/emc/kinematics/ned_ac_kins.c` — a classic
    maxkins-pattern module (KINS_NOT_SWITCHABLE). switchkins is BANNED on ned
    (operator order 2026-08-06): the module must never link switchkins.o and
    `motion.switchkins-type` must NOT exist after launch. Makefile objs list is
    exactly: ned_ac_kins.o, libnml/posemath/_posemath.o, libnml/posemath/sincos.o
    $(MATHSTUB), emc/kinematics/kins_util.o — NO switchkins.o, NO $(USERKFUNCS).
    Build: `make ../rtlib/ned_ac_kins.so` in the tree's src/.
    Install (root): copy to /usr/lib/linuxcnc/modules/ like homemod (§A1).
    A LinuxCNC package update DELETES it; rebuild+reinstall, then verify:
    (a) ned/tools/kins/kins_check.py (math lockstep),
    (b) -tcp launch: loadrt banner prints "NON-SWITCHABLE",
    (c) `halcmd show pin motion.switchkins-type` returns EMPTY,
    (d) `halcmd getp ned_ac_kins.pivot-length` reads arm-fed (head_pivot +
        tool length), not the 250 placeholder.
    INI: KINEMATICS = ned_ac_kins coordinates=XYZXAC
    (coordinates= is the ONLY module param; any sparm= fails loadrt.)

## 2. tools/run5.sh:183–187 — comment rewrite (functional lines untouched)

OLD:
    # TOOL-TIP LAUNCHES DIRECTLY IN TYPE 0 (2026-08-05): switching switchkins
    # at runtime UNHOMES every joint (LinuxCNC invalidates homing on a kins
    # change) -- the machine came up homed, switched, and then refused to jog.
    # Instead generate an ini whose type 0 IS the tool-tip kins. Safe because
    # identity and tool-tip agree EXACTLY at A=0, which is where homing happens.

NEW:
    # TOOL-TIP KINS IS NON-SWITCHABLE (operator order 2026-08-06): runtime
    # kins switching unhomes every joint, so ned_ac_kins is a classic fixed
    # module and this generated ini simply loads it instead of trivkins.
    # Safe because identity and tool-tip agree EXACTLY at A=0, which is
    # where homing happens.

Also :218 `echo "run5: TOOL-TIP kins at launch (no runtime switch)"` →
    echo "run5: TOOL-TIP kins at launch (non-switchable module)"

## 3. tools/live/ned_brain.py — two comment fixes (no code change)

:526–528 OLD:
        # NED_KINS=tooltip flips switchkins to type 1 (tool-tip mode) at the
        # homed upright pose, where identity and tool-tip agree exactly.
        # One shot; missing env (old launcher) = no clamps, no switch.
NEW:
        # NED_KINS=tooltip means run5 launched the NON-SWITCHABLE tool-tip
        # kins (identity and tool-tip agree exactly at the homed upright
        # pose). One shot; missing env (old launcher) = no clamps.

:574–575 OLD:
                # NO runtime switchkins call: it unhomes every joint
                # (2026-08-05). run5 launches the tool-tip kins as type 0.
NEW:
                # Kins is non-switchable by design (a runtime kins switch
                # unhomes every joint). run5 launches the tool-tip module.

:576 log string OLD: 'MODE %s: TOOL-TIP kins (launched as type 0), pivot '
                NEW: 'MODE %s: TOOL-TIP kins (non-switchable), pivot '

## 4. tools/kins/kins_check.py:8  (NOTE the leading space — keep it in the anchor)

OLD: ` 3. A=0  =>  TCP == identity for all C (seamless mode switch at upright)`
NEW: ` 3. A=0  =>  TCP == identity for all C (homing happens upright)`

## 4b. docs/kinematics_quickref.md:19 (advisor-found residue)

Line 19 says real TCP/RTCP is "Deferred" and recommends building it
"switchable via `switchkins`" — both false now. Rewrite to state: ned runs
its own NON-SWITCHABLE ned_ac_kins tool-tip module (switchkins banned by
operator order 2026-08-06). Line 11 (distro background) stays. The vendored
manual under docs/linuxcnc/ stays untouched.

## 4c. run5.sh — ALL launch flags required and explicit (operator
## 2026-08-06: "no plain run5 allowed. it must be clearly speced with
## axis intent" + "-xyzac -tcp and -xyzac -notcp are two different
## things. make the flags required and explicit")

- Bare `run5.sh` REFUSES with a usage line. No default axis set.
- `-xyzac` alone REFUSES: it must carry exactly one of `-tcp` (tool-tip
  ned_ac_kins) or `-notcp` (trivkins identity) — new -notcp flag, no
  default kins, ever.
- `-xyz -notcp` = allowed: trivkins, no A/C joints (operator's stated use
  for non-AC programs). `-xyz -tcp` = REJECTED with an error message (no
  head axes to compensate).
- pb_restart.sh relaunches the SAME flags the session was launched with;
  docs quoting bare run5.sh get flags added.

## 5. src tree (already done, uncommitted)

- emc/kinematics/ned_ac_kins.c rewritten (classic, KINS_NOT_SWITCHABLE);
  old source at git f17fe9272d and emc/kinematics/ned_ac_kins.c.switchkins-bak
- src/Makefile ned_ac_kins-objs: dropped switchkins.o + $(USERKFUNCS)
- COMMIT the linuxcnc tree at machine-down (msg: "ned_ac_kins: non-switchable
  classic module (operator order: no switchkins)")

## 6. Install + verify (machine-down window, in order — VERIFY BEFORE COMMIT)

1. Apply edits 1–4b above.
2. sudo cp ~/Documents/linuxcnc/rtlib/ned_ac_kins.so /usr/lib/linuxcnc/modules/
3. Operator launches run5.sh -xyzac -tcp.
4. Verify: banner "NON-SWITCHABLE" in lcnc.log; motion.switchkins-type pin
   ABSENT; pivot-length ≈ head_pivot + tool, not 250; kins_check.py passes.
5. Only after 4 passes: commit ned repo + linuxcnc tree (a failed launch
   must not leave a commit claiming success).

Also at pickup of the AhBt work (task #25): the saved plan file
curious-waddling-wilkinson.md still describes SWITCHABLE comps — reword to
non-switchable variants before building ned_ab_kins.
