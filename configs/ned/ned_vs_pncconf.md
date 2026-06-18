# ned.hal  vs  pncconf reference  (hm2-servo-eth.hal)

Reference = the analog-servo-over-Ethernet config that ships with LinuxCNC and is
the structure pncconf / MesaCT generate:
  /usr/share/doc/linuxcnc/examples/sample-configs/by_interface/mesa/hm2-servo/hm2-servo-eth.hal

Verdict: SAME skeleton. ned.hal is that skeleton extended to the real machine
(4th gantry joint, real e-stop, spindle, limits, full drawbar tool change).
A pncconf run would emit the generic 3-axis skeleton and you would then hand-add
exactly the "ADDED" items below -- which ned.hal already contains.

================================================================================
SAME  (structural parity -- identical pattern, just my names)
================================================================================
- Core loads: loadrt [KINS]KINEMATICS ; loadrt [EMCMOT]EMCMOT ...num_joints ;
  loadrt pid ; loadrt hostmot2 ; load the hm2 ethernet driver.
- Thread order: hm2.read -> motion-command-handler -> motion-controller
  -> pid.N.do-pid-calcs (per joint) -> hm2.write.
- Per-joint servo loop (identical wiring):
    joint.N.amp-enable-out -> pid.N.enable + pwmgen.NN.enable
    encoder.NN.position    -> pid.N.feedback + joint.N.motor-pos-fb
    joint.N.motor-pos-cmd  -> pid.N.command
    pid.N.output           -> pwmgen.NN.value
- Encoder setup lines: counter-mode 0, filter 1, index-*; scale = [JOINT_n]INPUT_SCALE.
- PID gains pulled from INI: P I D BIAS FF0 FF1 FF2 DEADBAND MAX_OUTPUT.
- pwmgen: output-type 1; scale = [JOINT_n]OUTPUT_SCALE; pwm_frequency.
- Tool prepare/change handshake nets to iocontrol.
- Home switch read through the INVERTED input pin (.in_not / .input-NN-not).

================================================================================
DIFFERENT  (deliberate -- real machine, not the generic template)
================================================================================
- Joints: reference 3 (X,Y,Z). ned 4 with `trivkins coordinates=XYZX` -- joint 3
  is the 2nd gantry side (W), so X is driven by two servos (joints 0 + 3).
- E-STOP: reference is a DUMMY loopback (user-enable-out -> emc-enable-in).
  ned reads the REAL hardware e-stop chain (sig-estop-released -> emc-enable-in)
  and drives drive-enable (R5 coil) from user-enable-out. pncconf always emits
  the dummy; you replace it -- ned already has the real one.
- pid channels named pid.x/y/z/w (vs pid.0/1/2) and descriptive sig-* signal
  names (vs emcmot.NN.* / motor.NN.*). Cosmetic only.
- Board prefix literal hm2_7i97.0 (vs parametric hm2_[HOSTMOT2](BOARD).0).
  Confirm the real prefix once with `halcmd show pin hm2_7i97.0`.

================================================================================
ADDED  (everything the Fagor machine does -- absent from the generic reference)
================================================================================
- SPINDLE: motion.spindle.0.on/forward/reverse -> spin-cw / spin-ccw with a
  drawbar-clamped interlock; speed-out-abs -> pwmgen.04 (+/-10 V to the VFD);
  running / vfd-fault / overtemp inputs.
- LIMITS: 6 NC fail-safe limit switches -> joint pos/neg-lim-sw-in + home-sw-in.
- TOOL CHANGE: drawbar release/clamp, taper purge, toolsetter deploy, chip
  blow-off as motion.digital-out-*; drawbar up/down + rack as motion.digital-in-*;
  toolsetter probe -> motion.probe-input (for G38). (pncconf only stubs an
  immediate tool-change loopback.)
- PHYSICAL I/O BINDING BLOCK: 7I97T native encoders + pwmgen, and all field
  digital I/O routed via the 7I84U over smart serial.

================================================================================
RAW UNIFIED DIFF  (diff -u reference ned.hal)  -- noisy by nature; above is the
useful read. Included for completeness.
================================================================================
