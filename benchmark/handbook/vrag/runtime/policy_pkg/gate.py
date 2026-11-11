"""vrag gate: deterministic interwhen checks driven by the compiled PolicyKB (+ optional compiled guards).

Runs inside the container as an OpenHands command hook (``python -m gate pre|stop``, /app/.venv python, stdin =
HookEvent JSON) and as ``dry_run`` behind the policy__check tool. Prints {"decision": "allow"|"deny", "reason"}.
Precision first: every check fails open on errors, each finding key has a denial budget, and only clear
violations of compiled SOP data block a call.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

PKG = Path(os.environ.get("VRAG_PKG", Path(__file__).resolve().parent))
STATE = Path(os.environ.get("VRAG_STATE", "/logs/agent/vrag"))
SEED = Path(os.environ.get("VRAG_SEED", "/initial_data"))
BUDGET_PER_KEY = int(os.environ.get("VRAG_BUDGET", "2"))
STOP_BUDGET = int(os.environ.get("VRAG_STOP_BUDGET", "3"))

_DASH = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'",
                       "\u201c": '"', "\u201d": '"', "\u00a0": " "})


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").translate(_DASH)).strip().lower()


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


KB = load_json(PKG / "data" / "kb.json", {})
GUARDS = load_json(PKG / "data" / "guards.json", {})
MESSAGES = [m for m in load_json(PKG / "data" / "messages.json", {}).get("messages", []) if m.get("enabled", True)]
TEMPLATES = KB.get("templates", [])
COMM_KINDS = ("email_send", "email_reply", "email_forward", "email_draft", "slack_post", "slack_dm")


# ---- actions ------------------------------------------------------------------------------------------------------

@dataclass
class Act:
    tool: str
    kind: str
    args: dict
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    text: str = ""
    channel: str = ""
    files: list[str] = field(default_factory=list)
    project: str = ""
    people: list[str] = field(default_factory=list)  # DM recipients: normalised handles / names / emails

    @property
    def is_comm(self) -> bool:
        return self.kind in ("email_send", "email_reply", "email_forward", "email_draft", "slack_post", "slack_dm")

    @property
    def is_write(self) -> bool:
        return self.kind not in ("read", "other", "control")


def _addrs(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return [x.strip().lower() for x in re.split(r"[,;]", v) if x.strip()]
    if isinstance(v, dict):
        v = [v.get("email") or v.get("address") or ""]
    if not isinstance(v, list):
        v = [v]
    return [str(x.get("email") if isinstance(x, dict) else x).strip().lower() for x in v if x]


WRITE_MARK = re.compile(r"\.save\(|to_excel|to_csv|open\([^)]*['\"][wa]b?\+?['\"]|write_text|write_bytes|"
                        r"shutil\.(copy|move)|os\.(rename|replace|remove)|>\s*\S+|\b(cp|mv|rm|touch|tee|sed -i)\b")
FILE_RX = re.compile(r"[\w-]+(?:[ .][\w-]+)*\.(?:xlsx|xls|csv|docx|pdf|txt|json|md)", re.I)


def _attachments(a: dict) -> list[str]:
    v = a.get("attachments") or a.get("attachment_paths") or []
    if isinstance(v, str):
        v = [v]
    out = []
    for x in v if isinstance(v, list) else []:
        x = x.get("path") or x.get("filename") or "" if isinstance(x, dict) else x
        if x:
            out.append(str(x).split("/")[-1])
    return out


def _orig_email(email_id) -> dict:
    """Seed email a reply/forward refers to (its subject and sender are not in the call arguments)."""
    if email_id in (None, ""):
        return {}
    mail = load_json(SEED / "google_mail" / "inbox.json", {})
    for e in mail.get("emails", []) if isinstance(mail, dict) else []:
        if str(e.get("email_id")) == str(email_id):
            return e
    return {}


def _alias(s) -> str:
    """Identity key for channels/people: case-, '#'/'@'- and punctuation-insensitive."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


_SLACK: dict | None = None


def _slack() -> dict:
    """Slack users and channels (live mock state if present, else the task seed), loaded once per process."""
    global _SLACK
    if _SLACK is None:
        _SLACK = {"users": {}, "channels": {}}
        for p in (Path("/data/slack/final.json"), Path("/data/slack/slack.json"), SEED / "slack" / "slack.json"):
            d = load_json(p, {})
            if not isinstance(d, dict):
                continue
            for key in ("users", "channels"):
                v = d.get(key) or {}
                items = v.items() if isinstance(v, dict) else ((str(x.get("id", "")), x) for x in v)
                for k, x in items:
                    if isinstance(x, dict):
                        _SLACK[key].setdefault(str(k), x)
    return _SLACK


def slack_user(uid: str) -> dict:
    """{'email': str, 'aliases': [...]} for a Slack user id; unknown ids resolve to themselves."""
    u = _slack()["users"].get(str(uid)) or {}
    prof = u.get("profile") or {}
    email = str(prof.get("email") or u.get("email") or "").lower()
    names = [u.get("name"), u.get("real_name"), prof.get("real_name"), prof.get("display_name"),
             email.split("@")[0] if email else "", str(uid)]
    return {"email": email, "aliases": sorted({_alias(n) for n in names if n})}


def _dm_user_ids(a: dict, tool_name: str) -> list[str]:
    """User ids a Slack call addresses directly: send_dm/send_mpim recipients, or a post into a user/IM channel."""
    if tool_name in ("send_dm", "send_mpim"):
        v = a.get("user_id") or a.get("user_ids") or a.get("users") or []
        v = re.split(r"[,\s]+", v) if isinstance(v, str) else v
        return [str(x) for x in v if x]
    ch = str(a.get("channel_id") or a.get("channel") or "")
    if re.fullmatch(r"U[A-Z0-9_]+", ch):
        return [ch]
    c = _slack()["channels"].get(ch) or {}
    if ch.startswith("D") and (c.get("is_im") or c.get("user")):
        return [str(c["user"])] if c.get("user") else []
    return []


def classify(tool: str, args: dict) -> Act:
    t = tool.split("__")[-1] if "__" in tool else tool
    svc = tool.split("__")[0] if "__" in tool else ""
    a = args.get("data") if isinstance(args.get("data"), dict) else args
    if t in ("think", "finish"):
        return Act(tool, "control", a)
    if svc == "google_mail":
        if t == "send_email":
            return Act(tool, "email_send", a, _addrs(a.get("to")), _addrs(a.get("cc")), a.get("subject") or "",
                       a.get("body") or a.get("html_body") or "", files=_attachments(a))
        if t in ("reply_email", "reply_to_email"):
            o = _orig_email(a.get("email_id"))
            return Act(tool, "email_reply", a, _addrs(a.get("to")) or _addrs(o.get("from_addr")),
                       subject=a.get("subject") or (f"Re: {o['subject']}" if o.get("subject") else ""),
                       text=a.get("body") or a.get("html_body") or "", files=_attachments(a))
        if t == "forward_email":
            o = _orig_email(a.get("email_id"))  # a forward carries the original's attachments
            return Act(tool, "email_forward", a, _addrs(a.get("to")),
                       subject=a.get("subject") or (f"Fwd: {o['subject']}" if o.get("subject") else ""),
                       text=a.get("body") or "", files=_attachments(a) + _attachments(o))
        if t in ("save_draft", "update_draft"):
            return Act(tool, "email_draft", a, _addrs(a.get("to")), _addrs(a.get("cc")), a.get("subject") or "",
                       a.get("body") or a.get("html_body") or "")
        if re.match(r"(move|mark|delete|create|edit|add)_", t):
            return Act(tool, "mail_admin", a)
        return Act(tool, "read", a)
    if svc == "slack":
        if t in ("post_message", "reply_to_thread", "send_dm", "send_mpim"):
            uids = _dm_user_ids(a, t)
            if not uids:
                return Act(tool, "slack_post", a, text=a.get("text") or "",
                           channel=str(a.get("channel_id") or a.get("channel") or ""))
            users = [slack_user(u) for u in uids]
            return Act(tool, "slack_dm", a, to=[u["email"] for u in users if u["email"]], text=a.get("text") or "",
                       people=sorted({x for u in users for x in u["aliases"]}))
        if t == "add_reaction":
            return Act(tool, "slack_admin", a)
        return Act(tool, "read", a)
    if svc == "jira":
        if t == "create_issue":
            return Act(tool, "jira_create", a, subject=a.get("summary") or "", text=json.dumps(a, ensure_ascii=False),
                       project=str(a.get("project_key") or ""))
        if t in ("update_issue", "transition_issue", "add_comment", "link_issues", "delete_issue"):
            return Act(tool, f"jira_{t}", a, text=json.dumps(a, ensure_ascii=False),
                       project=str(a.get("issue_key") or "").split("-")[0])
        return Act(tool, "read", a)
    if svc == "google_calendar":
        if t in ("create_event", "update_event", "delete_event"):
            return Act(tool, f"cal_{t}", a, subject=a.get("summary") or "", text=json.dumps(a, ensure_ascii=False))
        return Act(tool, "read", a)
    if t in ("executeBash", "executePython", "writeFile"):
        code = a.get("command") or a.get("code") or a.get("content") or ""
        if t == "writeFile":
            path = str(a.get("file_path") or a.get("path") or a.get("filename") or "")
            return Act(tool, "file_write", a, text=str(a.get("content", ""))[:5000],
                       files=[path.split("/")[-1]] if path else [])
        if WRITE_MARK.search(code):
            files = sorted({m.group(0).strip().split("/")[-1] for m in FILE_RX.finditer(code)})
            return Act(tool, "file_write" if files else "code", a, text=code, files=files)
        return Act(tool, "code", a, text=code)
    if svc == "policy":
        return Act(tool, "read", a)
    return Act(tool, "other", a)


# ---- world ----------------------------------------------------------------------------------------------------

def ledger() -> list[dict]:
    p = STATE / "ledger.jsonl"
    out = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def _payload(text: str):
    """JSON body of a tool observation ('[Tool 'x' executed.]{...}'), or None."""
    body = re.sub(r"^\s*\[Tool '[^']*' executed\.\]\s*", "", text or "")
    starts = [i for i in (body.find("{"), body.find("[")) if i >= 0]
    if not starts:
        return None
    try:
        return json.JSONDecoder().raw_decode(body[min(starts):])[0]
    except json.JSONDecodeError:
        return None


def succeeded(text: str) -> bool:
    """Whether a tool observation reports success (structured result first, wording heuristics as fallback)."""
    p = _payload(text)
    if isinstance(p, dict):
        if p.get("ok") is False or p.get("success") is False or p.get("error") or \
                str(p.get("status", "")).lower() in ("error", "failed", "failure"):
            return False
        return p.get("returncode") in (None, 0) and p.get("exit_code") in (None, 0)
    return not (len(text or "") < 400 and re.search(r"\b(error|failed|not found|invalid)\b", text or "", re.I))


def executed(led: list[dict]) -> list[Act]:
    """Write actions that ran successfully: an observation followed, no rejection, and no reported tool error."""
    obs = {r.get("call_id"): r for r in led if r.get("type") == "observation"}
    rej = {r.get("call_id") for r in led if r.get("type") == "rejection"}
    out = []
    for r in led:
        cid = r.get("call_id")
        if r.get("type") == "action" and cid in obs and cid not in rej and succeeded(obs[cid].get("text", "")):
            out.append(classify(r.get("tool") or "", r.get("args") or {}))
    return out


def slack_channels() -> dict[str, str]:
    return {cid: str(c.get("name")) for cid, c in _slack()["channels"].items() if c.get("name")}


def channel_name(ch: str) -> str:
    ch = str(ch or "")
    return slack_channels().get(ch, ch).lstrip("#").lower()


# ---- templates ------------------------------------------------------------------------------------------------

PH = re.compile(r"\[[^\[\]]{1,120}\]")
TAG_RX = re.compile(r"\s*(\[[A-Z0-9][A-Z0-9 /&\-_.]{1,40}\])")


def tpl_tag(t: dict) -> str | None:
    m = TAG_RX.match(t.get("body") or "")
    return m.group(1) if m else None


TAGS = {x for x in (tpl_tag(t) for t in TEMPLATES) if x}


def _tag_tokens() -> set[str]:
    """Bracket tokens that sit in tag position (start of a subject, body or line) in any template: literal tags."""
    out = set()
    for t in TEMPLATES:
        for field_ in (t.get("subject") or "", t.get("body") or ""):
            for line in field_.split("\n"):
                m = re.match(r"\s*(?:re:\s*|fw:\s*)?(\[[^\[\]]{1,60}\])", line, re.I)
                if m:
                    out.add(m.group(1))
    return out


def placeholder_names() -> set[str]:
    """Only placeholders the compiler declared, minus anything that is used as a literal tag somewhere."""
    tagpos = _tag_tokens() | TAGS
    out = set()
    for t in TEMPLATES:
        for k in (t.get("placeholders") or {}):
            k = k.strip()
            if k.startswith("[") and k.endswith("]"):
                out.add(k)
    return {p for p in out if p not in tagpos and not re.fullmatch(r"\[\s*[xX ]?\s*\]", p)}


PLACEHOLDERS = placeholder_names()


def segments(text: str, min_len: int = 6) -> list[str]:
    # bracketed/braced placeholders and bare ALL-CAPS identifiers (CASEID, CARC) are variable slots; an ALL-CAPS
    # word followed by ':' is a literal field label ("NPI:", "DOS:") and stays part of the required text
    parts = re.split(r"\[[^\[\]]{1,120}\]|\{[^}\n]{1,60}\}|<[^>\n]{1,60}>|\b[A-Z][A-Z0-9_]{2,}\b(?!\s*:)",
                     text or "")
    out = []
    for p in parts:
        for line in p.split("\n"):
            s = norm(line).strip(" .,:;|")
            if len(s) >= min_len and re.search(r"[a-z]{2}", s):
                out.append(s)
    return out


def _nows(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _loose(s: str) -> str:
    """Formatting-insensitive form for required-text checks: case, dashes, whitespace, thousands separators."""
    return _nows(re.sub(r"(?<=\d),(?=\d{3}\b)", "", norm(s)))


def missing_in_order(segs: list[str], text: str) -> list[str]:
    """Literal segments not found in order; whitespace-insensitive (PDF extraction often drops/adds spaces)."""
    t = _nows(norm(text))
    pos, miss = 0, []
    for s0 in segs:
        s = _nows(s0)
        i = t.find(s, pos)
        if i < 0:
            i = t.find(s)
            if i < 0:
                miss.append(s0)
                continue
        pos = i + len(s)
    return miss


def tpl_channel(t: dict) -> str:
    m = re.search(r"#([\w-]+)", t.get("channel") or "")
    return m.group(1).lower() if m else ""


# ---- findings / budgets -----------------------------------------------------------------------------------------

@dataclass
class Finding:
    key: str
    problem: str
    fix: str = ""
    source: str = ""


def budget_ok(key: str, cap: int) -> bool:
    return load_json(STATE / "budget.json", {}).get(key, 0) < cap


def cap(key: str) -> int:
    """Compiled guards (g:*) and duplicate checks block once: the agent is told it may repeat the identical call
    after re-checking, so a wrong block costs one turn, not the task. Format/placeholder checks block up to
    BUDGET_PER_KEY times."""
    return 1 if key.startswith(("g:", "dup", "mf:")) else BUDGET_PER_KEY


def spend(keys: list[str]) -> None:
    p = STATE / "budget.json"
    b = load_json(p, {})
    for k in keys:
        b[k] = b.get(k, 0) + 1
    STATE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(b))


def cite(blocks: list[str]) -> str:
    return f" (SOP {blocks[0]})" if blocks else ""


# ---- checks -----------------------------------------------------------------------------------------------------

def check_placeholders(a: Act) -> list[Finding]:
    if not a.is_comm:
        return []
    left = sorted({m.group(0) for m in PH.finditer(a.subject + "\n" + a.text)} & PLACEHOLDERS)
    if not left:
        return []
    return [Finding("placeholders", f"The message still contains unfilled template placeholders {left}.",
                    "Replace every placeholder with the actual value before sending.")]


def check_slack_format(a: Act) -> list[Finding]:
    if a.kind not in ("slack_post", "slack_dm"):
        return []
    out = []
    used = [t for t in TEMPLATES if tpl_tag(t) and norm(tpl_tag(t)) in norm(a.text)]
    for t in used[:2]:
        miss = missing_in_order(segments(t.get("body", ""), 3), a.text)
        if miss:
            out.append(Finding(f"fmt:{t['id']}", f"This {tpl_tag(t)} message does not follow the SOP format; "
                                                 f"missing/changed parts: {miss[:4]}.",
                               f"Use exactly: {t.get('body', '').strip()[:400]}", cite(t.get("blocks", []))))
        want, got = tpl_channel(t), channel_name(a.channel)
        known = {c.lstrip("#").lower().replace("-", "") for c in slack_channels().values()}
        if want and want.replace("-", "") not in known:
            want = ""
        if want and a.kind == "slack_post" and got and want.replace("-", "") != got.replace("-", ""):
            out.append(Finding(f"chan:{t['id']}", f"{tpl_tag(t)} messages go to #{want} per the SOP, not #{got}.",
                               f"Post it in #{want}.", cite(t.get("blocks", []))))
    return out


def check_email_format(a: Act) -> list[Finding]:
    if a.kind not in ("email_send", "email_draft") or not a.subject:
        return []
    out = []
    t = _subject_template(a.subject)
    if t:
        subj = t.get("subject") or ""
        segs = segments(subj, 6)
        miss = missing_in_order(segs, a.subject)
        if miss:
            out.append(Finding(f"subj:{t['id']}", f"Subject does not follow the SOP format ({t['title']}); "
                                                  f"missing/changed: {miss[:3]}.", f"Use the subject format: {subj}",
                               cite(t.get("blocks", []))))
        want = [x.lower().strip() for x in t.get("to", []) if re.fullmatch(r"[^@\s]+@[^@\s]+\.\w+", x.strip())]
        if want and not set(want) & set(a.to + a.cc):
            out.append(Finding(f"to:{t['id']}", f"'{t['title']}' goes to {want} per the SOP.",
                               f"Address it to {', '.join(want)}.", cite(t.get("blocks", []))))
    return out


_LEAD_TAG = re.compile(r"\s*(?:(?:re|fw|fwd)\s*:\s*)*\[([^\[\]]{2,60})\]", re.I)


def _tagkey(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _subject_template(subject: str) -> dict | None:
    """The one template whose subject format this subject is clearly using, else None (precision first).
    A leading ALL-CAPS bracket token is a literal tag ([CLAIM SUBMISSION]); when the template has one, the
    subject's tag must match it (spacing-insensitive). Otherwise the first literal segment must match, and
    the choice must be unique."""
    m = _LEAD_TAG.match(subject or "")
    stag = _tagkey(m.group(1)) if m else ""
    tagged, untagged = [], []
    for t in TEMPLATES:
        subj = t.get("subject") or ""
        if not segments(subj, 6) and not _LEAD_TAG.match(subj):
            continue
        tm = _LEAD_TAG.match(subj)
        ttag = tm.group(1) if tm else ""
        if ttag and ttag.strip() == ttag.strip().upper() and re.search(r"[A-Z]{2}", ttag):
            if stag and _tagkey(ttag) == stag:
                tagged.append(t)
        elif not stag:
            segs = segments(subj, 6)
            if segs and len(segs[0]) >= 10 and _nows(segs[0]) in _nows(norm(subject)):
                untagged.append(t)
    cands = tagged or untagged
    return cands[0] if len(cands) == 1 else None


def _sig(a: Act) -> tuple:
    ref = str(a.args.get("email_id") or a.args.get("thread_ts") or a.args.get("user_id") or "")
    return (a.kind, ref, tuple(sorted(a.to)), channel_name(a.channel), norm(a.subject), norm(a.text)[:500])


def check_duplicate(a: Act, done: list[Act]) -> list[Finding]:
    if not a.is_comm or a.kind == "email_draft":
        return []
    if any(_sig(d) == _sig(a) for d in done):
        return [Finding("dup", "This exact message was already sent; sending it again would duplicate it.",
                        "Do not resend it.")]
    return []


def _match(spec: dict, a: Act) -> bool:
    """Guard match spec keys: kinds, channel, to_any, subject_rx, text_rx, file_rx, project (all must hold)."""
    if not spec:
        return False
    kinds = spec.get("kinds") or []
    if kinds and a.kind not in kinds:
        return False
    if spec.get("channel") and _alias(spec["channel"]) not in {_alias(channel_name(a.channel)), *a.people}:
        return False
    if spec.get("to_any"):
        want = {str(x).lower() for x in spec["to_any"]}
        if not (want & set(a.to + a.cc) or {_alias(x) for x in want} & set(a.people)):
            return False
    for k, val in (("subject_rx", a.subject), ("text_rx", a.subject + "\n" + a.text)):
        if spec.get(k):
            try:
                v = val.translate(_DASH)
                # also accept the pattern on a bracket-free variant ("[CLAIM SUBMISSION] X" ~ "CLAIM SUBMISSION X")
                if not any(re.search(spec[k], x, re.I | re.S) for x in (v, re.sub(r"[\[\]]", "", v))):
                    return False
            except re.error:
                return False
    if spec.get("file_rx"):
        try:
            if not any(re.search(spec["file_rx"], f, re.I) for f in a.files):
                return False
        except re.error:
            return False
    if spec.get("project") and a.project.lower() != str(spec["project"]).lower():
        return False
    return True


def _seed_messages() -> list[dict]:
    msgs = []
    mail = load_json(SEED / "google_mail" / "inbox.json", {})
    for e in mail.get("emails", []) if isinstance(mail, dict) else []:
        msgs.append({"from": str(e.get("from_addr", "")).lower(),
                     "text": f"{e.get('subject', '')}\n{e.get('body_text', '')}"})
    sl = load_json(SEED / "slack" / "slack.json", {})
    users = sl.get("users", {}) if isinstance(sl, dict) else {}
    for _, lst in (sl.get("messages", {}) if isinstance(sl, dict) else {}).items():
        for m in lst or []:
            if not isinstance(m, dict):
                continue
            u = users.get(m.get("user"), {}) or {}
            who = " ".join(str(x) for x in (u.get("real_name"), u.get("name"),
                                            (u.get("profile") or {}).get("email")) if x).lower()
            msgs.append({"from": who, "text": m.get("text", "")})
    return msgs


def authorized(people: list[str], about_rx: str) -> bool:
    """True if a seed mail/Slack message from an authorized person mentions the subject of the action."""
    for m in _seed_messages():
        if not any(p in m["from"] for p in people):
            continue
        if not about_rx:
            return True
        try:
            if re.search(about_rx, m["text"], re.I):
                return True
        except re.error:
            return True
    return False


def _file_exists(file_rx: str) -> bool:
    """A prior file-write step also counts as done when a matching file exists in the live workspace (the agent
    may build file names in code, which the ledger cannot see)."""
    if not file_rx:
        return False
    root = Path(os.environ.get("VRAG_WORKDIR", "/workdir"))
    try:
        rx = re.compile(file_rx, re.I)
        return any(rx.search(str(p.relative_to(root))) for p in root.rglob("*") if p.is_file())
    except Exception:
        return True


def _addresses_authorizer(a: Act, people: list[str]) -> bool:
    """Messages sent to (or naming) an authorizer are requests for authorization/escalations, never blocked."""
    emails = {p for p in people if "@" in p}
    names = [p for p in people if "@" not in p]
    if emails & set(a.to + a.cc):
        return True
    if a.kind == "slack_post" and re.search(r"escalat|alert|complian|legal|mgmt|manag|supervis|director",
                                            channel_name(a.channel)):
        return True
    body = norm(a.subject + " " + a.text)
    return a.is_comm and any(n and (n in body or n.split()[-1] in body.split()) for n in names)


def check_guards(a: Act, done: list[Act]) -> list[Finding]:
    out = []
    for g in GUARDS.get("guards", []):
        if not g.get("enabled", True) or _superseded(g) or not _match(g.get("match") or {}, a):
            continue
        typ, src = g.get("type"), cite(g.get("blocks", []))
        msg, fix = g.get("message", ""), g.get("fix", "")
        if typ == "forbid":
            out.append(Finding(f"g:{g['id']}", msg or "This action is not allowed by the SOP.", fix, src))
        elif typ == "require_text":
            hay = _loose(a.subject + " " + a.text)
            miss = [x for x in g.get("must_contain", []) if _loose(x) not in hay]
            if miss:
                out.append(Finding(f"g:{g['id']}", msg or f"Required text missing: {miss}",
                                   fix or f"Include exactly: {miss}", src))
        elif typ == "require_prior":
            prior = g.get("prior") or {}
            if not any(_match(prior, d) for d in done) and not _file_exists(prior.get("file_rx", "")):
                out.append(Finding(f"g:{g['id']}", msg or "A required earlier SOP step was not done.", fix, src))
        elif typ == "require_authorization":
            people = [p.lower() for p in g.get("people", []) if p]
            asks = _addresses_authorizer(a, people)
            if people and not asks and not authorized(people, g.get("about_rx", "")):
                out.append(Finding(f"g:{g['id']}", msg or "No written authorization from an authorized person "
                                                          "was found for this action.",
                                   fix or f"Act only on written authorization from: {', '.join(people)}.", src))
    return out


def _xlsx_rows(file_rx: str) -> list[tuple[str, dict]]:
    """Rows of every live workbook under /workdir whose path matches file_rx: (path, {header: value})."""
    import openpyxl

    out = []
    root = Path(os.environ.get("VRAG_WORKDIR", "/workdir"))
    for p in sorted(root.rglob("*.xlsx")):
        rel = str(p.relative_to(root))
        try:
            if not re.search(file_rx, rel, re.I):
                continue
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        except Exception:
            continue
        for ws in wb.worksheets:
            header = None
            for r in ws.iter_rows(values_only=True):
                vals = ["" if c is None else (c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c))
                        for c in r]
                if header is None:
                    if sum(bool(v.strip()) for v in vals) >= 2:
                        header = [norm(v) for v in vals]
                    continue
                if any(v.strip() for v in vals):
                    out.append((rel, dict(zip(header, vals, strict=False))))  # ragged rows are normal in xlsx
    return out


def _row_ok(row: dict, cond: dict) -> bool:
    for col, rx in (cond or {}).items():
        key = norm(col)
        val = next((v for k, v in row.items() if k == key), None)
        if val is None:
            val = next((v for k, v in row.items() if key in k), None)
        if val is None:
            return False
        try:
            if not re.search(rx, str(val).translate(_DASH), re.I):
                return False
        except re.error:
            if norm(rx) != norm(val):
                return False
    return True


# ---- message specs (one spec per required/forbidden message: checklist, pre-call check and completion) -----------

_BULLETS = str.maketrans("", "", "\u2022\u25aa\u25cf\u25cb\u25e6\u25a0*_#>`")


def mloose(s: str) -> str:
    """Message-comparison form: case/dash/quote-folded, no whitespace, bullets or markdown, no thousands commas
    (PDF extraction drops and inserts spaces; agents re-flow lines and add markdown)."""
    return _loose(str(s or "").translate(_BULLETS))


def quote_rx(quote: str) -> re.Pattern | None:
    """Regex over mloose() text for an SOP quote whose [Placeholders] may be filled with anything (<=300 chars)."""
    chunks = [mloose(c) for c in PH.split(quote or "")]
    chunks = [c for c in chunks if len(c) >= 3]
    if sum(map(len, chunks)) < 12:
        return None
    return re.compile(".{0,300}?".join(re.escape(c) for c in chunks), re.S)


def _superseded(spec: dict) -> bool:
    """Communication guards/obligations are replaced by message specs when the task has any."""
    kinds = (spec.get("match") or {}).get("kinds") or []
    return bool(MESSAGES) and bool(kinds) and all(k in COMM_KINDS for k in kinds)


def msg_about(m: dict, a: Act) -> bool:
    return _match({"kinds": m.get("kinds") or [], **(m.get("about") or {})}, a)


def msg_problems(m: dict, a: Act) -> list[str]:
    """What is wrong with action ``a`` as an instance of message spec ``m`` (empty = conforms)."""
    out: list[str] = []
    have = set(a.to + a.cc)
    miss_to = [x for x in m.get("to") or [] if x.lower() not in set(a.to) | (have if a.kind == "slack_dm" else set())]
    if a.kind == "slack_dm":
        miss_to = [x for x in miss_to if _alias(x.split("@")[0]) not in a.people and _alias(x) not in a.people]
    if miss_to:
        out.append(f"Send it to {', '.join(miss_to)}.")
    miss_cc = [x for x in m.get("cc") or [] if x.lower() not in have]
    if miss_cc:
        out.append(f"CC {', '.join(miss_cc)}.")
    if m.get("exact_to"):
        extra = sorted(have - {x.lower() for x in (m.get("to") or []) + (m.get("cc") or [])})
        if extra:
            out.append(f"Remove recipients the SOP does not route this to: {', '.join(extra)}.")
    if m.get("channel") and a.kind == "slack_post" and _alias(channel_name(a.channel)) != _alias(m["channel"]):
        out.append(f"Post it in #{m['channel'].lstrip('#')} (not #{channel_name(a.channel)}).")
    if m.get("subject_rx"):
        try:
            if not re.search(m["subject_rx"], a.subject.translate(_DASH), re.I | re.S):
                out.append(f"Subject must follow the SOP format: {m.get('subject_hint') or m['subject_rx']}"
                           f" (got {a.subject!r}).")
        except re.error:
            pass
    hay = mloose(a.subject + "\n" + a.text)
    for q in m.get("quotes") or []:
        rx = quote_rx(q.get("text", ""))
        if rx is not None and not rx.search(hay):
            out.append(f"Missing the SOP wording: \"{' '.join(q['text'].split())[:200]}\".")
    miss_v = [v for v in m.get("values") or [] if mloose(v) and mloose(v) not in hay]
    if miss_v:
        out.append(f"Missing these details: {', '.join(miss_v)}.")
    for at in m.get("attach") or []:
        try:
            if not any(re.search(at.get("rx", ""), f, re.I) for f in a.files):
                out.append(f"Attach {at.get('desc') or at.get('rx')}.")
        except re.error:
            pass
    return out


def _msg_hint(m: dict) -> str:
    bits = []
    if m.get("to"):
        bits.append(("DM to " if "slack_dm" in (m.get("kinds") or []) else "to ") + ", ".join(m["to"]))
    if m.get("cc"):
        bits.append("cc " + ", ".join(m["cc"]))
    if m.get("channel") and "slack_post" in (m.get("kinds") or []):
        bits.append(f"in #{m['channel'].lstrip('#')}")
    if m.get("subject_hint"):
        bits.append(f"subject \"{m['subject_hint']}\"")
    if m.get("quotes"):
        bits.append("with the SOP wording " + "; ".join(f"\"{' '.join(q['text'].split())[:120]}\""
                                                        for q in m["quotes"]))
    if m.get("values"):
        bits.append("stating " + ", ".join(m["values"]))
    if m.get("attach"):
        bits.append("attaching " + ", ".join(x.get("desc") or x.get("rx", "") for x in m["attach"]))
    return "; ".join(bits)


def check_messages(a: Act, done: list[Act]) -> list[Finding]:
    if not a.is_comm:
        return []
    out = []
    for m in MESSAGES:
        if not m.get("pre", True) or not msg_about(m, a):
            continue
        src = cite(m.get("blocks", []))
        if m.get("status") == "forbidden":
            out.append(Finding(f"mf:{m['key']}", f"{m.get('what', 'This message')} must not be sent: "
                                                 f"{m.get('why', '')}", "Do not send this message.", src))
            continue
        probs = msg_problems(m, a)
        if not probs and sum(msg_about(m, d) and not msg_problems(m, d) for d in done) >= int(m.get("max_count", 1)):
            probs = [f"This message ({m.get('what', '')}) was already sent; do not send it again."]
        if probs:
            out.append(Finding(f"m:{m['key']}", f"{m.get('what', 'Message')}: " + " ".join(probs),
                               "Fix the message as listed and send it again.", src))
    return out


def message_obligations(done: list[Act]) -> list[Finding]:
    out = []
    for m in MESSAGES:
        if m.get("status") != "required" or not m.get("completion", True):
            continue
        if any(msg_about(m, d) and not msg_problems(m, d) for d in done):
            continue
        out.append(Finding(f"m:{m['key']}", f"Not yet done per the SOP: {m.get('what', '')}.",
                           f"Send it ({_msg_hint(m)}).", cite(m.get("blocks", []))))
    return out


def checklist_text(messages: list[dict]) -> str:
    """Prompt section listing what the checker verifies (rendered offline into the policy package)."""
    req = [m for m in messages if m.get("status") == "required" and m.get("enabled", True)]
    forb = [m for m in messages if m.get("status") == "forbidden" and m.get("enabled", True) and m.get("pre", True)]
    if not (req or forb):
        return ""
    lines = ["MESSAGES THE SOP CHECKER WILL VERIFY (derived from the SOP and this workspace's data; each outgoing "
             "message is checked before it is sent and the task cannot finish until the required ones are sent):"]
    lines += [f"- SEND: {m.get('what', '')} ({_msg_hint(m)})" for m in req]
    lines += [f"- DO NOT SEND: {m.get('what', '')} - {m.get('why', '')}" for m in forb]
    return "\n".join(lines)


def obligations(led: list[dict]) -> list[Finding]:
    """Completion obligations from compiled guards. type 'action' (default): a matching executed action must exist;
    'row': a live workbook row matching `where` must exist and satisfy `expect`; 'no_row': no row may match `where`."""
    done = executed(led)
    out = message_obligations(done)
    for g in GUARDS.get("obligations", []):
        if not g.get("enabled", True) or _superseded(g):
            continue
        typ = g.get("type", "action")
        try:
            if typ == "action":
                ok = any(_match(g.get("match") or {}, d) for d in done)
            elif typ == "row":
                rows = [r for _, r in _xlsx_rows(g.get("file_rx", "."))]
                ok = any(_row_ok(r, g.get("where")) and _row_ok(r, g.get("expect")) for r in rows)
            elif typ == "no_row":
                ok = not any(_row_ok(r, g.get("where")) for _, r in _xlsx_rows(g.get("file_rx", ".")))
            else:
                ok = True
        except Exception:
            ok = True
        if not ok:
            fix = g.get("fix", "")
            if typ == "action":
                near = _near_miss(g.get("match") or {}, done)
                if near:
                    fix += (f" You already did a similar action ({near}) that does not satisfy this. If it is the same "
                            "item, correct that item (e.g. update its title/summary/text) instead of duplicating it.")
            out.append(Finding(f"o:{g['id']}", g.get("message", "A required SOP step is not done."),
                               fix.strip(), cite(g.get("blocks", []))))
    return out


def _near_miss(m: dict, done: list) -> str:
    """Most recent executed action of the same kind (and recipient/channel/project) as an unmet obligation."""
    loose = {k: v for k, v in m.items() if k in ("kinds", "channel", "to_any", "project") and v}
    if not loose.get("kinds"):
        return ""
    for d in reversed(done):
        try:
            if _match(loose, d):
                desc = d.subject or d.text
                return f"{d.kind}: {' '.join(str(desc).split())[:140]!r}"
        except Exception:
            continue
    return ""


# ---- entry points ---------------------------------------------------------------------------------------------

def log(entry: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "decisions.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": time.time(), **entry}, ensure_ascii=False, default=str) + "\n")


def evaluate(tool: str, args: dict, spend_budget: bool = True) -> tuple[str, list[Finding]]:
    a = classify(tool, args or {})
    if not a.is_write or a.kind in ("code", "control"):
        return "allow", []
    led = ledger()
    done = executed(led)
    findings: list[Finding] = []
    for fn in (lambda: check_placeholders(a), lambda: check_slack_format(a), lambda: check_email_format(a),
               lambda: check_duplicate(a, done), lambda: check_guards(a, done), lambda: check_messages(a, done)):
        try:
            findings += fn()
        except Exception:
            log({"stage": "error", "tb": traceback.format_exc()[-800:]})
    findings = [f for f in findings if budget_ok(f.key, cap(f.key))]
    if findings and spend_budget:
        spend([f.key for f in findings])
    return ("deny" if findings else "allow"), findings


def feedback(findings: list[Finding], blocked: bool = True) -> str:
    head = ("SOP CHECK (interwhen): this tool call was BLOCKED before execution - nothing was changed."
            if blocked else "SOP CHECK (interwhen): problems found:")
    lines = [head, ""]
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. {f.problem}{f.source}")
        if f.fix:
            lines.append(f"   Fix: {f.fix}")
    if blocked:
        lines += ["", "Correct the call and make it again (do not skip the step), unless the SOP says this action "
                      "must not be taken at all."]
        if any(f.key.startswith(("g:", "mf:")) for f in findings):
            lines.append("If, after re-reading the SOP section and the actual data, you are certain this exact call "
                         "is correct, repeat it unchanged and it will be allowed.")
    return "\n".join(lines)


def stop() -> dict:
    led = ledger()
    p = STATE / "stop_denials.json"
    hist = load_json(p, [])
    findings = obligations(led)
    stale = len(hist) >= 2 and hist[-1] <= len(findings) and hist[-2] <= len(findings)
    if not findings or len(hist) >= STOP_BUDGET or stale:
        log({"stage": "stop", "decision": "allow", "open": len(findings), "denials": len(hist)})
        return {"decision": "allow"}
    STATE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(hist + [len(findings)]))
    text = "SOP CHECK (interwhen): the task is not complete yet per the SOP.\n\n" + "\n".join(
        f"{i}. {f.problem}{f.source}" + (f"\n   Fix: {f.fix}" if f.fix else "") for i, f in enumerate(findings, 1))
    log({"stage": "stop", "decision": "deny", "findings": [f.__dict__ for f in findings]})
    return {"decision": "deny", "reason": text, "additionalContext": text}


def pre(event: dict) -> dict:
    tool = event.get("tool_name") or ""
    args = event.get("tool_input") or {}
    if tool == "finish":
        return stop()
    decision, findings = evaluate(tool, args)
    log({"stage": "pre", "tool": tool, "decision": decision, "findings": [f.__dict__ for f in findings]})
    if decision == "allow":
        return {"decision": "allow"}
    return {"decision": "deny", "reason": feedback(findings)}


def dry_run(tool_name: str, arguments: dict) -> str:
    try:
        decision, findings = evaluate(tool_name, arguments or {}, spend_budget=False)
    except Exception as e:
        return f"Checker error ({e}); proceed carefully."
    if decision == "allow":
        return "OK: no SOP problem detected by the checker (it does not prove full compliance)."
    return feedback(findings, blocked=False)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    try:
        event = json.loads(sys.stdin.read() or "{}")
        out = pre(event) if mode == "pre" else stop()
    except Exception:
        log({"stage": "error", "mode": mode, "tb": traceback.format_exc()[-1500:]})
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
