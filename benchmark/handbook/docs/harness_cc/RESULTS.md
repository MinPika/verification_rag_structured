# Haiku 5.5: OpenHands harness vs Claude Code harness

OpenHands: the HANDBOOK.md harness, model through the Copilot proxy (system prompt sent as a user turn, reasoning not carried between turns), 4 trials per task. Claude Code: Harbor's Claude Code agent plus the task's system prompt, direct to Anthropic, effort max, **1 trial per task**. Same tasks, MCP tools and grader. Tasks compared: 65.

## 1. Headline (tasks in common)

| harness | trials | mean reward | strict pass@1 | pass@1 (N-1) | strict pass@4 | pass^4 |
|---|---|---|---|---|---|---|
| OpenHands (k=4) | 260 | 71.5 | 10.8 | 28.5 | 18.5 | 3.1 |
| OpenHands, one trial per task (min–max over its 4 replicates) | 65 | 70.3–73.0 | 9.2–12.3 | 27.7–30.8 | | |
| **Claude Code (k=1)** | 65 | 75.2 | 16.9 | 29.2 | n/a (k=1) | n/a (k=1) |

## 2. Claude Code − OpenHands (paired over tasks, 95% bootstrap CI; * = excludes 0)

| metric | difference |
|---|---|
| mean reward | +3.6 [-2.0, +9.4] |
| strict pass@1 | +6.2 [-3.1, +15.4] |
| pass@1 (N-1) | +0.8 [-10.8, +12.3] |

## 3. Tasks

Claude Code ahead by ≥ 10 points on 20 tasks, behind by ≥ 10 on 15, within 10 on 30.

| domain | tasks | mean Δ (CC − OH) |
|---|---|---|
| finance | 12 | +7.7 |
| hr | 13 | +3.6 |
| insurance | 13 | +3.7 |
| logistics | 12 | +7.7 |
| medical | 15 | -3.0 |

| task | OpenHands mean (4) | Claude Code (1) | Δ |
|---|---|---|---|
| hr_crestwood_university_2071c562 | 0.0 | 71.4 | +71.4 |
| logistics_gear_sytems_inc_74170ae1 | 0.0 | 68.4 | +68.4 |
| medical_pathfinder_billing_and_coding_1d8667fc | 35.0 | 80.0 | +45.0 |
| insurance_mojave_crest_assurance_company_2a800bf7 | 56.9 | 100.0 | +43.1 |
| finance_meridian_partners_4dace65e | 57.8 | 100.0 | +42.2 |
| hr_ridgeline_gear_co_929c1527 | 43.4 | 80.8 | +37.4 |
| logistics_gear_sytems_inc_502e8c5e | 70.0 | 100.0 | +30.0 |
| hr_ridgeline_gear_co_2deeab56 | 75.0 | 100.0 | +25.0 |
| medical_careig_specialty_pharmacy_ea622238 | 57.9 | 79.5 | +21.6 |
| finance_sunshine_set_ebac9768 | 80.8 | 100.0 | +19.2 |
| insurance_vanguard_shield_mutual_177fce83 | 30.6 | 49.2 | +18.6 |
| finance_sunshine_set_6b9398f4 | 73.2 | 90.0 | +16.8 |
| hr_crestwood_university_1b602061 | 81.0 | 95.2 | +14.3 |
| insurance_vanguard_shield_mutual_82da8d17 | 71.4 | 85.7 | +14.3 |
| hr_crestwood_university_da394eac | 71.1 | 85.0 | +13.9 |
| logistics_prairie_star_creamery_4a2f4b1a | 68.2 | 81.8 | +13.6 |
| hr_crestwood_university_ee4d1791 | 59.7 | 72.2 | +12.5 |
| insurance_vanguard_shield_mutual_9b2f7a29 | 41.0 | 51.4 | +10.4 |
| medical_careig_specialty_pharmacy_f5947c33 | 54.4 | 64.7 | +10.3 |
| hr_ridgeline_gear_co_6d4d0f70 | 45.0 | 55.0 | +10.0 |
| finance_meridian_partners_331accf1 | 85.1 | 94.7 | +9.7 |
| hr_ridgeline_gear_co_44e4c745 | 90.3 | 99.3 | +9.0 |
| logistics_prairie_star_creamery_7b63c60d | 57.6 | 66.7 | +9.0 |
| medical_pathfinder_billing_and_coding_073e602b | 83.2 | 92.0 | +8.8 |
| logistics_prairie_star_creamery_27470081 | 46.8 | 55.4 | +8.6 |
| insurance_mojave_crest_assurance_company_5122b4da | 91.7 | 100.0 | +8.3 |
| medical_careig_specialty_pharmacy_f6d19d30 | 78.6 | 85.7 | +7.1 |
| logistics_gear_sytems_inc_dba0375e | 76.6 | 83.6 | +7.0 |
| finance_meridian_partners_158b9045 | 84.1 | 90.9 | +6.7 |
| finance_sunshine_set_b0b8129d | 93.3 | 100.0 | +6.7 |
| insurance_vanguard_shield_mutual_fe30fce5 | 75.0 | 81.6 | +6.6 |
| insurance_vanguard_shield_mutual_89007056 | 62.5 | 68.8 | +6.2 |
| finance_meridian_partners_a0895480 | 68.8 | 75.0 | +6.2 |
| medical_pathfinder_billing_and_coding_c01deb6e | 79.1 | 83.2 | +4.1 |
| insurance_mojave_crest_assurance_company_187e3a8c | 94.3 | 97.2 | +2.9 |
| finance_meridian_partners_cc2fc143 | 67.1 | 70.0 | +2.9 |
| finance_meridian_partners_19d57538 | 97.2 | 100.0 | +2.8 |
| hr_crestwood_university_79786c46 | 97.6 | 100.0 | +2.4 |
| logistics_prairie_star_creamery_a9dc52cb | 65.4 | 67.1 | +1.7 |
| logistics_prairie_star_creamery_f382586a | 76.1 | 77.8 | +1.7 |
| logistics_prairie_star_creamery_861b2650 | 71.7 | 73.3 | +1.7 |
| logistics_gear_sytems_inc_ad2ff597 | 50.4 | 50.5 | +0.1 |
| medical_pathfinder_billing_and_coding_a25684b9 | 100.0 | 100.0 | +0.0 |
| insurance_vanguard_shield_mutual_90ff0751 | 72.7 | 72.7 | +0.0 |
| medical_pathfinder_billing_and_coding_ec505b6b | 69.1 | 68.4 | -0.7 |
| hr_ridgeline_gear_co_6e501f78 | 87.5 | 85.7 | -1.8 |
| finance_sunshine_set_7c041148 | 80.4 | 78.6 | -1.8 |
| finance_sunshine_set_b581c493 | 93.8 | 87.5 | -6.2 |
| medical_careig_specialty_pharmacy_d3e312a5 | 84.4 | 75.0 | -9.4 |
| medical_pathfinder_billing_and_coding_9d274282 | 72.9 | 62.9 | -10.0 |
| insurance_mojave_crest_assurance_company_ab59bcf7 | 84.2 | 73.7 | -10.5 |
| insurance_vanguard_shield_mutual_4321b8e9 | 70.8 | 58.3 | -12.5 |
| finance_sunshine_set_d9d532c1 | 95.8 | 83.3 | -12.5 |
| insurance_mojave_crest_assurance_company_7245b8dd | 81.7 | 66.7 | -15.0 |
| logistics_gear_sytems_inc_0807b5a6 | 60.9 | 43.6 | -17.3 |
| medical_pathfinder_billing_and_coding_a70deabc | 39.3 | 19.1 | -20.2 |
| medical_careig_specialty_pharmacy_3c62ee67 | 81.9 | 61.5 | -20.5 |
| medical_careig_specialty_pharmacy_08ae3378 | 99.2 | 77.8 | -21.3 |
| medical_pathfinder_billing_and_coding_bbf1a560 | 85.0 | 60.0 | -25.0 |
| insurance_mojave_crest_assurance_company_4d2a2588 | 75.0 | 50.0 | -25.0 |
| logistics_gear_sytems_inc_9b60992d | 81.9 | 49.5 | -32.4 |
| medical_careig_specialty_pharmacy_d4619b8b | 99.4 | 64.6 | -34.8 |
| hr_ridgeline_gear_co_b337f86b | 95.0 | 54.5 | -40.5 |
| hr_crestwood_university_d93daa01 | 100.0 | 50.0 | -50.0 |
| hr_ridgeline_gear_co_6950ff2b | 75.0 | 18.2 | -56.8 |

## 4. Criteria

Of 791 criteria, 61 that OpenHands fails (≤ 25% of its trials) pass in Claude Code, and 72 that OpenHands passes (≥ 75%) fail in Claude Code. Claude Code has one trial per task, so single flips include its trial-to-trial noise.

## 5. Behaviour per trial

| | OpenHands | Claude Code |
|---|---|---|
| calls/trial | 21.8 | 45.6 |
| SOP reads/trial | 3.8 | 9.8 |
| context overflow (%) | 4.2 | 0.00 |
| turns | – | 46.6 |
| thinking tokens/trial | – | 103,261 |
| cost $/trial | – | 0.51 |
| minutes/trial | – | 8.4 |

Tool calls per trial by family:

| tool family | OpenHands | Claude Code |
|---|---|---|
| google_mail | 6.20 | 10.83 |
| slack | 4.62 | 9.08 |
| built-in: Bash (python) | 0.00 | 7.17 |
| jira | 2.52 | 4.65 |
| built-in: Read | 0.00 | 4.83 |
| syntara: run code | 4.40 | 0.03 |
| built-in: Bash (shell) | 0.00 | 4.26 |
| syntara: files | 2.84 | 0.18 |
| google_calendar | 0.82 | 1.49 |
| built-in: ToolSearch | 0.00 | 1.86 |
| built-in: Write | 0.00 | 1.06 |
| built-in: finish | 0.30 | 0.00 |
| shopify | 0.05 | 0.06 |
| built-in: Edit | 0.00 | 0.11 |

## 6. Claude Code behaviour vs per-task gain (Spearman ρ over tasks; Δ = CC − OH mean reward)

| Claude Code behaviour (per trial) | ρ with Δ |
|---|---|
| calls | +0.20 |
| sop_reads | +0.03 |
| thinking | +0.05 |
| turns | +0.20 |
| built-in: Bash (python) calls | -0.23 |
| built-in: Read calls | +0.17 |
| built-in: Bash (shell) calls | +0.10 |
| built-in: ToolSearch calls | +0.08 |
| built-in: Write calls | +0.03 |
| built-in: Edit calls | -0.04 |
