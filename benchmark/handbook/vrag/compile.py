"""Offline compiler: task policy corpus (K0 policy.md) -> PolicyKB JSON (vrag.schema), pointer-based.

The author model returns STRUCTURE plus K0 block ids (or ranges "D1.0100..D1.0160") and, where exact wording matters
inline (subject lines, Slack tags), the exact substring. Verbatim text is rebuilt from K0 by ``materialize`` so
templates and step text cannot be paraphrased or invented, and output tokens stay small (proxy Claude output is
~20 tok/s).

Calls (author claude-opus-5.5; each sees the whole policy corpus):
  A entities   definitions, people/authorities, channels, files, reference tables
  B structure  templates (pointers + exact subject/inline text), procedure index (block ranges)
  C rules      cross-cutting rules
  D procedure  one call per procedure: typed steps/actions/conditions/failure branches + local rules
then lint -> review (gpt-5.6-sol) of procedures/rules/templates -> repair (opus) on major findings.

    python -m vrag.compile <task> [...] [--workers 8] [--no-review]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import time

from . import llm, paths
from .schema import PolicyKB, Procedure, Rule, Template

AUTHOR = "claude-opus-5.5"
REVIEWER = "gpt-5.6-sol"

SYSTEM = """You compile a company's standard operating procedure (SOP) corpus into a structured policy knowledge base.
An AI office agent will use it while working (what to do, exact wording to send, who may authorize what, when to
stop), and deterministic code will use it to check the agent's actions.

The corpus is anchored markdown: every heading, paragraph, list item and table row carries a block id in square
brackets, e.g. [D1.0123]. POINTER RULES:
- Do NOT retype long text. Point to it with block ids or inclusive ranges: "D1.0123" or "D1.0123..D1.0131".
- Only where exact wording is short and matters (subject lines, Slack tags/inline message formats, exact values),
  copy the exact substring character for character (keep dashes, brackets, capitalisation, placeholders).
CONTENT RULES:
- Use ONLY the corpus. No outside knowledge; never fix or improve the SOP; never guess missing values.
- Corpora are deliberately edited variants of a base SOP: use the values printed HERE (names, emails, channels,
  thresholds, day counts, time zones, codes, columns, tags).
- Record ambiguities/contradictions in "open_questions" instead of resolving them silently.
- Output one JSON object in a single ```json block and nothing else. Be concise in free-text fields."""

ENTITIES = """TASK (entities). Return JSON:
{"company":str,"summary":"<=60 words",
 "definitions":[{"term","meaning":"<=25 words, exact values","blocks":[...]}],   // business day, time zone, date
            // and ID formats, naming conventions, sign-off rules, holidays, glossary terms that change behaviour
 "people":[{"name","role","email","slack","aliases":[],"authority":["what they approve/authorize/receive"],
            "blocks":[...]}],
 "channels":[{"name":"#x / address / project","kind":"slack_channel|email|jira|calendar|phone|fax|portal|other",
              "purpose":"<=15 words","blocks":[...]}],
 "files":[{"name","purpose":"<=15 words","columns":[...],"rules":["append-only","copy blank template first",...],
           "blocks":[...]}],
 "tables":[{"id":"T1","title","blocks":["header..last row range"]}],             // decision/reference tables
 "open_questions":[]}"""

STRUCTURE = """TASK (structure). Return JSON:
{"templates":[{"id":"TPL-<slug>","title","kind":"email|slack|dm|jira|calendar|document|log_row|other",
   "to":["recipient/role as printed"],"cc":[],"channel":"#channel/mailbox if printed",
   "subject":"exact substring if the SOP prints a subject line format, else empty",
   "body":"exact substring ONLY for one-line inline formats (e.g. '[PA HOLD] CASE_ID — [missing / invalid]: [document name]'), else empty",
   "blocks":["block ids/ranges holding the template text (exclude its heading)"],
   "placeholders":{"[Placeholder]":"source of the value, <=10 words"}}],
 "procedures":[{"id":"P1","title","sections":["4.2"],"blocks":["range(s) the procedure spans"],
   "trigger":"<=20 words"}],
 "open_questions":[]}
Templates: EVERY prescribed text artifact - email/letter templates, Slack posts/tags, Jira summary/comment formats,
calendar event formats, log row formats, subject-line formats, file-naming formats, scripts.
Procedures: every distinct workflow incl. exception handling (stop/hold protocols, escalations, legal holds,
corrections); cover the whole corpus; 6-40 procedures."""

RULES = """TASK (cross-cutting rules). Return JSON:
{"rules":[{"id":"R1","kind":"prohibition|obligation|authority|threshold|deadline|ordering|stop|format|escalation|
  exception|definition","statement":"<=30 words, faithful, exact values","when":"<=20 words","then":"<=20 words",
  "unless":"printed exception or empty","params":{"threshold":"$5,000","allowed":"Nicole Ashford; Marta Voss",...},
  "procedures":["P3"],"severity":"hard|soft","blocks":[...]}],"open_questions":[]}
Include every prohibition, authority/approval requirement (who may authorize and that others may not), stop / hold /
do-not-proceed condition, escalation path, deadline/SLA, threshold/limit, ordering ("only after"), required format
(dates, IDs, sign-offs, naming), logging requirement, append-only/never-edit rule, confidentiality/legal rule, and
precedence rule (which instruction/document wins). Procedure ids: {procs}"""

PROCEDURE = """TASK (procedure {pid} "{title}", blocks {blocks}, trigger: {trigger}). Compile it into ordered typed
steps. Return JSON:
{{"id":"{pid}","title":"{title}","done_when":"<=25 words",
 "steps":[{{"id":"{pid}.S1","kind":"check|decide|act|compute|stop|escalate|wait|info","blocks":["source blocks"],
   "instruction":"<=25 words gloss with exact names/values",
   "when":"condition, exact field names/values ('always' if unconditional)",
   "actions":[{{"kind":"send_email|reply_email|forward_email|draft_email|post_slack|send_dm|create_jira|update_jira|
     comment_jira|calendar_event|write_cells|append_row|create_file|copy_file|rename_file|move_email|label_email|none",
     "target":"exact channel/recipient/file","template":"TPL id or empty","literal":"exact short inline text or empty",
     "fields":{{"Column":"value/source"}}}}],
   "on_fail":"<=20 words: what happens if the check fails"}}],
 "rules":[{{"id":"{pid}.R1","kind":"...","statement":"<=30 words","when":"","then":"","unless":"","params":{{}},
   "severity":"hard|soft","blocks":[...]}}]}}
Cover every instruction of the procedure in order (checks, logging checkpoints, notifications, holds, branches,
failure handling). Put rules that only constrain this procedure in "rules". Templates: {tpls}"""

REVIEW = """You audit a structured extraction of the SOP corpus above. Text fields are glosses; "blocks" point to the
verbatim source. Report problems that would make an AI agent or a compliance checker act WRONGLY:
- a value differs from the corpus (name, email, channel, threshold, day count, time zone, tag, column);
- a condition / exception / authority / stop rule is missing, inverted, or over-/under-generalised;
- a step is missing, out of order, or points to the wrong blocks; an action targets the wrong channel/recipient/file;
- an item is not supported by the corpus.
Ignore style and harmless brevity. Return JSON:
{{"findings":[{{"item":"<id>","severity":"major|minor","problem":"...","fix":"...","blocks":["supporting ids"]}}]}}
Items:
{items}"""

REPAIR = """An auditor reported problems with these items extracted from the corpus above.
Items:
{items}
Findings:
{findings}
Return the corrected items as JSON {{"items":[...]}} (same schema and ids, pointer rules apply). Fix only what the
corpus supports; if a finding is wrong, keep the item unchanged."""


# ---- K0 access -------------------------------------------------------------------------------------------------

def load_k0(task: str) -> tuple[str, dict[str, dict], list[str]]:
    docs = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    blocks, order = {}, []
    for d in docs:
        if d["role"] != "policy":
            continue
        for b in d["blocks"]:
            blocks[b["id"]] = b
            order.append(b["id"])
    return (paths.KB / task / "k0" / "policy.md").read_text(), blocks, order


def expand(ids: list[str], order: list[str]) -> list[str]:
    pos = {b: i for i, b in enumerate(order)}
    out: list[str] = []
    for x in ids or []:
        m = re.fullmatch(r"\s*(D\d+\.\d{4})\s*(?:\.\.|–|-|to)\s*(D\d+\.\d{4})\s*", str(x))
        if m and m.group(1) in pos and m.group(2) in pos:
            i, j = sorted((pos[m.group(1)], pos[m.group(2)]))
            out += order[i:j + 1][:400]
        elif str(x).strip() in pos:
            out.append(str(x).strip())
    return list(dict.fromkeys(out))


def text_of(ids: list[str], blocks: dict[str, dict], skip_headings: bool = False) -> str:
    lines = []
    for i in ids:
        b = blocks[i]
        if skip_headings and b["kind"] == "heading":
            continue
        lines.append(b["text"])
    return "\n".join(lines)


def materialize(kb: dict, blocks: dict[str, dict], order: list[str]) -> dict:
    """Expand block ranges, rebuild verbatim template bodies / table rows, attach refs."""
    def refs_for(ids: list[str]) -> list[dict]:
        return [{"blocks": ids[:12], "quote": blocks[ids[0]]["text"][:200]}] if ids else []

    for sec in ("definitions", "people", "channels", "files", "rules"):
        for it in kb.get(sec, []):
            ids = expand(it.get("blocks", []), order)
            it["blocks"] = ids
            it["refs"] = refs_for(ids)
    for t in kb.get("tables", []):
        ids = expand(t.get("blocks", []), order)
        rows = [blocks[i] for i in ids if blocks[i]["kind"] == "row"]
        t["blocks"] = ids
        if rows:
            t["columns"] = rows[0]["header"] or rows[0]["text"].split(" | ")
            t["rows"] = [r["text"].split(" | ") for r in rows if r["header"]]
        t["refs"] = refs_for(ids)
    for t in kb.get("templates", []):
        ids = expand(t.get("blocks", []), order)
        t["blocks"] = ids
        if not t.get("body") and ids:
            t["body"] = text_of(ids, blocks, skip_headings=True)
        t["refs"] = refs_for(ids)
    for p in kb.get("procedures", []):
        p["blocks"] = expand(p.get("blocks", []), order)
        p["refs"] = refs_for(p["blocks"])
        for s in p.get("steps", []):
            s["blocks"] = expand(s.get("blocks", []), order)
            s["refs"] = refs_for(s["blocks"])
    return kb


# ---- calls -----------------------------------------------------------------------------------------------------

def _author(corpus: str, task: str, max_tokens: int = 16000) -> dict:
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"<corpus>\n{corpus}\n</corpus>\n\n{task}"}]
    return llm.chat_json(AUTHOR, msgs, max_tokens=max_tokens, cache="compile", timeout=2400)


def compile_task(task: str, workers: int = 8, review: bool = True) -> dict:
    out = paths.KB / task
    corpus, blocks, order = load_k0(task)
    t0 = time.time()
    with cf.ThreadPoolExecutor(2) as ex:
        fa, fb = ex.submit(_author, corpus, ENTITIES), ex.submit(_author, corpus, STRUCTURE)
        ent, st = fa.result(), fb.result()
    procs = st.get("procedures", [])
    tpls = st.get("templates", [])
    proc_index = "; ".join(f"{p['id']} {p['title']}" for p in procs)
    tpl_index = "; ".join(f"{t['id']} ({t.get('title', '')})" for t in tpls)

    def one(p: dict) -> dict:
        return _author(corpus, PROCEDURE.format(pid=p["id"], title=p["title"], blocks=", ".join(p.get("blocks", [])),
                                                trigger=p.get("trigger", ""), tpls=tpl_index))

    with cf.ThreadPoolExecutor(workers) as ex:
        frules = ex.submit(_author, corpus, RULES.replace("{procs}", proc_index))
        full = list(ex.map(one, procs))
        grules = frules.result()
    rules = list(grules.get("rules", []))
    procedures = []
    for p, f in zip(procs, full, strict=True):
        for r in f.get("rules", []):
            r.setdefault("procedures", [p["id"]])
            rules.append(r)
        procedures.append({**p, "done_when": f.get("done_when", ""), "steps": f.get("steps", [])})
    kb = {**{k: v for k, v in ent.items() if k != "open_questions"}, "templates": tpls, "rules": rules,
          "procedures": procedures,
          "open_questions": ent.get("open_questions", []) + st.get("open_questions", [])
          + grules.get("open_questions", [])}
    kb = materialize(PolicyKB.model_validate(kb).model_dump(), blocks, order)
    (out / "kb_draft.json").write_text(json.dumps(kb, indent=1, ensure_ascii=False))
    stats = {"task": task, "secs_author": round(time.time() - t0), "procedures": len(kb["procedures"]),
             "steps": sum(len(p["steps"]) for p in kb["procedures"]), "templates": len(kb["templates"]),
             "rules": len(kb["rules"]), "people": len(kb["people"])}
    findings = []
    if review:
        kb, rstats, findings = review_kb(corpus, kb, workers, blocks, order)
        stats.update(rstats)
    from . import lint
    report = lint.lint(task, kb)
    kb["_meta"] = {"author": AUTHOR, "reviewer": REVIEWER if review else None, "lint": report["summary"],
                   "compiled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out / "kb.json").write_text(json.dumps(kb, indent=1, ensure_ascii=False))
    (out / "lint.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    (out / "review.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
    stats.update({"secs_total": round(time.time() - t0), "lint": report["summary"]})
    (out / "compile_stats.json").write_text(json.dumps(stats, indent=1))
    return stats


def _strip(it: dict) -> dict:
    """Drop rebuilt verbatim text from review payloads (pointer form is what the reviewer checks)."""
    it = json.loads(json.dumps(it))
    it.pop("refs", None)
    if it.get("blocks") and len(it.get("body", "")) > 200:
        it["body"] = it["body"][:200] + "..."
    for s in it.get("steps", []):
        s.pop("refs", None)
    return it


def review_kb(corpus: str, kb: dict, workers: int, blocks, order) -> tuple[dict, dict, list]:
    groups = [("procedures", [p]) for p in kb["procedures"]]
    groups += [("templates", kb["templates"][i:i + 15]) for i in range(0, len(kb["templates"]), 15)]
    groups += [("rules", kb["rules"][i:i + 30]) for i in range(0, len(kb["rules"]), 30)]

    def rev(group):
        kind, items = group
        payload = json.dumps([_strip(i) for i in items], ensure_ascii=False)
        msgs = [{"role": "user", "content": f"<corpus>\n{corpus}\n</corpus>\n\n" + REVIEW.format(items=payload)}]
        try:
            res = llm.chat_json(REVIEWER, msgs, max_tokens=30000, cache="review", timeout=1800)
        except Exception as e:
            return kind, items, [{"item": "*", "severity": "error", "problem": str(e)[:200]}], items
        major = [f for f in res.get("findings", []) if f.get("severity") == "major"]
        if not major:
            return kind, items, res.get("findings", []), items
        try:
            fix = _author(corpus, REPAIR.format(items=payload, findings=json.dumps(major, ensure_ascii=False)))
            fixed = fix.get("items") or items
        except Exception:
            fixed = items
        return kind, items, res.get("findings", []), fixed

    with cf.ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(rev, groups))
    cls = {"procedures": Procedure, "templates": Template, "rules": Rule}
    new = {k: [] for k in cls}
    log = []
    for kind, old, f, fixed in results:
        log.append({"kind": kind, "ids": [i.get("id") for i in old], "findings": f})
        for it in fixed:
            try:
                new[kind].append(cls[kind].model_validate(it).model_dump())
            except Exception:
                continue
        if not fixed:
            new[kind] += old
    for k, v in new.items():
        kb[k] = v
    kb = materialize(kb, blocks, order)
    allf = [f for g in log for f in g["findings"]]
    return kb, {"review_major": sum(f.get("severity") == "major" for f in allf),
                "review_minor": sum(f.get("severity") == "minor" for f in allf),
                "review_errors": sum(f.get("severity") == "error" for f in allf)}, log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-review", action="store_true")
    a = ap.parse_args()
    for t in a.tasks:
        print(json.dumps(compile_task(t, a.workers, not a.no_review)), flush=True)


if __name__ == "__main__":
    main()
