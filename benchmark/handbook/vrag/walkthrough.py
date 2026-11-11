"""Render one harbor trial into a single readable markdown walkthrough (input -> every step -> gate -> grade).

    python -m vrag.walkthrough <trial_dir> [--out file.md] [--max 2500]

Sections: run config and file map; the exact system prompt the agent received (task prompt + vrag addendum, SOP
brief and task checklist rebuilt from the run's policy package); the user instruction; every step (agent text,
tool call with arguments, tool result) with the interwhen gate's decision on that call; stop-hook refusals; the
final answer; the benchmark verifier's rubric results (dev tasks only, unless --allow-test).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import paths
from .package import package_dir

sys.path.insert(0, str(paths.ROOT / "vrag" / "runtime"))


def _cut(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n... [{len(s) - n} more chars]"


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _system_prompt(cfg: dict) -> str:
    import types  # noqa: PLC0415

    sys.modules.setdefault("openhands_runner", types.ModuleType("openhands_runner"))  # container-only import
    import vrag_runner as vr  # noqa: PLC0415

    v = cfg.get("vrag") or {}
    sp = cfg.get("systemPrompt", "")
    if not v:
        return sp
    pkg = package_dir(v["task"], v["arm"], v.get("tier", "kb"), v.get("plan", True), bool(v.get("audit")),
                      bool(v.get("msgs")), v.get("code") or "")
    vr.PKG = str(pkg)
    sp += vr.ADDENDUM
    if v["arm"] in ("A2", "A3"):
        b = vr.brief()
        sp += vr.BRIEF_HEAD + ("\n\n" + b if b else "")
    return sp + f"\n\n(rebuilt from {pkg.relative_to(paths.ROOT)})"


def render(trial: Path, maxc: int, allow_test: bool) -> str:
    res = json.loads((trial / "result.json").read_text())
    task = res["task_name"].split("/")[-1]
    cfg = json.loads((trial / "agent" / "openhands_run_config.json").read_text())
    traj = json.loads((trial / "agent" / "trajectory.json").read_text())
    st = trial / "agent" / ("vrag" if (trial / "agent" / "vrag").exists() else "interwhen")
    dec = _jsonl(st / "decisions.jsonl")
    pre = [d for d in dec if d.get("stage") == "pre"]
    stops = [d for d in dec if d.get("stage") in ("stop", "completion")]
    reward = ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward")

    o = [f"# Trial walkthrough: `{task}`", "",
         f"- trial dir: `{trial.relative_to(paths.ROOT)}`",
         f"- arm: `{(cfg.get('vrag') or {}).get('arm') or ('R' if cfg.get('interwhen') else 'A0')}`  "
         f"config: `{json.dumps(cfg.get('vrag') or cfg.get('interwhen') or {})}`",
         f"- model: `{cfg.get('model')}` (`{json.dumps(cfg.get('llmKwargs'))}`), "
         f"max tool calls {cfg.get('maxToolCalls')}",
         f"- steps: {len(traj['steps'])}, tool calls: {traj.get('n_tool_calls')}, "
         f"stopped: `{traj.get('stopped_reason')}`",
         f"- **reward: {reward}**", "",
         "## Files in this trial",
         "| file | what it is |", "|---|---|",
         "| `agent/openhands_run_config.json` | runner input: instruction, base system prompt, model, arm |",
         "| `agent/run-openhands.log` | raw console log of the OpenHands loop (incl. full rendered system prompt) |",
         "| `agent/trajectory.json` | every step: agent message, tool calls + arguments, tool observations |",
         "| `agent/mcp-proxy.log` | start-up log of the mock services (mail, slack, jira, calendar, files, policy) |",
         f"| `agent/{st.name}/decisions.jsonl` | interwhen gate decision on every tool call and stop attempt |",
         f"| `agent/{st.name}/ledger.jsonl` | (ours) mirror of all actions/observations the gate reasons over |",
         "| `verifier/test-stdout.txt` | the benchmark grader: PASS/FAIL per rubric check |",
         "| `result.json` | harbor's summary (reward, timings, exceptions) |", "",
         "## 1. Input: system prompt the agent received", "", "```text", _system_prompt(cfg), "```", "",
         "## 2. Input: user instruction", "", "```text", cfg.get("instruction", ""), "```", "",
         "## 3. The run, step by step", ""]
    pi, si = 0, 0
    for s in traj["steps"]:
        msg = (s.get("message") or "").strip()
        if s["source"] == "user":
            continue
        is_hook = msg.startswith("[Stop hook feedback]")
        hook_note = " · STOP HOOK (interwhen refuses to let the agent finish)" if is_hook else ""
        o.append(f"### Step {s['step_id']}{hook_note}")
        if s.get("reasoning_content"):
            o += ["*reasoning:*", "```text", _cut(s["reasoning_content"], maxc), "```"]
        if msg:
            o += ["```text", _cut(msg, maxc), "```"]
        if is_hook and si < len(stops):
            si += 1
        calls = s.get("tool_calls") or []
        results = (s.get("observation") or {}).get("results") or []
        for i, tc in enumerate(calls):
            o.append(f"**Tool call:** `{tc['function_name']}`")
            o += ["```json", _cut(json.dumps(tc.get("arguments"), indent=1, ensure_ascii=False), maxc), "```"]
            if pi < len(pre) and pre[pi].get("tool") == tc["function_name"]:
                d = pre[pi]
                pi += 1
                if d["decision"] == "allow":
                    o.append("*interwhen gate (PreToolUse):* allow")
                else:
                    o.append("*interwhen gate (PreToolUse):* **DENY** - " + "; ".join(
                        f.get("problem", "") for f in d.get("findings", [])))
            if i < len(results):
                o += ["**Result:**", "```text", _cut(results[i].get("content") or "", maxc), "```"]
        if not calls and not is_hook and s is not traj["steps"][-1]:
            o.append("*(agent ends its turn here -> the Stop hook runs)*")
        o.append("")
    o += ["## 4. Stop-hook decisions (interwhen completion check)", ""]
    for d in stops:
        o.append(f"- **{d['decision']}**" + (": " + "; ".join(
            f"{f.get('problem', '')} Fix: {f.get('fix', '')}" for f in d.get("findings", [])) if d.get("findings") else
            f" (open={d.get('open')}, denials so far={d.get('denials')})"))
    o += ["", "## 5. Final answer", "", "```text", traj.get("final_output") or "", "```", ""]
    o += ["## 6. Grade (benchmark verifier)", ""]
    if paths.split(task) == "dev" or allow_test:
        o += ["```text", (trial / "verifier" / "test-stdout.txt").read_text().split("[sop-verifier]", 1)[-1].strip()
              if (trial / "verifier" / "test-stdout.txt").exists() else "(none)", "```"]
    else:
        o.append(f"(test task: rubric lines withheld; reward {reward})")
    return "\n".join(o) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trial")
    ap.add_argument("--out", default="")
    ap.add_argument("--max", type=int, default=2500)
    ap.add_argument("--allow-test", action="store_true")
    a = ap.parse_args()
    trial = Path(a.trial).resolve()
    text = render(trial, a.max, a.allow_test)
    out = Path(a.out) if a.out else trial / "WALKTHROUGH.md"
    out.write_text(text)
    print(out)


if __name__ == "__main__":
    main()
