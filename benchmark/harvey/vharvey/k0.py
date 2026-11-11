"""K0: the corpus as the agent sees it. Every DMS file is converted with LAB's own ``parse-doc`` inside the LAB
sandbox image (docx: pandoc markdown with changes accepted; xlsx: pandas; pptx: markitdown); .eml files are read raw,
exactly like LAB's ``read`` tool. KB text is therefore byte-identical to what ``read`` returns, so every quote the KB
stores can be found by the agent and checked by the verifiers.

    python -m vharvey.k0            # -> kb/k0/text/<matter>/<relpath>.txt + kb/k0/manifest.jsonl

The manifest has one row per file: path (matter/relpath, the unique key; bare filenames repeat across matters),
matter, client number, ext, chars, sha256, parse status. Parse failures are recorded, never dropped.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from functools import cache
from pathlib import Path

from . import paths

K0 = paths.KB / "k0"
TEXT = K0 / "text"
MANIFEST = K0 / "manifest.jsonl"
STATUS = K0 / "parse_status.jsonl"
IMAGE = "lab-sandbox:latest"
PARSED_EXT = {".docx", ".xlsx", ".pptx", ".pdf"}

# Runs inside the sandbox image: parse every listed file with LAB's parse-doc functions, in parallel.
_INNER = r"""
import importlib.machinery, importlib.util, json, sys, traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
loader = importlib.machinery.SourceFileLoader("parse_doc", "/usr/local/bin/parse-doc")
spec = importlib.util.spec_from_loader("parse_doc", loader)
pd_mod = importlib.util.module_from_spec(spec); loader.exec_module(pd_mod)
SRC, DST = Path("/dms"), Path("/out")
def one(rel):
    src, dst = SRC / rel, DST / (rel + ".txt")
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = pd_mod.PARSERS[src.suffix.lower()[1:]](str(src))
        dst.write_text(text, encoding="utf-8")
        return rel, "ok", ""
    except Exception as e:
        return rel, "error", f"{type(e).__name__}: {e}"[:500]
rels = [l.strip() for l in sys.stdin if l.strip()]
with ProcessPoolExecutor(max_workers=int(sys.argv[1])) as ex:
    for rel, status, err in ex.map(one, rels, chunksize=8):
        print(json.dumps({"rel": rel, "status": status, "error": err}), flush=True)
"""


def matter_of(rel: str) -> str:
    return rel.split("/")[1]  # rel = matters/<CCCC-MMMMM>/...


def build(workers: int = 16) -> None:
    files = sorted(p for p in paths.DMS.rglob("*") if p.is_file())
    rels = [str(p.relative_to(paths.DMS)) for p in files]
    TEXT.mkdir(parents=True, exist_ok=True)
    to_parse = [r for r in rels if Path(r).suffix.lower() in PARSED_EXT]
    status: dict[str, tuple[str, str]] = {}
    if STATUS.exists():  # resume: keep files a previous (interrupted) build finished
        for line in STATUS.open():
            d = json.loads(line)
            if d["status"] == "ok" and (TEXT / (d["rel"] + ".txt")).exists():
                status[d["rel"]] = ("ok", "")
    todo = [r for r in to_parse if r not in status]
    cmd = ["docker", "run", "--rm", "-i", "--user", f"{_uid()}", "--network=none",
           "-v", f"{paths.DMS}:/dms:ro", "-v", f"{TEXT}:/out:rw", IMAGE, "python3", "-c", _INNER, str(workers)]
    with STATUS.open("a") as log, subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, text=True) as proc:
        assert proc.stdin and proc.stdout and proc.stderr
        proc.stdin.write("\n".join(todo))
        proc.stdin.close()
        for line in proc.stdout:  # each parsed file is logged as it finishes, so an interrupt loses nothing
            if line.startswith("{"):
                d = json.loads(line)
                status[d["rel"]] = (d["status"], d["error"])
                log.write(line)
                log.flush()
        stderr = proc.stderr.read()
    missing = [r for r in to_parse if r not in status]
    if proc.returncode != 0 or missing:
        raise RuntimeError(f"parse run failed (rc={proc.returncode}, {len(missing)} files unreported): "
                           f"{stderr[-1500:]}")
    for r in rels:  # plain-text files: LAB `read` decodes utf-8 with replacement
        if Path(r).suffix.lower() not in PARSED_EXT:
            dst = TEXT / (r + ".txt")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text((paths.DMS / r).read_bytes().decode("utf-8", errors="replace"), encoding="utf-8")
            status[r] = ("ok", "")
    with MANIFEST.open("w") as f:
        for r in rels:
            st, err = status[r]
            tp = TEXT / (r + ".txt")
            text = tp.read_text(encoding="utf-8") if tp.exists() else ""
            m = matter_of(r)
            f.write(json.dumps({"path": r.removeprefix("matters/"), "matter": m, "client": m.split("-")[0],
                                "ext": Path(r).suffix.lower()[1:], "chars": len(text),
                                "sha256": hashlib.sha256(text.encode()).hexdigest(), "status": st,
                                "error": err}) + "\n")
    bad = sum(1 for v in status.values() if v[0] != "ok")
    print(f"K0: {len(rels)} files, {bad} parse errors -> {MANIFEST}")


def _uid() -> str:
    import os
    return f"{os.getuid()}:{os.getgid()}"


def manifest() -> list[dict]:
    return [json.loads(line) for line in MANIFEST.open()]


@cache
def manifest_index() -> dict[str, list[dict]]:
    """matter id -> its manifest rows."""
    idx: dict[str, list[dict]] = {}
    for r in manifest():
        idx.setdefault(r["matter"], []).append(r)
    return idx


def text(path: str) -> str:
    """K0 text of a file by its key ``<matter>/<relpath>``."""
    return (TEXT / "matters" / (path + ".txt")).read_text(encoding="utf-8")


if __name__ == "__main__":
    build(int(sys.argv[1]) if len(sys.argv) > 1 else 16)
