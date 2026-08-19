#!/usr/bin/env python3
"""Publish ned's machine facts to ~/418ops/machine/ per contracts/machine-facts.md.

Nothing here is hand-typed. Every number is read out of the file that owns it
and carries that file's path and mtime, so a stale fact is visible as a stale
date rather than believed.

    python3 tools/publish_machine_facts.py [--dry-run]

Sources:
  configs/params/joint_*.inc   joint travel and maxima (the real stops)
  configs/params/axis_*.inc    axis soft limits (DISABLED -- see limits.json)
  configs/ned5_pb/ned5_pb_ab_gen.ini   B axis / JOINT_6
  configs/ned5_pb/ned5_pb.var  work offsets, written by LinuxCNC at shutdown
  docs/tool_library/tool_table.json    exported by tools/live/export_tool_library.py
  docs/fixtures/*.json         named fixtures
"""
import json, os, re, sys, hashlib, datetime

NED = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.expanduser("~/418ops/machine")
DRY = "--dry-run" in sys.argv


def verified(relpath):
    """ISO date this source file was last written -- when the value was last true."""
    p = os.path.join(NED, relpath)
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds")


def ini_values(relpath, section=None):
    """KEY = VALUE pairs, comments stripped. section=None reads a bare .inc body."""
    out, cur = {}, None
    for line in open(os.path.join(NED, relpath)):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\[(\w+)\]$", line)
        if m:
            cur = m.group(1)
            continue
        if section is not None and cur != section:
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def num(s):
    f = float(s)
    return int(f) if f == int(f) else f


def var_file(relpath):
    """LinuxCNC .var -- '<number> <value>' per line."""
    out = {}
    for line in open(os.path.join(NED, relpath)):
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            out[int(parts[0])] = float(parts[1])
    return out


def write(name, obj):
    body = json.dumps(obj, indent=2) + "\n"
    path = os.path.join(OUT, name)
    if not DRY:
        os.makedirs(OUT, exist_ok=True)
        open(path, "w").write(body)
    print("%-22s %s  %s" % (name, hashlib.md5(body.encode()).hexdigest(), path))


# ---------------------------------------------------------------- limits.json
JOINTS = [
    ("X", "joint_x1.inc", "JOINT_0", "gantry left"),
    ("X", "joint_x2.inc", "JOINT_3", "gantry right"),
    ("Y", "joint_y.inc",  "JOINT_1", None),
    ("Z", "joint_z.inc",  "JOINT_2", None),
    ("A", "joint_a.inc",  "JOINT_4", "swivel-head TILT about X"),
    ("C", "joint_c.inc",  "JOINT_5", "swivel-head SPIN about Z"),
]
AXES = [("X", "axis_x.inc"), ("Y", "axis_y.inc"), ("Z", "axis_z.inc"),
        ("A", "axis_a.inc"), ("C", "axis_c.inc")]

joints = []
for letter, inc, jnum, note in JOINTS:
    v = ini_values("configs/params/" + inc)
    j = {
        "axis": letter, "joint": jnum,
        "min_limit": num(v["MIN_LIMIT"]), "max_limit": num(v["MAX_LIMIT"]),
        "max_velocity": num(v["MAX_VELOCITY"]),
        "max_acceleration": num(v["MAX_ACCELERATION"]),
        "source": "ned:configs/params/" + inc, "verified": verified("configs/params/" + inc),
    }
    if note:
        j["note"] = note
    joints.append(j)

axes = []
for letter, inc in AXES:
    v = ini_values("configs/params/" + inc)
    axes.append({
        "axis": letter, "enforced": False,
        "min_limit": num(v["MIN_LIMIT"]), "max_limit": num(v["MAX_LIMIT"]),
        "max_velocity": num(v["MAX_VELOCITY"]),
        "max_acceleration": num(v["MAX_ACCELERATION"]),
        "source": "ned:configs/params/" + inc, "verified": verified("configs/params/" + inc),
    })

AB = "configs/ned5_pb/ned5_pb_ab_gen.ini"
b_axis, b_joint = ini_values(AB, "AXIS_B"), ini_values(AB, "JOINT_6")
axes.append({
    "axis": "B", "enforced": False,
    "min_limit": num(b_axis["MIN_LIMIT"]), "max_limit": num(b_axis["MAX_LIMIT"]),
    "max_velocity": num(b_axis["MAX_VELOCITY"]),
    "max_acceleration": num(b_axis["MAX_ACCELERATION"]),
    "source": "ned:" + AB + " [AXIS_B]", "verified": verified(AB),
})
joints.append({
    "axis": "B", "joint": "JOINT_6",
    "min_limit": num(b_joint["MIN_LIMIT"]), "max_limit": num(b_joint["MAX_LIMIT"]),
    "max_velocity": num(b_joint["MAX_VELOCITY"]),
    "max_acceleration": num(b_joint["MAX_ACCELERATION"]),
    "note": "continuous rotary, self-locking worm, no travel limit",
    "source": "ned:" + AB + " [JOINT_6]", "verified": verified(AB),
})

write("limits.json", {
    "machine": "ned", "units": "mm and degrees",
    "generated_by": "ned:tools/publish_machine_facts.py",
    "read_this_first": [
        "The JOINT limits are the real stops. Size any program against those.",
        "The AXIS soft limits are DISABLED (enforced=false, deliberately huge). "
        "An axis limit bounds the TOOL TIP, not the carriage; under ned_ac_kins "
        "the tip sits up to L*(1-cos A) above the joint, so a joint-sized number "
        "there refused most of Z. Operator disabled them 2026-08-07.",
        "A and C soft limits are enforced by LinuxCNC only AFTER homing, and are "
        "absolute only if home was set to the true head angle.",
        "X is a gantry: JOINT_0 and JOINT_3 move together and home only as a "
        "synchronized pair.",
    ],
    "kinematics": "ned_ac_kins -- 5 axis, A tilt about X, C spin about Z, plus an "
                  "independent B rotary on JOINT_6",
    "joints": joints, "axes": axes,
})

# --------------------------------------------------------- work_offsets.json
VAR = "configs/ned5_pb/ned5_pb.var"
v = var_file(VAR)
NAMES = [("G54", 5221), ("G55", 5241), ("G56", 5261), ("G57", 5281),
         ("G58", 5301), ("G59", 5321), ("G59.1", 5341), ("G59.2", 5361), ("G59.3", 5381)]
PURPOSE = {
    "G54": "the operator's manual jogging space. Holds whatever was last set by "
           "hand. Flat work may legitimately use it; a rotary setup must not.",
    "G55": "the rotary work offset. A rotary program on G54 runs against whatever "
           "the operator last jogged.",
}
zj = next(j for j in joints if j["axis"] == "Z")
z_min, z_max = zj["min_limit"], zj["max_limit"]

offsets = []
for name, base in NAMES:
    xyz = [v.get(base + i, 0.0) for i in range(3)]
    rec = {"name": name, "x": xyz[0], "y": xyz[1], "z": xyz[2],
           "a": v.get(base + 3, 0.0), "b": v.get(base + 4, 0.0), "c": v.get(base + 5, 0.0),
           "set": any(abs(n) > 0 for n in xyz)}
    if name in PURPOSE:
        rec["purpose"] = PURPOSE[name]
    if rec["set"]:
        # Where does this offset's Z0 sit relative to the Z joint travel?
        rec["z0_in_machine_z"] = xyz[2]
        rec["z0_reachable"] = z_min <= xyz[2] <= z_max
        if not rec["z0_reachable"]:
            rec["z0_note"] = ("Z0 of %s is %.3f mm below the Z joint travel minimum "
                              "%.3f. Any G-code that commands Z0 in %s is out of "
                              "travel." % (name, z_min - xyz[2], z_min, name))
    offsets.append(rec)

write("work_offsets.json", {
    "machine": "ned", "units": "mm and degrees",
    "frame": "machine coordinates, relative to the physically homed position",
    "generated_by": "ned:tools/publish_machine_facts.py",
    "source": "ned:" + VAR, "verified": verified(VAR),
    "read_this_first": [
        "These are the values LinuxCNC last wrote to its var file, at the last "
        "clean shutdown. They mean nothing unless the machine has been PHYSICALLY "
        "homed -- every launch declares home wherever the machine is sitting.",
        "Machining republishes after any home, re-set or re-measure. If the "
        "verified date is older than the last home, ask before using it.",
        "G92 offsets are #5211-#5219; G92 is active only when #5210 is 1.",
    ],
    "g92_active": bool(v.get(5210, 0.0)),
    "g92": [v.get(5211 + i, 0.0) for i in range(9)],
    "active_at_last_shutdown": NAMES[int(v.get(5220, 1.0)) - 1][0],
    "offsets": offsets,
})

# ------------------------------------------------------------ fixtures.json
FIXDIR = "docs/fixtures"
fixtures = []
for fn in sorted(os.listdir(os.path.join(NED, FIXDIR))):
    if not fn.endswith(".json"):
        continue
    rel = FIXDIR + "/" + fn
    rec = json.load(open(os.path.join(NED, rel)))
    rec["source"] = "ned:" + rel
    rec["verified"] = verified(rel)
    rec["setup_record"] = None
    rec["setup_record_note"] = (
        "No measured setup record exists for this fixture. safety/machining-rules.md "
        "R2 refuses a program whose workholding has no such record. Schema: "
        "ned:docs/fixtures/SETUP-RECORD-SCHEMA.md")
    fixtures.append(rec)

write("fixtures.json", {
    "machine": "ned", "units": "mm",
    "generated_by": "ned:tools/publish_machine_facts.py",
    "read_this_first": [
        "A fixture record is geometry -- what bolts to what. It is NOT a setup "
        "record. A setup record is how one blank was actually held for one job, "
        "measured and dated, and it is what R2 requires before a program runs.",
    ],
    "fixtures": fixtures,
})

# ----------------------------------------------------------- tool_table.json
TT = "docs/tool_library/tool_table.json"
tt = json.load(open(os.path.join(NED, TT)))
tt["source"] = "ned:" + TT
tt["verified"] = verified(TT)
tt["read_this_first"] = [
    "z_offset is MEASURED on ned: spindle nose to tool tip. Never derive a tool "
    "length from a CAM library -- on 2026-08-13 that put a tip 112.92 mm too deep "
    "on fifteen G43 lines.",
    "A tool whose z_offset is 0.0 has NOT been measured. Do not post it.",
]
write("tool_table.json", tt)
