# FV iterations on dev (Haiku 5.5, dev 50, k=1; every change is dev-informed and labelled as such)

## V1 (FV v1.1, `runs/FREEZE_fv_v1.1.json`)

| | A0 (base-dev50) | V1 (V1-dev50) |
|---|---|---|
| Criterion pass (48 paired tasks) | 0.665 | 0.587 (Δ −0.078, 95% CI [−0.18, +0.02]) |
| All-pass | 0.281 | 0.271 |
| **Precision criterion pass** (47 tasks) | 0.511 | **0.745** |
| Turns / wall clock / prompt tokens per trial | 30.6 / 506 s / 1.69M | **13.9 / 182 s / 0.44M** |

**What happened.** The verifiers did their job on precision: wrong inclusions fell a lot. But Haiku treated verification as a stop signal and searched only half as long. Of the 61 required matters that A0 found and V1 missed:
- **40 were never checked**: they were not found at all (search stopped early);
- **4 were checked and every check was TRUE**: the agent left them out anyway;
- **17 got a non-TRUE verdict**: verifier too strict or wrong.

V1 also found 63 required matters A0 had missed. Per-matter lists are in `logs/v1_lost_matters.txt`.

**Verifier errors seen (the 17), and the generic fix in V2:**

| Error | Example | Fix (generic) |
|---|---|---|
| Term-key granularity | `working_capital_adjustment` asked; the executed agreement has `net_working_capital_target` (it was in drafts under the asked key) | Directional near-match: an executed key containing all non-generic tokens of the asked key wins (`api._contained`). `management_fee_offset` can never match a plain `management_fee`. |
| Long executed agreements cut in the middle | MFN clause at character ~150K of a 268K credit agreement was never extracted | New pass reads the middle of all 728 truncated files (terms/issues only): **+18,596 grounded items** (`docs --extend-long`) |
| Execution copies with blank signature lines labelled "unsigned" | 69 `*-execution*` files | A file named execution / executed / signed / conformed counts as executed (`matters.EXEC_NAME`) |
| `closed_year` UNKNOWN (only 94/266 cards have a closing date), and the agent dropped matters on UNKNOWN | 186 (closed in 2023) | Fallback to the status date when status is closed/terminated/withdrawn; otherwise UNKNOWN plus a hint giving the outcome date |
| NOT_FOUND / draft-only treated as proof of absence | — | Notes now tell the agent to read the key document before excluding |
| Search stopped early | 40 never-checked matters | Prompt step 0: "the verifier does not find matters and does not tell you when you have found them all; search as thoroughly as without it" |

Already in V1 (v1 → v1.1, from the known-case check, before any agent run): practice area distinguishes the **primary** practice area (TRUE) from a secondary one (SECONDARY), because an ABS deal also carried `capital_markets`.

## V2 (FV v2, `runs/FREEZE_fv_v2.json`) and VC (V2 + completeness verifier, FV v2.1)

| run | criterion pass | all-pass | precision criterion | required-matter recall | turns | secs |
|---|---|---|---|---|---|---|
| A0 (base-dev50) | 0.667 | 0.276 | 0.521 | 0.730 | 30.6 | 505 |
| V2 | 0.660 (−0.007 [−0.08, +0.07]) | 0.265 | 0.615 (+0.094 [−0.03, +0.21]) | 0.667 (−0.063 [−0.19, +0.05]) | 16.3 | 225 |
| VC | 0.666 (−0.001 [−0.11, +0.10]) | 0.276 | 0.635 (+0.115 [−0.02, +0.26]) | 0.704 (−0.026 [−0.17, +0.12]) | 11.6 | 128 |

(49 paired tasks; one VC trial pair lost to a Docker start timeout. Δ vs A0 with a paired bootstrap 95% CI.)

- **V2:** the fixes removed most of V1's recall loss, and precision stays up. But Haiku still searches about half as much as A0, so the net is about 0.
- **VC:** adds `fv_check_complete(conditions, matters)`, which verifies the claim "my list is complete" against the index. Haiku called it in 48 of 49 tasks.
  - It offered 449 "missing" matters. 163 were reference matters, and Haiku added 160 of them.
  - The other 286 were wrong leads, mostly from loose conditions Haiku wrote: `practice_area` alone for a "largest offering" question, `term.non_compete` with no duration, or a value the index cannot express ("lock-up under 90 days").
  - Haiku mentioned 127 of those wrong leads in its answers without reading the documents, and searched even less (11.6 turns).
- **Diagnosis:** with the tools visible from the start, Haiku substitutes verification (and index leads) for search. Prompting ("search as thoroughly as without it") did not change this.

## VL / VLC: verify late (FV v2.2)
The tools are **hidden** until the agent first calls `finish`. That call is refused once; the FV tools are added to the live tool list, and the agent is asked to verify every matter in its `response.md`, fix the answer and finish again. Search behaviour before the gate is therefore exactly A0's. VLC also offers the completeness check at the gate.

**Effort:** both arms run as long as A0 (34–35 turns, about 600 s), so the gate fixed the search-effort collapse seen in V1, V2 and VC.

**Dev, k=1:**
- VL: criterion −0.031, all-pass +0.020.
- VLC: criterion +0.045, all-pass +0.120.

**Dev, k=2, VLC vs A0:** criterion **+0.065 [+0.005, +0.126]**, all-pass +0.095, precision +0.138.

**Within-trial effect** (the same trajectory graded before vs after the gate; see Results):
- VL: about +0.01, so the checks alone barely change answers.
- VLC on test: **+0.055 [+0.017, +0.097]** criterion pass and +0.112 precision. The completeness leads add reference matters (34 on test), and the checks fix precision criteria (5 fixed, 0 broken).

**Known v3 fixes (not applied; the frozen system stays as tested):**
- Return evidence paths with every completeness lead. Matters added from leads often lack the proof document (VLC dev: evidence-document failures 24 → 39).
- Resolve keys like `underwriting_structure` and `fee_shifting` better. Today an unresolved key comes back UNKNOWN, and Haiku sometimes drops the matter despite the instruction.
- Practice areas: SECONDARY dropped a reference matter once (1025-00005). Primary-vs-secondary is the reference's taxonomy, which the index can only approximate.
- The gate never fires when the agent ends without calling `finish` (2–5 trials per run). A stop check at loop end would cover them.
