# vrag_harvey: what we did, why, and what it changed (Haiku 5.5, Harvey LAB firm-knowledge)

_Living document; numbers are filled in as runs finish. Every number links to a run in the Trials tab._

## 1. Setup
- **Benchmark:** 250 firm-knowledge tasks over one synthetic law firm (266 matters, 9,288 files).
- **Harness:** LAB's own sandbox, tools, prompt and loop, pinned at `ba363f5`. The model goes through the Copilot proxy, which is patched so effort and the full context window are honoured.
- **Judges:** dual, claude-sonnet-5 + gpt-5.6-sol. Metrics are the criterion pass rate and all-pass (0.5 when the judges disagree).
- **Split:** dev 50 / test 200, stratified by question type (`splits/`).
- **Model:** Haiku only for this phase, at effort high.

## 2. Baseline failures (A0): why we built verifiers
On dev15, Haiku usually **found** the right matters but **also listed near-misses**. Precision failed in 8 of the 12 tasks that have a precision criterion. The near-misses fall into six classes:
- a related term instead of the asked one (CVR vs earnout);
- outcome category (settled vs dismissed);
- mentioned vs analysed;
- draft vs executed;
- whose side the firm is on;
- practice area or matter identity.

See *Precision analysis*.

## 3. The verifier API (arm V)
the code-API design: verifier functions the agent calls, declared in the system prompt, with no hooks.
- `fv_check(matter, field, value)` and `fv_check_many` return TRUE / FALSE / NOT_FOUND / UNKNOWN plus evidence (path + verbatim quote).
- `fv_matter` returns the matter card; `fv_doc` returns a document card (stage, terms).

**Offline build** (once, task-independent; no task or rubric text used):
1. **K0:** every file converted with LAB's own `parse-doc`, so the text is identical to what the agent reads (9,288 files, 0 errors).
2. **Document cards:** claude-sonnet-5, one per file. Every extracted item needs a verbatim quote found in the file, or it is dropped.
3. **Vocabulary:** claude-opus-5.5 groups the raw labels into canonical practice areas, terms and issues.
4. **Matter cards:** claude-opus-5.5, from the document cards. Evidence must be a file of that matter with a verbatim quote; otherwise the value is UNKNOWN. Terms and issues are aggregated deterministically, with executed and draft documents kept apart.

**Runtime:** deterministic lookups with no LLM. A key or value that isn't recognised gives UNKNOWN, never NOT_FOUND, so a vocabulary gap can't make the agent drop a correct matter.

**Checks before any agent run:**
- unit tests: a passing and a failing case per field type (`tests/test_fv_api.py`);
- call test: Haiku given the V prompt on all 50 dev questions (`logs/calltest/`).

## 4. How the design changed on dev (details: *Iterations*)

| Arm | What the agent gets | What happened on dev 50 |
|---|---|---|
| A0 | LAB as is | 0.67 criterion, 0.27 all-pass; precision criterion passes only 0.51 |
| V1 | FV tools from the start | precision +0.22 (significant), but Haiku **searched half as much** (14 vs 31 turns): recall −0.14 |
| V2 | V1 + verifier fixes + "search first" prompt | net ≈ 0; still ~16 turns |
| VC | V2 + completeness check | Haiku used the index leads instead of searching (12 turns); 286 of 449 leads were wrong, from loose conditions |
| **VL** | **A0 until the first `finish`**; then the FV tools appear and Haiku must verify its answer before finishing | effort = A0; see Results |
| **VLC** | VL + completeness check at the gate | see Results |

Lesson: for Haiku, **when** the verifier is available matters as much as what it checks. Available from the start, it replaces search. Offered once at the end, it checks an answer that was built by a full search.

## 5. Results (details in *Results*)
- **VLC (verify late + completeness check)** is the version that works for Haiku:
  - dev, k=2 vs A0: criterion **+6.5** points, all-pass **+9.5**, precision **+13.8**, all significant;
  - the same trajectories graded before vs after verification: criterion **+5.5** / precision **+11.2** on test, and **+11.7** / **+11.9** on dev, all significant.
- **Verification without the completeness check** (VL) barely changes answers (+1 point within trial).
- **Verifiers offered from the start** make Haiku search half as much.

## 6. What still fails
1. **Search recall in the A0 phase.** The largest source of misses: big enumerations (e.g. 84 OFAC matters) vary a lot from run to run.
2. **Completeness leads can add a matter without its proof document.** Evidence-document failures rose on dev.
3. **Vocabulary gaps.** A key the index cannot resolve gives UNKNOWN, and Haiku sometimes drops the matter anyway.
4. **The reference taxonomy is unstated.** Primary practice area, and dismissed vs settled, are inferred by the index; mostly right, sometimes not.
5. **Benchmark noise.** Two identical A0 runs differ by ±0.1 on 15 tasks, so every claim here uses k=2 or a within-trial pairing.
