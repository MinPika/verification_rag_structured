"""Offline SOP-to-code compiler ("retrieve the code, not the text").

Each SOP procedure in the compiled KB becomes one pure Python function that encodes its conditions, thresholds,
deadlines, exceptions, stop/escalation rules and the ordered actions, with every statement commented with the SOP
block ids it implements. Shared facts (definitions, people, channels, files, templates, holidays) are emitted
verbatim from the KB into one constants module, so the LLM only writes logic. The block -> function mapping is the
procedure's block list; blocks without code fall back to SOP text at retrieval time.

Validation (code that fails is not served; its blocks fall back to text):
- static safety check (no imports, I/O, dunder access, dangerous builtins, while loops) - sop_exec.check;
- message wording grounded: string literals passed as message text must occur in the SOP (or come from the
  template constants);
- the author's example cases execute in the sandbox and return a list of actions (``runnable``).

    python -m vrag.sopcode [--tasks a,b | --split dev|test|all] [--workers 16]
Output: kb/<task>/sop_code.json  {"common": src, "procedures": {pid: {...}}, "block_map": {block: pid}}
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import json
import pprint
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from . import llm, paths
from .compile import load_k0, text_of

AUTHOR = "claude-opus-5.5"
RUNTIME = paths.ROOT / "vrag" / "runtime" / "policy_pkg"
sys.path.insert(0, str(RUNTIME))
import sop_exec  # noqa: E402


def _load_gate():
    """The gate's message normaliser, loaded once at import (worker threads only read it)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("vrag_gate_sopcode", RUNTIME / "gate.py")
    g = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = g  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(g)
    return g


_GATE = _load_gate()

PROMPT = """Rewrite one procedure of a company SOP as a single pure Python function. An AI office agent will read this code
INSTEAD of the SOP text, as the precise specification, and can also call it with the facts of a case to get the
ordered actions the SOP prescribes. Be exact and complete: the code must say everything the SOP text says.

<procedure id="{pid}" title="{title}" trigger="{trigger}">
<sop_text>
{sop}
</sop_text>
<compiled_steps>
{steps}
</compiled_steps>
</procedure>

Shared names you can use (already defined; do not redefine):
{names}
Action constructors (return dicts; do not perform anything): send_email(to, subject, body, cc=(), attachments=(),
template=""), reply_email(email, body, template=""), forward_email(email, to, note=""), post_slack(channel, text,
template=""), send_dm(person, text, template=""), jira_create(project, summary, description="", assignee="",
**fields), jira_update(issue, **fields), jira_transition(issue, status), jira_comment(issue, text),
calendar_event(title, start="", end="", attendees=(), description=""), write_row(file, values, sheet=""),
update_cells(file, where, values, sheet=""), move_email(email, folder), stop(reason), escalate(to, reason, via=""),
note(text).
Helpers: date(s), fmt(d, style="%m/%d/%Y"), is_business_day(d, holidays=()), add_business_days(d, n,
holidays=()), business_days_between(a, b, holidays=()), add_days(d, n), days_between(a, b), money(x),
fill(template, **values), datetime, timedelta.

Write:
def {fn}(case: dict, today: str = "") -> list[dict]:
    \"\"\"<one-line purpose> [blocks]
    case keys: <each input fact the SOP decision needs: name, type/allowed values, and where it comes from (file +
    column, email, Slack, Jira)>\"\"\"
Rules:
- Encode every condition, threshold, date window, exception, authority/approval requirement, ordering, stop/hold
  and escalation rule as code; return the actions in SOP order. When a required fact is missing from ``case``,
  return [note("<what to check and where>")] rather than guessing.
- Message wording: use TEMPLATES[...] subject/body with fill(), or copy the SOP's literal text verbatim. Never
  invent wording.
- Use exact values from the SOP (amounts, days, recipients, channels, file and column names, tags).
- Comment each statement with the SOP block id(s) it implements, e.g. ``# [D1.0297]``.
- No imports, no I/O, no while loops, no global state. Only the shared names, the API above and builtins.
Return JSON only, in one ```json block: {{"code": "<the function source>", "examples": [{{"case": {{...}},
"today": "YYYY-MM-DD"}}, ...]}}  (1-3 realistic example cases covering the main branches)."""


# ---- shared constants ---------------------------------------------------------------------------------------------

def _ident(s: str) -> str:
    return re.sub(r"\W+", "_", s).strip("_").lower()


def common_source(kb: dict) -> str:
    """Verbatim KB facts as Python literals (no LLM involved)."""
    holidays = sorted({m.group(0) for d in kb.get("definitions", []) + kb.get("tables", [])
                       if "holiday" in json.dumps(d).lower()
                       for m in re.finditer(r"\d{4}-\d{2}-\d{2}", json.dumps(d))})
    parts = {
        "COMPANY": kb.get("company", ""),
        "DEFINITIONS": {d["term"]: d["meaning"] for d in kb.get("definitions", []) if d.get("term")},
        "PEOPLE": {p["name"]: {k: p.get(k) or ([] if k in ("aliases", "authority") else "")
                               for k in ("role", "email", "slack", "aliases", "authority")}
                   for p in kb.get("people", []) if p.get("name")},
        "CHANNELS": {c["name"].lstrip("#"): c.get("purpose", "") for c in kb.get("channels", []) if c.get("name")},
        "FILES": {f["name"]: {"purpose": f.get("purpose") or "", "columns": f.get("columns") or []}
                  for f in kb.get("files", []) if f.get("name")},
        "TEMPLATES": {t["id"]: {k: t.get(k) or ([] if k in ("to", "cc") else "")
                                for k in ("title", "kind", "to", "cc", "channel", "subject", "body")}
                      for t in kb.get("templates", []) if t.get("id")},
        "HOLIDAYS": holidays,
    }
    out = ['"""Shared SOP facts, copied verbatim from the compiled policy KB."""', ""]
    for name, val in parts.items():
        out.append(f"{name} = {pprint.pformat(val, width=116, sort_dicts=False)}")
        out.append("")
    return "\n".join(out)


def _names(kb: dict) -> str:
    t = ", ".join(f"'{x['id']}' ({x.get('title', '')[:40]})" for x in kb.get("templates", []))
    return ("COMPANY; DEFINITIONS {term: meaning}; PEOPLE {name: {role, email, slack, aliases, authority}}; "
            "CHANNELS {name: purpose}; FILES {name: {purpose, columns}}; HOLIDAYS [YYYY-MM-DD]; "
            f"TEMPLATES {{id: {{title, kind, to, cc, channel, subject, body}}}} with ids: {t}")


# ---- validation -----------------------------------------------------------------------------------------------------

def execute(common: str, code: str, fn: str, case: dict, today: str = "", timeout: int = 10) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"common": common, "code": code, "fn": fn, "case": case, "today": today}, fh)
    try:
        p = subprocess.run([sys.executable, str(RUNTIME / "sop_exec.py"), fh.name], capture_output=True, text=True,
                           timeout=timeout, check=False)
        return json.loads(p.stdout or "{}") or {"ok": False, "error": p.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "no JSON output"}
    finally:
        Path(fh.name).unlink(missing_ok=True)


def _literal_text(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    if isinstance(node, ast.BinOp):
        return _literal_text(node.left) + _literal_text(node.right)
    return []


_FMT = re.compile(r"%[-+0-9.]*[sdfr]|\{[^{}]*\}|\[[^\[\]]{1,80}\]")


def _grounded(piece: str, sop_loose: str, loose) -> bool:
    """A literal is grounded when its fixed parts (between %s / {..} / [..] slots) occur in order in the SOP."""
    chunks = [loose(c) for c in _FMT.split(piece)]
    chunks = [c for c in chunks if len(c) >= 4]
    if not chunks:
        return True
    return re.search(".{0,300}?".join(re.escape(c) for c in chunks), sop_loose, re.S) is not None


def ungrounded_wording(code: str, sop_loose: str, loose) -> list[tuple[int, str]]:
    """(line, text) of message-text literals (>= 25 chars of fixed text) not found in the SOP: invented wording."""
    out = []
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in sop_exec.MESSAGE_CALLS):
            continue
        fields = sop_exec.MESSAGE_CALLS[node.func.id]
        args = [kw.value for kw in node.keywords if kw.arg in fields]
        args += node.args[1:3] if node.func.id in ("send_email", "post_slack", "send_dm", "jira_comment") else []
        for a in args:
            for s in _literal_text(a):
                for piece in re.split(r"\n+", s):
                    if len(_FMT.sub("", piece).strip()) >= 25 and not _grounded(piece, sop_loose, loose):
                        out.append((a.lineno, piece.strip()[:80]))
    return out


def annotate(code: str, flagged: list[tuple[int, str]]) -> str:
    """Mark lines whose message wording is not in the SOP, so the reader checks the SOP text there."""
    lines = code.split("\n")
    for ln in sorted({ln for ln, _ in flagged}):
        if 0 < ln <= len(lines):
            lines[ln - 1] += "  # NOTE: wording not found in the SOP text - check the SOP"
    return "\n".join(lines)


def validate_function(common: str, code: str, fn: str, examples: list[dict], sop_loose: str, loose) -> dict:
    res: dict[str, Any] = {"fn": fn, "code": code, "ok": False, "runnable": False, "problems": []}
    problems = sop_exec.check(code)
    if not problems:
        tree = ast.parse(code)
        if not any(isinstance(n, ast.FunctionDef) and n.name == fn for n in tree.body):
            problems.append(f"function {fn} not defined at top level")
    if not problems:
        bad = ungrounded_wording(code, sop_loose, loose)
        if bad:
            code = annotate(code, bad)
            res["code"] = code
            res["ungrounded"] = [t for _, t in bad]
    if problems:
        res["problems"] = problems
        return res
    runs = [execute(common, code, fn, e.get("case") or {}, e.get("today", "")) for e in (examples or [])[:3]]
    res["examples"] = [{"case": e.get("case"), "today": e.get("today", ""), "result": r}
                       for e, r in zip((examples or [])[:3], runs, strict=True)]
    res["runnable"] = bool(runs) and all(r.get("ok") for r in runs)
    if not res["runnable"]:
        res["problems"].append("examples do not execute: " + "; ".join(r.get("error", "")[:120] for r in runs
                                                                         if not r.get("ok"))[:300])
    res["ok"] = True  # readable, safe and grounded; runnable is reported separately
    return res


# ---- compile ----------------------------------------------------------------------------------------------------

def compile_procedure(task: str, kb: dict, proc: dict, blocks: dict, common: str, sop_loose: str, loose) -> dict:
    fn = f"{_ident(proc['id'])}_{_ident(proc.get('title', ''))}"[:60]
    ids = [b for b in proc.get("blocks", []) if b in blocks]
    sop = "\n".join(f"[{b}] {blocks[b]['text']}" for b in ids) or text_of(ids, blocks)
    steps = json.dumps([{k: s.get(k) for k in ("id", "kind", "instruction", "when", "actions", "on_fail")}
                        for s in proc.get("steps", [])], ensure_ascii=False)[:12000]
    prompt = PROMPT.format(pid=proc["id"], title=proc.get("title", ""), trigger=proc.get("trigger", ""), sop=sop,
                           steps=steps, names=_names(kb), fn=fn)
    try:
        out = llm.chat_json(AUTHOR, [{"role": "user", "content": prompt}], max_tokens=12000, cache="sopcode",
                            timeout=1800)
    except Exception as e:  # noqa: BLE001 - one procedure's failure falls back to text
        return {"fn": fn, "ok": False, "runnable": False, "problems": [f"author error: {e}"[:200]], "blocks": ids}
    res = validate_function(common, str(out.get("code") or ""), fn, out.get("examples") or [], sop_loose, loose)
    res.update({"blocks": ids, "title": proc.get("title", ""), "trigger": proc.get("trigger", "")})
    return res


def compile_task(task: str, workers: int = 8) -> dict:
    kb = json.loads((paths.KB / task / "kb.json").read_text())
    _, blocks, _ = load_k0(task)
    common = common_source(kb)
    problems = sop_exec.check(common)
    if problems:
        raise RuntimeError(f"common module failed the safety check: {problems[:3]}")
    loose = _GATE.mloose
    sop_loose = loose("\n".join(b["text"] for b in blocks.values()))
    t0 = time.time()
    procs = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(compile_procedure, task, kb, p, blocks, common, sop_loose, loose): p["id"]
                for p in kb.get("procedures", [])}
        for f in cf.as_completed(futs):
            procs[futs[f]] = f.result()
    block_map = {b: pid for pid, r in procs.items() if r.get("ok") for b in r.get("blocks", [])}
    out = {"task": task, "author": AUTHOR, "secs": round(time.time() - t0), "common": common, "procedures": procs,
           "block_map": block_map}
    (paths.KB / task / "sop_code.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return {"task": task, "secs": out["secs"], "procedures": len(procs), "served": sum(r["ok"] for r in procs.values()),
            "runnable": sum(r.get("runnable", False) for r in procs.values()), "mapped_blocks": len(block_map),
            "policy_blocks": len(blocks)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--split", default="dev", choices=("dev", "test", "all"))
    ap.add_argument("--workers", type=int, default=4, help="tasks in parallel")
    ap.add_argument("--proc-workers", type=int, default=6, help="procedures in parallel per task")
    a = ap.parse_args()
    tasks = a.tasks.split(",") if a.tasks else [t for t in paths.all_tasks()
                                                 if a.split == "all" or paths.split(t) == a.split]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(compile_task, t, a.proc_workers): t for t in tasks}
        for f in cf.as_completed(futs):
            try:
                print(json.dumps(f.result()), flush=True)
            except Exception as e:  # noqa: BLE001 - one task's failure must not stop the batch
                print(json.dumps({"task": futs[f], "error": f"{type(e).__name__}: {e}"[:300]}), flush=True)


if __name__ == "__main__":
    main()
