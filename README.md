# Verification for RAG: structuring a corpus offline so an agent can use and check it

Code from two studies of one question: **if a document corpus is compiled offline into a structured,
quote-grounded representation, can an LLM agent use it to act more correctly, and to verify its own answer?**

| Benchmark | Corpus | What we built | Main result (Claude Haiku 5.5) |
|---|---|---|---|
| [HANDBOOK.md](benchmark/handbook/) (Surge AI, 65 tasks) | one company SOP handbook per task (PDF/DOCX) + mailbox, Slack, workbooks | the SOP compiled into a typed **policy KB** (procedures, rules, templates, people, definitions); `policy__*` tools; a short SOP brief and a per-task checklist in the prompt; optionally the interwhen verifiers on top | test mean reward 72.5 → **80.8** (structure) → **85.7** (structure + interwhen); strict pass 10.8% → 26.5% on all 65 |
| [Harvey LAB firm-knowledge](benchmark/harvey/) (250 tasks) | a law firm's document system: 266 matters, 9,288 files | every file compiled into a **document card**, every matter into a **matter card**, each value with a verbatim quote; deterministic **verifier tools** (`fv_*`) the agent calls after drafting its answer | held-out 150 tasks, same trajectories before/after: criterion 59.6 → **70.4** (+10.8), all-pass 23.2 → **31.7** (+8.5) |

Each folder has its own README with the pipeline, every module, commands, results and lessons.

## The approach in one page

**Offline (once per corpus; frontier models allowed):**
1. **Anchor the corpus (K0).** Parse every document deterministically into small blocks with stable ids
   (`D1.0056`) and exact text. No model. Everything later points back here.
2. **Compile to a typed schema.** A frontier model (Opus) reads the corpus and fills a typed schema for the domain:
   - HANDBOOK: definitions, people and what they may approve, channels, files, templates, procedures (trigger +
     ordered steps + actions + conditions), rules (when/then/unless/severity);
   - Harvey: per document (stage draft/executed, date, parties, terms, issues), per matter (practice areas,
     client role, status, outcome, dates, relief, executed terms).
3. **Ground every value.** The model points at block ids or copies a quote; text is rebuilt from K0 or the quote is
   checked to exist verbatim. Ungrounded items are dropped or flagged (`lint`). This is what makes the structure
   trustworthy enough to act on.
4. **Normalise vocabulary.** Canonical keys and synonyms (e.g. "MFN" = "most favoured nation"), so lookups match.
5. **Per-task material (optional).** A fact sheet of everything the agent can observe at the start, and a drafted
   checklist for the task, labelled as possibly wrong.
6. **Freeze.** Hash every artefact; runs refuse an unfrozen or changed build. Test is run once per frozen system.

**At runtime (no extra model calls; deterministic code over the JSON):**
- **Tools in the harness** that render the structure as readable views or answer narrow questions with evidence:
  HANDBOOK `policy__overview/procedure/find/read/template/rules/who/business_days`; Harvey
  `fv_check/fv_check_many/fv_matter/fv_doc/fv_check_complete` (TRUE/FALSE/SECONDARY/NOT_FOUND/UNKNOWN + path +
  quote).
- **Prompt additions**: HANDBOOK a compact brief + the task checklist (this is where most of its gain came from);
  Harvey one verification request at the end.
- **When the tools appear matters.** Given from the first step, agents used the Harvey verifiers *instead of*
  searching (search calls 19 → 8, worse answers). Giving them only when the agent is about to finish ("verify late")
  keeps search intact and adds checks on top.

## Lessons that transfer

- **Tools alone did not help** (HANDBOOK A1: no gain). Agents call them rarely or shallowly. The gain came from the
  structure being *put in front of the agent* (brief + checklist) or *asked for at a decision point* (verify late).
- **Ground everything in verbatim text.** Paraphrased structure gets copied into answers; quotes can be checked.
- **Unknown is not false.** Every verdict distinguishes "the index says no, here is the quote" from "the index has
  no record"; agents are told never to drop an item on UNKNOWN.
- **Literal-but-wrong verdicts are the main failure.** E.g. "is the matter closed?" → FALSE because the matter file
  stays open after the deal closed. Report the neighbouring field (outcome) and tell the agent to drop an item only
  when the quote really contradicts the question.
- **Strong models have little headroom.** Structure breaks a few criteria a model already passes (7–10% in
  HANDBOOK); for Opus that outweighed the gains. Measure "fixed vs broken" per criterion, not only the mean.
- **Measure noise.** Grade identical answers twice (judge noise was 0.4–0.7% of criteria) and use paired,
  same-trajectory comparisons where possible.

## Applying it to a new benchmark (e.g. JobBench)

1. **Inventory the corpus** and what the grader checks (actions, documents, facts). Decide what the agent gets
   wrong today: run the plain agent on a train split and read failing criteria first.
2. **Write the domain schema** (start from `benchmark/handbook/vrag/schema.py` for procedure/rule corpora, or the
   card prompts in `benchmark/harvey/vharvey/fv/docs.py` and `matters.py` for document collections). Only fields that
   a failing criterion needs; every field carries `refs`/`evidence`.
3. **K0 + compile + lint** (copy `k0.py`, `compile.py`/`lint.py` or `fv/docs.py`, `fv/matters.py`, `fv/vocab.py`).
   Keep the "pointer or verbatim quote" rule.
4. **Expose it**: a small tool server over the JSON (`runtime/policy_pkg/policy_server.py` or `vharvey/fv/server.py`)
   plus either a prompt brief/checklist (procedural tasks) or a late verification gate (lookup/list tasks; DSH plugin
   in `benchmark/harvey/dsh/fv-gate.mjs`).
5. **Evaluate honestly**: train/validation/test split by task, frozen build before test, paired before/after
   analysis, attribution of every changed criterion to the tool call that caused it (`vharvey/dsh_analysis.py`).

## Repository map

```
benchmark/
  handbook/   vrag/ (K0, schema, compile, lint, facts, plan/guards, policy tools, gate, harness agents, runs, stats),
              tests/, docs/, RESULTS*.md, examples/<task>/ (a compiled kb.json, plan, fact sheet, guards)
  harvey/     vharvey/ (K0, fv/ build + runtime API + HTTP server, LAB and DSH runners, grading, analysis, dashboard),
              dsh/ (DSH harness plugin, patch rows, assets, model config), tests/, docs/, examples/ (matter and
              document cards, vocabulary excerpt)
```

Not included: the benchmarks themselves (clone them: [surge-ai/handbook](https://github.com/surge-ai/handbook),
[harveyai/harvey-labs](https://github.com/harveyai/harvey-labs)), compiled indexes for every task, run
trajectories, caches and virtual environments. The examples are derived from those benchmarks (HANDBOOK: Apache-2.0;
harvey-labs: MIT, Copyright (c) 2026 Harvey AI).
