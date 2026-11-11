"""Offline call test: before any agent run, can the model call the FV tools correctly?

    python -m vharvey.fv.calltest --model claude-haiku-5.5 --tasks dev

For each task, one model turn with LAB's system prompt + the V block + all tools, and the task instruction followed
by a calibration note naming three candidate matters. We record the fv_* calls and check that every call parses
(known field, plausible value). Output: logs/calltest/<model>.json and a printed summary. No grading, no rubric use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from .. import batch, k0, paths, proxy
from . import api
from .arm import PROMPT, TOOLS

NOTE = ("\n\n[Calibration step — not the full task] Suppose your search has already produced these candidate "
        "matters: {cands}. Using the fv_* tools only, make the verification calls you would make to decide whether "
        "each candidate satisfies the question's conditions. Make the calls now; do not answer the question.")


def _cands(task: str, matters: list[str]) -> list[str]:
    h = int(hashlib.sha256(task.encode()).hexdigest(), 16)
    return [matters[(h >> (8 * i)) % len(matters)] for i in range(3)]


def one(model: str, task: str, matters: list[str]) -> dict:
    from lab_core.harness.run import DEFAULT_SKILLS, build_system_preamble, load_skills
    from lab_core.harness.tools import get_all_tool_definitions

    instr = json.loads((paths.TASKS / task / "task.json").read_text())["instructions"]
    cands = _cands(task, matters)
    adapter = proxy.ProxyAdapter(model, 0.0, "high")
    system = build_system_preamble(True) + load_skills(list(DEFAULT_SKILLS)) + PROMPT
    msgs = [adapter.make_system_message(system), adapter.make_user_message(instr + NOTE.format(cands=", ".join(cands)))]
    r = adapter.chat(msgs, get_all_tool_definitions(True) + TOOLS)
    calls = []
    for tc in r.tool_calls:
        try:
            args = json.loads(tc.arguments or "{}")
        except json.JSONDecodeError:
            calls.append({"tool": tc.name, "ok": False, "error": "bad JSON"})
            continue
        checks = args.get("checks", []) if tc.name == "fv_check_many" else [args] if tc.name == "fv_check" else []
        for c in checks:
            try:
                api.parse_field(str(c.get("field", "")))
                calls.append({"tool": tc.name, "field": c.get("field"), "value": c.get("value"),
                              "matter_id": c.get("matter_id"), "ok": c.get("matter_id") in cands})
            except ValueError as e:
                calls.append({"tool": tc.name, "field": c.get("field"), "value": c.get("value"), "ok": False,
                              "error": str(e)})
        if tc.name in ("fv_matter", "fv_doc") or not tc.name.startswith("fv_"):
            calls.append({"tool": tc.name, "ok": tc.name.startswith("fv_"), "args": args})
    return {"task": task, "candidates": cands, "instruction": instr.split("Output:")[0].strip(), "calls": calls,
            "text": r.text[:500]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-5.5")
    ap.add_argument("--tasks", default="dev")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from .. import runner
    runner.activate()
    matters = sorted(k0.manifest_index())
    tasks = batch.resolve_tasks(a.tasks)
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda t: one(a.model, t, matters), tasks))
    out = paths.ROOT / "logs" / "calltest" / f"{a.model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    fv_calls = [c for r in res for c in r["calls"] if c["tool"].startswith("fv_check")]
    used = sum(any(c["tool"].startswith("fv_") for c in r["calls"]) for r in res)
    print(f"{a.model}: tasks {len(res)}, used fv tools in {used}, fv checks {len(fv_calls)}, "
          f"valid {sum(c['ok'] for c in fv_calls)} ({sum(c['ok'] for c in fv_calls) / max(len(fv_calls), 1):.0%})")
    for r in res:
        fields = sorted({str(c.get("field")) for c in r["calls"] if c.get("field")})
        bad = [c for c in r["calls"] if not c["ok"]]
        print(f"  {r['task']}: {fields} {'BAD ' + json.dumps(bad)[:200] if bad else ''}")


if __name__ == "__main__":
    main()
