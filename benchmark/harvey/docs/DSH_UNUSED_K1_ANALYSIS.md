# Verification in the DSH harness: what changed and why (U-late-k1, 80 tasks outside the AHE split, frozen v3-dsh, trial 1, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 55.7 | 68.8 | +13.1 [+8.1, +18.4] |
| all-pass | 20.6 | 26.2 | +5.6 [+1.2, +11.2] |
| precision criterion | 51.9 | 54.5 | +2.6 [-7.8, +13.0] |
| required-matter recall | 64.0 | 78.8 | +14.9 [+8.3, +21.9] |

**Same, without the 50 task ids in dev.txt** (70 trials):

| metric | before | after | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 58.0 | 69.8 | +11.9 [+7.2, +17.1] |
| all-pass | 20.7 | 25.7 | +5.0 [+0.0, +10.7] |
| precision criterion | 54.5 | 55.2 | +0.7 [-11.2, +11.9] |
| required-matter recall | 67.6 | 80.7 | +13.1 [+6.9, +20.3] |

Trials: 80. Gate fired and the agent called the verifier in 80 trials; the answer changed in 79.

## Is it noise?

- **Unchanged answers:** in the 1 trials whose answer did not change, 0 of 4 criteria flipped (0.0%), purely from grading the same text again.
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 6 of 888 criteria (0.7%). Verification changed 197 criteria in 80 trials; judge noise alone would flip about 6, in both directions.
- **Direction:** 178 of the 197 changed criteria were fixed and 19 broken. Noise flips both ways equally; two-sided sign test p = 1.5e-33.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | fixed | verifier: completeness lead, confirmed and added | 10 |
| document | fixed | verifier: checked, then added/cited | 3 |
| matter | broken | rewrite: dropped/uncited despite TRUE verdicts | 2 |
| matter | broken | verifier: dropped after a non-TRUE verdict (client_role=licensor→FALSE) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=litigation_general→SECONDARY) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=mergers_acquisitions→SECONDARY) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=intellectual_property→FALSE) | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 73 |
| matter | fixed | verifier: checked, then added/cited | 55 |
| number | broken | answer changed (verifier called) | 4 |
| number | fixed | answer changed (verifier called) | 3 |
| other | broken | answer changed (verifier called) | 1 |
| other | fixed | answer changed (verifier called) | 25 |
| precision | broken | verifier lead: added a matter outside the reference set | 7 |
| precision | broken | rewrite: wrong matter asserted without a verifier lead | 1 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 8 |
| precision | fixed | rewrite: wrong matter removed without a verifier call on it | 1 |

**Summary:** 5 broken by answer changed (verifier called), 3 broken by rewrite, 4 broken by verifier, 7 broken by verifier lead, 28 fixed by answer changed (verifier called), 1 fixed by rewrite, 149 fixed by verifier

## Examples (open the task in the Trials tab, run U-late-k1)

- **fixed · document · task 038 C-013** — verifier: checked, then added/cited
  - rubric: Provides or identifies a document from 1027-00001 (Pellegrino Capital) showing the executed over-allotment grant: either the executed underwriting agreement or the closing checklist. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1027-00001": ["practice_area=capital_markets\u2192TRUE", "term.over_allotment_option=present\u2192TRUE"]}
- **fixed · document · task 044 C-004** — verifier: completeness lead, confirmed and added
  - rubric: Provides or identifies a document from 1016-00003 (Dunmore Energy) supporting the closed offering and its lead underwriter: any of closing-binder-toc.docx, cross-receipt.docx, purchase-agreement.docx, or bring-down-dd-certificate.docx. Naming the file or clear
  - verifier facts: {"1016-00003": ["completeness lead", "outcome=transaction_closed\u2192TRUE", "practice_area=capital_markets\u2192TRUE", "client_role=issuer\u2192TRUE"]}
- **fixed · number · task 118 C-001** — answer changed (verifier called)
  - rubric: Identifies matter 1021-00006 (Verimark Hospitality) as a qualifying settlement we recovered, at $87,500,000.
  - verifier facts: {}
- **fixed · precision · task 044 C-003** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any matter other than 1016-00003 (Dunmore Energy) as the largest completed offering.
  - verifier facts: {"1018-00001": ["fv_matter", "outcome=transaction_closed\u2192TRUE", "issue.lock_up_waiver=analysed\u2192TRUE"]}
- **fixed · precision · task 224 C-007** — rewrite: wrong matter removed without a verifier call on it
  - rubric: Does not assert any qualifying matter outside: 1017-00009 (Aurelius Media); 1026-00004 (Briarwood Family Office, Linden at Gramercy Park JV); 1027-00004 (Pellegrino Capital); 1031-00004 (Metropolitan Transit Development Corp. (MTDC)); 1036-00004 (Fairwater REI
  - verifier facts: {}
- **broken · matter · task 076 C-001** — rewrite: dropped/uncited despite TRUE verdicts
  - rubric: Identifies matter 1013-00005 (GenomeDx) as a qualifying matter, with an asserted reasonable-royalty rate of 18%.
  - verifier facts: {"1013-00005": ["practice_area=intellectual_property\u2192TRUE"]}
- **broken · matter · task 086 C-001** — verifier: dropped after a non-TRUE verdict (client_role=licensor→FALSE)
  - rubric: Identifies matter 1013-00005 (GenomeDx) as a qualifying matter, contributing an asserted royalty rate of 18.0%.
  - verifier facts: {"1013-00005": ["client_role=licensor\u2192FALSE", "practice_area=intellectual_property\u2192TRUE", "fv_matter"]}
- **broken · matter · task 109 C-007** — verifier: dropped after a non-TRUE verdict (practice_area=litigation_general→SECONDARY)
  - rubric: Identifies matter 1025-00005 (Quorum Insurance) as a qualifying matter.
  - verifier facts: {"1025-00005": ["practice_area=litigation_general\u2192SECONDARY"]}
- **broken · matter · task 168 C-002** — verifier: dropped after a non-TRUE verdict (practice_area=mergers_acquisitions→SECONDARY)
  - rubric: Identifies matter 1002-00004 (Pinnacle Ventures) as a qualifying matter.
  - verifier facts: {"1002-00004": ["practice_area=mergers_acquisitions\u2192SECONDARY", "status=dormant\u2192TRUE", "fv_matter"]}
- **broken · matter · task 208 C-005** — verifier: dropped after a non-TRUE verdict (practice_area=intellectual_property→FALSE)
  - rubric: Identifies matter 1018-00006 (Penterra Pharma) as a qualifying IP matter, with Marcus Delgado as responsible partner and Catherine Bloom as billing partner.
  - verifier facts: {"1018-00006": ["practice_area=intellectual_property\u2192FALSE"]}
- **broken · number · task 188 C-010** — answer changed (verifier called)
  - rubric: Reports 1 qualifying valued deal for Tax.
  - verifier facts: {}
- **broken · precision · task 025 C-005** — verifier lead: added a matter outside the reference set
  - rubric: Does not assert any qualifying matter outside: 1008-00001 (Lumos Analytics); 1012-00001 (Stonefield Logistics); 1019-00002 (Whitmore Aerospace); 1038-00002 (Cascade Retail); 1021-00001 (Verimark Hospitality).
  - verifier facts: {"1043-00001": ["completeness lead"]}
- **broken · precision · task 204 C-066** — rewrite: wrong matter asserted without a verifier lead
  - rubric: Does not assert any matter outside the following set as closed in 2024: 1001-00001 (Ardent Capital Partners); 1001-00002 (Ardent Capital Partners); 1001-00006 (Ardent Capital Partners); 1003-00001 (Harrowgate PE); 1006-00004 (Crestline Packaging); 1008-00004 (
  - verifier facts: {"1005-00004": ["fv_matter", "closed_year=2024\u2192TRUE"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 765 | 57 | +7% |
| model steps | 24.4 | 4.9 | +20% |

80 trials. Agent seconds include tool execution and model latency through the proxy.
