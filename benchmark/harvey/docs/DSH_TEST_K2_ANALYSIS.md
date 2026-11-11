# Verification in the DSH harness: what changed and why (D-late-test-k2, AHE test split, frozen v3-dsh, second trial, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 60.1 | 72.9 | +12.8 [+7.8, +18.7] |
| all-pass | 27.9 | 37.1 | +9.3 [+2.1, +17.1] |
| precision criterion | 52.9 | 66.7 | +13.8 [+4.3, +23.9] |
| required-matter recall | 67.6 | 81.4 | +13.8 [+7.3, +21.4] |

**Same, without the 50 task ids in dev.txt** (53 trials):

| metric | before | after | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 58.1 | 70.7 | +12.6 [+6.5, +19.2] |
| all-pass | 24.5 | 33.0 | +8.5 [+0.0, +17.9] |
| precision criterion | 54.7 | 66.0 | +11.3 [+0.0, +22.6] |
| required-matter recall | 65.7 | 78.8 | +13.1 [+5.7, +22.1] |

Trials: 70. Gate fired and the agent called the verifier in 70 trials; the answer changed in 70.

## Is it noise?

- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification note), so the noise floor is measured by grading identical answers twice (below).
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 3 of 759 criteria (0.4%). Verification changed 91 criteria in 70 trials; judge noise alone would flip about 3, in both directions.
- **Direction:** 83 of the 91 changed criteria were fixed and 8 broken. Noise flips both ways equally; two-sided sign test p = 7.6e-17.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | broken | verifier: dropped after a non-TRUE verdict (fv_matter) | 1 |
| document | broken | rewrite: dropped/uncited without a verifier call on it | 1 |
| document | broken | rewrite: dropped/uncited despite TRUE verdicts | 1 |
| document | fixed | verifier: completeness lead, confirmed and added | 6 |
| document | fixed | answer changed (verifier called) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (term.comfort_letter_fee=delivered→FALSE) | 1 |
| matter | broken | rewrite: dropped/uncited despite TRUE verdicts | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 40 |
| matter | fixed | verifier: checked, then added/cited | 1 |
| number | fixed | answer changed (verifier called) | 1 |
| other | broken | answer changed (verifier called) | 1 |
| other | fixed | answer changed (verifier called) | 22 |
| precision | broken | verifier lead: added a matter outside the reference set | 2 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 12 |

**Summary:** 1 broken by answer changed (verifier called), 3 broken by rewrite, 2 broken by verifier, 2 broken by verifier lead, 24 fixed by answer changed (verifier called), 59 fixed by verifier

## Examples (open the task in the Trials tab, run D-late-test-k2)

- **fixed · document · task 008 C-003** — verifier: completeness lead, confirmed and added
  - rubric: Provides or identifies a model HSR filing document from 1003-00001 (Harrowgate PE): either hsr-filing-transmittal-letter.docx (the executed firm transmittal letter) or hsr-form-acquiring-person-draft.docx (the firm-prepared Notification and Report Form). Namin
  - verifier facts: {"1003-00001": ["completeness lead", "practice_area=antitrust_competition\u2192TRUE", "fv_matter"]}
- **fixed · document · task 097 C-010** — answer changed (verifier called)
  - rubric: States that no executed executive-employment-agreement DOCUMENT in the firm's Labor & Employment book contains a compensation clawback provision.
  - verifier facts: {}
- **fixed · matter · task 009 C-007** — verifier: checked, then added/cited
  - rubric: Identifies matter 1038-00002 (Cascade Retail) as a qualifying matter.
  - verifier facts: {"1038-00002": ["practice_area=banking_finance\u2192TRUE", "term.financial_covenant=present\u2192TRUE", "fv_matter"]}
- **fixed · precision · task 008 C-004** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any matter other than 1003-00001 (Harrowgate PE) as the most recent Antitrust & Competition matter where the firm itself made an HSR filing.
  - verifier facts: {"1038-00009": ["fv_matter", "practice_area=antitrust_competition\u2192SECONDARY", "issue.hsr_filing=analysed\u2192FALSE", "contradicted by completeness"]}
- **broken · document · task 009 C-016** — verifier: dropped after a non-TRUE verdict (fv_matter)
  - rubric: Provides or identifies a document from 1038-00002 (Cascade Retail) showing its springing financial maintenance covenant: any of credit-agreement-execution-version.docx, closing-memorandum.docx, or borrowers-counsel-legal-opinion.docx. Naming the file or clearl
  - verifier facts: {"1038-00002": ["practice_area=banking_finance\u2192TRUE", "term.financial_covenant=present\u2192TRUE", "fv_matter"]}
- **broken · document · task 024 C-006** — rewrite: dropped/uncited without a verifier call on it
  - rubric: Provides or identifies amendment-no-3-senior-credit-agreement-execution.docx from 1012-00001 (Stonefield Logistics) as the executed credit-agreement-class document to pull. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1012-00001": []}
- **broken · document · task 147 C-045** — rewrite: dropped/uncited despite TRUE verdicts
  - rubric: Provides or identifies a document from 1032-00005 evidencing the delivered disclosure schedules: any of disclosure-schedules-comments.docx (C&H mark-up of the schedules to the August 10, 2023 Agreement and Plan of Merger) or merger-agreement-execution-version.
  - verifier facts: {"1032-00005": ["completeness lead", "practice_area=mergers_acquisitions\u2192TRUE"]}
- **broken · matter · task 039 C-012** — verifier: dropped after a non-TRUE verdict (term.comfort_letter_fee=delivered→FALSE)
  - rubric: Identifies matter 1045-00001 (Belmont Ridge Bank) as a qualifying matter.
  - verifier facts: {"1045-00001": ["term.comfort_letter_fee=delivered\u2192FALSE", "fv_matter"]}
- **broken · other · task 124 C-029** — answer changed (verifier called)
  - rubric: Places matter 1027-00003 (Pellegrino Capital) in the no-operative-court-venue bucket (arbitration, JAMS).
  - verifier facts: {}
- **broken · precision · task 103 C-003** — verifier lead: added a matter outside the reference set
  - rubric: Does not assert any qualifying matter outside: 1017-00004 (Aurelius Media — Aldrich dispute); 1017-00005 (Aurelius Media — Hale investigation).
  - verifier facts: {"1033-00005": ["completeness lead", "practice_area=labor_employment\u2192TRUE", "term.equity_acceleration=analysed\u2192TRUE"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 726 | 52 | +7% |
| model steps | 22.5 | 4.8 | +22% |

70 trials. Agent seconds include tool execution and model latency through the proxy.
