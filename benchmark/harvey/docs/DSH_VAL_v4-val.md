# Verification in the DSH harness: what changed and why (D-v4-val, AHE validation split, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 54.2 | 62.8 | +8.6 [-0.6, +17.5] |
| all-pass | 22.5 | 35.0 | +12.5 [-5.0, +32.5] |
| precision criterion | 44.4 | 66.7 | +22.2 [+2.8, +44.4] |
| required-matter recall | 64.1 | 68.6 | +4.4 [-13.7, +19.3] |

Trials: 20. Gate fired and the agent called the verifier in 20 trials; the answer changed in 20.

## Is it noise?

- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification note), so the noise floor is measured by grading identical answers twice (below).
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 1 of 180 criteria (0.6%). Verification changed 32 criteria in 20 trials; judge noise alone would flip about 1, in both directions.
- **Direction:** 29 of the 32 changed criteria were fixed and 3 broken. Noise flips both ways equally; two-sided sign test p = 2.6e-06.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | fixed | verifier: completeness lead, confirmed and added | 7 |
| document | fixed | verifier: checked, then added/cited | 3 |
| matter | broken | verifier: dropped after a non-TRUE verdict (term.indemnity_basket=280000000→FALSE) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (client_role=defendant→FALSE) | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 11 |
| matter | fixed | verifier: checked, then added/cited | 4 |
| precision | broken | verifier lead: added a matter outside the reference set | 1 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 3 |
| precision | fixed | rewrite: wrong matter removed without a verifier call on it | 1 |

**Summary:** 2 broken by verifier, 1 broken by verifier lead, 1 fixed by rewrite, 28 fixed by verifier

## Examples (open the task in the Trials tab, run D-v4-val)

- **fixed · document · task 050 C-020** — verifier: completeness lead, confirmed and added
  - rubric: For matter 1017-00001 (Aurelius Media), provides or identifies block-trade-agreement-execution.docx as the executed firm-commitment block-trade agreement. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1017-00001": ["completeness lead"]}
- **fixed · document · task 249 C-010** — verifier: checked, then added/cited
  - rubric: Provides or identifies the document preservation / litigation hold notice for matter 1021-00008 (Verimark Hospitality): any of preservation-notice-vhg-company-wide.docx, preservation-notice-vcr-custodians.docx. Naming the file or clearly describing it both sat
  - verifier facts: {"1021-00008": ["fv_matter"]}
- **fixed · precision · task 007 C-003** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any qualifying matter outside: 1001-00001 (Ardent Capital Partners); 1003-00001 (Harrowgate PE); 1032-00001 (Halcyon Semi); 1038-00001 (Cascade Retail); 1041-00001 (Solara Digital).
  - verifier facts: {"1038-00009": ["practice_area=antitrust_competition\u2192SECONDARY", "contradicted by completeness"]}
- **fixed · precision · task 160 C-008** — rewrite: wrong matter removed without a verifier call on it
  - rubric: Does not assert any qualifying matter outside: 1007-00007 (Vantage Mobility); 1008-00009 (Lumos Analytics); 1009-00004 (Skybridge Fintech); 1017-00008 (Aurelius Media); 1022-00007 (Northgate Telecom); 1025-00006 (Quorum Insurance); 1038-00010 (Cascade Retail).
  - verifier facts: {"1022-00008": []}
- **broken · matter · task 020 C-001** — verifier: dropped after a non-TRUE verdict (term.indemnity_basket=280000000→FALSE)
  - rubric: Identifies matter 1005-00001 (Nexford Industrial) as the largest incremental-facility matter.
  - verifier facts: {"1005-00001": ["term.incremental_facility=analysed\u2192TRUE", "term.indemnity_basket=280000000\u2192FALSE", "practice_area=banking_finance\u2192TRUE"]}
- **broken · matter · task 202 C-012** — verifier: dropped after a non-TRUE verdict (client_role=defendant→FALSE)
  - rubric: Identifies matter 1034-00001 (Jonathan Caldwell) as a qualifying matter.
  - verifier facts: {"1034-00001": ["client_role=defendant\u2192FALSE"]}
- **broken · precision · task 020 C-003** — verifier lead: added a matter outside the reference set
  - rubric: Does not assert any qualifying matter outside 1005-00001 (Nexford Industrial).
  - verifier facts: {"1041-00003": ["completeness lead"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 597 | 41 | +7% |
| model steps | 20.4 | 4.2 | +21% |

20 trials. Agent seconds include tool execution and model latency through the proxy.
