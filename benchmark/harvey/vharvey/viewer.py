"""Dashboard for graded runs: one light page (index + docs) plus one detail file per trial, loaded on demand.

    python -m vharvey.viewer RUN1,RUN2,... [name]      # -> logs/viewer/<name>.html + logs/viewer/data/...

Views: Overview (run table + story), the markdown docs (Cases, Results, Iterations, Story, API spec, Errors,
Defects) with a table of contents, and Trials: a sidebar to pick run / compare-run / task (filterable, keyboard
j/k) and five sections per trial (Summary, Rubrics, Model calls, FV calls, Response). Serve the directory over HTTP
(``python -m http.server 8071`` in logs/viewer); detail files are fetched, so ``file://`` does not work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import batch, compare, failure_log, paths

MAX_RESULT = 6000
METRIC_KEYS = ("turn_count", "wall_clock_seconds", "input_tokens", "finish_reason")
OUT = paths.ROOT / "logs" / "viewer"
RUN_INFO = {
    "base-dev15": "A0, 3 models, first 15 dev tasks (first look)",
    "base-dev50": "A0 plain LAB agent, dev 50, k=2", "base-test60": "A0 plain LAB agent, test 60",
    "V1-dev50": "FV tools from the start (v1.1)", "V2-dev50": "FV v2 + fixes + 'search first' prompt",
    "VC-dev50": "V2 + completeness check from the start", "VL-dev50": "verify late: FV tools appear at first finish",
    "VLC-dev50": "verify late + completeness check, k=2", "VL-test60": "verify late, test 60",
    "VLC-test60": "verify late + completeness check, test 60",
    "VL-dev50-pregate": "VL answers as they were at the gate (before verifying)",
    "VLC-dev50-pregate": "VLC answers at the gate (before verifying)",
    "VL-test60-pregate": "VL test answers at the gate", "VLC-test60-pregate": "VLC test answers at the gate",
    "D-late-test": "DSH · FINAL: verify late + completeness (frozen v3-dsh), AHE test 70, after verification",
    "D-late-test-pregate": "DSH · plain DSH answers of the same test trajectories (at the gate)",
    "D-late-test-k2": "DSH · FINAL, second independent test trial (k=2), after verification",
    "D-late-test-k2-pregate": "DSH · plain DSH answers of the k=2 test trajectories",
    "D-late-train": "DSH · verify late + completeness (v3-dsh), AHE train 80, after verification",
    "D-late-train-pregate": "DSH · plain DSH answers of the same train trajectories",
    "D-start-train20": "DSH · ablation: verifier tools from the start, 20 train tasks",
    "D-v3-val": "DSH · v3-dsh on AHE validation 20 (selection run)", "D-v3-val-pregate": "plain DSH, same trajectories",
    "D-v4-val": "DSH · v4 (not adopted) on AHE validation 20", "D-v4-val-pregate": "plain DSH, same trajectories",
    "D-v4-trainbroken": "DSH · v4 on the 9 train tasks v3 broke (diagnostic)",
    "D-v4-trainbroken-pregate": "plain DSH, same trajectories",
    "U-late-k1": "DSH · frozen system on the 80 tasks outside the AHE split, trial 1",
    "U-late-k1-pregate": "plain DSH answers of the same trajectories (outside-split trial 1)",
    "U-late-k2": "DSH · frozen system on the 80 tasks outside the AHE split, trial 2",
    "U-late-k2-pregate": "plain DSH answers of the same trajectories (outside-split trial 2)",
}
DOCS = [("DSH · Final report", "docs/DSH_REPORT.md"), ("DSH · Train analysis", "docs/DSH_TRAIN_ANALYSIS.md"),
        ("DSH · Test analysis", "docs/DSH_TEST_ANALYSIS.md"), ("DSH · Test k=2", "docs/DSH_TEST_K2_ANALYSIS.md"),
        ("DSH · Outside split k=1", "docs/DSH_UNUSED_K1_ANALYSIS.md"),
        ("DSH · Outside split k=2", "docs/DSH_UNUSED_K2_ANALYSIS.md"),
        ("DSH · Validation v3", "docs/DSH_VAL_v3-val.md"),
        ("DSH · Validation v4 (not adopted)", "docs/DSH_VAL_v4-val.md"),
        ("1 · Baseline failures (train)", "docs/BASELINE_TRAIN.md"), ("2 · Approach", "docs/APPROACH.md"),
        ("3 · Results (like-for-like)", "docs/RESULTS_PAIRED.md"), ("4 · Architecture A–Z", "docs/ARCHITECTURE.md"),
        ("Cases", "docs/CASES.md"), ("Iterations", "docs/ITERATIONS.md"), ("Errors", "docs/ERRORS.md"),
        ("API spec", "docs/FV_API_SPEC.md"), ("Benchmark defects", "docs/BENCHMARK_DEFECTS.md")]


def _turns(tdir: Path) -> list[dict]:
    turns: list[dict] = []
    for line in (tdir / "transcript.jsonl").open():
        d = json.loads(line)
        if d["role"] == "assistant":
            turns.append({"turn": d["turn"], "text": d.get("text") or "",
                          "calls": [{"id": tc["id"], "name": tc["name"], "args": tc["arguments"]}
                                    for tc in d.get("tool_calls") or []], "results": []})
        elif turns:
            res = d.get("result") or ""
            turns[-1]["results"].append({"id": d.get("tool_call_id"), "chars": len(res), "text": res[:MAX_RESULT]})
    return turns


def _fv_calls(meta: dict) -> list[dict]:
    out = []
    for e in meta.get("arm_log") or []:
        res = e.get("result")
        for r in res if isinstance(res, list) else [res]:
            if isinstance(r, dict):
                out.append({"tool": e.get("tool"), "matter_id": r.get("matter_id"), "field": r.get("field"),
                            "asked": r.get("asked"), "verdict": r.get("verdict"),
                            "actual": r.get("actual") if e.get("tool") != "fv_check_complete" else
                            [m["matter_id"] for m in r.get("missing_from_your_list") or []],
                            "note": r.get("note") or r.get("error"), "evidence": r.get("evidence")})
    return out


def _trial(run: str, row: dict) -> dict:
    tdir = Path(row["dir"])
    task = json.loads((paths.TASKS / row["task"] / "task.json").read_text())
    judges = failure_log._judges(tdir)
    key = failure_log.page_name(row)
    page = paths.ROOT / "logs" / run / row["model"] / f"{key}.md"
    analysis = ""
    if page.exists() and failure_log.ANALYSIS in page.read_text():
        analysis = page.read_text().split(failure_log.ANALYSIS, 1)[1].strip()
    resp = tdir / "output" / "response.md"
    meta = json.loads((tdir / "vharvey.json").read_text())
    detail = {"instructions": task["instructions"], "analysis": analysis, "fv_calls": _fv_calls(meta),
              "response": resp.read_text() if resp.exists() else None, "turns": _turns(tdir),
              "criteria": [{"id": c["id"], "kind": failure_log.kind(c), "title": c["title"],
                            "match": c["match_criteria"],
                            "judges": {m: {"verdict": j.get(c["id"], {}).get("verdict"),
                                           "reasoning": j.get(c["id"], {}).get("reasoning", "")}
                                       for m, j in judges.items()}} for c in task["criteria"]]}
    rel = Path("data") / run / row["model"] / f"{key}.json"
    (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
    (OUT / rel).write_text(json.dumps(detail))
    tm = compare.task_metrics(row["task"], str(tdir))
    metrics = json.loads((tdir / "metrics.json").read_text())
    return {"run": run, "model": row["model"], "task": row["task"], "trial": row["trial"],
            "key": key, "title": task["title"],
            "arm": json.loads((tdir / "config.json").read_text()).get("arm", "A0"),
            "crit": row["crit"], "ap": row["all_pass"], "precision": tm["precision"], "recall": tm["recall"],
            "turns": tm["turns"], "metrics": {k: metrics.get(k) for k in METRIC_KEYS},
            "dir": str(tdir.relative_to(paths.ROOT)), "url": rel.as_posix()}


def build(runs: list[str], name: str = "index") -> Path:
    trials = []
    for run in runs:
        failure_log.build(run)
        rows = batch.results(run)
        multi_model = len({r["model"] for r in rows}) > 1
        for r in rows:
            t = _trial(run, r)
            if multi_model:  # base-dev15 has three models: key tasks per model
                t["key"] = f"{t['key']}·{r['model'].split('-')[0]}"
            trials.append(t)
    docs = {title: (paths.ROOT / p).read_text() for title, p in DOCS if (paths.ROOT / p).exists()}
    data = {"runs": runs, "run_info": {r: RUN_INFO.get(r, "") for r in runs}, "trials": trials, "docs": docs}
    OUT.mkdir(parents=True, exist_ok=True)
    html = (Path(__file__).with_name("viewer.html")).read_text()
    out = OUT / f"{name}.html"
    out.write_text(html.replace("__DATA__", json.dumps(data).replace("</", "<\\/")))
    return out


if __name__ == "__main__":
    print(build(sys.argv[1].split(","), sys.argv[2] if len(sys.argv) > 2 else "index"))
