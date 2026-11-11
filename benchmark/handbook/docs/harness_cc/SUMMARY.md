# Haiku 5.5: OpenHands harness vs Claude Code harness (2026-11-06)

Same model (Haiku 5.5, effort max), tasks, MCP tools and grader; only the agent harness differs. OpenHands is the
HANDBOOK.md harness (model through the Copilot proxy, 4 trials per task); Claude Code is Harbor's Claude Code agent
plus the task's system prompt (vrag/claude_code_agent.py), called directly at Anthropic with 1 trial per task
(k = 1, so pass@4 and pass^4 are not reported). 65/65 trials scored; cost $32.98. Tables: [RESULTS.md](RESULTS.md)
(analyze.py); trace labels for the 15 largest per-task differences: data/labels.jsonl.

| harness | mean reward | strict pass@1 | pass@1 (N-1) |
|---|---|---|---|
| OpenHands (k=4) | 71.5 | 10.8 | 28.5 |
| OpenHands, one trial per task (range over its 4 trials) | 70.3–73.0 | 9.2–12.3 | 27.7–30.8 |
| Claude Code (k=1) | 75.2 | 16.9 | 29.2 |
| Claude Code − OpenHands (paired, 95% CI) | +3.6 [−2.0, +9.4] | +6.2 [−3.1, +15.4] | +0.8 [−10.8, +12.3] |

For scale, our methods in the OpenHands harness: A2+R 83.2, text retrieval + exec tool 84.8 mean reward.

## Findings

1. **Small, non-significant gain, and it is mostly context handling.** OpenHands lost 11 of 260 trials (4.2%) to
   "Message exceeds token limit" (scored 0, e.g. reading a 122-page SOP in one call); Claude Code had none.
   Without those trials OpenHands averages 74.7 and the gap shrinks to +0.6 [−4.2, +5.1].
2. **What Claude Code does differently.** 2.1x more tool calls (45.6 vs 21.8 per trial), 2.6x more SOP reads, and
   it reads selectively: table of contents first, then the relevant pages; `pdftotext` + `sed` by section;
   oversized tool output saved to a file and paged with Read. Spreadsheets through Bash + Python (openpyxl), 7.2
   calls per trial. PDFs reach the model as documents (one case: a signed consent form that OpenHands' text reader
   showed as "Signature: ____"). Built-ins used: Bash 743, Read 314, ToolSearch 121, Write 69, Edit 7; no web
   search, no subagents. About 103k thinking tokens per trial.
3. **Where Claude Code wins (8 largest gains):** context crashes in OpenHands (4), better arithmetic or
   reconciliation in its own scripts (2), completing steps OpenHands skipped (2).
4. **Where it loses (7 largest losses): caution, not tools.** Holding sends as drafts, asking the user to
   confirm, refusing a send the user explicitly approved, or extra SOP steps the task excluded (H-REASONING 4,
   H-STOP 2, H-OVERACT 1). A harness artefact feeds this: Claude Code adds the machine's real date to its system
   prompt; the model cites it in 60/65 trials and on date-driven tasks stalls on the conflict with the task's date
   (e.g. hr_crestwood d93daa01: computed the three correct interview slots, then asked to confirm the date and
   created nothing; 0/4 criteria vs 4/4 for OpenHands). A faked container clock would remove this.
5. **Task-level swings are large in both directions** (≥ 10 points: 20 tasks ahead, 15 behind) and partly
   single-trial noise; the domain means range from −3.0 (medical) to +7.7 (finance, logistics).

Conclusion: a production harness gives Haiku a small, non-significant improvement, almost all of it from robust
context handling; our verification methods add +12–13 points on top of the benchmark harness.
