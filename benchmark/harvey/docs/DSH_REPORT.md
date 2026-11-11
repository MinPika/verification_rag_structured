# Firm Verifier in the DSH harness: final result (Harvey LAB firm-knowledge, AHE split)

**One system, frozen before test; test run as two independent trials (k=2) of that same frozen system.** Agent: claude-haiku-5.5 (reasoning effort high) in
the DSH harness (`dsh-bench-harness`, our branch `vrag/harvey-fv`). Split: AHE
`splits-firm-knowledge-c34-80-20-70.json` (train 80 / validation 20 / test 70; the other 80 of the 250 tasks are in
no split and were run afterwards as a second held-out set, §1). System: **verify late + completeness
check** (VLC) with Firm Verifier index **v3-dsh** (freeze `runs/FREEZE_fv_v3-dsh.json`, digest `325ef1f5…`, frozen
2026-11-10 22:20 UTC before any test trial; source snapshot `runs/freeze_src/v3-dsh/`). The working tree now holds
exactly this behaviour as `v3-dsh-final` (`runs/FREEZE_fv_v3-dsh-final.json`). It has the same index data and the
same verifier, gate and asset files; only the FV server's health/pinning code and the analysis tooling differ.
`v3-dsh-final-r1` is the same again with one registry label renamed (the Haiku model config's `display_name`, never
sent to the model) for the push to `dsh-bench-harness`; it is the tag to reproduce with.

## 1. Result

Each trial is plain DSH until the agent ends its turn. At that point the `fv_*` verifier tools appear and the agent is
asked once to verify its answer. The answer at the gate (**before**) *is* the plain-DSH answer of that trajectory, and
the final answer is **after**. Same trajectory, same search, same judges, so the difference is what verification did.
Scores average two judges (claude-sonnet-5, gpt-5.6-sol).

**Test, 70 tasks (k=1):**

| metric | plain DSH | + verification | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 60.3 | **70.7** | **+10.4** [+6.0, +15.4] |
| all-pass (task fully correct) | 23.6 | **35.7** | **+12.1** [+5.0, +20.0] |
| precision criteria | 41.3 | 58.0 | +16.7 [+7.2, +26.8] |
| required-matter recall | 69.6 | 79.8 | +10.2 [+5.4, +16.1] |

**Test, the 53 tasks never seen during design** (17 test tasks were in my earlier LAB dev set):
criterion 59.4 → 68.6 (**+9.3** [+4.8, +14.7]), all-pass 22.6 → 32.1 (**+9.4** [+1.9, +17.9]), precision +12.3,
recall +10.5.

**Train, 80 tasks:** criterion 55.6 → 67.0 (+11.4 [+6.4, +17.0]), all-pass 20.6 → 28.1 (+7.5), precision +11.7,
recall +10.7. **Validation, 20 tasks:** criterion 54.6 → 69.2 (+14.5 [+5.5, +26.7]), all-pass 27.5 → 35.0.

Each judge on its own (test): claude-sonnet-5 59.5 → 70.5 criterion, 24.3 → 38.6 all-pass; gpt-5.6-sol
61.1 → 70.8, 22.9 → 32.9. The gain does not depend on one judge.

**Test, second independent trial (k=2), same frozen system:** criterion 60.1 → 72.9 (**+12.8** [+7.8, +18.7]),
all-pass 27.9 → 37.1 (**+9.3** [+2.1, +17.1]), precision +13.8, recall +13.8. Judge noise 3 of 759 criteria;
83 fixed vs 8 broken (p = 8e-17). Clean 53: criterion +12.6 [+6.5, +19.2], all-pass +8.5.

**Test, both trials pooled** (140 trials; each task's two deltas are averaged and the CI bootstraps over the 70
tasks, `vharvey.pregate.pooled`):

| metric | plain DSH | + verification | Δ points [95% CI] | clean 53 tasks: Δ [95% CI] |
|---|---|---|---|---|
| criterion pass | 60.2 | **71.8** | **+11.6** [+7.7, +15.9] | +10.9 [+6.6, +15.8] |
| all-pass | 25.7 | **36.4** | **+10.7** [+4.6, +17.1] | +9.0 [+1.9, +16.5] |
| precision criteria | 47.1 | 62.3 | +15.2 [+7.2, +23.6] | +11.8 [+2.8, +21.2] |
| required-matter recall | 68.6 | 80.6 | +12.0 [+7.6, +16.8] | +11.8 [+6.7, +17.6] |

**Beyond the split: the 80 tasks the AHE split leaves out, and all 250.** The split assigns only 170 of the 250
tasks. The other 80 were run afterwards with the same frozen system (`U-late-k1`, `U-late-k2`; two trials;
`vharvey.dsh specs --split unused`). Nothing was changed or tuned after seeing them. 10 of them were in my earlier LAB
dev set, so 70 had never been seen.

| tasks (two trials each unless noted; pooled per task) | criterion pass | all-pass | precision | recall |
|---|---|---|---|---|
| the 80 outside the split | 59.1 → 69.2, **+10.1** [+6.5, +13.7] | 20.9 → 27.5, **+6.6** [+2.8, +10.3] | +5.2 [−1.3, +11.4] | +11.0 [+6.2, +16.0] |
| the 70 of those never seen | +9.7 [+6.0, +13.7] | +6.8 [+2.9, +11.1] | +5.2 [−2.2, +12.3] | +9.9 [+5.0, +15.4] |
| **all held-out: test 70 + outside 80** (150 tasks, 300 trials) | 59.6 → **70.4**, **+10.8** [+8.0, +13.7] | 23.2 → **31.7**, **+8.5** [+5.0, +12.3] | +9.9 [+4.8, +15.2] | +11.5 [+8.2, +15.0] |
| held-out and never seen in any design (123 tasks) | 59.7 → 70.0, +10.2 [+7.3, +13.1] | 21.7 → 29.5, +7.7 [+3.9, +11.8] | +8.1 [+2.3, +14.0] | +10.7 [+7.1, +14.5] |
| *all 250, descriptive* (train and validation k=1, the rest k=2) | 57.9 → 69.2, +11.3 | 22.7 → 30.8, +8.1 | +11.4 | +11.4 |

- The two trials on the 80 differ in shape but agree in direction. Trial 1: criterion +13.1, all-pass +5.6,
  precision +2.6, recall +14.9. Trial 2: +7.1, +7.5, +7.8, +7.2.
- Trial 1's extra change comes from a few large "list every…" tasks: task 204 alone has 53 changed criteria, 52 of
  them fixed. There the agent also took more completeness leads, which raised recall but added 7 matters outside the
  rubric's reference list. That is the same failure as §3 drop 3, and why precision on these 80 is not significant.
- Judge noise on the 80: 6 of 888 criteria per regrade (0.7%). Fixed vs broken: 178 vs 19 (trial 1), 88 vs 21
  (trial 2). Details: `DSH_UNUSED_K1_ANALYSIS.md`, `DSH_UNUSED_K2_ANALYSIS.md`.
- The all-250 row mixes tasks used for analysis (train) and for choosing between versions (validation). It is
  descriptive only; the held-out rows are the clean result.

**Cost:** verification adds about 55 s to a ~740 s trajectory (+7–8%) and about 5 model steps to ~22 (both test
trials).

**Leaderboard reference (not like-for-like):** gpt-5.6-sol high is listed at 36% all-pass / 79.1% criterion on LAB
firm-knowledge (all 250 tasks). Our verified Haiku reaches 30.8% all-pass / 69.2% criterion over all 250 tasks
(descriptive, above) and 36.4% / 71.8% on the 70 AHE test tasks. The model and judges differ, so this is context, not
a claim. We could not run sol as the agent: on this Copilot account every OpenAI-family model is rejected (HTTP 503
`model_overloaded`) once a request exceeds ~24K tokens (E26 in `ERRORS.md`).

## 2. Is the gain real or noise?

- **Search noise:** none. Before and after come from the same trajectory.
- **Judge noise, measured:** grading the identical before-answers twice flips 4 of 759 criteria on test (0.5%), 3 of
  796 on train (0.4%). Verification changed 108 criteria on test and 128 on train.
- **Direction:** test 87 fixed vs 21 broken (sign test p = 1e-10), test k=2 83 vs 8 (p = 8e-17); train 110 vs 18
  (p = 3e-17); the 80 outside the split 178 vs 19 and 88 vs 21. Noise would flip both ways equally.

## 3. Where the gain comes from (did the agent call the verifier for it?)

Every changed criterion is linked to the verifier calls made for that matter in that trial
(`vharvey/dsh_analysis.py`; full tables in `DSH_TEST_ANALYSIS.md`, `DSH_TEST_K2_ANALYSIS.md`,
`DSH_TRAIN_ANALYSIS.md`). The table shows the first test trial and train; the second test trial has the same
pattern (precision 12 fixed / 2 broken by leads outside the reference set; recall 47 fixed via the verifier,
5 broken).

| | test | train |
|---|---|---|
| **Precision fixed**: a wrong matter was checked (FALSE / SECONDARY / contradicted), then removed or relabelled | 14 | 11 |
| Precision broken: a completeness lead added a matter outside the reference set | 2 | 1 |
| Precision broken: rewrite without a verifier lead | 0 | 1 |
| **Recall fixed via completeness leads** (matter or document confirmed and added) | 58 | 72 |
| Recall fixed: checked, then added or cited | 5 | 16 |
| Recall fixed without a verifier call on that matter | 1 | 0 |
| Recall broken: correct matter dropped after a non-TRUE verdict | 2 | 16 |
| Recall broken: dropped during the rewrite despite TRUE verdicts | 12 | 0 |
| Recall broken: dropped during the rewrite, no verifier call on that matter | 1 | 0 |
| Number/other criteria fixed / broken (answer changed after verifier calls) | 9 / 4 | 11 / 0 |

- **Precision gains are verifier-driven.** In every precision fix the removed matter had been checked by the
  verifier in that trial and got a non-TRUE verdict.
- **Recall gains come from the completeness check.** `fv_check_complete` returns matters that meet the question's
  conditions but are missing from the answer, each with a file path and quote. The agent opens the file and adds the
  matter (58 of 64 test recall fixes).
- **Two test examples** (both from the 53 clean tasks; open them in the Trials tab, run `D-late-test`):
  - *Precision, task 248* ("our most recent white collar matter where we responded to a subpoena or CID").
    1. Plain DSH answered Dunmore Energy 1016-00001, an antitrust CID.
    2. At the gate the agent called `fv_check_many([{1016-00001, practice_area, white_collar}, …])` and got
       **FALSE**, actual `antitrust_competition`, with the engagement letter's quote "...the full resources of our
       Antitrust & Competition practice group...".
    3. `fv_check_complete([practice_area=white_collar_investigations], …)` listed the white-collar matters with
       evidence. The agent opened Torchlight Mining 1039-00005, found the SEC subpoena production of 2025-04-14 and
       rewrote the answer.
    4. Criteria went from 1/3 to **3/3** (all-pass).
  - *Recall, task 001* ("every antitrust matter where we drew an HSR second request, with the documents").
    1. Plain DSH missed Cascade Retail 1038-00001.
    2. `fv_check_complete([practice_area=antitrust, issue.second_request=analysed], [5 listed matters])` returned it
       as missing, with a quote per condition (litigation-hold memo: "a partner in the Firm's Antitrust &
       Competition Practice Group"; plus the second-request document).
    3. The agent opened the files and added the matter with `joint-status-report.docx` and
       `letter-ftc-meet-and-confer.docx`.
    4. Criteria went from 4/7 to 6/7 (Sonnet judge).
- **Why drops happen.** The agent called the verifier in every trial, and only one dropped matter (test) had not
  been checked, so drops are not about the tools going uncalled:
  1. *Correct matter dropped after a literally-true FALSE* (train 16). The commonest case: the question says "closed
     deal" and `status=closed` is FALSE because the matter **file** stays open for post-closing work, although the
     **deal** closed (`outcome=transaction_closed`). Other cases are index categories narrower than the rubric
     (relief type, a term recorded only in drafts) or NOT_FOUND/UNKNOWN taken as "no".
  2. *Broadness warning misfire* (test 186, 10 criteria in the first trial; not in the second). The check warns when more than 25 matters match, even when
     the conditions are the question's own (`closed_year=2023` matched 48). The agent then hedged and put deal
     closings in a separate "confirm scope" section, which the judges did not count (E22).
  3. *Completeness leads outside the reference set* (2 test). Rubric populations are sometimes narrower than the
     literal condition.

## 4. the harness question: do the tools replace search?

Yes, when they are available from the start, in DSH as in LAB. So this is not an artefact of the LAB harness. On the
same 20 train tasks:

| | plain DSH (before the gate) | tools from the start |
|---|---|---|
| model steps | 20.0 | 10.5 |
| search calls (bash/grep/glob/read) | 19.1 | 7.8 |
| distinct matters named in search calls | 17.4 | 8.9 |
| first verifier call at step | – | 1.4 (after 0.7 search calls) |
| distinct matters named in verifier calls | – | 12.4 |

With tools from the start, the agent queries the index almost immediately and searches the documents half as
much. Scores on these 20 tasks: start 67.5 criterion / 63.2 precision in 350 s, verify-late 69.0 / 42.1 in 921 s.
That is a single trial with its own trajectories, so it is not evidence either way. We keep **verify late**: the
search stays exactly the harness's own, and the verifier can only add checks on top. That is also what makes the
before/after measurement clean.

## 5. What was fixed for DSH (from the LAB-harness VLC failures)

| LAB VLC failure | In DSH |
|---|---|
| Gate never fired when the agent ended without calling `finish` (2–5 trials per run, E15) | DSH has no finish tool. The plugin `fv-gate.mjs` hooks `agent/turn-stopping` and fires once on the root agent: 170/170 trials. |
| Completeness leads had no evidence, so matters were added without the proof document | Each lead carries {condition, path, quote} (v3). Document criteria fixed by leads: test 17, train 24. |
| `closed_year` missed deals with a closing outcome but no closing date | Falls back to the status date (closed statuses) and then the final-outcome date; never for open/dormant/on_hold (v3) |
| Very broad completeness queries flooded the agent | Warning above 25 matches (v3). Its wording misfires, see §3 (E22). |

## 6. A fix that did not validate (v4, not adopted)

Built on the train failures alone:
1. A `status`/`outcome` cross-note: "the matter file is open, but its outcome is transaction_closed on <date>; if the
   question means the deal closed, check `outcome`."
2. A rule that a FALSE justifies dropping a matter only if its quote addresses the question's condition.

It ran from a separate frozen build (`FREEZE_fv_v4-dsh.json`, server :3151, arm `late-v4`), so the running test was
untouched. Its code, arm patch, assets and unit test are kept in `runs/freeze_src/v4-dsh/`; the working tree holds
the adopted v3 behaviour. The decision rule, fixed before the runs: adopt v4 only if, on validation, it keeps the gain and breaks
fewer criteria.

| validation 20 | criterion Δ | all-pass Δ | precision Δ | recall Δ | fixed / broken |
|---|---|---|---|---|---|
| v3-dsh | +14.5 [+5.5, +26.7] | +7.5 | +22.2 | +13.8 | 28 / 3 |
| v4 | +8.6 [−0.6, +17.5] | +12.5 | +22.2 | +4.4 | 29 / 3 |

On the 9 train tasks v3 had broken, v4 no longer dropped the closed deals (190 and 195 kept all 4). But on
validation it broke as many criteria as v3 and gained less, so it was **not adopted** and was never run on test.

## 7. Remaining failures (next work, to be developed on train/validation only)

1. Broadness warning wording (E22): report "N matters match; these are the population if they are the question's
   conditions" instead of asserting the conditions are too broad. *Observed on test, so it needs a train/validation
   check first.*
2. File-status vs deal-status: v4's note is right in substance, but its effect was not measurable on 20 validation
   tasks. It needs more validation trials (k=2–3) before adoption.
3. Rubric populations narrower than the literal condition (completeness leads outside the reference set): an
   answer-format issue more than a verifier one.
4. The plain-DSH baseline itself: ~1.4 bash timeouts per trial under CPU contention (E21) and long enumeration tasks
   where search stops early.

## 8. Reproduce

```bash
# services: SSE facade :3142 -> Copilot proxy :3141; FV server (v3-dsh) :3150
.venv/bin/python -m vharvey.sse_facade &
FV_FREEZE_TAG=v3-dsh-final-r1 .venv/bin/python -m vharvey.fv.server &   # refuses to start if anything differs
.venv/bin/python -m vharvey.dsh specs D-late-test --split test --arm late
.venv/bin/python -m vharvey.dsh run D-late-test --conc 12
.venv/bin/python -m vharvey.dsh grade D-late-test --workers 8
.venv/bin/python -m vharvey.dsh_analysis D-late-test --regrade --also-without splits/dev.txt \
    --label "AHE test split, frozen v3-dsh" --out docs/DSH_TEST_ANALYSIS.md
```

Runs: `runs/dsh/<RUN>/` (DSH layout) and LAB-style views in `runs/labroot/results/<RUN>` and `<RUN>-pregate`. All
trials are browsable in the dashboard (Trials tab).
