"""Launch one arm on a task split through harbor (one job, global concurrency -n).

    python -m vrag.run_arm A0 dev  [--attempts 4] [--n 5] [--tasks t1,t2]
Arms: A0 baseline OpenHands; R the frozen interwhen verifiers (their blind-run configuration); A1/A2/A3 ours;
CC the plain agent in the Claude Code harness (vrag.claude_code_agent), called directly at Anthropic with the
credentials in --cred-file (default ~/.anthropic_cc.env: CLAUDE_CODE_OAUTH_TOKEN=... or ANTHROPIC_API_KEY=...).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import time

from . import paths

AGENTS = {
    "A0": ("agent_harness.openhands_agent:OpenHandsAgent", []),
    "R": ("agent_harness.interwhen_agent:InterwhenOpenHandsAgent",
          ["--ak", "checklist=1", "--ak", "max_completion_denials=6", "--ak", "max_stale_denials=2"]),
    "A1": ("vrag.harbor_agent:VragA1", []),
    "A2": ("vrag.harbor_agent:VragA2", []),
    "A3": ("vrag.harbor_agent:VragA3", []),
    "CC": ("vrag.claude_code_agent:HandbookClaudeCode", []),
}
CRED_KEYS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
CRED_RX = re.compile(r"sk-ant-[A-Za-z0-9_-]{40,}")
DEFAULT_MODEL = "claude-haiku-5.5"


def agent_model(model: str) -> str:
    """Model id the agent sends. The OpenHands SDK routes names containing 'gpt-5' to the OpenAI Responses API,
    which the Copilot proxy does not serve; agents use the alias 'gpt_5...' and vrag.bridge maps it back."""
    return model.replace("gpt-5", "gpt_5")


def anthropic_model(model: str) -> str:
    """Anthropic API id of a proxy model id: claude-haiku-5.5 -> claude-haiku-5-5."""
    return re.sub(r"(\d)\.(\d)", r"\1-\2", model)


def read_credentials(path: str) -> dict[str, str]:
    """KEY=VALUE lines of a credentials file, keeping only the Claude Code credential variables (never printed)."""
    out = {}
    for line in open(os.path.expanduser(path), encoding="utf-8"):
        key, sep, value = line.strip().partition("=")
        if sep and key.strip() in CRED_KEYS and value.strip():
            out[key.strip()] = value.strip().strip("'\"")
    if not out:
        sys.exit(f"no {' or '.join(CRED_KEYS)} in {path}")
    bad = [k for k, v in out.items() if not CRED_RX.fullmatch(v)]
    if bad:  # e.g. a placeholder left in the file; the value itself is never printed
        sys.exit(f"{', '.join(bad)} in {path} is not an sk-ant-... token")
    return out


def job_prefix(model: str) -> str:
    """Runs of models other than the default get a '<model>__' job-name prefix, so default-model globs
    ('A0-test*') never pick them up."""
    return "" if model == DEFAULT_MODEL else f"{model}__"


def dataset(name: str, tasks: list[str]) -> str:
    d = paths.ROOT / "runs" / "sets" / name
    d.mkdir(parents=True, exist_ok=True)
    for old in d.iterdir():
        old.unlink()
    for t in tasks:
        (d / t).symlink_to(paths.TASKS / t, target_is_directory=True)
    return str(d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=sorted(AGENTS))
    ap.add_argument("split", help="dev | test | all | custom name (with --tasks)")
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--tier", default="", help="kb | kb_seed (vrag arms)")
    ap.add_argument("--noplan", action="store_true", help="vrag arms: do not show the compiled plan")
    ap.add_argument("--audit", action="store_true", help="vrag arms: apply the offline decision audit (v5)")
    ap.add_argument("--msgs", action="store_true", help="A3: per-message specs in checklist, pre-call and stop (v7)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="proxy model id of the agent")
    ap.add_argument("--effort", default="max", help="reasoning_effort passed to the agent (leaderboard: max or high)")
    ap.add_argument("--rhooks", action="store_true", help="A1/A2: add the interwhen verifiers (R) as the gate")
    ap.add_argument("--checker-first", action="store_true",
                    help="with --rhooks: tell the agent the checker takes precedence over the drafted plan")
    ap.add_argument("--code", default="", choices=("", "sop", "verifiers"),
                    help="vrag arms: SOP retrieval returns code: our compiled procedures (+policy__run) or the "
                         "interwhen baseline's verifier modules")
    ap.add_argument("--facts", action="store_true", help="A2/A3: the case fact sheet (vrag.facts) replaces the plan")
    ap.add_argument("--softstop", action="store_true", help="vrag arms: stop/hold rules scoped to the item they name")
    ap.add_argument("--exec", action="store_true",
                    help="vrag arms: policy__verify_action / policy__verify_completion run the task's verifier code "
                         "on demand (the exec tool; no monitor)")
    ap.add_argument("--finish-check", action="store_true", help="with --exec: one completion check at finish")
    ap.add_argument("--cred-file", default="~/.anthropic_cc.env", help="CC: file with the Claude Code credential")
    a = ap.parse_args()
    if a.finish_check and not a.exec:
        ap.error("--finish-check needs --exec")
    if a.exec and a.rhooks:
        ap.error("--exec replaces the monitor: do not combine with --rhooks")
    tasks = a.tasks.split(",") if a.tasks else [t for t in paths.all_tasks()
                                                 if a.split == "all" or paths.split(t) == a.split]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    variant = "".join(f"-{x}" for x in (a.tier, "noplan" if a.noplan else "", "audit" if a.audit else "",
                                         "msgs" if a.msgs else "",
                                         {"sop": "code", "verifiers": "vcode"}.get(a.code, ""),
                                         "facts" if a.facts else "", "soft" if a.softstop else "",
                                         "exec" if a.exec else "", "fin" if a.finish_check else "",
                                         "rhooks" if a.rhooks else "", "cf" if a.checker_first else "",
                                         f"e{a.effort}" if a.effort != "max" else "") if x)
    job = f"{job_prefix(a.model)}{a.arm}{variant}-{a.split}{'-' + a.tag if a.tag else ''}-{stamp}"
    model = f"openai/{a.model}"  # real id, for the proxy's model check
    ds = dataset(f"{a.split}-{a.arm}-{stamp}", tasks)
    agent, extra = AGENTS[a.arm]
    if a.arm == "CC":
        sys.exit(run_claude_code(a, ds, job, agent))
    for attempt in range(5):  # the proxy's model list is occasionally empty for a moment under load
        check = subprocess.run([str(paths.HANDBOOK / "scripts" / "check_model.sh"), model], cwd=paths.HANDBOOK)
        if check.returncode == 0:
            break
        time.sleep(15 * (attempt + 1))
    else:
        sys.exit("model check failed")
    cmd = [str(paths.HANDBOOK / ".venv" / "bin" / "harbor"), "run", "-p", ds, "--agent-import-path", agent,
           "-m", f"openai/{agent_model(a.model)}", "--ak", f"reasoning_effort={a.effort}", *extra,
           *(["--ak", f"tier={a.tier}"] if a.tier else []),
           *(["--ak", "plan=0"] if a.noplan else []),
           *(["--ak", "audit=1"] if a.audit else []),
           *(["--ak", "msgs=1"] if a.msgs else []),
           *(["--ak", f"code={a.code}"] if a.code else []),
           *(["--ak", "rhooks=1"] if a.rhooks else []),
           *(["--ak", "checker_first=1"] if a.checker_first else []),
           *(["--ak", "facts=1"] if a.facts else []),
           *(["--ak", "softstop=1"] if a.softstop else []),
           *(["--ak", "exec=1"] if a.exec else []),
           *(["--ak", "finish_check=1"] if a.finish_check else []),
           "-k", str(a.attempts), "-n", str(a.n),
           "--job-name", job, "--jobs-dir", str(paths.ROOT / "runs" / "jobs"), "--env-file",
           str(paths.HANDBOOK / ".env")]
    print(" ".join(cmd), flush=True)
    env = {**os.environ, "PYTHONPATH": f"{paths.ROOT}:{os.environ.get('PYTHONPATH', '')}"}
    sys.exit(_harbor(cmd, env, job))


def claude_code_env(base: dict[str, str], creds: dict[str, str]) -> dict[str, str]:
    """Environment for the CC harbor run: the given credentials, and every other Claude credential variable set to
    "" - Harbor calls load_dotenv() on import, which would otherwise pull the benchmark's proxy placeholder
    (ANTHROPIC_API_KEY=unused in handbook/.env) into the run; load_dotenv never overrides a variable that is set."""
    env = {k: v for k, v in base.items() if k not in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", *CRED_KEYS)}
    env.update({k: "" for k in (*CRED_KEYS, "ANTHROPIC_AUTH_TOKEN")})
    env.update(creds)
    env["PYTHONPATH"] = f"{paths.ROOT}:{base.get('PYTHONPATH', '')}"
    return env


def run_claude_code(a, ds: str, job: str, agent: str) -> int:
    """CC arm: Harbor's Claude Code agent against the Anthropic API (no Copilot proxy, no model check)."""
    env = claude_code_env(dict(os.environ), read_credentials(a.cred_file))
    cmd = [str(paths.HANDBOOK / ".venv" / "bin" / "harbor"), "run", "-p", ds, "--agent-import-path", agent,
           "-m", f"anthropic/{anthropic_model(a.model)}", "--ak", f"effort={a.effort}",
           "-k", str(a.attempts), "-n", str(a.n), "--job-name", job, "--jobs-dir", str(paths.ROOT / "runs" / "jobs")]
    print(" ".join(cmd), flush=True)
    return _harbor(cmd, env, job)


def _harbor(cmd: list[str], env: dict[str, str], job: str) -> int:
    rc = subprocess.call(cmd, cwd=paths.HANDBOOK, env=env)
    job_dir = paths.ROOT / "runs" / "jobs" / job
    rc = rc or job_health(job_dir)
    if rc and job_dir.exists():  # never let a failed job's partial trials mix into results
        failed = paths.ROOT / "runs" / "jobs_failed"
        failed.mkdir(exist_ok=True)
        job_dir.rename(failed / job_dir.name)
        print(f"moved {job_dir.name} to runs/jobs_failed", file=sys.stderr, flush=True)
    return rc


def job_health(job_dir, max_unscored: float = 0.2) -> int:
    """Exit status for a finished job: 3 when more than ``max_unscored`` of its trials ended without a reward
    (environment or model-proxy failures), so queue runners re-run it instead of counting it as done."""
    from .report import trials

    rows = list(trials(job_dir)) if job_dir.exists() else []
    unscored = sum(r[1] is None for r in rows)
    if not rows or unscored > max_unscored * len(rows):
        print(f"job unhealthy: {unscored} of {len(rows)} trials have no reward", file=sys.stderr, flush=True)
        return 3
    return 0


if __name__ == "__main__":
    main()
