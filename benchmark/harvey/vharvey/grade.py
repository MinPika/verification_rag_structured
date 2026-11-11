"""Grade trials with LAB's rubric scorer and dual-judge aggregation, judges routed through the proxy.

Mirrors ``lab_core.evaluation.run_eval.evaluate_run`` / ``evaluate_run_dual`` (pinned commit) except that the judge
objects are ``ProxyJudge``. Outputs per trial: ``scores_<judge>.json`` and ``scores_dual.json`` with LAB's fields
(``dual_criterion_pass``, ``dual_all_pass_rate``, ``all_pass``) plus ``judges_disagree``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from . import runner
from .judge import DEFAULT_JUDGES, ProxyJudge


def _criteria(task_id: str) -> tuple[list[dict], str]:
    from . import paths
    cfg = json.loads((paths.TASKS / task_id / "task.json").read_text())
    return cfg["criteria"], cfg["title"]


def grade_single(tdir: Path, task_id: str, judge: ProxyJudge, parallel: int = 6) -> dict:
    from lab_core.evaluation.scoring import score_rubric

    out = tdir / f"scores_{judge.model}.json"
    if out.exists():
        return json.loads(out.read_text())
    criteria, title = _criteria(task_id)
    result = score_rubric(criteria=criteria, run_dir=tdir, judge=judge, task_desc=title, parallel=parallel)
    n = len(result.criteria_results)
    passed = sum(1 for c in result.criteria_results if c["verdict"] == "pass")
    scores = {"score": result.score, "max_score": result.max_score, "all_pass": n > 0 and passed == n,
              "n_criteria": n, "n_passed": passed, "n_grading_errors": result.n_grading_errors,
              "pandoc_version": result.pandoc_version, "criteria_results": result.criteria_results,
              "task": runner.lab_task(task_id), "judge_model": judge.model,
              "scored_at": datetime.now(UTC).isoformat()}
    if result.n_grading_errors:
        raise RuntimeError(f"{tdir}: {result.n_grading_errors} criteria could not be graded by {judge.model}")
    out.write_text(json.dumps(scores, indent=2))
    return scores


def grade_trial(tdir: Path, task_id: str, judges: tuple[str, ...] = DEFAULT_JUDGES, parallel: int = 6) -> dict:
    """Dual-judge grade of one finished trial (LAB semantics: disagreement contributes 0.5 to all-pass)."""
    runner.activate()
    out = tdir / "scores_dual.json"
    if out.exists():
        return json.loads(out.read_text())
    if not (tdir / "metrics.json").exists():
        raise FileNotFoundError(f"{tdir} has no metrics.json (trial not finished)")
    per = {m: grade_single(tdir, task_id, ProxyJudge(m), parallel) for m in judges}
    crit = sum(s["n_passed"] / s["n_criteria"] for s in per.values() if s["n_criteria"]) / len(per)
    ap = sum(1.0 if s["all_pass"] else 0.0 for s in per.values()) / len(per)
    agg = {"task": runner.lab_task(task_id), "judges": list(judges), "judge_profile": "custom-dual-proxy",
           "per_judge": {m: {k: s[k] for k in ("n_criteria", "n_passed", "all_pass")} for m, s in per.items()},
           "dual_criterion_pass": crit, "dual_all_pass_rate": ap, "all_pass": ap == 1.0,
           "judges_disagree": 0.0 < ap < 1.0, "scored_at": datetime.now(UTC).isoformat()}
    out.write_text(json.dumps(agg, indent=2))
    return agg
