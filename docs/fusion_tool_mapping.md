# ned tool table <-> Fusion 360 tool library

Fusion stores a library as a `.tools` file: JSON, one object per tool, with a
`geometry` block whose keys are Autodesk's parameter codes. Those codes are
the stable part of the format and are what this mapping keys on.

The codes below are the ones this project's own schema already cites --
`tool_lathe` carries `-- SIG`, `-- LCF/LB`, `-- SFDM` in its DDL, written
before this document existed. Nothing here was invented for the mapping.

## Geometry

| ned column | Fusion `geometry` key | meaning |
|---|---|---|
| `diameter` (core) | `DC` | cutting diameter |
| `flute_depth` — FLUTE DOC | `LCF` | length of cut, tip to the top of the flutes |
| `body_len` — BODY LEN | `LB` | body length, tip to where the shank begins |
| `shank_dia` — SHANK DIA | `SFDM` | shank diameter |
| `flutes` — FLUTES | `NOF` | number of flutes |
| `z_offset` (core) | — | measured on THIS machine; not a library value |
| `shoulder` — SHOULDER | — | measured; the underside of the collet nut or shank step |
| `er_size` — ER | — | holder, not tool; sets the nut diameter used by MEASURE SHOULDER |
| `probe_offset` — OFFSET | — | machine-specific probing move, never leaves here |

`LB` matters only when the cutting diameter is smaller than the shank: it is
the length over which `DC` applies before the tool steps out to `SFDM`. When
the tool is a plain end mill, `LB` and `LCF` are the same number.

## Identity

| ned | Fusion |
|---|---|
| `tool_no` | `post-process.number` |
| `remark` | `description` |
| — | `product-id`, `vendor` — library identity, no home here yet |

## Which side owns what

MEASURED values belong to the machine and must never be overwritten by an
import: `z_offset`, `shoulder`, `probe_offset`. They describe this spindle
and this toolsetter.

CATALOGUE values belong to the library and should be imported: `diameter`,
`flute_depth`, `body_len`, `shank_dia`, `flutes`, `remark`.

A sync that ignores that split will silently replace a measured tool length
with a nominal one, and the first cut after it will be wrong by the
difference.
