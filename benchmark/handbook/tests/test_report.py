"""Strict pass follows the verifier's all-criteria-passed result, not reward == 1."""

from __future__ import annotations

import json

from vrag.report import all_passed, summarize


def _trial(job, name, reward, line):
    d = job / name
    (d / "verifier").mkdir(parents=True)
    result = {"task_name": "x/t1", "verifier_result": {"rewards": {"reward": reward}}}
    (d / "result.json").write_text(json.dumps(result))
    if line is not None:
        (d / "verifier" / "test-stdout.txt").write_text(f"[sop-verifier] {line}; score={reward}\n")
    return d


def test_all_passed_uses_verifier_line(tmp_path):
    assert all_passed(_trial(tmp_path, "a", 0.9934, "19/19 rubrics passed"), 0.9934)
    assert not all_passed(_trial(tmp_path, "b", 1.0, "18/19 rubrics passed"), 1.0)
    assert all_passed(_trial(tmp_path, "c", 1.0, None), 1.0)  # fallback without verifier output


def test_summarize_strict_rate(tmp_path):
    job = tmp_path / "job"
    _trial(job, "a", 0.9934, "19/19 rubrics passed")
    _trial(job, "b", 0.9, "17/19 rubrics passed")
    s = summarize([job])
    assert s["rows"]["t1"]["sp1"] == 50.0 and round(s["rows"]["t1"]["mean"], 2) == 94.67


def test_n1_allows_one_missed_criterion(tmp_path):
    from vrag.report import n1_passed, rubric_misses
    assert rubric_misses(_trial(tmp_path, "a", 0.95, "18/19 rubrics passed"), 0.95) == 1
    assert n1_passed(_trial(tmp_path, "b", 0.95, "18/19 rubrics passed"), 0.95)
    assert not n1_passed(_trial(tmp_path, "c", 0.9, "17/19 rubrics passed"), 0.9)
    assert not n1_passed(_trial(tmp_path, "d", 0.7, None), 0.7)  # undecidable without verifier output: fail
    assert n1_passed(_trial(tmp_path, "e", 1.0, None), 1.0)


def test_summarize_n1_rate(tmp_path):
    job = tmp_path / "job"
    _trial(job, "a", 0.9934, "19/19 rubrics passed")
    _trial(job, "b", 0.95, "18/19 rubrics passed")
    _trial(job, "c", 0.9, "17/19 rubrics passed")
    _trial(job, "d", 0.9, "17/19 rubrics passed")
    row = summarize([job])["rows"]["t1"]
    assert row["sp1"] == 25.0 and row["n1"] == 50.0


def test_agent_timeout_is_excluded(tmp_path):
    job = tmp_path / "job"
    _trial(job, "a", 0.9934, "19/19 rubrics passed")
    d = _trial(job, "b", 0.2, "5/19 rubrics passed")
    res = json.loads((d / "result.json").read_text())
    res["exception_info"] = {"exception_message": "Agent execution timed out after 3600.0 seconds"}
    (d / "result.json").write_text(json.dumps(res))
    s = summarize([job])
    assert s["errors"] == 1 and s["rows"]["t1"]["n"] == 1 and s["rows"]["t1"]["sp1"] == 100.0
