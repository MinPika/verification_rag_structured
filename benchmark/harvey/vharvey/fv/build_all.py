"""Run the rest of the offline FV build after the document cards: re-ground, vocabulary, matter cards, freeze.

    python -m vharvey.fv.build_all [--wait-pid PID]

Steps are idempotent (cached LLM calls; existing outputs are reused), so the script can be re-run after a failure.
The freeze writes runs/FREEZE_fv_<n>.json: sha256 of vocab, every matter card and the runtime code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

from .. import k0, paths
from .common import FV


def _run(*args: str) -> None:
    print(f"[{datetime.now(UTC):%H:%M:%S}] $ {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, "-m", *args], check=True, cwd=paths.ROOT)


def freeze(tag: str) -> dict:
    files = [FV / "vocab.json", *sorted((FV / "matters").glob("*.json"))]
    code = sorted((paths.ROOT / "vharvey" / "fv").glob("*.py"))
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    man = {"tag": tag, "created": datetime.now(UTC).isoformat(), "n_matters": len(files) - 1,
           "n_doc_cards": sum(1 for _ in (FV / "docs").rglob("*.json")),
           "files": {str(p.relative_to(paths.ROOT)): h(p) for p in files},
           "code": {str(p.relative_to(paths.ROOT)): h(p) for p in code}}
    man["digest"] = hashlib.sha256(json.dumps(man["files"] | man["code"], sort_keys=True).encode()).hexdigest()
    out = paths.RUNS / f"FREEZE_fv_{tag}.json"
    out.write_text(json.dumps(man, indent=1))
    print(f"froze {tag}: {man['n_matters']} matters, digest {man['digest'][:12]} -> {out}", flush=True)
    return man


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-pid", type=int, default=0)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--skip-docs", action="store_true", help="document cards are final; go straight to vocab")
    ap.add_argument("--keep-vocab", action="store_true", help="reuse kb/fv/vocab.json")
    a = ap.parse_args()
    while a.wait_pid and os.path.exists(f"/proc/{a.wait_pid}"):
        time.sleep(30)
    if not a.skip_docs:
        n_files = len(k0.manifest())
        n_cards = sum(1 for _ in (FV / "docs").rglob("*.json"))
        if n_cards < n_files:
            _run("vharvey.fv.docs", "--workers", "96")  # finish stragglers / earlier errors
        _run("vharvey.fv.docs", "--reground", "--workers", "32")
        _run("vharvey.fv.docs", "--extend-long", "--workers", "96")  # after reground (reground resets cards)
    if not a.keep_vocab:
        (FV / "vocab.json").unlink(missing_ok=True)
    if not a.keep_vocab:
        _run("vharvey.fv.vocab")
    for p in (FV / "matters").glob("*.json"):  # re-aggregate; the Opus call is a cache hit if inputs are unchanged
        p.unlink()
    _run("vharvey.fv.matters", "--workers", "16")
    freeze(a.tag)


if __name__ == "__main__":
    main()
