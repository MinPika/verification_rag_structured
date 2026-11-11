"""Run and grade a batch of trials: every (model, task, trial) in its own subprocess (shared-corpus host-side grep in
one process serialises badly), resumable, with a plain-text progress log.

    python -m vharvey.batch --run base-dev15 --arm A0 --models claude-haiku-5.5 gpt-5.6-luna gemini-3.8-flash \
        --tasks dev:15 --trials 1 --conc 12

Trial dirs: runs/labroot/results/<run>/<model>/<task>/t<k>. Grading (dual proxy judges) follows each finished trial.
Infra failures (status infra_error, judge errors) are logged and left ungraded, never scored 0.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from . import paths, runner, split


def resolve_tasks(spec: str) -> list[str]:
    """'dev', 'dev:15' (first 15 dev tasks in split hash order), 'test', 'all' or comma-separated ids."""
    name, _, n = spec.partition(":")
    if name in ("dev", "test"):
        ids = sorted(split.load(name), key=split._h)
    elif name == "all":
        ids = paths.task_ids()
    else:
        return [t.strip() for t in spec.split(",") if t.strip()]
    return ids[: int(n)] if n else ids


def run_name(run: str, model: str) -> str:
    return f"{run}/{model}"


def _one(run: str, model: str, task: str, trial: int, arm: str, effort: str, timeout: int) -> dict:
    tdir = runner.trial_dir(run_name(run, model), task, trial)
    t0 = time.time()
    if not (tdir / "metrics.json").exists():
        cmd = [sys.executable, "-m", "vharvey.batch", "_trial", run_name(run, model), task, str(trial), model, arm,
               effort]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=paths.ROOT)
            if p.returncode != 0:
                return {"task": task, "model": model, "status": "infra_error", "error": p.stderr[-800:]}
        except subprocess.TimeoutExpired:
            return {"task": task, "model": model, "status": "timeout", "error": f"trial exceeded {timeout}s"}
    meta = json.loads((tdir / "vharvey.json").read_text()) if (tdir / "vharvey.json").exists() else {}
    if meta.get("status") != "ok" or not (tdir / "metrics.json").exists():
        return {"task": task, "model": model, "status": meta.get("status", "infra_error"),
                "error": (meta.get("error") or "")[:800]}
    from . import grade
    try:
        g = grade.grade_trial(tdir, task)
    except Exception as e:
        return {"task": task, "model": model, "status": "grade_error", "error": f"{type(e).__name__}: {e}"[:800]}
    return {"task": task, "model": model, "status": "ok", "crit": round(g["dual_criterion_pass"], 3),
            "all_pass": g["dual_all_pass_rate"], "secs": round(time.time() - t0)}


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "_trial":
        run, task, trial, model, arm, effort = sys.argv[2:8]
        from .arms import make
        m = runner.run_trial(run, task, int(trial), runner.TrialConfig(model=model, effort=effort), make(arm))
        sys.exit(0 if m.get("status", "ok") == "ok" else 3)
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arm", default="A0")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--conc", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=5400)
    a = ap.parse_args()
    runner.ensure_labroot()
    jobs = [(m, t, k) for k in range(a.trials) for t in resolve_tasks(a.tasks) for m in a.models]
    logdir = runner.LABROOT / "results" / a.run
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / "batch.json").write_text(json.dumps({**vars(a), "n_jobs": len(jobs), "lab_commit": paths.LAB_COMMIT,
                                                   "started": datetime.now(UTC).isoformat()}, indent=1))
    log = (logdir / "batch.log").open("a")
    done = 0
    with ThreadPoolExecutor(a.conc) as ex:
        futs = [ex.submit(_one, a.run, m, t, k, a.arm, a.effort, a.timeout) for m, t, k in jobs]
        for f in as_completed(futs):
            r = f.result()
            done += 1
            line = f"{datetime.now(UTC):%H:%M:%S} [{done}/{len(jobs)}] " + json.dumps(r)
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()


if __name__ == "__main__":
    main()


def results(run: str) -> list[dict]:
    """All graded trials of a batch run: one row per trial with task, model, crit, all_pass."""
    rows = []
    base = runner.LABROOT / "results" / run
    for sd in sorted(base.glob("*/*/t*/scores_dual.json")):
        tdir: Path = sd.parent
        g = json.loads(sd.read_text())
        rows.append({"model": tdir.parents[1].name, "task": tdir.parent.name, "trial": tdir.name,
                     "crit": g["dual_criterion_pass"], "all_pass": g["dual_all_pass_rate"], "dir": str(tdir)})
    return rows
