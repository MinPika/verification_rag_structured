"""Paired task-level bootstrap for arm comparisons.

    python -m vrag.stats [--metric mean|sp1|n1] 'A3=A3-kb_seed-test-v3*' 'R=R-test*,R-dev*' 'A0=A0-test*'

Each arm is a comma-separated list of job globs under runs/jobs. Metrics are per-task values from
``report.summarize``: mean reward, strict pass@1 (all rubrics) or pass@1 (N-1, the leaderboard metric).
"""
from __future__ import annotations

import argparse
import random

from . import paths, report

METRICS = ("mean", "sp1", "n1")


def jobs(pat: str) -> list:
    root = paths.ROOT / "runs" / "jobs"
    return sorted({j for p in pat.split(",") if p for j in root.glob(p)})


def task_means(pat: str, metric: str = "mean") -> dict[str, float]:
    return {t: r[metric] for t, r in report.summarize(jobs(pat))["rows"].items()}


def paired(a: dict, b: dict, n: int = 10000, seed: int = 0) -> tuple[int, float, float, float]:
    ts = sorted(set(a) & set(b))
    d = [a[t] - b[t] for t in ts]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return len(ts), sum(d) / len(d), boots[int(0.025 * n)], boots[int(0.975 * n)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--metric", choices=METRICS, default="mean")
    ap.add_argument("arms", nargs="+", help="label=glob[,glob...]")
    args = ap.parse_args()
    means = {k: task_means(v, args.metric) for k, v in (x.split("=", 1) for x in args.arms)}
    names = list(means)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            k, m, lo, hi = paired(means[x], means[y])
            print(f"{args.metric}: {x} - {y}: n={k} diff={m:+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]")


if __name__ == "__main__":
    main()
