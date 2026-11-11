"""Filesystem layout of vrag_harvey. Everything is relative to the project root so runs are relocatable."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(os.environ.get("LAB_ROOT", ROOT / "harvey-labs"))
FK = LAB_ROOT / "tasks" / "firm-knowledge"
DMS = FK / "dms"
TASKS = FK / "tasks"
RUNS = ROOT / "runs"
CACHE = ROOT / "cache"
KB = ROOT / "kb"
BIN = ROOT / "bin"

LAB_COMMIT = "ba363f57c900166b616062c8153560d0508d9175"


def task_ids() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if (p / "task.json").is_file())


def lab_env() -> dict[str, str]:
    """Environment for lab_core: LAB_ROOT, results under runs/, and the podman->docker shim first on PATH."""
    env = dict(os.environ)
    env["LAB_ROOT"] = str(LAB_ROOT)
    env["PATH"] = f"{BIN}{os.pathsep}{env.get('PATH', '')}"
    return env


def activate_lab_env() -> None:
    """Apply lab_env() to this process (lab_core reads LAB_ROOT and spawns `podman` from PATH)."""
    os.environ.update(lab_env())
