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
  docs/tool_library/tool_table.json    exported by tools/live/export_tool_library.py
  docs/fixtures/*.json         named fixtures

Work offsets are NOT published. The numeric origin of a WCS stays on ned in
configs/ned5_pb/ned5_pb.var; Production names an offset and never needs to know
where it is. Which WCS is for what lives in 418ops/safety/machining-rules.md R5.
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

SP = "configs/params/spindle_0.inc"
sp = ini_values(SP)
spindle = {
    "min_rpm": num(sp["MIN_FORWARD_VELOCITY"]),
    "max_rpm": num(sp["MAX_FORWARD_VELOCITY"]),
    "max_reverse_rpm": num(sp["MAX_REVERSE_VELOCITY"]),
    "source": "ned:" + SP, "verified": verified(SP),
}

write("limits.json", {
    "machine": "ned", "units": "mm and degrees", "read_by": "Production",
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
    "joints": joints, "axes": axes, "spindle": spindle,
})

# ------------------------------------------------------------ kinematics.json
# Machining's admission check needs the tool-tip -> joint arithmetic and the
# pivot length without opening a config (handover 2026-10-01). Verified against
# linuxcnc/src/emc/kinematics/ned_ac_kins.c kinematicsInverse: joint = tip - r,
# r = s2r(L, C + azimuth_offset, 180 - tilt_sign*A).
PIV = "configs/params/head_pivot.inc"
TCP = "configs/ned5_pb/postgui_tcp.hal"
pivot = num(ini_values(PIV)["PIVOT_LENGTH"])
setp = {}
for line in open(os.path.join(NED, TCP)):
    m = re.match(r"^\s*setp\s+ned_ac_kins\.(azimuth-offset|tilt-sign)\s+(\S+)", line)
    if m:
        setp[m.group(1)] = num(m.group(2))
write("kinematics.json", {
    "machine": "ned", "units": "mm and degrees", "read_by": "Machining, Production",
    "generated_by": "ned:tools/publish_machine_facts.py",
    "module": "ned_ac_kins coordinates=XYZXAC (tool-tip programming, no G43.4; G43 must stay live)",
    "pivot_length_mm": pivot,
    "pivot_source": "ned:" + PIV, "pivot_verified": verified(PIV),
    "live_pivot": "ned_ac_kins.pivot-length = PIVOT_LENGTH + motion.tooloffset.z (postgui_tcp.hal sum2 arm)",
    "azimuth_offset_deg": setp.get("azimuth-offset"), "tilt_sign": setp.get("tilt-sign"),
    "convention_source": "ned:" + TCP, "convention_verified": verified(TCP),
    "inverse_with_azimuth_90_tilt_sign_1": [
        "L = pivot_length_mm + tool_length_z",
        "joint X = tipX + L*sin(A)*sin(C)",
        "joint Y = tipY - L*sin(A)*cos(C)",
        "joint Z = tipZ - L*(1 - cos(A))",
        "A and C joints = A and C words",
    ],
    "forward_z": "tipZ = jointZ + L*(1 - cos(A))",
    "check": "size every program against limits.json JOINT limits using these joint values; the DRO shows the tip, the limit is on the joint",
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
    "machine": "ned", "units": "mm", "read_by": "Production",
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
tt["read_by"] = "Production"
tt["source"] = "ned:" + TT
tt["verified"] = verified(TT)
tt["read_this_first"] = [
    "z_offset is MEASURED on ned: spindle nose to tool tip. Never derive a tool "
    "length from a CAM library -- on 2026-08-13 that put a tip 112.92 mm too deep "
    "on fifteen G43 lines.",
    "A tool whose z_offset is 0.0 has NOT been measured. Do not post it.",
]
write("tool_table.json", tt)
