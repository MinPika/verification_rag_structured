"""Render a LAB trial transcript verbatim as markdown: task prompt, then every model turn (text + tool calls with full
arguments) and every tool result, in order. Nothing is summarised. Long tool results are cut at ``--max-result``
characters, with the cut stated, so the file stays openable.

    python -m vharvey.transcript_md runs/labroot/results/smoke/001/t0 [-o out.md] [--max-result 4000]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _fence(text: str, lang: str = "") -> str:
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text}\n{ticks}"


def _args(raw: str) -> tuple[str, str]:
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw), ""
    if isinstance(d, dict) and set(d) <= {"command"} and "command" in d:
        return d["command"], "bash"
    if isinstance(d, dict) and "content" in d:
        rest = {k: v for k, v in d.items() if k != "content"}
        return f"{json.dumps(rest)}\n--- content ---\n{d['content']}", ""
    return json.dumps(d, indent=1), "json"


def render(tdir: Path, max_result: int = 4000) -> str:
    cfg = json.loads((tdir / "config.json").read_text())
    metrics = json.loads((tdir / "metrics.json").read_text()) if (tdir / "metrics.json").exists() else {}
    task_id = cfg["task"].rsplit("/", 1)[-1]
    from . import paths
    instructions = json.loads((paths.TASKS / task_id / "task.json").read_text())["instructions"]
    out = [f"# Trial transcript: task {task_id}, {cfg['model']} (arm {cfg.get('arm', 'A0')})", "",
           f"Turns {metrics.get('turn_count')}, wall clock {metrics.get('wall_clock_seconds')} s, "
           f"finish reason `{metrics.get('finish_reason')}`, effort `{cfg.get('reasoning_effort')}`.", "",
           "System prompt: LAB `lab_core/harness/system_prompt.md` + finish block + docx/pptx/xlsx skill manuals "
           "(unchanged). Tools: bash, read, write, edit, glob, grep, finish.", "",
           "## User message (the task, exactly as sent)", "", _fence(instructions), ""]
    for line in (tdir / "transcript.jsonl").open():
        d = json.loads(line)
        if d["role"] == "assistant":
            out.append(f"## Turn {d['turn']}: model")
            if d.get("text"):
                out += ["", "**Model text:**", "", _fence(d["text"])]
            for tc in d.get("tool_calls") or []:
                body, lang = _args(tc["arguments"])
                out += ["", f"**Tool call `{tc['name']}`** (id `{tc['id']}`):", "", _fence(body, lang)]
            if not d.get("tool_calls"):
                out += ["", "_No tool calls: the agent loop ends here._"]
            out.append("")
        else:
            res = d.get("result") or ""
            cut = len(res) > max_result
            shown = res[:max_result]
            out += [f"**Tool result `{d['tool_name']}`** ({len(res):,} chars"
                    + (f", first {max_result:,} shown" if cut else "") + "):", "", _fence(shown), ""]
    resp = tdir / "output" / "response.md"
    if resp.exists():
        out += ["## Deliverable `output/response.md` (full)", "", _fence(resp.read_text(), "markdown"), ""]
    crit = {c["id"]: c for c in json.loads((paths.TASKS / task_id / "task.json").read_text())["criteria"]}
    for sp in sorted(tdir.glob("scores_*.json")):
        if sp.name == "scores_dual.json":
            continue
        s = json.loads(sp.read_text())
        out += [f"## Judge {s['judge_model']}: {s['n_passed']}/{s['n_criteria']} criteria passed", ""]
        for r in s["criteria_results"]:
            cid = r.get("criterion_id") or r.get("id")
            c = crit.get(cid, {})
            out += [f"- **{cid} {r['verdict'].upper()}**: {c.get('match_criteria', r.get('title', ''))}",
                    f"  - judge reasoning: {r.get('reasoning', '')}"]
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trial_dir", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--max-result", type=int, default=4000)
    a = ap.parse_args()
    out = a.out or a.trial_dir / "transcript.md"
    out.write_text(render(a.trial_dir, a.max_result))
    print(out)


if __name__ == "__main__":
    main()
