"""Plan alternatives (fact sheet, soft stops) and the exec tool (model-invoked verifier code, no monitor)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from vrag import facts, package, paths
from vrag.brief import SCOPE, make_brief
from vrag.freeze import diff, freeze

TASK = "hr_crestwood_university_2071c562"
IW_DIR = paths.HANDBOOK / "docker" / "openhands-runner"
EXEC = Path(__file__).resolve().parents[1] / "vrag" / "runtime" / "policy_pkg" / "iw_exec.py"
needs_task = pytest.mark.skipif(not (paths.KB / TASK / "kb.json").exists(), reason="compiled KB not available")


def test_brief_softstop_scopes_stop_rules_only():
    kb = {"rules": [{"id": "R1", "kind": "stop", "statement": "Hold the case if ID is missing."},
                    {"id": "R2", "kind": "prohibition", "statement": "Never DM."}]}
    strict, soft = make_brief(kb), make_brief(kb, softstop=True)
    assert SCOPE not in strict
    assert f"Hold the case if ID is missing.{SCOPE}" in soft and f"Never DM.{SCOPE}" not in soft


def test_runner_softstop_rewrites_rule_4():
    sys.modules.setdefault("openhands_runner", types.ModuleType("openhands_runner"))
    sys.path.insert(0, str(package.RUNTIME))
    try:
        import vrag_runner as runner
    finally:
        sys.path.remove(str(package.RUNTIME))
    head = runner.STRICT_RULE.sub(runner.SOFTSTOP_RULE, runner.BRIEF_HEAD, count=1)
    assert head != runner.BRIEF_HEAD and "follow it instead of" not in head and "(4) a stop/hold" in head


def test_fact_sheet_lint_clean_render():
    valid = {"D1.0001", "D1.0002"}
    sheet = {"general": ["Today is 2026-04-09."],
             "items": [{"item": "Email 4", "source": "mailbox 4",
                        "facts": ["Email 4 mentions pay.", "Do not reply to the sender."],
                        "sop": [{"block": "[D1.0001]", "covers": "payroll routing"}, {"block": "D9.9999"}],
                        "questions": ["Should this be read as a legal threat? It has no attorney mention."]},
                       {"source": "no label: dropped"}]}
    found = facts.lint(sheet, valid)
    assert found["bad_blocks"] == ["D9.9999"]
    assert [d.split(":")[0] for d in found["directives"]] == ["items[0].facts[1]"]  # questions may ask "should"
    c = facts.clean(sheet, valid)
    assert len(c["items"]) == 1 and c["items"][0]["sop"] == [{"block": "D1.0001", "covers": "payroll routing"}]
    text = facts.render(c)
    assert text.startswith(facts.HEADER) and "Item 1: Email 4 [mailbox 4]" in text
    assert "SOP: D1.0001 (payroll routing)" in text and "Open question: Should" in text


@needs_task
def test_package_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    sheet = paths.KB / TASK / "facts_kb_seed.txt"
    if not sheet.exists():
        pytest.skip("fact sheet not compiled")
    out = package.build_package(TASK, "A2", "kb_seed", facts=True, softstop=True, exec_=True)
    assert out == tmp_path / "runs" / "pkgs" / "A2-kb_seed-facts-soft-exec" / TASK / "policy"
    data = out / "data"
    assert (data / "facts.txt").read_text() == sheet.read_text() and not (data / "plan.txt").exists()
    assert (data / "softstop").exists() and (data / "exec_enabled").exists() and (out / "iw_exec.py").exists()
    plain = package.build_package(TASK, "A2", "kb_seed", plan_on=False)
    assert plain.parent.parent.name == "A2-kb_seed-noplan" and not (plain / "data" / "exec_enabled").exists()
    assert not (plain / "data" / "plan.txt").exists() and not (plain / "data" / "facts.txt").exists()


def _iw(mode: str, payload: dict, state: Path) -> str:
    env = {**os.environ, "PYTHONPATH": str(IW_DIR), "INTERWHEN_TASK": TASK, "INTERWHEN_STATE_DIR": str(state / "iw"),
           "VRAG_STATE": str(state / "vrag"),
           "INTERWHEN_WORKDIR": str(paths.TASKS / TASK / "environment" / "initial_workspace")}
    return subprocess.run([sys.executable, str(EXEC), mode], input=json.dumps(payload), capture_output=True,
                          text=True, env=env, timeout=120, check=True).stdout


@pytest.mark.skipif(not (IW_DIR / "interwhen_sop" / "verifiers" / f"{TASK}.py").exists(),
                    reason="the interwhen verifiers not available")
def test_iw_exec_checks_run_on_demand(tmp_path):
    todo = _iw("completion", {}, tmp_path)
    assert "still open" in todo and "OFFBOARD-Teodoor-04192026" in todo
    email = {"to": "a.parke@crestwood.edu", "subject": "Re: Inquiry", "body": "Hi"}
    bad = _iw("action", {"tool_name": "google_mail__send_email", "arguments": email}, tmp_path)
    assert "would violate the SOP" in bad and "nothing was executed" in bad
    assert _iw("action", {"tool_name": "google_mail__list_emails", "arguments": {}}, tmp_path).startswith("OK")
    log = [json.loads(x) for x in (tmp_path / "vrag" / "exec.jsonl").read_text().splitlines()]
    assert [x["mode"] for x in log] == ["completion", "action"]  # read-only calls are not checked or logged
    assert json.loads(_iw("hook-pre", {"tool_name": "slack__post_message"}, tmp_path)) == {"decision": "allow"}


def test_freeze_manifest_and_check(tmp_path):
    (tmp_path / "vrag").mkdir()
    (tmp_path / "vrag" / "a.py").write_text("x = 1\n")
    (tmp_path / "runs").mkdir()
    freeze("t", root=tmp_path)
    assert diff("t", root=tmp_path) == [] and (tmp_path / "runs" / "freeze" / "t.tgz").exists()
    (tmp_path / "vrag" / "a.py").write_text("x = 2\n")
    assert diff("t", root=tmp_path) == ["vrag/a.py"]


def test_exec_note_mentions_code_only_in_code_mode():
    sys.modules.setdefault("openhands_runner", types.ModuleType("openhands_runner"))
    sys.path.insert(0, str(package.RUNTIME))
    try:
        import vrag_runner as runner
    finally:
        sys.path.remove(str(package.RUNTIME))
    text = runner.EXEC_NOTE.format(shown="")
    assert "policy__verify_completion" in text and "policy__procedure" not in text and "{" not in text
