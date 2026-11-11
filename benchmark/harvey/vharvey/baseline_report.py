"""Baseline failure analysis on the train (dev) split, A0 only: where would a verifier help?

    python -m vharvey.baseline_report [--run base-dev50]     # -> docs/BASELINE_TRAIN.md + logs/baseline_train.json

For every failing criterion of every A0 dev trial:
- precision: the matters the judges say were wrongly asserted (ids in the judge reasoning, outside the allowed set,
  present in the answer). Each wrong matter is labelled (claude-sonnet-5, offline analysis only) with the attribute
  that separates it from the qualifying set, given the task, the allowed set, the agent's own lines about it and the
  matter's FV card;
- required matter: was the matter ever seen in the trajectory (its id in any tool call or result)? never seen ->
  search/enumeration miss; seen -> judged out, labelled like precision;
- document / number / other: counted, with examples.
Each class maps to a verifier API (scope, call, return). Rubrics are used only for this evaluation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import batch, failure_log, paths
from .compare import _criteria_pass
from .fv import api
from .fv.common import call_json

LABELER = "claude-sonnet-5"
ID = re.compile(r"\b\d{4}-\d{5}\b")
CLASSES = {
    "outcome_status": "outcome or status (settled vs dismissed, closed vs dormant, closed deal vs terminated)",
    "practice_area": "practice area / matter type (e.g. ABS deal listed as capital markets)",
    "client_role_relief": "the firm client's side or the relief it sought (defendant vs plaintiff, counterclaim)",
    "term_absent_or_different": "the asked term/issue is absent or a different one (CVR vs earnout, MFN missing)",
    "draft_vs_executed": "the term exists only in a draft / proposal / unexecuted document",
    "mentioned_not_analysed": "the issue is only mentioned or flagged, not substantively analysed",
    "date_or_period": "wrong year / period / threshold (closed in 2022 not 2023, deal below $1B)",
    "matter_identity": "wrong matter number for the right client / deal (another matter of the same client)",
    "context_listing": "listed only as context/comparison but the judge counted it as asserted",
    "reference_disputable": "the matter arguably qualifies; the reference set looks too narrow",
    "other": "none of the above",
}
API_FOR = {
    "outcome_status": 'fv_check(m, "outcome", "dismissed") / fv_check(m, "status", "closed")',
    "practice_area": 'fv_check(m, "practice_area", "capital_markets") (primary vs SECONDARY)',
    "client_role_relief": 'fv_check(m, "client_role", "plaintiff") / fv_check(m, "relief_sought_by_client", ...)',
    "term_absent_or_different": 'fv_check(m, "term.earnout") -> NOT_FOUND, lists the terms the matter does have',
    "draft_vs_executed": 'fv_check(m, "term.<key>") -> FALSE "only in drafts"; fv_doc(path).stage',
    "mentioned_not_analysed": 'fv_check(m, "issue.<key>", "analysed") -> FALSE "only mentioned"',
    "date_or_period": 'fv_check(m, "closed_year", 2023) / fv_matter(m) dates and amounts',
    "matter_identity": "fv_matter(m): client + one-line description + dates",
    "context_listing": "answer-format rule (no verifier)",
    "reference_disputable": "none (benchmark side)",
    "other": "case by case",
}

LABEL_PROMPT = """A legal research agent answered a question about a law firm's matters. The grader says it wrongly \
listed matter {mid} as qualifying. Using the facts below, pick the ONE attribute that separates {mid} from the \
qualifying set. Return ONE JSON object: {{"class": "<one key below>", "why": "<one sentence, concrete>"}}

Classes:
{classes}

QUESTION: {question}
QUALIFYING SET (reference): {allowed}
WHAT THE AGENT WROTE ABOUT {mid}:
{lines}
INDEX CARD OF {mid} (offline extraction from the matter's files):
{card}
"""


MISSED_PROMPT = """A legal research agent answered a question about a law firm's matters. It saw matter {mid} \
during its search but did NOT list it, and the grader says {mid} qualifies. Using the facts below, pick the ONE \
attribute the agent misjudged when it left {mid} out. Return ONE JSON object: {{"class": "<one key below>", \
"why": "<one sentence, concrete>"}}

Classes:
{classes}

QUESTION: {question}
QUALIFYING SET (reference): {allowed}
WHAT THE AGENT WROTE ABOUT {mid} (empty if it never mentioned it in the answer):
{lines}
INDEX CARD OF {mid} (offline extraction from the matter's files):
{card}
"""


def _card_brief(mid: str) -> str:
    m = api.matter(mid)
    if "error" in m:
        return "(no card)"
    keep = ("client", "description", "matter_type", "primary_practice_area", "practice_areas", "client_role",
            "status", "outcome", "opened_date", "closed_date", "relief_sought_by_client", "terms_executed",
            "terms_draft_only", "issues_analysed", "issues_mentioned_only")
    return json.dumps({k: m.get(k) for k in keep}, ensure_ascii=False)[:3500]


def _seen(tdir: Path, mid: str) -> bool:
    """The agent touched the matter: a tool call argument names it (read/grep/cat inside its folder), or a search
    result line points into one of its files (``<id>/...:`` as grep prints). A bare folder listing does not count."""
    hit = re.compile(re.escape(mid) + r"/[^\n]*:")
    for line in (tdir / "transcript.jsonl").open():
        d = json.loads(line)
        if d["role"] == "assistant":
            if any(mid in (tc.get("arguments") or "") for tc in d.get("tool_calls") or []):
                return True
        elif d.get("tool_name") in ("grep", "bash") and hit.search(d.get("result") or ""):
            return True
    return False


def _lines(text: str, mid: str) -> list[str]:
    return [ln.strip()[:400] for ln in text.splitlines() if mid in ln][:4]


def collect(run: str, model: str = "claude-haiku-5.5") -> dict:
    rows = [r for r in batch.results(run) if r["model"] == model]
    wrong, missed, other = [], [], []
    for r in rows:
        tdir = Path(r["dir"])
        task = json.loads((paths.TASKS / r["task"] / "task.json").read_text())
        cp = _criteria_pass(r["dir"])
        judges = failure_log._judges(tdir)
        resp_p = tdir / "output" / "response.md"
        resp = resp_p.read_text() if resp_p.exists() else ""
        page = f"{run}/{model}/{failure_log.page_name(r)}"
        for c in task["criteria"]:
            if cp[c["id"]] >= 0.5:
                continue
            kind = failure_log.kind(c)
            reasons = " ".join(j.get(c["id"], {}).get("reasoning", "") for j in judges.values())
            base = {"task": r["task"], "trial": r["trial"], "title": task["title"], "page": page,
                    "question": task["instructions"].split("Output:")[0].strip(), "criterion": c,
                    "reason": reasons[:600]}
            if kind == "precision":
                allowed = set(ID.findall(c["match_criteria"]))
                bad = sorted({m for m in ID.findall(reasons) if m not in allowed and m in resp})
                for mid in bad:
                    wrong.append({**base, "matter": mid, "allowed": sorted(allowed), "lines": _lines(resp, mid)})
                if not bad:
                    other.append({**base, "kind": "precision (no wrong id found)"})
            elif kind == "matter" and (m := ID.search(c["match_criteria"])):
                mid = m.group(0)
                seen = _seen(tdir, mid)
                missed.append({**base, "matter": mid, "seen": seen, "in_answer": mid in resp,
                               "lines": _lines(resp, mid)})
            else:
                other.append({**base, "kind": kind})
    return {"run": run, "n_trials": len(rows), "wrong": wrong, "missed": missed, "other": other}


def label(items: list[dict], what: str) -> None:
    classes = "\n".join(f"- {k}: {v}" for k, v in CLASSES.items())

    def one(it: dict) -> None:
        tmpl = MISSED_PROMPT if what == "missed" else LABEL_PROMPT
        prompt = tmpl.format(mid=it["matter"], classes=classes, question=it["question"][:1500],
                                     allowed=", ".join(it.get("allowed") or ["(see criterion)"]) or "-",
                                     lines="\n".join(it["lines"]) or "(not mentioned)", card=_card_brief(it["matter"]))
        out = call_json(LABELER, prompt, "baseline_label", max_tokens=2000)
        it["class"] = out.get("class") if out.get("class") in CLASSES else "other"
        it["why"] = out.get("why", "")

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(one, items))


def to_md(d: dict) -> str:
    wrong, missed, other = d["wrong"], d["missed"], d["other"]
    seen_excl = [m for m in missed if m["seen"]]
    never = [m for m in missed if not m["seen"]]
    oc = Counter(o["kind"] for o in other)
    wc = Counter(w["class"] for w in wrong)
    sc = Counter(m["class"] for m in seen_excl)
    out = [
        "# 1 · Baseline failures on the train split (A0 only) and where a verifier would help", "",
        f"**Data:** the plain LAB agent (A0, Haiku 5.5) on the 50 dev (train) tasks, 2 trials each = "
        f"{d['n_trials']} trials. Test tasks are not used on this page.",
        "Every failing rubric criterion was assigned to one of the cases below. Wrong and missed matters were "
        "labelled with the attribute that went wrong (claude-sonnet-5 offline, given the question, the reference "
        "set, the agent's own lines and the matter's index card). The labels are analysis only and are never fed "
        "to the agent.", "",
        "## Where the failures are", "",
        "| failure | criteria (trial-level) | what went wrong | verifier opportunity |", "|---|---|---|---|",
        f"| **Wrong matter listed** (precision) | {len(wrong)} wrong matters in "
        f"{len({(w['task'], w['trial']) for w in wrong})} trials | near-miss matters included | **check each "
        "matter against the question's conditions** (`fv_check`) |",
        f"| **Required matter missing — never seen** | {len(never)} | search stopped before reaching it "
        "| **completeness against an index** (`fv_check_complete` / list-by-conditions) |",
        f"| **Required matter missing — seen but left out** | {len(seen_excl)} | agent judged it out "
        "| `fv_check` on the condition it misjudged |",
        f"| Proof document missing | {oc['document']} | matter named, its evidence file not | evidence paths "
        "in every verdict / `fv_doc` |",
        f"| Number / aggregate wrong | {oc['number']} | wrong count or sum | count over the index |",
        f"| Other (people, dates, classifications…) | {oc['other'] + oc.get('precision (no wrong id found)', 0)} "
        "| mixed | case by case |", "",
        "## A. Wrong matters listed: which attribute was wrong", "",
        "| attribute | wrong matters | verifier call that catches it |", "|---|---|---|"]
    for k, n in wc.most_common():
        out.append(f"| {CLASSES[k]} | {n} | `{API_FOR[k]}` |")
    out += ["", "## B. Required matters missed", "",
            f"- **{len(never)} never seen**: no tool call named the matter and no search hit pointed into its files "
            "(a bare folder listing does not count). The search did not reach it; only an enumeration/completeness "
            "check can catch these.",
            f"- **{len(seen_excl)} seen but left out.** What was misjudged:", "",
            "| attribute | missed matters | verifier call |", "|---|---|---|"]
    for k, n in sc.most_common():
        out.append(f"| {CLASSES[k]} | {n} | `{API_FOR[k]}` |")
    out += ["", "## Examples (each links to the full trajectory in the Trials tab)", ""]
    shown: set = set()
    for k, _ in wc.most_common():
        for w in [w for w in wrong if w["class"] == k and w["task"] not in shown][:2]:
            shown.add(w["task"])
            card = api.matter(w["matter"])
            out += [f"### Wrong matter · {CLASSES[k]} · task {w['task']} ({w['trial']})", "",
                    f"> {w['question']}", "",
                    f"- **Agent listed {w['matter']}:** " + (" / ".join(w["lines"][:2]) or "_(in a table)_"),
                    f"- **Why it is wrong:** {w['why']}",
                    f"- **Judge:** {w['reason'][:300]}",
                    f"- **Index card of {w['matter']}:** primary practice `{card.get('primary_practice_area')}`, "
                    f"outcome `{(card.get('outcome') or {}).get('value')}`, role `{card.get('client_role')}`, "
                    f"executed terms {', '.join((card.get('terms_executed') or [])[:12])}",
                    f"- **Verifier that would stop it:** `{API_FOR[k]}`",
                    f"- Trajectory: `{w['page']}`", ""]
    for m in never[:3]:
        out += [f"### Missed, never seen · task {m['task']} ({m['trial']}): {m['matter']}", "",
                f"> {m['question']}", "", f"- **Rubric:** {m['criterion']['match_criteria']}",
                f"- **Judge:** {m['reason'][:250]}",
                "- **Verifier:** `fv_check_complete(conditions, my_list)` returns the index matches not in the "
                "list (here it would name this matter), and the agent confirms it in the documents.",
                f"- Trajectory: `{m['page']}`", ""]
    for k in ("document", "number"):
        for o in [o for o in other if o["kind"] == k][:2]:
            out += [f"### {k} · task {o['task']} ({o['trial']})", "", f"> {o['question']}", "",
                    f"- **Rubric:** {o['criterion']['match_criteria']}", f"- **Judge:** {o['reason'][:250]}",
                    f"- Trajectory: `{o['page']}`", ""]
    out += ["## Verifier API scope that follows from this (built offline for all 266 matters; deterministic at "
            "runtime)", "",
            "| API | scope | the agent passes | it returns | built from |", "|---|---|---|---|---|",
            "| `fv_check(matter_id, field, value)` | one condition about one matter | matter id, field (`outcome`, "
            "`status`, `practice_area`, `client_role`, `relief_sought_by_client`, `closed_year`, `term.<key>`, "
            "`issue.<key>`), the value it believes | TRUE / FALSE / SECONDARY / NOT_FOUND / UNKNOWN + actual value + "
            "file path + verbatim quote | matter card (Opus over document cards); terms/issues aggregated from "
            "document cards with draft vs executed kept apart |",
            "| `fv_check_many(checks)` | a candidate list | list of the above | one verdict each | same |",
            "| `fv_matter(matter_id)` | identity and facts | matter id | client, aliases, description, practice "
            "areas, role, status, outcome, dates, terms, issues | matter card |",
            "| `fv_doc(path)` | one file | `<matter>/<folder>/<file>` | type, date, stage (draft … executed), "
            "signed, terms, issues | document card (Sonnet over the file text) |",
            "| `fv_check_complete(conditions, matters)` | the claim \"this list is complete\" | the question's "
            "conditions as fields + the agent's list | index matches missing from the list, listed matters the "
            "index contradicts, possible matches | all matter cards |", ""]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="base-dev50")
    a = ap.parse_args()
    d = collect(a.run)
    label(d["wrong"], "wrong")
    label([m for m in d["missed"] if m["seen"]], "missed")
    (paths.ROOT / "logs" / "baseline_train.json").write_text(json.dumps(d, indent=1, default=str))
    md = to_md(d)
    (paths.ROOT / "docs" / "BASELINE_TRAIN.md").write_text(md)
    print({"trials": d["n_trials"], "wrong": len(d["wrong"]), "missed": len(d["missed"]),
           "seen_excluded": sum(m["seen"] for m in d["missed"]), "other": dict(Counter(o["kind"] for o in d["other"])),
           "wrong_classes": dict(Counter(w["class"] for w in d["wrong"]))})


if __name__ == "__main__":
    main()
