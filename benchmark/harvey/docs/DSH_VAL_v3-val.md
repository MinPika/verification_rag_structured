# Verification in the DSH harness: what changed and why (D-v3-val, AHE validation split, Haiku 5.5)

Each trial runs plain DSH until the agent ends its turn; then the verifier tools appear and the agent is asked once to verify. The answer at that moment (**before**) is the plain-DSH answer of the trajectory; the final answer is **after**. Both are graded by the same two judges (claude-sonnet-5, gpt-5.6-sol); headline scores average the two judges, and in the per-criterion attribution a criterion counts as passed when at least one judge passes it.

## Headline (same trajectories, before → after verification)

| metric | before (plain DSH) | after (verified) | Δ points [95% CI] |
|---|---|---|---|
| criterion pass | 54.6 | 69.2 | +14.5 [+5.5, +26.7] |
| all-pass | 27.5 | 35.0 | +7.5 [+0.0, +20.0] |
| precision criterion | 47.2 | 69.4 | +22.2 [+5.6, +41.7] |
| required-matter recall | 54.7 | 68.5 | +13.8 [+2.0, +29.4] |

Trials: 20. Gate fired and the agent called the verifier in 20 trials; the answer changed in 20.

## Is it noise?

- **Unchanged answers:** none. The agent edited its answer in every trial (at least a verification note), so the noise floor is measured by grading identical answers twice (below).
- **Search noise:** none here. Before and after come from the same trajectory, so the search is identical.
- **Judge noise, measured:** the same before-answers graded twice flip 2 of 180 criteria (1.1%). Verification changed 31 criteria in 20 trials; judge noise alone would flip about 2, in both directions.
- **Direction:** 28 of the 31 changed criteria were fixed and 3 broken. Noise flips both ways equally; two-sided sign test p = 4.6e-06.

## Every criterion that changed, by cause

| criterion type | change | cause | criteria |
|---|---|---|---|
| document | fixed | verifier: completeness lead, confirmed and added | 6 |
| document | fixed | verifier: checked, then added/cited | 3 |
| document | fixed | rewrite: added/cited without a verifier call on it | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (client_role=adverse→UNKNOWN) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (status=active→UNKNOWN) | 1 |
| matter | broken | verifier: dropped after a non-TRUE verdict (term.snda=executed→UNKNOWN) | 1 |
| matter | fixed | verifier: completeness lead, confirmed and added | 11 |
| matter | fixed | verifier: checked, then added/cited | 1 |
| other | fixed | answer changed (verifier called) | 1 |
| precision | fixed | verifier: wrong matter checked, then removed/relabelled | 4 |
| precision | fixed | rewrite: wrong matter removed without a verifier call on it | 1 |

**Summary:** 3 broken by verifier, 1 fixed by answer changed (verifier called), 2 fixed by rewrite, 25 fixed by verifier

## Examples (open the task in the Trials tab, run D-v3-val)

- **fixed · document · task 090 C-016** — verifier: completeness lead, confirmed and added
  - rubric: Provides or identifies a document from 1033-00004 evidencing the willfulness allegation: answer-and-affirmative-defenses.docx. Naming the file or clearly describing it both satisfy this.
  - verifier facts: {"1033-00004": ["completeness lead", "practice_area=intellectual_property\u2192TRUE"]}
- **fixed · document · task 113 C-004** — rewrite: added/cited without a verifier call on it
  - rubric: Provides or identifies a document from 1010-00005 evidencing the filed TRO/PI motion: any of motion-for-tro-and-pi.docx, memo-in-support-of-tro-pi-motion.docx, or proposed-temporary-restraining-order.docx. Naming the file or clearly describing it both satisfy 
  - verifier facts: {"1010-00005": []}
- **fixed · document · task 164 C-003** — verifier: checked, then added/cited
  - rubric: Provides or identifies a closing-set instrument from 1006-00008 as proof the deal closed: any of bill-of-sale.docx, officer-certificate-buyer.docx, officer-certificate-seller.docx, indemnification-escrow-agreement.docx, or purchase-price-adjustment-escrow-agre
  - verifier facts: {"1006-00008": ["closed_year=2025\u2192TRUE", "status=closed\u2192TRUE", "fv_matter", "outcome=transaction_closed\u2192TRUE", "practice_area=mergers_acquisitions\u2192TRUE"]}
- **fixed · other · task 164 C-002** — answer changed (verifier called)
  - rubric: States that matter 1006-00008 closed on August 15, 2025.
  - verifier facts: {}
- **fixed · precision · task 007 C-003** — verifier: wrong matter checked, then removed/relabelled
  - rubric: Does not assert any qualifying matter outside: 1001-00001 (Ardent Capital Partners); 1003-00001 (Harrowgate PE); 1032-00001 (Halcyon Semi); 1038-00001 (Cascade Retail); 1041-00001 (Solara Digital).
  - verifier facts: {"1001-00004": ["practice_area=antitrust_competition\u2192SECONDARY", "fv_matter"], "1032-00005": ["practice_area=antitrust_competition\u2192SECONDARY", "outcome=terminated\u2192TRUE"], "1038-00009": []}
- **fixed · precision · task 152 C-019** — rewrite: wrong matter removed without a verifier call on it
  - rubric: Does not assert any qualifying matter outside: 1001-00003 (Ardent Capital Partners); 1005-00006 (Nexford Industrial); 1006-00007 (Crestline Packaging); 1008-00008 (Lumos Analytics); 1009-00003 (Skybridge Fintech); 1013-00006 (Genome Dx); 1037-00006 (Solstice B
  - verifier facts: {"1032-00004": []}
- **broken · matter · task 202 C-006** — verifier: dropped after a non-TRUE verdict (client_role=adverse→UNKNOWN)
  - rubric: Identifies matter 1021-00008 (Verimark Hospitality) as a qualifying matter.
  - verifier facts: {"1021-00008": ["client_role=adverse\u2192UNKNOWN"]}
- **broken · matter · task 202 C-010** — verifier: dropped after a non-TRUE verdict (status=active→UNKNOWN)
  - rubric: Identifies matter 1032-00005 (Halcyon Semi, the merger the DOJ sued to block) as a qualifying matter.
  - verifier facts: {"1032-00005": ["status=active\u2192UNKNOWN"]}
- **broken · matter · task 228 C-004** — verifier: dropped after a non-TRUE verdict (term.snda=executed→UNKNOWN)
  - rubric: Identifies 1043-00003 (Ironhaven Data, Loudoun edge facility financing) as a qualifying matter.
  - verifier facts: {"1043-00003": ["practice_area=real_estate\u2192TRUE", "term.snda=executed\u2192UNKNOWN"]}

## Latency (same trajectories)

| | before the gate (plain DSH) | verification (after the gate) | added |
|---|---|---|---|
| agent seconds | 652 | 50 | +8% |
| model steps | 21.4 | 4.5 | +21% |

20 trials. Agent seconds include tool execution and model latency through the proxy.
