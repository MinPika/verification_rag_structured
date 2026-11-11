"""Criterion-level failure analysis across arms (read-only over runs/jobs).

    python -m vrag.failures [--out docs/failure_analysis/data]

For every model x arm (vrag.tables.model_arms, all 65 tasks) and every rubric criterion, the pass rate over the
trials of that arm, from the grader's own "[PASS]/[FAIL] <criterion id>: <feedback>" lines. A criterion is a solid
failure in an arm when its pass rate is <= 25% (0/2 or <= 1/4 trials); mixed outcomes are "flaky". Trials the report
excludes (agent timeouts during proxy outages, missing rewards) are skipped.

Writes to --out: criteria.json (criterion metadata), matrix_all.json ({model: {arm: {task|crit: [passes, trials]}}}),
overlap_all.json (fate in A2+R of the criteria failing in A2, R, both or neither), never_passed.json (criteria no
trial of any model or arm passed: the candidates for the hand-checked defect list). When defects.json exists (the
hand-verified rubric defects, tiers T1-T3) also rescored.json (metrics with defective criteria removed) and, when
labels.jsonl exists (root-cause annotation), labels_final.jsonl (SOURCE split into verified / unverified).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from . import paths, report
from .tables import MODELS, model_arms

LINE = re.compile(r"^\s*\[(PASS|FAIL)\]\s+([^:\s]+):\s?(.*)$", re.M)
FAIL_MAX, PASS_MIN = 0.25, 0.75


def criteria() -> dict[str, dict]:
    """task|criterion id -> {task, id, type, text}."""
    out = {}
    for f in sorted((paths.HANDBOOK / "tasks").glob("*/tests/rubrics.json")):
        task = f.parents[1].name
        for r in json.loads(f.read_text()):
            out[f"{task}|{r['id']}"] = {"task": task, "id": r["id"], "type": r.get("criterion_type", ""),
                                        "text": r.get("rubric_text", "")}
    return out


def trial_outcomes(trial_dir: Path) -> dict[str, tuple[bool, str]]:
    """criterion id -> (passed, grader feedback) for one trial."""
    out = trial_dir / "verifier" / "test-stdout.txt"
    if not out.exists():
        return {}
    text = out.read_text(errors="replace")
    return {m.group(2): (m.group(1) == "PASS", m.group(3).strip()) for m in LINE.finditer(text)}


def arm_matrix(jobs: list[Path]) -> dict[str, list[int]]:
    """task|criterion -> [passes, trials] over the scored trials of these jobs."""
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for job in jobs:
        for task, reward, _exc, d in report.trials(job):
            if reward is None:
                continue
            for cid, (ok, _fb) in trial_outcomes(d).items():
                key = f"{task}|{cid}"
                agg[key][0] += ok
                agg[key][1] += 1
    return dict(agg)


def state(cell: list[int] | None) -> str | None:
    """'fail' | 'flaky' | 'pass' | None (not observed)."""
    if not cell or not cell[1]:
        return None
    p = cell[0] / cell[1]
    return "fail" if p <= FAIL_MAX else "pass" if p >= PASS_MIN else "flaky"


def overlap(m: dict[str, dict[str, list[int]]], a: str = "A2", b: str = "R", c: str = "A2+R",
            base: str = "A0") -> dict:
    """Fate in c of the criteria failing in a, b, both, or neither (only criteria observed in all four arms)."""
    keys = set.intersection(*(set(m.get(x, {})) for x in (a, b, c, base)))
    groups: dict[str, dict[str, list[str]]] = {g: defaultdict(list) for g in ("both", "a_only", "b_only", "neither")}
    for k in sorted(keys):
        sa, sb, sc = state(m[a][k]), state(m[b][k]), state(m[c][k])
        g = "both" if sa == sb == "fail" else "a_only" if sa == "fail" else "b_only" if sb == "fail" else "neither"
        groups[g][sc].append(k)
    base_fail = {k for k in keys if state(m[base][k]) == "fail"}
    return {"n_criteria": len(keys), "groups": {g: dict(v) for g, v in groups.items()},
            "baseline_fail": sorted(base_fail)}


def ceilings(excluded: set[str]) -> dict[str, float]:
    """Best achievable score on all 65 tasks if every criterion except the excluded ones passes.

    strict = share of tasks with no excluded criterion; n1 = share with at most one; mean = mean over tasks of the
    share of criteria that can pass (the official reward averages per-criterion scores, so this is approximate)."""
    per_task: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for key in criteria():
        per_task[key.split("|", 1)[0]][1] += 1
        per_task[key.split("|", 1)[0]][0] += key in excluded
    n = len(per_task)
    return {"strict": 100 * sum(bad == 0 for bad, _ in per_task.values()) / n,
            "n1": 100 * sum(bad <= 1 for bad, _ in per_task.values()) / n,
            "mean": 100 * sum(1 - bad / tot for bad, tot in per_task.values()) / n}


def rescore(jobs: list[Path], excluded: set[str]) -> dict[str, float]:
    """Strict pass@1, pass@1 (N-1) and criteria-passed share per task (then averaged over tasks), counting only
    criteria outside `excluded`. Uses the grader's per-criterion lines; trials the report excludes are skipped."""
    per: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for job in jobs:
        for task, reward, _exc, d in report.trials(job):
            if reward is None:
                continue
            outcomes = {cid: ok for cid, (ok, _fb) in trial_outcomes(d).items() if f"{task}|{cid}" not in excluded}
            if outcomes:
                per[task].append((sum(not ok for ok in outcomes.values()), len(outcomes)))
    if not per:
        return {}
    rows = [(sum(m == 0 for m, _ in xs) / len(xs), sum(m <= 1 for m, _ in xs) / len(xs),
             sum(1 - m / n for m, n in xs) / len(xs)) for xs in per.values()]
    return {"tasks": len(rows), "strict": 100 * sum(r[0] for r in rows) / len(rows),
            "n1": 100 * sum(r[1] for r in rows) / len(rows), "checks": 100 * sum(r[2] for r in rows) / len(rows)}


def build(scope: str = "all") -> tuple[dict, dict]:
    matrix = {model: {arm: arm_matrix(jobs) for arm, jobs in model_arms(model, scope).items()} for model in MODELS}
    over = {model: overlap(arms) for model, arms in matrix.items() if {"A0", "A2", "R", "A2+R"} <= set(arms)}
    return matrix, over


def never_passed(matrix: dict) -> dict[str, list[int]]:
    """Criteria that no trial of any model or arm passed -> [0, trials]: candidates for hand verification."""
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for arms in matrix.values():
        for cells in arms.values():
            for key, (p, n) in cells.items():
                totals[key][0] += p
                totals[key][1] += n
    return {k: v for k, v in sorted(totals.items()) if v[1] and not v[0]}


TIERS = {"T1": {"T1"}, "T1+T2": {"T1", "T2"}, "T1+T2+T3": {"T1", "T2", "T3"}}


def defect_sets(defects: list[dict]) -> dict[str, set[str]]:
    """Excluded-criteria sets for rescoring: none, T1 (unpassable), T1+T2, T1+T2+T3."""
    out = {"none": set()}
    out.update({name: {d["key"] for d in defects if d["tier"] in tiers} for name, tiers in TIERS.items()})
    return out


def rescore_all(defects: list[dict], arms=("A0", "A2", "R", "A2+R")) -> dict[str, dict]:
    sets = defect_sets(defects)
    out = {}
    for model in MODELS:
        jobs = model_arms(model, "all")
        for arm in arms:
            if arm in jobs:
                out[f"{model}|{arm}"] = {name: rescore(jobs[arm], s) for name, s in sets.items()}
    return out


def finalize_labels(labels: list[dict], defects: list[dict]) -> list[dict]:
    """Root-cause labels with SOURCE split: 'SOURCE' only for hand-verified defects, 'SOURCE?' for the rest."""
    verified = {d["key"] for d in defects}
    out = []
    for x in labels:
        final = "SOURCE" if x["key"] in verified else "SOURCE?" if x["primary"] == "SOURCE" else x["primary"]
        out.append({**x, "final": final})
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum(a.count(c) * b.count(c) for c in set(a) | set(b)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="docs/failure_analysis/data")
    a = ap.parse_args()
    out = paths.ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    matrix, over = build("all")
    (out / "criteria.json").write_text(json.dumps(criteria(), indent=1))
    (out / "matrix_all.json").write_text(json.dumps(matrix))
    (out / "overlap_all.json").write_text(json.dumps(over, indent=1))
    never = never_passed(matrix)
    (out / "never_passed.json").write_text(json.dumps(never, indent=1))
    print(f"{len(matrix)} models; {len(never)} criteria never passed in any trial")
    defects = json.loads((out / "defects.json").read_text()) if (out / "defects.json").exists() else []
    if defects:
        (out / "rescored.json").write_text(json.dumps(rescore_all(defects), indent=1))
        for name, s in defect_sets(defects).items():
            if s:
                c = ceilings(s)
                print(f"ceiling without {name}: strict {c['strict']:.1f} n1 {c['n1']:.1f} mean {c['mean']:.1f}")
    labels = _jsonl(out / "labels.jsonl")
    if labels and defects:
        final = finalize_labels(labels, defects)
        (out / "labels_final.jsonl").write_text("".join(json.dumps(x) + "\n" for x in final))
        second = {x["key"]: x["primary"] for x in _jsonl(out / "labels_agreement.jsonl")}
        first = {x["key"]: x["primary"] for x in labels}
        keys = sorted(set(first) & set(second))
        if keys:
            k = cohen_kappa([first[x] for x in keys], [second[x] for x in keys])
            print(f"root-cause labels: {len(final)}; agreement on {len(keys)} items: kappa {k:.2f}")


if __name__ == "__main__":
    main()
