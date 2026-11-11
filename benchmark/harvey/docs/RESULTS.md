# Results: Haiku 5.5 on Harvey LAB firm-knowledge (verifiers only, no structuring)

**Setup:** dual judges (claude-sonnet-5 + gpt-5.6-sol), effort high, LAB harness unchanged except the arm's tools. Δ is each arm minus A0 on the same tasks, with a paired bootstrap 95% CI over tasks.

**Read with care: the noise is large.** Two identical A0 runs on the same 15 dev tasks differed by −0.115 criterion pass (CI [−0.22, −0.03]), with a mean absolute per-task difference of 0.15. With one trial per task, differences under about 0.1 are not reliable, and the task-level CI understates the uncertainty. k=2 reruns are in progress for A0 and VLC on dev.

## Dev 50 (k=1; all design iterations happened here, labelled dev-informed)

| run | tasks | trials/task | criterion pass | all-pass | precision criterion | required-matter recall | turns | secs |
|---|---|---|---|---|---|---|---|---|
| A0 | 50 | 1 | 0.671 | 0.270 | 0.510 | 0.735 | 30.6 | 506 |
| V1: FV tools from start | 50 | 1 | 0.596 (−0.075 [−0.170, +0.014]) | 0.260 (−0.010) | **0.735 (+0.224 [+0.082, +0.367])** | 0.600 (−0.135 [−0.277, +0.002]) | 13.8 | 179 |
| V2: + verifier fixes, "search first" | 50 | 1 | 0.662 (−0.009) | 0.260 (−0.010) | 0.602 (+0.092) | 0.669 (−0.065) | 16.5 | 226 |
| VC: V2 + completeness check | 50 | 1 | 0.666 (−0.005) | 0.270 (+0.000) | 0.622 (+0.112) | 0.707 (−0.028) | 11.7 | 129 |
| VL: verify late (tools appear at first `finish`) | 50 | 1 | 0.640 (−0.031) | 0.290 (+0.020) | 0.551 (+0.041) | 0.676 (−0.059) | 34.0 | 597 |
| **VLC: verify late + completeness check** | 50 | 1 | **0.717 (+0.045 [−0.043, +0.134])** | **0.390 (+0.120 [+0.000, +0.240])** | 0.633 (+0.122 [−0.010, +0.255]) | 0.780 (+0.045 [−0.060, +0.149]) | 35.4 | 630 |

**Attribution** (`logs/attribution_*.json`), per required matter that one run got and the other missed:
- **VL:** 41 gained and 55 lost. 49 of the losses were matters the VL run never looked at, i.e. search variance between runs. Only 2 were lost because of a verifier verdict.
- **VLC:** 61 gained, 19 of them through completeness leads. 57 lost:
  - 31 never looked at;
  - 18 checked TRUE but still judged missing (answer wording / evidence);
  - 8 after a non-TRUE verdict, mostly UNKNOWN on a key the vocabulary does not resolve (`underwriting_structure`), which Haiku treated as "drop" against instructions.
- **VLC residual failures by criterion type (vs A0):**

  | Criterion type | A0 | VLC |
  |---|---|---|
  | precision | 27 | 20 |
  | required matter | 121 | 113 |
  | evidence document | 24 | **39** |

  Matters added from completeness leads often come without the proof document. Planned fix for v3: return evidence paths with each lead.

## Test 60 (single labelled look per frozen system: FV v2.2, arms VL and VLC; first 60 test tasks in split-hash order)

| run | tasks | trials/task | criterion pass | all-pass | precision criterion | required-matter recall | turns | secs |
|---|---|---|---|---|---|---|---|---|
| A0 | 60 | 1 | 0.580 | 0.200 | 0.362 | 0.649 | 32.7 | 626 |
| **VL** | 60 | 1 | **0.656 (+0.076 [−0.006, +0.159])** | **0.308 (+0.108 [+0.017, +0.208])** | **0.509 (+0.147 [+0.034, +0.259])** | 0.731 (+0.082 [−0.024, +0.190]) | 37.0 | 702 |
| VLC | 60 | 1 | 0.641 (+0.061 [−0.010, +0.128]) | 0.217 (+0.017 [−0.050, +0.092]) | 0.431 (+0.069 [−0.034, +0.172]) | 0.733 (+0.084 [−0.017, +0.178]) | 37.5 | 664 |

- VL improves every metric on test. All-pass rises from 20% to 31% and the precision criterion from 36% to 51% (both CIs exclude 0).
- On dev, VLC was the better arm; on test, VL is. With k=1 and the noise level above, **the two cannot be ranked**. Both beat A0 on test in criterion pass and recall.
- **Search variance dominates single tasks.** In test task 193 (OFAC, 84 matters), VL's answer already had only 37 matters *before* the gate (A0 found about 84), so VL scored 0.38 vs 0.99. This has nothing to do with the verifier: before the gate, VL is A0. The within-trial analysis below removes this noise.

## The causal estimate: same trajectory, graded before vs after the verification step

In VL/VLC the agent behaves exactly like A0 until its first `finish`. We rebuild `response.md` as it was at that moment (replaying the agent's `write`/`edit` calls; `vharvey/pregate.py`) and grade it with the same judges. Pre vs post is then a paired, within-trial effect of verification, with no search variance.

Coverage: trials are skipped where the answer was written through bash before the gate (7 per run) or where the agent ended without calling `finish`, so the gate never fired (2–5 per run).

| arm, split | matched trials | criterion pass | all-pass | precision criterion | required-matter recall |
|---|---|---|---|---|---|
| VL test (pre → post) | 49 | 0.617 → 0.628 (+0.011 [−0.030, +0.062]) | 0.316 → 0.337 (+0.020) | 0.479 → 0.553 (+0.074 [−0.021, +0.181]) | 0.716 → 0.704 (−0.012) |
| VL dev | 39 | 0.649 → 0.663 (+0.015 [−0.012, +0.039]) | 0.269 → 0.295 (+0.026) | 0.487 → 0.553 (+0.066) | 0.684 → 0.670 (−0.014) |
| **VLC test** | 51 | **0.625 → 0.679 (+0.055 [+0.017, +0.097])** | 0.206 → 0.245 (+0.039 [+0.000, +0.088]) | **0.316 → 0.429 (+0.112 [+0.041, +0.194])** | 0.716 → 0.764 (+0.047 [−0.010, +0.121]) |
| **VLC dev** (k=2, both trials) | 81 | **0.621 → 0.738 (+0.117 [+0.053, +0.185])** | **0.302 → 0.426 (+0.123 [+0.043, +0.210])** | **0.519 → 0.637 (+0.119 [+0.050, +0.194])** | **0.690 → 0.785 (+0.095 [+0.024, +0.175])** |

Trial-matched (`vharvey.pregate.paired`); bootstrap over trials.

**Within-trial attribution, VLC test** (`logs/attribution_VLC-test60.json`):
- **Gained:** 42 required-matter criteria; 34 of these came through completeness leads.
- **Lost:** 15. Of these:
  - 8 followed a non-TRUE verdict: `fee_shifting` reported draft-only in 3 matters; a primary-vs-secondary practice area; an UNKNOWN treated as "drop";
  - 6 were checked TRUE but still failed;
  - 1 other.
- **Precision criteria:** 5 fixed, 0 broken.

**Within-trial attribution, VL test:** precision criteria 6 fixed, 2 broken; the effect on matters is small.

## Dev 50 with k=2 (A0 vs VLC; two trials per task)

| run | tasks | trials/task | criterion pass | all-pass | precision criterion | required-matter recall | turns | secs |
|---|---|---|---|---|---|---|---|---|
| A0 | 50 | 2 | 0.656 | 0.290 | 0.490 | 0.718 | 32.0 | 591 |
| **VLC** | 50 | 2 | **0.721 (+0.065 [+0.005, +0.126])** | **0.385 (+0.095 [+0.020, +0.175])** | **0.628 (+0.138 [+0.031, +0.240])** | 0.771 (+0.053 [−0.020, +0.128]) | 35.2 | 627 |

## Bottom line (Haiku 5.5)
- **Verify late plus completeness check (VLC) is the system that works.**
  - Dev, k=2: +6.5 points criterion pass, +9.5 points all-pass, +13.8 points precision vs A0, all significant.
  - Within the same trajectories: +5.5 criterion / +11.2 precision on test, and +11.7 / +11.9 on dev (all significant).
  - k=2 on test is running.
- **Precision checks alone at the end (VL)** have a small causal effect (+1 point). VL's large test gap over A0 was mostly run-to-run variance.
- **Offering the verifiers from the start (V1/V2/VC)** cuts Haiku's search effort in half, which cancels the precision gains.
