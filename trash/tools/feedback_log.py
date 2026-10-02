#!/usr/bin/env python3
"""The operator feedback log. His words, the file, the material, the tool, the
machine as it stood -- and the number his words became.

Operator 2026-09-29: "i want to build a history of my comments so that we can
fix file, material and we know the tools used, and you know the machine state."

WHY IT IS A TOOL AND NOT A DOC. Every field except his comment and the
material is readable from the machine, and every one of them was got wrong by
hand at least once today: T12's diameter (6.35 when it was 6.00), T14's flute
count (reported absent when it was stored), the published tool table (six
weeks stale), the Z floor (quoted from the ini, not the live pin). A log whose
facts are typed is a log that disagrees with the machine by the end of the
week. This reads them at the moment the comment is made.

    tools/feedback_log.py add "his words, verbatim" \
        --program <path.ngc> --material "white oak" \
        --became "swarf entry F3600 -> F1800, 0.0500 mm/tooth" \
        --topic feed

    tools/feedback_log.py render          # rewrite docs/operator_feedback.md
    tools/feedback_log.py show --topic feed --tool 12

STORE: docs/operator_feedback.jsonl, one JSON object per line, append only.
RENDER: docs/operator_feedback.md, regenerated, never hand-edited.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

NED = "/home/brains/Documents/ned"
STORE = os.path.join(NED, "docs/operator_feedback.jsonl")
RENDER = os.path.join(NED, "docs/operator_feedback.md")
TOOLDB = os.path.join(NED, "configs/ned5_pb/tool_table.db")

TOPICS = ("feed", "speed", "geometry", "tool", "fixture", "safety",
          "structure", "gui", "process", "other")


def machine_state():
    """What the machine says about itself RIGHT NOW. Never typed by hand."""
    st = {"read": "live"}
    try:
        import linuxcnc
        s = linuxcnc.stat()
        s.poll()
        st.update({
            "running_file": os.path.basename(s.file) if s.file else None,
            "interp": {1: "IDLE", 2: "RUNNING", 3: "PAUSED",
                       4: "WAITING"}.get(s.interp_state, s.interp_state),
            "current_line": s.current_line,
            "tool_in_spindle": s.tool_in_spindle,
            "tool_offset_z": round(s.tool_offset[2], 4),
            "g5x": [round(v, 4) for v in s.g5x_offset[:3]],
            "homed": list(s.homed)[:6],
            "task_state": s.task_state,
        })
    except Exception as e:                      # LinuxCNC down is a FACT, not an error
        st.update({"read": "LinuxCNC not running", "error": str(e)[:120]})
    try:
        out = subprocess.run(
            ["halcmd", "-s", "show", "pin", "arm.out"],
            capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"(-?[\d.]+)\s+arm\.out", out)
        if m:
            st["pivot_arm"] = float(m.group(1))
    except Exception:
        pass
    return st


def tool_facts(tno):
    """Diameter, flutes and measured length, out of ned's own table."""
    if tno is None:
        return None
    try:
        import sqlite3
        c = sqlite3.connect("file:%s?mode=ro" % TOOLDB, uri=True)
        row = c.execute("select id,tool_no,z_offset,diameter,remark "
                        "from tool where tool_no=?", (tno,)).fetchone()
        if not row:
            return {"tool_no": tno, "note": "not in ned's tool table"}
        tid = row[0]
        fld = {r[0]: r[1] for r in c.execute("select id,name from custom_field_def")}
        cf = {fld.get(f): v for t, f, v in
              c.execute("select tool_id,field_id,value from custom_field_value")
              if t == tid}
        return {"tool_no": row[1], "z_offset": row[2], "diameter": row[3],
                "remark": row[4], "flutes": cf.get("flutes"),
                "flute_depth": cf.get("flute_depth"),
                "shoulder": cf.get("shoulder")}
    except Exception as e:
        return {"tool_no": tno, "error": str(e)[:120]}


def program_facts(path):
    """Identity of the file the comment was about: code, md5, tool it calls."""
    if not path:
        return None
    if not os.path.exists(path):
        return {"path": path, "note": "not on disk"}
    body = open(path, "rb").read()
    text = body.decode("utf-8", "replace")
    code = re.search(r"^\(===\s*([A-Z]{3})\s*===\)", text, re.M)
    tool = re.search(r"\bT(\d+)\s*M6", text)
    return {"path": path.replace("/home/brains/", "~/"),
            "name": os.path.basename(path),
            "code": code.group(1) if code else None,
            "md5": hashlib.md5(body).hexdigest(),
            "calls_tool": int(tool.group(1)) if tool else None,
            "lines": text.count("\n") + 1}


def add(args):
    prog = program_facts(args.program)
    tno = args.tool
    if tno is None and prog and prog.get("calls_tool") is not None:
        tno = prog["calls_tool"]
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "said": args.said,
        "topic": args.topic,
        "material": args.material,
        "became": args.became,
        "program": prog,
        "tool": tool_facts(tno),
        "machine": machine_state(),
    }
    with open(STORE, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=2))
    return rec


def load():
    if not os.path.exists(STORE):
        return []
    out = []
    for line in open(STORE):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def render(_args=None):
    recs = load()
    L = ["# Operator feedback — his words, and what they became",
         "",
         "GENERATED by `tools/feedback_log.py render` from "
         "`docs/operator_feedback.jsonl`. **Do not hand-edit.**",
         "",
         "Operator 2026-09-29: *\"i want to build a history of my comments so "
         "that we can fix file, material and we know the tools used, and you "
         "know the machine state.\"*",
         "",
         "His comment is verbatim. Everything else was read from the machine "
         "at the moment he said it.",
         "", "---", ""]
    for r in reversed(recs):                      # newest first
        p = r.get("program") or {}
        t = r.get("tool") or {}
        m = r.get("machine") or {}
        L.append("## %s — %s" % (r["at"], r.get("topic") or "other"))
        L.append("")
        L.append("> %s" % r["said"])
        L.append("")
        L.append("```")
        L.append("became    %s" % (r.get("became") or "-"))
        L.append("material  %s" % (r.get("material") or "-"))
        if p:
            L.append("program   %s  code %s  md5 %s"
                     % (p.get("name"), p.get("code") or "-", (p.get("md5") or "")[:12]))
        if t:
            L.append("tool      T%s  dia %s  flutes %s  z_offset %s  %s"
                     % (t.get("tool_no"), t.get("diameter"), t.get("flutes"),
                        t.get("z_offset"), t.get("remark") or ""))
        if m.get("read") == "live":
            L.append("machine   T%s in spindle, tool_offset %s, G57 %s"
                     % (m.get("tool_in_spindle"), m.get("tool_offset_z"), m.get("g5x")))
            L.append("          %s, interp %s%s"
                     % (m.get("running_file") or "no file",
                        m.get("interp"),
                        ", line %s" % m["current_line"] if m.get("current_line") else ""))
            if m.get("pivot_arm"):
                L.append("          pivot arm %s" % m["pivot_arm"])
        else:
            L.append("machine   %s" % m.get("read"))
        L.append("```")
        L.append("")
    open(RENDER, "w").write("\n".join(L) + "\n")
    print("%s  (%d entries)" % (RENDER, len(recs)))


def show(args):
    for r in load():
        if args.topic and r.get("topic") != args.topic:
            continue
        if args.tool is not None and (r.get("tool") or {}).get("tool_no") != args.tool:
            continue
        if args.program and args.program not in ((r.get("program") or {}).get("name") or ""):
            continue
        print("%s  %-9s  %s" % (r["at"], r.get("topic"), r["said"][:70]))
        if r.get("became"):
            print("%s-> %s" % (" " * 21, r["became"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="record one comment")
    a.add_argument("said", help="his words, VERBATIM, typos and all")
    a.add_argument("--topic", choices=TOPICS, default="other")
    a.add_argument("--material", default=None)
    a.add_argument("--program", default=None, help="path to the .ngc it was about")
    a.add_argument("--tool", type=int, default=None,
                   help="tool number; taken from the program's T word if omitted")
    a.add_argument("--became", default=None, help="the number it turned into")
    a.set_defaults(func=add)

    r = sub.add_parser("render", help="rewrite docs/operator_feedback.md")
    r.set_defaults(func=render)

    s = sub.add_parser("show", help="filter the log")
    s.add_argument("--topic", choices=TOPICS)
    s.add_argument("--tool", type=int)
    s.add_argument("--program")
    s.set_defaults(func=show)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
