#!/bin/bash
# Extract a page range from tagged.txt
# Usage: ./split_chapters.sh START END OUTFILE
extract() {
  local start=$1
  local end=$2
  local out=$3
  awk -v s=$start -v e=$end '
    /^===== PAGE [0-9]+/ {
      match($0, /[0-9]+/)
      p = substr($0, RSTART, RLENGTH) + 0
      printing = (p >= s && p <= e)
    }
    printing { print }
  ' tagged.txt > "$out"
}

cd "$(dirname "$0")"
extract 1 26   ch00_frontmatter.txt
extract 27 72  ch01_8055_config.txt
extract 73 107 ch02_8055i_config.txt
extract 108 112 ch03_heat.txt
extract 113 130 ch04_remote_modules.txt
extract 131 144 ch05_machine_power.txt
extract 145 283 ch06_machine_parameters.txt
extract 284 411 ch07_concepts.txt
extract 412 420 ch08_plc_intro.txt
extract 421 441 ch09_plc_resources.txt
extract 442 459 ch10_plc_programming.txt
extract 460 471 ch11_cnc_plc_comm.txt
extract 472 510 ch12_logic_io.txt
extract 511 557 ch13_internal_vars.txt
extract 558 569 ch14_axes_from_plc.txt
extract 570 584 ch15_custom_screens.txt
extract 585 607 ch16_config_workmode.txt
extract 608 620 ch17_plc_example.txt
extract 621 706 appendix.txt

wc -l ch*.txt appendix.txt
