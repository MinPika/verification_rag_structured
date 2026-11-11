# Verification in the DSH harness: what changed and why (D-late-test, AHE test split, frozen v3-dsh, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 60.3 | 70.7 | +10.4 [+6.0, +15.4] |
| all-pass | 23.6 | 35.7 | +12.1 [+5.0, +20.0] |
| precision criterion | 41.3 | 58.0 | +16.7 [+7.2, +26.8] |
| required-matter recall | 69.6 | 79.8 | +10.2 [+5.4, +16.1] |

**Same, without the 50 task ids in dev.txt** (53 trials):

| metric | before | after | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 59.4 | 68.6 | +9.3 [+4.8, +14.7] |
| all-pass | 22.6 | 32.1 | +9.4 [+1.9, +17.9] |
| precision criterion | 43.4 | 55.7 | +12.3 [+1.9, +23.6] |
| required-matter recall | 66.8 | 77.3 | +10.5 [+4.3, +18.0] |

Trials: 70. Gate fired and the agent called the verifier in 70 trials; the answer changed in 70.

## Is it noise?

- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification note), so the noise floor is measured by grading identical answers twice (below).
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 4 of 759 criteria (0.5%). Verification changed 108 criteria in 70 trials; judge noise alone would flip about 4, in both directions.
- **Direction:** 87 of the 108 changed criteria were fixed and 21 broken. Noise flips both ways equally; two-sided sign test p = 9.9e-11.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | broken | rewrite: dropped/uncited despite TRUE verdicts | 2 |
| document | broken | verifier: dropped after a non-TRUE verdict (fv_matter) | 1 |
| document | fixed | verifier: completeness lead, confirmed and added | 17 |
| matter | broken | rewrite: dropped/uncited despite TRUE verdicts | 10 |
| matter | broken | rewrite: dropped/uncited without a verifier call on it | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (practice_area=mergers_acquisitions→SECONDARY) | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 41 |
| matter | fixed | verifier: checked, then added/cited | 5 |
| matter | fixed | rewrite: added/cited without a verifier call on it | 1 |
| number | broken | answer changed (verifier called) | 1 |
| number | fixed | answer changed (verifier called) | 1 |
| other | broken | answer changed (verifier called) | 3 |
| other | fixed | answer changed (verifier called) | 8 |
| precision | broken | verifier lead: added a matter outside the reference set | 2 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 14 |

**Summary:** 4 broken by answer changed (verifier called), 13 broken by rewrite, 2 broken by verifier, 2 broken by verifier lead, 9 fixed by answer changed (verifier called), 1 fixed by rewrite, 77 fixed by verifier

## Examples (open the task in the Trials tab, run D-late-test)

- **fixed · document · task 001 C-005** — verifier: completeness lead, confirmed and added
  - rubric: Provides or identifies a document from 1038-00001 (Cascade Retail) showing the Second Request: any of joint-status-report.docx, case-assessment-memo.docx, or letter-ftc-meet-and-confer.docx. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1038-00001": ["completeness lead", "practice_area=antitrust_competition\u2192TRUE", "issue.hsr_second_request=analysed\u2192TRUE", "client_role=defendant\u2192TRUE"]}
- **fixed · matter · task 142 C-001** — verifier: checked, then added/cited
  - rubric: Identifies matter 1001-00003 (Ardent Capital Partners; $620M multi-site healthcare-services acquisition) as a qualifying acquisition.
  - verifier facts: {"1001-00003": ["practice_area=mergers_acquisitions\u2192TRUE"]}
- **fixed · matter · task 142 C-006** — rewrite: added/cited without a verifier call on it
  - rubric: Identifies matter 1003-00004 (Harrowgate PE; $980M specialty-retailer take-private) as a qualifying acquisition.
  - verifier facts: {"1003-00004": []}
- **fixed · number · task 187 C-001** — answer changed (verifier called)
  - rubric: Identifies matter 1042-00004 (Brightfield Cloud, the $22M Codelaunch acqui-hire merger) as a qualifying 2023 software/SaaS acquisition deal with a stated indemnification cap of 35%.
  - verifier facts: {}
- **fixed · precision · task 040 C-002** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any qualifying matter outside 1020-00003 (Greenfield Ag).
  - verifier facts: {"1008-00002": ["fv_matter", "practice_area=capital_markets\u2192TRUE", "outcome=withdrawn\u2192UNKNOWN"]}
- **broken · document · task 001 C-006** — rewrite: dropped/uncited despite TRUE verdicts
  - rubric: Provides or identifies a document from 1041-00001 (Solara Digital) showing the Second Request: any of substantial-compliance-certification-letter.docx or custodian-identification-collection-protocol.docx. Naming the file or clearly describing it both satisfy t
  - verifier facts: {"1041-00001": ["issue.hsr_second_request=analysed\u2192TRUE", "practice_area=antitrust_competition\u2192TRUE"]}
- **broken · document · task 147 C-038** — verifier: dropped after a non-TRUE verdict (fv_matter)
  - rubric: Provides or identifies a document from 1007-00006 evidencing the delivered disclosure schedules: any of disclosure-schedules-buyer-form.docx (schedules delivered pursuant to the June 6, 2025 Stock Purchase Agreement) or stock-purchase-agreement-execution.docx 
  - verifier facts: {"1007-00006": ["completeness lead", "fv_matter"]}
- **broken · matter · task 186 C-023** — rewrite: dropped/uncited without a verifier call on it
  - rubric: Identifies matter 1013-00006 (Genome Dx, the $140M assay-line divestiture) as a qualifying matter.
  - verifier facts: {"1013-00006": []}
- **broken · matter · task 189 C-004** — verifier: dropped after a non-TRUE verdict (practice_area=mergers_acquisitions→SECONDARY)
  - rubric: Identifies matter 1002-00004 (Pinnacle Ventures) as a qualifying matter opened in 2022.
  - verifier facts: {"1002-00004": ["practice_area=mergers_acquisitions\u2192SECONDARY"]}
- **broken · number · task 005 C-001** — answer changed (verifier called)
  - rubric: Identifies matter 1038-00001 (Cascade Retail, $4.7B) as a billion-dollar-plus M&A deal that drew a Second Request.
  - verifier facts: {}
- **broken · precision · task 024 C-009** — verifier lead: added a matter outside the reference set
  - rubric: Does not assert any qualifying matter outside: 1008-00001 (Lumos Analytics); 1012-00001 (Stonefield Logistics); 1019-00002 (Whitmore Aerospace); 1038-00002 (Cascade Retail).
  - verifier facts: {"1043-00001": ["completeness lead", "practice_area=banking_finance\u2192TRUE", "term.revolving_credit_facility=present\u2192TRUE"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 750 | 58 | +8% |
| model steps | 21.1 | 5.1 | +24% |

70 trials. Agent seconds include tool execution and model latency through the proxy.
