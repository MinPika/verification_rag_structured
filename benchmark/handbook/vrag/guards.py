"""Offline guard compiler: SOP corpus + compiled KB templates + task instruction (+ seed data in the seed tier) ->
executable guard specs, completion obligations and a task plan, each guard/obligation validated on its own
synthetic examples by the runtime gate code (vrag/runtime/policy_pkg/gate.py). Specs failing their tests are
disabled (precision first).

    python -m vrag.guards <task> [...] --tier kb|kb_seed
Output: kb/<task>/guards_<tier>.json, kb/<task>/plan_<tier>.txt
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import sys
import time

from . import llm, paths

AUTHOR = "claude-opus-5.5"

PROMPT = """You configure a runtime compliance checker for an AI office agent that will now work this task. The agent
acts only through tool calls; the checker sees each proposed call as an ACTION object and can block it before it
runs, and at the end it refuses to let the agent finish while obligations are open. A wrong block or a wrong
obligation is WORSE than a missing one: it wastes the agent's turns and can push it into a real violation. Emit a
spec only when the SOP{seed_note} makes it certain.

{inputs}

ACTION object (what the checker sees): {{"kind": one of email_send | email_reply | email_forward | email_draft |
slack_post | slack_dm | jira_create | jira_update_issue | jira_transition_issue | jira_add_comment |
cal_create_event | cal_update_event | cal_delete_event | file_write, "to": [lower-case emails], "cc": [...],
"subject": str, "text": str (email/slack body; for jira/calendar the JSON of the call; for file_write the code),
"channel": "slack channel name without #", "files": [file names written], "project": "jira project key"}}

Return JSON:
{{"analysis": "<=200 words: what the SOP requires in this task{seed_word}: the items/cases, the procedure for each,
   the correct outcome (including any STOP/HOLD/escalation/do-not-act decisions) and why",
 "plan": ["ordered, concrete checklist for the agent with exact values: recipients, channels, subject lines, exact
   message text where the SOP prescribes it, files/rows/cells to write, things NOT to do{seed_word}"],
 "guards": [{{"id":"G1","type":"forbid|require_text|require_prior|require_authorization",
   "match": {{"kinds":[...],"channel":"","to_any":[],"subject_rx":"","text_rx":"","file_rx":"","project":""}},
   "must_contain": ["exact strings (require_text)"], "prior": {{match spec (require_prior)}},
   "people": ["names/emails allowed to authorize (require_authorization)"], "about_rx": "regex the authorizing
   message must contain (require_authorization)", "message": "what is wrong, quoting the SOP rule",
   "fix": "exact corrective action", "blocks": ["SOP block ids"],
   "tests": {{"violating": [ACTION, ...], "compliant": [ACTION, ...]}}}}],
 "obligations": [{{"id":"O1","type":"action|row|no_row",
   "match": {{...match spec for type action...}},
   "file_rx": "regex on workbook path (row/no_row)", "where": {{"Column": "regex"}}, "expect": {{"Column": "regex"}},
   "message": "what is still missing per the SOP", "fix": "exact action incl. exact text/values", "blocks": [...],
   "tests": {{"satisfying": [ACTION, ...], "not_satisfying": [ACTION, ...]}}}}],
 "open_questions": []}}
Rules for specs:
- match fields are ANDed; regexes are Python, case-insensitive, run on dash-normalised text (— and – become -).
  Keep them specific (e.g. include the case id or the exact tag) so unrelated actions are not caught.
- forbid: actions that must not happen at all{seed_forbid}.
- require_text: when a matching action happens it must contain exact SOP strings (tags, subject formats, IDs).
- require_prior: a matching action is only allowed after an earlier action (prior match spec) was done.
- require_authorization: the action needs written authorization from listed people found in mail/Slack. Never let
  it (or a forbid) catch escalations / notifications that REPORT the issue or REQUEST authorization (messages to
  the authorizers, escalation/alert channels): include such a message among the compliant tests.
- obligations{seed_oblig}. Row obligations are checked on the live .xlsx files (first non-empty row = header);
  use them for required log/tracker rows and cell values; 'no_row' for rows that must not exist.
- Every spec needs >=1 violating and >=1 compliant test (guards) or >=1 satisfying and >=1 not_satisfying test
  (action obligations); row obligations need no tests.
- Prefer few, high-confidence specs (typically 3-25). Output only the JSON in one ```json block."""

SEED_NOTE = " and the task's actual data"
INPUTS_KB = """<sop_corpus>
{corpus}
</sop_corpus>

<compiled_templates>
{templates}
</compiled_templates>

<task_instruction>
{instruction}
</task_instruction>
(You do NOT see the mailbox, Slack, files or other data of this task: specs must hold for ANY data consistent with
the SOP and the instruction. Obligations can only be instruction-level.)"""

INPUTS_SEED = """<sop_corpus>
{corpus}
</sop_corpus>

<compiled_templates>
{templates}
</compiled_templates>

<task_environment>
{env}
</task_environment>"""


def _gate():
    spec = importlib.util.spec_from_file_location("vrag_gate", paths.ROOT / "vrag" / "runtime" / "policy_pkg" / "gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vrag_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def _act(g, d: dict):
    d = d or {}
    return g.Act(tool="test", kind=str(d.get("kind", "")), args={}, to=[str(x).lower() for x in d.get("to") or []],
                 cc=[str(x).lower() for x in d.get("cc") or []], subject=str(d.get("subject") or ""),
                 text=str(d.get("text") or ""), channel=str(d.get("channel") or ""),
                 files=[str(x) for x in d.get("files") or []], project=str(d.get("project") or ""))


def _seed_headers(task: str, g) -> dict[str, set[str]]:
    """{workbook relative path: normalised header names} for the task's seed workspace."""
    import os

    os.environ["VRAG_WORKDIR"] = str(paths.workspace(task))
    out: dict[str, set[str]] = {}
    for rel, row in g._xlsx_rows("."):
        out.setdefault(rel, set()).update(row.keys())
    os.environ["VRAG_WORKDIR"] = "/nonexistent"
    return out


def _cols_ok(cols: dict, headers: set[str], g) -> bool:
    for c in cols or {}:
        k = g.norm(c)
        if not any(k == h or k in h for h in headers):
            return False
    return True


def validate(spec: dict, task: str | None = None) -> dict:
    """Run every guard/obligation on its own tests with the runtime gate code; disable failures. Row obligations
    must name columns that exist in a seed workbook matching file_rx (or, for files the agent creates, in some seed
    workbook such as the blank template)."""
    import os
    import re

    g = _gate()
    os.environ["VRAG_WORKDIR"] = "/nonexistent"
    g.slack_channels()  # empty off-container: channel names are used as given
    heads = _seed_headers(task, g) if task else {}
    out = {"guards": [], "obligations": [], "dropped": []}
    for gd in spec.get("guards", []):
        tests = gd.get("tests") or {}
        viol, comp = tests.get("violating") or [], tests.get("compliant") or []
        g.GUARDS = {"guards": [gd]}
        g.authorized = lambda people, rx: False  # tests model the no-authorization case
        try:
            fires = [bool(g.check_guards(_act(g, a), [])) for a in viol]
            g.authorized = lambda people, rx: True
            clean = [not g.check_guards(_act(g, a), []) for a in comp]
            ok = bool(viol) and bool(comp) and all(fires) and all(clean)
            if gd.get("type") == "require_prior":
                prior = gd.get("prior") or {}
                ok = ok and bool(prior)
        except Exception as e:
            ok, fires, clean = False, [str(e)], []
        gd["enabled"] = ok
        (out["guards"] if ok else out["dropped"]).append(gd)
    for ob in spec.get("obligations", []):
        typ = ob.get("type", "action")
        if typ == "action":
            tests = ob.get("tests") or {}
            sat, uns = tests.get("satisfying") or [], tests.get("not_satisfying") or []
            try:
                ok = bool(sat) and bool(uns) and all(g._match(ob.get("match") or {}, _act(g, a)) for a in sat) \
                    and not any(g._match(ob.get("match") or {}, _act(g, a)) for a in uns)
            except Exception:
                ok = False
        else:
            ok = bool(ob.get("file_rx")) and bool(ob.get("where"))
            if ok and heads:
                try:
                    match = [h for rel, h in heads.items() if re.search(ob["file_rx"], rel, re.I)]
                except re.error:
                    match, ok = [], False
                pool = match or list(heads.values())
                cols = {**(ob.get("where") or {}), **(ob.get("expect") or {})}
                ok = ok and any(_cols_ok(cols, h, g) for h in pool)
        ob["enabled"] = ok
        (out["obligations"] if ok else out["dropped"]).append(ob)
    return out


REVIEW = """You are auditing a compliance configuration that another model wrote for an AI office agent's task (below the
inputs). Using ONLY the SOP and the task data, check the analysis, plan, guards and obligations. Report a MAJOR
finding only for a DEMONSTRABLE error - something the SOP text and the data clearly contradict:
- wrong reading of the SOP (missed condition, exception, threshold, date window, authority, stop/hold rule, a
  rule that the data actually triggers or does not trigger), wrong case outcome;
- wrong exact values (recipient, channel, subject/tag text, IDs, amounts, dates, file/row/column names);
- a guard that would block a correct action, an obligation that requires something the SOP does not require here;
- a missing spec for an outcome the SOP clearly requires/forbids here.
Do NOT raise major findings that rest on speculation or on information that is merely absent from the data (e.g.
"the document was not inspected", "cannot be sure X exists"): the agent will see the full workspace. Note such
concerns as minor. Do not weaken firm conclusions that the data supports. Compute dates/amounts yourself where
relevant. Return JSON:
{{"verdict":"ok|fix","findings":[{{"where":"analysis|plan[i]|G1|O2|missing","severity":"major|minor",
  "problem":"...","fix":"...","evidence":"SOP block id + exact data quote proving the error"}}]}}

{inputs}

<configuration>
{config}
</configuration>"""

REVISE = """{prompt}

A reviewer audited your previous answer (shown below) and reported findings. Re-check each finding against the SOP
and the data; apply only the ones that are demonstrably right, ignore speculative ones, keep conclusions the data
supports, and return the complete corrected JSON in the same format.

<previous_answer>
{config}
</previous_answer>

<review>
{review}
</review>"""

REVIEWER = "gpt-5.6-sol"


def templates_text(kb: dict) -> str:
    lines = []
    for t in kb.get("templates", []):
        lines.append(f"{t['id']} [{t.get('kind')}] {t.get('title')} | channel={t.get('channel', '')} "
                     f"to={t.get('to', [])} | subject={t.get('subject', '')!r}\n  body={t.get('body', '')[:700]!r}")
    return "\n".join(lines)


def compile_guards(task: str, tier: str, review: bool = True) -> dict:
    kbp = paths.KB / task / "kb.json"
    kb = json.loads(kbp.read_text())
    corpus = (paths.KB / task / "k0" / "policy.md").read_text()
    tdir = paths.TASKS / task
    if tier == "kb":
        inputs = INPUTS_KB.format(corpus=corpus, templates=templates_text(kb),
                                  instruction=(tdir / "instruction.md").read_text())
        prompt = PROMPT.format(inputs=inputs, seed_note="", seed_word="", seed_forbid="",
                               seed_oblig=": only what the instruction itself requires (often none)")
    else:
        env = (paths.KB / task / "env.txt").read_text()
        inputs = INPUTS_SEED.format(corpus=corpus, templates=templates_text(kb), env=env)
        prompt = PROMPT.format(inputs=inputs, seed_note=SEED_NOTE, seed_word=" for this data",
                               seed_forbid=" in this task (e.g. proceeding with a case that must be held, messaging "
                                           "a party the SOP excludes, acting on an unauthorized request)",
                               seed_oblig=": messages that must be sent, rows/cells that must be written, rows that "
                                          "must not exist, given this data")
    t0 = time.time()
    spec = llm.chat_json(AUTHOR, [{"role": "user", "content": prompt}], max_tokens=24000, cache=f"guards_{tier}",
                         timeout=2700)
    review_log = None
    if review:
        cfg = json.dumps({k: spec.get(k) for k in ("analysis", "plan", "guards", "obligations")}, ensure_ascii=False)
        try:
            rv = llm.chat_json(REVIEWER, [{"role": "user", "content": REVIEW.format(inputs=inputs, config=cfg)}],
                               max_tokens=30000, cache=f"guards_review_{tier}", timeout=2700)
        except Exception as e:
            rv = {"verdict": "error", "findings": [], "error": str(e)[:300]}
        review_log = rv
        major = [f for f in rv.get("findings", []) if f.get("severity") == "major"]
        if major:
            try:
                spec = llm.chat_json(AUTHOR, [{"role": "user", "content": REVISE.format(
                    prompt=prompt, config=cfg, review=json.dumps(major, ensure_ascii=False))}],
                    max_tokens=24000, cache=f"guards_revise_{tier}", timeout=2700)
            except Exception as e:
                review_log["revise_error"] = str(e)[:300]
    val = validate(spec, task)
    res = {"tier": tier, "analysis": spec.get("analysis", ""), "plan": spec.get("plan", []),
           "guards": val["guards"], "obligations": val["obligations"], "dropped": val["dropped"],
           "open_questions": spec.get("open_questions", []), "author": AUTHOR, "review": review_log,
           "secs": round(time.time() - t0)}
    (paths.KB / task / f"guards_{tier}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    plan = "\n".join(f"{i}. {p}" for i, p in enumerate(res["plan"], 1))
    (paths.KB / task / f"plan_{tier}.txt").write_text(plan)
    return {"task": task, "tier": tier, "guards": len(res["guards"]), "obligations": len(res["obligations"]),
            "dropped": len(res["dropped"]), "plan": len(res["plan"]), "secs": res["secs"],
            "review_major": len([f for f in (review_log or {}).get("findings", []) if f.get("severity") == "major"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--tier", default="kb_seed", choices=["kb", "kb_seed"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-review", action="store_true")
    a = ap.parse_args()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(lambda t: compile_guards(t, a.tier, not a.no_review), a.tasks):
            print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
