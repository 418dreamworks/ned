#!/bin/bash
# Extract a page range from programming_tagged.txt
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
  ' programming_tagged.txt > "$out"
}

cd "$(dirname "$0")"
extract 1 26     pg_ch00_frontmatter.txt
extract 27 32    pg_ch01_general_concepts.txt
extract 33 36    pg_ch02_creating_program.txt
extract 37 52    pg_ch03_axes_coords.txt
extract 53 60    pg_ch04_reference_systems.txt
extract 61 80    pg_ch05_iso_code.txt
extract 81 104   pg_ch06_path_control.txt
extract 105 127  pg_ch07_additional_prep.txt
extract 128 143  pg_ch08_tool_comp.txt
extract 144 200  pg_ch09_canned_cycles.txt
extract 201 219  pg_ch10_multiple_machining.txt
extract 220 280  pg_ch11_irregular_pocket.txt
extract 281 331  pg_ch12_probing.txt
extract 332 384  pg_ch13_high_level_lang.txt
extract 385 410  pg_ch14_program_control.txt
extract 411 432  pg_ch15_coord_transform.txt
extract 433 467  pg_ch16_angular_transform.txt

wc -l pg_*.txt
