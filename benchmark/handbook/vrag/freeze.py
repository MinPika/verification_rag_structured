"""Freeze the code an experiment runs with: a hash manifest (runs/FREEZE_<name>.json) and a restorable tarball
(runs/freeze/<name>.tgz) of vrag/, tests/ and pyproject.toml. The project is not under version control of its own,
so the tarball is what a frozen result can be reproduced from.

    python -m vrag.freeze <name> [--notes "..."]
    python -m vrag.freeze <name> --check      # exit 1 if the current code differs from the manifest
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import tarfile
from pathlib import Path

from . import paths

INCLUDE = ("vrag", "tests", "pyproject.toml")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def files(root: Path = paths.ROOT) -> list[Path]:
    out = []
    for name in INCLUDE:
        p = root / name
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += [f for f in p.rglob("*") if f.is_file() and not SKIP_DIRS & set(f.relative_to(root).parts)
                    and f.suffix != ".pyc"]
    return sorted(out)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def manifest(root: Path = paths.ROOT) -> dict[str, str]:
    return {str(f.relative_to(root)): digest(f) for f in files(root)}


def tree(m: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()[:16]


def freeze(name: str, notes: str = "", root: Path = paths.ROOT) -> Path:
    m = manifest(root)
    out = root / "runs" / f"FREEZE_{name}.json"
    out.write_text(json.dumps({"version": name, "frozen_at_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "tree": tree(m), "files": m, "notes": notes}, indent=1))
    tar = root / "runs" / "freeze" / f"{name}.tgz"
    tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar, "w:gz") as tf:
        for f in files(root):
            tf.add(f, arcname=str(f.relative_to(root)))
    return out


def diff(name: str, root: Path = paths.ROOT) -> list[str]:
    frozen = json.loads((root / "runs" / f"FREEZE_{name}.json").read_text())["files"]
    now = manifest(root)
    return sorted(k for k in frozen.keys() | now.keys() if frozen.get(k) != now.get(k))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--notes", default="")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        changed = diff(a.name)
        print("\n".join(changed) or "unchanged")
        sys.exit(1 if changed else 0)
    out = freeze(a.name, a.notes)
    print(f"{out} tree={json.loads(out.read_text())['tree']}")


if __name__ == "__main__":
    main()
