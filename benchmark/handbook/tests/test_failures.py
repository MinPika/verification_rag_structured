"""Criterion-level failure analysis: state thresholds, per-criterion parsing, rescoring and ceilings."""

from __future__ import annotations

import json

from vrag import failures


def test_state_thresholds():
    assert failures.state([0, 2]) == "fail" and failures.state([1, 4]) == "fail"
    assert failures.state([1, 2]) == "flaky" and failures.state([2, 2]) == "pass"
    assert failures.state(None) is None and failures.state([0, 0]) is None


def _trial(job, name, lines, reward=0.5):
    d = job / name
    (d / "verifier").mkdir(parents=True)
    result = {"task_name": "x/t1", "verifier_result": {"rewards": {"reward": reward}}}
    (d / "result.json").write_text(json.dumps(result))
    (d / "verifier" / "test-stdout.txt").write_text("\n".join(lines) + "\n")
    return d


def test_trial_outcomes_and_rescore(tmp_path):
    job = tmp_path / "job"
    _trial(job, "a", ["  [PASS] c1: ok", "  [FAIL] c2: wrong value", "  [PASS] c3: ok"])
    _trial(job, "b", ["  [FAIL] c1: no", "  [FAIL] c2: wrong value", "  [PASS] c3: ok"])
    assert failures.trial_outcomes(job / "a") == {"c1": (True, "ok"), "c2": (False, "wrong value"), "c3": (True, "ok")}
    assert failures.arm_matrix([job]) == {"t1|c1": [1, 2], "t1|c2": [0, 2], "t1|c3": [2, 2]}
    raw = failures.rescore([job], set())
    assert raw["strict"] == 0.0 and raw["n1"] == 50.0
    clean = failures.rescore([job], {"t1|c2"})
    assert clean["strict"] == 50.0 and clean["n1"] == 100.0


def test_ceilings(monkeypatch):
    monkeypatch.setattr(failures, "criteria", lambda: {f"t{t}|c{c}": {} for t in range(4) for c in range(4)})
    c = failures.ceilings({"t0|c0", "t1|c0", "t1|c1"})
    assert c["strict"] == 50.0 and c["n1"] == 75.0 and round(c["mean"], 2) == round(100 * (1 - 3 / 16), 2)


def test_never_passed_and_defect_sets():
    matrix = {"m1": {"A0": {"t|a": [0, 2], "t|b": [1, 2]}}, "m2": {"A0": {"t|a": [0, 2], "t|b": [0, 2]}}}
    assert failures.never_passed(matrix) == {"t|a": [0, 4]}
    sets = failures.defect_sets([{"key": "t|a", "tier": "T1"}, {"key": "t|b", "tier": "T3"}])
    assert sets["none"] == set() and sets["T1"] == {"t|a"} and sets["T1+T2+T3"] == {"t|a", "t|b"}


def test_finalize_labels_and_kappa():
    labels = [{"key": "k1", "primary": "SOURCE"}, {"key": "k2", "primary": "SOURCE"}, {"key": "k3", "primary": "PLAN"}]
    final = failures.finalize_labels(labels, [{"key": "k1", "tier": "T1"}])
    assert [x["final"] for x in final] == ["SOURCE", "SOURCE?", "PLAN"]
    assert failures.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    assert round(failures.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]), 6) == 0.0
