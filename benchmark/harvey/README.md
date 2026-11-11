# Harvey LAB firm-knowledge: a quote-grounded firm index and verifier tools

[Harvey LAB](https://github.com/harveyai/harvey-labs) firm-knowledge has 250 questions written by lawyers about a
synthetic law firm's document system (266 client matters, 9,288 files: Word, email, spreadsheets, slides). Answers
are graded per criterion: the right matters, the document that proves each, no wrong extras. There is no SOP here:
the "structure" is an index of facts about every file and every matter, and the agent uses it to **check** its
answer.

## Results (Claude Haiku 5.5, effort high)

Measured within the same trajectory: the agent works as the plain harness, its answer at the moment it tries to
finish is "before"; then the verifier tools appear, it checks once, and its final answer is "after". Two judges
(claude-sonnet-5, gpt-5.6-sol); two independent trials per task.

| Tasks | Criterion pass | All-pass (task fully right) | Precision | Recall |
|---|---|---|---|---|
| **held-out 150** (AHE test 70 + the 80 tasks outside the split) | 59.6 → **70.4** (+10.8 [+8.0, +13.7]) | 23.2 → **31.7** (+8.5 [+5.0, +12.3]) | +9.9 | +11.5 |
| test 70 | 60.2 → 71.8 (+11.6) | 25.7 → 36.4 (+10.7) | +15.2 | +12.0 |
| never seen in any design step (123) | +10.2 | +7.7 | +8.1 | +10.7 |

Judge noise (same answers graded twice) is 0.4–0.7% of criteria; verification fixed 83–178 and broke 8–21 criteria
per 70–80-task trial. Cost: about 55 s and 5 steps on top of a ~740 s run. Full report:
[docs/DSH_REPORT.md](docs/DSH_REPORT.md); the design story: [docs/APPROACH.md](docs/APPROACH.md),
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ITERATIONS.md](docs/ITERATIONS.md).

## Pipeline

### Offline: build the Firm Verifier (FV) index (`kb/fv/`)

| Step | Module | What it does |
|---|---|---|
| 1. Corpus text (K0) | `vharvey/k0.py` | every file to text with the benchmark's own `parse-doc` in its sandbox image, so the index sees exactly what the agent's `read` sees |
| 2. Document cards | `vharvey/fv/docs.py` (claude-sonnet-5) | one card per file: stage (draft / execution version / executed / filed), date, parties, status and outcome statements, practice-area signals, client role, relief sought, **terms**, **issues**. Every list item must carry a quote of 12–300 characters copied from the file; `--reground` drops any item whose quote is not found verbatim (after markup normalisation); `--extend-long` reads the middle of long files (+18.6K grounded items) |
| 3. Vocabulary | `vharvey/fv/vocab.py` (Opus proposes, Sonnet maps) | canonical keys and synonyms for practice areas (24), terms (318) and issues (311), so `MFN`, `most favoured nation` and `most-favored-nation clause` are one key |
| 4. Matter cards | `vharvey/fv/matters.py` (claude-opus-5.5) | one card per matter from its document cards: client and aliases, description, matter type, primary and secondary practice areas, client role, counterparties, status + date, outcome + date, opened/closed dates, relief sought, terms in executed documents vs drafts only, issues analysed vs mentioned. Controlled values; every value has `evidence: [{path, quote}]`; null when the files do not establish it |
| 5. Freeze | `vharvey/fv/build_all.py` | runs 2–4 and writes `runs/FREEZE_fv_<tag>.json` (sha256 of the vocabulary, every matter card and the runtime code) |

The build never reads task questions or rubrics. Examples: [examples/](examples/) (two matter cards, one document
card, a vocabulary excerpt).

### Runtime: deterministic verifier tools (`vharvey/fv/api.py`, no model calls)

| Tool | Answer |
|---|---|
| `fv_check(matter_id, field, value)` / `fv_check_many(checks)` | TRUE / FALSE / SECONDARY (practice area held but not primary) / NOT_FOUND (term or issue absent from every file) / UNKNOWN (the index has no evidence; never a reason to drop) + `actual` + evidence `{path, quote}` + note. Fields: `practice_area`, `client_role`, `status`, `outcome`, `closed_year`, `opened_year`, `relief_sought_by_client`, `term.<key>`, `issue.<key>` |
| `fv_matter(matter_id)`, `fv_doc(path)` | the verified card |
| `fv_check_complete(conditions, matters)` | matters meeting all conditions that are **missing** from the agent's list (each with a path + quote per condition) and listed matters the index **contradicts**; warns when the conditions match very many matters |

Served over HTTP by `vharvey/fv/server.py` (`POST /fv/<tool>`, `GET /health` → freeze tag and digest;
`FV_FREEZE_TAG=<tag>` refuses to start if any file differs from the freeze).

### Giving the tools to the agent: "verify late"

Given from the first step, the agent used the verifier *instead of* searching (first verifier call at step 1.4,
search calls 19 → 8, half the matters looked at). So the reported system hides the tools until the agent ends its
turn, then adds them and asks once: verify each matter in your answer, run the completeness check, open the cited
files, fix the answer. Two harness integrations:

- **LAB's own harness** (`vharvey/runner.py`, `arms.py`, `fv/arm.py`): arms A0, V, VC, VL, VLC (VLC = verify late +
  completeness, the best).
- **DSH harness** ([dsh/](dsh/)): `fv-gate.mjs` is a DSH plugin. On the root agent's first `agent/turn-stopping` it
  snapshots `output/` (the plain answer), registers the `fv_*` tools (calling the HTTP service) and steers one
  verification message; `fv-late.yml` / `fv-start.yml` are the patch rows; `assets.json` holds the tool schemas and
  messages (generated by `vharvey/fv/dsh_assets.py`); `haiku-copilot.json` is the model config. To use it, copy
  these into the harness's `benchmarks/harvey/` (`plugins/`, `fv/`) and `models/`; `vharvey/dsh.py` builds specs,
  runs and grades, `vharvey/dsh_analysis.py` attributes every changed criterion to the verifier call behind it and
  measures judge noise.

## Setup

```bash
git clone https://github.com/harveyai/harvey-labs benchmark/harvey/harvey-labs     # vharvey/paths.py expects it here
cd benchmark/harvey && uv venv --python 3.12 .venv
uv pip install -e ./harvey-labs httpx tiktoken json-repair rank-bm25 pytest ruff
docker pull ghcr.io/harveyai/lab-sandbox:latest && docker tag ghcr.io/harveyai/lab-sandbox:latest lab-sandbox:latest
.venv/bin/python -m pytest tests -q && .venv/bin/ruff check vharvey tests
```

Models are reached through an OpenAI-compatible endpoint (`FRONTIER_URL`, default `127.0.0.1:3141/v1`;
`vharvey/proxy.py`). `vharvey/sse_facade.py` adds SSE streaming in front of a non-streaming endpoint for harnesses
that stream (DSH).

```bash
python -m vharvey.k0                                         # corpus text
python -m vharvey.fv.docs --workers 64                       # document cards
python -m vharvey.fv.build_all --tag v1 --skip-docs          # reground, long files, vocabulary, matter cards, freeze
python -m vharvey.fv.server                                  # verifier service on 127.0.0.1:3150
python -m vharvey.batch --run VLC-dev --arm VLC --models claude-haiku-5.5 --tasks dev --trials 2   # LAB harness
python -m vharvey.dsh specs RUN --split test --arm late && python -m vharvey.dsh run RUN && python -m vharvey.dsh grade RUN
python -m vharvey.dsh_analysis RUN --regrade                 # before/after, attribution, judge noise
python -m vharvey.viewer RUN,RUN-pregate index               # dashboard in logs/viewer/
```

## What we learned

1. **Quote-grounded cards** make verdicts checkable: the agent can open the cited file instead of trusting the index.
2. **UNKNOWN ≠ FALSE.** Agents are told to drop a matter only on FALSE with evidence that addresses the question.
3. **Precision gains come from checks; recall gains from the completeness check.** Every precision fix followed a
   FALSE/SECONDARY verdict on that matter; most recall fixes followed a `fv_check_complete` lead.
4. **Remaining failures**: literal-but-wrong verdicts (the matter *file* is open although the *deal* closed),
   completeness leads outside a rubric's narrower population, and a broadness warning that made the agent hedge.
5. **Offer the tools late.** Early tools replace search; late tools add checks on top of it.
