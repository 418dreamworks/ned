#!/bin/bash
# Extract a page range from operating_tagged.txt
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
  ' operating_tagged.txt > "$out"
}

cd "$(dirname "$0")"
extract 1 25    op_ch00_frontmatter.txt
extract 26 35   op_ch01_general_concepts.txt
extract 36 43   op_ch02_operating_modes.txt
extract 44 52   op_ch03_ethernet.txt
extract 53 83   op_ch04_execute_simulate.txt
extract 84 116  op_ch05_edit.txt
extract 117 128 op_ch06_jog.txt
extract 129 137 op_ch07_tables.txt
extract 138 151 op_ch08_utilities.txt
extract 152 161 op_ch09_status.txt
extract 162 192 op_ch10_plc.txt
extract 193 207 op_ch11_screen_editor.txt
extract 208 215 op_ch12_machine_params.txt
extract 216 234 op_ch13_diagnosis.txt
extract 235 246 op_ch14_telediagnosis.txt

wc -l op_*.txt
