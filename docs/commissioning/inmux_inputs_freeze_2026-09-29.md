# inmux inputs froze FALSE, 2026-09-29 12:29:52 — cleared by a relaunch

**Purely software. A restart fixed it and nothing in the cabinet was wrong.**
Operator: *"its none o those things a restart fixed it, purely software"* —
after I had sent him to meter a TB5 IN COMMON jumper that was fine.

## The signature

```
12:29:52.928   inmux.00.input-12  TRUE -> FALSE     sig-air-pressure-ok
12:29:52.928   inmux.00.input-14  TRUE -> FALSE     sig-estop-chain-up
```

Same Mesa sample, and neither moved again for four minutes. Before that
`input-12` had read TRUE for 187 consecutive samples.

Everything else looked healthy, which is what made it convincing:

| | |
|---|---|
| `mesa.log` | still sampling to the current second |
| `hm2_7i97.0.packet-error` | FALSE |
| `packet-error-total` | 21, not climbing |
| `read.time` / `write.time` | running |
| `7i84.0.0.input-30` | still TRUE — the card was not wholly dark |

LinuxCNC refused to leave E-stop for the correct reason, because
`emc-enable-in = e-stop-released AND air-OK` (`ned5_iron.hal:431`) and both
were false.

## Why the cabinet looked guilty, and why that was wrong

`mesa_7i97t_wiring.md:279-282` puts IN12/IN13 on the IN COMMON at TB5 pin 9
and IN14/IN15 on pin 12, with pin 12 jumpered off pin 9. **IN12 and IN14 are
exactly the two that died together**, and IN10/IN11 — on the direct return at
pin 6 — were unaffected. One open jumper explains the pattern perfectly.

**It also explains a frozen serial read perfectly, and that is the lesson.**
Both hypotheses predict the same HAL state. The operator distinguished them in
one move: he shorted the air circuit at the contactor and `input-12` did not
change. That ruled out the switch; it did not rule out the return. The restart
did.

**A field fault and a stale driver read are indistinguishable from inside
HAL.** Two inputs changing in the same sample is not evidence of a shared
common — it is equally evidence of a single stale frame.

## The subsystem, and what preceded it

The 7I84 and the inmux hang off Smart Serial port 0, which had already
complained twice that day:

```
hm2/hm2_7i97.0: Smart Serial port 0: DoIt not cleared from previous servo
thread. Servo thread rate probably too fast.
hm2/hm2_7i97.0: error finishing read!
```

Same subsystem as the two Mesa link failures of 2026-09-28 (17:25 and 21:25),
and the same root condition: a 1 ms servo thread on a 4-core Pi with no
`isolcpus`, loadavg near 7. See `docs/migration.md` §2.

## Recognise it in one step next time

**Before touching the cabinet:** if two or more inputs on different circuits
change state in the SAME Mesa sample and then never move again, relaunch
first. It costs a minute. The cabinet check costs twenty and needs a meter.

If the relaunch does not clear it, then it is the wiring, and TB5 pins 9 and
12 are where to start.
