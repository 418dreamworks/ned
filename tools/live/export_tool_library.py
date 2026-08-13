#!/usr/bin/env python3
"""Export ned's tool table to readable, self-describing files.

WHY THIS EXISTS: the tool table lives in configs/ned5_pb/tool_table.db, a
SQLite database in WAL mode. Two problems for anyone outside this machine:

  1. WAL. The main .db file's bytes go stale silently -- committed rows sit
     in the -wal sidecar until a checkpoint, and the main file's mtime never
     moves. A git commit of the .db alone can therefore ship an old table
     with no sign that anything is wrong.
  2. It is binary, and the column MEANINGS are not in it in any usable form.
     Labels and units live in custom_field_def; the rules about which
     columns are measured on this machine and which come from a catalogue
     live only in docs/fusion_tool_mapping.md.

This reads through a READ-ONLY URI connection, which sees committed WAL
content, so the export is current even when the .db bytes are not. Nothing
here writes to the database.

    tools/live/export_tool_library.py [--out docs/tool_library]

Writes tool_table.csv (flat, one row per tool) and tool_table.json (same
data plus a `columns` block, so the file explains itself).
"""
import csv
import json
import os
import sqlite3
import sys

NED = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(NED, 'configs', 'ned5_pb', 'tool_table.db')

# The core columns are LinuxCNC's own and carry no custom_field_def row, so
# their labels are stated here -- they are the operator-facing headers as
# they read on the TOOL tab, not the database's own names.
CORE = [
    ('tool_no',   'TOOL',        'int',   None, 'LinuxCNC tool number'),
    ('pocket',    'P',           'int',   None,
     "operator's assigned home fork. Never written by the machine"),
    ('z_offset',  'Z OFFSET',    'float', 'mm',
     'MEASURED on this machine: spindle nose to tool tip'),
    ('diameter',  'DIAMETER MM', 'float', 'mm', 'cutting diameter'),
    ('remark',    'REMARK',      'text',  None,
     'short label, hard-capped at 10 characters'),
]
# Shown on the TOOL tab but not stored: derived for display only.
DERIVED = [
    ('diameter_in', 'DIAMETER IN', 'float', 'in',
     'display only, 2 dp -- derived from DIAMETER MM, never stored'),
]
SKIP_FIELDS = ('safety_x', 'safety_y')   # defined, never populated, not shown


def read(db=DB):
    con = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
    try:
        defs = [dict(zip(('id', 'name', 'label', 'type', 'unit', 'default',
                          'order'), r))
                for r in con.execute(
                    'SELECT id, name, label, value_type, unit, default_value,'
                    ' display_order FROM custom_field_def'
                    ' ORDER BY COALESCE(display_order, 999), id')
                if r[1] not in SKIP_FIELDS]

        tools = []
        for row in con.execute(
                'SELECT id, tool_no, pocket, z_offset, diameter, remark,'
                ' in_use FROM tool ORDER BY tool_no'):
            tid, tno, pocket, z, dia, remark, in_use = row
            t = {'tool_no': tno, 'pocket': pocket, 'z_offset': z,
                 'diameter': dia, 'remark': remark or '',
                 'diameter_in': round(dia / 25.4, 4) if dia else 0.0,
                 'in_spindle': bool(in_use)}
            vals = dict(con.execute(
                'SELECT f.name, v.value FROM custom_field_value v'
                '  JOIN custom_field_def f ON f.id = v.field_id'
                ' WHERE v.tool_id = ?', (tid,)))
            for d in defs:
                raw = vals.get(d['name'])
                if raw in (None, ''):
                    t[d['name']] = None
                elif d['type'] == 'int':
                    t[d['name']] = int(float(raw))
                elif d['type'] == 'float':
                    t[d['name']] = float(raw)
                else:
                    t[d['name']] = raw
            tools.append(t)
        return defs, tools
    finally:
        con.close()


def columns(defs):
    cols = []
    for name, label, typ, unit, note in CORE:
        cols.append({'field': name, 'label': label, 'type': typ,
                     'unit': unit, 'default': None, 'note': note})
    for name, label, typ, unit, note in DERIVED:
        cols.append({'field': name, 'label': label, 'type': typ,
                     'unit': unit, 'default': None, 'note': note})
    for d in defs:
        cols.append({'field': d['name'], 'label': d['label'],
                     'type': d['type'], 'unit': d['unit'],
                     'default': d['default'], 'note': NOTES.get(d['name'], '')})
    return cols


# One line per custom field explaining what it is FOR. These cannot be
# derived from the schema and are the whole reason this file exists.
NOTES = {
    'flutes': 'number of flutes',
    'flute_depth': 'length of cut, tip to the top of the flutes',
    'probe_offset':
        'machine-specific probing step, 0 or negative. Never leaves this machine',
    'shoulder':
        'MEASURED: stickout below the collet nut = Z OFFSET minus the probed '
        'nose-to-nut distance. How deep the tool can go before the nut hits',
    'shank_dia': 'shank diameter, IN INCHES on this table',
    'oal': 'overall length, from the catalogue. OAL minus SHOULDER = collet engagement',
    'shoulder_dia':
        'ER collet size as a label (ER11-20 / ER16-28 / ER20-34 / ER32-51); '
        'the trailing number is the nut diameter in mm. A property of the '
        'HOLDER, not the tool. Operator-set only -- no code writes it',
    'notes': "operator's own free text. Goes nowhere else",
}


def main(argv):
    out = os.path.join(NED, 'docs', 'tool_library')
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    os.makedirs(out, exist_ok=True)
    defs, tools = read()
    cols = columns(defs)
    order = [c['field'] for c in cols] + ['in_spindle']

    csv_path = os.path.join(out, 'tool_table.csv')
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([c['label'] for c in cols] + ['IN SPINDLE'])
        for t in tools:
            w.writerow(['' if t.get(k) is None else t.get(k) for k in order])

    json_path = os.path.join(out, 'tool_table.json')
    with open(json_path, 'w') as f:
        json.dump({
            'source': 'configs/ned5_pb/tool_table.db',
            'machine': 'ned',
            'units': 'mm unless a column says otherwise (SHANK IN and '
                     'DIAMETER IN are inches)',
            'generated_by': 'tools/live/export_tool_library.py',
            'columns': cols,
            'tools': tools,
        }, f, indent=2)
        f.write('\n')

    print('%d tool(s), %d column(s)' % (len(tools), len(cols)))
    print(csv_path)
    print(json_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
