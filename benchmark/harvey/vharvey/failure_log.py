"""Browsable failure logs for a graded batch run (markdown, meant to be scrolled in VS Code preview).

    python -m vharvey.failure_log base-dev15      # -> logs/base-dev15/INDEX.md + one page per trial

INDEX.md: score table (task x model), then every failed criterion grouped by type (precision first), each with
both judges' reasoning and a link to the trial page. A trial page has the task, every criterion with both
verdicts and reasoning, the agent's full response.md, a link to the verbatim transcript, and an ``Analysis``
section that is kept when the page is regenerated (notes written there survive re-runs).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import batch, paths, transcript_md

LOGS = paths.ROOT / "logs"
ANALYSIS = "## Analysis"
KINDS = [("precision", r"precision"), ("matter", r"qualifying matter|^matter|identifies matter"),
         ("document", r"record|document|file|evidence"), ("number", r"count|total|number|average|median|amount|\$"),
         ("other", r".")]


def kind(c: dict) -> str:
    t = f"{c.get('title', '')} {c.get('match_criteria', '')}".lower()
    for k, rx in KINDS:
        if re.search(rx, c.get("title", "").lower()) or (k == "number" and re.search(rx, t)):
            return k
    return "other"


def _judges(tdir: Path) -> dict[str, dict[str, dict]]:
    out = {}
    for sp in sorted(tdir.glob("scores_*.json")):
        if sp.name != "scores_dual.json":
            s = json.loads(sp.read_text())
            out[s["judge_model"]] = {r.get("criterion_id") or r.get("id"): r for r in s["criteria_results"]}
    return out


def _old_analysis(page: Path) -> str:
    if page.exists():
        text = page.read_text()
        if ANALYSIS in text:
            return text[text.index(ANALYSIS):]
    return f"{ANALYSIS}\n\n_(not analysed yet)_\n"


def page_name(row: dict) -> str:
    """'052' for a task's first trial, '052_t1' for later ones."""
    return row["task"] if row.get("trial", "t0") == "t0" else f"{row['task']}_{row['trial']}"


def trial_page(row: dict, out: Path) -> list[dict]:
    """Write the trial page; return its failed criteria (failed by at least one judge)."""
    tdir = Path(row["dir"])
    task = json.loads((paths.TASKS / row["task"] / "task.json").read_text())
    judges = _judges(tdir)
    tr = tdir / "transcript.md"
    tr.write_text(transcript_md.render(tdir))
    metrics = json.loads((tdir / "metrics.json").read_text())
    page = out / row["model"] / f"{page_name(row)}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    rel_tr = Path("../../..") / tr.relative_to(paths.ROOT)
    lines = [f"# Task {row['task']} · {row['model']} · criteria {row['crit']:.2f} · all-pass {row['all_pass']}", "",
             f"[verbatim transcript]({rel_tr.as_posix()}) · turns {metrics['turn_count']} · "
             f"{metrics['wall_clock_seconds']:.0f} s · finish `{metrics['finish_reason']}`", "",
             "## Task", "", task["instructions"], "", "## Criteria", ""]
    failed = []
    for c in task["criteria"]:
        verdicts = {m: j.get(c["id"], {}) for m, j in judges.items()}
        ok = all(v.get("verdict") == "pass" for v in verdicts.values())
        mark = "✅" if ok else ("❌" if all(v.get("verdict") == "fail" for v in verdicts.values()) else "⚠️ split")
        lines += [f"### {mark} {c['id']} [{kind(c)}] {c['title']}", "", f"> {c['match_criteria']}", ""]
        for m, v in verdicts.items():
            lines.append(f"- **{m}: {v.get('verdict')}**: {v.get('reasoning', '')}")
        lines.append("")
        if not ok:
            failed.append({"task": row["task"], "model": row["model"], "id": c["id"], "kind": kind(c),
                           "title": c["title"], "match": c["match_criteria"], "verdicts": verdicts,
                           "page": page.relative_to(out).as_posix()})
    resp = tdir / "output" / "response.md"
    lines += ["## Agent response (output/response.md)", "",
              resp.read_text() if resp.exists() else "_No response.md was written._", "", _old_analysis(page)]
    page.write_text("\n".join(lines))
    return failed


def build(run: str) -> Path:
    out = LOGS / run
    out.mkdir(parents=True, exist_ok=True)
    rows = batch.results(run)
    failed: list[dict] = []
    for r in rows:
        failed += trial_page(r, out)
    models = sorted({r["model"] for r in rows})
    by = {(r["task"], r["model"]): r for r in rows if r.get("trial", "t0") == "t0"}
    lines = [f"# Failure log: {run}", "", f"{len(rows)} graded trials. Criteria = dual-judge criterion pass; "
             "AP = dual all-pass (0.5 = judges disagree).", "", "| task | " + " | ".join(models) + " |",
             "|---|" + "---|" * len(models)]
    for t in sorted({r["task"] for r in rows}):
        cells = []
        for m in models:
            r = by.get((t, m))
            cells.append(f"[{r['crit']:.2f} / AP {r['all_pass']}]({m}/{page_name(r)}.md)" if r else "–")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        if rs:
            lines.append(f"\n**{m}**: mean criteria {sum(r['crit'] for r in rs) / len(rs):.3f}, "
                         f"all-pass {sum(r['all_pass'] for r in rs) / len(rs):.3f} (n={len(rs)})")
    groups: dict[str, list[dict]] = defaultdict(list)
    for f in failed:
        groups[f["kind"]].append(f)
    lines += ["", "## Failed criteria by type", "",
              " · ".join(f"{k}: {len(groups[k])}" for k, _ in KINDS if groups[k])]
    for k, _ in KINDS:
        if not groups[k]:
            continue
        lines += ["", f"### {k} ({len(groups[k])})", ""]
        for f in sorted(groups[k], key=lambda f: (f["task"], f["model"])):
            lines.append(f"- [{f['task']} · {f['model']} · {f['id']}]({f['page']}) {f['title']}")
            for m, v in f["verdicts"].items():
                lines.append(f"  - {m} **{v.get('verdict')}**: {(v.get('reasoning') or '')[:400]}")
    (out / "INDEX.md").write_text("\n".join(lines) + "\n")
    (out / "failed_criteria.json").write_text(json.dumps(failed, indent=1))
    return out / "INDEX.md"


if __name__ == "__main__":
    print(build(sys.argv[1]))
