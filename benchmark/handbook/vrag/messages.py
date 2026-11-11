"""Offline compiler of per-message specs (v7): one spec per message the task requires or forbids.

A spec drives three runtime uses with one definition (gate.py): the start checklist rendered into the prompt, the
pre-call check of every outgoing message it is about, and the completion check at Stop. The author (Opus) sees the
SOP corpus, the compiled templates, the task data and the task plan; every spec is then validated mechanically and
anything that cannot be grounded is removed (precision first):

- quotes (required template wording) must occur verbatim in the SOP text (placeholders = wildcards) and must be
  message text, not procedure instructions (this is the template-cleaning step);
- values (names, IDs, dates, amounts) must occur in the task data;
- recipients must occur in the data/SOP; Slack channels must exist in the seed; DM recipients must be Slack users;
- the author's own sample message must be recognised by the spec and conform to it (failing requirements dropped);
- a forbidden spec needs allowed look-alikes that it does not catch;
- no spec may recognise another spec's sample (else its pre-call check is switched off).

    python -m vrag.messages [--tasks a,b | --split dev|test|all] [--workers 10]
Output: kb/<task>/messages_kb_seed.json
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import re
import sys
import threading
import time
from typing import Any

from . import llm, paths

AUTHOR = "claude-opus-5.5"
TIER = "kb_seed"
KINDS = ("email_send", "email_reply", "email_forward", "email_draft", "slack_post", "slack_dm")
# procedure/instruction wording that marks a quote as "how to send" rather than "what the message says"
_INSTRUCTION = re.compile(r"\.xlsx|\bcol(umn)?\b|→|->|^\s*(\d+[.)]|step\s*\d)|\b(subject|to|cc|bcc)\s*:|"
                          r"\b(post to|email to|send to|export|update the|log in|attach the file)\b", re.I)

PROMPT = """You compile the MESSAGE SPECS a deterministic checker uses for an AI office agent working this task. The agent
acts through tool calls (email send/reply/forward/draft, Slack channel post, Slack DM). For every message the SOP
and this task's data make CERTAIN, write one spec. The same spec is (1) shown to the agent as a checklist item,
(2) used to check each outgoing message it is about, before it is sent, and (3) checked at the end. A wrong spec
blocks correct work, which is worse than a missing spec: when the SOP or the data leave a decision open (which case
qualifies, which date/slot, whether a stop/escalation applies), write NO spec for it.

{inputs}

<task_plan note="drafted earlier from the same inputs; it may contain errors - follow the SOP and the data">
{plan}
</task_plan>

Return JSON only, in one ```json block:
{{"messages": [{{
  "key": "M1",
  "status": "required" | "forbidden",
  "what": "short description incl. the case, e.g. 'Template 13 access revocation request for Gerta Teodoor'",
  "kinds": ["email_send"],            // any of email_send, email_reply, email_forward, email_draft, slack_post, slack_dm
  "to": ["exact recipient emails"],   // email: To recipients; slack_dm: the person's email; else []
  "cc": [], "exact_to": false,        // exact_to=true only if the SOP says to send ONLY to these recipients
  "channel": "",                      // slack_post: channel name without #; else ""
  "about": {{"to_any": [], "channel": "", "subject_rx": "", "text_rx": ""}},
       // how to RECOGNISE this message among everything the agent sends: combine the recipient/channel with a
       // case identifier (name, ID, ticket) in text_rx/subject_rx; it must not recognise any other message
  "subject_rx": "", "subject_hint": "",   // emails: Python regex the subject must match (case-insensitive, dashes
                                         // normalised to '-'); hint = the exact expected subject
  "quotes": [{{"text": "...", "block": "D1.0203"}}],
       // 1-4 distinctive lines of the SOP's template MESSAGE TEXT that must appear in the message, copied verbatim
       // from the SOP (keep [Placeholders] as written). Only words the recipient reads: never 'Subject:'/'To:'
       // headers, procedure steps, file/column references or instructions. 20-200 characters each.
  "values": ["case details that must appear, exactly as in the task data: names, IDs, dates, amounts"],
  "attach": [{{"rx": "file-name regex", "desc": "what to attach"}}],
  "max_count": 1,
  "why": "the SOP rule and the data that make this certain (<= 40 words)",
  "blocks": ["SOP block ids"],
  "sample": {{"kind": "...", "to": [], "cc": [], "subject": "", "text": "...", "channel": "", "files": []}},
       // required: the complete correct message as the agent should send it;
       // forbidden: a realistic example of the forbidden message (full recipients, subject and text)
  "allowed": []   // REQUIRED for every forbidden spec (else it is discarded): 1-3 closely related messages that ARE
                  // allowed (e.g. the escalation or internal note that reports the issue, a different case to the
                  // same recipient), as sample-shaped objects; the spec must not recognise them
}}]}}
Rules: required = messages this task needs; forbidden = messages that must not be sent here (an excluded party, a
template the user excluded, acting before a required approval). Use exact values from the data. Typically 2-12
specs."""

INPUTS = """<sop_corpus>
{corpus}
</sop_corpus>

<compiled_templates>
{templates}
</compiled_templates>

<task_environment>
{env}
</task_environment>"""


_IMPORT_LOCK = threading.Lock()


def _gate(task: str):
    """A fresh runtime gate module pointed at this task's seed (Slack users/channels, mailbox). The gate reads its
    configuration from the environment at import time, so imports are serialised across worker threads."""
    with _IMPORT_LOCK:
        os.environ.update({"VRAG_SEED": str(paths.services(task)), "VRAG_WORKDIR": "/nonexistent",
                           "VRAG_STATE": "/nonexistent", "VRAG_PKG": "/nonexistent"})
        name = f"vrag_gate_msgs_{task}"
        spec = importlib.util.spec_from_file_location(name, paths.ROOT / "vrag" / "runtime" / "policy_pkg" / "gate.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        mod._slack()  # load the seed while the environment still points at this task
    return mod


def _act(g, d: dict | None):
    d = d or {}
    kind = str(d.get("kind") or "")
    to = [str(x).lower() for x in d.get("to") or []]
    people: list[str] = []
    if kind == "slack_dm":
        for uid, u in g._slack()["users"].items():
            if str((u.get("profile") or {}).get("email") or "").lower() in to:
                people += g.slack_user(uid)["aliases"]
    channel = str(d.get("channel") or "")
    ids = {c.get("name"): cid for cid, c in g._slack()["channels"].items()}
    return g.Act(tool="test", kind=kind, args={}, to=to, cc=[str(x).lower() for x in d.get("cc") or []],
                 subject=str(d.get("subject") or ""), text=str(d.get("text") or ""),
                 channel=ids.get(channel.lstrip("#"), channel), files=[str(x) for x in d.get("files") or []],
                 people=people)


def _policy_text(task: str) -> str:
    docs = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    return "\n".join(b.get("text", "") for d in docs if d.get("role") == "policy" for b in d.get("blocks", []))


def validate(spec: dict, task: str) -> dict:
    """Ground, self-test and de-conflict compiled message specs with the runtime gate code. Returns
    {"messages": [...kept, with enabled/pre flags...], "dropped": [...], "log": [...]}"""
    g = _gate(task)
    corpus = g.mloose(_policy_text(task))
    env = (paths.KB / task / "env.txt").read_text()
    data = g.mloose(env)
    known_addr = set(re.findall(r"[\w.+-]+@[\w.-]+\w", (env + _policy_text(task)).lower()))
    channels = {g._alias(c.get("name")) for c in g._slack()["channels"].values() if c.get("name")}
    slack_emails = {str((u.get("profile") or {}).get("email") or "").lower() for u in g._slack()["users"].values()}
    kept, dropped, log = [], [], []

    def drop(m: dict, why: str) -> None:
        m["enabled"] = False
        m["drop_reason"] = why
        dropped.append(m)

    for m in spec.get("messages") or []:
        key = str(m.get("key") or f"M{len(kept) + len(dropped) + 1}")
        m["key"] = key
        m["kinds"] = [k for k in m.get("kinds") or [] if k in KINDS]
        if m.get("status") not in ("required", "forbidden") or not m["kinds"]:
            drop(m, "bad status/kinds")
            continue
        m["to"] = [x.lower() for x in m.get("to") or [] if isinstance(x, str)]
        m["cc"] = [x.lower() for x in m.get("cc") or [] if isinstance(x, str)]
        unknown = [x for x in m["to"] + m["cc"] if x not in known_addr]
        if unknown:
            drop(m, f"recipients not in data/SOP: {unknown}")
            continue
        if "slack_dm" in m["kinds"] and any(x not in slack_emails for x in m["to"]):
            drop(m, "DM recipient is not a Slack user")
            continue
        if m.get("channel") and "slack_post" in m["kinds"] and g._alias(m["channel"]) not in channels:
            drop(m, f"channel #{m['channel']} not in Slack seed")
            continue
        # quotes: verbatim SOP message text only
        quotes = []
        for q in m.get("quotes") or []:
            text = str((q or {}).get("text") or "")
            rx = g.quote_rx(text)
            literal = g.PH.sub(" ", text)
            if rx is None:
                log.append(f"{key}: quote too short {text[:60]!r}")
            elif _INSTRUCTION.search(literal):
                log.append(f"{key}: instruction-like quote dropped {text[:60]!r}")
            elif not rx.search(corpus):
                log.append(f"{key}: quote not in SOP {text[:60]!r}")
            else:
                quotes.append({"text": text, "block": q.get("block", "")})
        m["quotes"] = quotes
        m["values"] = [v for v in (str(x) for x in m.get("values") or []) if g.mloose(v) and g.mloose(v) in data]
        for k in ("subject_rx",):
            try:
                re.compile(m.get(k) or "")
            except re.error:
                m[k] = ""
        sample = _act(g, m.get("sample"))
        if not g.msg_about(m, sample):
            drop(m, "spec does not recognise its own sample")
            continue
        if m["status"] == "forbidden":
            allowed = [_act(g, x) for x in m.get("allowed") or []]
            if not allowed or any(g.msg_about(m, x) for x in allowed):
                drop(m, "forbidden spec lacks allowed look-alikes or catches them")
                continue
        else:
            # requirements the author's own correct message does not meet are not certain: remove them
            for attempt in range(2):
                probs = g.msg_problems(m, sample)
                if not probs:
                    break
                if any(p.startswith(("Send it to", "CC ", "Remove recipients", "Post it in")) for p in probs):
                    drop(m, f"sample contradicts routing: {probs}")
                    break
                hay = g.mloose(sample.subject + "\n" + sample.text)
                m["quotes"] = [q for q in m["quotes"] if g.quote_rx(q["text"]).search(hay)]
                m["values"] = [v for v in m["values"] if g.mloose(v) in hay]
                if any(p.startswith("Subject must") for p in probs):
                    m["subject_rx"] = ""
                if any(p.startswith("Attach") for p in probs):
                    m["attach"] = []
                log.append(f"{key}: removed requirements its sample fails (round {attempt + 1}): {probs}")
            if m.get("enabled") is False:
                continue
        m["enabled"] = True
        m["pre"] = True
        kept.append(m)
    # a forbidden spec must not catch any message the task requires
    required = [_act(g, m.get("sample")) for m in kept if m["status"] == "required"]
    for m in [m for m in kept if m["status"] == "forbidden"]:
        if any(g.msg_about(m, s) for s in required):
            kept.remove(m)
            drop(m, "forbidden spec catches a required message")
    # exclusivity: a required spec that recognises another required message cannot be used to vet messages (two
    # specs would demand different content from one message); overlap with a forbidden example is intended
    samples = {m["key"]: _act(g, m.get("sample")) for m in kept if m["status"] == "required"}
    for m in kept:
        if m["status"] != "required":
            continue
        clash = [k for k, s in samples.items() if k != m["key"] and g.msg_about(m, s)]
        if clash:
            m["pre"] = False
            log.append(f"{m['key']}: recognises samples of {clash}; pre-call check disabled")
    return {"messages": kept, "dropped": dropped, "log": log, "checklist": g.checklist_text(kept)}


def templates_text(kb: dict) -> str:
    out = []
    for t in kb.get("templates", []):
        if t.get("kind") in ("email", "slack", "dm", "other"):
            out.append(f"{t['id']} [{t.get('kind')}] {t.get('title')} | channel={t.get('channel', '')} "
                       f"to={t.get('to', [])} | subject={t.get('subject', '')!r}\n  body={t.get('body', '')[:900]!r}")
    return "\n".join(out)


def compile_messages(task: str) -> dict[str, Any]:
    kb = json.loads((paths.KB / task / "kb.json").read_text())
    plan_p = paths.KB / task / f"plan_{TIER}.txt"
    inputs = INPUTS.format(corpus=(paths.KB / task / "k0" / "policy.md").read_text(), templates=templates_text(kb),
                           env=(paths.KB / task / "env.txt").read_text())
    prompt = PROMPT.format(inputs=inputs, plan=plan_p.read_text() if plan_p.exists() else "(none)")
    t0 = time.time()
    spec = llm.chat_json(AUTHOR, [{"role": "user", "content": prompt}], max_tokens=24000, cache="messages",
                         timeout=2700)
    res = validate(spec, task)
    out = {"task": task, "tier": TIER, "author": AUTHOR, "secs": round(time.time() - t0), **res}
    (paths.KB / task / f"messages_{TIER}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return {"task": task, "secs": out["secs"], "kept": len(res["messages"]), "dropped": len(res["dropped"]),
            "pre_off": sum(not m["pre"] for m in res["messages"]),
            "required": sum(m["status"] == "required" for m in res["messages"]),
            "forbidden": sum(m["status"] == "forbidden" for m in res["messages"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--split", default="all", choices=("dev", "test", "all"))
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    tasks = a.tasks.split(",") if a.tasks else [t for t in paths.all_tasks()
                                                 if a.split == "all" or paths.split(t) == a.split]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(compile_messages, t): t for t in tasks}
        for f in cf.as_completed(futs):
            try:
                print(json.dumps(f.result()), flush=True)
            except Exception as e:  # noqa: BLE001 - one task's failure must not stop the batch
                print(json.dumps({"task": futs[f], "error": f"{type(e).__name__}: {e}"[:300]}), flush=True)


if __name__ == "__main__":
    main()
