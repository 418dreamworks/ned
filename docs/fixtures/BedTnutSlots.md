# BedTnutSlots

The six T-nut slots in ned's bed, and the 24 bolt locations used to fix a sheet
down to them. Machine fact, not a job: depths, diameters and cutters belong to
whatever program is bolting something down.

## Frame

Bed frame. `Y0` is the near plate edge, `X0` the near end. Slots run along `X`
and are spaced along `Y`; every number below is negative because the bed extends
in `-X` and `-Y`.

## The bed across Y

| | |
|---|---|
| outer width | 1530.350 (5 ft 0.25 in) |
| plate widths from Y0 | 67, 300, 234, 233, 233, 293, 70 = 1430.000 |
| left for the six slots | 100.350 |
| **slot width** | **16.725 = 0.658 in** |

**The slots are 0.658 in, not 3/4 in.** A 3/4 in slot needs an outer width of
1544.300. Anything cut to fit a 3/4 in slot will not fit.

## Slot centres

| slot | Y | pitch to the next |
|---|---|---|
| 1 | -75.3625 | 316.725 |
| 2 | -392.0875 | 250.725 |
| 3 | -642.8125 | 249.725 |
| 4 | -892.5375 | 249.725 |
| 5 | -1142.2625 | 309.725 |
| 6 | -1451.9875 | — |

The pitch is uneven because it follows the plate widths. Only slots 3-4 and 4-5
share a pitch.

## Bolt locations along each slot

Four per slot, 24 in all.

| | X |
|---|---|
| 1 | -50.0000 |
| 2 | -423.0667 |
| 3 | -796.1333 |
| 4 | -1169.2000 |

Pitch 373.0667, from `1119.2 / 3`: the first sits 50 in from the near end, the
last 50 in from the 4 ft mark.

## If the bed is ever re-measured

Every centre past the first follows from the outer width and the plate widths.
Change either and all of them move — re-derive, do not patch a number.
