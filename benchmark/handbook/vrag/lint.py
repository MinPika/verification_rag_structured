"""Deterministic lint of a compiled PolicyKB against its K0 corpus.

- every Ref: block ids exist; the quote occurs verbatim (after whitespace/dash/quote normalisation) in the cited
  blocks ('ok'), elsewhere in the corpus ('misanchored'), or nowhere ('ungrounded');
- every template subject/body and action literal: each literal segment between [placeholders] occurs in the corpus;
- action template ids resolve.
Ungrounded template text is the most dangerous defect (the agent would copy invented wording), so it is reported
per template and such templates are flagged ``grounded: false`` for the runtime.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from . import paths

_DASH = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'",
                       "\u201c": '"', "\u201d": '"', "\u00a0": " ", "\u2026": "..."})


def norm(s: str) -> str:
    s = (s or "").translate(_DASH)
    s = re.sub(r"\*\*|__", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_blocks(task: str) -> dict[str, str]:
    docs = json.loads((paths.KB / task / "k0" / "corpus.json").read_text())
    return {b["id"]: b["text"] for d in docs if d["role"] == "policy" for b in d["blocks"]}


def segments(text: str) -> list[str]:
    parts = re.split(r"\[[^\]]{1,80}\]|\{[^}]{1,80}\}|<[^>]{1,80}>", text or "")
    out = []
    for p in parts:
        for line in re.split(r"\\n|\n", p):
            line = norm(line).strip(" .,:;|-")
            if len(line) >= 12:
                out.append(line)
    return out


def lint(task: str, kb: dict) -> dict:
    blocks = load_blocks(task)
    nblocks = {k: norm(v) for k, v in blocks.items()}
    full = " ".join(nblocks.values())
    stats: Counter = Counter()
    issues = []

    def check_refs(where: str, refs: list[dict]):
        if not refs:
            stats["no_ref"] += 1
            issues.append({"where": where, "issue": "no_ref"})
        for r in refs:
            q = norm(r.get("quote", ""))
            bids = r.get("blocks", [])
            bad = [b for b in bids if b not in blocks]
            if bad:
                stats["bad_block"] += 1
            local = " ".join(nblocks.get(b, "") for b in bids)
            if q and q in local:
                stats["ref_ok"] += 1
            elif q and q in full:
                stats["ref_misanchored"] += 1
            else:
                stats["ref_ungrounded"] += 1
                issues.append({"where": where, "issue": "ungrounded_quote", "quote": r.get("quote", "")[:160]})

    for sec in ("definitions", "people", "channels", "files", "tables", "rules", "templates"):
        for i, it in enumerate(kb.get(sec, [])):
            check_refs(f"{sec}:{it.get('id') or it.get('name') or it.get('term') or i}", it.get("refs", []))
    tpl_ids = {t["id"] for t in kb.get("templates", [])}
    for t in kb.get("templates", []):
        segs = segments(t.get("subject", "")) + segments(t.get("body", ""))
        miss = [s for s in segs if s not in full]
        t["grounded"] = not miss
        stats["tpl_grounded" if not miss else "tpl_ungrounded"] += 1
        if miss:
            issues.append({"where": f"template:{t['id']}", "issue": "template_text_not_in_corpus",
                           "missing": [m[:120] for m in miss[:4]]})
    for p in kb.get("procedures", []):
        check_refs(f"procedure:{p['id']}", p.get("refs", []))
        for s in p.get("steps", []):
            check_refs(f"step:{s['id']}", s.get("refs", []))
            for a in s.get("actions", []):
                if a.get("template") and a["template"] not in tpl_ids:
                    stats["bad_template_ref"] += 1
                    issues.append({"where": f"step:{s['id']}", "issue": "unknown_template", "id": a["template"]})
                for seg in segments(a.get("literal", "")):
                    if seg not in full:
                        stats["literal_ungrounded"] += 1
                        issues.append({"where": f"step:{s['id']}", "issue": "literal_not_in_corpus",
                                       "text": seg[:120]})
    n = stats["ref_ok"] + stats["ref_misanchored"] + stats["ref_ungrounded"]
    summary = {"refs": n, "ref_ok": stats["ref_ok"], "ref_misanchored": stats["ref_misanchored"],
               "ref_ungrounded": stats["ref_ungrounded"], "no_ref": stats["no_ref"],
               "templates": len(tpl_ids), "tpl_ungrounded": stats["tpl_ungrounded"],
               "literal_ungrounded": stats["literal_ungrounded"], "bad_template_ref": stats["bad_template_ref"],
               "grounded_pct": round(100 * (stats["ref_ok"] + stats["ref_misanchored"]) / n, 1) if n else 0.0}
    return {"summary": summary, "issues": issues}


if __name__ == "__main__":
    import sys

    for t in sys.argv[1:]:
        kb = json.loads((paths.KB / t / "kb.json").read_text())
        print(t, json.dumps(lint(t, kb)["summary"]))
