# Harvey LAB firm-knowledge: what a task is, and one baseline run step by step

Run: `runs/labroot/results/smoke/001/t0/`. Model claude-haiku-5.5, plain LAB agent (A0), Copilot proxy. It was graded by two judges, claude-sonnet-5 and gpt-5.6-sol.

## 1. The environment: a synthetic law firm

- Calderwood & Harkness (C&H): 46 clients, 266 matters, 15 practice areas.
- 9,288 files: 8,055 .docx, 615 .eml, 573 .xlsx, 45 .pptx. About 134M tokens.
- Layout: `dms/matters/<client>-<matter>/<folder>/<file>`, e.g. `1003-00001/Memos & Analysis/second-request-strategy-memo.docx`.
- There is **no index**: no matter list, no practice-area field, no metadata. Client name, practice area, deal type and outcome only appear inside document text.
- All 250 tasks share the same corpus.

## 2. What a task is

`tasks/firm-knowledge/tasks/001/task.json` has three parts:

- **instructions**, the only thing the agent sees:
  > "I'm assembling a bank of our antitrust practice's deals that drew regulatory scrutiny. Pull every one of our antitrust matters where we drew an HSR second request, with the documents showing each request. Output: write your complete answer to `response.md`."
- **criteria**, hidden from the agent and used only by the judge. There are 7 atomic checks:

  | ID | Check |
  |---|---|
  | C-001 to C-003 | Identifies matter 1003-00001 / 1038-00001 / 1041-00001 as qualifying (recall) |
  | C-004 to C-006 | Names a document showing the request, e.g. "any of second-request-strategy-memo.docx or hsr-withdrawal-letter.docx" (evidence) |
  | C-007 | Asserts no qualifying matter outside an allowed set of 6 (precision) |

- **deliverable**: `response.md`.

Across all 250 tasks:
- Criteria types: matter identification 1,349; document/evidence 729; precision 241; numeric 180; classification 116.
- 42% of tasks need 5 or more matters; one needs 84.
- Scoring: each criterion gets pass/fail from an LLM judge. The task passes only if **all** criteria pass. The criterion pass rate is reported as a diagnostic.

## 3. The agent's harness (LAB's own, unchanged)

- **Tools:** `bash`, `read` (converts docx/xlsx/pptx to text), `write`, `edit`, `glob`, `grep`, `finish`. There is no search index.
- **Sandbox:** a Docker container; the corpus is mounted read-only at `/workspace/documents`.
- **Limits:** up to 200 turns; 60 s per shell command.

## 4. The run, step by step (36 turns, 12.8 min, ~1.2M input tokens)

| Turn | What the agent did | Why it matters |
|---|---|---|
| 1–3 | `ls -R documents`, counts 266 matters / 9,288 files, looks at folder names | Orients itself. There is nothing to read that summarises the firm. |
| 4 | Converts **every** file to text in its workspace with pandoc/unzip (`txt/`) | Builds its own throwaway "index", which costs minutes per task and is rebuilt on every task. |
| 5–9 | `grep "second request"` across all text; one grep **times out (60 s)**; retries with `timeout 50`, filename search | Keyword search over 134M tokens is slow, and many hits are false ("no second request was issued", "risk of a second request"). |
| 10–17 | Lists ~20 candidate matters; reads engagement letters to see the client and whether C&H was counsel; pickles all docs into Python | Separating real requests from mentions needs reading, not grep. |
| 18–19 | Regex: "issued / received / served / substantial compliance" near "second request"; excludes negations | Its own precision filter. |
| 20–29 | Reads key docs per candidate (strategy memos, compliance certifications, closing memos) | Confirms each matter, finds the evidence documents and outcomes. |
| 30 | `write response.md`: 6 matters, table, sources per matter | The deliverable. |
| 31–35 | Edits the file (removes an excluded matter, adds caveats) | Self-revision. |
| 36 | Final message; no more tool calls, so the loop ends (`no_tool_calls`) | |

**Answer:** 1003-00001, 1003-00003, 1032-00005, 1038-00001, 1038-00009, 1041-00001, each with dates, outcome and file paths.

## 5. Grading

Both judges passed 7/7, so this run is an **all-pass**. Excerpts from the judge's reasoning:
- C-004 pass: "names both second-request-strategy-memo.docx and hsr-withdrawal-letter.docx as sources under Matter 1003-00001"
- C-007 pass: "six qualifying matters … exactly match the allowed set"

This was an easy task: 3 required matters and a distinctive keyword. Harvey reports that strong models satisfy about half the criteria overall and drop to 0% all-pass as the number of required items grows. The usual failure is stopping before every matter has been found.

## 6. Why there is no SOP, and what replaces it

- **HANDBOOK:** the agent had to *act* (send emails, update sheets) by following a written policy (the SOP). Verifiers checked actions against the SOP's rules. A rule could be checked from the tool call alone, e.g. "an escalation email must go to X with subject Y".
- **Harvey:** the agent only *answers a question* from the corpus. There are no rules about procedure. A "correct" answer is a fact about the corpus: which matters qualify, and which documents show it. So a verifier can only check the answer against the corpus.
  - **Cheap and certain:** cited files exist in that matter; the matter id matches the client; a quoted fact appears in the cited file.
  - **The real failure, completeness:** "did you find all of them?" To check this you need to know the full set, so you need an index of the corpus.

This is why structure and verification are the same project here. One offline representation of the firm serves both:
- the agent queries it to enumerate;
- the verifier checks the agent's answer against it at the end.

Example feedback: "the index lists 6 matters with a second request; you cited 3; check 1003-00003, 1032-00005 and 1038-00009 or say why they don't qualify."
