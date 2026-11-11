"""Why did verification change the score? Per-criterion attribution of the DSH late arm (same trajectory, before vs
after the verification gate), plus the judge-noise floor and the tools-from-start ablation.

    python -m vharvey.dsh_analysis D-late-train [--start D-start-train20] [--out docs/DSH_TRAIN_ANALYSIS.md]

For every rubric criterion whose verdict differs between the answer at the gate (``<run>-pregate``) and the final
answer (``<run>``), with "pass" = at least one of the two judges passes:
- answer unchanged (byte-identical response.md) -> **judge noise** (the same text graded twice);
- precision criterion: the matters the judges named as outside the reference set; did the agent call a verifier
  about them (fv_check / completeness contradiction) before removing them (fixed) or did a completeness lead add them
  (broken)?
- required-matter / document criterion: the matter id; was it a completeness lead, was it checked, and what verdict
  did the verifier give before it was added (fixed) or dropped (broken)?
- number / other: whether any verifier was called in that trial.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import batch, failure_log, paths, runner
from .compare import _criteria_pass
from .dsh import VERIFY_LABEL

ID = re.compile(r"\b\d{4}-\d{5}\b")
MODEL = "claude-haiku-5.5"


def _resp(tdir: str) -> str:
    p = Path(tdir) / "output" / "response.md"
    return p.read_text() if p.exists() else ""


def _reasons(tdir: str, cid: str) -> str:
    return " ".join(j.get(cid, {}).get("reasoning", "") for j in failure_log._judges(Path(tdir)).values())


def fv_facts(tdir: str) -> dict:
    """Matter ids the trial's verifier calls were about: checked (with verdicts), leads, contradicted."""
    log = json.loads((Path(tdir) / "vharvey.json").read_text()).get("arm_log") or []
    checked: dict[str, list[str]] = defaultdict(list)
    leads: set[str] = set()
    contradicted: set[str] = set()
    for e in log:
        res, tool = e.get("result"), e.get("tool")
        if tool == "fv_check_complete" and isinstance(res, dict):
            leads |= {m["matter_id"] for m in res.get("missing_from_your_list") or []}
            contradicted |= {m["matter_id"] for m in res.get("listed_but_contradicted") or []}
            continue
        for r in res if isinstance(res, list) else [res]:
            if isinstance(r, dict) and r.get("verdict"):
                args = e.get("args") if isinstance(e.get("args"), dict) else {}
                mid = r.get("matter_id") or args.get("matter_id")
                if mid:
                    checked[mid].append(f"{r.get('field')}={r.get('asked')}→{r['verdict']}")
            elif isinstance(r, dict) and tool == "fv_matter" and r.get("matter_id"):
                checked[r["matter_id"]].append("fv_matter")
    return {"checked": checked, "leads": leads, "contradicted": contradicted, "n_calls": len(log)}


def attribute(run: str, exclude: frozenset[str] = frozenset()) -> dict:
    pre = {x["task"]: x for x in batch.results(f"{run}-pregate") if x["model"] == MODEL and x["task"] not in exclude}
    post = {x["task"]: x for x in batch.results(run) if x["model"] == MODEL and x["task"] not in exclude}
    flips, noise = [], {"criteria": 0, "flips": 0, "trials": 0}
    trials = []
    for t in sorted(set(pre) & set(post)):
        task = json.loads((paths.TASKS / t / "task.json").read_text())
        a, b = _criteria_pass(pre[t]["dir"]), _criteria_pass(post[t]["dir"])
        ra, rb = _resp(pre[t]["dir"]), _resp(post[t]["dir"])
        changed = ra.strip() != rb.strip()
        facts = fv_facts(post[t]["dir"])
        ids_a, ids_b = set(ID.findall(ra)), set(ID.findall(rb))
        trials.append({"task": t, "changed": changed, "n_calls": facts["n_calls"], "crit_pre": pre[t]["crit"],
                       "crit_post": post[t]["crit"], "added": sorted(ids_b - ids_a), "removed": sorted(ids_a - ids_b)})
        if not changed:
            noise["trials"] += 1
            noise["criteria"] += len(task["criteria"])
        for c in task["criteria"]:
            pa, pb = a[c["id"]] >= 0.5, b[c["id"]] >= 0.5
            if pa == pb:
                continue
            kind = failure_log.kind(c)
            fixed = pb
            row = {"task": t, "criterion": c["id"], "kind": kind, "fixed": fixed, "match": c["match_criteria"],
                   "title": task["title"]}
            if not changed:
                noise["flips"] += 1
                row["cause"] = "judge noise (answer unchanged)"
            elif kind == "precision":
                allowed = set(ID.findall(c["match_criteria"]))
                named = {m for m in ID.findall(_reasons(pre[t]["dir"] if fixed else post[t]["dir"], c["id"]))
                         if m not in allowed}
                if fixed:
                    gone = sorted(named & (ids_a - ids_b)) or sorted(named)
                    linked = {m: facts["checked"].get(m, []) + (["contradicted by completeness"]
                                                                 if m in facts["contradicted"] else []) for m in gone}
                    row["matters"] = linked
                    row["cause"] = ("verifier: wrong matter checked, then removed/relabelled" if any(linked.values())
                                    else "rewrite: wrong matter removed without a verifier call on it")
                else:
                    new = sorted(named & (ids_b - ids_a)) or sorted(named)
                    row["matters"] = {m: (["completeness lead"] if m in facts["leads"] else [])
                                      + facts["checked"].get(m, []) for m in new}
                    row["cause"] = ("verifier lead: added a matter outside the reference set"
                                    if any(m in facts["leads"] for m in new)
                                    else "rewrite: wrong matter asserted without a verifier lead")
            elif kind in ("matter", "document") and (m := ID.search(c["match_criteria"])):
                mid = m.group(0)
                ev = (["completeness lead"] if mid in facts["leads"] else []) + facts["checked"].get(mid, [])
                row["matters"] = {mid: ev}
                if fixed:
                    row["cause"] = ("verifier: completeness lead, confirmed and added" if mid in facts["leads"]
                                    else "verifier: checked, then added/cited" if ev
                                    else "rewrite: added/cited without a verifier call on it")
                else:
                    bad = [x for x in ev if not x.endswith("TRUE") and x != "completeness lead"]
                    row["cause"] = (f"verifier: dropped after a non-TRUE verdict ({bad[0]})" if bad
                                    else "rewrite: dropped/uncited despite TRUE verdicts" if ev
                                    else "rewrite: dropped/uncited without a verifier call on it")
            else:
                row["cause"] = "answer changed (verifier called)" if facts["n_calls"] else "answer changed, no call"
            flips.append(row)
    return {"run": run, "flips": flips, "noise": noise, "trials": trials}


def regrade_noise(run: str, workers: int = 8) -> dict:
    """Grade the same pre-gate answers a second time (run ``<run>-pregate-regrade``) and count criteria whose verdict
    flips between the two gradings of identical text: the judge-noise floor. Also returns a sign test of the
    pre->post flips (noise flips either way with equal probability)."""
    import shutil
    from concurrent.futures import ThreadPoolExecutor

    from . import grade as lab_grade
    src_run, dst_run = f"{run}-pregate", f"{run}-pregate-regrade"
    jobs = []
    for x in batch.results(src_run):
        src = Path(x["dir"])
        dst = Path(str(src).replace(f"/{src_run}/", f"/{dst_run}/"))
        if not (dst / "scores_dual.json").exists():
            (dst / "output").mkdir(parents=True, exist_ok=True)
            for f in (src / "output").iterdir():
                shutil.copy2(f, dst / "output" / f.name)
            for f in ("config.json", "metrics.json", "vharvey.json", "transcript.jsonl"):
                shutil.copy2(src / f, dst / f)
        jobs.append((dst, x["task"]))
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda j: lab_grade.grade_trial(*j), jobs))
    a = {x["task"]: x for x in batch.results(src_run)}
    b = {x["task"]: x for x in batch.results(dst_run)}
    n = flips = 0
    for t in sorted(set(a) & set(b)):
        pa, pb = _criteria_pass(a[t]["dir"]), _criteria_pass(b[t]["dir"])
        for cid in pa:
            n += 1
            flips += (pa[cid] >= 0.5) != (pb.get(cid, 0) >= 0.5)
    return {"criteria": n, "flips": flips, "rate": flips / max(n, 1), "trials": len(set(a) & set(b))}


def _sign_test(k: int, n: int) -> float:
    """Two-sided binomial p-value of k 'fixed' out of n flips under p=0.5."""
    from math import comb
    tail = sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _paired(run: str, exclude: frozenset[str] = frozenset()) -> dict:
    from .pregate import paired
    return paired(run, MODEL, exclude)


def search_profile(run: str, before_gate: bool, tasks: set[str] | None = None) -> dict:
    """Mean search calls, first verifier step, distinct matters named in verifier vs search calls (root agent)."""
    rows = [x for x in batch.results(run) if x["model"] == MODEL and (tasks is None or x["task"] in tasks)]
    agg: dict[str, list[float]] = defaultdict(list)
    for x in rows:
        tr = [json.loads(line) for line in open(Path(x["dir"]) / "transcript.jsonl")]
        gate = next((r["turn"] for r in tr if r.get("tool_name") == VERIFY_LABEL), None)
        calls = [(r["turn"], c["name"], c["arguments"] or "") for r in tr if r["role"] == "assistant"
                 for c in r.get("tool_calls") or []]
        if before_gate and gate is not None:
            calls = [c for c in calls if c[0] <= gate]
        search = [c for c in calls if c[1] in ("bash", "grep", "glob", "read")]
        fv = [c for c in calls if c[1].startswith("fv_")]
        agg["search_calls"].append(len(search))
        agg["steps"].append(max([c[0] for c in calls] or [0]))
        agg["fv_calls"].append(len(fv))
        agg["matters_in_search"].append(len({m for c in search for m in ID.findall(c[2])}))
        agg["matters_in_fv"].append(len({m for c in fv for m in ID.findall(c[2])}))
        if fv:
            agg["first_fv_step"].append(fv[0][0])
            agg["search_before_first_fv"].append(sum(1 for c in search if c[0] < fv[0][0]))
    return {k: sum(v) / len(v) for k, v in agg.items() if v} | {"n": len(rows)}


def latency(run: str) -> dict:
    """Mean agent seconds and root steps before the verification gate (plain DSH) and after it (verification)."""
    from datetime import datetime

    from . import dsh
    ts = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()  # noqa: E731
    agg: dict[str, list[float]] = defaultdict(list)
    for td in sorted((dsh.run_dir(run) / "tasks").iterdir()):
        rj, gj = td / "run.json", td / "fv" / "gate.jsonl"
        if not (rj.exists() and gj.exists()):
            continue
        r = json.loads(rj.read_text())
        gate = next((json.loads(line) for line in gj.read_text().splitlines() if '"gate"' in line), None)
        if not gate:
            continue
        start = ts(r["started_at"]) + r.get("setup_s", 0)
        agg["pre_s"].append(ts(gate["t"]) - start)
        agg["post_s"].append(ts(r["finished_at"]) - ts(gate["t"]))
        tr = runner.LABROOT / "results" / run / MODEL / dsh.task_key(r["task_id"]) / "t0" / "transcript.jsonl"
        if tr.exists():
            rows = [json.loads(line) for line in tr.open()]
            cut = next((i for i, x in enumerate(rows) if x.get("tool_name") == VERIFY_LABEL), len(rows))
            agg["pre_steps"].append(sum(1 for x in rows[:cut] if x["role"] == "assistant"))
            agg["post_steps"].append(sum(1 for x in rows[cut:] if x["role"] == "assistant"))
    return {k: sum(v) / len(v) for k, v in agg.items() if v} | {"n": len(agg["pre_s"])}


def to_md(d: dict, p: dict, start: str | None, rn: dict | None = None, label: str = "AHE train split",
          extra: list[tuple[str, dict]] | None = None) -> str:
    fl, nz = d["flips"], d["noise"]
    n_fixed = sum(1 for r in fl if r["fixed"])
    ch = [t for t in d["trials"] if t["changed"]]
    out = [f"# Verification in the DSH harness: what changed and why ({d['run']}, {label}, Haiku 5.5)", "",
           "Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is "
           "asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; "
           "the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); "
           "headline scores average the two judges, and in the per-criterion attribution a criterion counts as "
           "passed when at least one judge passes it.", "",
           "## Headline (same trajectories, before → after verification)", "",
           "| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |", "|---|---|---|---|"]
    for k, name in (("crit", "criterion pass"), ("ap", "all-pass"), ("precision", "precision criterion"),
                    ("recall", "required-matter recall")):
        v = p[k]
        out.append(f"| {name} | {100 * v['pre']:.1f} | {100 * v['post']:.1f} | {100 * v['delta']:+.1f} "
                   f"[{100 * v['ci'][0]:+.1f}, {100 * v['ci'][1]:+.1f}] |")
    for name, q in extra or []:
        out += ["", f"**Same, {name}** ({q['trials']} trials):", "",
                "| metric | before | after | Δ points [95% CI] |", "|---|---|---|---|"]
        for k, mname in (("crit", "criterion pass"), ("ap", "all-pass"), ("precision", "precision criterion"),
                         ("recall", "required-matter recall")):
            v = q[k]
            out.append(f"| {mname} | {100 * v['pre']:.1f} | {100 * v['post']:.1f} | {100 * v['delta']:+.1f} "
                       f"[{100 * v['ci'][0]:+.1f}, {100 * v['ci'][1]:+.1f}] |")
    out += ["", f"Trials: {p['trials']}. Gate fired and the agent called the verifier in "
            f"{sum(1 for t in d['trials'] if t['n_calls'])} trials; the answer changed in {len(ch)}.", "",
            "## Is it noise?", "",
            (f"- **Unchanged answers:** in the {nz['trials']} trials whose answer did not change, {nz['flips']} of "
             f"{nz['criteria']} criteria flipped ({100 * nz['flips'] / max(nz['criteria'], 1):.1f}%), purely from "
             "grading the same text again." if nz["trials"] else
             "- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification "
             "note), so the noise floor is measured by grading identical answers twice (below)."),
            "- **Search noise:** none here. Before and after come from the same trajectory, so the search is "
            "identical.",
            *([f"- **Judge noise, measured:** the same before-answers graded twice flip {rn['flips']} of "
               f"{rn['criteria']} criteria ({100 * rn['rate']:.1f}%). Verification changed {len(fl)} criteria in "
               f"{p['trials']} trials; judge noise alone would flip about {rn['rate'] * rn['criteria']:.0f}, in both "
               "directions."] if rn else []),
            f"- **Direction:** {n_fixed} of the {len(fl)} changed criteria were fixed and {len(fl) - n_fixed} broken. "
            f"Noise flips both ways equally; two-sided sign test p = {_sign_test(n_fixed, len(fl)):.2g}.",
            "", "## Every criterion that changed, by cause", "",
            "| criterion type | change | cause | criteria |", "|---|---|---|---|"]
    cnt = Counter((r["kind"], "fixed" if r["fixed"] else "broken", r["cause"]) for r in fl)
    for (kind, ch_, cause), n in sorted(cnt.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])):
        out.append(f"| {kind} | {ch_} | {cause} | {n} |")
    tot = Counter(("fixed" if r["fixed"] else "broken", r["cause"].split(":")[0]) for r in fl)
    out += ["", "**Summary:** " + ", ".join(f"{v} {k[0]} by {k[1]}" for k, v in sorted(tot.items())), "",
            "## Examples (open the task in the Trials tab, run " + d["run"] + ")", ""]
    seen: set = set()
    for r in sorted(fl, key=lambda r: (r["cause"].startswith("judge"), not r["fixed"], r["kind"])):
        if (r["cause"], r["fixed"]) in seen or r["cause"].startswith("judge"):
            continue
        seen.add((r["cause"], r["fixed"]))
        out += [f"- **{'fixed' if r['fixed'] else 'broken'} · {r['kind']} · task {r['task']} {r['criterion']}** "
                f"— {r['cause']}", f"  - rubric: {r['match'][:260]}",
                f"  - verifier facts: {json.dumps(r.get('matters', {}))[:400]}"]
    lat = latency(d["run"])
    if lat["n"]:
        out += ["", "## Latency (same trajectories)", "",
                "| | before the gate (plain DSH) | verification (after the gate) | added |", "|---|---|---|---|",
                f"| agent seconds | {lat['pre_s']:.0f} | {lat['post_s']:.0f} | "
                f"+{100 * lat['post_s'] / lat['pre_s']:.0f}% |",
                f"| model steps | {lat.get('pre_steps', 0):.1f} | {lat.get('post_steps', 0):.1f} | "
                f"+{100 * lat.get('post_steps', 0) / max(lat.get('pre_steps', 1), 1):.0f}% |",
                "", f"{lat['n']} trials. Agent seconds include tool execution and model latency through the proxy."]
    if start:
        start_tasks = {x["task"] for x in batch.results(start) if x["model"] == MODEL}
        sp, lp = search_profile(start, False), search_profile(d["run"], True, start_tasks)
        out += ["", "## Harness question: are the tools used instead of searching? (tools from the start, 20 train "
                "tasks)", "",
                "| | plain DSH (late arm, before the gate) | tools from the start |", "|---|---|---|"]
        for k, name in (("steps", "steps"), ("search_calls", "search calls (bash/grep/glob/read)"),
                        ("matters_in_search", "distinct matters named in search calls"),
                        ("fv_calls", "verifier calls"), ("first_fv_step", "step of the first verifier call"),
                        ("search_before_first_fv", "search calls before the first verifier call"),
                        ("matters_in_fv", "distinct matters named in verifier calls")):
            out.append(f"| {name} | {lp.get(k, 0):.1f} | {sp.get(k, 0):.1f} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", default=None)
    ap.add_argument("--out", default=str(paths.ROOT / "docs" / "DSH_TRAIN_ANALYSIS.md"))
    ap.add_argument("--regrade", action="store_true", help="measure judge noise by grading pre-gate answers twice")
    ap.add_argument("--label", default="AHE train split", help="split name shown in the report title")
    ap.add_argument("--also-without", default=None, metavar="IDS_FILE",
                    help="also report the headline without these task ids (e.g. splits/dev.txt: tasks seen in design)")
    a = ap.parse_args()
    d = attribute(a.run)
    p = _paired(a.run)
    extra = []
    if a.also_without:
        ex = frozenset(Path(a.also_without).read_text().split())
        extra.append((f"without the {len(ex)} task ids in {Path(a.also_without).name}", _paired(a.run, ex)))
    rn = regrade_noise(a.run) if a.regrade else None
    Path(a.out).write_text(to_md(d, p, a.start, rn, a.label, extra))
    (paths.ROOT / "logs" / f"dsh_attribution_{a.run}.json").write_text(json.dumps(d, indent=1))
    print(a.out, {"flips": len(d["flips"]), "noise": d["noise"]})


if __name__ == "__main__":
    main()
