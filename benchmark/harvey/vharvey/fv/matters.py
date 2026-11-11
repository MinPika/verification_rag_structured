"""B3: one matter card per matter.

    python -m vharvey.fv.matters [--workers 12] [--matters ...]

Two parts:
- **LLM part** (claude-opus-5.5, from the matter's document cards, no task text): client and aliases, description,
  practice areas (canonical, from vocab.json), matter type, the firm client's role, status (+date), outcome (+date),
  opened/closed dates, relief sought by the firm's client, people. Every value cites evidence {path, quote}; evidence
  is kept only if the path is a file of this matter and the quote is verbatim in it. A value left with no grounded
  evidence becomes UNKNOWN (null).
- **Deterministic part** (no LLM): terms and issues aggregated from the document cards with canonical keys
  (vocab.json synonyms). A term counts as *executed* when it comes from a document whose stage is executed,
  execution_version or filed, or a signed final; otherwise it is listed under ``draft_terms``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import k0
from .common import FV, call_json, grounded, write_json
from .common import key as kk
from .docs import DOCS

MODEL = "claude-opus-5.5"
MATTERS = FV / "matters"
EXECUTED_STAGES = {"executed", "execution_version", "filed"}
# execution copies in this DMS often carry blank signature lines; the file name is the firm's own version label
EXEC_NAME = re.compile(r"execut|signed|conformed", re.I)
STATUS = ["open", "closed", "dormant", "on_hold", "terminated", "withdrawn", "abandoned"]
OUTCOME = ["settled", "dismissed_voluntary", "dismissed_involuntary", "judgment_for_client",
           "judgment_against_client", "arbitral_award_for_client", "arbitral_award_against_client",
           "transaction_closed", "transaction_terminated", "regulatory_clearance", "advice_delivered", "ongoing",
           "other"]
ROLE = ["plaintiff", "defendant", "counterclaim_plaintiff", "claimant", "respondent", "petitioner", "buyer", "seller",
        "target", "issuer", "underwriter", "placement_agent", "borrower", "lender", "agent_bank", "sponsor_gp",
        "fund", "limited_partner", "investor", "debtor", "creditor", "committee", "licensor", "licensee", "employer",
        "employee", "landlord", "tenant", "insured", "insurer", "regulated_party", "advisee", "other"]
RELIEF = ["compensatory_damages", "declaratory", "injunctive", "specific_performance", "fees_costs", "enforcement",
          "other"]

PROMPT = """You are building the matter card for one matter in a law firm's DMS (the firm is Calderwood & Harkness, \
"C&H"). Below are catalogue cards for every file in the matter folder (each with its path). Decide the matter's \
facts. Use the controlled values given. Cite evidence for every value: {{"path": "<one of the paths below>", \
"quote": "<verbatim text copied from that file's quotes/summary below or from its text, 12-300 chars>"}}. If the \
files do not establish a value, use null; never guess.

Matter folder id: {matter}

Controlled values:
- practice_areas (one or more): {areas}
- client_role (the C&H client's role; one or more): {roles}
- status: {status}
- outcome (how the matter ended or where it stands): {outcomes}
  Notes: "settled" = the parties settled (even if a stipulated dismissal followed); "dismissed_voluntary" /
  "dismissed_involuntary" = dismissal without a settlement; "ongoing" = not yet resolved.
- relief type: {relief}

Return ONE JSON object:
{{
 "client": {{"name": "...", "aliases": ["short names / variants used in the files"], "evidence": [E]}},
 "description": "one sentence: what the matter is (parties, transaction or dispute)",
 "matter_type": {{"value": "short snake_case, e.g. merger_acquisition, ipo, credit_facility, fund_formation, \
commercial_litigation, patent_litigation, arbitration, regulatory_investigation, restructuring, ...", "evidence": [E]}},
 "practice_areas": [{{"value": "<controlled>", "evidence": [E]}}],
 "client_role": [{{"value": "<controlled>", "evidence": [E]}}],
 "counterparties": ["main opposing / other parties"],
 "opened_date": {{"value": "YYYY-MM-DD or null", "evidence": [E]}},
 "status": {{"value": "<controlled or null>", "date": "YYYY-MM-DD or null", "evidence": [E]}},
 "closed_date": {{"value": "YYYY-MM-DD or null", "evidence": [E]}},
 "outcome": {{"value": "<controlled or null>", "date": "YYYY-MM-DD or null", "detail": "one line", "evidence": [E]}},
 "relief_sought_by_client": [{{"type": "<controlled>", "amount": "... or null", "evidence": [E]}}],
 "people": {{"responsible_partner": "...", "billing_partner": "...", "others": ["name (role)"]}}
}}

FILE CARDS:
{cards}
"""


def _compact(card: dict) -> dict:
    keep = ("doc_type", "title", "date", "stage", "signed", "summary", "client", "people", "role_statements",
            "practice_area_signals", "status_statements", "outcome_statements", "relief_sought")
    return {"path": card["_meta"]["path"], **{k: card.get(k) for k in keep}}


def load_vocab() -> dict:
    return json.loads((FV / "vocab.json").read_text())


def synonym_map(entries: list[dict], key: str) -> dict[str, str]:
    m = {}
    for e in entries:
        canon = e[key]
        for s in [canon, e.get("label", ""), *e.get("synonyms", [])]:
            if s:
                m[kk(s)] = canon
    return m




def doc_cards(matter: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((DOCS / matter).rglob("*.json"))]


def _ground(ev: list | None, files: set[str]) -> list[dict]:
    out = []
    for e in ev or []:
        if isinstance(e, dict) and e.get("path") in files and grounded(e["path"], str(e.get("quote") or "")):
            out.append({"path": e["path"], "quote": e["quote"]})
    return out


def _field(obj: dict | None, files: set[str], allowed: list[str] | None = None) -> dict | None:
    if not isinstance(obj, dict) or obj.get("value") in (None, ""):
        return None
    if allowed is not None and obj["value"] not in allowed:
        return None
    ev = _ground(obj.get("evidence"), files)
    return {**obj, "evidence": ev} if ev else None


def aggregate_terms(cards: list[dict], vocab: dict) -> tuple[list, list, list]:
    tmap, imap = synonym_map(vocab["terms"], "key"), synonym_map(vocab["issues"], "key")
    executed, draft = defaultdict(list), defaultdict(list)
    issues: dict[str, dict] = {}
    for c in cards:
        path, stage = c["_meta"]["path"], c.get("stage")
        is_exec = (stage in EXECUTED_STAGES or (stage == "final" and c.get("signed") is True)
                   or bool(EXEC_NAME.search(path.rsplit("/", 1)[-1])))
        for t in c.get("terms") or []:
            key = tmap.get(kk(t.get("key", "")), kk(t.get("key", "")))
            item = {"value": t.get("value"), "path": path, "stage": stage, "quote": t.get("quote")}
            (executed if is_exec else draft)[key].append(item)
        for i in c.get("issues") or []:
            key = imap.get(kk(i.get("key", "")), kk(i.get("key", "")))
            depth = "analysed" if i.get("depth") == "analysed" else "mentioned"
            cur = issues.setdefault(key, {"key": key, "depth": "mentioned", "evidence": []})
            if depth == "analysed":
                cur["depth"] = "analysed"
            cur["evidence"].append({"path": path, "depth": depth, "quote": i.get("quote")})
    to_list = lambda d: [{"key": k, "evidence": v} for k, v in sorted(d.items())]  # noqa: E731
    draft_only = {k: v for k, v in draft.items() if k not in executed}
    return to_list(executed), to_list(draft_only), sorted(issues.values(), key=lambda x: x["key"])


def build_one(matter: str, vocab: dict) -> dict:
    out = MATTERS / f"{matter}.json"
    if out.exists():
        return json.loads(out.read_text())
    cards = doc_cards(matter)
    files = {r["path"] for r in k0.manifest_index().get(matter, [])}
    areas = [a["value"] for a in vocab["practice_areas"]]
    prompt = PROMPT.format(matter=matter, areas=", ".join(areas), roles=", ".join(ROLE), status=", ".join(STATUS),
                           outcomes=", ".join(OUTCOME), relief=", ".join(RELIEF),
                           cards=json.dumps([_compact(c) for c in cards], ensure_ascii=False))
    raw = call_json(MODEL, prompt, "matters", max_tokens=32000)
    card: dict = {"matter_id": matter, "client": None, "description": raw.get("description"),
                  "counterparties": raw.get("counterparties") or [], "people": raw.get("people") or {}}
    cl = raw.get("client") or {}
    ev = _ground(cl.get("evidence"), files)
    if cl.get("name") and ev:
        card["client"] = {"name": cl["name"], "aliases": cl.get("aliases") or [], "evidence": ev}
    card["matter_type"] = _field(raw.get("matter_type"), files)
    card["practice_areas"] = [f for f in (_field(x, files, areas) for x in raw.get("practice_areas") or []) if f]
    card["client_role"] = [f for f in (_field(x, files, ROLE) for x in raw.get("client_role") or []) if f]
    card["opened_date"] = _field(raw.get("opened_date"), files)
    card["status"] = _field(raw.get("status"), files, STATUS)
    card["closed_date"] = _field(raw.get("closed_date"), files)
    card["outcome"] = _field(raw.get("outcome"), files, OUTCOME)
    relief = []
    for r in raw.get("relief_sought_by_client") or []:
        if isinstance(r, dict) and r.get("type") in RELIEF:
            ev = _ground(r.get("evidence"), files)
            if ev:
                relief.append({"type": r["type"], "amount": r.get("amount"), "evidence": ev})
    card["relief_sought_by_client"] = relief
    card["terms_executed"], card["terms_draft_only"], card["issues"] = aggregate_terms(cards, vocab)
    card["documents"] = [{"path": c["_meta"]["path"], "doc_type": c.get("doc_type"), "stage": c.get("stage"),
                          "date": c.get("date"), "title": c.get("title")} for c in cards]
    card["_meta"] = {"model": MODEL, "n_docs": len(cards), "n_files": len(files),
                     "raw_fields_dropped": [k for k in ("matter_type", "status", "closed_date", "outcome",
                                                        "opened_date") if raw.get(k) and not card.get(k)]}
    write_json(out, card)
    return card


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--matters", default="")
    a = ap.parse_args()
    vocab = load_vocab()
    matters = a.matters.split(",") if a.matters else sorted(k0.manifest_index())
    errs = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(build_one, m, vocab): m for m in matters}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
            except Exception as e:
                errs += 1
                print(f"ERROR {futs[f]}: {type(e).__name__}: {str(e)[:200]}", flush=True)
            if i % 10 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} errors {errs}", flush=True)


if __name__ == "__main__":
    main()
