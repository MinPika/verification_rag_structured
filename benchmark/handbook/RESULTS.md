# vrag_handbook results

## Headline (2026-11-01)
**Question:** which representation of a policy corpus, and which runtime verification, make an LLM office agent
more accurate and compliant (HANDBOOK.md, 45 held-out test tasks)?

| Claude Haiku 5.5, test (45 x 4) | mean reward | strict pass@1 |
|---|---|---|
| A0 plain agent | 72.48 | 7.8 |
| A2 compiled representation (KB tools + brief + task plan), no runtime verification | 80.75 | 20.6 |
| A3 A2 + our compiled deterministic gate | 81.65 | 21.1 |
| R plain agent + the interwhen verifiers | 82.72 | 21.1 |
| **A2 + the interwhen verifiers (representation + verification)** | **85.74** | **28.9** |

1. **Representation helps** without any runtime check: A2 − A0 +8.3 [+3.4, +13.5].
2. **Verification helps on top, if the verifiers are precise:**
   - A2+R − A2 +5.0 [+1.5, +8.3];
   - our own compiled gate only +0.9 [−1.5, +3.2];
   - the difference is verifier quality (per-task, trace-tested code vs LLM-compiled regex specs), not the hook
     mechanism.
3. **They stack:** A2+R is the best arm (−A0 +13.3; −R +3.0 [−1.5, +7.8], positive but not significant). The gain
   over R comes where the representation alone was strong (logistics +8.9, finance +4.5). The main remaining
   failure is a wrong pre-solved decision in the compiled plan that anchors the agent even against the checker.
   A "checker takes precedence" variant is queued.
4. **the "retrieve code, not text"** (dev): code retrieval +3.4 over text retrieval [−2.0, +9.0]. The same code
   used as hooks is better again (R).
5. **Leaderboard comparability is unresolved** (see "leaderboard metric: what is and is not known"). The live board
   does not name its metric. Until 2026-10-14 it was strict pass@1. By 10-31 the same configurations had risen
   1.2–2.5×, which fits either a switch to pass@1 (N−1) or revised tasks. We report both metrics. Gains from our
   layer hold on both: test, weak models, A0 → A2+R, strict +9 to +22 and N−1 +23 to +34. RESULTS_SWEEP.md has the
   tables.

Every number is paired task-level bootstrap 95% CI on test unless marked dev. Test was evaluated several times
(v3, v5, v6, v7, A2+R); each run is a frozen version (runs/FREEZE_*.json), labelled in the sections below.

---

# vrag_handbook: verification for RAG on HANDBOOK.md (Claude Haiku 5.5)

Overnight run on 2026-10-28/29. Full tables: [runs/final_tables.md](runs/final_tables.md) (regenerate with
`runs/final_tables.sh`). Decision log: [PROGRESS.md](PROGRESS.md).

## Protocol
- 65 HANDBOOK tasks. **Dev** (CareIG, Crestwood, Vanguard; 20 tasks) was used for all development. **Test** (the
  other 7 companies; 45 tasks) was never inspected at the rubric level. Every number below is 4 trials/task, mean
  reward ×100, scored by the benchmark's own deterministic verifiers.
- The agent is always `claude-haiku-5.5` (OpenHands harness, reasoning_effort=max) through the Copilot proxy.
  Frontier models are used only **offline**: Opus 5.5 compiles the KB and the per-task specs, gpt-5.6-sol reviews
  and audits them.
- Arms:
  - **A0**: plain agent.
  - **R**: the interwhen verifiers, rerun here (checklist=1, 6 denials, stale 2).
  - **A2**: ours without interwhen. Compiled KB tools + SOP brief + compiled task plan.
  - **A3**: ours with interwhen. A2 + deterministic PreToolUse/Stop gate (compiled guards and obligations).
  - **v5** adds an offline decision audit.
- Frozen systems: v3 `ff52eccf946b7071`, v5 `82e31195fadfd845` (`runs/FREEZE_v*.json`).
  - **v3 is the primary test result.**
  - v4 and v5 were developed afterwards, on dev only. v5's test run was committed before its dev result was
    known, but it is a second look at test.

## Results

### Test (45 tasks)

| arm | mean | strict pass@1 | pass@4 | pass^4 |
|---|---|---|---|---|
| A0 plain Haiku | 72.48 | 7.78 | 13.33 | 2.22 |
| R the interwhen baseline interwhen (rerun) | **82.72** | 21.11 | 26.67 | **17.78** |
| A2 ours w/o interwhen (v3) | 80.75 | 20.56 | **31.11** | 15.56 |
| **A3 ours + interwhen (v3, primary)** | 81.65 | 21.11 | **31.11** | 13.33 |
| A2 ours w/o interwhen + audit (v5) | 77.47 | 20.56 | 31.11 | 13.33 |
| A3 ours + interwhen + audit (v5) | 80.44 | **21.67** | 28.89 | 13.33 |

Paired task bootstrap, 95% CI:

| comparison | difference | 95% CI |
|---|---|---|
| A3v3 − A0 | **+9.17** | [+3.72, +14.76] |
| A2v3 − A0 | **+8.28** | [+3.36, +13.46] |
| A3v3 − R | −1.08 | [−6.00, +4.22] |
| A3v3 − A2v3 (gate effect) | +0.89 | [−1.48, +3.20] |
| A3v5 − A2v5 (gate effect) | **+2.97** | [+0.40, +6.03] |
| A2v5 − A2v3 (audit effect) | −3.28 | [−6.60, −0.36] |

### Dev (20 tasks)
A0 69.46 | R 78.34 | A3 v4 72.91 | A3 v5 77.15 (v5−v4 +4.25 [−1.5, +11.8]; v5−R −1.2 [−8.0, +5.4]).

## What we learned
1. **Structured, task-compiled policy beats the plain agent by about 9 points** (A3/A2 vs A0, significant on
   test). This matches the per-task verifiers within noise (A3v3 − R = −1.1, CI ±5).
   - **We did not beat R.**
   - We do get higher strict pass@4 (31.1 vs 26.7).
   - R is more consistent (pass^4 17.8 vs 13.3).
2. **Where the gain comes from.** The offline compile with the task's seed data (the plan) carries almost all of
   it.
   - A2 without any online verification already gets +8.3.
   - Ablations on dev:
     - KB tools alone (A1) ≈ A0 or below.
     - Guards/plan compiled without seed data (tier `kb`) = A0.
     - The gate without the plan is below A0.
3. **The online deterministic gate (interwhen) adds little on top of a good plan** (+0.9, n.s.). It matters more
   when the plan is weaker (+3.0, significant, in v5 where the audit softens the plan). The gate must be precise:
   - On dev, one false block (wrong template matched → agent gave up) cost 80 points on a task.
   - v3/v4 fixed this class of error generically: tag-anchored template choice, whitespace/thousand-separator
     tolerant checks, reply/forward subjects from the seed mailbox, attachments.
4. **Main failure mode: wrong pre-solved decisions.** The offline compiler sometimes decides wrongly. On dev:
   - It treated a patient who is a lawyer as an "attorney communication" STOP.
   - It picked the wrong interview slots.
   - It forbade a reply that was required.

   The agent then follows the wrong plan. The v5 audit (mark unconfirmed decisions UNVERIFIED, disable unconfirmed
   guards and obligations) fixed these on dev (+4.3) **but did not transfer to test** (−1.2 for A3, −3.3 for A2).
   It removes correct guidance more often than wrong guidance. This is a dev-overfitting lesson.

## Caveats
- Dev has only 20 tasks, and some improvements were chosen from dev failures (regression to the mean). The test
  split was evaluated once for v3, and once more for v5 (labelled).
- R is the interwhen baseline's frozen verifier set run with our harness and proxy. Its own reported numbers on all 65 tasks were
  Haiku 68.90 and interwhen 81.84.
- Tasks that crash on "Message exceeds token limit" are scored 0 (as in the interwhen baseline's reports). Environment setup
  failures (Docker address-pool exhaustion) are excluded.
- Both seeded compiles (ours and R) see the task's initial data offline. A pure no-seed compile did not help.

## Diagnosis: why R's interwhen helps and ours does not (2026-10-31)
Both runtimes are deterministic OpenHands hooks (PreToolUse + Stop, plus R's start-of-task checklist). The
difference is in what the checks are made of and how actions are read.

- **R: one spec per message.** Each task has a hand-shaped Python module (65 modules, ~28.6K lines). It defines one
  `Comm` per required or forbidden message: an `about(action)` predicate, exact recipients, a subject regex,
  required body lines, attachments and max count. The same spec drives three things:
  - the start checklist (completion findings on the initial state);
  - the pre-call block (a precise diff of what is wrong with this message; 118 blocks on test, 61 of them
    "Missing: <required line>");
  - the stop check (a correctly formed instance was sent; 95% of what it flags gets fixed).
- **Ours: separate pieces.** The plan (free text), guards and obligations (LLM regexes) are compiled separately and
  are not linked. A pre-call check never tells the agent that a message will fail an obligation.
- **Bugs in our action reading (now fixed, v6).** On the recorded v3 test ledgers, 74 of the 111 action
  obligations reported "still open" at the end had in fact been done:
  - Slack DMs carry `user_id: "U005"`, which was never resolved to a person, so no DM obligation could ever be
    satisfied (49).
  - Replies and forwards had no subject or recipient (19; fixed in v4, which never ran on test).
  - `writeFile` uses `file_path` (5).

  So our stop hook mostly nagged about work that was already done. Dev (few DMs) did not expose this: 43 → 43.
- **Tried and rejected:** an email-body completeness check like R's main pre-call block. On dev replay it blocked
  good runs 8 times, because compiled template bodies sometimes contain procedure instructions. It would need a
  clean-template compile step first.
- Code now has `pyproject.toml` (ruff config), `tests/` (34 gate unit tests), and `runs/FREEZE_v6.json`.

### v6 on test (2026-10-31; third look at test, labelled)
| arm | mean | strict pass@1 | pass@4 | pass^4 | rubric checks |
|---|---|---|---|---|---|
| A3 v3 | 81.65 | 21.11 | 31.11 | 13.33 | 78.4% |
| **A3 v6** (gate fixes) | 81.61 | 22.22 | 28.89 | 13.33 | 78.1% |
| R | 82.72 | 21.11 | 26.67 | 17.78 | 83.4% |

- v6 − v3: −0.03, 95% CI [−1.99, +1.96]. v6 − R: −1.11 [−6.32, +4.26]. v6 − A0: +9.14 [+3.72, +14.85].
- The gate now behaves better:
  - stop refusals per trial 0.85 → 0.44;
  - share of flagged items the agent resolved 35% → 52%;
  - pre-call blocks 0.08 per trial.

  **But the score did not move.** The false refusals mostly concerned work that was already done, so removing
  them saved turns but not points. The remaining true interventions are too few to matter.
- By company, the DM-heavy handbooks rose (Mojave +4.8, Ridgeline +4.0) and Prairie Star and Meridian fell. With
  per-task swings of up to ±20 between identically configured runs, this is within noise.
- Conclusion: our interwhen gain is limited by **coverage**, not precision. R blocks 0.66 calls per trial with
  specific, message-level diffs; we block 0.08. Closing the gap needs per-message specs (one spec feeding the
  checklist, the pre-call check and the stop check) built from clean templates, not more fixes to how actions are
  read.
- 2 of 180 trials hit transient proxy HTTP 500 errors and are excluded (no reward).

## v7: per-message specs (2026-10-31; fourth look at test, labelled)
[vrag/messages.py](vrag/messages.py) compiles one spec per required or forbidden email/Slack message:
recipients/channel, subject regex, verbatim SOP quotes, case values and attachments. The same spec drives the
prompt checklist, the pre-call check and the stop check (gate.py `check_messages`, `message_obligations`,
`checklist_text`).

The author (Opus) sees the SOP, the templates, the task data and the plan. Every spec is then validated
mechanically:
- quotes must occur in the SOP, and instruction-like quotes are rejected (this is the template-cleaning step);
- values must occur in the task data;
- recipients and channels must be known;
- the author's sample message must pass the spec;
- forbidden specs need allowed look-alikes and must not catch required messages;
- required specs must be mutually exclusive.

Result: 274 specs over 65 tasks (185 required, 89 forbidden; 2 tasks need none). 16 new tests (50 total).

| arm | test mean | strict pass@1 | pass@4 | pass^4 | dev mean |
|---|---|---|---|---|---|
| A3 v3 | 81.65 | 21.11 | 31.11 | 13.33 | 73.3 (v3) / 72.9 (v4) |
| A3 v6 | 81.61 | 22.22 | 28.89 | 13.33 | - |
| **A3 v7** (message specs) | 81.36 | 18.89 | 28.89 | 13.33 | 70.46 |
| R | 82.72 | 21.11 | 26.67 | 17.78 | 78.34 |

- **Test:** v7 − v3 −0.29 [−2.39, +1.81]; v7 − A2 +0.61 [−1.97, +3.06]; v7 − R −1.36 [−6.76, +4.35].
- **Dev:** v7 − v4 −2.45 [−5.71, +0.57].
- **Precision is high.** On replayed A0/R dev trajectories, message-spec pre-call blocks fire 53 times on runs
  scoring below 0.95 and 0 times on runs scoring 0.95 or above. Required messages still open at the end: 83 vs 1.
- **But live A3 agents rarely trip the specs.** Message-spec blocks are 0.10 per trial on test (R: 0.66 total).
  The agent already sees the exact wording in the checklist and mostly complies. The remaining errors are outside
  messages: Jira, spreadsheet rows, and case decisions (e.g. offboarding the wrong employee).
- **Conclusion:** interwhen on top of a good compiled checklist adds about 0 here, consistent across v3, v6 and
  v7. Hypothesis to test next (on dev): R's gain also comes mainly from its verifier-derived checklist rather
  than from blocking. Ablate R into checklist-only vs hooks-only.
- Related-work survey: [docs/related_work.md](docs/related_work.md).

## the idea: retrieve the code, not the text (2026-10-31, dev only)
- **Code source:** The per-task interwhen verifier modules, cut into 995 code units (one per message spec or rule, with
  the references, constants and helpers it uses) by [vrag/vcode.py](vrag/vcode.py). 971 units are mapped to SOP
  blocks through their `(section, paragraph start)` references.
- **Retrieval:** `policy__procedure/find/read` return the mapped code and fall back to SOP text elsewhere
  (policy_server.py code mode). Same tools and prompt otherwise.
- **Alternative code source:** our own SOP-to-code compiler ([vrag/sopcode.py](vrag/sopcode.py): one pure,
  runnable, block-cited function per procedure + `policy__run` sandbox). Compiled for 1 task; paused in favour of
  the interwhen baseline's tested modules.

| dev (20 tasks x 4) | A0 | A1 text retrieval | **A1 code retrieval** | R (same code as hooks) |
|---|---|---|---|---|
| mean reward | 69.46 | 69.64 | **73.03** | 78.34 |
| strict pass@1 | 16.25 | 10.00 | 15.00 | 16.25 |

- code − text: +3.39, 95% CI [−1.97, +9.01] (n=20; positive but not significant).
- The agent consults policy tools twice as often with code (15.6 vs 8.5 calls/trial) and reads the raw PDF a bit
  less (3.0 vs 3.7).
- The same code used as hooks (R) is still +5 better: code is more useful enforced than retrieved.

## Our representation + the interwhen verifiers (2026-10-31, dev)
`--rhooks`: A2 (compiled KB tools + brief + plan) with the interwhen runner layered on top (its start
checklist, PreToolUse and Stop hooks, R's settings: 6 completion denials, stale 2).

| dev (20 x 4) | A0 | A2 | **A2 + R hooks** | R | A3 v4 (our gate) |
|---|---|---|---|---|---|
| mean reward | 69.46 | 71.54 | **77.35** | 78.34 | 72.91 |
| strict pass@1 | 16.25 | 10.00 | 16.25 | 16.25 | 11.25 |
| pass^4 | 5.00 | 0.00 | **15.00** | 10.00 | 5.00 |

- **A2+R − A2: +5.81, 95% CI [+0.42, +11.65].** Interwhen verification gives a real, significant gain when the
  verifiers are good (the per-task, trace-tested code). Our compiled gate on the same base gives about +1.
- A2+R − R: −0.99 [−6.72, +4.75]. On dev our representation adds nothing on top of the interwhen verifiers and their
  checklist.

## Best Haiku configuration on test: A2 + the interwhen verifiers (2026-10-31; labelled additional test look)
| test (45 x 4) | A0 | R | A2 | A3 (our gate) | **A2 + R hooks** |
|---|---|---|---|---|---|
| mean reward | 72.48 | 82.72 | 80.75 | 81.65 | **85.74** |
| strict pass@1 | 7.78 | 21.11 | 20.56 | 21.11 | **28.89** |
| strict pass@4 | 13.33 | 26.67 | 31.11 | 31.11 | **35.56** |
| pass^4 | 2.22 | 17.78 | 15.56 | 13.33 | **20.00** |

Paired (n=45):
- A2+R − A2 +4.98 [+1.51, +8.27] (verification on top of our representation);
- A2+R − A0 +13.26 [+8.91, +17.92];
- A2+R − R +3.01 [−1.45, +7.77] (representation on top of the interwhen baseline's verification; positive, not significant);
- A2+R − A3 +4.09 [+0.16, +8.03] (the interwhen verifiers beat our compiled gate as the interwhen layer).

Interpretation:
- Representation (compiled KB + plan) and verification (trace-tested per-task verifiers) stack.
- The best arm combines both, and its strict pass@1 (28.9) is the highest of all Haiku arms.
- The arm was chosen on dev, and the test run was committed before its result was known. It is still an
  additional look at test.

## Code retrieval + the interwhen verifiers (dev, 71/80 trials; the proxy hung before the last 9)
| dev | A0 | R | A1 code | A1 code + R | A2 + R |
|---|---|---|---|---|---|
| mean reward | 69.46 | 78.34 | 73.03 | 78.42 | 77.35 |

- A1 code + R − R: +0.07 [−2.53, +3.02]; − A1 code: +5.39 [−2.18, +12.83].
- On dev, every arm with the interwhen verifiers lands at about 78, whatever representation sits underneath.

Where A2+R beats R on Haiku test (task means): logistics +8.9 (Prairie Star +19.1), finance +4.5 (Sunshine +6.5,
Meridian +2.5), medical +0.3, HR −2.1, insurance −2.0. Per task: 11 better, 8 worse, 26 within 5 points. The gain
over R comes where our compiled representation alone (A2) was already strong; where the interwhen verifiers dominate
(HR, insurance), the representation adds nothing.

## 2026-11-01: metric fix, leaderboard protocol, harness findings
- **Strict pass@1 definition fixed** (report.all_passed). A trial passes when every rubric criterion passes (the
  verifier's "X/Y rubrics passed" line), as in HANDBOOK.md. The reward is the mean rubric score and can be below
  1.0 when all criteria pass (36 trials, e.g. 19/19 passed, reward 0.9934). Earlier strict numbers in this file
  slightly under-count.
  Haiku over all 65 tasks x 4 (leaderboard protocol), corrected:

  | arm | strict pass@1 |
  |---|---|
  | A0 | 10.8% |
  | A2 | 18.8% |
  | R | 21.2% |
  | **A2+R** | **26.5%** |

  A2+R − A0 +15.8 [+7.3, +25.0].
- **Opus 5.5 on the leaderboard protocol** (65 tasks, ~4 trials, same harness code and tasks): plain Opus
  **31.5%** strict pass@1 vs **52.3%** on the public leaderboard. Gemini-4-argon is the opposite (test: 45.6% here
  vs 36.6% on the leaderboard), so the setup is not uniformly weaker.
  - Ruled out: context window (Copilot gives every model 870K+ tokens), dropped images (readPDF returns text; no
    test task has image files), harness code and task set (Surge's own commit).
  - ~~Most likely cause: the Opus thinking budget.~~ Not supported; see "leaderboard metric: what is and is not
    known" below.
- **Our layer on Opus:** strict pass@1 31.5% → 25.5% (−6.0 [−16.0, +3.3]); mean reward −0.6 [−2.8, +1.4]. On
  strong models the compiled plan and checklist anchor the agent and cost some all-correct runs.
- **gpt-5.x through this harness:** the OpenHands SDK sends any model id containing "gpt-5" to the OpenAI Responses
  API, which the proxy does not serve (404). Fixed with an agent-side alias (run_arm.agent_model) that vrag.bridge
  maps back. The bridge replaces handbook/scripts/proxy_bridge.py and logs every request.
- **"Checker takes precedence" variant** (`--checker-first`, dev 20 x 4): it tells the agent that the interwhen baseline's checker
  overrides the drafted plan. No gain: 77.0 mean / 13.3% strict vs A2+R 77.4 / 16.2% (−0.4 [−1.8, +0.9]), so it
  is dropped.

## 2026-11-01 (later): leaderboard metric: what is and is not known
**Correction.** An earlier version of this section said the board reports pass@1 (N−1). That was an inference from
the launch blog and is **not established**. Sources: the live page (published 2026-10-31), Wayback snapshots of
2026-07-30 and 2026-10-14, the paper (arXiv 2607.25398v3) and upstream `surge-ai/handbook@374bc87`.

1. **The live page names no metric.** It shows only "model (effort) xx.x %", with no harness tag and no
   strict/N−1 label.
2. **Up to 2026-10-14 the board was strict pass@1.** In both snapshots, Fable 5 = 36.2 and Opus 4.8 (max) = 21.9.
   These equal the paper's Table 2 ("Strict pass@1 … 65 tasks, 4 trials per task, July 2026 leaderboard"). The
   paper gives N−1 only in a figure (Opus 4.8 max ≈ 46, GPT-5.5 ≈ 32).
3. **Between 10-14 and 10-31 every configuration still on the board rose:**

   | config (identical label) | 10-14 (strict) | 10-31 | ratio |
   |---|---|---|---|
   | Fable 5.1 (Adaptive/Max) | 38.8 | 47.1 | 1.21 |
   | Kimi K3 (Max) | 11.9 | 28.6 | 2.40 |
   | Gemini 3.8 Flash (High) | 10.8 | 26.5 | 2.45 |
   | Qwen 3.8 Max (xHigh) | 16.5 | 30.8 | 1.87 |
   | GLM 5.3 (Max) | 15.0 | 29.9 | 1.99 |
   | Muse Spark 1.3 (xHigh→Max) | 15.4 | 33.9 | 2.20 |

   Older entries (Fable 5, Opus 5, Opus 4.8, GPT-5.5/5.6) were removed. The current 52.3 for Opus 5.5 is therefore
   **not** strict pass@1 on the task set the July–October board used. If it were, Fable 5.1 would still read 38.8.
4. **Two explanations fit, and we cannot tell them apart without Surge:**
   - (a) **Metric switched to pass@1 (N−1).** The paper says N−1 "roughly doubles" the leaders.
   - (b) **Revised tasks and rubrics, re-run.** The public sample task `hr_crestwood_university_79786c46` differs from
     our copy: 22 vs 21 criteria; one criterion relaxed (a Jira "OFFBOARD" record is now allowed if it is marked
     on hold); one tightened (emails must match); one added (benefits row unchanged).
   - Both could be true.
5. **Our numbers against each reading** (plain agent, ours vs board):

   | model | ours strict | ours N−1 | board 10-31 | board 10-14 strict |
   |---|---|---|---|---|
   | Opus 5.5 (65 × 4) | 31.5 | 53.3 | 52.3 | — (Opus 5 max 32.3) |
   | Sonnet 5.5 (test × 2) | 25.6 | 51.1 | 47.7 | — |
   | Gemini 3.8 Flash (test × 2, effort max) | 16.7 | 31.1 | 26.5 | 10.8 (effort high) |
   | Gemini 4 Argon (test × 2) | 45.6 | 68.9 | 36.6 | — |

   - Reading (a): we match the board within +1 to +5 for three of four models.
   - Reading (b): our strict numbers are on the older task version, so they compare with the 10-14 strict board,
     and there the only overlapping configuration is Gemini 3.8 Flash at effort high (A0 high is running).
   - Gemini 4 Argon is high under either reading. Effort high gives the same result as max (interim: 45.0 strict,
     70.0 N−1), so effort is ruled out.
6. **Ruled out as causes:**
   - harness code (upstream differences only touch Responses-API/Gemini/Qwen routing);
   - grading (deterministic code, no LLM judge);
   - context window;
   - image handling.
7. **What does not depend on this:** every arm comparison here is paired, on the same tasks, harness and metric,
   and we report strict and N−1 side by side. To settle the board question, ask benchmarks@surgehq.ai (named in
   the README) which metric the board uses since late October, and for the revised task set.

**Scoring rule (2026-11-01 17:20):** trials that hit the 1 h agent timeout are excluded as infrastructure errors.
They only occur during proxy hangs (24 trials in 6 jobs). Gemini 3.8 Flash below therefore reads A0 19.3 / 31.8 and
A2+R 28.9 / 65.6 (strict / N−1); RESULTS_SWEEP.md is regenerated with the rule.

**Gains on both metrics** (test, plain agent → A2+R, paired bootstrap; * = CI excludes 0; before the timeout rule):

| model | strict | N−1 |
|---|---|---|
| Haiku 5.5 | 8.3 → 31.1 (+22.8*) | 28.9 → 52.2 (+23.3*) |
| gpt-6-luna | 5.6 → 23.9 (+18.2*) | 21.1 → 55.7 (+34.1*) |
| gpt-6-sol | 10.0 → 32.2 (+22.2*) | 27.8 → 55.6 (+27.8*) |
| gpt-5.6-sol | 14.4 → 33.3 (+18.9*) | 30.0 → 57.8 (+27.8*) |
| Gemini 3.8 Flash | 16.7 → 25.6 (+8.9) | 31.1 → 62.2 (+31.1*) |
| Sonnet 5.5 | 25.6 → 30.0 (+4.4) | 51.1 → 58.9 (+7.8) |
| Opus 5.5 (test × 4) | 34.4 → 30.0 | 55.4 → 57.2 |
| Gemini 4 Argon | 45.6 → 44.4 | 68.9 → 73.3 |

Interwhen's own share on Haiku (A2+R − A2): strict +8.9 [+1.1, +17.8], N−1 +14.4 [+3.9, +25.0], mean +5.0 [+1.5, +8.3].

## 2026-11-01 evening: four-arm ablation, test split (mean / strict / N−1; * = paired 95% CI excludes 0)
| model | plain (A0) | structure (A2) | the interwhen baseline verifiers (R) | ours + verifiers (A2+R) | R − A0 (N−1) | A2 − A0 (N−1) | A2+R − R (N−1) |
|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | 72.5 / 8.3 / 28.9 | 80.8 / 22.2 / 37.8 | 82.7 / 23.3 / 42.8 | 85.7 / 31.1 / 52.2 | +13.9* | +8.9 | +9.4 |
| gpt-6-luna | 66.7 / 5.6 / 21.1 | 73.5 / 11.4 / 33.0 | 84.9 / 20.0 / 44.4 | 86.0 / 23.9 / 55.7 | +23.3* | +11.4 | +10.2 |
| gpt-6-sol | 71.7 / 10.0 / 27.8 | 74.1 / 20.0 / 30.0 | 86.5 / 33.3 / 48.9 | 87.3 / 32.2 / 55.6 | +21.1* | +2.2 | +6.7 |
| gpt-5.6-sol | 74.2 / 14.4 / 30.0 | 83.2 / 29.5 / 51.1 | 86.7 / 25.6 / 47.8 | 89.5 / 33.3 / 57.8 | +17.8* | +20.5* | +10.0 |
| claude-sonnet-5.5 | 84.0 / 25.6 / 51.1 | 83.8 / 21.1 / 42.2 | 88.2 / 27.8 / 57.8 | 89.7 / 30.0 / 58.9 | +6.7 | -8.9 | +1.1 |
| claude-opus-5.5 | 88.6 / 34.4 / 55.4 | 84.3 / 34.4 / 48.9 | 87.1 / 31.1 / 53.3 | 89.2 / 30.0 / 57.2 | -2.0 | -6.5 | +3.9 |
| gemini-4-argon | 91.6 / 45.6 / 68.9 | 88.3 / 40.0 / 61.1 | 92.0 / 40.0 / 71.1 | 92.3 / 44.4 / 73.3 | +2.2 | -7.8 | +2.2 |
| gemini-3.8-flash | 76.8 / 19.3 / 31.8 | 84.1 / 26.7 / 45.6 | 89.6 / 30.0 / 60.0 | 90.7 / 28.9 / 65.6 | +27.3* | +14.8* | +5.6 |

Haiku's A2 is the v3 compiler; other models use the current one. All 8 models complete on test (23:35 UTC); dev
runs (for all-65 numbers) are still running; RESULTS_SWEEP.md is regenerated from the jobs.
- **Verification is the main driver.** the interwhen verifiers alone (R − A0) give large N−1 gains for the weaker models
  (gpt-6-luna, gpt-6-sol, gpt-5.6-sol, Haiku), a modest gain for Sonnet, and nothing for Opus and Gemini-4-argon,
  which already do most of what the verifiers check.
- **Our structure alone (A2 − A0)** helps weaker models (gpt-5.6-sol significant, gpt-6-luna and Haiku positive)
  and is neutral to slightly negative for strong ones (Opus mean −4.3*, Argon −3.4): a pre-drafted plan pulls a
  strong model off its own reading.
- **Both together (A2+R)** is the best or tied-best arm for every model. Our structure adds most on top of the
  verifiers for gpt-5.6-sol and Haiku, and about nothing for gpt-6-sol and Sonnet.

## the idea on test: retrieve the interwhen verifier code instead of SOP text (Haiku, 45 × 4; 2026-11-02 00:40)
Both arms share everything: the same policy__* tools and plain-agent prompt, no plan, no hooks. The only difference
is what retrieval returns: the SOP prose (A1 text), or the per-task verifier code mapped to the same SOP blocks
(A1 code; `Comm(...)` message specs, `pre_rule`, `state_rule`), with text as the fallback.

| arm | mean | strict | N−1 |
|---|---|---|---|
| A0 plain | 72.5 | 8.3 | 28.9 |
| A1 text retrieval | 71.2 | 11.7 | 27.8 |
| **A1 code retrieval** | **80.8** | **24.4** | **33.9** |
| A2 our structure (reference) | 80.8 | 22.2 | 37.8 |

- **Code − text, test:** mean **+9.6 [+3.9, +15.2]**, strict **+12.8 [+2.2, +23.9]**, N−1 +6.1 [−6.7, +18.9].
- **Code − text, all 65 tasks:** mean **+7.7 [+3.4, +12.1]**, strict **+10.4 [+3.1, +18.5]**, N−1 +5.0 [−3.9, +14.2].
- Retrieving SOP text adds nothing over the plain agent (−1.3), which already reads the SOP files itself.
  Retrieving the same sections as code adds +8.3 mean and +16.1 strict over plain, matching our whole compiled
  structure (A2: KB tools + brief + plan) on mean.
- Representation matters: an executable, precise restatement of the policy is a better retrieval unit than prose.
  Enforcing that same code (R: hooks) is still worth more than reading it (R 82.7 / 23.3 / 42.8).

## 2026-11-02 final: all 8 models × 4 arms on all 65 tasks (mean / strict / N−1; * = paired 95% CI excludes 0)
| model | plain (A0) | structure (A2) | the interwhen baseline verifiers (R) | structure + verifiers (A2+R) | R − A0 N−1 | A2 − A0 N−1 | A2+R − R N−1 | A2+R − A0 N−1 | board 10-31 |
|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 71.5 / 10.8 / 28.5 | 78.0 / 18.8 / 32.7 | 81.4 / 21.2 / 40.4 | 83.2 / 26.5 / 43.5 | +11.9 [+2.3, +21.9]* | +4.2 [-5.8, +14.2] | +3.1 [-6.9, +13.5] | +15.0 [+5.0, +25.0]* |  |
| gpt-6-luna | 66.6 / 5.4 / 19.2 | 70.3 / 10.9 / 27.3 | 83.2 / 18.5 / 40.8 | 81.8 / 19.5 / 46.9 | +21.5 [+12.3, +31.5]* | +7.8 [-2.3, +18.0] | +5.5 [-4.7, +15.6] | +27.3 [+15.6, +39.1]* |  |
| gpt-6-sol | 72.4 / 9.2 / 24.6 | 72.6 / 16.9 / 25.4 | 85.0 / 27.7 / 43.8 | 83.3 / 26.2 / 45.4 | +19.2 [+7.7, +30.8]* | +0.8 [-10.8, +12.3] | +1.5 [-8.5, +11.5] | +20.8 [+9.2, +32.3]* |  |
| gpt-5.6-sol | 73.3 / 15.4 / 28.5 | 78.8 / 23.4 / 41.4 | 85.1 / 23.8 / 47.7 | 84.9 / 26.9 / 46.9 | +19.2 [+6.9, +32.3]* | +12.5 [+1.6, +23.4]* | -0.8 [-12.3, +10.8] | +18.5 [+5.4, +31.5]* |  |
| Gemini 3.8 Flash | 76.2 / 15.6 / 27.3 | 80.6 / 21.5 / 37.7 | 86.3 / 23.1 / 50.8 | 87.3 / 25.0 / 56.2 | +22.7 [+10.2, +35.2]* | +10.9 [-0.8, +22.7] | +4.7 [-5.5, +14.8] | +27.8 [+16.7, +39.7]* | 26.5 |
| Sonnet 5.5 | 82.8 / 23.1 / 50.0 | 81.7 / 20.0 / 39.2 | 85.9 / 25.4 / 50.8 | 86.3 / 25.4 / 50.8 | +0.8 [-10.8, +12.3] | -10.8 [-23.8, +2.3] | +0.0 [-10.8, +10.0] | +0.8 [-11.5, +13.1] | 47.7 |
| Opus 5.5 | 87.5 / 31.5 / 53.3 | 82.8 / 29.2 / 46.2 | 85.8 / 26.2 / 48.5 | 86.8 / 25.4 / 50.4 | -4.9 [-16.5, +6.9] | -7.2 [-17.2, +2.7] | +1.9 [-7.2, +10.9] | -2.9 [-14.0, +7.8] | 52.3 |
| Gemini 4 Argon | 88.8 / 36.9 / 60.8 | 84.5 / 32.3 / 52.3 | 88.8 / 32.3 / 60.0 | 89.6 / 38.5 / 64.6 | -0.8 [-10.0, +8.5] | -8.5 [-20.0, +3.1] | +4.6 [-3.8, +13.1] | +3.8 [-6.2, +13.8] | 36.6 |

Haiku 4 trials/task; other models 2 (Opus A0 and A2+R 4). Agent-timeout trials (proxy outages) are excluded.
Per-model tables, test-only numbers and every contrast are in RESULTS_SWEEP.md. The slide deck is
docs/deck/HANDBOOK_verification_for_RAG.pptx (build: docs/deck/build_deck.py).
- **Verification is the main driver.** the interwhen verifiers alone (R − A0) are significant on N−1 for all five
  weaker models (+12 to +23) and add nothing for Sonnet, Opus or Gemini Argon.
- **Structure alone (A2 − A0)** is weaker and less consistent: significant N−1 only for gpt-5.6-sol (+12.5);
  significant mean and strict for Haiku; significantly negative mean for Opus (−4.7) and Argon (−4.3).
- **Together (A2+R − A0):** +15 to +28 N−1 for weaker models, which then reach plain-Sonnet/Opus level (≈ 43–56
  N−1). Adding structure on top of the verifiers is −1 to +6 N−1 and not significant anywhere.
- **Plain-agent agreement with the live board:** Opus 53.3 vs 52.3, Sonnet 50.0 vs 47.7, Gemini Flash 27.3 vs
  26.5 (N−1). Gemini Argon 60.8 vs 36.6 remains unexplained (effort ruled out).
- **the idea (Haiku):** code retrieval beats text retrieval by +7.7 mean [+3.4, +12.1] and +10.4 strict
  [+3.1, +18.5] on all 65 tasks.

## 2026-11-03: failure analysis (criterion level) and benchmark defects
Full analysis: docs/failure_analysis/ (deck HANDBOOK_failure_analysis.pptx; protocol PROTOCOL.md; data in data/).
- **Overlap.** Solid failures per model: R < A2 for every model, and A2+R is within −7 to +22 of R. 54–66% of
  A2+R failures also fail in both A2 and R, and at most 7% of those shared failures are fixed in A2+R. Failures
  only one of them has are mostly fixed, but A2+R inherits some of A2's own, so net A2+R ≈ R. New failures (in
  neither A2 nor R) are few, except for Opus (15).
- **Shared core.** 57 criteria fail in A2+R for all 8 models, 78 for at least 7.
- **Root causes, Haiku A2+R (145 residual solid failures, 5 annotators; second annotator on a random 30, Cohen's
  κ 0.61):**

  | Cause | Criteria | Share |
  |---|---|---|
  | Verified rubric defect | 39 | 27% |
  | Unverified rubric claim | 34 | 23% |
  | Our drafted plan wrong | 30 | 21% |
  | Verifier gap / too loose / wrong spec | 38 | 26% |
  | Agent ignored a flag or slipped | 3 | 2% |
  | Tool or harness limit | 1 | 1% |

  Of the 72 non-rubric failures, the verifier fully covered only 9.
- **Benchmark defects, verified by hand in grader code and task data (data/defects.json): 39 criteria in 15
  tasks.**
  - T1, cannot be passed by any SOP-consistent output: 16, in 5 tasks.
  - T2, rubric contradicts the SOP or SOP names do not match the environment: 15.
  - T3, brittle exact match: 8.
  - Most share one cause: graders written for an earlier environment whose Jira keys and IDs differ from the
    shipped data. Surge's current public release rewrote all 7 T1 criteria of the one task we can diff (9b2f7a29);
    no errata were published.
- **Ceilings, all 65 tasks:** strict pass@1 92.3 / N−1 93.8 / mean 98.2 (T1 only); 76.9 / 89.2 / 95.3 (T1–T3).
- **Rescored results** (data/rescored.json): removing defects lifts arms by 0–5 points (T1) or 2–11 (all tiers) and
  no conclusion changes. The A2+R strict gain of weak models grows (Haiku +15 → +20, gpt-6-sol +17 → +23); Opus
  stays negative.

## 2026-11-03: why structure alone (A2) hurts strong models
- **Breakage is the same for every model, gains are not.** A0 → A2 breaks 7–10% of the criteria A0 passes for
  every model (gpt-6-sol 12%). It fixes 17–41% of A0 failures, but strong models have few left (Sonnet 135, Opus
  104, Argon 92 vs 180–230 for weak models), so net criteria fixed − broken is +7 to +31 for weak models and −6 to
  −28 for Sonnet, Opus, Argon and gpt-6-sol.
- **Not noise.** Two halves of the same A0 runs differ by 6–7 broken criteria (Opus, Haiku); A0 vs A2 on the
  same trial counts by 44 (Opus) and 30 (Haiku).
- **Not simply skipping the SOP.** With A2, trials that open the SOP fall from ~95% to 10–12% (Claude) and
  24–51% (others). Within A2, trials that do read it do not pass A0-passing criteria reliably more often.
- **Mechanism** (132 regressed criteria, 202 model instances, 5 annotators; data/labels_a2_regressions.jsonl):
  the drafted plan causes 69% of instances (plan wrong 82, plan omits a required step 49, plan adds a harmful
  extra action 9); KB/brief 32 (16%), mostly gpt-6-sol halting whole tasks on compiled "stop"/guard rules;
  rubric 17 (8%); execution and other 13. Per model, plan-caused: Argon 43/47, Sonnet 36/44, Opus 36/46,
  gpt-6-sol 25/65 (KB stop rules 27/65).
- **Examples.** CareIG f6d19d30: the plan declares an "attorney-communication global stop" because the patient
  mentions a plan from her law firm, and forbids the hardship and log updates. Gear Systems 0807b5a6: the plan
  forbids the release the Quality Manager authorised. Crestwood 2071c562: the plan treats email 4 as a legal
  threat (no reply, no Briggs/Voss forwards, no BENEFITS ticket). The checklist is labelled fallible ("follow the
  SOP where they disagree"), but strong models follow it.

## 2026-11-04 overnight (x10): plan alternatives and the exec tool (Haiku, Opus; all 65 x 4)
Details: docs/overnight_x10/SUMMARY.md (tables: docs/overnight_x10/RESULTS.md). Mean reward Haiku / Opus:
A0 71.5 / 87.5; A1 text 70.7 / 81.0; A2 78.0 / 83.1; A2 noplan 68.9 / 80.8; A2 facts(+soft) 69.3 (69.9) / 79.7 (80.3);
R 81.4 / 86.3; A2+R 83.2 / 86.8; A2 noplan+R 83.5 / 85.6; A1 code 78.4 / 83.1; A1 code+exec 84.1 / 86.2;
A1 text+exec 84.8 / 87.1.
- **Best for both: SOP text retrieval + exec tool (the reviewer; model-invoked verifier code, no monitor, no plan).** Haiku
  +13.3* mean over A0, +3.5* over R, = A2+R, best N−1 (44.6); Opus = A0 = R (its best arm, not above A0). One finish
  check adds nothing.
- **Verifiers own the checklist:** A2 noplan+R = A2 facts+soft+R = A2+R = R for both models.
- **Without verifiers the plan carried A2:** dropping it hurts (Haiku −9.1*, Opus strict −13.5* vs A2); a
  non-deciding fact sheet = no plan; soft stops: no effect.

## 2026-11-04: why nothing beats the plain agent for Opus
- **Little headroom.** Opus A0 fails 104 criteria (solid) and 40 flaky: 35 are verified rubric defects, 14 fail for
  ≥ 7 of 8 models, 42 for 4–6, only 13 are Opus-specific. Its noise floor is small (A0 half vs half −0.4 [−2.1, +1.2]
  mean), so the flat results are real.
- **The verifiers fire as often as for Haiku** (0.83 pre-call denials per trial) **and fix 30 Opus failures, but break
  33 criteria Opus already passes** (Haiku: 84 fixed, 28 broken). 21 break in all four verifier arms (R, A2+R,
  noplan+R, exec), i.e. caused by the verifier content itself.
- **Mechanism of those 21** (2 annotators; data/labels_opus_verifier_regressions.jsonl; 20 of 21 fail the same way in
  the exec arm): checklist omission 10 (Opus treats the verifier's checklist as the complete to-do list, copies its
  calls and skips what the SOP requires beyond it; its read calls halve, 9.2 → 4.6 per trial), wrong verifier spec 4,
  verifier redirect 4 (a different channel/wording than the rubric), rubric defect 3 (verifier right), noise 0. The
  SOP sides with the rubric in 12, the verifier in 4, ambiguous 5.
- Example (hr_crestwood 79786c46): checklist item 27 "mark_emails email_ids ["7"], is_read true"; R makes exactly that
  call; A0 (from the SOP) marks it read and important (P1) and posts the escalation.

## 2026-11-06: harness comparison, Haiku 5.5 in Claude Code vs OpenHands (docs/harness_cc/SUMMARY.md)
- Claude Code (k=1, direct to Anthropic, effort max) 75.2 / 16.9 / 29.2 (mean / strict / N−1) vs OpenHands (k=4)
  71.5 / 10.8 / 28.5: +3.6 [−2.0, +9.4] mean, n.s.; $32.98 for 65 trials.
- The gain is mostly context handling: OpenHands lost 11/260 trials to context overflow; without them the gap is
  +0.6 [−4.2, +5.1]. Claude Code's losses are over-caution, partly from the real date in its system prompt
  conflicting with the task date (cited in 60/65 trials).
