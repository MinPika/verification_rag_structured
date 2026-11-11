"""Queue runner resume logic."""

from __future__ import annotations

from vrag.sweep import pending

QUEUE = "# comment\ncmd a\n\ncmd b\ncmd c\n"


def test_successful_commands_are_skipped_failed_ones_rerun():
    lines, todo = pending(QUEUE, "0\tcmd a\n1\tcmd b\n")
    assert lines == ["cmd a", "cmd b", "cmd c"]
    assert todo == [(2, "cmd b"), (3, "cmd c")]


def test_empty_done_file_runs_everything():
    assert [c for _, c in pending(QUEUE, "")[1]] == ["cmd a", "cmd b", "cmd c"]


def test_job_health_flags_mostly_unscored_jobs(tmp_path):
    import json

    from vrag.run_arm import job_health

    def trial(name, reward):
        d = tmp_path / name
        d.mkdir()
        vr = {"rewards": {"reward": reward}} if reward is not None else None
        (d / "result.json").write_text(json.dumps({"task_name": "t", "verifier_result": vr,
                                                   "exception_info": None if reward is not None else {"x": 1}}))

    trial("a", 1.0)
    trial("b", 0.5)
    assert job_health(tmp_path) == 0
    for n in "cde":
        trial(n, None)
    assert job_health(tmp_path) == 3
    assert job_health(tmp_path / "missing") == 3
