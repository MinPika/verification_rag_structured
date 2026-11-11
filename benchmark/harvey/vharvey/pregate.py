"""Within-trial effect of late verification: grade the answer as it was just before the verification gate.

    python -m vharvey.pregate VL-test60        # -> run "<run>-pregate" with the pre-gate response.md, graded

In VL/VLC the agent works exactly like A0 until its first ``finish``; the gate then asks it to verify and lets it
edit. Rebuilding ``response.md`` at the gate (replaying the agent's ``write``/``edit`` calls in order) and grading it
with the same judges gives a paired, same-trajectory estimate of what the verification step changed, free of
between-run search variance. Trials whose answer was changed through ``bash`` before the gate cannot be replayed
and are skipped (listed in ``skipped.json``).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import batch, grade, runner

GATE_MARK = "Before you finish: verify the matters"
# shell commands that change response.md (reads such as cat/head/wc/grep are harmless)
WRITES_RESPONSE = re.compile(r"(>>?\s*['\"]?\S*response\.md|tee\s+(-a\s+)?\S*response\.md"
                             r"|(sed|perl)\s+-i[^|;&]*response\.md|open\([^)]*response\.md[^)]*['\"][wa]|\b(mv|cp)\s+\S+\s+\S*response\.md|write_text)")


def replay(transcript: Path) -> tuple[str | None, str]:
    """(response.md content at the gate or None, reason)."""
    calls: dict[str, dict] = {}
    content: str | None = None
    for line in transcript.open():
        d = json.loads(line)
        if d["role"] == "assistant":
            for tc in d.get("tool_calls") or []:
                calls[tc["id"]] = {"name": tc["name"], "args": tc["arguments"]}
            continue
        if GATE_MARK in (d.get("result") or ""):
            return content, "ok" if content is not None else "no response.md before the gate"
        call = calls.get(d.get("tool_call_id") or "", {})
        name, raw = call.get("name"), call.get("args") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        target = str(args.get("file_path") or "")
        res = d.get("result") or ""
        if name == "write" and target.endswith("response.md") and not res.startswith("Error"):
            content = args.get("content", "")
        elif name == "edit" and target.endswith("response.md") and not res.startswith("Error") and content is not None:
            old, new = args.get("old_string", ""), args.get("new_string", "")
            content = content.replace(old, new) if args.get("replace_all") else content.replace(old, new, 1)
        elif name == "bash" and WRITES_RESPONSE.search(str(args.get("command", ""))):
            return None, "response.md written through bash before the gate"
    return None, "gate never reached"


def build(run: str, workers: int = 6) -> str:
    out_run = f"{run}-pregate"
    skipped = {}
    todo = []
    for r in batch.results(run):
        src = Path(r["dir"])
        text, why = replay(src / "transcript.jsonl")
        if text is None:
            skipped[f"{r['model']}/{r['task']}/{r['trial']}"] = why
            continue
        dst = runner.LABROOT / "results" / out_run / r["model"] / r["task"] / r["trial"]
        if not (dst / "scores_dual.json").exists():
            (dst / "output").mkdir(parents=True, exist_ok=True)
            (dst / "output" / "response.md").write_text(text)
            for f in ("config.json", "metrics.json", "transcript.jsonl", "vharvey.json"):
                shutil.copy(src / f, dst / f)
        todo.append((dst, r["task"]))
    (runner.LABROOT / "results" / out_run).mkdir(parents=True, exist_ok=True)
    (runner.LABROOT / "results" / out_run / "skipped.json").write_text(json.dumps(skipped, indent=1))
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda x: grade.grade_trial(*x), todo))
    print(f"{out_run}: {len(todo)} graded, {len(skipped)} skipped {skipped}")
    return out_run


if __name__ == "__main__":
    for run in sys.argv[1:]:
        build(run)


def paired(run: str, model: str = "claude-haiku-5.5", exclude: frozenset[str] = frozenset()) -> dict:
    """Trial-matched pre vs post deltas (only trials present in both runs; tasks in ``exclude`` are left out)."""
    from .compare import _boot, task_metrics
    pre = {(x["task"], x["trial"]): x for x in batch.results(f"{run}-pregate")
           if x["model"] == model and x["task"] not in exclude}
    post = {(x["task"], x["trial"]): x for x in batch.results(run) if x["model"] == model and x["task"] not in exclude}
    keys = sorted(set(pre) & set(post))
    out: dict = {"run": run, "trials": len(keys)}
    for k in ("crit", "ap", "precision", "recall"):
        d = []
        for key in keys:
            a = pre[key]["crit"] if k == "crit" else pre[key]["all_pass"] if k == "ap" else \
                task_metrics(key[0], pre[key]["dir"])[k]
            b = post[key]["crit"] if k == "crit" else post[key]["all_pass"] if k == "ap" else \
                task_metrics(key[0], post[key]["dir"])[k]
            if a is not None and b is not None:
                d.append((a, b))
        diffs = [b - a for a, b in d]
        out[k] = {"pre": sum(a for a, _ in d) / len(d), "post": sum(b for _, b in d) / len(d),
                  "delta": sum(diffs) / len(diffs), "ci": _boot(diffs), "n": len(d)}
    return out


def pooled(runs: list[str], model: str = "claude-haiku-5.5", exclude: frozenset[str] = frozenset()) -> dict:
    """Pre vs post over several independent trials of the same tasks (e.g. k=1 and k=2 runs). Each task's deltas are
    averaged over its trials first and the CI bootstraps over tasks, so repeated trials of one task are not treated
    as independent."""
    from collections import defaultdict

    from .compare import _boot, task_metrics
    out: dict = {"runs": runs}
    for k in ("crit", "ap", "precision", "recall"):
        per_task: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for run in runs:
            pre = {x["task"]: x for x in batch.results(f"{run}-pregate") if x["model"] == model}
            post = {x["task"]: x for x in batch.results(run) if x["model"] == model}
            for t in sorted((set(pre) & set(post)) - exclude):
                a = pre[t]["crit"] if k == "crit" else pre[t]["all_pass"] if k == "ap" else \
                    task_metrics(t, pre[t]["dir"])[k]
                b = post[t]["crit"] if k == "crit" else post[t]["all_pass"] if k == "ap" else \
                    task_metrics(t, post[t]["dir"])[k]
                if a is not None and b is not None:
                    per_task[t].append((a, b))
        rows = [(sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v)) for v in per_task.values()]
        diffs = [b - a for a, b in rows]
        out[k] = {"pre": sum(a for a, _ in rows) / len(rows), "post": sum(b for _, b in rows) / len(rows),
                  "delta": sum(diffs) / len(diffs), "ci": _boot(diffs), "tasks": len(rows),
                  "trials": sum(len(v) for v in per_task.values())}
    return out
