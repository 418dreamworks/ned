# LinuxCNC Documentation (offline mirror)

Local mirror of the LinuxCNC documentation needed to build and maintain `ned`'s
HAL/INI configuration. Fetched from <https://linuxcnc.org/docs/html/> on
2026-06-18. The website is the source of truth — these copies are for offline
work on the machine and for grep-ability.

Each `.md` is a plain-text extract (stdlib HTML→Markdown) of the matching
`.html`, which is the raw downloaded page. Grep the `.md` files; open the
`.html` if a table or figure didn't survive extraction.

## `hal/` — the HAL Manual (whole section)

| File | Page |
|---|---|
| [intro.md](hal/intro.md) | What HAL is — pins, signals, components, threads |
| [basic-hal.md](hal/basic-hal.md) | `halcmd` commands: loadrt, addf, net, setp, getp |
| [tutorial.md](hal/tutorial.md) | Hands-on `halrun` tutorial (the page the build started from) |
| [general-ref.md](hal/general-ref.md) | HAL file syntax / general reference |
| [rtcomps.md](hal/rtcomps.md) | Realtime components (siggen, pid, and2, mux, etc.) |
| [components.md](hal/components.md) | Master list of all bundled HAL components |
| [canonical-devices.md](hal/canonical-devices.md) | Canonical device interfaces (digital/analog in/out, encoder) |
| [hal-examples.md](hal/hal-examples.md) | Worked HAL examples |
| [halui-examples.md](hal/halui-examples.md) | halui (user-interface) wiring examples |
| [parallel-port.md](hal/parallel-port.md) | Parallel-port driver (not used here — reference only) |
| [comp.md](hal/comp.md) | Writing your own realtime component (`.comp`) |
| [halmodule.md](hal/halmodule.md) | Writing HAL components in Python |
| [halshow.md](hal/halshow.md) | `halshow` GUI for inspecting live HAL |
| [haltcl.md](hal/haltcl.md) | HAL Tcl (`.tcl`) configs |
| [tools.md](hal/tools.md) | HAL command-line tools |
| [twopass.md](hal/twopass.md) | Two-pass HAL file processing |

## `man/` — man-page references (card-specific)

| File | Covers |
|---|---|
| [hostmot2.9.md](man/hostmot2.9.md) | The Mesa HostMot2 driver — **the authoritative pin/parameter names** for encoders, pwmgen, stepgen, sserial, gpio, watchdog. Note: the 7I97's ±10 V outputs are **`pwmgen`** instances (PWM→analog), not a dedicated "analogout" module; use `offset-mode` for bipolar ±10 V. |
| [hm2_eth.9.md](man/hm2_eth.9.md) | The `hm2_eth` Ethernet driver — `board_ip`, `config=` firmware string, how to probe a live board with `show pin`. |

## Refreshing

```bash
cd docs/linuxcnc
base=https://linuxcnc.org/docs/html
for p in intro basic-hal tutorial rtcomps general-ref components \
         canonical-devices parallel-port hal-examples comp halmodule \
         halshow haltcl halui-examples tools twopass; do
  wget -q "$base/hal/$p.html" -O "hal/$p.html"
done
# then re-run the HTML→Markdown extractor over the .html files
```
