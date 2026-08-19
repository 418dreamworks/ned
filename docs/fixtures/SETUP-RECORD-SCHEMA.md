# Setup records

Two different things live in this folder.

| kind | file | answers |
|---|---|---|
| **named fixture** | `RotaryFixturePlate.*` | what the fixture *is* — walls, thickness, holes, thread |
| **setup record** | `setup-<job>-<YYYY-MM-DD>.json` | how a blank was *actually held*, measured at the machine |

A named fixture is a part. A setup record is a measurement of one job on the bed,
and it is what `safety/machining-rules.md` R2 requires before a program is
admitted.

## Setup record fields

```json
{
  "job": "<program basename, no extension>",
  "measured": "YYYY-MM-DD",
  "measured_by": "<who put the tape on it>",
  "wcs": "G54",
  "blank_measured": { "x": 0.0, "y": 0.0, "z": 0.0 },
  "blank_origin": "min-X min-Y corner, Z0 = top face",
  "rests_on": { "what": "spoilboard | sacrificial sheet | rails",
                "thickness": 0.0 },
  "holding": "vacuum | tape-and-glue | clamps | dogs | screws",
  "hardware": [
    { "what": "clamp", "nearest_edge": "-X", "distance_from_edge": 0.0 }
  ],
  "notes": ""
}
```

`measured` is the field that makes it a record. **Null or absent means the file
describes an intention and admits nothing** — R2 refuses the program exactly as
if the file were not here.

`distance_from_edge` is to the *blank edge*, positive outward. Anything inside
the program's swept envelope on that edge fails the check.

## The check R2 runs against it

```
no entry in hardware[] inside the swept envelope, to full depth, on any edge
blank overhangs or sits on sacrificial material wherever the envelope
    crosses a blank edge
blank_measured.z + rests_on.thickness  under the deepest Z  >  0
```

The swept envelope is the **tool body**: programmed extents grown by the tool
radius on every side.
