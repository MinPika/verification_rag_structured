"""Runtime Firm Verifier API: deterministic lookups over the frozen matter and document cards (no LLM calls).

Verdicts:
- TRUE: the card has the field and it matches (practice_area: the matter's primary practice area);
- SECONDARY: (practice_area only) listed for the matter but not its primary practice area;
- FALSE: the card has the field with a different value, backed by evidence;
- NOT_FOUND: (terms/issues) the offline read of every file in the matter found no such term/issue (or only in drafts,
  for terms, reported as FALSE with a note);
- UNKNOWN: the card has no evidence for the field; the agent must check the documents itself.
Every answer carries evidence {path, quote}. Field names and values are normalised through vocab.json synonyms.
"""

from __future__ import annotations

import json
import re
from functools import cache
from typing import Any

from .common import FV
from .common import key as kk
from .docs import DOCS
from .matters import MATTERS, OUTCOME, RELIEF, ROLE, STATUS, synonym_map

MAX_EVIDENCE = 3
CLOSED_STATUSES = {"closed", "terminated", "withdrawn", "abandoned"}
# outcomes that end a matter; their date is a closing date when the index has no explicit one (v3)
FINAL_OUTCOMES = {"settled", "dismissed_voluntary", "dismissed_involuntary", "judgment_for_client",
                  "judgment_against_client", "arbitral_award_for_client", "arbitral_award_against_client",
                  "transaction_closed", "transaction_terminated", "regulatory_clearance"}
NOT_CLOSED_STATUSES = {"open", "dormant", "on_hold"}
BROAD_MATCHES = 25
OUTCOME_FAMILIES = {
    "dismissed": {"dismissed_voluntary", "dismissed_involuntary"},
    "dismissal": {"dismissed_voluntary", "dismissed_involuntary"},
    "won": {"judgment_for_client", "arbitral_award_for_client"},
    "lost": {"judgment_against_client", "arbitral_award_against_client"},
    "judgment": {"judgment_for_client", "judgment_against_client"},
    "award": {"arbitral_award_for_client", "arbitral_award_against_client"},
    "closed_deal": {"transaction_closed"}, "closed": {"transaction_closed"},
    "terminated": {"transaction_terminated"}, "cleared": {"regulatory_clearance"},
}
ROLE_FAMILIES = {"plaintiff": {"plaintiff", "counterclaim_plaintiff", "claimant", "petitioner"},
                 "defendant": {"defendant", "respondent"}}
FIELD_ALIASES = {"practice": "practice_area", "practice_group": "practice_area", "practice_areas": "practice_area",
                 "role": "client_role", "side": "client_role", "relief": "relief_sought_by_client",
                 "relief_sought": "relief_sought_by_client", "closed": "closed_year", "opened": "opened_year",
                 "matter_status": "status"}




@cache
def vocab() -> dict:
    return json.loads((FV / "vocab.json").read_text())


@cache
def _maps() -> tuple[dict, dict, dict]:
    v = vocab()
    return synonym_map(v["practice_areas"], "value"), synonym_map(v["terms"], "key"), synonym_map(v["issues"], "key")


@cache
def card(matter_id: str) -> dict | None:
    p = MATTERS / f"{matter_id}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _ev(items: list[dict] | None) -> list[dict]:
    return [{"path": e.get("path"), "quote": e.get("quote")} for e in (items or [])[:MAX_EVIDENCE]]


def _res(verdict: str, field: str, asked: Any, actual: Any, evidence: list, note: str = "") -> dict:
    out = {"verdict": verdict, "field": field, "asked": asked, "actual": actual, "evidence": evidence}
    if note:
        out["note"] = note
    return out


def parse_field(field: str) -> tuple[str, str | None]:
    """'deal_term.earnout' -> ('term', 'earnout'); 'outcome' -> ('outcome', None). Raises ValueError if unknown."""
    f = field.strip().lower()
    if "." in f:
        kind, fk = f.split(".", 1)
        kind = {"deal_term": "term", "term": "term", "terms": "term", "issue": "issue", "issues": "issue"}.get(kind)
        if not kind:
            raise ValueError(f"unknown field prefix in {field!r}; use term.<key> or issue.<key>")
        return kind, kk(fk)
    f = FIELD_ALIASES.get(kk(f), kk(f))
    if f in ("practice_area", "client_role", "status", "outcome", "closed_year", "opened_year",
             "relief_sought_by_client"):
        return f, None
    _, tmap, imap = _maps()
    if f in tmap:
        return "term", f
    if f in imap:
        return "issue", f
    raise ValueError(f"unknown field {field!r}")


def check(matter_id: str, field: str, value: Any = None) -> dict:
    c = card(matter_id)
    if c is None:
        return {"verdict": "UNKNOWN", "error": f"no matter {matter_id!r} in the index (use the folder id, e.g. "
                                               "1003-00001)"}
    try:
        kind, fk = parse_field(field)
    except ValueError as e:
        return {"verdict": "UNKNOWN", "error": str(e), "fields": FIELDS_HELP}
    amap, tmap, imap = _maps()
    if kind == "practice_area":
        have = [p["value"] for p in c["practice_areas"]]
        allowed = [a["value"] for a in vocab()["practice_areas"]]
        want = resolve(value, amap, allowed)
        if want is None:
            return _res("UNKNOWN", kind, value, have, [], f"unrecognised practice area; allowed: {allowed}")
        ev = [e for p in c["practice_areas"] for e in _ev(p["evidence"])][:MAX_EVIDENCE]
        if not have:
            return _res("UNKNOWN", kind, want, None, [])
        if want == have[0]:
            return _res("TRUE", kind, want, have, ev, "primary practice area of the matter")
        if want in have:
            return _res("SECONDARY", kind, want, have, ev, f"a secondary workstream; the matter's primary practice "
                        f"area is {have[0]}")
        return _res("FALSE", kind, want, have, ev)
    if kind == "client_role":
        have = [p["value"] for p in c["client_role"]]
        want = kk(value)
        if want not in ROLE and want not in ROLE_FAMILIES:
            return _res("UNKNOWN", kind, value, have, [], f"unrecognised role; allowed: {ROLE}")
        if not have:
            return _res("UNKNOWN", kind, want, None, [])
        ev = [e for p in c["client_role"] for e in _ev(p["evidence"])][:MAX_EVIDENCE]
        return _res("TRUE" if ROLE_FAMILIES.get(want, {want}) & set(have) else "FALSE", kind, want, have, ev)
    if kind in ("status", "outcome"):
        f = c.get(kind)
        allowed = OUTCOME if kind == "outcome" else STATUS
        want = kk(value)
        fam = (OUTCOME_FAMILIES if kind == "outcome" else {}).get(want) or ({want} if want in allowed else None)
        if fam is None:
            return _res("UNKNOWN", kind, value, f and {"value": f["value"], "date": f.get("date")},
                        _ev(f["evidence"]) if f else [], f"unrecognised value; allowed: {allowed}")
        if not f:
            return _res("UNKNOWN", kind, want, None, [])
        return _res("TRUE" if f["value"] in fam else "FALSE", kind, want,
                    {"value": f["value"], "date": f.get("date")}, _ev(f["evidence"]), f.get("detail") or "")
    if kind in ("closed_year", "opened_year"):
        return _year(c, kind, value)
    if kind == "relief_sought_by_client":
        have = [r["type"] for r in c["relief_sought_by_client"]]
        want = kk(value)
        if want not in RELIEF:
            return _res("UNKNOWN", kind, value, have, [], f"unrecognised relief type; allowed: {RELIEF}")
        if not have:
            return _res("UNKNOWN", kind, want, None, [])
        ev = [e for r in c["relief_sought_by_client"] for e in _ev(r["evidence"])][:MAX_EVIDENCE]
        return _res("TRUE" if want in have else "FALSE", kind, want, have, ev)
    return _topic(c, kind, fk or "", value)
    return {"verdict": "UNKNOWN", "error": f"unhandled field {field!r}"}


def _tokens(s: str) -> set[str]:
    return {t for t in s.split("_") if t and t not in {"of", "the", "and", "a", "in", "provision", "clause"}}


def resolve(raw: Any, synonyms: dict[str, str], candidates: list[str]) -> str | None:
    """Map a free key/value to a canonical one: exact, synonym, then token overlap (Jaccard >= 0.5). None if no
    candidate is close enough; callers then answer UNKNOWN rather than guessing."""
    k = kk(raw)
    if not k:
        return None
    if k in candidates:
        return k
    if k in synonyms:
        return synonyms[k]
    tk = _tokens(k)
    best, score = None, 0.0
    for cnd in set(candidates) | set(synonyms):
        tc = _tokens(cnd)
        j = len(tk & tc) / len(tk | tc) if tk | tc else 0.0
        if tk <= tc or tc <= tk:
            j = max(j, 0.5 + 0.5 * j)
        if j > score:
            best, score = synonyms.get(cnd, cnd), j
    return best if score >= 0.5 else None


GENERIC = {"adjustment", "provision", "provisions", "clause", "term", "terms", "period", "duration", "amount",
           "mechanism", "right", "rights", "covenant", "language", "present"}


def _contained(raw: Any, candidates: list[str]) -> str | None:
    """A candidate whose tokens contain all of the asked key's non-generic tokens (asked general -> found specific;
    never the reverse, so management_fee_offset cannot match a plain management_fee)."""
    want = _tokens(kk(raw)) - GENERIC
    if not want:
        return None
    hits = [c for c in candidates if want <= _tokens(c)]
    return min(hits, key=lambda c: len(_tokens(c))) if hits else None


def _topic(c: dict, kind: str, raw_key: str, value: Any) -> dict:
    """term.<key> / issue.<key>: one lookup across executed terms, draft-only terms and issues of the matter."""
    v = vocab()
    _, tmap, imap = _maps()
    exe = {t["key"]: t for t in c["terms_executed"]}
    dr = {t["key"]: t for t in c["terms_draft_only"]}
    iss = {i["key"]: i for i in c["issues"]}
    canon = [t["key"] for t in v["terms"]] + [i["key"] for i in v["issues"]]
    syn = {**imap, **tmap} if kind == "term" else {**tmap, **imap}
    key = resolve(raw_key, syn, canon + list(exe) + list(dr) + list(iss))
    # a closely related key that IS in this matter's executed documents (or issues) wins over a draft-only or
    # absent canonical key, e.g. working_capital_adjustment -> net_working_capital_target
    near = _contained(raw_key, list(exe)) or _contained(raw_key, list(iss))
    if near and key not in exe and key not in iss:
        key = near
    label = f"{kind}.{raw_key}"
    if key is None:
        return _res("UNKNOWN", label, value, None, [], "key not in the index vocabulary; check the documents "
                    f"yourself. Terms in this matter: {', '.join(sorted(exe)[:30])}; issues: "
                    f"{', '.join(sorted(iss)[:30])}")
    want = kk(value) if value else "present"
    if key in exe:
        return _res("TRUE", f"term.{key}", want, [e["value"] for e in exe[key]["evidence"]][:3],
                    _ev(exe[key]["evidence"]), "found in an executed/filed document")
    if key in iss:
        i = iss[key]
        ok = want != "analysed" or i["depth"] == "analysed"
        return _res("TRUE" if ok else "FALSE", f"issue.{key}", want, i["depth"], _ev(i["evidence"]),
                    "" if ok else "only mentioned/flagged in this matter, not analysed")
    if key in dr:
        return _res("FALSE", f"term.{key}", want, None, _ev(dr[key]["evidence"]),
                    "in the index this appears only in drafts / non-executed documents of this matter; check the "
                    "executed version before excluding")
    return _res("NOT_FOUND", f"{kind}.{key}", want, None, [],
                "the offline index found no such term or issue in this matter's files (the index can miss terms "
                "in very long documents: if the matter otherwise fits, read its key document before excluding "
                "it). Executed terms here: "
                + ", ".join(sorted(exe)[:30]) + "; issues: " + ", ".join(sorted(iss)[:30]))


def _year(c: dict, kind: str, value: Any) -> dict:
    """closed_year / opened_year. closed_year uses, in order: the explicit closing date; the status date when the
    status is closed/terminated/withdrawn/abandoned; the date of a final outcome (deal closed or terminated,
    settlement, dismissal, judgment, award, clearance) unless the matter is recorded as open/dormant/on hold.
    The reply names which source answered."""
    st = c.get("status") or {}
    if kind == "opened_year":
        f, source = c.get("opened_date"), "opening date"
    else:
        f, source = c.get("closed_date"), "matter closing date"
        st_date = str(st.get("date") or "")
        if not (f and f.get("value")) and st.get("value") in CLOSED_STATUSES and st_date[:4].isdigit():
            f, source = {"value": st["date"], "evidence": st.get("evidence")}, f"status {st['value']} date"
        oc = c.get("outcome") or {}
        if (not (f and f.get("value")) and oc.get("value") in FINAL_OUTCOMES and str(oc.get("date") or "")[:4].isdigit()
                and st.get("value") not in NOT_CLOSED_STATUSES):
            f, source = {"value": oc["date"], "evidence": oc.get("evidence")}, f"final outcome ({oc['value']}) date"
    if not f or not str(f.get("value") or "")[:4].isdigit():
        hint = f"status: {st.get('value')}" if st else ""
        if st.get("value") in NOT_CLOSED_STATUSES:
            hint += "; the matter is recorded as not closed"
        return _res("UNKNOWN", kind, value, None, [], hint.strip("; "))
    year = str(f["value"])[:4]
    return _res("TRUE" if year == str(value).strip()[:4] else "FALSE", kind, value, f["value"], _ev(f["evidence"]),
                f"from the {source}")


def _lead_evidence(mid: str, conds: list[dict]) -> list[dict]:
    """One {condition, path, quote} per condition for an index match, so the agent can open and cite the proof."""
    out = []
    for cond in conds:
        r = check(mid, str(cond["field"]), cond.get("value"))
        ev = (r.get("evidence") or [None])[0]
        if ev:
            out.append({"condition": f"{cond['field']}={cond.get('value')}", **ev})
    return out


def matter(matter_id: str) -> dict:
    c = card(matter_id)
    if c is None:
        return {"error": f"no matter {matter_id!r}"}
    slim = lambda f: None if not f else {k: v for k, v in f.items() if k != "evidence"} | {  # noqa: E731
        "evidence": _ev(f.get("evidence"))[:1]}
    return {"matter_id": matter_id, "client": c.get("client") and {"name": c["client"]["name"],
                                                                    "aliases": c["client"]["aliases"]},
            "description": c.get("description"), "matter_type": (c.get("matter_type") or {}).get("value"),
            "primary_practice_area": c["practice_areas"][0]["value"] if c["practice_areas"] else None,
            "practice_areas": [p["value"] for p in c["practice_areas"]],
            "client_role": [p["value"] for p in c["client_role"]], "counterparties": c.get("counterparties"),
            "status": slim(c.get("status")), "outcome": slim(c.get("outcome")),
            "opened_date": (c.get("opened_date") or {}).get("value"),
            "closed_date": (c.get("closed_date") or {}).get("value"),
            "relief_sought_by_client": [r["type"] for r in c["relief_sought_by_client"]],
            "terms_executed": sorted(t["key"] for t in c["terms_executed"]),
            "terms_draft_only": sorted(t["key"] for t in c["terms_draft_only"]),
            "issues_analysed": sorted(i["key"] for i in c["issues"] if i["depth"] == "analysed"),
            "issues_mentioned_only": sorted(i["key"] for i in c["issues"] if i["depth"] != "analysed"),
            "people": c.get("people"), "n_documents": len(c.get("documents") or []),
            "note": "Use fv_check for a verdict with evidence; fields not listed are UNKNOWN, not absent."}


def doc(path: str) -> dict:
    p = path.strip().lstrip("/")
    p = re.sub(r"^(workspace/)?(documents/)?(matters/)?", "", p)
    f = DOCS / (p + ".json")
    if not f.exists():
        return {"error": f"no document {path!r}; give the path as <matter>/<folder>/<file>"}
    c = json.loads(f.read_text())
    return {"path": p, "doc_type": c.get("doc_type"), "title": c.get("title"), "date": c.get("date"),
            "stage": c.get("stage"), "stage_quote": c.get("stage_quote"), "signed": c.get("signed"),
            "summary": c.get("summary"),
            "terms": [{"key": t["key"], "value": t["value"]} for t in c.get("terms") or []][:30],
            "issues": [{"key": i["key"], "depth": i["depth"]} for i in c.get("issues") or []][:30],
            "outcome_statements": c.get("outcome_statements")[:5], "truncated_read": c["_meta"]["truncated"]}


FIELDS_HELP = ("fields: practice_area, client_role, status, outcome, closed_year, opened_year, "
               "relief_sought_by_client, term.<key> (executed deal/legal terms), issue.<key> (value analysed or "
               "mentioned)")


def check_complete(conditions: list[dict], matters: list[str], limit: int = 60) -> dict:
    """Verify the claim "``matters`` is the complete list of matters satisfying all ``conditions``" against the index.

    For every indexed matter, each condition is checked with ``check``. Index matches = all conditions TRUE. The
    reply lists index matches missing from the agent's list, listed matters the index contradicts (a FALSE /
    NOT_FOUND condition), and matters that might match (no FALSE, at least one UNKNOWN). Index matches are leads, not
    answers: the index can be wrong, so the agent must confirm a missing matter in its documents before adding it.
    """
    conds = [c for c in conditions if isinstance(c, dict) and c.get("field")]
    if not conds:
        return {"error": "give conditions as [{field, value}, ...]", "fields": FIELDS_HELP}
    for c in conds:
        try:
            parse_field(str(c["field"]))
        except ValueError as e:
            return {"error": str(e), "fields": FIELDS_HELP}
    listed = {str(m).strip() for m in matters}
    all_ids = sorted(p.stem for p in MATTERS.glob("*.json"))
    match, possible, contradicted = [], [], []
    for mid in all_ids:
        vs = [check(mid, str(c["field"]), c.get("value"))["verdict"] for c in conds]
        if all(v == "TRUE" for v in vs):
            match.append(mid)
        elif not any(v in ("FALSE", "NOT_FOUND", "SECONDARY") for v in vs):
            possible.append(mid)
        if mid in listed and any(v in ("FALSE", "NOT_FOUND") for v in vs):
            contradicted.append({"matter_id": mid, "verdicts": dict(zip([c["field"] for c in conds], vs, strict=True))})
    missing = [m for m in match if m not in listed]
    describe = lambda m: {"matter_id": m, "client": ((card(m) or {}).get("client") or {}).get("name"),  # noqa: E731
                          "description": (card(m) or {}).get("description"), "evidence": _lead_evidence(m, conds)}
    verdict = "TRUE" if not missing and not contradicted else "FALSE"
    broad = len(match) > BROAD_MATCHES
    return {"verdict": verdict, "conditions": conds, "n_index_matches": len(match),
            **({"warning": f"these conditions match {len(match)} matters: they are probably broader than the question "
                           "(e.g. only a practice area). Add the question's specific condition (term, issue, outcome, "
                           "year) and call again before using the leads."} if broad else {}),
            "missing_from_your_list": [describe(m) for m in missing[:limit]],
            "listed_but_contradicted": contradicted[:limit],
            "possible_matches_unknown": [m for m in possible if m not in listed][:20],
            "note": "Index matches are leads from an offline index that can be wrong or incomplete: open each missing "
                    "matter's documents and confirm before adding it; do not add a matter on the index alone."}
