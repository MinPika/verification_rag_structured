"""Sweep monitor: status snapshot, stale-network cleanup, and a watch mode that exits on the first event.

    python -m vrag.monitor                       # one status snapshot
    python -m vrag.monitor --watch --interval 300 --max-hours 2
    python -m vrag.monitor --keep                # unattended supervisor (run detached)
    python -m vrag.monitor --keep --queue runs/x10_queue.txt   # another queue (log runs/logs/x10_queue.out)

Watch mode polls and exits (printing the reason and a snapshot) when a sweep command finishes, the sweep process
is gone, the model proxy fails two health checks in a row, or --max-hours passes (heartbeat). Each poll also
removes this project's trial networks (names containing '__') that have no containers and are older than
--stale-min minutes: killed trials leave them behind, and Docker's default address pools hold only ~31.

Keep mode supervises an unattended sweep. Every --interval seconds it cleans stale networks, restarts the bridge if
nothing listens on its port, and restarts the sweep if it is not running while commands are pending. The restart
also retries commands that failed: the sweep only re-runs failures on a fresh start. It allows at most
--max-restarts sweep starts and exits once every command has succeeded. It logs to runs/logs/keeper.log.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
import subprocess
import time
from pathlib import Path

from . import paths
from .bridge import LISTEN_HOST, LISTEN_PORT
from .sweep import healthy, pending

QUEUE = paths.ROOT / "runs" / "sweep_queue.txt"
OUT = paths.ROOT / "runs" / "logs" / "sweep_queue.out"
JOBS = paths.ROOT / "runs" / "jobs"
PYTHON = str(paths.ROOT / ".venv" / "bin" / "python")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False).stdout


def sweep_alive() -> bool:
    for p in Path("/proc").iterdir():
        if p.name.isdigit():
            try:
                cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if "-m vrag.sweep" in cmd and "/bin/bash" not in cmd and "sh -c" not in cmd:
                return True
    return False


def bridge_listening(host: str = LISTEN_HOST, port: int = LISTEN_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


def _spawn(args: list[str], log: Path) -> None:
    """Start a process in its own session so it outlives this supervisor."""
    with open(log, "a") as fh:
        subprocess.Popen(args, cwd=paths.ROOT, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True)


def _todo() -> list[tuple[int, str]]:
    done_file = QUEUE.with_suffix(QUEUE.suffix + ".done")
    return pending(QUEUE.read_text(), done_file.read_text() if done_file.exists() else "")[1]


def keep(interval: int, max_restarts: int, stale_min: int) -> None:
    log = paths.ROOT / "runs" / "logs" / "keeper.log"

    def note(msg: str) -> None:
        with open(log, "a") as fh:
            fh.write(f"{_now():%m-%d %H:%M:%S} {msg}\n")

    state = {"restarts": 0, "last_beat": 0.0}
    note(f"keeper start (interval {interval}s, max restarts {max_restarts})")
    while True:
        try:
            if not _keep_poll(state, note, max_restarts, stale_min):
                return
        except Exception as e:  # noqa: BLE001 - one bad poll must not end an unattended supervisor
            note(f"poll failed: {type(e).__name__}: {e}")
        time.sleep(interval)


def _keep_poll(state: dict, note, max_restarts: int, stale_min: int) -> bool:
    """One supervisor pass; False when the keeper should exit."""
    removed = clean_stale_networks(stale_min)
    if removed:
        note(f"removed {len(removed)} stale networks")
    if not bridge_listening():
        note("bridge not listening; restarting it")
        _spawn([PYTHON, "-m", "vrag.bridge"], paths.ROOT / "runs" / "logs" / "bridge.log")
    todo = _todo()
    if not sweep_alive():
        if not todo:
            note("all sweep commands succeeded; keeper exits")
            return False
        if state["restarts"] >= max_restarts:
            note(f"sweep stopped with {len(todo)} commands pending and {state['restarts']} restarts used; "
                 "keeper exits")
            return False
        state["restarts"] += 1
        note(f"sweep not running with {len(todo)} pending; start {state['restarts']}/{max_restarts}")
        _spawn([PYTHON, "-m", "vrag.sweep", str(QUEUE), "--parallel", "2"], OUT)
    if time.time() - state["last_beat"] > 3600:
        state["last_beat"] = time.time()
        note(f"heartbeat: {len(todo)} pending, proxy {'ok' if healthy() else 'NOT answering'}")
    return True


def clean_stale_networks(stale_min: int) -> list[str]:
    removed = []
    cutoff = _now() - dt.timedelta(minutes=stale_min)
    for name in _docker("network", "ls", "--format", "{{.Name}}").split():
        if "__" not in name:
            continue
        info = _docker("network", "inspect", "-f", "{{len .Containers}} {{.Created}}", name).split()
        if len(info) < 3 or info[0] != "0":
            continue
        created = dt.datetime.fromisoformat(f"{info[1]}T{info[2][:15]}+00:00")
        if created < cutoff:
            _docker("network", "rm", name)
            removed.append(name)
    return removed


def running_jobs() -> list[tuple[str, int, int]]:
    """(job name, scored trials, total trials) for jobs that have started but not finished."""
    rows = []
    for res in sorted(JOBS.glob("*/result.json")):
        try:
            d = json.loads(res.read_text())
        except (OSError, json.JSONDecodeError):  # harbor is rewriting it right now
            continue
        if d.get("finished_at"):
            continue
        done = sum(1 for t in res.parent.glob("*/result.json"))
        rows.append((res.parent.name, done, int(d.get("n_total_trials") or 0)))
    return rows


def done_lines() -> int:
    return sum(1 for ln in OUT.read_text().splitlines() if " done " in ln) if OUT.exists() else 0


def snapshot(stale_min: int = 15) -> str:
    done_file = QUEUE.with_suffix(QUEUE.suffix + ".done")
    lines, todo = pending(QUEUE.read_text(), done_file.read_text() if done_file.exists() else "")
    removed = clean_stale_networks(stale_min)
    nets = len(_docker("network", "ls", "-q").split())
    out = [f"{_now():%H:%M} UTC  sweep {'alive' if sweep_alive() else 'NOT RUNNING'}; "
           f"{len(lines) - len(todo)}/{len(lines)} commands ok; containers {len(_docker('ps', '-q').split())}; "
           f"networks {nets}" + (f" (removed {len(removed)} stale)" if removed else "")]
    out += [f"  running {name}: {k}/{n} trials" for name, k, n in running_jobs()]
    tail = OUT.read_text().splitlines()[-3:] if OUT.exists() else []
    out += [f"  log: {ln[:150]}" for ln in tail]
    return "\n".join(out)


def watch(interval: int, max_hours: float, stale_min: int) -> str:
    start, base_done, bad = time.time(), done_lines(), 0
    while True:
        snap = snapshot(stale_min)
        if done_lines() > base_done:
            return "EVENT command finished\n" + snap
        if not sweep_alive():
            return "EVENT sweep not running\n" + snap
        bad = 0 if healthy() else bad + 1
        if bad >= 2:
            return "EVENT model proxy unhealthy (2 checks)\n" + snap
        if time.time() - start > max_hours * 3600:
            return "HEARTBEAT\n" + snap
        time.sleep(interval)


def use_queue(queue: Path) -> None:
    """Point the monitor at another sweep queue; its sweep output goes to runs/logs/<queue stem>.out."""
    global QUEUE, OUT
    QUEUE = queue.resolve()
    OUT = paths.ROOT / "runs" / "logs" / f"{queue.stem}.out"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue", type=Path, default=QUEUE, help="sweep queue file (default runs/sweep_queue.txt)")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--keep", action="store_true", help="unattended supervisor (see module docstring)")
    ap.add_argument("--max-restarts", type=int, default=4)
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--max-hours", type=float, default=2.0)
    ap.add_argument("--stale-min", type=int, default=15)
    a = ap.parse_args()
    use_queue(a.queue)
    if a.keep:
        keep(a.interval, a.max_restarts, a.stale_min)
        return
    print(watch(a.interval, a.max_hours, a.stale_min) if a.watch else snapshot(a.stale_min), flush=True)


if __name__ == "__main__":
    main()
