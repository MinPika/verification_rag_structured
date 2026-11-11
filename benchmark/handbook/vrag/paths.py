from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "handbook"
TASKS = HANDBOOK / "tasks"
KB = ROOT / "kb"
CACHE = ROOT / "cache"

DEV_COMPANIES = ("careig", "crestwood", "vanguard")
COMPANIES = ("meridian", "sunshine", "crestwood", "ridgeline", "mojave", "vanguard", "gear_sytems", "prairie",
             "careig", "pathfinder")


def company(task: str) -> str:
    return next(c for c in COMPANIES if c in task)


def split(task: str) -> str:
    return "dev" if company(task) in DEV_COMPANIES else "test"


def all_tasks() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if p.is_dir())


def workspace(task: str) -> Path:
    return TASKS / task / "environment" / "initial_workspace"


def services(task: str) -> Path:
    return TASKS / task / "environment" / "initial_external_services"
