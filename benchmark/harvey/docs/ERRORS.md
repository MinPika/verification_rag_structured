# base-dev15: errors and issues (run level)

| # | Issue | Whose | Trials hit | Status |
|---|---|---|---|---|
| E1 | **Our 240K prompt cap.** Set before the proxy patch; it ended trials as "context overflow". | **ours (harness)** | luna 10, Gemini 9 | Fixed: cap = model window − 5%. Trials moved to `runs/quarantine/base-dev15-cap240k/`, not counted. Gemini rerun done (15/15 valid). |
| E2 | **OpenAI quota on the Copilot account.** gpt-5.6-luna, gpt-5.6-sol and gpt-6-luna reject prompts above ~16–24K tokens with "Upstream provider rate limit hit". During the morning baseline luna accepted 236K. Probed at 11:50 and 19:30; still limited. | Copilot service | luna 10 pending | **Blocked.** luna's 10 trials wait. The gpt-5.6-sol judge still works on small judge prompts; watch for grading errors. |
| E3 | **No deliverable.** The agent wrote the full answer as its final chat message, never called `write`, and the loop ended (`no_tool_calls`). LAB grades only `output/`, so the run scores ~0. | model behaviour (Gemini) | Gemini 152, 165 (2/15) | Recorded. Option: a deliverable check at stop (spec §6, arm V+D). |
| E4 | **Judges split on "context" listings.** The correct single answer plus a comparison table of older matters: one judge says the extra matters are asserted, the other says they are context. | grader/format | Haiku 165, luna 165, Gemini 161 | Recorded; an answer-format rule, not a verifier. |
| E5 | **Benchmark defect.** Task 189 C-037: the precision criterion omits its 37-entry allowed set. | Harvey dataset | all 189 trials | `docs/BENCHMARK_DEFECTS.md` |
| E6 | **Window reload killed the K0 corpus build** (8,673 files parsed, no manifest written). | ours | – | K0 is now resumable (`parse_status.jsonl`) and rerunning. |
| E7 | **Unpatched proxy ignored reasoning effort and cut long prompts.** | proxy | all runs before 10:00 (smoke only) | Proxy patched (backup in `docs/proxy_patch/`); verified with `vharvey.probe`. |

## Model-level failure classes (from the trial analyses)

| Class | Haiku | Gemini | Example |
|---|---|---|---|
| Precision: near-miss attribute (term, outcome, mention, stage, role, practice area, status) | 8 tasks | 5 tasks | 153 CVR as earnout; 106 settled as dismissed |
| Recall: large enumerations | 186 (35/50 missed), 189 (7/35) | 125 (8/14), 186 (13/50) | |
| No deliverable | 0 | 2 | Gemini 152, 165 |
| Context listing on a superlative | 1 | 1 | 165, 161 |

## Overnight runs (2026-11-09/10: FV build, V1–VLC, test 60)

| # | Issue | Whose | Effect | Handling |
|---|---|---|---|---|
| E8 | Docker sandbox start exceeded LAB's 30 s limit when ~14 containers started at once | infra | 2 V1 and 2 VC trials | Logged as `infra_error`, rerun by the resume pass; never scored |
| E9 | Host CPU saturated (load ≈ 24/24) by agents scanning the 600 MB corpus | infra | Trials took 1.5–2× longer; no failures | Ran at most about 20 agents at once |
| E10 | The vocabulary step as one Opus call (25K raw labels) hit the 15-minute timeout repeatedly | ours | 30 min lost | Split into propose (Opus) + map (Sonnet, parallel batches) |
| E11 | Quote normaliser turned pandoc's `\"` into a space, so 25% of extracted items failed grounding | ours | Cards lost items | Fixed; re-grounded from the cache with no new calls; drop rate 5.4% |
| E12 | Card build read only the first 90K + last 30K characters of 728 long files | ours (design) | Missed terms (e.g. an MFN clause mid-agreement) | Middle-section pass: +18,596 grounded items |
| E13 | Execution copies with blank signature lines were labelled "unsigned" | ours | Executed terms classed as draft-only | Filename rule (execution / executed / signed / conformed) |
| E14 | 2 emails got "Model declined to respond" from claude-sonnet-5 | provider | No card for 2 of 9,288 files | Recorded; those matters' cards use the other files |
| E15 | Gate never fired when the agent ended without calling `finish` | design | 2–5 trials per VL/VLC run behaved as A0 | Counted in the arm (intention to treat); excluded from the within-trial analysis |
| E16 | Some vocabulary synonyms are wrong (e.g. `frand_licensing` → `mfn`) | ours (Sonnet mapping) | Possible wrong matches | Listed for human review |
| E17 | The OpenAI models on the Copilot account still reject prompts over ~20K tokens | Copilot | luna not run; gpt-5.6-sol judge unaffected (small prompts) | Haiku-only phase as agreed |

## DSH harness port (2026-11-10/11: dsh-bench-harness branch `vrag/harvey-fv`, AHE split)

| # | Issue | Whose | Effect | Handling |
|---|---|---|---|---|
| E18 | gpt-5.6-sol (the leaderboard model) and luna still reject prompts over ~20K tokens on the Copilot account (12K passes, 20K fails); no CAO endpoint on this host | Copilot | Cannot run sol as the agent | Agent = claude-haiku-5.5, effort high (as agreed). sol still works as a judge |
| E19 | DSH injects a "Current runtime context" user message at step 0; the transcript converter labelled it like the gate's verification request, so the gate looked like step 0 and the before-gate search profile read 0 | ours (analysis) | Wrong search-profile table only; scores unaffected | Separate labels (`runtime context (DSH)`, `verification request (fv-gate)`); the gate is found by the gate message's prefix |
| E20 | Agents copy read-only corpus files into `output/`; rebuilding a view could not overwrite them | ours | View rebuild crashed on task 081 | Copy contents only, never the mode |
| E21 | 60 s bash timeouts under CPU contention (~1.4 per trial in train and test) | infra | Lowers the absolute baseline; before and after share the trajectory, so the verification delta is unaffected | Kept concurrency ≤ 16 agents; recorded |
| E22 | `fv_check_complete` warns "conditions are probably broader than the question" whenever more than 25 matters match, even when the conditions are the question's own (task 186, `closed_year=2023`, 48 matches); the agent then hedged and split deal closings into a "confirm scope" section, losing 10 criteria | ours (v3 design) | Test 186: 10 matter criteria broken | **Test-observed, so not fixed in the evaluated system.** Proposed wording: "N matters match; if the question has further conditions add them, otherwise these N are the population". Evaluate on train/validation first |
| E23 | FV `/health` reported the newest freeze file, not the version a server actually serves | ours | Two servers (v3 :3150, v4 :3151) both showed the newest digest | `FV_FREEZE_TAG` pins the served freeze; the server refuses to start if code, data or harness files differ from it |
| E24 | DSH launcher cleanup ran `docker rm -f -t 0`; `-t` is podman-only, docker rejects it, and the error was swallowed, so every task container kept running (238 at peak) | DSH harness (podman-first) | Memory and some load; no effect on scores | Fixed on branch `vrag/harvey-fv` (`dsh_bench/launch.py`: `-t 0` only for podman); `tests/test_launch.py` now honours `RUNTIME` and passes 15/15 on docker, including "container removed" |
| E25 | `tests/test_layout.py` flags `models/haiku-copilot.json` because its display name mentions "vrag_harvey" | ours | Cosmetic; the file is part of the frozen system, so it was left unchanged | Rename the display name at the next freeze |
| E26 | **E2/E17/E18 diagnosed (2026-11-11).** The "rate limit" is not a rate limit. The Copilot API answers HTTP 503 `model_overloaded` ("upstream model provider is currently experiencing high demand. Please try another model") within ~350 ms for every OpenAI-family model (gpt-5.6-sol/-fast/-terra, gpt-6-sol, gpt-6.1-sol, gpt-5.3-codex) once a request exceeds ~24.1K o200k tokens. The cut-off is exact: 24,045 passes, 24,146 fails. It does not depend on pacing (4 × 12K back to back pass), and Claude passes at 300K. The account is `copilot_enterprise_seat_quota`. First seen 2026-11-09 09:53, four minutes after we patched the proxy to send the full prompt (`contextSize = maxInputTokens`). Before the patch the Copilot Chat wrapper silently trimmed long prompts from the start (needle probe, E7), so oversized requests never reached the API | Copilot service (size-based load shedding) | No OpenAI agent runs. The judges (<24K) are unaffected; occasional overnight 503s were retried | Ask teammates which route they use and whether their prompts are trimmed (run `vharvey.probe`). Request IDs are in the Copilot Chat log for a support ticket |
