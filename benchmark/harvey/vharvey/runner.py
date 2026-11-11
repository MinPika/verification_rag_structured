"""Run one LAB firm-knowledge trial with LAB's own harness pieces and the Copilot-proxy adapter.

Fidelity: the sandbox, tool executor, tool schemas, system preamble, skills and agent loop are imported from
lab_core unchanged (pinned clone, ``paths.LAB_COMMIT``); only the model transport differs (``proxy.ProxyAdapter``).
Arms that add tools or hooks plug in through ``Arm`` (see vharvey/arms.py) without editing lab_core.

Layout: ``runs/labroot`` is a LAB root whose ``tasks`` symlinks to the clone and whose ``results`` holds our runs,
so lab_core's load_task / score_rubric / results layout work as-is. A trial lives at
``runs/labroot/results/<run>/<task>/t<k>/`` with LAB's files (config.json, transcript.jsonl, metrics.json,
output/, workspace/) plus ``vharvey.json`` (arm, model calls, harness caveats).
"""

from __future__ import annotations

import json
import os
import shutil
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import paths, proxy

LABROOT = paths.RUNS / "labroot"
TASK_PREFIX = "firm-knowledge/tasks"


def ensure_labroot() -> Path:
    LABROOT.mkdir(parents=True, exist_ok=True)
    (LABROOT / "results").mkdir(exist_ok=True)
    link = LABROOT / "tasks"
    if not link.exists():
        link.symlink_to(paths.LAB_ROOT / "tasks", target_is_directory=True)
    return LABROOT


def activate() -> None:
    """Point lab_core at runs/labroot and put the podman->docker shim on PATH. Call before importing lab_core."""
    ensure_labroot()
    os.environ["LAB_ROOT"] = str(LABROOT)
    os.environ["PATH"] = f"{paths.BIN}{os.pathsep}{os.environ.get('PATH', '')}"


def lab_task(task_id: str) -> str:
    return f"{TASK_PREFIX}/{task_id}"


def trial_dir(run: str, task_id: str, trial: int) -> Path:
    return LABROOT / "results" / run / task_id / f"t{trial}"


def run_id(run: str, task_id: str, trial: int) -> str:
    """LAB run id (relative to LAB results dir) of a trial."""
    return f"{run}/{task_id}/t{trial}"


@dataclass
class TrialConfig:
    model: str
    effort: str | None = "high"
    max_turns: int = 200
    shell_timeout: int = 60
    temperature: float = 0.0
    context_limit: int | None = None  # None: model window minus proxy.CONTEXT_MARGIN
    enable_finish: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def run_trial(run: str, task_id: str, trial: int, cfg: TrialConfig, arm: Any = None) -> dict:
    """Run one trial; returns LAB metrics plus our status. Never raises for agent-side failures."""
    activate()
    from lab_core.harness import agent_loop
    from lab_core.harness.run import (
        DEFAULT_SKILLS,
        build_system_preamble,
        load_skills,
        load_task,
        setup_skill_scripts,
    )
    from lab_core.harness.tools import ToolExecutor, get_all_tool_definitions
    from lab_core.sandbox.sandbox import Sandbox

    from .arms import Arm

    arm = arm or Arm()
    tdir = trial_dir(run, task_id, trial)
    if (tdir / "metrics.json").exists():
        return json.loads((tdir / "metrics.json").read_text())
    if tdir.exists():  # an interrupted or infra-failed attempt: start clean so stale output cannot be graded
        results = (LABROOT / "results").resolve()
        if results not in tdir.resolve().parents:
            raise RuntimeError(f"refusing to clear {tdir}: not under {results}")
        shutil.rmtree(tdir)
    output_dir, workspace_dir = tdir / "output", tdir / "workspace"
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    task = load_task(lab_task(task_id))
    skills = list(DEFAULT_SKILLS)
    config = {"model": cfg.model, "task": lab_task(task_id), "run_id": run_id(run, task_id, trial),
              "max_turns": cfg.max_turns, "temperature": cfg.temperature, "shell_timeout": cfg.shell_timeout,
              "reasoning_effort": cfg.effort, "skills": skills, "sandbox_image": "lab-sandbox:latest",
              "enable_finish": cfg.enable_finish, "started_at": datetime.now(UTC).isoformat(),
              "arm": arm.name, "context_limit": cfg.context_limit or proxy.window_limit(cfg.model),
              "transport": "copilot-proxy chat completions",
              "lab_commit": paths.LAB_COMMIT, **cfg.extra}
    (tdir / "config.json").write_text(json.dumps(config, indent=2))

    sandbox = Sandbox(documents_dir=Path(task["docs_dir"]), output_dir=output_dir, workspace_dir=workspace_dir,
                      default_timeout=cfg.shell_timeout)
    adapter = proxy.ProxyAdapter(cfg.model, cfg.temperature, cfg.effort, context_limit=cfg.context_limit)
    status, error, result = "ok", None, None
    t0 = time.time()
    sandbox.start()
    try:
        executor = ToolExecutor(sandbox=sandbox, shell_timeout=cfg.shell_timeout, enable_finish=cfg.enable_finish)
        tools = get_all_tool_definitions(enable_finish=cfg.enable_finish)
        system_prompt = build_system_preamble(cfg.enable_finish) + load_skills(skills)
        setup_skill_scripts(skills, workspace_dir)
        executor, tools, system_prompt = arm.prepare(task_id=task_id, executor=executor, tools=tools,
                                                     system_prompt=system_prompt, trial_dir=tdir)
        result = arm.run_agent(agent_loop, adapter=adapter, system_prompt=system_prompt,
                               user_prompt=task["instructions"], tool_executor=executor, tools=tools,
                               max_turns=cfg.max_turns, transcript_path=str(tdir / "transcript.jsonl"))
    except Exception as e:  # infrastructure failure: recorded, never scored as a model failure
        status, error = "infra_error", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}"
    finally:
        sandbox.stop()

    meta = {"status": status, "error": error, "arm": arm.name, "seconds": round(time.time() - t0, 1),
            "model_calls": adapter.calls, "arm_log": arm.log,
            "deliverable_present": (output_dir / "response.md").exists()}
    (tdir / "vharvey.json").write_text(json.dumps(meta, indent=2, default=str))
    if result is None:
        return {"status": status, "error": error}
    metrics = {"model": cfg.model, "task": lab_task(task_id), "run_id": run_id(run, task_id, trial),
               "turn_count": result["turn_count"], "input_tokens": result["input_tokens"],
               "output_tokens": result["output_tokens"],
               "total_tokens": result["input_tokens"] + result["output_tokens"],
               "wall_clock_seconds": result["wall_clock_seconds"], "finished_cleanly": result["finished_cleanly"],
               "finish_reason": result["finish_reason"], "finish_summary": result["finish_summary"],
               "completed_at": datetime.now(UTC).isoformat(), "status": status, **result["tool_metrics"]}
    (tdir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    return metrics
