"""Claude Code harness arm (CC): model id mapping, credential loading, and the wrapper agent's prompt/effort wiring.

The agent tests need Harbor (installed only in handbook/.venv); they are skipped elsewhere."""

from __future__ import annotations

import asyncio
import importlib.util
import shlex
from pathlib import Path

import pytest

from vrag.run_arm import anthropic_model, read_credentials

has_harbor = importlib.util.find_spec("harbor") is not None


def test_anthropic_model_ids():
    assert anthropic_model("claude-haiku-5.5") == "claude-haiku-5-5"
    assert anthropic_model("claude-opus-5.5") == "claude-opus-5-5"
    assert anthropic_model("claude-sonnet-5") == "claude-sonnet-5"


def test_read_credentials_keeps_only_claude_keys(tmp_path):
    f = tmp_path / "cred.env"
    tok = "sk-ant-oat01-" + "x" * 60
    f.write_text(f"# comment\nCLAUDE_CODE_OAUTH_TOKEN='{tok}'\nANTHROPIC_BASE_URL=http://proxy\nOTHER=x\n")
    assert read_credentials(str(f)) == {"CLAUDE_CODE_OAUTH_TOKEN": tok}
    f.write_text("ANTHROPIC_API_KEY=\n")
    with pytest.raises(SystemExit):
        read_credentials(str(f))


@pytest.mark.skipif(not has_harbor, reason="harbor is installed only in handbook/.venv")
def test_agent_appends_task_prompt_and_sets_effort(tmp_path, monkeypatch):
    from harbor.agents.installed.base import BaseInstalledAgent
    from harbor.agents.installed.claude_code import ClaudeCode

    from vrag.claude_code_agent import HandbookClaudeCode

    task = tmp_path / "task"
    (task / "environment").mkdir(parents=True)
    (task / "system_prompt.md").write_text("Today's date is April 9, 2026. Don't ask.")
    env = type("Env", (), {"environment_dir": str(task / "environment")})()
    seen = {}

    async def fake_run(self, instruction, environment, context):
        seen["flags"] = self.build_cli_flags()

    async def fake_exec(self, environment, command, env=None, cwd=None, timeout_sec=None):
        seen["env"] = env

    monkeypatch.setattr(ClaudeCode, "run", fake_run)
    monkeypatch.setattr(BaseInstalledAgent, "exec_as_agent", fake_exec)
    agent = HandbookClaudeCode(logs_dir=tmp_path / "logs", model_name="anthropic/claude-haiku-5-5", effort="max")
    asyncio.run(agent.run("do it", env, None))
    prompt = Path(task / "system_prompt.md").read_text()
    assert f"--append-system-prompt {shlex.quote(prompt)}" in seen["flags"]
    asyncio.run(agent.exec_as_agent(env, "claude ...", env={"A": "1"}))
    assert seen["env"] == {"A": "1", "CLAUDE_CODE_EFFORT_LEVEL": "max"}
    with pytest.raises(ValueError):
        HandbookClaudeCode(logs_dir=tmp_path / "l2", model_name="x", effort="ultra")


def test_read_credentials_rejects_placeholder(tmp_path):
    f = tmp_path / "cred.env"
    f.write_text("CLAUDE_CODE_OAUTH_TOKEN=PASTE_THE_sk-ant-oat01_TOKEN_HERE\n")
    with pytest.raises(SystemExit) as e:
        read_credentials(str(f))
    assert "PASTE" not in str(e.value)


def test_api_error_trials_are_unscored(tmp_path):
    import json

    from vrag import report

    for name, last in (("auth", {"type": "result", "is_error": True, "api_error_status": 401}),
                       ("ok", {"type": "result", "is_error": False, "result": "done"})):
        d = tmp_path / "job" / f"t1__{name}"
        (d / "agent").mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"task_name": "x/t1",
                                                   "verifier_result": {"rewards": {"reward": 0.3}}}))
        (d / "agent" / "claude-code.txt").write_text('{"type":"system"}\n' + json.dumps(last) + "\n")
    got = {d.name: r for _t, r, _e, d in report.trials(tmp_path / "job")}
    assert got == {"t1__auth": None, "t1__ok": 0.3}


def test_claude_code_env_blocks_dotenv_placeholders():
    from vrag.run_arm import claude_code_env

    base = {"ANTHROPIC_API_KEY": "unused", "ANTHROPIC_BASE_URL": "http://127.0.0.1:3141", "PATH": "/bin"}
    env = claude_code_env(base, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-" + "x" * 60})
    assert env["ANTHROPIC_API_KEY"] == "" and env["ANTHROPIC_AUTH_TOKEN"] == "" and "ANTHROPIC_BASE_URL" not in env
    assert env["CLAUDE_CODE_OAUTH_TOKEN"].startswith("sk-ant-oat01-") and env["PATH"] == "/bin"
