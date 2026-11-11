"""Summarise harbor jobs: per task mean reward, strict pass rates (no rubric text is read)."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import paths

_PASSED = re.compile(r"(\d+)/(\d+) rubrics passed")


def rubric_misses(trial_dir: Path, reward: float | None) -> int | None:
    """Number of failed rubric criteria, from the verifier's own 'X/Y rubrics passed' line.

    Without verifier output only a perfect reward is decidable (0 misses); anything else returns None, which
    every pass metric counts as a failure."""
    out = trial_dir / "verifier" / "test-stdout.txt"
    if out.exists():
        m = _PASSED.search(out.read_text(errors="replace"))
        if m and int(m.group(2)) > 0:
            return int(m.group(2)) - int(m.group(1))
    return 0 if reward is not None and reward >= 0.9999 else None


def all_passed(trial_dir: Path, reward: float | None) -> bool:
    """Strict pass as HANDBOOK.md defines it: every rubric criterion passes. The reward is the mean rubric
    *score*, which can stay below 1.0 when partially-scored criteria all pass, so it is only a fallback."""
    return rubric_misses(trial_dir, reward) == 0


def n1_passed(trial_dir: Path, reward: float | None) -> bool:
    """pass@1 (N-1) as HANDBOOK.md defines it: at most one missed criterion. This is the leaderboard number."""
    misses = rubric_misses(trial_dir, reward)
    return misses is not None and misses <= 1


def claude_code_api_error(trial_dir: Path) -> bool:
    """True when a Claude Code agent run ended on an API error (auth, rate limit, overload): a transport failure,
    not agent behaviour; the verifier still grades the untouched workspace, so such trials must not be scored."""
    log = trial_dir / "agent" / "claude-code.txt"
    if not log.exists():
        return False
    for line in reversed(log.read_text(errors="replace").splitlines()):
        if '"type":"result"' in line.replace(" ", ""):
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                return False
            return bool(ev.get("is_error")) and ev.get("api_error_status") is not None
    return False


def trials(job: Path):
    for d in sorted(job.iterdir()):
        r = d / "result.json"
        if not d.is_dir() or not r.exists():
            continue
        res = json.loads(r.read_text())
        task = (res.get("task_name") or d.name.split("__")[0]).split("/")[-1]
        vr = (res.get("verifier_result") or {}).get("rewards") or {}
        reward = vr.get("reward")
        exc = res.get("exception_info")
        msg = str((exc or {}).get("exception_message", ""))
        if reward is None and exc and "exceeds token limit" in msg:
            reward = 0.0  # agent-caused context overflow: scored 0 (as in the interwhen baseline's reports)
        elif claude_code_api_error(d):
            reward = None
        elif "Agent execution timed out" in msg:
            # Trials take minutes; the one-hour agent timeout only fires when the model proxy hangs. The verifier
            # still grades the half-finished state, but HANDBOOK.md excludes transport failures, so do we.
            reward = None
        yield task, reward, exc, d


def summarize(jobs: list[Path]) -> dict:
    per: dict[str, list[tuple[float, bool, bool]]] = defaultdict(list)
    errors = 0
    for job in jobs:
        for task, reward, _exc, d in trials(job):
            if reward is None:
                errors += 1
                continue
            per[task].append((float(reward), all_passed(d, reward), n1_passed(d, reward)))
    rows = {}
    for t, xs in per.items():
        rs, ok, n1 = [x[0] for x in xs], [x[1] for x in xs], [x[2] for x in xs]
        rows[t] = {"n": len(xs), "mean": 100 * sum(rs) / len(rs), "sp1": 100 * sum(ok) / len(ok),
                   "n1": 100 * sum(n1) / len(n1), "sp4": 100.0 * any(ok), "spall": 100.0 * all(ok)}
    keys = ("mean", "sp1", "n1", "sp4", "spall")
    agg = {k: sum(r[k] for r in rows.values()) / len(rows) for k in keys} if rows else {}
    return {"tasks": len(rows), "trials": sum(r["n"] for r in rows.values()), "errors": errors, "agg": agg,
            "rows": rows}


def compare(arms: dict[str, str], tasks: list[str] | None = None, out: str | None = None) -> str:
    """arms: {label: job glob}. Paired per-task table + aggregates over the common task set."""
    data = {k: summarize(sorted((paths.ROOT / "runs" / "jobs").glob(v)))["rows"] for k, v in arms.items()}
    common = set.intersection(*(set(v) for v in data.values())) if data else set()
    if tasks:
        common &= set(tasks)
    common = sorted(common)
    labels = list(arms)
    lines = ["| task | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for t in common:
        lines.append(f"| {t.split('_')[-1]} {paths.company(t)} | " + " | ".join(
            f"{data[k][t]['mean']:.1f} ({data[k][t]['sp1']:.0f})" for k in labels) + " |")
    lines.append("")
    lines.append("| metric | " + " | ".join(labels) + " |")
    lines.append("|---|" + "---|" * len(labels))
    for m, name in (("mean", "mean reward"), ("sp1", "strict pass@1"), ("n1", "pass@1 (N-1)"),
                    ("sp4", "strict pass@4"), ("spall", "strict pass^4")):
        lines.append(f"| {name} | " + " | ".join(
            f"{sum(data[k][t][m] for t in common) / max(1, len(common)):.2f}" for k in labels) + " |")
    base = labels[0]
    for k in labels[1:]:
        d = [data[k][t]["mean"] - data[base][t]["mean"] for t in common]
        lines.append(f"\n{k} vs {base}: improved {sum(x > 2 for x in d)} / worse {sum(x < -2 for x in d)} / "
                     f"same {sum(abs(x) <= 2 for x in d)} (n={len(common)})")
    text = "\n".join(lines)
    if out:
        (paths.ROOT / out).write_text(text + "\n")
    return text


def main() -> None:
    for pat in sys.argv[1:]:
        s = summarize(sorted((paths.ROOT / "runs" / "jobs").glob(pat)))
        print(pat, s["tasks"], "tasks", s["trials"], "trials", s["errors"], "err",
              {k: round(v, 2) for k, v in s["agg"].items()})


if __name__ == "__main__":
    main()
