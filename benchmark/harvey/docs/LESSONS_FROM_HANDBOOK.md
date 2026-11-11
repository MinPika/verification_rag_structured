# Lessons from HANDBOOK.md (vrag_handbook) that constrain vrag_harvey

Sources: `../vrag_handbook/RESULTS.md`, `../vrag_handbook/docs/failure_analysis/` (labels, defects),
`../vrag_handbook/docs/overnight_x10/SUMMARY.md`, `../vrag_handbook/docs/harness_cc/SUMMARY.md`.

## A. Failures of our structuring (KB + drafted plan, arms A1/A2/A3)

| # | Failure | Evidence | Rule for vrag_harvey |
|---|---|---|---|
| S1 | **The offline compiler pre-solved the task and was wrong.** The drafted per-task plan (Opus, seed data) decided outcomes; agents followed wrong decisions. | 69% of the 132 criteria A2 broke vs A0 (plan wrong 82, omits a step 49, harmful extra action 9); 21% of Haiku A2+R residual failures. | The representation describes the corpus and never answers a task. No per-task frontier output at runtime. |
| S2 | **Per-task frontier pre-solving is a confound.** A2's gain came almost entirely from the seeded plan; the KB tools alone (A1) did not beat A0. | A1 text ≈ A0 (Haiku 70.7 vs 71.5); A2 without the plan −9.1 vs A2. | Structure must be task-independent (one corpus build for all 250 tasks). Report any per-task offline work as a separate, labelled arm. |
| S3 | **Compiled "stop" or guard rules halted whole tasks.** | KB stop rules caused 16% of A2 regressions (mostly gpt-6-sol). | Expose facts, not imperatives. No compiled rule may tell the agent to stop. |
| S4 | **KB tools displaced the primary source.** Agents read the compact KB and stopped opening the SOP. | SOP opened in 99% → 62% of Opus trials; Claude 95% → 10–12% with A2. | The KB returns pointers into source files plus short cards, and the agent can always open the original file. Cards must say what they omit. |
| S5 | **Lossy or incorrect extraction.** Template bodies contained procedure text; regex obligations named the wrong columns. | Body-completeness check blocked good runs 8× on dev replay. | Every extracted field keeps a source anchor (file path plus span or quote). Lint grounds each field in the source text deterministically. |
| S6 | **Action/identity resolution bugs made the checks nag about completed work.** | 74 of 111 "open" obligations were already done (DM user ids not resolved, replies without a subject, `file_path` vs `path`). | Normalise identifiers once, in one place, with tests (matter ids `NNNN-NNNNN`, client names and aliases, file paths). |
| S7 | **Fixes chosen from dev failures did not transfer to test** (v5 audit: +4.3 dev, −1.2 / −3.3 test). | RESULTS.md, "What we learned" item 4. | Freeze before test. Evaluate test once per frozen system and label any extra look. |
| S8 | **Fixed checklists anchored strong models.** They treated the checklist as the whole task. | Opus checklist omission accounts for 10 of 21 always-broken criteria. | Any injected list must be marked "partial, from an index". Prefer tools the agent queries over injected lists. |

## B. Failures of the interwhen baseline's verifier method (R)

| # | Failure | Evidence |
|---|---|---|
| V1 | **Coverage gap.** No rule existed for an obligation. | V-GAP 6 (e.g. an ncr_log row that was never required, a missing A-1 email). |
| V2 | **Too loose.** The rule accepted an answer the exact-match grader rejected (extra text appended to an SOP literal; address split across cells). | V-WEAK 23, the largest verifier class. |
| V3 | **Wrong spec.** The rule demanded the wrong thing or blocked a correct action (a cross-reference block on a legitimate DM; 'Status awaits approval' coined a value the register never uses). | V-WRONG 9 (Haiku) + 4 (Opus). |
| V4 | **Redirection.** Feedback pushed the agent to the wrong channel or format. | VERIFIER-REDIRECT 4 (Opus). |
| V5 | **The checklist was treated as complete.** The agent finished every listed item and skipped unlisted ones. | CHECKLIST-OMISSION 10 of 21 (Opus). |
| V6 | **It helps weak models only.** R − A0 is +12 to +23 N−1 for weak models and ≈ 0 or negative for Sonnet, Opus and Argon. For Opus, 30 criteria were fixed and 33 broken. | RESULTS.md "final" and "Opus". |
| V7 | **The verifiers pre-solve the task too.** Expected values (amounts, recipients, rows) were derived offline from seed data by a frontier builder, which makes them per-task oracles. | algo_blind.md Step 1/3; this is the same confound as S2. |
| V8 | **Of the 72 non-rubric residual failures, the verifier fully covered only 9.** The verifiers mostly fix what they cover, and coverage was the limit. | failure analysis. |
| V9 | **Benchmark defects capped every method.** 39 verified rubric defects in 15 tasks; grading ceiling 92–98. | defects.json. |

What worked in R and must be kept:
- One spec drives the checklist, the pre-call check and the stop check.
- Exact expected values go into the feedback.
- Precision before recall: a wrong block is worse than a missing one.
- Fail-open.
- Adaptive stop budget (6 refusals in total, 2 stale).
- Blind builder (never reads tests).
- Validation before freezing: initial state, replay of baseline trajectories, a pair of unit tests per rule, and triage coverage with 0 gaps.
- One scored run.

## C. Process mistakes (ours)
- Metrics: define strict and all-pass once from the grader's own per-criterion output, not from `reward == 1`.
- Infrastructure failures (proxy outages, token-limit crashes, Docker address-pool exhaustion) must be separated from model failures and reported, never silently scored 0 or dropped.
- Model id routing: the OpenHands SDK sends `gpt-5*` to the Responses API, and the interwhen baseline's agent silently falls back to its first model on a wrong id. Always verify the served model id.
- Shell safety: never `rm` with a possibly-empty variable path.
- Harness artefacts matter. Claude Code injected the real date, and OpenHands crashed on 357K-character reads. Record the harness and its limits next to every number.
