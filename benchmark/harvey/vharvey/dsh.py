"""Run Harvey firm-knowledge in the DSH harness (dsh-bench-harness, branch vrag/harvey-fv) with the Firm Verifier.

    python -m vharvey.dsh specs RUN --split train --arm late [--tasks 003,011] [--model haiku-copilot]
    python -m vharvey.dsh run RUN [--conc 10]
    python -m vharvey.dsh grade RUN [--workers 6]

Arms (the only difference between them is one extra DSH patch file):
  base   plain DSH (the harness as shipped for Harvey)
  late   verify late + completeness check: plain DSH until the agent ends its turn; then the fv_* tools appear and it
         is asked once to verify its answer (benchmarks/harvey/fv-late.yml). The answer at the gate is snapshotted.
  start  fv_* tools and their usage text from the first step (ablation, benchmarks/harvey/fv-start.yml).

Specs come from DSH's own benchmarks/harvey/make_specs.py (AHE split file, task.json sha256 checked), then get the
container runtime and the arm's patch. Runs go to runs/dsh/<RUN>/ (DSH's layout: tasks/<task>/{run.json, workspace,
dsh-home, fv/}). Grading writes a LAB-style view under runs/labroot/results/: <RUN> (final answers) and, for the late
arm, <RUN>-pregate (answers at the gate, i.e. the plain-DSH answer of the same trajectory), so vharvey.compare,
pregate.paired, attribution, cases and the viewer work unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths, runner
from .fv.dsh_assets import build as fv_assets

DSH_REPO = paths.ROOT / "dsh-bench-harness"
SPLIT_FILE = paths.ROOT / "splits" / "ahe-c34-80-20-70.json"
NODE_BIN = Path.home() / ".local/node/node-v24.11.1-linux-x64/bin"
RUNS = paths.RUNS / "dsh"
VERIFY_PREFIX = "Before you finish: verify"  # first words of the gate's verification request (fv/arm.py LATE_MSG)
VERIFY_LABEL = "verification request (fv-gate)"
# late = the reported system (verify late + completeness check). The v4 variant evaluated on validation and not
# adopted is kept, with its arm patch and assets, in runs/freeze_src/v4-dsh (docs/DSH_REPORT.md §6).
ARM_PATCH = {"base": None, "late": "benchmarks/harvey/fv-late.yml", "start": "benchmarks/harvey/fv-start.yml"}


def run_dir(run: str) -> Path:
    return RUNS / run


def task_key(task_id: str) -> str:
    """'firm-knowledge/tasks/003' -> '003'."""
    return task_id.rsplit("/", 1)[-1]


UNUSED = "unused"  # benchmark tasks the AHE split assigns to none of train / validation / test (80 of 250)


def unused_tasks() -> list[str]:
    """Task keys ('012', ...) of firm-knowledge tasks outside every split of SPLIT_FILE."""
    split = json.loads(SPLIT_FILE.read_text())["splits"]
    assigned = {task_key(e["task_id"]) for entries in split.values() for e in entries}
    return sorted(t.name for t in paths.TASKS.iterdir() if (t / "task.json").exists() and t.name not in assigned)


def specs(run: str, split: str, arm: str, model: str = "haiku-copilot", tasks: list[str] | None = None) -> Path:
    if arm not in ARM_PATCH:
        raise SystemExit(f"unknown arm {arm!r}: {sorted(ARM_PATCH)}")
    out = run_dir(run) / "specs"
    if out.exists():
        shutil.rmtree(out)
    source = f"{SPLIT_FILE}:{split}"
    if split == UNUSED:
        run_dir(run).mkdir(parents=True, exist_ok=True)
        ids = run_dir(run) / "unused_task_ids.txt"
        ids.write_text("".join(f"firm-knowledge/tasks/{t}\n" for t in unused_tasks()))
        source = str(ids)
    subprocess.run([sys.executable, "benchmarks/harvey/make_specs.py", "--tasks", source, "--out",
                    str(out), "--model", f"{{repo}}/models/{model}.json"], cwd=DSH_REPO, check=True)
    assets = fv_assets()
    kept = 0
    for f in sorted(out.glob("*.json")):
        spec = json.loads(f.read_text())
        if tasks and task_key(spec["task_id"]) not in tasks:
            f.unlink()
            continue
        spec["runtime"] = "docker"
        if ARM_PATCH[arm]:
            spec["extra_patches"].append(str(DSH_REPO / ARM_PATCH[arm]))
        if arm == "start":
            spec["system_prompt"] += "\n" + assets["start_prompt_complete"]
        spec.setdefault("meta", {})["vrag_arm"] = arm
        f.write_text(json.dumps(spec, indent=2) + "\n")
        kept += 1
    (run_dir(run) / "run_config.json").write_text(json.dumps(
        {"split": split, "arm": arm, "model": model, "n_tasks": kept, "split_file": str(SPLIT_FILE)}, indent=1))
    print(f"{kept} specs in {out}")
    return out


def run(run: str, conc: int) -> None:
    env = os.environ | {"PATH": f"{NODE_BIN}{os.pathsep}{os.environ['PATH']}", "NODE": str(NODE_BIN / "node")}
    subprocess.run(["bash", "dsh_bench/run_specs.sh", str(run_dir(run) / "specs"), str(run_dir(run)), str(conc)],
                   cwd=DSH_REPO, env=env, check=False)


# ---- LAB-style view + grading -------------------------------------------------------------------------------------

def _session_events(home: Path) -> list[dict]:
    """Events of the root session (DSH session.v2.jsonl)."""
    for p in sorted((home / "sessions").rglob("session.v*.jsonl")):
        lines = [json.loads(x) for x in p.read_text().split("\n") if x.strip()]
        if lines and not lines[0].get("parentSession"):
            return lines[1:]
    return []


def _args_text(block: dict) -> str:
    args = block.get("arguments", block.get("input"))
    return args if isinstance(args, str) else json.dumps(args)


def _text_blocks(content) -> str:
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            out.append(b.get("text", ""))
        elif b.get("type") == "tool-result":
            out.append(_text_blocks(b.get("content")))
    return "".join(out)


def lab_transcript(events: list[dict]) -> list[dict]:
    """DSH root-session events -> LAB transcript.jsonl rows (assistant steps with tool calls; tool results; user
    messages the harness injected mid-run, e.g. the verification request, shown as tool name 'user (harness)')."""
    rows: list[dict] = []
    names: dict[str, str] = {}
    first_user = True
    for e in events:
        t, d = e.get("type"), e.get("data") or {}
        if t == "assistant/message":
            msg = d.get("message") or {}
            content = msg.get("content") or []
            calls = [{"id": b.get("id"), "name": b.get("name"), "arguments": _args_text(b)}
                     for b in content if b.get("type") == "tool-call"]
            for c in calls:
                names[c["id"]] = c["name"]
            rows.append({"turn": d.get("step"), "role": "assistant", "text": _text_blocks(content) or None,
                         "tool_calls": calls or None})
        elif t == "tool/result":
            msg = d.get("message") or {}
            cid = (msg.get("source") or {}).get("callId")
            text = _text_blocks(msg.get("content"))
            rows.append({"turn": d.get("step"), "role": "tool", "tool_call_id": cid, "tool_name": names.get(cid, "?"),
                         "result": text, "result_preview": text[:1000]})
        elif t == "user/message":
            if first_user:  # the task prompt itself
                first_user = False
                continue
            text = _text_blocks(d.get("content"))
            if text:
                label = (VERIFY_LABEL if text.startswith(VERIFY_PREFIX) else
                         "runtime context (DSH)" if text.startswith("Current runtime context") else "user (harness)")
                rows.append({"turn": rows[-1]["turn"] if rows else 0, "role": "tool", "tool_call_id": None,
                             "tool_name": label, "result": text, "result_preview": text[:1000]})
    return rows


def lab_view(run: str, task_dir: Path, variant: str) -> Path | None:
    """Make runs/labroot/results/<run>[-pregate]/<model>/<task>/t0 for one DSH task; returns it (None if absent)."""
    rec = json.loads((task_dir / "run.json").read_text())
    key = task_key(rec["task_id"])
    model = rec["model"]["model"]
    src = task_dir / "workspace" / "output" if variant == "post" else task_dir / "fv" / "pregate" / "output"
    if not src.exists():
        return None
    name = run if variant == "post" else f"{run}-pregate"
    dst = runner.LABROOT / "results" / name / model / key / "t0"
    (dst / "output").mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():  # contents only: agents copy read-only corpus files into output/, their mode must not follow
            target = dst / "output" / f.name
            if target.exists():
                target.chmod(0o644)
                target.unlink()
            shutil.copyfile(f, target)
    events = _session_events(task_dir / "dsh-home")
    rows = lab_transcript(events)
    (dst / "transcript.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    calls = task_dir / "fv" / "calls.jsonl"
    arm_log = [json.loads(x) for x in calls.read_text().splitlines()] if calls.exists() else []
    gate = task_dir / "fv" / "gate.jsonl"
    gates = [json.loads(x) for x in gate.read_text().splitlines()] if gate.exists() else []
    arm = rec["spec"].get("meta", {}).get("vrag_arm", "base")
    (dst / "config.json").write_text(json.dumps({"model": model, "arm": f"DSH-{arm}", "harness": "dsh",
                                                 "task": rec["task_id"], "variant": variant}))
    (dst / "metrics.json").write_text(json.dumps({
        "turn_count": rec.get("root_steps"), "wall_clock_seconds": rec.get("agent_s"),
        "input_tokens": 0, "output_tokens": 0, "finish_reason": rec.get("finish_reason"),
        "sessions": rec.get("sessions")}))
    (dst / "vharvey.json").write_text(json.dumps({"status": "ok", "arm": arm, "harness": "dsh",
                                                  "arm_log": [{"tool": c["tool"], "args": c.get("args"),
                                                               "result": c.get("result")} for c in arm_log
                                                              if variant == "post"],
                                                  "gate": gates, "model_calls": []}))
    return dst


def grade(run: str, workers: int) -> None:
    from . import grade as lab_grade
    jobs = []
    for td in sorted((run_dir(run) / "tasks").iterdir()):
        if not (td / "run.json").exists():
            continue
        key = task_key(json.loads((td / "run.json").read_text())["task_id"])
        for variant in ("post", "pre"):
            dst = lab_view(run, td, variant)
            if dst is not None:
                jobs.append((dst, key))

    def one(job: tuple[Path, str]) -> str:
        try:
            g = lab_grade.grade_trial(*job)
            name = job[0].parents[2].name
            return f"{job[1]} {name}: crit {g['dual_criterion_pass']:.2f} ap {g['dual_all_pass_rate']}"
        except Exception as e:  # recorded, never scored as a model failure
            return f"{job[1]} {job[0].parents[2].name}: GRADE ERROR {type(e).__name__}: {str(e)[:200]}"

    with ThreadPoolExecutor(workers) as ex:
        for line in ex.map(one, jobs):
            print(line, flush=True)


def freeze(tag: str, arm: str, model: str = "haiku-copilot", note: str = "") -> dict:
    """Freeze the verifier (index data + code, as vharvey.fv.build_all.freeze) plus the DSH files of ``arm``: the
    plugin, the arm's patch, the assets it points to, the model config and the SSE facade."""
    import hashlib
    import re

    from .fv.build_all import freeze as freeze_fv
    man = freeze_fv(tag)
    patch = DSH_REPO / ARM_PATCH[arm]
    assets = re.search(r"assets:\s*__BENCH_REPO__/(\S+)", patch.read_text())
    files = [DSH_REPO / "benchmarks/harvey/plugins/fv-gate.mjs", patch, DSH_REPO / "models" / f"{model}.json",
             paths.ROOT / "vharvey" / "sse_facade.py", *([DSH_REPO / assets.group(1)] if assets else [])]
    man["dsh_files"] = {str(p.relative_to(paths.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    man["digest"] = hashlib.sha256(json.dumps(man["files"] | man["code"] | man["dsh_files"],
                                              sort_keys=True).encode()).hexdigest()
    man["arm"] = arm
    if note:
        man["note"] = note
    out = paths.RUNS / f"FREEZE_fv_{tag}.json"
    out.write_text(json.dumps(man, indent=1))
    print(f"froze {tag} (arm {arm}): digest {man['digest'][:12]} -> {out}")
    return man


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("specs")
    s.add_argument("run")
    s.add_argument("--split", required=True, choices=["train", "validation", "test", UNUSED])
    s.add_argument("--arm", required=True, choices=sorted(ARM_PATCH))
    s.add_argument("--model", default="haiku-copilot")
    s.add_argument("--tasks", default="")
    r = sub.add_parser("run")
    r.add_argument("run")
    r.add_argument("--conc", type=int, default=10)
    g = sub.add_parser("grade")
    g.add_argument("run")
    g.add_argument("--workers", type=int, default=6)
    f = sub.add_parser("freeze", help="freeze index + verifier code + the arm's DSH files before a test run")
    f.add_argument("tag")
    f.add_argument("--arm", required=True, choices=sorted(k for k, v in ARM_PATCH.items() if v))
    f.add_argument("--model", default="haiku-copilot")
    f.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "freeze":
        freeze(a.tag, a.arm, a.model, a.note)
    elif a.cmd == "specs":
        specs(a.run, a.split, a.arm, a.model, [t for t in a.tasks.split(",") if t] or None)
    elif a.cmd == "run":
        run(a.run, a.conc)
    else:
        grade(a.run, a.workers)


if __name__ == "__main__":
    main()
