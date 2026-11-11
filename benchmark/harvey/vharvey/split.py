"""Dev/test split of the 250 firm-knowledge tasks: dev 50 / test 200, stratified, deterministic.

Strata = instruction archetype (regex over the instruction text the agent sees) x size bucket (number of rubric
criteria; only the count is used, never criterion content). Within a stratum, tasks are ordered by
sha256(SEED + task id) and every fifth goes to dev (largest-remainder allocation so dev is exactly 50).

    python -m vharvey.split          # writes splits/{dev,test}.txt and splits/split.json
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from . import paths

SEED = "vrag-harvey-split-v1"
DEV_SIZE = 50
SPLITS = paths.ROOT / "splits"

ARCHETYPES: list[tuple[str, str]] = [
    ("conflict", r"\bconflict"),
    ("count", r"\bhow many\b|\bcount\b|\bnumber of\b|\btally\b|\baverage\b|\btotal\b|\bmedian\b|\bpercent"
              r"|\bhow (often|common)\b|\bsplit between\b|\bspread of\b|\bproportion\b|\bshare of\b|\bhow frequently"),
    ("superlative", r"\b(most recent|latest|earliest|first|largest|biggest|highest|lowest|smallest|longest)\b"),
    ("trend", r"\btrend|\bcompare|\bcomparison|\bover time\b|\bmarket standard|\btypical|\bmarket practice"),
    ("people", r"\b(partner|associate|attorney|lawyer|staff)s?\b.*\b(who|which)\b|\bwho (led|handled|worked)"),
    ("existence", r"\bhave we (ever|done|handled|closed|run|set up|won)\b|\bdo we have (any )?precedent"),
    ("document", r"\b(every|all) (document|file|memo|letter|agreement)s?\b"),
    ("enumerate", r"\b(every|all|each|list|pull|identify|find|which)\b"),
]


def archetype(instruction: str) -> str:
    text = instruction.lower().split("output:")[0]
    for name, rx in ARCHETYPES:
        if re.search(rx, text):
            return name
    return "other"


def size_bucket(n: int) -> str:
    return "1-5" if n <= 5 else "6-15" if n <= 15 else "16+"


def _h(task_id: str) -> str:
    return hashlib.sha256(f"{SEED}:{task_id}".encode()).hexdigest()


def make() -> dict[str, list[str]]:
    strata: dict[str, list[str]] = defaultdict(list)
    meta = {}
    for t in paths.task_ids():
        cfg = json.loads((paths.TASKS / t / "task.json").read_text())
        a, b = archetype(cfg["instructions"]), size_bucket(len(cfg["criteria"]))
        strata[f"{a}|{b}"].append(t)
        meta[t] = {"archetype": a, "size": b}
    total = sum(len(v) for v in strata.values())
    quota = {k: DEV_SIZE * len(v) / total for k, v in strata.items()}
    alloc = {k: int(q) for k, q in quota.items()}
    for k in sorted(quota, key=lambda k: (-(quota[k] - alloc[k]), k))[: DEV_SIZE - sum(alloc.values())]:
        alloc[k] += 1
    dev = sorted(t for k, v in strata.items() for t in sorted(v, key=_h)[: alloc[k]])
    test = sorted(set(meta) - set(dev))
    return {"dev": dev, "test": test, "meta": meta}  # type: ignore[dict-item]


def load(name: str) -> list[str]:
    return (SPLITS / f"{name}.txt").read_text().split()


def main() -> None:
    s = make()
    SPLITS.mkdir(exist_ok=True)
    for k in ("dev", "test"):
        (SPLITS / f"{k}.txt").write_text("\n".join(s[k]) + "\n")
    (SPLITS / "split.json").write_text(json.dumps({"seed": SEED, **s}, indent=1))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"dev": 0, "test": 0})
    for k in ("dev", "test"):
        for t in s[k]:
            counts[s["meta"][t]["archetype"]][k] += 1  # type: ignore[index]
    print(f"dev {len(s['dev'])} test {len(s['test'])}")
    for a, c in sorted(counts.items()):
        print(f"  {a:12s} dev {c['dev']:3d} test {c['test']:3d}")


if __name__ == "__main__":
    main()
