"""Experiment arms. The base ``Arm`` is the plain LAB agent (A0): LAB tools, prompt and loop, nothing added."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Arm:
    name = "A0"

    def __init__(self) -> None:
        self.log: list[dict] = []

    def prepare(self, *, task_id: str, executor: Any, tools: list[dict], system_prompt: str,
                trial_dir: Path) -> tuple[Any, list[dict], str]:
        """Return the (executor, tools, system prompt) the agent runs with. A0 changes nothing."""
        return executor, tools, system_prompt

    def run_agent(self, agent_loop: Any, **kw: Any) -> dict:
        return agent_loop.run_agent(**kw)


ARMS: dict[str, type[Arm]] = {"A0": Arm}


def make(name: str) -> Arm:
    from .fv import arm as _fv_arm  # noqa: F401  (registers arm V)
    if name not in ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {sorted(ARMS)}")
    return ARMS[name]()
