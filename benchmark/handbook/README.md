# HANDBOOK: compiling an SOP handbook into a policy KB for an office agent

[HANDBOOK.md](https://github.com/surge-ai/handbook) has 65 tasks across 10 companies. Each task gives an agent a
company SOP handbook (PDF/DOCX), a mock workplace (Gmail, Slack, Jira, Calendar, Shopify through MCP) and workbooks,
and grades it with deterministic rubric checks (right emails, right Slack posts, right workbook rows, no forbidden
actions). This folder compiles each handbook into a typed, quote-grounded **policy KB** and gives it to the agent.

## Results (Claude Haiku 5.5, OpenHands harness)

| Arm | What the agent gets | Test mean reward | Strict pass, all 65 tasks × 4 |
|---|---|---|---|
| A0 | the benchmark's MCP tools only | 72.5 | 10.8% |
| A1 | A0 + `policy__*` tools over the KB | no gain (62.8 vs 64.7 on 12 dev tasks) | – |
| **A2** | A1 + SOP brief + drafted task checklist in the system prompt | **80.8** | 18.8% |
| R | A0 + the interwhen verifiers (per-task Python; start checklist, PreToolUse and Stop hooks) | 82.7 | 21.2% |
| **A2+R** | A2 with the interwhen verifiers layered on top (`--rhooks`) | **85.7** | **26.5%** |

- A2+R − A0 on all 65 tasks: +15.8 [+7.3, +25.0] mean reward. Weak models gain +15 to +28; strong models
  (Opus 5.5, Gemini argon) gain nothing or lose a little: structure breaks 7–10% of criteria they already pass.
- Dev (20 tasks: CareIG, Crestwood, Vanguard) was used for all development; test (45 tasks) was run once per frozen
  version. Full tables: [RESULTS.md](RESULTS.md), [RESULTS_SWEEP.md](RESULTS_SWEEP.md) (8 models).

## Pipeline

### Offline, once per task corpus

| Step | Module | Output (`kb/<task>/`) |
|---|---|---|
| 1. Anchor the corpus | `vrag/k0.py` | `k0/{corpus.json, policy.md, cases.md}`: every document as blocks `D1.0001…` (kind, level, section, exact text); table rows keep their header; policy documents are separated from case documents by content |
| 2. Compile the KB | `vrag/compile.py` (author claude-opus-5.5; optional reviewer gpt-5.6-sol) | `kb.json` (`vrag/schema.py`): four calls in parallel, ENTITIES (definitions, people + authority, channels, files, tables), STRUCTURE (templates, procedure index), RULES, then one call per PROCEDURE |
| 3. Rebuild text + lint | `compile.materialize`, `vrag/lint.py` | `lint.json`: the model returns **block pointers**, the text is rebuilt verbatim from K0; every quote must occur in the cited blocks; templates with any ungrounded wording are flagged `grounded: false` |
| 4. Fact sheet of the task's world | `vrag/envdump.py`, `vrag/facts.py` | `env.txt` (instruction, clock, mailbox, Slack, calendar, Jira, workbooks) and `facts_kb_seed.txt` (per item: facts in the data, SOP blocks that apply, open decisions with evidence; it locates, it does not decide) |
| 5. Task checklist (+ guards) | `vrag/guards.py`, `vrag/pipeline.py` | `plan_kb_seed.txt` (concrete steps for this task, labelled "may contain mistakes") and `guards_kb_seed.json` (executable guard specs and completion obligations, each self-tested on synthetic examples; failing specs are disabled) |
| 6. Package + freeze | `vrag/package.py`, `vrag/freeze.py` | the per-task policy package mounted in the container; `runs/FREEZE_*.json` hashes |

Tiers: `kb` = compiled from the handbook and instruction only; `kb_seed` = also sees the task's initial data
(`env.txt`), the same information the interwhen verifiers were built with. Rubrics and `tests/` are never read.

**The schema** (`vrag/schema.py`, pydantic) is the heart of it. Every item carries `refs: [{blocks, quote}]`:
`definitions`, `people` (role, email, slack, aliases, **authority**: what they may approve), `channels` (Slack,
email, Jira…), `files` (sheets, columns, rules such as append-only), `templates` (exact subject/body with
`[PLACEHOLDERS]`, to/cc/channel), `procedures` (trigger, ordered steps with actions, conditions, failure branches,
local rules), `rules` (kind, when, then, unless, params, severity), `tables`, `open_questions`. See
[examples/finance_meridian_partners_158b9045/](examples/finance_meridian_partners_158b9045/) for a compiled
`kb.json` (26 procedures, 186 rules, 39 templates), its lint report, fact sheet, checklist and guards.

### Runtime

- **Tools** (`vrag/runtime/policy_pkg/policy_server.py`, a FastMCP server mounted inside the harness's own MCP
  proxy, so tool names are `policy__*`). They render the KB as readable text, not raw JSON:
  `overview()` (start here: definitions, procedure index, people, hard rules), `procedure(id)` (ordered playbook
  with exact SOP text and block ids), `find(query)` (BM25), `read(block or section)`, `template(id, values)` (exact
  wording with placeholders filled, unfilled ones listed), `rules(query)`, `who(query)`, `business_days(start, days)`
  (computed with the company calendar), and in some arms `run`, `check`, `verify_action`, `verify_completion`.
- **Prompt** (`vrag/runtime/vrag_runner.py`, `vrag/brief.py`): A2 appends a compact SOP brief (hard rules, procedure
  index, definitions) and the task checklist to the system prompt.
- **Gate** (A3; `vrag/runtime/policy_pkg/gate.py`): our deterministic PreToolUse/Stop gate from `guards_*.json`.
  It fired too rarely to help (+1.0); layering the interwhen verifiers (`--rhooks`) worked better.
- Harness integration: `vrag/harbor_agent.py` (Harbor agents subclassing the OpenHands agent; upload the package and
  start the proxy with the policy toolset), `vrag/run_arm.py`, `vrag/sweep.py`, `vrag/monitor.py`.

### Analysis

`vrag/report.py`, `stats.py` (paired bootstrap), `tables.py`, `failures.py` (per-criterion fixed/broken across
arms), `replay.py` (replay trajectories through the gate offline), `walkthrough.py` (one trial as readable markdown).

## Setup

```bash
git clone https://github.com/surge-ai/handbook benchmark/handbook/handbook   # the benchmark (vrag/paths.py expects it here)
cd benchmark/handbook && uv venv --python 3.12 .venv && uv pip install -e '.[dev]'
.venv/bin/python -m pytest && .venv/bin/ruff check vrag tests
```

- Models are reached through an OpenAI-compatible endpoint at `127.0.0.1:3141/v1` (`vrag/llm.py`; plain-string
  message content, exact model-id check, disk cache in `cache/`). The agent containers reach it via a bridge on the
  Docker host; see `vrag/bridge.py`.
- The R and A2+R arms need the benchmark's interwhen verifier runner (`agent_harness.interwhen_agent`, per-task
  verifiers under `handbook/docker/openhands-runner/interwhen_sop/verifiers`).
- Docker's default address pools allow about 29 concurrent task networks; keep concurrency at 26 or less.

```bash
python -m vrag.k0                                                # anchor every corpus (or: python -m vrag.k0 <task> ...)
python -m vrag.compile <task>                                    # kb.json (+ lint.json)
python -m vrag.pipeline --tiers kb_seed                          # checklists/guards for every compiled KB
python -m vrag.facts --split all                                 # fact sheets
python -m vrag.run_arm A2 dev --tier kb_seed --n 12              # structure only
python -m vrag.run_arm A2 test --tier kb_seed --rhooks --n 12    # structure + interwhen
python -m vrag.stats 'X=A2-kb_seed-rhooks-test*' 'Y=A0-test*'    # paired comparison with CI
```

## What we learned

1. **Tools alone do not help.** The gain came from putting the structure in front of the agent (brief + checklist).
2. **Pointer-based compilation** (the model returns block ids; text is copied from the source) removes paraphrase and
   invented wording, which matters because agents copy template text verbatim into emails and posts.
3. **Structure and runtime verification are complementary**: A2+R beat both A2 (+5.0, significant) and R (+3.0).
4. **Checklists can be wrong**; label them as drafts and keep the SOP text one call away.
5. **Headroom decides the sign.** Report fixed vs broken criteria per model, not only the mean.
