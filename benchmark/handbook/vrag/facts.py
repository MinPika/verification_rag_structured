"""Offline case fact sheet (an alternative to the drafted task plan): for every item the task may need handled, the
facts found in the task's data, the SOP blocks that bear on it and the open decision questions with the evidence on
each side. It locates; it does not decide. Same author model and inputs as the plan (guards.py, seed tier), so the
two differ only in what the agent is handed.

    python -m vrag.facts <task> [...] [--workers 6]
    python -m vrag.facts --split all
Output: kb/<task>/facts_kb_seed.json (structured, with lint results) and kb/<task>/facts_kb_seed.txt (what the
agent sees).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import time

from . import llm, paths
from .guards import AUTHOR, templates_text

TIER = "kb_seed"

PROMPT = """You prepare a CASE FACT SHEET for an AI office agent that will now work the task below. The agent reads
the SOP and decides and acts on its own; your sheet only helps it find what matters. You LOCATE, you do not DECIDE.

<sop_corpus>
{corpus}
</sop_corpus>

<compiled_templates>
{templates}
</compiled_templates>

<task_environment>
{env}
</task_environment>

Return JSON:
{{"general": ["task-wide facts: acting user and role, today's date, the people/roles/emails/channels/files/tickets
   that the items involve - as found in the data"],
 "items": [{{"item": "short label, e.g. 'Email 4 from a.parke@x.edu, subject ...'",
   "source": "where it is: mailbox email_id / Slack channel + time / file + row / instruction",
   "facts": ["facts from the data relevant to handling it, quoted or close to verbatim: senders, IDs, dates,
     amounts, names, matching roster/tracker rows, earlier related messages or tickets"],
   "sop": [{{"block": "D1.0123", "covers": "what this SOP block is about for this item (not what to do)"}}],
   "questions": ["each decision the SOP leaves to the agent for this item, phrased neutrally with the evidence on
     each side, e.g. 'Is this a legal threat as the SOP defines it (D1.0040)? The email mentions ...; it does not
     mention ...'"]}}]}}

Rules:
- Do NOT decide anything. No instructions or advice: never write do / do not / must / should / need to / skip /
  hold / stop / reply / forward / send / escalate as a recommendation; no proposed recipients, subjects, message
  text, values to write, or verdicts on which procedure applies. Where several SOP sections could apply, cite all
  of them and pose the question.
- List EVERY item that may need handling (every unread or open message, every request in the instruction or in
  messages, every record the instruction points to), including items that may need no action. Do not merge items.
- Facts must be checkable in the data; quote IDs, dates and amounts exactly; no inference beyond the data.
- "block" must be a block id that appears in the corpus in square brackets (e.g. D1.0123); cite the most specific
  blocks (definitions, steps, templates, exceptions), 2-10 per item.
Output only the JSON in one ```json block."""

REVISE = """Your fact sheet below contains wording that decides or instructs instead of locating facts:

{violations}

Rewrite those entries neutrally (facts, SOP pointers, open questions with evidence on each side), keep everything
else, and return the complete JSON in the same format, in one ```json block.

<fact_sheet>
{sheet}
</fact_sheet>"""

# Directive wording that turns a fact sheet back into a plan (lint). Facts, "covers" and general entries may not
# instruct at all; questions may ask "should ...?" but may not tell the agent what to do.
DIRECTIVE = re.compile(
    r"\b(do not|don't|must not|must|should|need(?:s)? to|you (?:will|can)|make sure|be sure|remember to|"
    r"skip|ignore|avoid)\b|^\s*(?:reply|forward|send|post|create|move|flag|escalate|hold|stop|notify|"
    r"write|assign)\b",
    re.I)
DIRECTIVE_Q = re.compile(r"\b(do not|don't|must not|make sure|be sure|remember to)\b", re.I)

HEADER = ("CASE FACT SHEET (drafted offline from this workspace's data and SOP; it lists the items, the facts found "
          "for each and the SOP blocks that bear on them - read those blocks with policy__read. It makes no "
          "decisions, can be incomplete or wrong, and is not a checklist: verify in the data, decide from the SOP "
          "yourself, and handle whatever the SOP requires.)")


def block_ids(task: str) -> set[str]:
    docs = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    return {b["id"] for d in docs for b in d["blocks"]}


def lint(sheet: dict, valid: set[str]) -> dict:
    """Directive phrases (by location) and SOP pointers whose block id is not in the corpus."""
    directives, bad_blocks = [], []
    for i, it in enumerate(sheet.get("items") or []):
        for field, rx in (("facts", DIRECTIVE), ("questions", DIRECTIVE_Q)):
            for j, s in enumerate(it.get(field) or []):
                if isinstance(s, str) and rx.search(s):
                    directives.append(f"items[{i}].{field}[{j}]: {s}")
        for j, p in enumerate(it.get("sop") or []):
            if isinstance(p, dict) and DIRECTIVE.search(str(p.get("covers", ""))):
                directives.append(f"items[{i}].sop[{j}].covers: {p.get('covers')}")
            if isinstance(p, dict) and str(p.get("block", "")).strip("[] ") not in valid:
                bad_blocks.append(str(p.get("block")))
    for j, s in enumerate(sheet.get("general") or []):
        if isinstance(s, str) and DIRECTIVE.search(s):
            directives.append(f"general[{j}]: {s}")
    return {"directives": directives, "bad_blocks": bad_blocks}


def clean(sheet: dict, valid: set[str]) -> dict:
    """Keep well-formed entries only; drop SOP pointers to blocks that do not exist."""
    items = []
    for it in sheet.get("items") or []:
        if not isinstance(it, dict) or not it.get("item"):
            continue
        sop = [{"block": str(p["block"]).strip("[] "), "covers": str(p.get("covers", ""))}
               for p in it.get("sop") or [] if isinstance(p, dict) and str(p.get("block", "")).strip("[] ") in valid]
        items.append({"item": str(it["item"]), "source": str(it.get("source", "")),
                      "facts": [str(x) for x in it.get("facts") or [] if str(x).strip()],
                      "sop": sop, "questions": [str(x) for x in it.get("questions") or [] if str(x).strip()]})
    return {"general": [str(x) for x in sheet.get("general") or [] if str(x).strip()], "items": items}


def render(sheet: dict) -> str:
    out = [HEADER]
    if sheet["general"]:
        out += ["General:"] + [f"- {x}" for x in sheet["general"]]
    for i, it in enumerate(sheet["items"], 1):
        out.append(f"Item {i}: {it['item']}" + (f" [{it['source']}]" if it["source"] else ""))
        out += [f"  - {x}" for x in it["facts"]]
        if it["sop"]:
            out.append("  SOP: " + "; ".join(f"{p['block']} ({p['covers']})" if p["covers"] else p["block"]
                                              for p in it["sop"]))
        out += [f"  Open question: {q}" for q in it["questions"]]
    return "\n".join(out)


def compile_facts(task: str) -> dict:
    kb = json.loads((paths.KB / task / "kb.json").read_text())
    prompt = PROMPT.format(corpus=(paths.KB / task / "k0" / "policy.md").read_text(), templates=templates_text(kb),
                           env=(paths.KB / task / "env.txt").read_text())
    valid = block_ids(task)
    t0 = time.time()
    msgs = [{"role": "user", "content": prompt}]
    sheet = llm.chat_json(AUTHOR, msgs, max_tokens=24000, cache="facts", timeout=2700)
    first = lint(sheet, valid)
    if first["directives"]:
        sheet = llm.chat_json(AUTHOR, msgs + [{"role": "assistant", "content": json.dumps(sheet, ensure_ascii=False)},
                                              {"role": "user", "content": REVISE.format(
                                                  violations="\n".join(first["directives"][:60]),
                                                  sheet=json.dumps(sheet, ensure_ascii=False))}],
                              max_tokens=24000, cache="facts_revise", timeout=2700)
    final = lint(sheet, valid)
    sheet = clean(sheet, valid)
    res = {"tier": TIER, "author": AUTHOR, "lint_first": first, "lint_final": final, "secs": round(time.time() - t0),
           **sheet}
    (paths.KB / task / f"facts_{TIER}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (paths.KB / task / f"facts_{TIER}.txt").write_text(render(sheet))
    return {"task": task, "items": len(sheet["items"]), "directives_first": len(first["directives"]),
            "directives_final": len(final["directives"]), "bad_blocks": len(final["bad_blocks"]), "secs": res["secs"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--split", default="", help="dev | test | all (instead of task names)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="recompile tasks that already have a fact sheet")
    a = ap.parse_args()
    tasks = a.tasks or [t for t in paths.all_tasks() if a.split == "all" or paths.split(t) == a.split]
    if not a.force:
        tasks = [t for t in tasks if not (paths.KB / t / f"facts_{TIER}.txt").exists()]

    def one(t: str) -> dict:
        try:
            return compile_facts(t)
        except Exception as e:  # noqa: BLE001 - report and continue with the other tasks
            return {"task": t, "error": f"{type(e).__name__}: {str(e)[:300]}"}

    with cf.ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(one, tasks):
            print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
