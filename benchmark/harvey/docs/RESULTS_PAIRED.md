# 3 · Results: like-for-like comparisons (Haiku 5.5)

Every table compares approaches on **the same tasks with the same trial index**, so the number of trials is equal across rows. Train = the 50 dev tasks (all design iterations happened here). Test = the first 60 test tasks in split order, run once per frozen system (FV v2.2; arms VL and VLC).
Judges: claude-sonnet-5 + gpt-5.6-sol. *Criterion pass* = share of rubric criteria passed (mean of the two judges); *all-pass* = task fully correct (LAB's headline; 0.5 when the judges disagree); *precision criterion* = the "no matter outside the reference set" criterion; *required-matter recall* = share of "identifies matter X" criteria passed.

## Train (dev 50), one trial per task (t0) — all approaches

Tasks: **50** (the same for every row) · trials per task: **1** (trial index t0 for every arm)

| approach | criterion pass % | all-pass % | precision criterion % | required-matter recall % |
|---|---|---|---|---|
| A0 plain agent | 67.1 | 27.0 | 51.0 | 73.5 |
| V1 tools from start | 59.6 (-7.5 [-17.0, +1.4]) | 26.0 (-1.0 [-13.0, +11.0]) | 73.5 (+22.4 [+8.2, +36.7] *) | 60.0 (-13.5 [-27.7, +0.2]) |
| V2 tools from start + fixes | 66.2 (-0.9 [-8.1, +6.2]) | 26.0 (-1.0 [-10.0, +8.0]) | 60.2 (+9.2 [-2.0, +21.4]) | 66.9 (-6.5 [-18.4, +4.3]) |
| VC tools + completeness from start | 66.6 (-0.5 [-10.3, +9.6]) | 27.0 (+0.0 [-10.0, +10.0]) | 62.2 (+11.2 [-3.1, +25.5]) | 70.7 (-2.8 [-16.5, +10.4]) |
| VL verify late | 64.0 (-3.1 [-11.0, +3.6]) | 29.0 (+2.0 [-7.0, +11.0]) | 55.1 (+4.1 [-6.1, +14.3]) | 67.6 (-5.9 [-15.7, +2.7]) |
| VLC verify late + completeness | 71.7 (+4.5 [-4.3, +13.4]) | 39.0 (+12.0 [+0.0, +24.0]) | 63.3 (+12.2 [-1.0, +25.5]) | 78.0 (+4.5 [-6.0, +14.9]) |

In brackets: difference to A0 in points, paired over tasks, bootstrap 95% CI; * = CI excludes 0.

| approach | turns | wall clock (s) | prompt tokens (K, cumulative) | output tokens (K) | verifier calls |
|---|---|---|---|---|---|
| A0 plain agent | 30.6 | 506 | 1689 | 9.0 | 0.0 |
| V1 tools from start | 13.8 | 179 | 432 | 5.0 | 11.7 |
| V2 tools from start + fixes | 16.5 | 226 | 598 | 6.1 | 11.9 |
| VC tools + completeness from start | 11.7 | 129 | 418 | 4.4 | 10.2 |
| VL verify late | 34.0 | 597 | 1650 | 10.4 | 2.1 |
| VLC verify late + completeness | 35.4 | 630 | 1927 | 10.6 | 2.8 |

## Train (dev 50), two trials per task (t0 + t1) — A0 vs VLC

Tasks: **50** (the same for every row) · trials per task: **2** (trial index t0–t1 for every arm)

| approach | criterion pass % | all-pass % | precision criterion % | required-matter recall % |
|---|---|---|---|---|
| A0 plain agent | 65.6 | 29.0 | 49.0 | 71.8 |
| VLC verify late + completeness | 72.1 (+6.5 [+0.5, +12.6] *) | 38.5 (+9.5 [+2.0, +17.5] *) | 62.8 (+13.8 [+3.1, +24.0] *) | 77.1 (+5.3 [-2.0, +12.8]) |

In brackets: difference to A0 in points, paired over tasks, bootstrap 95% CI; * = CI excludes 0.

| approach | turns | wall clock (s) | prompt tokens (K, cumulative) | output tokens (K) | verifier calls |
|---|---|---|---|---|---|
| A0 plain agent | 32.0 | 591 | 1627 | 9.1 | 0.0 |
| VLC verify late + completeness | 35.2 | 627 | 1785 | 10.7 | 3.1 |

## Test (60), one trial per task (t0)

Tasks: **60** (the same for every row) · trials per task: **1** (trial index t0 for every arm)

| approach | criterion pass % | all-pass % | precision criterion % | required-matter recall % |
|---|---|---|---|---|
| A0 plain agent | 58.0 | 20.0 | 36.2 | 64.9 |
| VL verify late | 65.6 (+7.6 [-0.6, +15.9]) | 30.8 (+10.8 [+1.7, +20.8] *) | 50.9 (+14.7 [+3.4, +25.9] *) | 73.1 (+8.2 [-2.4, +19.0]) |
| VLC verify late + completeness | 64.1 (+6.1 [-1.0, +12.8]) | 21.7 (+1.7 [-5.0, +9.2]) | 43.1 (+6.9 [-3.4, +17.2]) | 73.3 (+8.4 [-1.7, +17.8]) |

In brackets: difference to A0 in points, paired over tasks, bootstrap 95% CI; * = CI excludes 0.

| approach | turns | wall clock (s) | prompt tokens (K, cumulative) | output tokens (K) | verifier calls |
|---|---|---|---|---|---|
| A0 plain agent | 32.7 | 626 | 1694 | 9.5 | 0.0 |
| VL verify late | 37.0 | 702 | 2452 | 11.4 | 2.2 |
| VLC verify late + completeness | 37.5 | 664 | 2160 | 11.7 | 3.3 |

## Test (60), two trials per task (t0 + t1) — A0 vs VLC

Tasks: **60** (the same for every row) · trials per task: **2** (trial index t0–t1 for every arm)

| approach | criterion pass % | all-pass % | precision criterion % | required-matter recall % |
|---|---|---|---|---|
| A0 plain agent | 61.1 | 23.3 | 36.6 | 68.4 |
| VLC verify late + completeness | 64.1 (+2.9 [-3.0, +8.6]) | 24.6 (+1.2 [-2.5, +5.4]) | 42.2 (+5.6 [-2.2, +13.4]) | 72.6 (+4.1 [-4.7, +11.9]) |

In brackets: difference to A0 in points, paired over tasks, bootstrap 95% CI; * = CI excludes 0.

| approach | turns | wall clock (s) | prompt tokens (K, cumulative) | output tokens (K) | verifier calls |
|---|---|---|---|---|---|
| A0 plain agent | 32.6 | 645 | 1637 | 9.5 | 0.0 |
| VLC verify late + completeness | 36.8 | 669 | 2243 | 11.4 | 3.5 |

## Same trajectory, before vs after the verification step

VL/VLC behave exactly like A0 until the first `finish`. Grading the answer as it was at that moment and the final answer of the **same** trajectory isolates what verification changed, with no search variance. Trials where the answer was written through bash before the gate, or where the agent never called `finish`, cannot be replayed and are excluded.

| approach, split | matched trials | criterion pass % | all-pass % | precision % | recall % |
|---|---|---|---|---|---|
| VL verify late, train | 39 | 64.9 → 66.3 (+1.5 [-1.2, +3.9]) | 26.9 → 29.5 (+2.6 [-3.8, +10.3]) | 48.7 → 55.3 (+6.6 [-1.3, +15.8]) | 68.4 → 67.0 (-1.4 [-8.4, +3.2]) |
| VLC verify late + completeness, train | 81 | 62.1 → 73.8 (+11.7 [+5.3, +18.5] *) | 30.2 → 42.6 (+12.3 [+4.3, +21.0] *) | 51.9 → 63.7 (+11.9 [+5.0, +19.4] *) | 69.0 → 78.5 (+9.5 [+2.4, +17.5] *) |
| VL verify late, test | 49 | 61.7 → 62.8 (+1.1 [-3.0, +6.2]) | 31.6 → 33.7 (+2.0 [-2.0, +7.1]) | 47.9 → 55.3 (+7.4 [-2.1, +18.1]) | 71.6 → 70.4 (-1.2 [-4.1, +0.8]) |
| VLC verify late + completeness, test | 101 | 61.1 → 67.4 (+6.4 [+2.8, +10.4] *) | 23.8 → 28.2 (+4.5 [+0.5, +9.4] *) | 33.5 → 44.3 (+10.8 [+5.2, +17.5] *) | 69.9 → 74.4 (+4.5 [+0.1, +9.6] *) |

**Why the same-trajectory gain is larger than the run-vs-run gain on test.** The run-vs-run comparison adds the large search variance of two independent runs (±11 points per 15 tasks), and it includes trials where the gate never fired or the answer was written through bash (~16% of VLC test trials), which behave as A0. The same-trajectory comparison removes both, and is the direct estimate of what the verification step itself changes.

## Noise floor

Two identical A0 runs on the same 15 dev tasks differed by −11.5 criterion points (CI [−21.8, −2.7]), with a mean absolute per-task difference of 14.7 points. Single-trial differences under ~10 points are not reliable; prefer the two-trial and the same-trajectory rows.
