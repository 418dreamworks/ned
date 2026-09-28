# PB says the machine is ON while the drive enable is dead — 2026-09-28

## The signature, in one line

```
halui.machine.is-on           TRUE     <- PB shows the machine ON
iocontrol.0.user-enable-out   FALSE    <- the pin the hardware actually follows
```

When those two disagree, **believe `user-enable-out`.** It is the E-stop enable
output; `*7` follows it, and R0 and R11 hang off `*7`, so the XYZ servo bus and
the head/stepper contactor are both dead while the screen says everything is on.

Only a PB restart cleared it. Nothing in the GUI showed the machine as off.

## What it looked like from the outside

The spindle "stopped dead" mid warm-up and would not restart. Everything on the
spindle path read correct — `spindle.0.on`, `forward`, `permit.out`,
`pwmgen.05.enable` and a 4500 speed reference all asserted, `sig-vfd-fault` and
`sig-spindle-overtemp` both FALSE — so the spindle looked like the fault. It was
not. The spindle is switched off along with everything else when the machine
leaves the ON state.

**The tell was that the drives had no power.** The operator noticed it before any
pin did: the VFD had power, the Mesa cards had power, the drives did not. That
split is only possible below `*7`, because the VFD and the cards are fed
separately.

## The actual sequence, from the session log

```
ned_pendant: ZERO Z (102 detents)
JOG status: MOVING - 18.2 mm/s
joint 2 following error
Homing menu DISABLED because: moving (vel 38.312); machine not ON (state 2)
JOG status: OFF - machine not on
```

Z threw a following error while being jogged, which dropped the machine out of
ON and with it `*7`, R0 and R11. The machine was then powered back on from the
GUI — `halui.machine.is-on` went TRUE and stayed TRUE — but
`user-enable-out` did not follow, so the contactors never re-closed.

## What does NOT explain it

- **The 70 V brick being off is normal in `-xyz`.** It feeds the B rotary
  stepper through R11 pole 4 (`components.md:78`), and B is not configured in
  three-axis mode. Z is a servo on the R0 bus (`components.md:26`), a different
  supply. An unpowered brick in `-xyz` is not evidence of anything.
- **`sig-spindle-running` TRUE while the spindle is commanded off is not a lying
  input.** It is `F5-03 = 1`, the VFD's own "drive operating" output
  (`vfd/mollom_parameterization.md:132`), and it stays true while the shaft
  coasts down.
- **The packet errors are real but separate.** `packet-error-exceeded` was TRUE
  with `packet-error-total 7` against a limit of 10. Worth chasing on its own;
  it did not cause this.

## Check it in one command

```
halcmd -s show pin | grep -E 'user-enable-out|machine.is-on'
```

Disagreement means restart PB. Nothing else clears it.
