"""Per-matter attribution of an FV arm against the baseline: for every required matter (a criterion naming a matter)
that one run passes and the other fails, did the FV arm check it, and what did the verifier say?

    python -m vharvey.attribution base-dev50 VL-dev50     # -> logs/attribution_<arm>.json + printed summary

Uses rubric criteria only to *evaluate* (which matters were required); nothing here feeds back into the cards.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import batch, paths
from .compare import _criteria_pass


def fv_checks(tdir: str) -> dict[str, list[str]]:
    """matter id -> ['field=asked->VERDICT', ...] from the trial's FV log."""
    out: dict[str, list[str]] = defaultdict(list)
    for e in json.loads((Path(tdir) / "vharvey.json").read_text()).get("arm_log") or []:
        res = e.get("result")
        args = e.get("args")
        args = json.loads(args) if isinstance(args, str) and args.strip().startswith("{") else (args or {})
        for r in res if isinstance(res, list) else [res]:
            if isinstance(r, dict) and r.get("verdict"):
                mid = r.get("matter_id") or (args.get("matter_id") if isinstance(args, dict) else None)
                if mid:
                    out[mid].append(f"{r.get('field')}={r.get('asked')}->{r['verdict']}")
            if e.get("tool") == "fv_check_complete" and isinstance(r, dict):
                for m in r.get("missing_from_your_list") or []:
                    out[m["matter_id"]].append("complete->LEAD")
    return out


def attribute(base: str, arm: str, model: str = "claude-haiku-5.5") -> dict:
    a = {x["task"]: x for x in batch.results(base) if x["model"] == model and x["trial"] == "t0"}
    v = {x["task"]: x for x in batch.results(arm) if x["model"] == model and x["trial"] == "t0"}
    lost, gained = [], []
    cls: Counter = Counter()
    for t in sorted(set(a) & set(v)):
        task = json.loads((paths.TASKS / t / "task.json").read_text())
        pa, pv = _criteria_pass(a[t]["dir"]), _criteria_pass(v[t]["dir"])
        checks = fv_checks(v[t]["dir"])
        for c in task["criteria"]:
            m = re.search(r"matter (\d{4}-\d{5})", c["match_criteria"])
            if not m or "precision" in c["title"].lower():
                continue
            mid, ch = m.group(1), checks.get(m.group(1), [])
            if pa[c["id"]] >= 0.5 > pv[c["id"]]:
                bad = [x for x in ch if not x.endswith(("TRUE", "LEAD"))]
                k = "lost:verifier_not_TRUE" if bad else ("lost:checked_TRUE" if ch else "lost:never_checked")
                cls[k] += 1
                lost.append({"task": t, "criterion": c["id"], "matter": mid, "class": k, "checks": ch[:6]})
            elif pv[c["id"]] >= 0.5 > pa[c["id"]]:
                k = "gained:via_completeness_lead" if any(x == "complete->LEAD" for x in ch) else "gained:other"
                cls[k] += 1
                gained.append({"task": t, "criterion": c["id"], "matter": mid, "class": k})
    out = {"base": base, "arm": arm, "summary": dict(cls), "lost": lost, "gained": gained}
    (paths.ROOT / "logs" / f"attribution_{arm}.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = attribute(sys.argv[1], sys.argv[2])
    print(r["summary"])
    for x in r["lost"]:
        if x["class"] == "lost:verifier_not_TRUE":
            print(" ", x["task"], x["matter"], x["checks"])
