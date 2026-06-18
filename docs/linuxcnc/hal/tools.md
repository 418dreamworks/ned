<!-- Mirror of https://linuxcnc.org/docs/html/hal/tools.html -->
<!-- LinuxCNC HAL Manual. Downloaded 2026-06-18. Source of truth is the URL above. -->

# HAL Tools



Table of Contents

**JavaScript must be enabled in your browser to display the table of contents.**





## 1. Halcmd



`halcmd` is a command line tool for manipulating the HAL. There is a rather complete man page for ``halcmd, which will be installed if you have installed LinuxCNC from either source or a package. The manpage provides usage info:





```
man halcmd
```


If you have compiled LinuxCNC for "run-in-place", you must source the rip-environment script to make the man page available:





```
cd toplevel_directory_for_rip_build
. scripts/rip-environment
man halcmd
```


The HAL Tutorial has a number of examples of halcmd usage, and is a good tutorial for `halcmd`.



## 2. Halmeter



Halmeter is a *voltmeter* for the HAL. It lets you look at a pin, signal, or parameter, and displays the current value of that item. It is pretty simple to use. Start it by typing `halmeter` in an X windows shell. Halmeter is a GUI application. It will pop up a small window, with two buttons labeled "Select" and "Exit". Exit is easy - it shuts down the program. Select pops up a larger window, with three tabs. One tab lists all the pins currently defined in the HAL. The next lists all the signals, and the last tab lists all the parameters. Click on a tab, then click on a pin/signal/parameter. Then click on "OK". The lists will disappear, and the small window will display the name and value of the selected item. The display is updated approximately 10 times per second. If you click "Accept" instead of "OK", the small window will display the name and value of the selected item, but the large window will remain on the screen. This is convenient if you want to look at a number of different items quickly.

You can have many halmeters running at the same time, if you want to monitor several items. If you want to launch a halmeter without tying up a shell window, type `halmeter &` to run it in the background. You can also make halmeter start displaying a specific item immediately, by adding `pin|sig|par[am] _<name>_` to the command line. It will display the pin, signal, or parameter *<name>* as soon as it starts - if there is no such item, it will simply start normally. And finally, if you specify an item to display, you can add `-s` before the `pin|sig|param` to tell halmeter to use a small window. The item name will be displayed in the title bar instead of under the value, and there will be no buttons. Useful when you want a lot of meters in a small amount of screen space.

Refer to Halmeter Tutorial section for more information.

`halmeter` can be loaded from a terminal or from AXIS. `halmeter` is faster than `halshow` at displaying values. `halmeter` has two windows, one to pick the pin, signal, or parameter to monitor and one that displays the value. Multiple ``halmeter``s can be open at the same time. If you use a script to open multiple ``halmeter``s you can set the position of each one with `-g X Y` relative to the upper left corner of your screen. For example:





```
loadusr halmeter pin hm2.0.stepgen.00.velocity-fb -g 0 500
```


See the man page for more options and the section Halmeter.



    Figure 1. Halmeter selection window



    Figure 2. Halmeter watch window



## 3. Halshow



`halshow` (complete usage description) can be started from the command line to show details for selected components, pins, parameters, signals, functions, and threads of a running HAL. The WATCH tab provides a continuous display of selected pin, parameters, and signal items. The File menu provides buttons to save the watch items to a watch list and to load an existing watch list. The watch list items can also be loaded automatically on startup. For command line usage:





```
halshow --help
Usage:
  halshow [Options] [watchfile]
  Options:
           --help    (this help)
           --fformat format_string_for_float
           --iformat format_string_for_int

Notes:
  Create watchfile in halshow using: 'File/Save Watch List'.
  LinuxCNC must be running for standalone usage.
```




    Figure 3. Halshow Watch Tab

A watchfile created using the *File/Save Watch List* menu item is formatted as a single line with tokens "pin+", "param+", "sig=+", followed by the appropriate pin, param, or signal name. The token-name pairs are separated by a space character.



Single Line Watchfile Example



```
pin+joint.0.pos-hard-limit pin+joint.1.pos-hard-limit sig+estop-loop
```


A watchfile created using the *File/Save Watch List (multiline)* menu item is formatted with separate lines for each item identified with token-name pairs as described above.



Separated Lines Watchfile Example



```
pin+joint.0.pos-hard-limit
pin+joint.1.pos-hard-limit
sig+estop-loop
```


When loading a watchfile with the *File/Load Watch List* menu item, the token-name pairs may appear as single or multiple lines. Blank lines and lines beginning with a # character are ignored.



## 4. Halscope



`Halscope` is an *oscilloscope* for the HAL. It lets you capture the value of pins, signals, and parameters as a function of time. Complete operating instructions should be located here eventually. For now, refer to section  Halscope in the tutorial chapter, which explains the basics.

The halscope "File" menu selector provides buttons to save a configuration or open a previously saved configuration. When halscope is terminated, the last configuration is saved in a file named autosave.halscope.

Configuration files may also be specified when starting halscope from the commandline. Commandline help (`-h`) usage:





```
halscope -h
Usage:
  halscope [-h] [-i infile] [-o outfile] [num_samples]
```




## 5. Sim Pin



sim_pin is a command line utility to display and update any number of writable pins, parameters or signals.



sim_pin Usage



```
Usage:
        sim_pin [Options] name1 [name2 ...] &

Options:
        --help                (this text)
        --title title_string  (window title, default: sim_pin)

Note:  LinuxCNC (or a standalone HAL application) must be running
        A named item can specify a pin, param, or signal
        The item must be writable, e.g.:
          pin:    IN or I/O (and not connected to a signal with a writer)
          param:  RW
          signal: connected to a writable pin

        HAL item types bit,s32,u32,float are supported.

        When a bit item is specified, a pushbutton is created
        to manage the item in one of three manners specified
        by radio buttons:
            toggle: Toggle value when button pressed
            pulse:  Pulse item to 1 once when button pressed
            hold:   Set to 1 while button pressed
        The bit pushbutton mode can be specified on the command
        line by formatting the item name:
            namei/mode=[toggle | pulse | hold]
        If the mode begins with an uppercase letter, the radio
        buttons for selecting other modes are not shown
```


For complete information, see the man page:





```
man sim_pin
```




sim_pin Example (with LinuxCNC running)



```
halcmd loadrt mux2 names=example; halcmd net sig_example example.in0
sim_pin example.sel example.in1 sig_example &
```




    Figure 4. sim_pin Window



## 6. Simulate Probe



`simulate_probe` is a simple GUI to simulate activation of the pin motion.probe-input. Usage:





```
simulate_probe &
```




    Figure 5. simulate_probe Window



## 7. HAL Histogram



`hal-histogram` is a command line utility to display histograms for HAL pins.



Usage:



```
   hal-histogram --help | -?
or
   hal-histogram [Options] [pinname]
```


  Table 1. Options:
|  Option      |  Value     |  Description |
|

--minvalue |

minvalue |

minimum bin, default: 0 |
|

--binsize |

binsize |

binsize, default: 100 |
|

--nbins |

nbins |

number of bins, default: 50 |
|

 |

 |

 |
|

--logscale |

0/1 |

y axis log scale, default: 1 |
|

--text |

note |

text display, default: "" |
|

--show |

 |

show count of undisplayed nbins, default off |
|

--verbose |

 |

progress and debug, default off |

Notes:

1.

 LinuxCNC (or another HAL application) must be running.
1.

 If no pinname is specified, default is: `motion-command-handler.time`.
1.

 This app may be opened for 5 pins.
1.

 Pintypes float, s32, u32, bit are supported.
1.

 The pin must be associated with a thread supporting floating point. For a base thread, this may require using `loadrt motmod ... base_thread_fp=1` .



    Figure 6. hal-histogram Window



## 8. Halreport



`halreport` is a command-line utility that generates a report about HAL connections for a running LinuxCNC (or other HAL) application. The report shows all signal connections and flags potential problems. Information included:


1.

 System description and kernel version.
1.

 Signals and all connected output, io, and input pins.
1.

 Each pin’s component_function, thread, and addf-order.
1.

 Non-realtime component pins having non-ordered functions.
1.

 Identification of unknown functions for unhandled components.
1.

 Signals   with no output.
1.

 Signals   with no inputs.
1.

 Functions with no addf.
1.

 Warning tags for components marked as deprecated/obsolete in docs.
1.

 Real names for pins that use alias names.

The report can be generated from the command line and directed to an output file (or stdout if no outfilename is specified):



halreport Usage



```
Usage:
  halreport -h | --help (this help)
or
  halreport [outfilename]
```


To generate the report for every LinuxCNC startup, include halreport and an output filename as an [APPLICATIONS]APP entry in the INI file.



halreport Example



```
[APPLICATIONS]
APP = halreport /tmp/halreport.txt
```


The function addf-ordering can be important for servo loops where the sequence of the functions computed at each servo period is important. Typically, the order is:


1.

 Read input pins,
1.

 do the motion command-handler and motion-controller functions,
1.

 perform pid calculations, and finally
1.

 write output pins.

For each signal in a critical path, the addf-order of the output pin should be numerically lower than the addf-order of the critical input pins that it connects to.

For routine signal paths that handle switch inputs, non-realtime pins, etc., the addf-ordering is often not critical. Moreover, the timing of non-realtime pin value changes cannot be controlled or guaranteed at the intervals typically employed for HAL threads.

Example report file excerpts showing a pid loop for a hostmot2 stepgen operated in velocity mode on a trivkins machine with `joint.0` corresponding to the X axis coordinate:





```
SIG:    pos-fb-0
  OUT:    h.00.position-fb                     hm2_7i92.0.read        servo-thread 001
          (=hm2_7i92.0.stepgen.00.position-fb)
    IN:     X_pid.feedback                     X_pid.do-pid-calcs     servo-thread 004
    IN:     joint.0.motor-pos-fb               motion-command-handler servo-thread 002
            ....................               motion-controller      servo-thread 003
...
SIG:    pos-cmd-0
  OUT:    joint.0.motor-pos-cmd                motion-command-handler servo-thread 002
          .....................                motion-controller      servo-thread 003
    IN:     X_pid.command                      X_pid.do-pid-calcs     servo-thread 004
...
SIG:    motor-cmd-0
  OUT:    X_pid.output                         X_pid.do-pid-calcs     servo-thread 004
    IN:     h.00.velocity-cmd                  hm2_7i92.0.write       servo-thread 008
            (=hm2_7i92.0.stepgen.00.velocity-cmd)
```


In the example above, the HALFILE uses halcmd aliases to simplify pin names for an hostmot2 FPGA board with commands like:





```
alias pin hm2_7i92.0.stepgen.00.position-fb h.00.position-fb
```



|

Note  |

Questionable component function detection may occur for


1.

 unsupported (deprecated) components,
1.

 user-created components that use multiple functions or unconventional function naming, or
1.

 GUI-created non-realtime components that lack distinguishing characteristics such as a prefix based on the GUI program name.

Questionable functions are tagged with a question mark "?".  |


|

Note  |  Component pins that cannot be associated with a known thread function report the function as "Unknown". |

`halreport` generates a connections report (without pin types, and current values) for a running HAL application to aid in designing and verifying connections. This helps with the understanding what the source of a pin value is. Use this information with applications like `halshow`, `halmeter`, `halscope` or the  `halcmd  show` command in a terminal.





 Last updated 2025-12-15 07:42:37 MST
