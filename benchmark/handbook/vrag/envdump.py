"""Fact sheet of everything the agent can observe at t=0 (seed tier, information parity with the interwhen
baseline): instruction, system prompt, clock, mailbox, Slack, calendar, Jira, Shopify, workbooks and case documents.
Never reads tests/."""

from __future__ import annotations

import json
import re
import sys
import tomllib

from . import paths


def _j(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def workbooks(task: str, max_rows: int = 120) -> str:
    import openpyxl

    out = []
    for p in sorted(paths.workspace(task).rglob("*.xlsx")):
        try:
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        except Exception as e:
            out.append(f"## {p.name}: unreadable ({e})")
            continue
        for ws in wb.worksheets:
            rows = []
            for r in ws.iter_rows(values_only=True):
                if any(c not in (None, "") for c in r):
                    rows.append(" | ".join("" if c is None else str(c) for c in r))
                if len(rows) >= max_rows:
                    rows.append(f"... ({ws.max_row} rows total)")
                    break
            out.append(f"## {p.relative_to(paths.workspace(task))} :: sheet {ws.title}\n" + "\n".join(rows))
    return "\n\n".join(out)


def mail(task: str) -> str:
    d = _j(paths.services(task) / "google_mail" / "inbox.json") or {}
    out = []
    for e in d.get("emails", []):
        att = [a.get("filename") if isinstance(a, dict) else str(a) for a in e.get("attachments") or []]
        out.append(f"[email {e.get('email_id')}] folder={e.get('folder')} read={e.get('is_read')} "
                   f"date={e.get('date')}\nFrom: {e.get('from_addr')}\nTo: {e.get('to_addr')}\nCc: {e.get('cc_addr')}\n"
                   f"Subject: {e.get('subject')}\nAttachments: {att}\n{(e.get('body_text') or '')[:4000]}")
    mb = d.get("mailbox", {})
    return f"Mailbox: {mb}\nContacts: {json.dumps(d.get('contacts', []))[:3000]}\n\n" + "\n\n".join(out)


def slack(task: str) -> str:
    d = _j(paths.services(task) / "slack" / "slack.json") or {}
    users = d.get("users", {})
    out = ["Users: " + "; ".join(f"{uid}={u.get('real_name')} ({(u.get('profile') or {}).get('title', '')}, "
                                 f"{(u.get('profile') or {}).get('email', '')})" for uid, u in users.items())]
    chans = d.get("channels", {})
    out.append("Channels: " + "; ".join(f"{cid}=#{c.get('name')}" for cid, c in chans.items()))
    for cid, msgs in (d.get("messages") or {}).items():
        name = chans.get(cid, {}).get("name", cid)
        for m in msgs or []:
            u = users.get(m.get("user"), {})
            out.append(f"[#{name} ts={m.get('ts')}] {u.get('real_name', m.get('user'))}: {m.get('text', '')[:2000]}")
    return "\n".join(out)


def other_services(task: str) -> str:
    out = []
    for name, fn in (("google_calendar", "calendar_data.json"), ("jira", "jira_state.json"),
                     ("shopify", "shopify_data.json")):
        d = _j(paths.services(task) / name / fn)
        if d:
            out.append(f"## {name}\n{json.dumps(d, ensure_ascii=False)[:25000]}")
    return "\n\n".join(out)


def dump(task: str, max_chars: int = 160_000) -> str:
    tdir = paths.TASKS / task
    toml = tomllib.loads((tdir / "task.toml").read_text())
    env = (toml.get("environment") or {}).get("env") or {}
    clock = next((v for k, v in env.items() if k.endswith("CURRENT_TIME")), "")
    cases = (paths.KB / task / "k0" / "cases.md")
    parts = [f"# TASK {task}", f"Clock (current time): {clock}",
             f"## System prompt\n{(tdir / 'system_prompt.md').read_text()}",
             f"## Instruction\n{(tdir / 'instruction.md').read_text()}",
             "## Workspace files\n" + "\n".join(str(p.relative_to(paths.workspace(task)))
                                                for p in sorted(paths.workspace(task).rglob('*')) if p.is_file()),
             f"## Mail\n{mail(task)}", f"## Slack\n{slack(task)}", other_services(task),
             f"## Workbooks\n{workbooks(task)}",
             f"## Case documents (text)\n{cases.read_text()[:60000] if cases.exists() else ''}"]
    text = "\n\n".join(p for p in parts if p)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text if len(text) <= max_chars else text[:max_chars] + "\n...[truncated]"


if __name__ == "__main__":
    for t in sys.argv[1:]:
        d = dump(t)
        (paths.KB / t).mkdir(parents=True, exist_ok=True)
        (paths.KB / t / "env.txt").write_text(d)
        print(t, len(d))
