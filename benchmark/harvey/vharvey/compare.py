"""Compare graded runs on the tasks they share: criterion pass, all-pass, precision-criterion pass, required-matter
recall, effort; paired bootstrap 95% CI of each arm minus the baseline.

    python -m vharvey.compare base-dev50 V1-dev50 V2-dev50 [--md docs/RESULTS_dev.md]
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from . import batch, paths

JUDGES = ("claude-sonnet-5", "gpt-5.6-sol")


def _criteria_pass(tdir: str) -> dict[str, float]:
    """criterion id -> fraction of judges passing it."""
    out: dict[str, float] = {}
    for j in JUDGES:
        s = json.loads((Path(tdir) / f"scores_{j}.json").read_text())
        for r in s["criteria_results"]:
            cid = r.get("criterion_id") or r.get("id")
            out[cid] = out.get(cid, 0.0) + (r["verdict"] == "pass") / len(JUDGES)
    return out


def task_metrics(task: str, tdir: str) -> dict:
    t = json.loads((paths.TASKS / task / "task.json").read_text())
    cp = _criteria_pass(tdir)
    prec = [c["id"] for c in t["criteria"] if "precision" in c["title"].lower()]
    req = [c["id"] for c in t["criteria"] if re.search(r"matter \d{4}-\d{5}", c["match_criteria"])
           and c["id"] not in prec and c["title"].lower().startswith(("qualifying", "identifies"))]
    m = json.loads((Path(tdir) / "metrics.json").read_text())
    meta = json.loads((Path(tdir) / "vharvey.json").read_text())
    fv = sum(1 for e in meta.get("arm_log") or [] if str(e.get("tool", "")).startswith("fv_"))
    return {"precision": sum(cp[c] for c in prec) / len(prec) if prec else None,
            "recall": sum(cp[c] for c in req) / len(req) if req else None,
            "turns": m["turn_count"], "secs": m["wall_clock_seconds"], "tokens": m["input_tokens"],
            "out_tokens": m.get("output_tokens", 0), "fv_calls": fv}


def _boot(d: list[float], n: int = 4000) -> tuple[float, float]:
    rnd = random.Random(0)
    bs = sorted(sum(rnd.choice(d) for _ in d) / len(d) for _ in range(n))
    return bs[int(0.025 * n)], bs[int(0.975 * n)]


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def per_task(run: str, model: str, trials: int | None = None) -> dict[str, dict]:
    """task -> metrics averaged over the run's graded trials (the first ``trials`` if given)."""
    by: dict[str, list[dict]] = {}
    for x in sorted(batch.results(run), key=lambda x: x["trial"]):
        if x["model"] == model and (trials is None or int(x["trial"][1:]) < trials):
            by.setdefault(x["task"], []).append({**task_metrics(x["task"], x["dir"]), "crit": x["crit"],
                                                 "ap": x["all_pass"]})
    return {t: {k: _mean([r[k] for r in rs]) for k in rs[0]} | {"k": len(rs)} for t, rs in by.items()}


def compare(runs: list[str], model: str = "claude-haiku-5.5", trials: int | None = None) -> list[dict]:
    data = {r: per_task(r, model, trials) for r in runs}
    common = sorted(set.intersection(*(set(d) for d in data.values())))
    rows = []
    for r in runs:
        tm = {t: data[r][t] for t in common}
        row: dict = {"run": r, "n": len(common), "k": _mean([tm[t]["k"] for t in common])}
        for k in ("crit", "ap", "precision", "recall", "turns", "secs", "tokens", "out_tokens", "fv_calls"):
            vals = [tm[t][k] for t in common if tm[t][k] is not None]
            row[k] = sum(vals) / len(vals) if vals else None
        row["_tm"] = tm
        rows.append(row)
    b = rows[0]["_tm"]
    for row in rows[1:]:
        for k in ("crit", "ap", "precision", "recall"):
            d = [row["_tm"][t][k] - b[t][k] for t in common if b[t][k] is not None and row["_tm"][t][k] is not None]
            row[f"d_{k}"] = (sum(d) / len(d), *_boot(d)) if d else None
    for row in rows:
        row.pop("_tm")
    return rows


def to_md(rows: list[dict]) -> str:
    f = lambda x: "–" if x is None else f"{x:.3f}"  # noqa: E731
    g = lambda d: "" if not d else f" ({d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}])"  # noqa: E731
    out = ["| run | tasks | trials/task | criterion pass | all-pass | precision criterion | required-matter recall "
           "| turns | secs |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['run']} | {r['n']} | {r['k']:.1f} | {f(r['crit'])}{g(r.get('d_crit'))} | "
                   f"{f(r['ap'])}{g(r.get('d_ap'))} | "
                   f"{f(r['precision'])}{g(r.get('d_precision'))} | {f(r['recall'])}{g(r.get('d_recall'))} | "
                   f"{r['turns']:.1f} | {r['secs']:.0f} |")
    return "\n".join(out) + "\n\nΔ vs the first run, paired bootstrap 95% CI over tasks.\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--md")
    ap.add_argument("--trials", type=int, default=None, help="use only the first N trials of each task")
    a = ap.parse_args()
    md = to_md(compare(a.runs, trials=a.trials))
    print(md)
    if a.md:
        Path(a.md).write_text(md)


if __name__ == "__main__":
    main()
