"""Sandbox for compiled SOP code."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vrag" / "runtime" / "policy_pkg"))
import sop_exec  # noqa: E402

COMMON = 'HOLIDAYS = ["2026-02-16"]\nTEMPLATES = {"T14": {"subject": "Exit Interview – [Name]"}}\n'


def test_business_days_skip_weekends_and_holidays():
    assert str(sop_exec.add_business_days("2026-02-13", 2, ["2026-02-16"])) == "2026-02-18"
    assert sop_exec.business_days_between("2026-02-13", "2026-02-18", ["2026-02-16"]) == 2


def test_run_returns_actions_and_uses_shared_names():
    code = ('def f(case, today=""):\n'
            '    return [send_email(case["to"], fill(TEMPLATES["T14"]["subject"], Name="Ann"), "b"),\n'
            '            note(fmt(add_business_days(today, 2, HOLIDAYS)))]\n')
    out = sop_exec.run(COMMON, code, "f", {"to": "a@b.c"}, "2026-02-13")
    assert out["ok"] and out["actions"][0]["subject"] == "Exit Interview – Ann"
    assert out["actions"][1] == {"action": "note", "text": "02/18/2026"}


def test_strptime_works_under_restricted_builtins():
    code = ('def f(case, today=""):\n'
            '    return [note(datetime.strptime("2026-02-13 09:00", "%Y-%m-%d %H:%M").isoformat())]\n')
    assert sop_exec.run("", code, "f", {}, "")["ok"]


def test_unsafe_code_is_rejected_statically():
    problems = sop_exec.check("import os\nopen('x')\nwhile True:\n    pass\nx.__class__\n")
    assert len(problems) == 4
    assert not sop_exec.run("", "def f(c, t=''):\n    return [__import__('os')]\n", "f", {}, "")["ok"]


def test_errors_and_bad_returns_are_reported():
    assert "KeyError" in sop_exec.run("", "def f(c, t=''):\n    return [c['x']]\n", "f", {}, "")["error"]
    assert "list of actions" in sop_exec.run("", "def f(c, t=''):\n    return 5\n", "f", {}, "")["error"]
