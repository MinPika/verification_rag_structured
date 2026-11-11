# Overnight 2026-11-03 (x10): plan alternatives and the exec tool

Haiku 5.5 and Opus 5.5, all 65 tasks, 4 trials per task for the new arms (Opus A2 and R: 2). Code: runs/FREEZE_v10_overnight.json; code before the changes: runs/FREEZE_v10_pre.json.

## 1. Arms

### Haiku 5.5

| arm | tasks | trials | mean | strict | N-1 | test mean | test strict | test N-1 |
|---|---|---|---|---|---|---|---|---|
| A0 | 65 | 260 | 71.5 | 10.8 | 28.5 | 72.5 | 8.3 | 28.9 |
| A2 | 65 | 260 | 78.0 | 18.8 | 32.7 | 80.8 | 22.2 | 37.8 |
| A2 noplan | 65 | 258 | 68.9 | 11.7 | 23.5 | 69.9 | 11.9 | 23.9 |
| A2 facts | 65 | 260 | 69.3 | 11.5 | 22.3 | 72.5 | 13.9 | 26.7 |
| A2 facts+soft | 65 | 260 | 69.9 | 11.2 | 22.7 | 71.5 | 13.9 | 26.1 |
| R | 65 | 260 | 81.4 | 21.2 | 40.4 | 82.7 | 23.3 | 42.8 |
| A2+R | 65 | 259 | 83.2 | 26.5 | 43.5 | 85.7 | 31.1 | 52.2 |
| A2 noplan+R | 65 | 260 | 83.5 | 22.7 | 41.9 | 86.3 | 28.9 | 50.0 |
| A2 facts+soft+R | 65 | 260 | 82.6 | 22.7 | 41.5 | 84.8 | 28.3 | 47.2 |
| A1 text | 65 | 260 | 70.7 | 11.2 | 26.2 | 71.2 | 11.7 | 27.8 |
| A1 text+exec | 65 | 260 | 84.8 | 26.2 | 44.6 | 87.5 | 30.6 | 49.4 |
| A1 code | 65 | 260 | 78.4 | 21.5 | 31.2 | 80.8 | 24.4 | 33.9 |
| A1 code+exec | 65 | 260 | 84.1 | 24.6 | 42.3 | 86.1 | 26.1 | 47.8 |
| A1 code+exec+fin | 65 | 260 | 84.3 | 23.5 | 42.7 | 87.4 | 26.1 | 47.8 |

### Opus 5.5

| arm | tasks | trials | mean | strict | N-1 | test mean | test strict | test N-1 |
|---|---|---|---|---|---|---|---|---|
| A0 | 65 | 248 | 87.5 | 31.5 | 53.3 | 88.6 | 34.4 | 55.4 |
| A2 | 65 | 259 | 83.1 | 28.5 | 45.4 | 84.9 | 35.0 | 48.3 |
| A2 noplan | 65 | 260 | 80.8 | 15.8 | 36.2 | 80.3 | 16.1 | 37.2 |
| A2 facts | 65 | 259 | 79.7 | 22.1 | 40.6 | 78.9 | 24.1 | 40.9 |
| A2 facts+soft | 65 | 259 | 80.3 | 21.2 | 39.2 | 80.5 | 22.8 | 41.1 |
| R | 65 | 260 | 86.3 | 27.3 | 50.8 | 88.2 | 32.8 | 56.7 |
| A2+R | 65 | 248 | 86.8 | 25.4 | 50.4 | 89.2 | 30.0 | 57.2 |
| A2 noplan+R | 65 | 260 | 85.6 | 26.2 | 49.2 | 87.6 | 30.6 | 58.3 |
| A2 facts+soft+R | 65 | 260 | 86.3 | 25.4 | 48.8 | 88.3 | 31.7 | 55.6 |
| A1 text | 65 | 259 | 81.0 | 18.5 | 37.3 | 82.0 | 20.0 | 39.4 |
| A1 text+exec | 65 | 260 | 87.1 | 27.3 | 52.3 | 89.2 | 30.0 | 60.6 |
| A1 code | 65 | 260 | 83.1 | 20.0 | 36.9 | 84.5 | 22.8 | 40.6 |
| A1 code+exec | 65 | 260 | 86.2 | 25.4 | 43.8 | 87.8 | 25.6 | 50.0 |
| A1 code+exec+fin | 65 | 260 | 86.1 | 25.0 | 45.4 | 87.8 | 26.1 | 52.2 |

## 2. Questions (paired contrasts)

### Haiku 5.5 (all 65 tasks; paired over tasks, 95% bootstrap CI; * = CI excludes 0)

| question | contrast | n | mean | strict | N-1 |
|---|---|---|---|---|---|
| Drop the plan | A2 noplan − A2 | 65 | -9.1 [-13.0, -4.9]* | -7.2 [-12.9, -2.3]* | -9.2 [-17.7, -1.2]* |
| Drop the plan (vs plain) | A2 noplan − A0 | 65 | -2.7 [-7.2, +1.8] | +0.9 [-4.1, +6.2] | -5.0 [-13.1, +2.3] |
| Fact sheet instead of plan | A2 facts − A2 | 65 | -8.7 [-13.4, -4.1]* | -7.3 [-13.5, -1.5]* | -10.4 [-19.2, -1.5]* |
| Fact sheet vs no plan | A2 facts − A2 noplan | 65 | +0.4 [-3.5, +4.4] | -0.1 [-5.4, +5.0] | -1.2 [-8.1, +6.5] |
| Soft stops (on the fact sheet) | A2 facts+soft − A2 facts | 65 | +0.6 [-2.5, +3.3] | -0.4 [-3.8, +3.1] | +0.4 [-3.8, +4.2] |
| Fact sheet + soft stops vs plain | A2 facts+soft − A0 | 65 | -1.6 [-7.0, +3.8] | +0.4 [-5.8, +6.9] | -5.8 [-14.6, +2.7] |
| Verifiers own the checklist (no plan) vs A2+R | A2 noplan+R − A2+R | 65 | +0.4 [-2.1, +3.1] | -3.8 [-11.5, +3.1] | -1.5 [-8.8, +5.8] |
| No plan + verifiers vs verifiers alone | A2 noplan+R − R | 65 | +2.1 [-0.6, +5.4] | +1.5 [-5.0, +8.5] | +1.5 [-5.0, +8.5] |
| Fact sheet + soft + verifiers vs A2+R | A2 facts+soft+R − A2+R | 65 | -0.6 [-3.0, +2.0] | -3.8 [-11.9, +3.8] | -1.9 [-8.8, +5.0] |
| KB tools alone vs plain | A1 text − A0 | 65 | -0.8 [-4.8, +3.5] | +0.4 [-4.2, +5.0] | -2.3 [-8.8, +3.8] |
| Brief on top of the KB tools | A2 noplan − A1 text | 65 | -1.9 [-4.1, +0.3] | +0.5 [-2.7, +4.0] | -2.7 [-8.1, +2.7] |
| Code instead of text retrieval | A1 code − A1 text | 65 | +7.7 [+3.4, +12.1]* | +10.4 [+3.1, +18.5]* | +5.0 [-3.8, +14.2] |
| Exec tool vs reading the same code | A1 code+exec − A1 code | 65 | +5.7 [+3.0, +8.6]* | +3.1 [-2.7, +9.6] | +11.2 [+4.2, +18.8]* |
| Exec tool (model-invoked) vs monitor (R) | A1 code+exec − R | 65 | +2.8 [+0.2, +5.6]* | +3.5 [-2.7, +10.4] | +1.9 [-3.8, +8.1] |
| Exec tool vs plain | A1 code+exec − A0 | 65 | +12.6 [+8.3, +17.0]* | +13.8 [+5.8, +22.7]* | +13.8 [+3.8, +23.8]* |
| + one finish check | A1 code+exec+fin − A1 code+exec | 65 | +0.2 [-1.4, +1.8] | -1.2 [-3.8, +1.2] | +0.4 [-2.7, +3.8] |
| Exec tool on text retrieval vs text retrieval | A1 text+exec − A1 text | 65 | +14.1 [+10.4, +18.0]* | +15.0 [+7.3, +23.5]* | +18.5 [+10.8, +26.9]* |
| Exec with text vs with code retrieval | A1 text+exec − A1 code+exec | 65 | +0.7 [-1.1, +2.7] | +1.5 [-3.5, +6.9] | +2.3 [-3.1, +8.1] |
| Exec with text retrieval vs plain | A1 text+exec − A0 | 65 | +13.3 [+9.1, +17.6]* | +15.4 [+7.7, +23.8]* | +16.2 [+8.1, +24.6]* |
| Exec + finish check vs monitor (R) | A1 code+exec+fin − R | 65 | +3.0 [-0.1, +6.4] | +2.3 [-3.5, +8.5] | +2.3 [-4.2, +9.2] |

### Opus 5.5 (all 65 tasks; paired over tasks, 95% bootstrap CI; * = CI excludes 0)

| question | contrast | n | mean | strict | N-1 |
|---|---|---|---|---|---|
| Drop the plan | A2 noplan − A2 | 65 | -2.3 [-5.7, +1.3] | -12.7 [-21.9, -4.2]* | -9.2 [-18.5, -0.4]* |
| Drop the plan (vs plain) | A2 noplan − A0 | 65 | -6.7 [-9.8, -3.8]* | -15.8 [-25.1, -6.8]* | -17.2 [-26.2, -8.2]* |
| Fact sheet instead of plan | A2 facts − A2 | 65 | -3.4 [-7.3, +0.6] | -6.4 [-15.3, +2.3] | -4.7 [-15.1, +5.4] |
| Fact sheet vs no plan | A2 facts − A2 noplan | 65 | -1.1 [-4.0, +1.6] | +6.3 [-1.9, +14.7] | +4.5 [-4.2, +12.8] |
| Soft stops (on the fact sheet) | A2 facts+soft − A2 facts | 65 | +0.6 [-1.4, +2.6] | -0.9 [-5.0, +3.3] | -1.4 [-7.7, +4.6] |
| Fact sheet + soft stops vs plain | A2 facts+soft − A0 | 65 | -7.2 [-10.1, -4.6]* | -10.4 [-17.9, -3.1]* | -14.1 [-23.2, -5.1]* |
| Verifiers own the checklist (no plan) vs A2+R | A2 noplan+R − A2+R | 65 | -1.3 [-3.5, +0.9] | +0.8 [-6.9, +8.5] | -1.2 [-9.0, +6.9] |
| No plan + verifiers vs verifiers alone | A2 noplan+R − R | 65 | -0.8 [-2.1, +0.6] | -1.2 [-6.2, +3.5] | -1.5 [-7.7, +4.2] |
| Fact sheet + soft + verifiers vs A2+R | A2 facts+soft+R − A2+R | 65 | -0.5 [-2.3, +1.3] | +0.0 [-8.1, +8.5] | -1.5 [-9.7, +6.8] |
| KB tools alone vs plain | A1 text − A0 | 65 | -6.5 [-9.8, -3.6]* | -13.1 [-21.5, -5.0]* | -16.0 [-24.7, -7.4]* |
| Brief on top of the KB tools | A2 noplan − A1 text | 65 | -0.2 [-2.4, +1.8] | -2.7 [-7.7, +1.9] | -1.2 [-6.9, +5.0] |
| Code instead of text retrieval | A1 code − A1 text | 65 | +2.1 [-1.4, +5.2] | +1.5 [-7.3, +10.4] | -0.4 [-11.2, +10.4] |
| Exec tool vs reading the same code | A1 code+exec − A1 code | 65 | +3.1 [+1.4, +4.8]* | +5.4 [-2.7, +13.5] | +6.9 [-0.4, +14.2] |
| Exec tool (model-invoked) vs monitor (R) | A1 code+exec − R | 65 | -0.2 [-1.8, +1.3] | -1.9 [-9.6, +5.8] | -6.9 [-13.5, -0.8]* |
| Exec tool vs plain | A1 code+exec − A0 | 65 | -1.3 [-4.1, +1.2] | -6.2 [-16.3, +4.0] | -9.5 [-21.2, +2.2] |
| + one finish check | A1 code+exec+fin − A1 code+exec | 65 | -0.1 [-1.0, +0.9] | -0.4 [-2.7, +2.3] | +1.5 [-1.9, +5.4] |
| Exec tool on text retrieval vs text retrieval | A1 text+exec − A1 text | 65 | +6.0 [+3.4, +8.9]* | +8.8 [-0.8, +18.8] | +15.0 [+4.6, +25.8]* |
| Exec with text vs with code retrieval | A1 text+exec − A1 code+exec | 65 | +0.9 [-0.2, +2.3] | +1.9 [-1.2, +5.4] | +8.5 [+2.7, +14.6]* |
| Exec with text retrieval vs plain | A1 text+exec − A0 | 65 | -0.4 [-2.7, +1.9] | -4.2 [-13.8, +5.1] | -1.0 [-12.1, +9.9] |
| Exec + finish check vs monitor (R) | A1 code+exec+fin − R | 65 | -0.3 [-2.2, +1.5] | -2.3 [-9.6, +5.0] | -5.4 [-13.1, +1.9] |

## 3. Criteria broken and fixed against the plain agent (solid: ≤ 25% / ≥ 75% of trials)

### Haiku 5.5

| arm | broken (A0 pass → fail) | fixed (A0 fail → pass) | net |
|---|---|---|---|
| A2 | 44 | 75 | +31 |
| A2 noplan | 62 | 33 | -29 |
| A2 facts | 87 | 49 | -38 |
| A2 facts+soft | 84 | 44 | -40 |
| R | 28 | 84 | +56 |
| A2+R | 27 | 90 | +63 |
| A2 noplan+R | 31 | 91 | +60 |
| A2 facts+soft+R | 27 | 87 | +60 |
| A1 text | 55 | 31 | -24 |
| A1 text+exec | 20 | 84 | +64 |
| A1 code | 37 | 69 | +32 |
| A1 code+exec | 25 | 93 | +68 |
| A1 code+exec+fin | 27 | 89 | +62 |

### Opus 5.5

| arm | broken (A0 pass → fail) | fixed (A0 fail → pass) | net |
|---|---|---|---|
| A2 | 49 | 19 | -30 |
| A2 noplan | 52 | 21 | -31 |
| A2 facts | 61 | 18 | -43 |
| A2 facts+soft | 54 | 16 | -38 |
| R | 35 | 31 | -4 |
| A2+R | 36 | 21 | -15 |
| A2 noplan+R | 40 | 26 | -14 |
| A2 facts+soft+R | 38 | 28 | -10 |
| A1 text | 56 | 20 | -36 |
| A1 text+exec | 32 | 28 | -4 |
| A1 code | 57 | 21 | -36 |
| A1 code+exec | 41 | 28 | -13 |
| A1 code+exec+fin | 41 | 30 | -11 |

## 4. Do the criteria the plan broke come back?

### Haiku 5.5

| criteria | n | A2 noplan | A2 facts | A2 facts+soft | R | A2+R | A2 noplan+R | A2 facts+soft+R | A1 text | A1 text+exec | A1 code | A1 code+exec | A1 code+exec+fin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all broken by A2 | 44 | 30% | 41% | 39% | 75% | 48% | 55% | 57% | 41% | 73% | 70% | 68% | 66% |
| of which caused by the plan (labelled) | 18 | 33% | 56% | 61% | 83% | 50% | 83% | 72% | 56% | 89% | 94% | 83% | 83% |

Share of those criteria that pass (≥ 75% of trials) in each arm.

### Opus 5.5

| criteria | n | A2 noplan | A2 facts | A2 facts+soft | R | A2+R | A2 noplan+R | A2 facts+soft+R | A1 text | A1 text+exec | A1 code | A1 code+exec | A1 code+exec+fin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all broken by A2 | 49 | 45% | 49% | 39% | 63% | 61% | 63% | 63% | 51% | 67% | 61% | 67% | 69% |
| of which caused by the plan (labelled) | 37 | 49% | 49% | 43% | 62% | 65% | 65% | 62% | 49% | 65% | 59% | 65% | 65% |

Share of those criteria that pass (≥ 75% of trials) in each arm.

## 5. Exec tool usage

### Haiku 5.5

| arm | trials | calls verify_completion | calls verify_action | completion calls / trial | action calls / trial | actions flagged | last completion check OK | finish-check refusals / trial |
|---|---|---|---|---|---|---|---|---|
| A1 text+exec | 260 | 100% | 69% | 2.3 | 1.2 | 13% | 73% | 0.00 |
| A1 code+exec | 260 | 100% | 67% | 2.4 | 1.4 | 9% | 78% | 0.00 |
| A1 code+exec+fin | 260 | 100% | 65% | 2.4 | 1.3 | 9% | 80% | 0.11 |

### Opus 5.5

| arm | trials | calls verify_completion | calls verify_action | completion calls / trial | action calls / trial | actions flagged | last completion check OK | finish-check refusals / trial |
|---|---|---|---|---|---|---|---|---|
| A1 text+exec | 260 | 99% | 16% | 2.3 | 0.2 | 79% | 67% | 0.00 |
| A1 code+exec | 260 | 100% | 34% | 2.4 | 0.4 | 74% | 64% | 0.00 |
| A1 code+exec+fin | 260 | 100% | 32% | 2.4 | 0.4 | 72% | 64% | 0.00 |

