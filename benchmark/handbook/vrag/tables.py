"""Final results tables: every model x arm on all 65 tasks (headline) and on the 45 test tasks, with paired
task-level bootstrap contrasts.

Dev (20 tasks) was used to develop our layer (A2/A3 compilers, plan wording, gate rules) and to pick A2+R; test was
never inspected at the rubric level. A0 and R involve nothing of ours, so for them all 65 tasks are one clean set.
For our arms the test-only rows are the strictly held-out estimate.

    python -m vrag.tables [--out RESULTS_SWEEP.md]

Arms (job globs; models other than the default carry a '<model>__' job prefix, see run_arm.job_prefix):
  A0      plain agent (OpenHands + MCP tools)
  A2      ours without interwhen: compiled KB tools + SOP brief + task plan
  A2+R    ours with interwhen: A2 + the interwhen verifiers (checklist, PreToolUse and Stop hooks)
  R       the interwhen verifiers on the plain agent
  A0 high plain agent at reasoning_effort=high (the leaderboard's Gemini setting; all other arms use max)
Haiku also reports A3 (our compiled gate), A3+msgs and the retrieval ablation (A1 text vs A1 code retrieval).
Overnight 2026-11-03 (tag x10, Haiku and Opus; FREEZE_v10_pre is the code before these changes):
  A2 noplan        A2 without the drafted plan (KB tools + brief)
  A2 facts(+soft)  the case fact sheet (vrag.facts: facts, SOP pointers, open questions; no decisions) replaces the
                   plan; +soft scopes stop/hold rules to the item they name
  A2 noplan+R / A2 facts+soft+R   the same with the interwhen verifiers (the plan's role left to its checklist)
  A1 code+exec     the exec tool: code retrieval of the interwhen verifier units plus policy__verify_action /
                   policy__verify_completion, which run that code on demand; no monitor (+fin: one completion
                   check at finish)
  A1 text+exec     the exec tool with SOP text retrieval (the SOP text stays the agent's reading material)
  A0 Claude Code   the plain agent in the Claude Code harness instead of OpenHands (vrag.claude_code_agent; Haiku)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import paths, report
from .run_arm import DEFAULT_MODEL, job_prefix
from .stats import paired

MODELS = [DEFAULT_MODEL, "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "claude-opus-5.5", "claude-sonnet-5.5",
          "gemini-4-argon", "gemini-3.8-flash"]
# arm -> (test glob, dev glob); None = not run on that split
SWEEP_ARMS = {"A0": ("A0-test-sweep*", "A0-dev-sweep*"),
              "A2": ("A2-kb_seed-test-sweep*", "A2-kb_seed-dev-sweep*"),
              "A2+R": ("A2-kb_seed-rhooks-test-sweep*", "A2-kb_seed-rhooks-dev-sweep*"),
              "R": ("R-test-sweep*", "R-dev-sweep*"),
              "A0 high": ("A0-ehigh-test-sweep*", None)}
# Haiku's A2 test run is v3 and its dev run v9 (the later compiler); its all-65 row mixes the two versions.
HAIKU_ARMS = {"A0": ("A0-test-2*", "A0-dev-2*"), "A2": ("A2-kb_seed-test-v3*", "A2-kb_seed-dev-v9*"),
              "A2+R": ("A2-kb_seed-rhooks-test-v9*", "A2-kb_seed-rhooks-dev-v9*"), "R": ("R-test-2*", "R-dev-2*"),
              "A3 (our gate)": ("A3-kb_seed-test-v3*", "A3-kb_seed-dev-v3*"),
              "A3+msgs": ("A3-kb_seed-msgs-test-v7*", "A3-kb_seed-msgs-dev-v7*"),
              "A1 text": ("A1-test-v8*", "A1-dev-v8*"), "A1 code": ("A1-vcode-test-v8*", "A1-vcode-dev-v8*"),
              "A1 code+R": (None, "A1-vcode-rhooks-dev-v10*")}
X10_ARMS = {"A2 noplan": ("A2-kb_seed-noplan-test-x10*", "A2-kb_seed-noplan-dev-x10*"),
            "A2 facts": ("A2-kb_seed-facts-test-x10*", "A2-kb_seed-facts-dev-x10*"),
            "A2 facts+soft": ("A2-kb_seed-facts-soft-test-x10*", "A2-kb_seed-facts-soft-dev-x10*"),
            "A2 noplan+R": ("A2-kb_seed-noplan-rhooks-test-x10*", "A2-kb_seed-noplan-rhooks-dev-x10*"),
            "A2 facts+soft+R": ("A2-kb_seed-facts-soft-rhooks-test-x10*", "A2-kb_seed-facts-soft-rhooks-dev-x10*"),
            "A1 text+exec": ("A1-exec-test-x10*", "A1-exec-dev-x10*"),
            "A1 code+exec": ("A1-vcode-exec-test-x10*", "A1-vcode-exec-dev-x10*"),
            "A1 code+exec+fin": ("A1-vcode-exec-fin-test-x10*", "A1-vcode-exec-fin-dev-x10*")}
SWEEP_ARMS.update({"A1 text": ("A1-test-x10*", "A1-dev-x10*"), "A1 code": ("A1-vcode-test-x10*", "A1-vcode-dev-x10*"),
                   **X10_ARMS})
HAIKU_ARMS.update({**X10_ARMS, "A0 Claude Code": ("CC-test-*", "CC-dev-*")})
SCOPES = (("all", "All 65 tasks (test + dev)"), ("test", "Test split only (45 held-out tasks)"))
# Published HANDBOOK.md leaderboard (https://surgehq.ai/benchmarks/handbook, 4 trials/task). The page does not
# name its metric. Up to the 2026-10-14 Wayback snapshot it was strict pass@1 (values equal the paper's strict
# Table 2). By 2026-10-31 the same configurations had risen 1.2-2.5x (e.g. Gemini 3.8 Flash 10.8 -> 26.5): either
# the metric became pass@1 (N-1) or the tasks were revised. See RESULTS.md, "leaderboard metric".
LEADERBOARD = {"claude-opus-5.5": 52.3, "claude-sonnet-5.5": 47.7, "gemini-4-argon": 36.6, "gemini-3.8-flash": 26.5}
LEADERBOARD_STRICT_1014 = {"gemini-3.8-flash": 10.8}
METRICS = (("mean", "mean reward"), ("sp1", "strict pass@1"), ("n1", "pass@1 (N-1)"))
CONTRASTS = [("A2", "A0"), ("A2+R", "A2"), ("A2+R", "A0"), ("R", "A0"), ("A2+R", "R"),
             ("A3 (our gate)", "A2"), ("A1 code", "A1 text"), ("A1 code+R", "R"), ("A0 high", "A0"),
             ("A2 noplan", "A0"), ("A2 noplan", "A2"), ("A2 facts", "A2"), ("A2 facts", "A2 noplan"),
             ("A2 facts+soft", "A2 facts"), ("A2 facts+soft", "A2"), ("A2 noplan+R", "A2+R"), ("A2 noplan+R", "R"),
             ("A2 facts+soft+R", "A2+R"), ("A1 code+exec", "A1 code"), ("A1 code+exec", "R"),
             ("A1 code+exec+fin", "A1 code+exec"), ("A1 code+exec+fin", "R"), ("A1 text+exec", "A1 text"),
             ("A1 text+exec", "A1 code+exec"), ("A1 text+exec", "A0"), ("A0 Claude Code", "A0")]


def _jobs(pattern: str) -> list[Path]:
    return sorted((paths.ROOT / "runs" / "jobs").glob(pattern))


def rubric_rate(jobs: list[Path]) -> float | None:
    p = f = 0
    for job in jobs:
        for out in job.glob("*/verifier/test-stdout.txt"):
            text = out.read_text(errors="replace")
            p += len(re.findall(r"^\s*\[PASS\]", text, re.M))
            f += len(re.findall(r"^\s*\[FAIL\]", text, re.M))
    return 100 * p / (p + f) if p + f else None


def model_arms(model: str, scope: str = "all") -> dict[str, list[Path]]:
    arms = HAIKU_ARMS if model == DEFAULT_MODEL else SWEEP_ARMS
    pre = "" if model == DEFAULT_MODEL else job_prefix(model)
    out = {}
    for name, (test, dev) in arms.items():
        globs = [g for g in ((test, dev) if scope == "all" else (test,)) if g]
        jobs = sorted({j for g in globs for j in _jobs(pre + g)})
        if jobs:
            out[name] = jobs
    return out


def _section(scope: str, title: str) -> list[str]:
    out = [f"## {title}", "",
           "| model | arm | tasks | trials | mean reward | strict pass@1 | pass@1 (N-1) | board 10-31 | "
           "board 10-14 (strict) | rubric checks passed |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    contrast_rows = []
    for model in MODELS:
        per: dict[str, dict[str, dict[str, float]]] = {m: {} for m, _ in METRICS}
        for arm, jobs in model_arms(model, scope).items():
            s = report.summarize(jobs)
            if not s["tasks"]:
                continue
            for m, _ in METRICS:
                per[m][arm] = {t: r[m] for t, r in s["rows"].items()}
            rr = rubric_rate(jobs)
            lb = LEADERBOARD.get(model) if arm == "A0" else None
            lb14 = LEADERBOARD_STRICT_1014.get(model) if arm == "A0" else None
            out.append(f"| {model} | {arm} | {s['tasks']} | {s['trials']} | {s['agg']['mean']:.2f} | "
                       f"{s['agg']['sp1']:.2f} | {s['agg']['n1']:.2f} | {'' if lb is None else f'{lb:.1f}'} | "
                       f"{'' if lb14 is None else f'{lb14:.1f}'} | {'' if rr is None else f'{rr:.1f}%'} |")
        for a, b in CONTRASTS:
            for m, name in METRICS:
                if a in per[m] and b in per[m]:
                    n, d, lo, hi = paired(per[m][a], per[m][b])
                    sig = " *" if lo > 0 or hi < 0 else ""
                    contrast_rows.append(
                        f"| {model} | {a} − {b} | {name} | {n} | {d:+.2f} | [{lo:+.2f}, {hi:+.2f}]{sig} |")
    out += ["", f"### Paired contrasts, {title.lower()} (task-level bootstrap, 95% CI; * = excludes 0)", "",
            "| model | contrast | metric | tasks | diff | 95% CI |", "|---|---|---|---|---|---|", *contrast_rows, ""]
    return out


def tables() -> str:
    out = ["# Results by model (Haiku 4 trials/task, other models 2; Opus 4)", "",
           "Strict pass@1 needs every rubric criterion; pass@1 (N-1) allows one miss. Board columns: the live"
           " leaderboard (2026-10-31, metric not stated) and the last snapshot known to be strict (2026-10-14).",
           "A 'tasks' count below 65 in the first section means that arm's dev run is still pending. Dev was used to"
           " develop our layer, so test-only is the strictly held-out estimate for A2/A2+R/A3.", ""]
    for scope, title in SCOPES:
        out += _section(scope, title)
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="RESULTS_SWEEP.md")
    a = ap.parse_args()
    text = tables()
    (paths.ROOT / a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
