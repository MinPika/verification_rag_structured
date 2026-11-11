"""Per-task policy package (mounted by the container's MCP proxy as package ``policy``)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import paths
from .brief import make_brief

RUNTIME = Path(__file__).resolve().parent / "runtime"


def package_dir(task: str, arm: str, tier: str, plan_on: bool = True, audit: bool = False,
                msgs: bool = False, code: str = "", facts: bool = False, softstop: bool = False,
                exec_: bool = False) -> Path:
    """runs/pkgs/<arm>-<tier>[-noplan][-audit][-msgs][-code|-vcode][-facts][-soft][-exec]/<task>/policy: one
    directory per configuration."""
    flags = [x for x, on in (("noplan", not plan_on and not facts), ("audit", audit), ("msgs", msgs),
                             ({"sop": "code", "verifiers": "vcode"}.get(code, ""), bool(code)), ("facts", facts),
                             ("soft", softstop), ("exec", exec_)) if on]
    variant = "-".join([arm, tier, *flags])
    return paths.ROOT / "runs" / "pkgs" / variant / task / "policy"


def build_package(task: str, arm: str, tier: str, plan_on: bool = True, audit: bool = False,
                  msgs: bool = False, code: str = "", facts: bool = False, softstop: bool = False,
                  exec_: bool = False) -> Path:
    """code: "" (SOP text retrieval) | "sop" (our compiled procedure code, vrag.sopcode) | "verifiers" (the
    interwhen baseline's verifier modules cut into code units, vrag.vcode). facts: the case fact sheet (vrag.facts)
    replaces the drafted plan (A2/A3). softstop: stop/hold/escalation rules are scoped to their item. exec_: the
    policy__verify_* tools run the task's verifier code on demand (iw_exec.py)."""
    kb_path = paths.KB / task / "kb.json"
    if not kb_path.exists():
        raise RuntimeError(f"no compiled KB for {task}: {kb_path}")
    out = package_dir(task, arm, tier, plan_on, audit, msgs, code, facts, softstop, exec_)
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    for f in ("policy_server.py", "gate.py", "sop_exec.py", "iw_exec.py", "mcp.json", "mcp-tools.generated.json"):
        shutil.copy(RUNTIME / "policy_pkg" / f, out / f)
    kb = json.loads(kb_path.read_text())
    (out / "data" / "kb.json").write_text(json.dumps(kb, ensure_ascii=False))
    docs = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    (out / "data" / "corpus.json").write_text(json.dumps([d for d in docs if d["role"] == "policy"],
                                                         ensure_ascii=False))
    (out / "data" / "brief.txt").write_text(make_brief(kb, softstop=softstop))
    if softstop:
        (out / "data" / "softstop").write_text("1")
    if exec_:
        (out / "data" / "exec_enabled").write_text("1")
    guards = paths.KB / task / f"guards_{tier}.json"
    aud = _audit(task, tier) if audit else {}
    if arm == "A3" and guards.exists():
        spec = json.loads(guards.read_text())
        off = {x.get("id") for k in ("guards", "obligations") for x in aud.get(k, []) if x.get("verdict") == "check"}
        for k in ("guards", "obligations"):
            for g in spec.get(k, []):
                if g.get("id") in off:
                    g["enabled"] = False
        (out / "data" / "guards.json").write_text(json.dumps(spec, ensure_ascii=False))
    plan = paths.KB / task / f"plan_{tier}.txt"
    sheet = paths.KB / task / f"facts_{tier}.txt"
    if facts and arm in ("A2", "A3"):
        if not sheet.exists():
            raise RuntimeError(f"no fact sheet for {task}: run python -m vrag.facts {task}")
        (out / "data" / "facts.txt").write_text(sheet.read_text())
    elif plan_on and arm in ("A2", "A3") and plan.exists() and plan.read_text().strip():
        text = plan.read_text()
        if aud:
            text = _mark_plan(text, aud)
        (out / "data" / "plan.txt").write_text(text)
    if code:
        src = paths.KB / task / {"sop": "sop_code.json", "verifiers": "vcode.json"}[code]
        if not src.exists():
            raise RuntimeError(f"no code representation for {task}: run python -m vrag."
                               f"{'sopcode' if code == 'sop' else 'vcode'} --tasks {task}")
        compiled = json.loads(src.read_text())
        served = {pid: r for pid, r in compiled["procedures"].items() if r.get("ok")}
        bmap = {b: [x for x in ([v] if isinstance(v, str) else v) if x in served]
                for b, v in compiled["block_map"].items()}
        (out / "data" / "sop_code.json").write_text(json.dumps(
            {"source": compiled.get("source", "compiled"), "common": compiled.get("common", ""), "procedures": served,
             "block_map": {b: v for b, v in bmap.items() if v}}, ensure_ascii=False))
    mspec = paths.KB / task / f"messages_{tier}.json"
    if msgs and arm == "A3" and mspec.exists():
        compiled = json.loads(mspec.read_text())
        (out / "data" / "messages.json").write_text(json.dumps({"messages": compiled["messages"]}, ensure_ascii=False))
        if compiled.get("checklist"):
            (out / "data" / "messages.txt").write_text(compiled["checklist"])
    if arm == "A3":
        (out / "data" / "check_enabled").write_text("1")
    return out


def _audit(task: str, tier: str) -> dict:
    p = paths.KB / task / f"audit_{tier}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _mark_plan(text: str, aud: dict) -> str:
    """Plan items the offline audit could not confirm are shown as UNVERIFIED with a neutral question."""
    import re

    q = {int(x.get("i", 0)): (x.get("question") or "").strip() for x in aud.get("plan", [])
         if x.get("verdict") == "check"}
    out = []
    for line in text.split("\n"):
        m = re.match(r"(\d+)\.\s", line)
        if m and int(m.group(1)) in q:
            line += f"  [UNVERIFIED - decide from the SOP and the data: {q[int(m.group(1))] or 'is this right?'}]"
        out.append(line)
    return "\n".join(out)
