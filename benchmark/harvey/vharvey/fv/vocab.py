"""B1: canonical vocabularies, derived from the document cards (corpus only, no tasks or rubrics).

    python -m vharvey.fv.vocab      # -> kb/fv/vocab.json

Two phases per category (practice areas, terms, issues), sized so no single call has a huge output:
1. claude-opus-5.5 proposes the canonical list from the most frequent raw labels;
2. claude-sonnet-5 maps every raw label seen at least ``MIN_COUNT`` times onto that list (or "none"), in parallel
   batches. Rarer labels stay unmapped and are handled by fuzzy matching at runtime (api.resolve).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from .common import FV, call_json, key, write_json
from .docs import DOCS

PROPOSER, MAPPER = "claude-opus-5.5", "claude-sonnet-5"
VOCAB = FV / "vocab.json"
MIN_COUNT, TOP_FOR_PROPOSAL, BATCH = 2, 400, 250

WHAT = {
    "practice_areas": ("practice area / practice group of a law firm", "value",
                       "aim for the firm's 12-20 practice groups (e.g. capital markets, banking & finance, "
                       "structured finance, M&A, antitrust, IP, general commercial litigation, ...)"),
    "terms": ("material deal or legal term found in agreements and filings", "key",
              "keep distinct concepts distinct (earnout vs contingent_value_right vs escrow vs holdback; "
              "maintenance vs incurrence covenants; exclusive vs non-exclusive license); aim for 150-300 keys"),
    "issues": ("legal issue, claim type or regulatory event a matter deals with", "key",
               "keep distinct concepts distinct (stark_law vs anti_kickback; hsr_second_request vs hsr_filing); "
               "aim for 150-300 keys"),
}

PROPOSE = """Below are the most frequent raw labels for "{what}" extracted from one law firm's documents (label: count).
Propose the canonical vocabulary: {guide}. Return ONE JSON object:
{{"items": [{{"{field}": "snake_case canonical id", "label": "human label"}}]}}

RAW LABELS:
{labels}
"""

MAP = """Map each raw label for "{what}" to one canonical id from the list, or "none" if no canonical id has the
same meaning (do not force near-misses: a related but different concept is "none"). Return ONE JSON object
{{"map": {{"<raw label>": "<canonical id or none>", ...}}}} covering every raw label below.

CANONICAL IDS:
{canon}

RAW LABELS:
{labels}
"""


def collect() -> dict[str, Counter]:
    out: dict[str, Counter] = {"practice_areas": Counter(), "terms": Counter(), "issues": Counter()}
    for p in DOCS.rglob("*.json"):
        c = json.loads(p.read_text())
        out["practice_areas"].update(key(s.get("area")) for s in c.get("practice_area_signals") or [])
        out["terms"].update(key(t.get("key")) for t in c.get("terms") or [])
        out["issues"].update(key(i.get("key")) for i in c.get("issues") or [])
    for c in out.values():
        c.pop("", None)
    return out


def _category(cat: str, counts: Counter) -> list[dict]:
    what, field, guide = WHAT[cat]
    top = "\n".join(f"{k}: {v}" for k, v in counts.most_common(TOP_FOR_PROPOSAL))
    items = call_json(PROPOSER, PROPOSE.format(what=what, guide=guide, field=field, labels=top), "vocab_propose",
                      max_tokens=32000)["items"]
    canon = {key(i[field]): i.get("label", "") for i in items if i.get(field)}
    raw = [k for k, v in counts.most_common() if v >= MIN_COUNT]
    batches = [raw[i:i + BATCH] for i in range(0, len(raw), BATCH)]
    canon_txt = "\n".join(f"{k}: {lab}" for k, lab in canon.items())

    def one(b: list[str]) -> dict:
        return call_json(MAPPER, MAP.format(what=what, canon=canon_txt, labels="\n".join(b)), "vocab_map",
                         max_tokens=32000).get("map", {})

    syn: dict[str, list[str]] = defaultdict(list)
    with ThreadPoolExecutor(16) as ex:
        for m in ex.map(one, batches):
            for r, c in m.items():
                ck = key(c)
                if ck in canon and key(r) != ck:
                    syn[ck].append(key(r))
    return [{field: k, "label": lab, "synonyms": sorted(set(syn[k]))} for k, lab in canon.items()]


def build() -> dict:
    counts = collect()
    out: dict = {cat: _category(cat, counts[cat]) for cat in WHAT}
    out["_counts"] = {cat: {"raw": len(c), f"raw_ge_{MIN_COUNT}": sum(v >= MIN_COUNT for v in c.values()),
                            "mapped": sum(len(e["synonyms"]) for e in out[cat])} for cat, c in counts.items()}
    write_json(VOCAB, out)
    return out


if __name__ == "__main__":
    v = build()
    print({k: len(v[k]) for k in WHAT}, v["_counts"])
