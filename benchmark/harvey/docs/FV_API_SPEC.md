# Firm Verifier API (FV) — spec v0.1 (draft for review)

**Status:** draft; nothing has been built. It is derived from the precision failures in the base-dev15 logs (dev split only, labelled as such). Test (200 tasks) stays untouched until FV is frozen.

## 1. Idea in one paragraph

We give the agent **verifier functions it can call**. There are no hooks at fixed points (the approach). Every function answers one question about one matter or one document, e.g. "is 1038-00007 dismissed?" or "is this file the executed version?". It returns **TRUE / FALSE / UNKNOWN** plus **evidence**: the file path and a verbatim quote. Answers are **precomputed offline** for all 266 matters and 9,288 files by Claude reading the documents. At runtime a call is a deterministic lookup, with no LLM call. The functions and how to use them are declared in the system prompt. The agent decides when to call them; the intended use is "before you list a matter as qualifying, check each condition of the question".

## 2. Why these functions: the failures they target

| Failure seen (dev) | Example | Function |
|---|---|---|
| Related term counted as the asked term | CVR counted as an earnout (1018-00003) | `fv_check(m, "deal_term.earnout", …)` |
| Outcome category | Settled, then stipulated dismissal, counted as "dismissed" | `fv_check(m, "outcome", "dismissed")` |
| Mentioned vs analysed | Memo: AKS "is not a primary focus" | `fv_check(m, "issue.anti_kickback", "analysed")` |
| Draft vs executed | Fee offset only in an LPA first draft | `fv_doc(m, path).stage` |
| Our client's role / relief | Defendant counted as "seeking damages"; counterclaim missed | `fv_check(m, "relief_sought_by_client", "compensatory_damages")` |
| Practice area | ABS / CLO / muni bonds counted as Capital Markets | `fv_check(m, "practice_area", "capital_markets")` |
| Status and dates | Dormant counted as closed in 2023; wrong matter of the same client | `fv_check(m, "status", "closed")`, `fv_check(m, "closed_year", 2023)`, `fv_matter(m)` |

Not covered by FV (separate, harness-level):
- **No deliverable.** Gemini answered in chat in 2 of 15 trials, and the run ended without `response.md`.
- **Context listings on superlatives**, which the judges count as extra matters.

## 3. Runtime API (tools added to LAB's tool list)

All take a `matter_id` like `1003-00001`. Paths are `matter/relpath`, because bare filenames repeat across matters.

### `fv_matter(matter_id)` → matter card
The examples below show the shape only. Values marked `<…>` are placeholders; the outcome "settled, 2023-06-12" for 1038-00007 is verified in a 1038-00007 document ("executed a confidential Settlement Agreement and Mutual Release on June 12, 2023").
```json
{"matter_id": "1038-00007",
 "client": {"name": "Cascade Retail Holdings, Inc.", "aliases": ["Cascade Retail"], "evidence": [E]},
 "description": "Defense of Vantor Holdings v. Cascade Retail Holdings (L.A. Super. Ct.)",
 "practice_areas": [{"value": "litigation_general", "evidence": [E]}],
 "matter_type": {"value": "commercial_litigation", "evidence": [E]},
 "client_role": {"value": "defendant", "evidence": [E]},
 "counterparties": [...],
 "status": {"value": "closed", "date": "<from closing memo>", "evidence": [E]},
 "outcome": {"value": "settled", "date": "2023-06-12", "evidence": [E]},
 "relief_sought_by_client": [{"type": "none", "pleading": null}],
 "deal_terms": [], "issues": [...], "people": {"responsible_partner": ..., "associates": [...]},
 "unknown_fields": ["opened_date"]}
```
`E` = `{"path": "1038-00007/Closing/matter-closing-memo-final-fee-summary.docx", "quote": "<verbatim text from the file>"}`.

### `fv_check(matter_id, field, value)` → verdict
```json
{"verdict": "FALSE", "field": "outcome", "asked": "dismissed", "actual": "settled",
 "evidence": [E], "note": "dismissal by stipulation followed a settlement; the firm records the outcome as settled"}
```
- **TRUE:** the card has the field and it matches `value`.
- **FALSE:** the card has the field with a different value, and evidence supports that value.
- **UNKNOWN:** no evidence for the field. The agent must check the documents itself; UNKNOWN is **never** a reason to drop a matter.

### `fv_doc(matter_id, path)` → document card
```json
{"path": "1004-00002/Transaction Documents/clso-fund-i-lpa-first-draft.docx",
 "doc_type": "limited_partnership_agreement", "stage": "draft", "date": "<from document>",
 "signed": false, "summary": "...", "terms": [{"key": "mgmt_fee_offset", "value": "100% placement fees", "quote": "..."}]}
```

### `fv_check_many(checks: [{matter_id, field, value}, …])`
A batch of `fv_check` calls, so the agent can verify a candidate list in one turn.

## 4. Field vocabulary (closed, listed in the system prompt)

| Field | Values |
|---|---|
| `practice_area` | antitrust, banking_finance, bankruptcy_restructuring, capital_markets, corporate_ma, data_privacy, employment, funds_asset_management, healthcare_life_sciences, ip, litigation_general, real_estate, structured_finance, tax, … (≈15; derived from the corpus in build step B1, not from rubrics) |
| `matter_type` | open string + canonical class |
| `client_role` | plaintiff, defendant, claimant, respondent, buyer, seller, issuer, underwriter, borrower, lender, sponsor_gp, lp_investor, debtor, creditor, advisor, other |
| `status` | open / ongoing, closed, dormant, terminated, withdrawn, abandoned |
| `outcome` | settled, dismissed_voluntary, dismissed_involuntary, judgment_for_client, judgment_against_client, award, closed_transaction, terminated_transaction, cleared, other, none |
| `relief_sought_by_client` | compensatory_damages, declaratory, injunctive, fees, enforcement_of_award, none (with the pleading file) |
| `closed_year`, `opened_year`, `filed_date` | numbers / dates |
| `deal_term.<key>` | executed-document terms: earnout, cvr, escrow_pct, holdback, indemnity_cap, non_compete_months, lock_up_days, greenshoe, underwriting_basis (firm_commitment / best_efforts), mgmt_fee_offset, waterfall (deal_by_deal / whole_fund), covenant_lite, springing_lien, dip_financing, … (open key list per matter; synonyms mapped) |
| `issue.<key>` | e.g. anti_kickback, stark, hsr_second_request, willful_infringement, privilege_clawback, …; value `analysed` or `mentioned` |

`deal_term.*` is read only from **executed or filed** documents; draft-only terms are kept separately as `draft_terms`, so "executed vs proposed" is answerable. Unknown keys return UNKNOWN and list the keys the matter does have.

## 5. Offline build (once, all 266 matters; no task text or rubric used)

| Step | What | Model | Check that must pass |
|---|---|---|---|
| B0 | K0 text = LAB's own `parse-doc` (byte-identical to the agent's `read`) | – | 9,288 files parsed or errors listed |
| B1 | Vocabulary: practice areas, outcome/status sets, term keys from a corpus sample | claude-opus-5.5 | human review (you) |
| B2 | Document cards for every file: type, stage, date, signed, parties, terms + quotes | claude-sonnet-5 | each quote is found verbatim in that file's K0 text, else the field is dropped |
| B3 | Matter cards from the doc cards + key documents (engagement letter, closing/status memos, pleadings, executed agreements) | claude-opus-5.5 | quotes verbatim; ids and folders consistent; a field with no evidence is UNKNOWN |
| B4 | Review: second model re-reads the evidence for a sample, plus every field whose doc cards disagree | claude-sonnet-5 (gpt-5.6-sol is rate-limited now) | agreement rate reported; disagreements become UNKNOWN |
| B5 | Unit tests per function (verifier unit-test style): for each field type, a passing case and a failing case on real matters, written before any agent run | – | all pass |
| B6 | Freeze: hash of the cards + code | – | `runs/FREEZE_fv_v1.json` |

Rough cost: B2 is about 9.3K Sonnet calls (≈134M input tokens). B3 is 266 Opus calls. Matters too big for one call are built from doc cards only.

## 6. Arms and protocol

| Arm | What |
|---|---|
| A0 | Plain LAB agent (done on dev15) |
| V | A0 + FV tools + a system-prompt block declaring them and the usage rule |
| V+D | V + deliverable check at stop (separates the Gemini no-deliverable effect) |
| later: S | Structuring (`fv_find` / list-by-field for recall), as you said, after V |

- **Models:** claude-haiku-5.5, gemini-3.8-flash, gpt-5.6-luna (the last when the OpenAI quota recovers). Effort high for all.
- **Judges:** dual (claude-sonnet-5 + gpt-5.6-sol).
- **Splits:** dev 50 for building and debugging; test 200 run once with the frozen FV. k=1, as in Harvey's post; LAB itself has no repeat setting.

## 7. Open questions for you / the reviewer
1. Is a closed field vocabulary OK? The alternative is free-text `fv_check(m, "has an earnout in the executed agreement")`, but that needs an LLM at runtime.
2. Should V also expose `fv_find(field, value)`, which lists all matters with a field? That fixes recall but is "structuring"; per your note it comes later.
3. Should the deliverable check go into every arm (as a harness fix) or stay a separate arm?
