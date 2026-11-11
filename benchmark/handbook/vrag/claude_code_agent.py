"""HANDBOOK.md plain-agent baseline in the Claude Code harness (Harbor's built-in ClaudeCode agent).

Same tasks, tools and grader as the OpenHands plain agent (A0); only the agent harness differs. Harbor's built-in
agent installs Claude Code in the task container and registers the task's MCP server (mcp-proxy at
localhost:8000/mcp), but two HANDBOOK specifics are added here:
- the task container's MCP proxy (mail, Slack, calendar, Jira, Shopify, files) is started before the agent runs, as
  the OpenHands agent does;
- the task's system_prompt.md (today's date, the acting user, the workspace) is passed with --append-system-prompt.
Effort is set with CLAUDE_CODE_EFFORT_LEVEL, which takes precedence inside Claude Code and accepts "max" (Harbor's
--effort flag only accepts low/medium/high).

    harbor run -p <tasks> --agent-import-path vrag.claude_code_agent:HandbookClaudeCode \
        -m anthropic/claude-haiku-5-5 --ak effort=max ...
Credentials come from the host environment: CLAUDE_CODE_OAUTH_TOKEN (Claude subscription, `claude setup-token`) or
ANTHROPIC_API_KEY. ANTHROPIC_BASE_URL must be unset so calls go to Anthropic, not the Copilot proxy
(vrag.run_arm CC does this).
"""

from __future__ import annotations

import asyncio
import shlex
import time
from pathlib import Path

from agent_harness.openhands_agent import (
    HEALTH_TIMEOUT,
    HEALTH_URL,
    PROBE_TIMEOUT,
    PROXY_START_CMD,
    REMOTE_LOG_DIR,
    REMOTE_PROXY_LOG_PATH,
)
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

EFFORTS = ("low", "medium", "high", "xhigh", "max")


class HandbookClaudeCode(ClaudeCode):
    def __init__(self, *args, effort: str = "max", **kwargs) -> None:
        if effort not in EFFORTS:
            raise ValueError(f"effort must be one of {EFFORTS}, got {effort!r}")
        self.effort = effort
        super().__init__(*args, **kwargs)

    @staticmethod
    def name() -> str:
        return "claude-code-handbook"

    async def _proxy_healthy(self, environment: BaseEnvironment) -> bool:
        res = await environment.exec(f"curl -fsS -o /dev/null --max-time 5 {shlex.quote(HEALTH_URL)}",
                                     timeout_sec=PROBE_TIMEOUT)
        return res.return_code == 0

    async def setup(self, environment: BaseEnvironment) -> None:
        if not await self._proxy_healthy(environment):
            launch = (f"mkdir -p {REMOTE_LOG_DIR} && nohup {PROXY_START_CMD} </dev/null "
                      f">>{REMOTE_PROXY_LOG_PATH} 2>&1 &")
            res = await environment.exec(launch, timeout_sec=PROBE_TIMEOUT)
            if res.return_code != 0:
                raise RuntimeError(f"failed to launch the MCP proxy: {(res.stderr or '').strip()}")
        deadline = time.monotonic() + HEALTH_TIMEOUT
        while not await self._proxy_healthy(environment):
            if time.monotonic() > deadline:
                raise RuntimeError(f"MCP proxy at {HEALTH_URL} not healthy within {HEALTH_TIMEOUT}s")
            await asyncio.sleep(2)
        await super().setup(environment)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        system_prompt = (Path(environment.environment_dir).parent / "system_prompt.md").read_text()
        # build_cli_flags inserts values verbatim into a shell command, so quote it here.
        self._resolved_flags["append_system_prompt"] = shlex.quote(system_prompt)
        await super().run(instruction, environment, context)

    async def exec_as_agent(self, environment: BaseEnvironment, command: str, env: dict[str, str] | None = None,
                            cwd: str | None = None, timeout_sec: int | None = None):
        if env is not None:
            env = {**env, "CLAUDE_CODE_EFFORT_LEVEL": self.effort}
        return await super().exec_as_agent(environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec)
