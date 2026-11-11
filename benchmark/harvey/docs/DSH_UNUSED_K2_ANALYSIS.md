# Verification in the DSH harness: what changed and why (U-late-k2, 80 tasks outside the AHE split, frozen v3-dsh, trial 2, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 62.4 | 69.5 | +7.1 [+3.5, +10.9] |
| all-pass | 21.2 | 28.7 | +7.5 [+2.5, +13.1] |
| precision criterion | 44.2 | 51.9 | +7.8 [+0.6, +14.9] |
| required-matter recall | 72.8 | 79.9 | +7.2 [+2.5, +11.8] |

**Same, without the 50 task ids in dev.txt** (70 trials):

| metric | before | after | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 63.0 | 70.5 | +7.5 [+3.5, +11.9] |
| all-pass | 20.0 | 28.6 | +8.6 [+2.9, +15.0] |
| precision criterion | 44.8 | 54.5 | +9.7 [+1.5, +17.9] |
| required-matter recall | 74.4 | 81.1 | +6.7 [+1.8, +12.1] |

Trials: 80. Gate fired and the agent called the verifier in 80 trials; the answer changed in 80.

## Is it noise?

- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification note), so the noise floor is measured by grading identical answers twice (below).
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 6 of 888 criteria (0.7%). Verification changed 109 criteria in 80 trials; judge noise alone would flip about 6, in both directions.
- **Direction:** 88 of the 109 changed criteria were fixed and 21 broken. Noise flips both ways equally; two-sided sign test p = 6.1e-11.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | broken | rewrite: dropped/uncited despite TRUE verdicts | 5 |
| document | fixed | verifier: completeness lead, confirmed and added | 8 |
| document | fixed | verifier: checked, then added/cited | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=intellectual_property→FALSE) | 2 |
| matter | broken | verifier: dropped after a non-TRUE verdict (client_role=licensor→FALSE) | 2 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=litigation_general→SECONDARY) | 1 |
| matter | broken | rewrite: dropped/uncited despite TRUE verdicts | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (term.escrow=5→FALSE) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (fv_matter) | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 53 |
| matter | fixed | verifier: checked, then added/cited | 4 |
| number | broken | answer changed (verifier called) | 4 |
| number | fixed | answer changed (verifier called) | 3 |
| other | broken | answer changed (verifier called) | 3 |
| other | fixed | answer changed (verifier called) | 10 |
| precision | broken | verifier lead: added a matter outside the reference set | 1 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 9 |

**Summary:** 7 broken by answer changed (verifier called), 6 broken by rewrite, 7 broken by verifier, 1 broken by verifier lead, 13 fixed by answer changed (verifier called), 75 fixed by verifier

## Examples (open the task in the Trials tab, run U-late-k2)

- **fixed · document · task 055 C-002** — verifier: completeness lead, confirmed and added
  - rubric: Provides or identifies final-offering-memorandum.docx from 1045-00001 (Belmont Ridge Bank). Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1045-00001": ["completeness lead", "practice_area=capital_markets\u2192TRUE", "opened_year=2026\u2192FALSE"]}
- **fixed · document · task 143 C-020** — verifier: checked, then added/cited
  - rubric: Provides or identifies offer-to-purchase-agreement-execution.docx from 1039-00004 as the executed agreement carrying the fee. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1039-00004": ["term.reverse_termination_fee=present\u2192TRUE", "practice_area=mergers_acquisitions\u2192TRUE"]}
- **fixed · number · task 118 C-003** — answer changed (verifier called)
  - rubric: Identifies matter 1006-00005 (Crestline Packaging) as a qualifying settlement we recovered, at $1,575,000.
  - verifier facts: {}
- **fixed · precision · task 077 C-009** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any qualifying matter outside: 1006-00004 (Crestline Packaging); 1008-00005 (Lumos Analytics); 1011-00003 (Meridian Consumer Brands); 1021-00004 (Verimark Hospitality); 1038-00006 (Cascade Retail Holdings).
  - verifier facts: {"1014-00004": ["practice_area=intellectual_property\u2192TRUE", "relief_sought_by_client=injunction\u2192UNKNOWN", "relief_sought_by_client=injunctive\u2192TRUE", "practice_area=intellectual_property\u2192TRUE"]}
- **broken · document · task 136 C-025** — rewrite: dropped/uncited despite TRUE verdicts
  - rubric: Provides or identifies a document from 1001-00007 evidencing that RWI was bound: any of stock-purchase-agreement-execution.docx or rw-insurance-policy-binder.docx. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1001-00007": ["practice_area=mergers_acquisitions\u2192TRUE", "term.rw_insurance=analysed\u2192TRUE"]}
- **broken · matter · task 076 C-004** — verifier: dropped after a non-TRUE verdict (practice_area=intellectual_property→FALSE)
  - rubric: Identifies matter 1018-00006 (Penterra Pharmaceuticals) as a qualifying matter, with negotiated tiered royalty rates of 8%, 11%, and 14% in the executed license.
  - verifier facts: {"1018-00006": ["practice_area=intellectual_property\u2192FALSE", "term.royalty_rate=14\u2192TRUE"]}
- **broken · matter · task 086 C-001** — verifier: dropped after a non-TRUE verdict (client_role=licensor→FALSE)
  - rubric: Identifies matter 1013-00005 (GenomeDx) as a qualifying matter, contributing an asserted royalty rate of 18.0%.
  - verifier facts: {"1013-00005": ["practice_area=intellectual_property\u2192TRUE", "client_role=licensor\u2192FALSE"]}
- **broken · matter · task 109 C-007** — verifier: dropped after a non-TRUE verdict (practice_area=litigation_general→SECONDARY)
  - rubric: Identifies matter 1025-00005 (Quorum Insurance) as a qualifying matter.
  - verifier facts: {"1025-00005": ["practice_area=litigation_general\u2192SECONDARY", "status=open\u2192TRUE"]}
- **broken · matter · task 134 C-003** — verifier: dropped after a non-TRUE verdict (term.escrow=5→FALSE)
  - rubric: Identifies matter 1004-00003 (Cobalt Ventures) as a qualifying matter.
  - verifier facts: {"1004-00003": ["term.escrow=5\u2192FALSE"]}
- **broken · matter · task 143 C-009** — verifier: dropped after a non-TRUE verdict (fv_matter)
  - rubric: Identifies matter 1038-00009 (Cascade Retail) as a qualifying strategic-buyer deal.
  - verifier facts: {"1038-00009": ["fv_matter", "term.reverse_termination_fee=present\u2192FALSE"]}
- **broken · number · task 118 C-005** — answer changed (verifier called)
  - rubric: Identifies matter 1012-00006 (Stonefield Logistics) as a qualifying settlement we recovered, at $425,000.
  - verifier facts: {}
- **broken · precision · task 108 C-012** — verifier lead: added a matter outside the reference set
  - rubric: Does not assert any qualifying matter outside: 1005-00005 (Nexford Industrial); 1006-00005 (Crestline Packaging); 1007-00005 (Vantage Mobility); 1008-00007 (Lumos Analytics); 1012-00006 (Stonefield Logistics); 1021-00006 (Verimark Hospitality); 1027-00003 (Pel
  - verifier facts: {"1035-00002": ["completeness lead", "practice_area=litigation_general\u2192TRUE", "outcome=settled\u2192TRUE", "fv_matter"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 748 | 60 | +8% |
| model steps | 24.0 | 4.8 | +20% |

80 trials. Agent seconds include tool execution and model latency through the proxy.
