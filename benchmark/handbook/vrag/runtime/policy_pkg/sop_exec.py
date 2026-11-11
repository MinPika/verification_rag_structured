"""Runtime for compiled SOP code: the action/helper API the procedure functions use, a static safety check and a
sandboxed executor. Shared by the offline compiler (validation) and the policy server (``policy__run``).

Compiled procedures are pure functions ``fn(case: dict, today: str = "") -> list[dict]``: they read case facts the
agent passes in and return the ordered actions the SOP prescribes. Nothing here touches files, mail or the network.

    python sop_exec.py <code.json>   # {"common": src, "code": src, "fn": name, "case": {...}, "today": "..."}
prints {"ok": true, "actions": [...]} or {"ok": false, "error": "..."}.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import sys

# ---- action constructors (what the SOP says to do) ---------------------------------------------------------


def _act(kind: str, **fields) -> dict:
    return {"action": kind, **{k: v for k, v in fields.items() if v not in (None, "", [], {})}}


def send_email(to, subject: str = "", body: str = "", cc=(), attachments=(), template: str = "") -> dict:
    return _act("send_email", to=to, cc=list(cc), subject=subject, body=body, attachments=list(attachments),
                template=template)


def reply_email(email: str, body: str = "", template: str = "") -> dict:
    return _act("reply_email", email=email, body=body, template=template)


def forward_email(email: str, to, note: str = "") -> dict:
    return _act("forward_email", email=email, to=to, note=note)


def post_slack(channel: str, text: str, template: str = "") -> dict:
    return _act("post_slack", channel=channel, text=text, template=template)


def send_dm(person: str, text: str, template: str = "") -> dict:
    return _act("send_dm", person=person, text=text, template=template)


def jira_create(project: str, summary: str, description: str = "", assignee: str = "", **fields) -> dict:
    return _act("jira_create", project=project, summary=summary, description=description, assignee=assignee,
                fields=fields)


def jira_update(issue: str, **fields) -> dict:
    return _act("jira_update", issue=issue, fields=fields)


def jira_transition(issue: str, status: str) -> dict:
    return _act("jira_transition", issue=issue, status=status)


def jira_comment(issue: str, text: str) -> dict:
    return _act("jira_comment", issue=issue, text=text)


def calendar_event(title: str, start: str = "", end: str = "", attendees=(), description: str = "") -> dict:
    return _act("calendar_event", title=title, start=start, end=end, attendees=list(attendees),
                description=description)


def write_row(file: str, values: dict, sheet: str = "") -> dict:
    return _act("write_row", file=file, sheet=sheet, values=values)


def update_cells(file: str, where: dict, values: dict, sheet: str = "") -> dict:
    return _act("update_cells", file=file, sheet=sheet, where=where, values=values)


def move_email(email: str, folder: str) -> dict:
    return _act("move_email", email=email, folder=folder)


def stop(reason: str) -> dict:
    """The SOP says not to proceed (hold / stop / do nothing further for this case)."""
    return _act("stop", reason=reason)


def escalate(to: str, reason: str, via: str = "") -> dict:
    return _act("escalate", to=to, reason=reason, via=via)


def note(text: str) -> dict:
    """A check or decision the agent must make or record that has no tool action of its own."""
    return _act("note", text=text)


# ---- helpers ---------------------------------------------------------------------------------------------------

def date(s) -> dt.date:
    """Parse YYYY-MM-DD, MM/DD/YYYY or M/D/YY."""
    if isinstance(s, dt.date):
        return s
    s = str(s).strip()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s[:10] if f == "%Y-%m-%d" else s, f).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {s!r}")


def fmt(d, style: str = "%m/%d/%Y") -> str:
    return date(d).strftime(style)


def is_business_day(d, holidays=()) -> bool:
    d = date(d)
    return d.weekday() < 5 and d not in {date(h) for h in holidays}


def add_business_days(d, n: int, holidays=()) -> dt.date:
    d, step = date(d), (1 if n >= 0 else -1)
    while n:
        d += dt.timedelta(days=step)
        if is_business_day(d, holidays):
            n -= step
    return d


def business_days_between(a, b, holidays=()) -> int:
    a, b = date(a), date(b)
    step, n, d = (1 if b >= a else -1), 0, a
    while d != b:
        d += dt.timedelta(days=step)
        n += step if is_business_day(d, holidays) else 0
    return n


def add_days(d, n: int) -> dt.date:
    return date(d) + dt.timedelta(days=n)


def days_between(a, b) -> int:
    return (date(b) - date(a)).days


def money(x) -> float:
    return round(float(str(x).replace("$", "").replace(",", "")), 2)


def fill(template: str, **values) -> str:
    """Fill [Placeholder] fields of a template; keys may be given with or without brackets."""
    out = template
    for k, v in values.items():
        out = out.replace(k if k.startswith("[") else f"[{k}]", str(v))
    return out


API = {name: obj for name, obj in dict(globals()).items()
       if callable(obj) and not name.startswith("_") and name not in ("ast", "dt", "json", "re", "sys", "check",
                                                                       "run", "main")}
API.update({"datetime": dt.datetime, "timedelta": dt.timedelta})
MESSAGE_CALLS = {"send_email": ("subject", "body"), "reply_email": ("body",), "post_slack": ("text",),
                 "send_dm": ("text",), "jira_comment": ("text",), "forward_email": ("note",)}

# ---- static safety check and sandboxed execution ------------------------------------------------------------------

_BANNED = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
           "delattr", "input", "breakpoint", "exit", "quit", "help", "memoryview", "type", "object", "super"}
_SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
                  for n in ("abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "isinstance", "len",
                            "list", "max", "min", "range", "reversed", "round", "set", "sorted", "str", "sum",
                            "tuple", "zip", "ValueError", "KeyError", "Exception", "print")}


_STDLIB_INTERNAL = {"_strptime", "datetime", "time", "_datetime", "calendar", "locale", "re", "math"}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002 - __import__ signature
    """Only the stdlib modules that datetime/re import lazily (user code cannot write imports at all)."""
    if name not in _STDLIB_INTERNAL:
        raise ImportError(f"import of {name} is not allowed")
    return __import__(name, globals, locals, fromlist, level)


_SAFE_BUILTINS["__import__"] = _safe_import


def check(src: str) -> list[str]:
    """Static restrictions: no imports, no dunder attributes, no dangerous builtins, no while-True loops."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"syntax error: {e}"]
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            problems.append(f"line {node.lineno}: imports/global state are not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"line {node.lineno}: dunder attribute {node.attr}")
        elif isinstance(node, ast.Name) and node.id in _BANNED:
            problems.append(f"line {node.lineno}: {node.id} is not allowed")
        elif isinstance(node, ast.While):
            problems.append(f"line {node.lineno}: while loops are not allowed (use for over a bounded range)")
    return problems


def run(common: str, code: str, fn: str, case: dict, today: str = "") -> dict:
    """Execute ``fn(case, today)`` from ``code`` with the shared constants and the API; restricted builtins."""
    problems = check(common) + check(code)
    if problems:
        return {"ok": False, "error": "; ".join(problems[:5])}
    ns: dict = {"__builtins__": _SAFE_BUILTINS, **API}
    try:
        exec(compile(common, "sop_common", "exec"), ns)  # noqa: S102 - statically checked, restricted builtins
        exec(compile(code, "sop_code", "exec"), ns)  # noqa: S102
        out = ns[fn](dict(case or {}), today or "")
    except Exception as e:  # noqa: BLE001 - report any failure of compiled code to the caller
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if not isinstance(out, list) or not all(isinstance(x, dict) for x in out):
        return {"ok": False, "error": f"{fn} must return a list of actions, got {type(out).__name__}"}
    return {"ok": True, "actions": json.loads(json.dumps(out, default=str))}


def main() -> None:
    req = json.loads(open(sys.argv[1]).read()) if len(sys.argv) > 1 else json.loads(sys.stdin.read())
    print(json.dumps(run(req.get("common", ""), req["code"], req["fn"], req.get("case") or {}, req.get("today", "")),
                     ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
