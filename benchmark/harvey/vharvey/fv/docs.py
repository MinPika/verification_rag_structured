"""B2: one document card per DMS file (claude-sonnet-5), every extracted value backed by a verbatim quote.

    python -m vharvey.fv.docs [--workers 24] [--limit N] [--matters 1001-00001,...]

Input: the file's K0 text (what LAB's ``read`` returns), its matter folder id and relative path. Nothing about any
task or rubric. Output: kb/fv/docs/<matter>/<relpath>.json = the model's card plus ``_grounding``: every list item
whose quote is not found verbatim in the file is dropped (and counted), so no ungrounded value reaches runtime.
Long files: the first HEAD and last TAIL characters are sent and the card records ``truncated``.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import k0
from .common import FV, call_json, grounded, write_json

MODEL = "claude-sonnet-5"
HEAD, TAIL = 90_000, 30_000
DOCS = FV / "docs"
QUOTED_LISTS = ("status_statements", "outcome_statements", "practice_area_signals", "relief_sought", "terms",
                "issues", "role_statements")

PROMPT = """You are cataloguing one file from a law firm's document management system (the firm is Calderwood & \
Harkness LLP, "C&H", "the firm"). Read it and return ONE JSON object describing it. Be literal: report only what \
this file states. Every item in the list fields must carry a "quote" copied EXACTLY (verbatim, 12-300 characters) \
from the file text below; items you cannot support with an exact quote must be omitted.

File: {path}
Matter folder: {matter} (the DMS folder id; numbers printed inside documents can be wrong, do not "correct" it)
{trunc}
JSON schema (all keys required; use null / [] when the file says nothing):
{{
 "doc_type": "short snake_case type, e.g. engagement_letter, merger_agreement, credit_agreement, lpa, side_letter, \
complaint, counterclaim, answer, motion, order, stipulation_of_dismissal, settlement_agreement, judgment, \
arbitral_award, closing_memo, status_memo, legal_memo, letter, email, checklist, tracker_spreadsheet, presentation, \
term_sheet, other",
 "title": "the document's own title or subject line",
 "date": "YYYY-MM-DD or null (the document's own date)",
 "stage": "one of: draft, redline, execution_version, executed, filed, final, template, unsigned, not_applicable",
 "stage_quote": "verbatim words that show the stage (e.g. 'EXECUTION VERSION', 'DRAFT', signature block, \
'Filed') or null",
 "signed": "true if signatures/conformed signatures appear, false if signature lines are blank, null if n/a",
 "summary": "2-3 sentences: what this document is and what it says about the matter",
 "client": "the C&H client this matter is for, as named in the file, or null",
 "people": [{{"name": "...", "role": "e.g. Responsible Partner, Billing Partner, associate, opposing counsel, \
judge, client contact", "group": "practice group if stated or null"}}],
 "role_statements": [{{"party": "name", "role": "e.g. plaintiff, defendant, counterclaim-plaintiff, claimant, \
respondent, buyer, seller, issuer, underwriter, borrower, lender, sponsor/GP, limited partner, debtor, creditor, \
licensor, licensee, employer, employee", "is_firm_client": true, "quote": "..."}}],
 "practice_area_signals": [{{"area": "practice group or matter type as the file names it", "quote": "..."}}],
 "status_statements": [{{"status": "e.g. open, closed, dormant, on hold, terminated, withdrawn, abandoned, \
pending, completed", "date": "YYYY-MM-DD or null", "quote": "..."}}],
 "outcome_statements": [{{"outcome": "what finally happened, in the file's words (e.g. settled, dismissed \
voluntarily, dismissed with prejudice after settlement, judgment for X, award, deal closed, deal terminated, \
cleared by regulator, second request issued)", "date": "YYYY-MM-DD or null", "quote": "..."}}],
 "relief_sought": [{{"by": "party seeking it", "by_firm_client": true, "type": "compensatory_damages | \
declaratory | injunctive | specific_performance | fees_costs | enforcement | other", "amount": "as stated or null", \
"quote": "..."}}],
 "terms": [{{"key": "snake_case name of a material deal/legal term (e.g. earnout, contingent_value_right, \
escrow, holdback, indemnity_cap, non_compete, lock_up, over_allotment_option, underwriting_basis, \
management_fee, management_fee_offset, carried_interest, waterfall, financial_covenant, springing_lien, \
dip_financing, royalty_rate, purchase_price, break_fee, mfn, clawback, ...)", "value": "the term's value/content as \
stated", "quote": "..."}}],
 "issues": [{{"key": "snake_case legal issue or regulatory event (e.g. hsr_second_request, anti_kickback, \
stark_law, willful_infringement, privilege_waiver, ofac_sanctions, wage_and_hour, ...)", "depth": "analysed if the \
file discusses or decides it substantively, mentioned if only named/listed/flagged", "quote": "..."}}]
}}
Return only the JSON object.

FILE TEXT:
<<<
{text}
>>>"""


CHUNK = 90_000
MIDDLE_PROMPT = """You are cataloguing part of one long file from a law firm DMS (Calderwood & Harkness LLP). This is \
a middle section (characters {start:,}-{end:,} of {total:,}); the beginning and end were catalogued separately.
List the material deal/legal terms and legal issues stated IN THIS SECTION. Every item needs a "quote" copied EXACTLY \
(12-300 characters) from the section; omit anything you cannot quote.

File: {path}
Return ONE JSON object:
{{"terms": [{{"key": "snake_case term name (e.g. mfn, earnout, contingent_value_right, escrow, indemnity_cap, \
non_compete, lock_up, financial_covenant, springing_lien, management_fee_offset, ...)", "value": "as stated", \
"quote": "..."}}],
 "issues": [{{"key": "snake_case legal issue / regulatory event", "depth": "analysed or mentioned", "quote": "..."}}]}}

SECTION TEXT:
<<<
{text}
>>>"""


def extend_long(path: str) -> int:
    """Add terms/issues from the middle of a truncated file (the part the card build did not see). Returns the
    number of grounded items added; idempotent (``_meta.middle_read``)."""
    out = card_path(path)
    card = json.loads(out.read_text())
    meta = card["_meta"]
    if not meta.get("truncated") or meta.get("middle_read"):
        return 0
    text = k0.text(path)
    added = 0
    for start in range(HEAD, len(text) - TAIL, CHUNK):
        end = min(start + CHUNK, len(text) - TAIL)
        part = call_json(MODEL, MIDDLE_PROMPT.format(start=start, end=end, total=len(text), path=path,
                                                     text=text[start:end]), "docs_middle")
        for k in ("terms", "issues"):
            for it in part.get(k) or []:
                if isinstance(it, dict) and grounded(path, str(it.get("quote") or "")):
                    it["from_middle"] = True
                    card.setdefault(k, []).append(it)
                    added += 1
    meta["middle_read"] = True
    meta["middle_items"] = added
    write_json(out, card)
    return added


def card_path(path: str):
    return DOCS / (path + ".json")


def build_one(path: str, matter: str, reground: bool = False) -> dict:
    """Build (or with ``reground``: re-ground from the cached model reply, no new call) one document card."""
    out = card_path(path)
    if out.exists() and not reground:
        return json.loads(out.read_text())
    text = k0.text(path)
    trunc = ""
    if len(text) > HEAD + TAIL:
        trunc = (f"NOTE: the file is long ({len(text):,} characters); you see the first {HEAD:,} and last {TAIL:,} "
                 "characters, joined by [...TRUNCATED...].\n")
        text = text[:HEAD] + "\n[...TRUNCATED...]\n" + text[-TAIL:]
    card = call_json(MODEL, PROMPT.format(path=path, matter=matter, trunc=trunc, text=text), "docs")
    dropped = 0
    for key in QUOTED_LISTS:
        items = card.get(key) or []
        keep = [it for it in items if isinstance(it, dict) and grounded(path, str(it.get("quote") or ""))]
        dropped += len(items) - len(keep)
        card[key] = keep
    if card.get("stage_quote") and not grounded(path, str(card["stage_quote"]), min_len=4):
        card["stage_quote"] = None
    card["_meta"] = {"path": path, "matter": matter, "model": MODEL, "truncated": bool(trunc),
                     "chars": len(k0.text(path)), "dropped_ungrounded": dropped}
    write_json(out, card)
    return card


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--matters", default="")
    ap.add_argument("--reground", action="store_true", help="re-apply grounding to built cards from the cache")
    ap.add_argument("--extend-long", action="store_true", help="read the middle of truncated files (terms/issues)")
    a = ap.parse_args()
    if a.extend_long:
        long = [r["path"] for r in k0.manifest() if card_path(r["path"]).exists()
                and json.loads(card_path(r["path"]).read_text())["_meta"].get("truncated")]
        print(f"{len(long)} truncated files", flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(extend_long, p): p for p in long}
            n = errs = 0
            for i, f in enumerate(as_completed(futs), 1):
                try:
                    n += f.result()
                except Exception as e:
                    errs += 1
                    print(f"ERROR {futs[f]}: {type(e).__name__}: {str(e)[:200]}", flush=True)
                if i % 50 == 0 or i == len(futs):
                    print(f"{i}/{len(futs)} files, {n} items added, {errs} errors", flush=True)
        return
    rows = k0.manifest()
    if a.matters:
        keep = set(a.matters.split(","))
        rows = [r for r in rows if r["matter"] in keep]
    todo = [r for r in rows if card_path(r["path"]).exists() == a.reground]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(rows)} files, {len(todo)} to build", flush=True)
    t0, done, errs = time.time(), 0, 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(build_one, r["path"], r["matter"], a.reground): r["path"] for r in todo}
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:
                errs += 1
                print(f"ERROR {futs[f]}: {type(e).__name__}: {str(e)[:200]}", flush=True)
            if done % 50 == 0 or done == len(todo):
                rate = done / (time.time() - t0)
                print(f"{done}/{len(todo)} errors {errs} {rate * 60:.1f}/min eta "
                      f"{(len(todo) - done) / max(rate, 1e-9) / 60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
