"""Policy KB MCP server, mounted by the task container's MCP proxy as package ``policy`` (tools appear to the agent as
``policy__<name>``). Read-only over the compiled PolicyKB (data/kb.json) and the anchored K0 corpus
(data/corpus.json). Runs under the container's /app/.venv python (fastmcp 3.2).

Code mode (data/sop_code.json present): procedure/find/read return the compiled code that implements the SOP
blocks instead of their text (blocks without code fall back to text), and ``run`` executes a compiled procedure
on the facts of a case in a sandbox (sop_exec.py)."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
KB = json.loads((HERE / "data" / "kb.json").read_text())
DOCS = json.loads((HERE / "data" / "corpus.json").read_text())
BLOCKS = {b["id"]: {**b, "doc": d["name"], "role": d["role"]} for d in DOCS for b in d["blocks"]}
ORDER = [b["id"] for d in DOCS for b in d["blocks"]]
TPL = {t["id"]: t for t in KB.get("templates", [])}
PROC = {p["id"]: p for p in KB.get("procedures", [])}
MAXC = 12000
_CODE = json.loads((HERE / "data" / "sop_code.json").read_text()) if (HERE / "data" / "sop_code.json").exists() else {}
CODE = {pid: r for pid, r in (_CODE.get("procedures") or {}).items() if r.get("ok")}
SOURCE = _CODE.get("source", "compiled")
CODE_MAP: dict[str, list[str]] = {}
for _b, _ids in (_CODE.get("block_map") or {}).items():
    CODE_MAP[_b] = [i for i in ([_ids] if isinstance(_ids, str) else _ids) if i in CODE]
BY_FN = {r["fn"]: pid for pid, r in CODE.items() if r.get("runnable")}
SOFTSTOP = (HERE / "data" / "softstop").exists()
SCOPE = ("[applies to the item it names: do what it prescribes for that item, record what is pending, and complete "
         "every other required step and item]")
EXEC_ENV = Path(os.environ.get("VRAG_STATE", "/logs/agent/vrag")) / "exec_env.json"


def _covering(block_ids) -> list[str]:
    """Code units implementing any of these SOP blocks, in SOP order."""
    return list(dict.fromkeys(u for b in block_ids for u in CODE_MAP.get(b, [])))


def _code_view(pid: str, limit: int = 9000) -> str:
    """One code unit as the agent sees it."""
    r, p = CODE[pid], PROC.get(pid, {})
    ids = r.get("blocks") or []
    span = f"{ids[0]}..{ids[-1]}" if ids else ""
    if SOURCE == "verifiers":
        head = (f"CODE {pid}: {r.get('title', '')} (SOP blocks {span}) - the executable check this task is verified "
                "with; it states what the SOP requires here (recipients, subject/body wording, values, what must "
                "not happen, end-state conditions).")
    else:
        head = (f"PROCEDURE {pid}: {p.get('title', r.get('title', ''))} - compiled from the SOP (blocks {span}); "
                "every line cites the SOP blocks it implements. Shared names: TEMPLATES (policy__template), PEOPLE "
                "(policy__who), DEFINITIONS/CHANNELS/FILES/HOLIDAYS (policy__overview).")
    if r.get("runnable"):
        head += f' Run it on a case: policy__run("{r["fn"]}", {{case keys from the docstring}}, "YYYY-MM-DD").'
    return head + "\n```python\n" + _cut(r["code"], limit) + "\n```"


def _code_views(units: list[str], budget: int = 14000, most: int = 4) -> str:
    out, used = [], 0
    for u in units[:most]:
        v = _code_view(u, max(2000, budget - used))
        used += len(v)
        out.append(v)
        if used >= budget:
            break
    rest = units[len(out):]
    if rest:
        out.append("More code for this part of the SOP: " + ", ".join(rest) + " (policy__procedure('<id>')).")
    return "\n\n".join(out)


def _cut(s: str, n: int = MAXC) -> str:
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s) - n} more chars]"


def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", s.lower())


class BM25:
    def __init__(self, docs: list[tuple[str, str]]):
        self.ids = [i for i, _ in docs]
        self.toks = [_tok(t) for _, t in docs]
        self.df = Counter(w for t in self.toks for w in set(t))
        self.avg = sum(map(len, self.toks)) / max(1, len(self.toks))

    def search(self, q: str, k: int) -> list[tuple[str, float]]:
        qt = _tok(q)
        n = len(self.toks)
        scores = []
        for i, t in enumerate(self.toks):
            tf = Counter(t)
            s = 0.0
            for w in qt:
                if w in tf:
                    idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(t) / self.avg))
            if s > 0:
                scores.append((self.ids[i], s))
        return sorted(scores, key=lambda x: -x[1])[:k]


def _btext(b: dict) -> str:
    return f"{b['section']} | {b['text']}" if b.get("section") else b["text"]


INDEX = BM25([(bid, _btext(b) + (" " + " ".join(b["header"]) if b.get("header") else ""))
              for bid, b in BLOCKS.items()])


def _tpl_text(t: dict) -> str:
    out = [f"TEMPLATE {t['id']}: {t.get('title', '')} [{t.get('kind', '')}]"]
    if t.get("channel"):
        out.append(f"Channel: {t['channel']}")
    if t.get("to"):
        out.append(f"To: {', '.join(t['to'])}")
    if t.get("cc"):
        out.append(f"Cc: {', '.join(t['cc'])}")
    if t.get("subject"):
        out.append(f"Subject: {t['subject']}")
    out.append("Text (verbatim from the SOP):\n" + (t.get("body") or "").strip())
    if t.get("placeholders"):
        out.append("Placeholders: " + "; ".join(f"{k} = {v}" for k, v in t["placeholders"].items()))
    if t.get("blocks"):
        out.append(f"Source: {t['blocks'][0]}")
    return "\n".join(out)


def _rule_line(r: dict) -> str:
    s = f"- {r['id']} [{r.get('kind', '')}] {r.get('statement', '')}"
    if r.get("when") and r["when"] != "always":
        s += f" WHEN {r['when']}"
    if r.get("unless"):
        s += f" UNLESS {r['unless']}"
    if r.get("params"):
        s += " (" + "; ".join(f"{k}: {v}" for k, v in r["params"].items()) + ")"
    if r.get("blocks"):
        s += f" [{r['blocks'][0]}]"
    if SOFTSTOP and r.get("kind") in ("stop", "escalation"):
        s += f" {SCOPE}"
    return s


app = FastMCP("policy")


@app.tool
async def overview() -> str:
    """Start here. Compiled map of the company SOP: definitions (business days, time zone, formats), the list of
    procedures with their triggers, people and who may authorize what, channels, and the hard rules (prohibitions,
    authority, stop/hold and escalation rules). Then open the procedures that apply with policy__procedure."""
    k = KB
    out = [f"COMPANY: {k.get('company', '')}", k.get("summary", ""), "", "DEFINITIONS:"]
    out += [f"- {d['term']}: {d['meaning']}" for d in k.get("definitions", [])]
    out += ["", "PROCEDURES (open with policy__procedure(id)):"]
    out += [f"- {p['id']} {p['title']} — trigger: {p.get('trigger', '')}" for p in k.get("procedures", [])]
    out += ["", "PEOPLE / AUTHORITY:"]
    for p in k.get("people", []):
        bits = [p.get("role", ""), p.get("email", ""), p.get("slack", "")]
        line = f"- {p['name']} ({', '.join(b for b in bits if b)})"
        if p.get("authority"):
            line += " — authority: " + "; ".join(p["authority"])
        out.append(line)
    out += ["", "CHANNELS:"] + [f"- {c['name']} [{c.get('kind', '')}]: {c.get('purpose', '')}"
                                for c in k.get("channels", [])]
    hard = [r for r in k.get("rules", []) if r.get("kind") in ("prohibition", "authority", "stop", "escalation")
            and r.get("severity", "hard") == "hard" and "." not in r["id"]]
    out += ["", "HARD RULES:"] + [_rule_line(r) for r in hard]
    out += ["", "Other tools: policy__find (search the SOP), policy__read (exact SOP text by block/section), "
                "policy__template (exact wording, fill placeholders), policy__rules, policy__who, "
                "policy__business_days."]
    return _cut("\n".join(out), 16000)


@app.tool
async def procedure(id: str) -> str:
    """One SOP procedure (id like 'P3' or a title keyword), as compiled code where available (conditions,
    deadlines, exceptions and the ordered actions, each line citing its SOP blocks), otherwise as a step-by-step
    playbook with the exact SOP text, actions, templates, failure handling and rules."""
    if id.strip() in CODE:
        return _code_view(id.strip())
    p = PROC.get(id.strip()) or next((x for x in PROC.values() if id.lower() in x["title"].lower()), None)
    if not p:
        return "No such procedure. Available: " + "; ".join(f"{x['id']} {x['title']}" for x in PROC.values())
    units = [p["id"]] if p["id"] in CODE else _covering(p.get("blocks", []))
    if units:
        return _cut(f"PROCEDURE {p['id']}: {p['title']} (trigger: {p.get('trigger', '')})\n\n" + _code_views(units),
                    20000)
    out = [f"PROCEDURE {p['id']}: {p['title']}", f"Trigger: {p.get('trigger', '')}",
           f"Done when: {p.get('done_when', '')}", ""]
    for s in p.get("steps", []):
        text = " ".join(BLOCKS[b]["text"] for b in s.get("blocks", []) if b in BLOCKS) or s.get("instruction", "")
        out.append(f"{s['id']} [{s.get('kind', '')}]" + (f" WHEN {s['when']}" if s.get("when") not in
                                                          (None, "", "always") else ""))
        out.append(f"   SOP: {text}")
        if s.get("instruction"):
            out.append(f"   In short: {s['instruction']}")
        for a in s.get("actions", []):
            if a.get("kind") in (None, "none"):
                continue
            line = f"   -> {a['kind']}"
            if a.get("target"):
                line += f" to {a['target']}"
            if a.get("literal"):
                line += f' — exact text: "{a["literal"]}"'
            if a.get("fields"):
                line += " — fields: " + "; ".join(f"{k}={v}" for k, v in a["fields"].items())
            out.append(line)
            t = TPL.get(a.get("template", ""))
            if t:
                out.append("      " + _tpl_text(t).replace("\n", "\n      "))
        if s.get("on_fail"):
            out.append(f"   If this fails: {s['on_fail']}" + (f" {SCOPE}" if SOFTSTOP else ""))
        if s.get("blocks"):
            out.append(f"   [{s['blocks'][0]}]")
    rules = [r for r in KB.get("rules", []) if p["id"] in r.get("procedures", [])]
    if rules:
        out += ["", "RULES FOR THIS PROCEDURE:"] + [_rule_line(r) for r in rules]
    return _cut("\n".join(out), 20000)


@app.tool
async def find(query: str, k: int = 8) -> str:
    """Search the SOP (and other policy documents) for a query. Matching passages come back as the compiled code
    that implements them where available, otherwise as SOP text, with block ids and section. Use
    policy__read(block_id) for a whole section."""
    hits = INDEX.search(query, max(1, min(int(k), 20)))
    if not hits:
        return "No matches."
    out, shown = [], []
    for bid, _ in hits:
        b, units = BLOCKS[bid], [u for u in CODE_MAP.get(bid, []) if u not in shown]
        if units and len(shown) < 2:
            shown += units[:2]
            out.append(f"[{bid}] is implemented by:\n" + "\n".join(_code_view(u, 5000) for u in units[:2]))
        elif CODE_MAP.get(bid):
            out.append(f"[{bid}] ({b.get('section', '')}) -> code: "
                       + ", ".join(f"policy__procedure('{u}')" for u in CODE_MAP[bid][:3]))
        else:
            out.append(f"[{bid}] ({b['doc']}; {b.get('section', '')}) {b['text'][:600]}")
    return _cut("\n".join(out), 16000)


@app.tool
async def read(ref: str) -> str:
    """A whole SOP section. ref = a block id (e.g. 'D1.0123': returns its section) or a section number/title
    (e.g. '8.2' or 'Stop Protocol'). Parts compiled to code come back as that code, the rest as exact SOP text."""
    ref = ref.strip()
    if ref not in BLOCKS:
        cand = [bid for bid, b in BLOCKS.items() if b["kind"] == "heading"
                and (b["text"].lower().startswith(ref.lower() + " ") or ref.lower() in b["text"].lower())]
        if not cand:
            return "No such block/section. Use policy__find."
        ref = cand[0]
    i = ORDER.index(ref)
    start = i
    if BLOCKS[ref]["kind"] != "heading":
        while start > 0 and BLOCKS[ORDER[start]]["kind"] != "heading":
            start -= 1
    lvl = BLOCKS[ORDER[start]].get("level", 1) if BLOCKS[ORDER[start]]["kind"] == "heading" else 9
    section = []
    for j in range(start, len(ORDER)):
        b = BLOCKS[ORDER[j]]
        if j > start and b["kind"] == "heading" and b.get("level", 1) <= lvl:
            break
        section.append(b)
        if sum(len(x["text"]) for x in section) > MAXC:
            break
    pids = _covering([b["id"] for b in section])
    out = [_code_views(pids, 12000, 3)] if pids else []
    rest = [f"[{b['id']}] {b['text']}" for b in section if not CODE_MAP.get(b["id"])]
    if rest:
        out.append(("SOP text not compiled to code:\n" if pids else "") + "\n".join(rest))
    return _cut("\n\n".join(out), 16000)


def _fill(text: str, values: dict) -> str:
    for k, v in (values or {}).items():
        key = k if k.startswith("[") else f"[{k}]"
        text = text.replace(key, str(v))
    return text


@app.tool
async def template(id: str, values: dict | None = None) -> str:
    """Exact SOP wording for a message/log/document template (id like 'TPL-...' or a keyword). Pass values
    {"[Placeholder]": "value"} to get the filled text; any placeholder left unfilled is listed."""
    t = TPL.get(id.strip()) or next((x for x in TPL.values() if id.lower() in (x["id"] + " " + x["title"]).lower()),
                                    None)
    if not t:
        return "No such template. Available: " + "; ".join(f"{x['id']} ({x['title']})" for x in TPL.values())
    if not values:
        return _tpl_text(t)
    subj, body = _fill(t.get("subject", ""), values), _fill(t.get("body", ""), values)
    left = sorted(set(re.findall(r"\[[^\]\n]{1,60}\]", subj + "\n" + body)))
    out = [f"TEMPLATE {t['id']} filled:"]
    if subj:
        out.append(f"Subject: {subj}")
    out.append(body)
    if left:
        out.append("Still unfilled (check whether each is a placeholder or a literal tag): " + ", ".join(left))
    return "\n".join(out)


@app.tool
async def rules(query: str = "") -> str:
    """SOP rules (prohibitions, authority, stop/hold, deadlines, thresholds, formats ...). Filter by a keyword, a
    rule kind, or a procedure id; empty query lists all."""
    q = query.lower().strip()
    rs = [r for r in KB.get("rules", []) if not q or q in json.dumps(r, ensure_ascii=False).lower()]
    return _cut("\n".join(_rule_line(r) for r in rs) or "No matching rules.")


@app.tool
async def who(query: str) -> str:
    """Look up people, roles, contacts and what each person may authorize, approve or receive."""
    q = query.lower()
    hits = [p for p in KB.get("people", []) if q in json.dumps(p, ensure_ascii=False).lower()]
    if not hits:
        return "No match in the SOP's people list. Try policy__find."
    return "\n".join(json.dumps({k: v for k, v in p.items() if k not in ("refs", "blocks")}, ensure_ascii=False)
                     for p in hits)


def _holidays() -> set[dt.date]:
    out = set()
    blob = json.dumps([d for d in KB.get("definitions", []) if "holiday" in json.dumps(d).lower()]
                      + [t for t in KB.get("tables", []) if "holiday" in json.dumps(t).lower()])
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", blob):
        try:
            out.add(dt.date(int(m[1]), int(m[2]), int(m[3])))
        except ValueError:
            pass
    return out


@app.tool
async def business_days(start: str, days: int = 0, end: str = "") -> str:
    """Business-day calculator (weekends and SOP holidays excluded). start/end as YYYY-MM-DD. With days: the date
    `days` business days after start (negative = before). With end: number of business days from start to end."""
    hol = _holidays()

    def biz(d: dt.date) -> bool:
        return d.weekday() < 5 and d not in hol
    s = dt.date.fromisoformat(start)
    if end:
        e = dt.date.fromisoformat(end)
        step = 1 if e >= s else -1
        n, d = 0, s
        while d != e:
            d += dt.timedelta(days=step)
            n += step if biz(d) else 0
        return f"{n} business days from {s} to {e} (holidays considered: {sorted(map(str, hol)) or 'none listed'})"
    n, d = 0, s
    step = 1 if days >= 0 else -1
    while n != days:
        d += dt.timedelta(days=step)
        if biz(d):
            n += step
    return f"{d.isoformat()} ({d.strftime('%A')}) is {days} business days from {s}"


@app.tool
async def run(function: str, case: dict | None = None, today: str = "") -> str:
    """Execute a compiled SOP procedure on the facts of one case and get the ordered actions the SOP prescribes
    (nothing is performed: you still make the tool calls). function = the function name shown by
    policy__procedure; case = the keys documented in its docstring; today = YYYY-MM-DD."""
    pid = BY_FN.get(function.strip()) or (function.strip() if CODE.get(function.strip(), {}).get("runnable")
                                          else None)
    if not pid:
        return "No such compiled procedure. Available: " + ", ".join(sorted(BY_FN))
    req = {"common": _CODE.get("common", ""), "code": CODE[pid]["code"], "fn": CODE[pid]["fn"],
           "case": case or {}, "today": today}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(req, fh)
    try:
        p = subprocess.run([sys.executable, str(HERE / "sop_exec.py"), fh.name], capture_output=True, text=True,
                           timeout=20, check=False)
        res = json.loads(p.stdout or "{}") or {"ok": False, "error": p.stderr[-300:]}
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        res = {"ok": False, "error": f"{type(e).__name__}"}
    finally:
        os.unlink(fh.name)
    if not res.get("ok"):
        return f"{CODE[pid]['fn']} failed: {res.get('error')}. Read the code (policy__procedure('{pid}')) instead."
    return json.dumps(res["actions"], indent=1, ensure_ascii=False)


def _iw_exec(mode: str, payload: dict) -> str:
    """Run iw_exec.py (the task's registered SOP verifier code) under the agent runner's python."""
    try:
        env_cfg = json.loads(EXEC_ENV.read_text())
    except (OSError, json.JSONDecodeError):
        return "The SOP checks are not available in this workspace; rely on the SOP text (policy__read)."
    env = {**os.environ, **{k: str(v) for k, v in env_cfg.get("env", {}).items()}}
    try:
        p = subprocess.run([env_cfg["python"], str(HERE / "iw_exec.py"), mode], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=240, env=env, check=False)
    except subprocess.TimeoutExpired:
        return "The SOP check timed out; rely on the SOP text (policy__read)."
    return p.stdout.strip() or f"The SOP check failed ({p.stderr.strip()[-300:]}); rely on the SOP text."


if (HERE / "data" / "exec_enabled").exists():

    @app.tool
    async def verify_action(tool_name: str, arguments: dict) -> str:
        """Run this task's registered SOP checks - the executable code compiled from the SOP that policy__procedure
        and policy__find show - on a tool call you are about to make (e.g. an email, Slack post, Jira change or file
        write): tool_name as you would call it (e.g. google_mail__send_email) and its arguments. Nothing is executed
        or sent. Returns OK or the SOP problems with their references and the fix."""
        return _iw_exec("action", {"tool_name": tool_name, "arguments": arguments})

    @app.tool
    async def verify_completion() -> str:
        """Run this task's registered SOP end-state checks on everything done so far and list what the SOP still
        requires (or OK). Useful at the start to see what must be done, and before you finish."""
        return _iw_exec("completion", {})


if os.environ.get("VRAG_CHECK_TOOL") == "1" or (HERE / "data" / "check_enabled").exists():
    from gate import dry_run  # noqa: E402

    @app.tool
    async def check(tool_name: str, arguments: dict) -> str:
        """Before an important action, ask the SOP checker whether a proposed tool call (e.g. an email, Slack post,
        Jira update or file write) complies with the SOP. Returns problems and the exact fix, or OK. Nothing is
        executed."""
        return dry_run(tool_name, arguments)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "0") or 0)
    os.environ.pop("MCP_PROXY_TOKEN", None)
    if port:
        app.run(transport="http", host="127.0.0.1", port=port, show_banner=False)
    else:
        app.run(show_banner=False)
