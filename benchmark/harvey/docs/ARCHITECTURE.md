# 4 · Architecture A to Z

## A. The benchmark
- **Harvey LAB firm-knowledge** (repo `harveyai/harvey-labs`, pinned at commit `ba363f5`).
  - The corpus is one synthetic law firm, Calderwood & Harkness: 46 clients, 266 matters, 9,288 files (8,055 .docx, 615 .eml, 573 .xlsx, 45 .pptx), about 600M characters.
  - Every task runs against the whole corpus.
- **A task** (`tasks/firm-knowledge/tasks/NNN/task.json`) has three parts:
  - a lawyer's question, plus "write your answer to `response.md`";
  - 1–85 hidden rubric criteria;
  - the deliverable name.
- **Criterion types** (2,623 in total):

  | Type | Count |
  |---|---|
  | "identifies matter X as qualifying" | 1,349 |
  | "names a document showing it" | 729 |
  | precision: "asserts no matter outside {set}" | 241 |
  | numbers | 180 |
  | classifications | 116 |
- **Grading:** each criterion is judged pass/fail by an LLM that reads `response.md`. A task is all-pass only if every criterion passes.

## B. The harness (unchanged LAB pieces)
- **Agent loop.** `lab_core.harness.agent_loop.run_agent`: up to 200 turns. The model calls tools until it calls `finish` or stops calling tools.
- **Tools.** `bash`, `read` (converts docx/xlsx/pptx to text with LAB's `parse-doc`), `write`, `edit`, `glob`, `grep`, `finish`.
- **System prompt.** LAB's preamble plus the docx, pptx and xlsx skill manuals.
- **Sandbox.** One Docker container per trial (`lab-sandbox:latest`):
  - the corpus is mounted read-only at `/workspace/documents`, with `output/` and a scratch workspace;
  - no network; 60 s per shell command.
- **What we changed, and why:**
  - **Transport only.** `vharvey/proxy.py` is a lab_core `ModelAdapter` that talks Chat Completions to the local Copilot proxy:
    - exact-model check on every reply (the proxy can silently fall back to another model);
    - sends `reasoning.effort` (high);
    - estimates tokens with o200k, because the proxy reports 0;
    - refuses prompts above the model's window minus 5%, raising LAB's own "context_length_exceeded".
  - **Proxy patch.** The proxy itself was patched (`docs/proxy_patch/`) so that effort and the full context window are honoured; before the patch it silently cut prompts over ~270K tokens.
  - **`bin/podman`:** a shim that runs LAB's podman calls on Docker with `--user` so files written to the mounts have the right owner.
  - **`vharvey/runner.py`** runs one trial with exactly LAB's sandbox, executor, tools, prompt and loop, plus an optional **arm** that can wrap the executor, add tools and extend the prompt.
  - **`vharvey/batch.py`** runs each trial in its own process (host-side grep in one process serialises badly), resumes after crashes, and treats infrastructure failures as reruns, never as scores.

## C. Judging and metrics
- **Judges.** LAB's own rubric scorer (`score_rubric`, same prompt and parsing), with two judges called through the proxy: claude-sonnet-5 and gpt-5.6-sol. LAB's default judges (claude-sonnet-4-6, gpt-5.5) are not served by the proxy.
  - Judge prompts above 240K characters score "fail" without a call. This is an explicit rule (as in evo-harness), never a silent drop.
- **Metrics:**
  - *criterion pass*: mean over the two judges of passed / total;
  - *all-pass*: LAB's headline, 0.5 when the judges disagree;
  - *precision criterion*: pass rate of the "no matter outside the set" criteria;
  - *required-matter recall*: pass rate of the "identifies matter X" criteria.
- **Statistics:** paired over tasks (same tasks, same trial index); bootstrap 95% CI.

## D. Data splits and protocol
- **Split.** Dev (train) 50 / test 200, stratified by question type (`vharvey/split.py`, seed `vrag-harvey-split-v1`, using only instruction text and criterion counts).
- **Dev.** All analysis and every design change happened on dev, and is labelled as dev-informed.
- **Test.** The first 60 test tasks in split order, run with the frozen FV v2.2: arms VL (one trial) and VLC (two trials), A0 with two trials.
- **No leakage.** The verifier index is built from the corpus only; no task text and no rubric are used. Rubrics are read only by the grader and by offline analysis.

## E. The verifier index (offline, built once for all 266 matters)

| step | module | model | input → output | size / time |
|---|---|---|---|---|
| K0 text | `vharvey/k0.py` | – | every file converted with LAB's own `parse-doc` inside the sandbox image → `kb/k0/text/` (the same text the agent's `read` returns) | 9,288 files, 0 errors, 599 MB, ~15 min |
| Document cards | `vharvey/fv/docs.py` | claude-sonnet-5 | one call per file (long files: first 90K + last 30K characters) → type, title, date, **stage**, signed, summary, client, people, role statements, practice-area signals, status/outcome statements, relief sought, **terms**, **issues**; every list item must carry a verbatim quote | 9,286 cards, ~2 h at 128 parallel calls |
| Grounding | `vharvey/fv/common.py` | – | each quote must occur verbatim in the file (pandoc markup and whitespace normalised; ellipses allowed); items that fail are dropped | 129K items kept, 5.4% dropped |
| Long-file middles | `docs --extend-long` | claude-sonnet-5 | the unread middle of 728 long files, in 90K-character chunks → more terms/issues, grounded the same way | +18,596 items, ~30 min |
| Vocabulary | `vharvey/fv/vocab.py` | claude-opus-5.5 proposes, claude-sonnet-5 maps | all raw labels with counts → 24 practice areas, 318 terms, 311 issues; every raw label seen ≥2 times is mapped to a canonical id or "none" | 3 + 33 calls, ~20 min |
| Matter cards | `vharvey/fv/matters.py` | claude-opus-5.5 + rules | all document cards of the matter → client and aliases, description, matter type, practice areas, client role, status, outcome, dates, relief sought, people; every value needs evidence {path in this matter, verbatim quote} or it becomes null (UNKNOWN). **Terms and issues are aggregated by rule**: executed if the file is executed / execution version / filed (or its name says executed / execution / signed / conformed), else draft-only; an issue is "analysed" if any document analyses it | 266 cards, ~40 min |
| Freeze | `vharvey/fv/build_all.py` | – | sha256 of vocabulary, cards and code → `runs/FREEZE_fv_v2.2.json` | |

Cache: every LLM call is cached by its prompt (`cache/fv/`), so rebuilds after a code fix cost nothing.

## F. The runtime verifier (`vharvey/fv/api.py`, no LLM, ~0.1 ms per check)
- `check(matter, field, value)`:
  1. normalise the field (aliases such as `role` → `client_role`, prefixes `term.` / `issue.`);
  2. resolve keys and values to canonical ids: exact match, then the vocabulary's synonyms, then token overlap. If nothing is close enough, return UNKNOWN;
  3. compare with the matter card and return the verdict, the actual value and up to 3 evidence quotes.
- **Terms and issues:**
  - one lookup across executed terms, draft-only terms and issues;
  - a more specific key found in an executed document wins over an absent general one (`working_capital_adjustment` → `net_working_capital_target`), but never the reverse.
- **Practice area:** the first practice area on the card is primary (TRUE); later ones are SECONDARY.
- **closed_year:** uses the closing date, or the status date if the status is closed, terminated or withdrawn; otherwise UNKNOWN with a hint.
- **`check_complete(conditions, matters)`:** runs `check` for every condition on all 266 matters.
  - matches = all conditions TRUE;
  - it returns the matches missing from the list, the listed matters with a FALSE or NOT_FOUND condition, and possible matches with UNKNOWN fields;
  - the note always says the leads must be confirmed in the documents.
- **Tests** (`tests/test_fv_api.py`, 35): a passing and a failing case per field type, unknown keys and values, grounding, completeness.

## G. The arms (how the agent sees the verifier; `vharvey/fv/arm.py`)

| arm | before the first `finish` | at the first `finish` |
|---|---|---|
| A0 | LAB as is | finishes |
| V | FV tools + a usage block in the system prompt from turn 1 | finishes |
| VC | V + `fv_check_complete` | finishes |
| VL | **identical to A0** (FV tools hidden; a call to them is refused as an unknown tool) | refused once; FV tools are added to the live tool list; the agent is told to verify every listed matter |
| **VLC** | identical to A0 | as VL, plus the completeness check and "open each missing matter's documents before adding it" |

The gate is implemented as a wrapper around LAB's executor: it intercepts `finish` and the `fv_*` names and delegates everything else unchanged. LAB's loop passes the same tool list object to every model call, so tools added at the gate are visible from the next turn on.

## H. What the agent actually does (VLC, typical trajectory)
1. **Turns 1–30: normal LAB behaviour.**
   - Lists folders and greps the corpus (often converting all files to text in its workspace first).
   - Reads candidate engagement letters, memos and agreements.
   - Writes `response.md`.
2. **Turn ~31: calls `finish`.** The gate replies with the verification instructions and the tools appear.
3. **Turns 32–35: verification.**
   - One `fv_check_many` over its listed matters × the question's conditions.
   - One `fv_check_complete`.
   - `read` on 1–3 files of missing or contradicted matters.
   - `edit`s to `response.md`: drop matters with FALSE plus evidence, add confirmed missing ones, relabel.
4. **Turn ~36: `finish`** goes through.

On average VLC makes 2.8–3.3 verifier calls per trial.

## I. Latency and cost (Haiku 5.5, means per trial; like-for-like tasks and trials)

| | turns | wall clock | prompt tokens (cumulative) | output tokens | verifier calls |
|---|---|---|---|---|---|
| A0, train k=2 | 32.0 | 591 s | 1.63M | 9.1K | 0 |
| VLC, train k=2 | 35.2 | 627 s (+6%) | 1.79M (+10%) | 10.7K | 3.1 |
| A0, test k=2 | 32.6 | 645 s | 1.64M | 9.5K | 0 |
| VLC, test k=2 | 36.8 | 669 s (+4%) | 2.24M (+37%) | 11.4K | 3.5 |
| V1 (tools from start), train t0 | 13.8 | 179 s | 0.43M | 5.0K | 11.7 |

- **Runtime verifier cost:** a lookup (~0.1 ms; completeness ~0.25 s). No model calls.
- **One-time index cost:** about 9.3K Sonnet calls (~150M input tokens), 266 + 3 Opus calls and 33 Sonnet mapping calls; about 3.5 h wall clock at high concurrency. It is reused by every task and every run.

## J. Results summary
See tab 3. Headline (VLC vs A0, Haiku):
- **train, 2 trials:** +6.5 criterion, +9.5 all-pass, +13.8 precision (significant);
- **test, 2 trials:** +2.9 criterion (not significant);
- **same trajectory before → after verification:** +11.7 criterion on train (81 trials) and +6.4 on test (101 trials), both significant; test precision +10.8, all-pass +4.5.

## K. Known limitations and failure modes
1. **The search phase limits recall.** 92 required matters on train were never reached by A0's search. The completeness leads recover some; enumeration ("list all matters with …") is the next step (structuring).
2. **Index errors become agent errors.** Examples: a lock-up found only in a closing checklist was reported as "not executed", and 14 criteria regressed on train. The reference taxonomy (primary practice area, settled vs dismissed) is unstated, so the index can only approximate it.
3. **Vocabulary mapping errors.** Some synonyms are wrong (e.g. `oig_inquiry_billing` → `anti_kickback`, `frand_licensing` → `mfn`). They need human review before the next freeze.
4. **Gate coverage.** The gate never fires if the agent ends without calling `finish`, or writes the answer only through bash (2–5 trials per run behave as A0).
5. **Noise.** Two identical A0 runs differ by ~11 points on 15 tasks; claims rest on two-trial or same-trajectory comparisons.
6. **One model so far.** Haiku only. The OpenAI models on the Copilot account currently reject prompts over ~20K tokens.

## L. Where everything lives
- `vharvey/`: the code; `vharvey/fv/`: the verifier build and runtime.
- `kb/`: K0 text and the verifier index.
- `runs/labroot/results/<run>/<model>/<task>/t<k>/`: each trial, with config, transcript, metrics, output and scores.
- `logs/`: failure pages, attribution, calltest.
- `docs/`: this document, the approach, results, cases, iterations, errors, defects and the API spec.
- `logs/viewer/`: the dashboard. Rebuild with `python -m vharvey.viewer <runs>`.
