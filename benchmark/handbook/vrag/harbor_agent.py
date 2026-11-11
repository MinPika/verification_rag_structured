"""Harbor agents for the vrag arms (host side). Same OpenHands harness as A0; additionally uploads the task's
compiled policy package into the container's MCP proxy package dir and the vrag runner, then launches the proxy
with the policy toolset enabled.

  A1  policy__* tools (KB lookup, exact templates, search/read, calculators)
  A2  A1 + compiled SOP brief in the system prompt
  A3  A2 + interwhen gates (PreToolUse + Stop hooks) + policy__check
Options: ``--ak rhooks=1`` (A1/A2) adds the interwhen verifiers (checklist + PreToolUse + Stop hooks, their
blind-run configuration) on top of our representation; ``--ak code=sop|verifiers`` makes SOP retrieval return code.
``--ak facts=1`` replaces the drafted plan by the case fact sheet; ``--ak softstop=1`` scopes stop/hold rules to their
item; ``--ak exec=1`` adds policy__verify_action / policy__verify_completion, which run the task's verifier code on
demand with no monitor (the exec tool), and ``--ak finish_check=1`` one completion check at finish.
Tier: ``--ak tier=kb`` (guards/plan from handbook+instruction, default) or ``--ak tier=kb_seed`` (also seed data;
information parity with the interwhen baseline). The KB itself is always compiled from the policy documents only.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from agent_harness.interwhen_agent import LOCAL_RUNNER_DIR, REMOTE_IW_DIR
from agent_harness.openhands_agent import (
    HEALTH_TIMEOUT,
    PROBE_TIMEOUT,
    PROXY_START_CMD,
    REMOTE_LOG_DIR,
    REMOTE_PROXY_LOG_PATH,
    OpenHandsAgent,
)
from harbor.environments.base import BaseEnvironment

from .package import RUNTIME, build_package

REMOTE_RUNNER = "/app/vrag-runner"
REMOTE_PKG = "/app/packages/policy"


class VragBase(OpenHandsAgent):
    arm = "A1"
    runner_path = f"{REMOTE_RUNNER}/vrag_runner.py"

    def __init__(self, *args, **kwargs) -> None:
        self.tier = str(kwargs.pop("tier", "kb"))
        self.plan_on = str(kwargs.pop("plan", "1")) not in ("0", "false", "False")
        self.audit = str(kwargs.pop("audit", "0")) in ("1", "true", "True")
        self.msgs = str(kwargs.pop("msgs", "0")) in ("1", "true", "True")
        self.code = str(kwargs.pop("code", "")).strip()  # "" | "sop" | "verifiers"
        self.rhooks = str(kwargs.pop("rhooks", "0")) in ("1", "true", "True")
        self.checker_first = str(kwargs.pop("checker_first", "0")) in ("1", "true", "True")
        self.facts = str(kwargs.pop("facts", "0")) in ("1", "true", "True")
        self.softstop = str(kwargs.pop("softstop", "0")) in ("1", "true", "True")
        self.exec_ = str(kwargs.pop("exec", "0")) in ("1", "true", "True")
        self.finish_check = str(kwargs.pop("finish_check", "0")) in ("1", "true", "True")
        if self.rhooks and self.arm == "A3":
            raise ValueError("rhooks replaces our gate: use it with A1/A2")
        if self.exec_ and (self.rhooks or self.arm == "A3"):
            raise ValueError("exec replaces the monitor: do not combine with rhooks or A3")
        super().__init__(*args, **kwargs)

    @staticmethod
    def name() -> str:
        return "openhands-vrag"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        task = Path(environment.environment_dir).parent.name
        pkg = build_package(task, self.arm, self.tier, self.plan_on, self.audit, self.msgs, self.code, self.facts,
                            self.softstop, self.exec_)
        await environment.exec(f"rm -rf {REMOTE_PKG} {REMOTE_RUNNER} && mkdir -p {REMOTE_RUNNER}",
                               timeout_sec=PROBE_TIMEOUT)
        await environment.upload_dir(str(pkg), REMOTE_PKG)
        await environment.upload_file(str(RUNTIME / "vrag_runner.py"), f"{REMOTE_RUNNER}/vrag_runner.py")
        if self.rhooks or self.exec_:
            await environment.upload_dir(str(LOCAL_RUNNER_DIR), REMOTE_IW_DIR)
        sets = "policy_core" + (" policy_check" if self.arm == "A3" else "") + \
            (" policy_code" if self.code == "sop" else "") + \
            (" policy_exec" if self.exec_ else "")  # only our compiled procedures are runnable
        launch = (f"mkdir -p {REMOTE_LOG_DIR} && chmod -R a+rX {REMOTE_PKG} && "
                  f"WORLDBENCH_TOOL_SETS=\"$WORLDBENCH_TOOL_SETS {sets}\" nohup {PROXY_START_CMD} </dev/null "
                  f">>{REMOTE_PROXY_LOG_PATH} 2>&1 &")
        res = await environment.exec(launch, timeout_sec=PROBE_TIMEOUT)
        if res.return_code != 0:
            raise RuntimeError(f"failed to launch MCP proxy with policy package: {res.stderr}")
        await self._wait_for_proxy(environment)
        await super().setup(environment)  # probes runner; proxy already healthy -> not relaunched

    def _extra_run_config(self, task_dir: Path) -> dict:
        cfg = {"vrag": {"arm": self.arm, "task": task_dir.name, "tier": self.tier, "plan": self.plan_on,
                        "audit": self.audit, "msgs": self.msgs, "code": self.code, "rhooks": self.rhooks,
                        "checker_first": self.checker_first, "facts": self.facts, "softstop": self.softstop,
                        "exec": self.exec_, "finish_check": self.finish_check}}
        if self.rhooks:  # same settings as the R arm (run_arm.AGENTS["R"])
            cfg["interwhen"] = {"task": task_dir.name, "maxCompletionDenials": 6, "maxStaleDenials": 2,
                                "checklist": True}
        return cfg


class VragA1(VragBase):
    arm = "A1"


class VragA2(VragBase):
    arm = "A2"


class VragA3(VragBase):
    arm = "A3"


__all__ = ["VragA1", "VragA2", "VragA3", "build_package", "HEALTH_TIMEOUT", "shlex"]
