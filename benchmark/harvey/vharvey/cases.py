"""Case studies for review: rubrics that verification flipped inside the same trajectory (train/dev split).

    python -m vharvey.cases VLC-dev50 [--out docs/CASES.md]

For every trial of the arm with a graded pre-gate answer (``<run>-pregate``), compare each criterion before vs after
the verification gate. A case = one criterion that flipped: what the rubric asks, what the agent had before, which
FV calls it made about that matter (verdict + evidence quote), what it changed, and both judges' reasoning. Also
lists the A0 failures that verification did not touch, grouped by criterion type, as remaining opportunities.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import batch, failure_log, paths
from .compare import _criteria_pass

MAX_CASES = {"precision_fixed": 6, "matter_added": 6, "regression": 5}


def _judges(tdir: str) -> dict[str, dict]:
    out = {}
    for j in ("claude-sonnet-5", "gpt-5.6-sol"):
        s = json.loads((Path(tdir) / f"scores_{j}.json").read_text())
        for r in s["criteria_results"]:
            out.setdefault(r.get("criterion_id") or r.get("id"), {})[j] = r.get("reasoning", "")
    return out


def _fv_calls(tdir: str) -> list[dict]:
    rows = []
    for e in json.loads((Path(tdir) / "vharvey.json").read_text()).get("arm_log") or []:
        res = e.get("result")
        for r in res if isinstance(res, list) else [res]:
            if isinstance(r, dict) and (r.get("verdict") or e["tool"] == "fv_check_complete"):
                rows.append({"tool": e["tool"], **r})
    return rows


def _lines(text: str, mid: str, n: int = 3) -> list[str]:
    return [ln.strip()[:300] for ln in text.splitlines() if mid in ln][:n]


def _ev(r: dict) -> str:
    ev = (r.get("evidence") or [{}])[0] or {}
    return f' — `{ev.get("path", "")}`: “{(ev.get("quote") or "")[:200]}”' if ev.get("path") else ""


def collect(run: str, model: str = "claude-haiku-5.5") -> dict:
    pre = {(x["task"], x["trial"]): x for x in batch.results(f"{run}-pregate") if x["model"] == model}
    post = {(x["task"], x["trial"]): x for x in batch.results(run) if x["model"] == model}
    cases: dict[str, list[dict]] = defaultdict(list)
    flips: Counter = Counter()
    for key in sorted(set(pre) & set(post)):
        task, trial = key
        t = json.loads((paths.TASKS / task / "task.json").read_text())
        a, b = _criteria_pass(pre[key]["dir"]), _criteria_pass(post[key]["dir"])
        ja, jb = _judges(pre[key]["dir"]), _judges(post[key]["dir"])
        calls = _fv_calls(post[key]["dir"])
        resp_pre = (Path(pre[key]["dir"]) / "output" / "response.md").read_text()
        resp_post_p = Path(post[key]["dir"]) / "output" / "response.md"
        resp_post = resp_post_p.read_text() if resp_post_p.exists() else ""
        for c in t["criteria"]:
            if (a[c["id"]] >= 0.5) == (b[c["id"]] >= 0.5):
                continue
            kind = failure_log.kind(c)
            fixed = b[c["id"]] >= 0.5
            m = re.search(r"\d{4}-\d{5}", c["match_criteria"])
            mid = m.group(0) if m and kind != "precision" else None
            if kind == "precision":
                rel = [r for r in calls if r.get("verdict") in ("FALSE", "NOT_FOUND", "SECONDARY")]
                removed = sorted({x for x in re.findall(r"\d{4}-\d{5}", resp_pre)} -
                                 {x for x in re.findall(r"\d{4}-\d{5}", resp_post)})
            else:
                rel = [r for r in calls if r.get("matter_id") == mid
                       or any(x.get("matter_id") == mid for x in r.get("missing_from_your_list") or [])]
                removed = []
            group = ("precision_fixed" if kind == "precision" else "matter_added") if fixed else "regression"
            flips[(kind, "fixed" if fixed else "broken")] += 1
            cases[group].append({
                "task": task, "trial": trial, "title": t["title"], "instruction": t["instructions"].split("Output:")[0],
                "criterion": c, "kind": kind, "matter": mid, "calls": rel[:8], "removed": removed[:12],
                "pre_lines": _lines(resp_pre, mid) if mid else [], "post_lines": _lines(resp_post, mid) if mid else [],
                "judge_pre": ja.get(c["id"], {}), "judge_post": jb.get(c["id"], {}),
                "page": f"{run}/{model}/{failure_log.page_name({'task': task, 'trial': trial})}"})
    return {"cases": cases, "flips": flips, "n_trials": len(set(pre) & set(post))}


TOOL_FOR_KIND = {
    "matter": "enumeration: `fv_find(conditions)` / completeness against the index; the agent never found the matter",
    "document": "evidence: per-matter proof-document lookup (`fv_doc`, evidence paths returned with every verdict)",
    "precision": "`fv_check` on the condition the wrong matter fails (outcome, term, role, practice area, stage)",
    "number": "aggregate: count/sum over the index (SQL over matter cards) with the list it counted",
    "other": "case by case (people/staffing, dates, classifications): matter-card fields + `fv_check`",
}


def remaining(base: str, arm: str, model: str = "claude-haiku-5.5") -> tuple[Counter, dict[str, list[dict]]]:
    """A0 failures (first trial) by criterion type and whether the arm fixed them; examples of the still-failing."""
    a = {x["task"]: x for x in batch.results(base) if x["model"] == model and x["trial"] == "t0"}
    v = {x["task"]: x for x in batch.results(arm) if x["model"] == model and x["trial"] == "t0"}
    out: Counter = Counter()
    ex: dict[str, list[dict]] = defaultdict(list)
    for t in sorted(set(a) & set(v)):
        task = json.loads((paths.TASKS / t / "task.json").read_text())
        pa, pv = _criteria_pass(a[t]["dir"]), _criteria_pass(v[t]["dir"])
        ja = _judges(a[t]["dir"])
        for c in task["criteria"]:
            if pa[c["id"]] < 0.5:
                k = failure_log.kind(c)
                still = pv[c["id"]] < 0.5
                out[(k, "still failing" if still else "fixed")] += 1
                if still and all(e["task"] != t for e in ex[k]):
                    ex[k].append({"task": t, "title": task["title"], "criterion": c,
                                  "reason": (ja.get(c["id"], {}).get("claude-sonnet-5") or "")[:300],
                                  "page": f"{base}/{model}/{t}"})
    return out, ex


def _call_line(r: dict) -> str:
    if r.get("tool") == "fv_check_complete":
        miss = ", ".join(m["matter_id"] for m in (r.get("missing_from_your_list") or [])[:8])
        return (f"- `fv_check_complete({json.dumps(r.get('conditions'))[:160]})` → **{r.get('verdict')}**, "
                f"{r.get('n_index_matches')} index matches; missing from the agent's list: {miss}")
    return (f"- `fv_check({r.get('matter_id')}, {r.get('field')}, {r.get('asked')})` → **{r.get('verdict')}** "
            f"(actual: {json.dumps(r.get('actual'))[:90]}){_ev(r)}")


def to_md(run: str, base: str, data: dict, rem: Counter, rem_ex: dict[str, list[dict]]) -> str:
    fl = data["flips"]
    out = [f"# Verification opportunities and effects — train/dev split ({run}, Haiku 5.5)", "",
           "How to read this page: each case is **one rubric criterion that changed inside the same trajectory** "
           "when the agent was made to verify its answer (VLC: tools appear at the first `finish`). Before = the "
           "answer the agent had written at that moment; after = its final answer. Both are graded by the same two "
           "judges, so the change is caused by the verification step, not by a different search. A criterion counts as "
           "passing when at least one of the two judges passes it.", "",
           f"**{data['n_trials']} trials.** Criteria flipped by verification:", "",
           "| criterion type | fixed | broken |", "|---|---|---|"]
    for k in sorted({k for k, _ in fl}):
        out.append(f"| {k} | {fl[(k, 'fixed')]} | {fl[(k, 'broken')]} |")
    out += ["", f"**Remaining opportunities** (criteria A0 failed on dev, first trial; status in {run}):", "",
            "| criterion type | A0 failures fixed by the arm | still failing |", "|---|---|---|"]
    for k in sorted({k for k, _ in rem}):
        out.append(f"| {k} | {rem[(k, 'fixed')]} | {rem[(k, 'still failing')]} |")
    titles = {"precision_fixed": "A. Precision: the verifier stopped a wrong inclusion",
              "matter_added": "B. Recall and evidence: a missed matter or proof document was added after verifying",
              "regression": "C. Regressions: verification made a criterion fail (honest failure cases)"}
    for g, title in titles.items():
        cs = data["cases"].get(g, [])
        seen: set = set()
        picked = [c for c in cs if not (c["task"] in seen or seen.add(c["task"]))][:MAX_CASES[g]]
        out += ["", f"## {title} — {len(cs)} criteria, {len(picked)} shown", ""]
        for i, c in enumerate(picked, 1):
            cr = c["criterion"]
            out += [f"### {g[0].upper()}{i}. Task {c['task']} ({c['trial']}): {c['title']}", "",
                    f"> {c['instruction'].strip()}", "",
                    f"**Rubric {cr['id']}** [{c['kind']}]: {cr['match_criteria']}", ""]
            if c["removed"]:
                out.append(f"**Matters the agent removed after verifying:** {', '.join(c['removed'])}")
            if c["pre_lines"] or c["post_lines"]:
                out += ["**Answer before:** " + (" / ".join(c["pre_lines"]) or "_matter not mentioned_"),
                        "", "**Answer after:** " + (" / ".join(c["post_lines"]) or "_matter not mentioned_")]
            out += ["", "**Verifier calls the agent made:**"] + ([_call_line(r) for r in c["calls"]] or
                                                                 ["- _none about this matter_"])
            for j in ("claude-sonnet-5", "gpt-5.6-sol"):
                out.append(f"- judge {j} before: {c['judge_pre'].get(j, '')[:260]}")
                out.append(f"- judge {j} after: {c['judge_post'].get(j, '')[:260]}")
            out += ["", f"_Trial in dashboard: {c['page']}_", ""]
    out += ["", "## D. Remaining opportunities: A0 failures verification does not fix yet (3 examples per type)", ""]
    for k, tool in TOOL_FOR_KIND.items():
        if not rem_ex.get(k):
            continue
        out += [f"**{k}** — {rem[(k, 'still failing')]} still failing. Tool that would target it: {tool}", ""]
        for e in rem_ex[k][:3]:
            cr = e["criterion"]
            out.append(f"- Task {e['task']} ({e['title']}), {cr['id']}: {cr['match_criteria'][:220]}"
                       f" — judge: {e['reason'][:220]} _(trial: {e['page']})_")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--base", default="base-dev50")
    ap.add_argument("--out", default=str(paths.ROOT / "docs" / "CASES.md"))
    a = ap.parse_args()
    data = collect(a.run)
    md = to_md(a.run, a.base, data, *remaining(a.base, a.run))
    Path(a.out).write_text(md)
    print(a.out, {k: len(v) for k, v in data["cases"].items()}, dict(data["flips"]))


if __name__ == "__main__":
    main()
