"""Offline replay of recorded trajectories through the vrag gate (precision calibration before any scored run).

For each tool call of a trial (in order) the gate sees the ledger of earlier calls/observations, exactly as at run
time, and its decision is recorded. Denials on trajectories are then reviewed (dev only may be correlated with
rubric outcomes).

    python -m vrag.replay <job glob> --tier kb_seed [--arm A3]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import paths
from .package import build_package


def load_gate(pkg: Path, state: Path, task: str):
    os.environ.update({"VRAG_PKG": str(pkg), "VRAG_STATE": str(state),
                       "VRAG_SEED": str(paths.services(task)), "VRAG_WORKDIR": str(paths.workspace(task))})
    name = f"gate_{abs(hash((str(pkg), str(state))))}"
    spec = importlib.util.spec_from_file_location(name, pkg / "gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def replay_trial(trial: Path, tier: str, arm: str = "A3", msgs: bool = False) -> dict:
    res = json.loads((trial / "result.json").read_text())
    task = (res.get("task_name") or trial.name.split("__")[0]).split("/")[-1]
    traj = json.loads((trial / "agent" / "trajectory.json").read_text())
    pkg = build_package(task, arm, tier, msgs=msgs)
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        g = load_gate(pkg, state, task)
        led = state / "ledger.jsonl"
        denials = []
        n = 0
        for s in traj.get("steps", []):
            for tc in s.get("tool_calls") or []:
                tool, args = tc.get("function_name", ""), tc.get("arguments") or {}
                decision, findings = g.evaluate(tool, args)
                n += 1
                if decision == "deny":
                    denials.append({"tool": tool, "findings": [f.__dict__ for f in findings],
                                    "args": json.dumps(args, ensure_ascii=False)[:600]})
                cid = tc.get("tool_call_id") or f"c{n}"
                with open(led, "a") as fh:
                    fh.write(json.dumps({"type": "action", "call_id": cid, "tool": tool, "args": args}) + "\n")
                    text = " ".join(r.get("content", "") for r in (s.get("observation") or {}).get("results", []))
                    fh.write(json.dumps({"type": "observation", "call_id": cid, "tool": tool, "text": text[:5000]})
                             + "\n")
        stop = g.obligations(g.ledger())
    reward = ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    return {"task": task, "trial": trial.name, "reward": reward, "calls": n, "denials": denials,
            "open_at_end": [f.__dict__ for f in stop]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--tier", default="kb_seed")
    ap.add_argument("--arm", default="A3")
    ap.add_argument("--out", default="")
    ap.add_argument("--msgs", action="store_true", help="include compiled message specs (v7)")
    a = ap.parse_args()
    rows = []
    for pat in a.jobs:
        for job in sorted((paths.ROOT / "runs" / "jobs").glob(pat)):
            for trial in sorted(p for p in job.iterdir() if (p / "agent" / "trajectory.json").exists()):
                try:
                    res = json.loads((trial / "result.json").read_text())
                except Exception:
                    continue
                task = (res.get("task_name") or "").split("/")[-1]
                if not (paths.KB / task / "kb.json").exists():
                    continue
                try:
                    rows.append(replay_trial(trial, a.tier, a.arm, msgs=a.msgs))
                except Exception as e:
                    rows.append({"trial": trial.name, "error": str(e)[:300]})
    c = Counter(f["key"].split(":")[0] for r in rows for d in r.get("denials", []) for f in d["findings"])
    print(f"trials {len(rows)}  calls {sum(r.get('calls', 0) for r in rows)}  denials "
          f"{sum(len(r.get('denials', [])) for r in rows)}  by kind {dict(c)}")
    print(f"open obligations at end: {sum(len(r.get('open_at_end', [])) for r in rows)}")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
