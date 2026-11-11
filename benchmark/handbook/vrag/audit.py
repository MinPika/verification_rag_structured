"""Offline decision audit of a compiled task spec (v5).

The seeded compiler (guards.py) pre-solves the task; its plan/guards/obligations sometimes encode a wrong decision
(a mention read as a STOP trigger, one slot picked where the data require another). An independent model (default
gpt-5.6-sol) re-checks every item against the cited SOP text and the task data and marks it `keep` (follows
unambiguously) or `check` (interpretation / judgment / derived choice). Runtime effect (package.py, audit=1):
`check` plan items are shown as UNVERIFIED with a neutral question; `check` guards/obligations are disabled.

    python -m vrag.audit [--tasks a,b] [--workers 10]
Output: kb/<task>/audit_kb_seed.json
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import time

from . import llm, paths

AUDITOR = "gpt-5.6-sol"

PROMPT = """An offline compiler read a company SOP and this task's data, pre-solved the task, and wrote (a) a PLAN shown
to an AI office agent, (b) GUARDS that block agent actions, (c) OBLIGATIONS the agent must satisfy before finishing.
The compiler is sometimes WRONG on decisions: it reads a mention as a trigger (e.g. a person who happens to be a
lawyer treated as an "attorney communication"), invents a stop/hold/escalation the SOP does not require here,
excludes a case that qualifies (or includes one that does not), or picks one date/slot/amount/recipient where the
SOP and data point to another. A wrong item makes the agent fail; a missing item costs little.

Audit every plan item, guard and obligation against the SOP excerpts and the task data below:
- "keep": it follows directly and unambiguously from explicit SOP text and explicit data (exact formats, recipients,
  templates, required steps that clearly apply).
- "check": it rests on an interpretation, a judgment call, a derived choice (which slot/date/amount, which cases
  qualify, whether a stop/hold/escalation condition is met), or on facts you cannot confirm in the data.
Be strict: when in doubt, "check". For "check", write a short NEUTRAL question the agent should answer from the SOP
and data (do not presuppose the compiler's answer).

<sop_excerpts>
{sop}
</sop_excerpts>

<task_data>
{env}
</task_data>

<compiled>
ANALYSIS: {analysis}

PLAN:
{plan}

GUARDS:
{guards}

OBLIGATIONS:
{obligations}
</compiled>

Return JSON only, in one ```json block:
{{"plan": [{{"i": 1, "verdict": "keep|check", "question": ""}}, ...],
 "guards": [{{"id": "G1", "verdict": "keep|check", "why": ""}}, ...],
 "obligations": [{{"id": "O1", "verdict": "keep|check", "why": ""}}, ...]}}"""


def _blocks(task: str) -> dict[str, dict]:
    corpus = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    return {b["id"]: b for d in corpus for b in d.get("blocks", [])}


def _sop_excerpts(task: str, spec: dict, limit: int = 60000) -> str:
    blocks = _blocks(task)
    order = list(blocks)
    cited: list[str] = []
    text = json.dumps(spec, ensure_ascii=False)
    for bid in re.findall(r"D\d+\.\d{4}", text):
        if bid in blocks and bid not in cited:
            cited.append(bid)
    want: list[str] = []
    for bid in cited:
        i = order.index(bid)
        for j in range(max(0, i - 4), min(len(order), i + 7)):
            if order[j] not in want:
                want.append(order[j])
    want.sort(key=order.index)
    out, n = [], 0
    for bid in want:
        line = f"[{bid}] {blocks[bid].get('text', '')}"
        n += len(line)
        if n > limit:
            break
        out.append(line)
    return "\n".join(out)


def audit_task(task: str) -> dict:
    t0 = time.time()
    spec = json.loads((paths.KB / task / "guards_kb_seed.json").read_text())
    env = (paths.KB / task / "env.txt").read_text()[:120000]

    def fmt(items, keys):
        return "\n".join(json.dumps({k: g.get(k) for k in keys}, ensure_ascii=False) for g in items) or "(none)"

    prompt = PROMPT.format(
        sop=_sop_excerpts(task, spec), env=env, analysis=spec.get("analysis", ""),
        plan="\n".join(f"{i}. {p}" for i, p in enumerate(spec.get("plan", []), 1)) or "(none)",
        guards=fmt(spec.get("guards", []), ("id", "type", "match", "must_contain", "message")),
        obligations=fmt(spec.get("obligations", []), ("id", "type", "match", "where", "expect", "message")))
    res = llm.chat_json(AUDITOR, [{"role": "user", "content": prompt}], max_tokens=12000, cache="audit")
    out = {"task": task, "auditor": AUDITOR, "secs": round(time.time() - t0), **{k: res.get(k, []) for k in
                                                                                  ("plan", "guards", "obligations")}}
    (paths.KB / task / "audit_kb_seed.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return {"task": task, "secs": out["secs"],
            **{k: sum(1 for x in out[k] if x.get("verdict") == "check") for k in ("plan", "guards", "obligations")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    tasks = a.tasks.split(",") if a.tasks else [t for t in paths.all_tasks()
                                                 if (paths.KB / t / "guards_kb_seed.json").exists()]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for f in cf.as_completed([ex.submit(audit_task, t) for t in tasks]):
            try:
                print(json.dumps(f.result()), flush=True)
            except Exception as e:  # noqa: BLE001
                print(json.dumps({"error": str(e)[:300]}), flush=True)


if __name__ == "__main__":
    main()
