"""Pipeline: as soon as a task's KB (kb.json) exists, compile its guards for the requested tiers.

    python -m vrag.pipeline --tiers kb_seed,kb --workers 4 [--tasks-file runs/compile_order.txt]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import time

from . import guards, paths


def _lock_path(j):
    return paths.KB / j[0] / f"guards_{j[1]}.lock"


def _lock(j) -> bool:
    """Claim a (task, tier) job so concurrent pipelines don't duplicate it; locks older than 45 min are stale."""
    p = _lock_path(j)
    if p.exists() and time.time() - p.stat().st_mtime > 2700:
        p.unlink(missing_ok=True)
    try:
        os.close(os.open(p, os.O_CREAT | os.O_EXCL))
        return True
    except FileExistsError:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="kb_seed,kb")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tasks-file", default="")
    ap.add_argument("--timeout-h", type=float, default=10)
    a = ap.parse_args()
    tasks = [t.strip() for t in open(a.tasks_file)] if a.tasks_file else paths.all_tasks()
    tasks = [t for t in tasks if t]
    jobs = [(t, tier) for t in tasks for tier in a.tiers.split(",")]
    todo = [j for j in jobs if not (paths.KB / j[0] / f"guards_{j[1]}.json").exists()]
    t_end = time.time() + a.timeout_h * 3600
    running: dict = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        while (todo or running) and time.time() < t_end:
            for j in list(todo):
                if len(running) >= a.workers:
                    break
                if (paths.KB / j[0] / f"guards_{j[1]}.json").exists():
                    todo.remove(j)
                    continue
                if (paths.KB / j[0] / "kb.json").exists() and _lock(j):
                    todo.remove(j)
                    running[ex.submit(guards.compile_guards, j[0], j[1])] = j
            done = [f for f in running if f.done()]
            for f in done:
                j = running.pop(f)
                _lock_path(j).unlink(missing_ok=True)
                try:
                    print(json.dumps(f.result()), flush=True)
                except Exception as e:
                    print(json.dumps({"task": j[0], "tier": j[1], "error": str(e)[:300]}), flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
