"""Like-for-like results page: every comparison uses the same tasks and the same trial index for all arms.

    python -m vharvey.report_results      # -> docs/RESULTS_PAIRED.md

Sections: train (dev) with trial t0 for every arm; train with t0+t1 where two trials exist; test with t0; test with
t0+t1 when available; within-trial before/after verification; latency and tokens per arm.
"""

from __future__ import annotations

from . import batch, compare, paths, pregate

ARM_NAME = {"base": "A0 plain agent", "V1": "V1 tools from start", "V2": "V2 tools from start + fixes",
            "VC": "VC tools + completeness from start", "VL": "VL verify late",
            "VLC": "VLC verify late + completeness"}


def _label(run: str) -> str:
    return ARM_NAME.get(run.split("-")[0], run)


def _f(x: float | None, pct: bool = True) -> str:
    return "–" if x is None else (f"{100 * x:.1f}" if pct else f"{x:.1f}")


def _d(d: tuple | None) -> str:
    if not d:
        return ""
    sig = " *" if d[1] > 0 or d[2] < 0 else ""
    return f" ({100 * d[0]:+.1f} [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]{sig})"


def table(runs: list[str], trials: int) -> str:
    rows = compare.compare(runs, trials=trials)
    out = [f"Tasks: **{rows[0]['n']}** (the same for every row) · trials per task: **{trials}** "
           f"(trial index t0{'' if trials == 1 else '–t' + str(trials - 1)} for every arm)", "",
           "| approach | criterion pass % | all-pass % | precision criterion % | required-matter recall % |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {_label(r['run'])} | {_f(r['crit'])}{_d(r.get('d_crit'))} | {_f(r['ap'])}{_d(r.get('d_ap'))} "
                   f"| {_f(r['precision'])}{_d(r.get('d_precision'))} | {_f(r['recall'])}{_d(r.get('d_recall'))} |")
    out += ["", "In brackets: difference to A0 in points, paired over tasks, bootstrap 95% CI; * = CI excludes 0.", "",
            "| approach | turns | wall clock (s) | prompt tokens (K, cumulative) | output tokens (K) "
            "| verifier calls |",
            "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {_label(r['run'])} | {r['turns']:.1f} | {r['secs']:.0f} | {r['tokens'] / 1e3:.0f} | "
                   f"{r['out_tokens'] / 1e3:.1f} | {r['fv_calls']:.1f} |")
    return "\n".join(out) + "\n"


def within(runs: list[str]) -> str:
    out = ["| approach, split | matched trials | criterion pass % | all-pass % | precision % | recall % |",
           "|---|---|---|---|---|---|"]
    for run in runs:
        p = pregate.paired(run)
        cells = []
        for k in ("crit", "ap", "precision", "recall"):
            v = p[k]
            sig = " *" if v["ci"][0] > 0 or v["ci"][1] < 0 else ""
            cells.append(f"{100 * v['pre']:.1f} → {100 * v['post']:.1f} ({100 * v['delta']:+.1f} "
                         f"[{100 * v['ci'][0]:+.1f}, {100 * v['ci'][1]:+.1f}]{sig})")
        split = "train" if "dev" in run else "test"
        out.append(f"| {_label(run)}, {split} | {p['trials']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def _have(run: str, trial: str, n: int) -> bool:
    return sum(1 for x in batch.results(run) if x["trial"] == trial) >= n


def build() -> str:
    dev_all = ["base-dev50", "V1-dev50", "V2-dev50", "VC-dev50", "VL-dev50", "VLC-dev50"]
    md = ["# 3 · Results: like-for-like comparisons (Haiku 5.5)", "",
          "Every table compares approaches on **the same tasks with the same trial index**, so the number of trials "
          "is equal across rows. Train = the 50 dev tasks (all design iterations happened here). Test = the first 60 "
          "test tasks in split order, run once per frozen system (FV v2.2; arms VL and VLC).",
          "Judges: claude-sonnet-5 + gpt-5.6-sol. *Criterion pass* = share of rubric criteria passed (mean of the "
          "two judges); *all-pass* = task fully correct (LAB's headline; 0.5 when the judges disagree); *precision "
          "criterion* = the \"no matter outside the reference set\" criterion; *required-matter recall* = share of "
          "\"identifies matter X\" criteria passed.", "",
          "## Train (dev 50), one trial per task (t0) — all approaches", "", table(dev_all, 1)]
    if _have("VLC-dev50", "t1", 45) and _have("base-dev50", "t1", 45):
        md += ["## Train (dev 50), two trials per task (t0 + t1) — A0 vs VLC", "",
               table(["base-dev50", "VLC-dev50"], 2)]
    md += ["## Test (60), one trial per task (t0)", "", table(["base-test60", "VL-test60", "VLC-test60"], 1)]
    if _have("VLC-test60", "t1", 55) and _have("base-test60", "t1", 55):
        md += ["## Test (60), two trials per task (t0 + t1) — A0 vs VLC", "",
               table(["base-test60", "VLC-test60"], 2)]
    else:
        n = sum(1 for x in batch.results("VLC-test60") if x["trial"] == "t1")
        md += [f"_Test with two trials per task: running ({n}/60 second trials of VLC graded so far)._", ""]
    md += ["## Same trajectory, before vs after the verification step", "",
           "VL/VLC behave exactly like A0 until the first `finish`. Grading the answer as it was at that moment "
           "and the final answer of the **same** trajectory isolates what verification changed, with no search "
           "variance. Trials where the answer was written through bash before the gate, or where the agent never "
           "called `finish`, cannot be replayed and are excluded.", "",
           within(["VL-dev50", "VLC-dev50", "VL-test60", "VLC-test60"]),
           "**Why the same-trajectory gain is larger than the run-vs-run gain on test.** The run-vs-run comparison "
           "adds the large search variance of two independent runs (±11 points per 15 tasks), and it includes "
           "trials where the gate never fired or the answer was written through bash (~16% of VLC test trials), "
           "which behave as A0. The same-trajectory comparison removes both, and is the direct estimate of what "
           "the verification step itself changes.", "",
           "## Noise floor", "",
           "Two identical A0 runs on the same 15 dev tasks differed by −11.5 criterion points (CI [−21.8, −2.7]), "
           "with a mean absolute per-task difference of 14.7 points. Single-trial differences under ~10 points are "
           "not reliable; prefer the two-trial and the same-trajectory rows.", ""]
    text = "\n".join(md)
    (paths.ROOT / "docs" / "RESULTS_PAIRED.md").write_text(text)
    return text


if __name__ == "__main__":
    print(build())
