# ned tool table <-> Fusion 360 tool library

Fusion stores a library as a `.tools` file: JSON, one object per tool, with a
`geometry` block whose keys are Autodesk's parameter codes. Those codes are
the stable part of the format and are what this mapping keys on.

The codes below are the ones this project's own schema already cites --
`tool_lathe` carries `-- SIG`, `-- LCF/LB`, `-- SFDM` in its DDL, written
before this document existed. Nothing here was invented for the mapping.

## Where the data is

| file | what it is |
|---|---|
| `docs/tool_library/tool_table.csv` | flat export, one row per tool, operator-facing headers |
| `docs/tool_library/tool_table.json` | same rows plus a `columns` block giving every field's label, type, unit, default and meaning |
| `configs/ned5_pb/tool_table.db` | the live database. SQLite, **WAL mode** |
| `tools/live/export_tool_library.py` | regenerates both exports from the database |

**Read the exports, not the `.db`.** The database is in WAL mode, so its main
file's bytes go stale silently -- committed rows sit in the `-wal` sidecar
until a checkpoint, and the main file's mtime never moves. The exporter reads
through a read-only connection, which does see committed WAL content, so the
CSV and JSON are current whenever they were last generated. Re-run the
exporter after any table edit.

## Columns, as they read on the TOOL tab

| column | field | unit | measured or catalogue | meaning |
|---|---|---|---|---|
| TOOL | `tool_no` | — | — | LinuxCNC tool number |
| P | `pocket` | — | operator | assigned home fork. **Never written by the machine** |
| Z OFFSET | `z_offset` | mm | **measured** | spindle nose to tool tip |
| DIAMETER MM | `diameter` | mm | catalogue | cutting diameter |
| DIAMETER IN | — | in | derived | display only, 2 dp, from DIAMETER MM. Not stored |
| FLUTES | `flutes` | — | catalogue | number of flutes, default 2 |
| DOC | `flute_depth` | mm | catalogue | length of cut, tip to the top of the flutes |
| OFFSET | `probe_offset` | mm | **machine** | probing step, 0 or negative. Never leaves this machine |
| SHOULDER | `shoulder` | mm | **measured** | stickout below the collet nut |
| SHANK IN | `shank_dia` | **in** | catalogue | shank diameter, in inches on this table |
| OAL | `oal` | mm | catalogue | overall length |
| SHOULDER DIA | `shoulder_dia` | — | operator | ER collet size as a LABEL, not a number |
| NOTES | `notes` | — | operator | free text, goes nowhere else |
| REMARK | `remark` | — | catalogue | short label, hard-capped at 10 characters |
| LOC | `pocket` (derived) | — | machine | hidden from view, still used by the ATC: 0 = spindle, 1..N = fork, -1 = table |

## Geometry mapping

| ned column | Fusion `geometry` key | note |
|---|---|---|
| `diameter` — DIAMETER MM | `DC` | cutting diameter |
| `flute_depth` — DOC | `LCF` | length of cut |
| `shank_dia` — SHANK IN | `SFDM` | **ned stores INCHES, Fusion expects mm** -- convert |
| `flutes` — FLUTES | `NOF` | |
| `oal` — OAL | `OAL` | overall length |
| `z_offset` — Z OFFSET | — | measured on THIS machine; not a library value |
| `shoulder` — SHOULDER | — | measured; see below |
| `shoulder_dia` — SHOULDER DIA | — | holder, not tool |
| `probe_offset` — OFFSET | — | machine-specific probing move, never leaves here |

`BODY LEN` / `LB` **was deleted from this table** (2026-08-13). If a Fusion
library carries `LB`, there is nowhere on this side to put it.

## Identity

| ned | Fusion |
|---|---|
| `tool_no` | `post-process.number` |
| `remark` | `description` -- 10 characters maximum here, so Fusion descriptions truncate on import |
| `notes` | — |
| — | `product-id`, `vendor` -- library identity, no home here yet |

## SHOULDER DIA is an ER label, not a diameter

The cell holds one of exactly four strings, picked from a drop-down:

    ER11-20    ER16-28    ER20-34    ER32-51

The trailing number is the collet nut's diameter in millimetres -- ER16-28 is
a 28 mm nut. It describes the HOLDER, not the tool, and it is what decides how
far the spindle steps sideways during a shoulder probe. **Only the operator
writes it.** No routine on this machine may set it.

## How SHOULDER is produced

Both probes measure from the spindle nose, because that is the only face the
machine can locate with no tool fitted:

    tool length   = |#3010 + probed tip Z - starting Z|      -> Z OFFSET
    nose to nut   = |#3010 + probed nut Z - starting Z|      -> #3100
    SHOULDER      = Z OFFSET - #3100

`#3010` is the bare spindle nose's trip height against the toolsetter. The
formula cancels, so neither probe cares which work coordinate system is
active.

Special case: when the cutter is at least as wide as the collet nut, the nut
can never touch the work before the cutter body does. `measure_shoulder.ngc`
then writes `#3100 = -1` -- a sentinel, because 0 means "never measured" --
skips the probe entirely, moves nothing, and SHOULDER becomes the whole tool
length. The tool is treated as a solid shaft at cutting diameter all the way
to the nose.

`OAL - SHOULDER` is the collet engagement: how much shank is inside the
collet. It is the only use for OAL on this machine.

## Which side owns what

MEASURED values belong to the machine and must never be overwritten by an
import: `z_offset`, `shoulder`, `probe_offset`. They describe this spindle
and this toolsetter.

OPERATOR values belong to the person and must never be written by code:
`pocket` (P), `shoulder_dia`, `notes`.

CATALOGUE values belong to the library and should be imported: `diameter`,
`flute_depth`, `shank_dia`, `flutes`, `oal`, `remark`.

A sync that ignores the first split will silently replace a measured tool
length with a nominal one, and the first cut after it will be wrong by the
difference. A sync that ignores the second will destroy the operator's rack
assignments -- which has already happened once, on 2026-08-13, when a
synthetic `P0` from LinuxCNC's spindle convention was written back over a
real home fork.
