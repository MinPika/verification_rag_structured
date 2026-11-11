# 2 · Approach: what we built, how the agent uses it, what it returns, and the gains

## The idea in one paragraph
On the train split the plain agent (A0) loses points in two ways (page 1):
- it **lists near-miss matters**: a draft instead of an executed term, the wrong practice area, a CVR counted as an earnout, a settled case counted as dismissed;
- it **stops searching too early**.

Both are claims about the firm that can be checked against the documents. So we read every document once, offline, into a **verified index** where every value carries a verbatim quote from its file. We then give the agent **verifier functions** over that index (the "code API" design). The agent calls them itself; there are no hooks firing at fixed points. Each call returns TRUE / FALSE / … plus the evidence (file + quote), and it is a deterministic lookup with no LLM at runtime.

**What made it work for Haiku:**
- **Timing.** The verifier is offered **after** the agent has written its answer: at its first `finish` (arm **VLC**).
- **Completeness.** Besides checking each listed matter, the agent can ask "is my list complete?"

## The verifier API (as declared to the agent)

| function | the agent passes | it returns | scope |
|---|---|---|---|
| `fv_check(matter_id, field, value)` | a matter and one condition it believes holds | `verdict` ∈ TRUE / FALSE / SECONDARY / NOT_FOUND / UNKNOWN, `actual` value, `evidence` [{path, quote}], `note` | one condition of one matter |
| `fv_check_many(checks)` | a list of the above | a list of verdicts | a candidate list in one call |
| `fv_matter(matter_id)` | a matter id | client and aliases, description, practice areas (primary first), the firm client's role, status, outcome, dates, relief sought, executed vs draft-only terms, issues analysed vs only mentioned | identity and facts of a matter |
| `fv_doc(path)` | `<matter>/<folder>/<file>` | type, date, **stage** (draft / redline / execution_version / executed / filed / final / unsigned), signed, terms, issues | one file |
| `fv_check_complete(conditions, matters)` | the question's conditions as fields + its current answer list | index matches **missing** from the list, listed matters the index **contradicts**, possible matches with unknown fields | the claim "this list is complete" |

**Fields:**
- `practice_area`: 24 canonical groups; TRUE only for the matter's primary group, SECONDARY otherwise.
- `client_role`: 33 values; "plaintiff" also covers counterclaim-plaintiff and claimant.
- `status`: open, closed, dormant, terminated, withdrawn, …
- `outcome`: settled, dismissed_voluntary, transaction_closed, regulatory_clearance, …; "dismissed" covers both dismissal kinds.
- `closed_year`, `opened_year`.
- `relief_sought_by_client`.
- `term.<key>`: 318 canonical deal/legal terms. TRUE only if found in an **executed or filed** document; FALSE "only in drafts" otherwise.
- `issue.<key>`: 311 canonical issues, valued `analysed` or `mentioned`.

**Verdict semantics:**
- **UNKNOWN** means the index has no evidence. It is never a reason to drop a matter.
- An unrecognised key or value always gives UNKNOWN, never NOT_FOUND.

## How the agent uses it (arm VLC)
1. The agent works exactly like the plain LAB agent (bash/read/grep/glob/write/edit), with no verifier visible, and writes `response.md`.
2. Its first `finish` is refused once. The harness adds the five FV tools to the live tool list and tells the agent:
   - verify every matter in the answer against the question's conditions;
   - call `fv_check_complete` with the question's conditions and the answer list;
   - open the documents of any missing or contradicted matter before changing the answer, because the index can be wrong.
3. The agent edits `response.md` and calls `finish` again, which goes through.

## Example A (train, task 067: "which Healthcare & Life Sciences matters raised Stark or Anti-Kickback issues?"): what the agent passes and what comes back
After 36 turns of normal search the agent calls `finish` and is asked to verify. It then sends one batch:
```json
fv_check_many({"checks":[
 {"matter_id":"1010-00003","field":"practice_area","value":"healthcare"},
 {"matter_id":"1010-00003","field":"issue.stark_law","value":"analysed"},
 {"matter_id":"1013-00004","field":"issue.anti_kickback","value":"analysed"},
 {"matter_id":"1037-00002","field":"issue.anti_kickback","value":"analysed"}, ...]})
```
Returned (abridged, real):
```json
{"matter_id":"1010-00003","verdict":"TRUE","field":"practice_area","asked":"healthcare_life_sciences",
 "actual":["healthcare_life_sciences","regulatory"],
 "evidence":[{"path":"1010-00003/Engagement & Administration/engagement-letter.docx",
   "quote":"Ms. Calloway leads the Healthcare & Life Sciences practice group in the Firm's Boston office."}],
 "note":"primary practice area of the matter"}
{"matter_id":"1013-00004","verdict":"FALSE","field":"issue.anti_kickback","asked":"analysed","actual":"mentioned",
 "evidence":[{"path":"1013-00004/Memos & Analyses/larkfield-heor-review-memo.docx",
   "quote":"must be structured to comply with the federal AKS, 42 U.S.C. § 1320a-7b(b), and the Stark Law, ..."}],
 "note":"only mentioned/flagged in this matter, not analysed"}
{"matter_id":"1037-00002","verdict":"NOT_FOUND", ...}
```
Then the completeness check:
```json
fv_check_complete({"conditions":[{"field":"practice_area","value":"healthcare"},
                                 {"field":"issue.stark_law","value":"analysed"}],
                   "matters":["1010-00003","1018-00004","1037-00003"]})
→ {"verdict":"FALSE","n_index_matches":1,"missing_from_your_list":[],
   "listed_but_contradicted":[{"matter_id":"1018-00004","verdicts":{"practice_area":"TRUE","issue.stark_law":"FALSE"}}, ...],
   "note":"Index matches are leads ... open each missing matter's documents and confirm before adding it"}
```
The agent keeps 1013-00004 and 1037-00002 out of the qualifying list and relabels Stark as "mentioned only" for two matters. Its score did not change here, because this trial's pre-gate answer already passed. In task 070, a related count question, the same kind of check removed five non-qualifying matters and fixed the precision criterion (Cases P6).

**How the index knew this** (offline, before any task was seen):
- **Document card** (claude-sonnet-5 read the full memo): `larkfield-heor-review-memo.docx` → `doc_type: legal_memo`, `stage: draft`, `issues: [{key: anti_kickback, depth: mentioned, quote: "must be structured to comply with the federal AKS ..."}]`. The quote was checked verbatim against the file text before it was kept.
- **Vocabulary:** the raw key `anti_kickback` and its variants (`anti_kickback_statute`, `state_anti_kickback_law`, …) map to canonical `anti_kickback`.
- **Matter card:** for 1013-00004, issues are aggregated over all 30+ document cards. No document *analyses* AKS, so depth = `mentioned`. A deterministic rule, no LLM.
- **Runtime:** `fv_check` maps "anti_kickback" → canonical key, finds depth `mentioned` ≠ asked `analysed` → FALSE plus the stored quote, in about 0.1 ms.

## Example B (train, task 044 "largest completed capital-markets offering and its lead underwriter"): a completeness lead fixes the answer
- **Before verification**, the answer named Verimark (1021-00002). Both judges failed it.
- At the gate the agent called:
  ```
  fv_check_complete([practice_area=capital_markets, status=closed, outcome=transaction_closed], [its candidates])
  → FALSE, 10 index matches; missing from your list: 1010-00002, 1013-00002, 1014-00001, 1016-00003, ...
  ```
- It then checked 1016-00003 (`status closed` TRUE, quote from `closing-checklist.xlsx`: "Notes issued; gross proceeds $837,250,000") and **opened the closing binder itself**.
- It rewrote the answer: Dunmore Energy 1016-00003, $850M notes, lead initial purchaser Ridgeline Capital Markets, evidence `Closing/closing-binder-toc.docx`. Both judges passed it.

**Where the index got this:** the matter card's outcome `transaction_closed` (2025-05-15) with the quote from `closing-binder-toc.docx`, and practice area `capital_markets` with the quote "Practice Group: Capital Markets" from `matter-opening-form.docx`. Both were extracted offline and grounded verbatim.

## Example C (a failure we keep visible): a correct matter dropped on a wrong FALSE
Task 036, trial t1 ("offerings with a lock-up under 90 days"):
- `fv_check(1017-00001, term.lock_up, 60_days)` returned FALSE, because the 60-day lock-up was found only in `closing-checklist.xlsx`, which the index does not treat as an executed document.
- The agent dropped the matter, which was correct, and the criterion failed.

Fourteen such regressions on train are listed in the Cases tab, against 63 criteria fixed.

## What it gained (Haiku; full tables with CIs in tab 3)

| comparison | criterion pass | all-pass | precision criterion | required-matter recall |
|---|---|---|---|---|
| **Train, same trajectory before → after verification (81 trials)** | **+11.7** * | **+12.3** * | **+11.9** * | **+9.5** * |
| Train, A0 vs VLC, 2 trials × 50 tasks | **+6.5** * | **+9.5** * | **+13.8** * | +5.3 |
| **Test, same trajectory before → after (101 trials, 2 per task)** | **+6.4** * | **+4.5** * | **+10.8** * | **+4.5** * |
| Test, A0 vs VLC, 2 trials × 60 tasks | +2.9 | +1.2 | +5.6 | +4.1 |

Points; * = 95% CI excludes 0.

**Cost:**
- VLC adds about 3–4 turns: +6% wall clock on train (627 s vs 591 s) and +4% on test (669 s vs 645 s). Prompt tokens rise about 10% on train and 37% on test (a few test trials ran long).
- The run-vs-run gain on test (+2.9, not significant) is smaller than the same-trajectory gain (+6.4, significant). The run-vs-run number also contains search variance between independent runs and the ~16% of trials where the gate never fired.
- Each verifier call takes ~0.1 ms (completeness check ~0.25 s), with no LLM at runtime.

## What did not work (and why it matters)
- **Verifiers available from the start (V1/V2/VC).** Precision rose (+22 points for V1), but Haiku cut its search in half (14 turns vs 31) and missed more matters. Net ≤ 0.
- **Verify late without the completeness check (VL).** Answers barely change (+1.5 within trajectory). The checks only remove matters, and most errors are missed matters.
