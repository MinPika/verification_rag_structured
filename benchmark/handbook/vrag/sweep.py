"""Run a queue of arm commands with bounded concurrency (one log per command, resumable).

    python -m vrag.sweep runs/sweep_queue.txt --parallel 2

Each non-empty, non-comment line is a shell command run from the project root. Finished lines are appended to
<queue>.done with their exit code; on a re-run, commands that succeeded (exit 0) are skipped and failed or
interrupted ones run again, so an interrupted sweep resumes where it stopped.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import shlex
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from . import paths

_LOCK = threading.Lock()
HEALTH_URL = "http://172.17.0.1:3141/v1/chat/completions"  # the bridge the containers use


def healthy(url: str = HEALTH_URL, timeout: int = 60) -> bool:
    """One tiny completion through the bridge (the VS Code proxy can hang while still accepting connections)."""
    body = json.dumps({"model": "claude-haiku-5.5", "messages": [{"role": "user", "content": "ok"}],
                       "max_tokens": 5}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 - any failure means "not healthy yet"
        return False


def wait_healthy(poll: int = 120) -> None:
    while not healthy():
        print(f"{_stamp()} model proxy not answering; waiting {poll}s", flush=True)
        time.sleep(poll)


def _stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%H:%M:%S")


def run_line(i: int, line: str, logdir: Path, done_file: Path) -> int:
    with _LOCK:
        wait_healthy()
    log = logdir / f"{i:02d}.log"
    print(f"{_stamp()} start {i:02d} {line}", flush=True)
    with open(log, "w") as fh:
        rc = subprocess.run(shlex.split(line), cwd=paths.ROOT, stdout=fh, stderr=subprocess.STDOUT,
                            check=False).returncode
    with _LOCK, open(done_file, "a") as fh:
        fh.write(f"{rc}\t{line}\n")
    print(f"{_stamp()} done  {i:02d} rc={rc}", flush=True)
    return rc


def pending(queue_text: str, done_text: str) -> tuple[list[str], list[tuple[int, str]]]:
    """(all commands, [(1-based index, command) still to run]): commands that exited 0 are done; failed or
    interrupted ones run again."""
    lines = [ln.strip() for ln in queue_text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    ok = {ln.split("\t", 1)[1].strip() for ln in done_text.splitlines() if ln.split("\t", 1)[0] == "0" and "\t" in ln}
    return lines, [(i, ln) for i, ln in enumerate(lines, 1) if ln not in ok]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("queue")
    ap.add_argument("--parallel", type=int, default=2)
    a = ap.parse_args()
    qfile = Path(a.queue)
    done_file = qfile.with_suffix(qfile.suffix + ".done")
    lines, todo = pending(qfile.read_text(), done_file.read_text() if done_file.exists() else "")
    logdir = paths.ROOT / "runs" / "logs" / qfile.stem
    logdir.mkdir(parents=True, exist_ok=True)
    print(f"{_stamp()} {len(todo)} of {len(lines)} commands to run, {a.parallel} at a time", flush=True)
    with cf.ThreadPoolExecutor(a.parallel) as ex:
        for f in cf.as_completed([ex.submit(run_line, i, ln, logdir, done_file) for i, ln in todo]):
            f.result()


if __name__ == "__main__":
    main()
