# Results by model (Haiku 4 trials/task, other models 2; Opus 4)

Strict pass@1 needs every rubric criterion; pass@1 (N-1) allows one miss. Board columns: the live leaderboard (2026-10-31, metric not stated) and the last snapshot known to be strict (2026-10-14).
A 'tasks' count below 65 in the first section means that arm's dev run is still pending. Dev was used to develop our layer, so test-only is the strictly held-out estimate for A2/A2+R/A3.

## All 65 tasks (test + dev)

| model | arm | tasks | trials | mean reward | strict pass@1 | pass@1 (N-1) | board 10-31 | board 10-14 (strict) | rubric checks passed |
|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | A0 | 65 | 260 | 71.55 | 10.77 | 28.46 |  |  | 70.3% |
| claude-haiku-5.5 | A2 | 65 | 260 | 77.96 | 18.85 | 32.69 |  |  | 75.1% |
| claude-haiku-5.5 | A2+R | 65 | 259 | 83.16 | 26.54 | 43.46 |  |  | 81.1% |
| claude-haiku-5.5 | R | 65 | 260 | 81.38 | 21.15 | 40.38 |  |  | 80.7% |
| claude-haiku-5.5 | A3 (our gate) | 65 | 260 | 79.00 | 18.85 | 32.69 |  |  | 75.9% |
| claude-haiku-5.5 | A3+msgs | 65 | 259 | 78.01 | 16.54 | 33.08 |  |  | 74.5% |
| claude-haiku-5.5 | A1 text | 65 | 260 | 70.71 | 11.15 | 26.15 |  |  | 68.6% |
| claude-haiku-5.5 | A1 code | 65 | 260 | 78.41 | 21.54 | 31.15 |  |  | 74.8% |
| claude-haiku-5.5 | A1 code+R | 20 | 71 | 78.42 | 17.92 | 31.25 |  |  | 69.3% |
| gpt-6-sol | A0 | 65 | 130 | 72.39 | 9.23 | 24.62 |  |  | 69.7% |
| gpt-6-sol | A2 | 65 | 130 | 72.55 | 16.92 | 25.38 |  |  | 68.0% |
| gpt-6-sol | A2+R | 65 | 129 | 83.31 | 26.15 | 45.38 |  |  | 79.6% |
| gpt-6-sol | R | 65 | 129 | 85.02 | 27.69 | 43.85 |  |  | 82.5% |
| gpt-6-luna | A0 | 65 | 130 | 66.64 | 5.38 | 19.23 |  |  | 63.2% |
| gpt-6-luna | A2 | 64 | 128 | 70.26 | 10.94 | 27.34 |  |  | 65.9% |
| gpt-6-luna | A2+R | 64 | 128 | 81.77 | 19.53 | 46.88 |  |  | 80.0% |
| gpt-6-luna | R | 65 | 130 | 83.19 | 18.46 | 40.77 |  |  | 80.7% |
| gpt-5.6-sol | A0 | 65 | 130 | 73.34 | 15.38 | 28.46 |  |  | 71.5% |
| gpt-5.6-sol | A2 | 64 | 127 | 78.82 | 23.44 | 41.41 |  |  | 74.6% |
| gpt-5.6-sol | A2+R | 65 | 128 | 84.92 | 26.92 | 46.92 |  |  | 81.2% |
| gpt-5.6-sol | R | 65 | 130 | 85.08 | 23.85 | 47.69 |  |  | 82.7% |
| claude-opus-5.5 | A0 | 65 | 248 | 87.48 | 31.54 | 53.33 | 52.3 |  | 84.6% |
| claude-opus-5.5 | A2 | 65 | 129 | 82.77 | 29.23 | 46.15 |  |  | 80.1% |
| claude-opus-5.5 | A2+R | 65 | 248 | 86.83 | 25.38 | 50.38 |  |  | 83.6% |
| claude-opus-5.5 | R | 65 | 130 | 85.78 | 26.15 | 48.46 |  |  | 84.2% |
| claude-sonnet-5.5 | A0 | 65 | 130 | 82.77 | 23.08 | 50.00 | 47.7 |  | 79.5% |
| claude-sonnet-5.5 | A2 | 65 | 130 | 81.74 | 20.00 | 39.23 |  |  | 79.1% |
| claude-sonnet-5.5 | A2+R | 65 | 130 | 86.29 | 25.38 | 50.77 |  |  | 83.7% |
| claude-sonnet-5.5 | R | 65 | 129 | 85.89 | 25.38 | 50.77 |  |  | 83.4% |
| gemini-4-argon | A0 | 65 | 126 | 88.81 | 36.92 | 60.77 | 36.6 |  | 85.7% |
| gemini-4-argon | A2 | 65 | 127 | 84.47 | 32.31 | 52.31 |  |  | 82.1% |
| gemini-4-argon | A2+R | 65 | 129 | 89.64 | 38.46 | 64.62 |  |  | 86.9% |
| gemini-4-argon | R | 65 | 129 | 88.81 | 32.31 | 60.00 |  |  | 86.6% |
| gemini-4-argon | A0 high | 45 | 89 | 91.25 | 42.22 | 66.67 |  |  | 87.1% |
| gemini-3.8-flash | A0 | 64 | 122 | 76.23 | 15.62 | 27.34 | 26.5 | 10.8 | 71.6% |
| gemini-3.8-flash | A2 | 65 | 130 | 80.61 | 21.54 | 37.69 |  |  | 77.0% |
| gemini-3.8-flash | A2+R | 64 | 121 | 87.35 | 25.00 | 56.25 |  |  | 81.7% |
| gemini-3.8-flash | R | 65 | 130 | 86.27 | 23.08 | 50.77 |  |  | 83.1% |
| gemini-3.8-flash | A0 high | 45 | 90 | 76.75 | 16.67 | 33.33 |  |  | 73.5% |

### Paired contrasts, all 65 tasks (test + dev) (task-level bootstrap, 95% CI; * = excludes 0)

| model | contrast | metric | tasks | diff | 95% CI |
|---|---|---|---|---|---|
| claude-haiku-5.5 | A2 − A0 | mean reward | 65 | +6.41 | [+1.81, +10.87] * |
| claude-haiku-5.5 | A2 − A0 | strict pass@1 | 65 | +8.08 | [+1.54, +15.38] * |
| claude-haiku-5.5 | A2 − A0 | pass@1 (N-1) | 65 | +4.23 | [-5.77, +14.23] |
| claude-haiku-5.5 | A2+R − A2 | mean reward | 65 | +5.19 | [+2.27, +8.03] * |
| claude-haiku-5.5 | A2+R − A2 | strict pass@1 | 65 | +7.69 | [+1.15, +15.00] * |
| claude-haiku-5.5 | A2+R − A2 | pass@1 (N-1) | 65 | +10.77 | [+2.69, +18.85] * |
| claude-haiku-5.5 | A2+R − A0 | mean reward | 65 | +11.61 | [+7.72, +15.52] * |
| claude-haiku-5.5 | A2+R − A0 | strict pass@1 | 65 | +15.77 | [+7.31, +25.00] * |
| claude-haiku-5.5 | A2+R − A0 | pass@1 (N-1) | 65 | +15.00 | [+5.00, +25.00] * |
| claude-haiku-5.5 | R − A0 | mean reward | 65 | +9.83 | [+5.75, +14.06] * |
| claude-haiku-5.5 | R − A0 | strict pass@1 | 65 | +10.38 | [+3.46, +17.69] * |
| claude-haiku-5.5 | R − A0 | pass@1 (N-1) | 65 | +11.92 | [+2.31, +21.92] * |
| claude-haiku-5.5 | A2+R − R | mean reward | 65 | +1.78 | [-1.88, +5.49] |
| claude-haiku-5.5 | A2+R − R | strict pass@1 | 65 | +5.38 | [-3.85, +15.00] |
| claude-haiku-5.5 | A2+R − R | pass@1 (N-1) | 65 | +3.08 | [-6.92, +13.46] |
| claude-haiku-5.5 | A3 (our gate) − A2 | mean reward | 65 | +1.03 | [-0.83, +2.87] |
| claude-haiku-5.5 | A3 (our gate) − A2 | strict pass@1 | 65 | +0.00 | [-2.69, +2.69] |
| claude-haiku-5.5 | A3 (our gate) − A2 | pass@1 (N-1) | 65 | +0.00 | [-5.00, +4.62] |
| claude-haiku-5.5 | A1 code − A1 text | mean reward | 65 | +7.70 | [+3.41, +12.12] * |
| claude-haiku-5.5 | A1 code − A1 text | strict pass@1 | 65 | +10.38 | [+3.08, +18.46] * |
| claude-haiku-5.5 | A1 code − A1 text | pass@1 (N-1) | 65 | +5.00 | [-3.85, +14.23] |
| claude-haiku-5.5 | A1 code+R − R | mean reward | 20 | +0.07 | [-2.53, +3.02] |
| claude-haiku-5.5 | A1 code+R − R | strict pass@1 | 20 | +1.67 | [-10.42, +13.75] |
| claude-haiku-5.5 | A1 code+R − R | pass@1 (N-1) | 20 | -3.75 | [-12.50, +5.00] |
| gpt-6-sol | A2 − A0 | mean reward | 65 | +0.17 | [-6.50, +6.42] |
| gpt-6-sol | A2 − A0 | strict pass@1 | 65 | +7.69 | [-0.77, +16.92] |
| gpt-6-sol | A2 − A0 | pass@1 (N-1) | 65 | +0.77 | [-10.77, +12.31] |
| gpt-6-sol | A2+R − A2 | mean reward | 65 | +10.76 | [+6.83, +15.21] * |
| gpt-6-sol | A2+R − A2 | strict pass@1 | 65 | +9.23 | [+0.77, +17.69] * |
| gpt-6-sol | A2+R − A2 | pass@1 (N-1) | 65 | +20.00 | [+10.77, +29.23] * |
| gpt-6-sol | A2+R − A0 | mean reward | 65 | +10.92 | [+5.01, +16.63] * |
| gpt-6-sol | A2+R − A0 | strict pass@1 | 65 | +16.92 | [+6.92, +27.69] * |
| gpt-6-sol | A2+R − A0 | pass@1 (N-1) | 65 | +20.77 | [+9.23, +32.31] * |
| gpt-6-sol | R − A0 | mean reward | 65 | +12.63 | [+7.79, +17.82] * |
| gpt-6-sol | R − A0 | strict pass@1 | 65 | +18.46 | [+7.69, +29.23] * |
| gpt-6-sol | R − A0 | pass@1 (N-1) | 65 | +19.23 | [+7.69, +30.77] * |
| gpt-6-sol | A2+R − R | mean reward | 65 | -1.71 | [-5.99, +2.24] |
| gpt-6-sol | A2+R − R | strict pass@1 | 65 | -1.54 | [-9.23, +6.15] |
| gpt-6-sol | A2+R − R | pass@1 (N-1) | 65 | +1.54 | [-8.46, +11.54] |
| gpt-6-luna | A2 − A0 | mean reward | 64 | +3.62 | [-2.21, +9.10] |
| gpt-6-luna | A2 − A0 | strict pass@1 | 64 | +5.47 | [-0.78, +12.50] |
| gpt-6-luna | A2 − A0 | pass@1 (N-1) | 64 | +7.81 | [-2.34, +17.97] |
| gpt-6-luna | A2+R − A2 | mean reward | 64 | +11.51 | [+7.44, +15.77] * |
| gpt-6-luna | A2+R − A2 | strict pass@1 | 64 | +8.59 | [+0.78, +17.19] * |
| gpt-6-luna | A2+R − A2 | pass@1 (N-1) | 64 | +19.53 | [+8.59, +31.25] * |
| gpt-6-luna | A2+R − A0 | mean reward | 64 | +15.13 | [+9.88, +20.29] * |
| gpt-6-luna | A2+R − A0 | strict pass@1 | 64 | +14.06 | [+6.25, +22.66] * |
| gpt-6-luna | A2+R − A0 | pass@1 (N-1) | 64 | +27.34 | [+15.62, +39.06] * |
| gpt-6-luna | R − A0 | mean reward | 65 | +16.55 | [+12.35, +20.90] * |
| gpt-6-luna | R − A0 | strict pass@1 | 65 | +13.08 | [+5.38, +21.54] * |
| gpt-6-luna | R − A0 | pass@1 (N-1) | 65 | +21.54 | [+12.31, +31.54] * |
| gpt-6-luna | A2+R − R | mean reward | 64 | -1.45 | [-5.29, +1.76] |
| gpt-6-luna | A2+R − R | strict pass@1 | 64 | +0.78 | [-6.25, +7.81] |
| gpt-6-luna | A2+R − R | pass@1 (N-1) | 64 | +5.47 | [-4.69, +15.62] |
| gpt-5.6-sol | A2 − A0 | mean reward | 64 | +5.19 | [-0.25, +10.86] |
| gpt-5.6-sol | A2 − A0 | strict pass@1 | 64 | +7.81 | [-2.34, +17.97] |
| gpt-5.6-sol | A2 − A0 | pass@1 (N-1) | 64 | +12.50 | [+1.56, +23.44] * |
| gpt-5.6-sol | A2+R − A2 | mean reward | 64 | +6.31 | [+2.71, +10.10] * |
| gpt-5.6-sol | A2+R − A2 | strict pass@1 | 64 | +3.91 | [-3.12, +10.94] |
| gpt-5.6-sol | A2+R − A2 | pass@1 (N-1) | 64 | +6.25 | [-3.12, +16.41] |
| gpt-5.6-sol | A2+R − A0 | mean reward | 65 | +11.57 | [+6.64, +16.75] * |
| gpt-5.6-sol | A2+R − A0 | strict pass@1 | 65 | +11.54 | [+1.54, +21.54] * |
| gpt-5.6-sol | A2+R − A0 | pass@1 (N-1) | 65 | +18.46 | [+5.38, +31.54] * |
| gpt-5.6-sol | R − A0 | mean reward | 65 | +11.74 | [+7.19, +16.82] * |
| gpt-5.6-sol | R − A0 | strict pass@1 | 65 | +8.46 | [-0.77, +17.69] |
| gpt-5.6-sol | R − A0 | pass@1 (N-1) | 65 | +19.23 | [+6.92, +32.31] * |
| gpt-5.6-sol | A2+R − R | mean reward | 65 | -0.16 | [-3.70, +3.34] |
| gpt-5.6-sol | A2+R − R | strict pass@1 | 65 | +3.08 | [-4.62, +10.77] |
| gpt-5.6-sol | A2+R − R | pass@1 (N-1) | 65 | -0.77 | [-12.31, +10.77] |
| claude-opus-5.5 | A2 − A0 | mean reward | 65 | -4.71 | [-8.10, -1.59] * |
| claude-opus-5.5 | A2 − A0 | strict pass@1 | 65 | -2.31 | [-12.56, +7.69] |
| claude-opus-5.5 | A2 − A0 | pass@1 (N-1) | 65 | -7.18 | [-17.18, +2.69] |
| claude-opus-5.5 | A2+R − A2 | mean reward | 65 | +4.06 | [+1.59, +6.76] * |
| claude-opus-5.5 | A2+R − A2 | strict pass@1 | 65 | -3.85 | [-11.15, +3.08] |
| claude-opus-5.5 | A2+R − A2 | pass@1 (N-1) | 65 | +4.23 | [-6.03, +14.62] |
| claude-opus-5.5 | A2+R − A0 | mean reward | 65 | -0.65 | [-2.77, +1.42] |
| claude-opus-5.5 | A2+R − A0 | strict pass@1 | 65 | -6.15 | [-16.15, +3.21] |
| claude-opus-5.5 | A2+R − A0 | pass@1 (N-1) | 65 | -2.95 | [-13.97, +7.82] |
| claude-opus-5.5 | R − A0 | mean reward | 65 | -1.70 | [-4.35, +0.92] |
| claude-opus-5.5 | R − A0 | strict pass@1 | 65 | -5.38 | [-16.54, +5.64] |
| claude-opus-5.5 | R − A0 | pass@1 (N-1) | 65 | -4.87 | [-16.54, +6.92] |
| claude-opus-5.5 | A2+R − R | mean reward | 65 | +1.05 | [-1.14, +3.36] |
| claude-opus-5.5 | A2+R − R | strict pass@1 | 65 | -0.77 | [-9.23, +7.69] |
| claude-opus-5.5 | A2+R − R | pass@1 (N-1) | 65 | +1.92 | [-7.18, +10.90] |
| claude-sonnet-5.5 | A2 − A0 | mean reward | 65 | -1.03 | [-5.59, +3.44] |
| claude-sonnet-5.5 | A2 − A0 | strict pass@1 | 65 | -3.08 | [-13.85, +8.46] |
| claude-sonnet-5.5 | A2 − A0 | pass@1 (N-1) | 65 | -10.77 | [-23.85, +2.31] |
| claude-sonnet-5.5 | A2+R − A2 | mean reward | 65 | +4.56 | [+1.64, +7.79] * |
| claude-sonnet-5.5 | A2+R − A2 | strict pass@1 | 65 | +5.38 | [-2.31, +13.85] |
| claude-sonnet-5.5 | A2+R − A2 | pass@1 (N-1) | 65 | +11.54 | [+1.54, +22.31] * |
| claude-sonnet-5.5 | A2+R − A0 | mean reward | 65 | +3.52 | [+0.01, +7.36] * |
| claude-sonnet-5.5 | A2+R − A0 | strict pass@1 | 65 | +2.31 | [-6.92, +12.31] |
| claude-sonnet-5.5 | A2+R − A0 | pass@1 (N-1) | 65 | +0.77 | [-11.54, +13.08] |
| claude-sonnet-5.5 | R − A0 | mean reward | 65 | +3.12 | [-0.45, +7.01] |
| claude-sonnet-5.5 | R − A0 | strict pass@1 | 65 | +2.31 | [-7.69, +13.08] |
| claude-sonnet-5.5 | R − A0 | pass@1 (N-1) | 65 | +0.77 | [-10.77, +12.31] |
| claude-sonnet-5.5 | A2+R − R | mean reward | 65 | +0.40 | [-1.82, +2.47] |
| claude-sonnet-5.5 | A2+R − R | strict pass@1 | 65 | +0.00 | [-9.23, +9.23] |
| claude-sonnet-5.5 | A2+R − R | pass@1 (N-1) | 65 | +0.00 | [-10.77, +10.00] |
| gemini-4-argon | A2 − A0 | mean reward | 65 | -4.33 | [-8.85, -0.26] * |
| gemini-4-argon | A2 − A0 | strict pass@1 | 65 | -4.62 | [-14.62, +5.38] |
| gemini-4-argon | A2 − A0 | pass@1 (N-1) | 65 | -8.46 | [-20.00, +3.08] |
| gemini-4-argon | A2+R − A2 | mean reward | 65 | +5.17 | [+2.11, +9.09] * |
| gemini-4-argon | A2+R − A2 | strict pass@1 | 65 | +6.15 | [-2.31, +15.38] |
| gemini-4-argon | A2+R − A2 | pass@1 (N-1) | 65 | +12.31 | [+2.31, +22.31] * |
| gemini-4-argon | A2+R − A0 | mean reward | 65 | +0.83 | [-1.97, +3.74] |
| gemini-4-argon | A2+R − A0 | strict pass@1 | 65 | +1.54 | [-9.23, +11.54] |
| gemini-4-argon | A2+R − A0 | pass@1 (N-1) | 65 | +3.85 | [-6.15, +13.85] |
| gemini-4-argon | R − A0 | mean reward | 65 | -0.00 | [-2.60, +2.82] |
| gemini-4-argon | R − A0 | strict pass@1 | 65 | -4.62 | [-14.62, +5.38] |
| gemini-4-argon | R − A0 | pass@1 (N-1) | 65 | -0.77 | [-10.00, +8.46] |
| gemini-4-argon | A2+R − R | mean reward | 65 | +0.84 | [-0.67, +2.40] |
| gemini-4-argon | A2+R − R | strict pass@1 | 65 | +6.15 | [-2.31, +14.62] |
| gemini-4-argon | A2+R − R | pass@1 (N-1) | 65 | +4.62 | [-3.85, +13.08] |
| gemini-4-argon | A0 high − A0 | mean reward | 45 | -0.38 | [-1.72, +1.00] |
| gemini-4-argon | A0 high − A0 | strict pass@1 | 45 | -3.33 | [-11.11, +3.33] |
| gemini-4-argon | A0 high − A0 | pass@1 (N-1) | 45 | -2.22 | [-10.00, +5.56] |
| gemini-3.8-flash | A2 − A0 | mean reward | 64 | +5.00 | [-0.70, +10.79] |
| gemini-3.8-flash | A2 − A0 | strict pass@1 | 64 | +6.25 | [-3.91, +16.41] |
| gemini-3.8-flash | A2 − A0 | pass@1 (N-1) | 64 | +10.94 | [-0.78, +22.66] |
| gemini-3.8-flash | A2+R − A2 | mean reward | 64 | +6.30 | [+2.55, +10.39] * |
| gemini-3.8-flash | A2+R − A2 | strict pass@1 | 64 | +3.12 | [-4.69, +10.94] |
| gemini-3.8-flash | A2+R − A2 | pass@1 (N-1) | 64 | +17.97 | [+4.69, +30.47] * |
| gemini-3.8-flash | A2+R − A0 | mean reward | 63 | +10.69 | [+5.76, +16.02] * |
| gemini-3.8-flash | A2+R − A0 | strict pass@1 | 63 | +9.52 | [-0.79, +19.84] |
| gemini-3.8-flash | A2+R − A0 | pass@1 (N-1) | 63 | +27.78 | [+16.67, +39.68] * |
| gemini-3.8-flash | R − A0 | mean reward | 64 | +9.96 | [+5.06, +15.20] * |
| gemini-3.8-flash | R − A0 | strict pass@1 | 64 | +7.81 | [-2.34, +17.97] |
| gemini-3.8-flash | R − A0 | pass@1 (N-1) | 64 | +22.66 | [+10.16, +35.16] * |
| gemini-3.8-flash | A2+R − R | mean reward | 64 | +0.56 | [-2.12, +3.30] |
| gemini-3.8-flash | A2+R − R | strict pass@1 | 64 | +1.56 | [-7.81, +10.94] |
| gemini-3.8-flash | A2+R − R | pass@1 (N-1) | 64 | +4.69 | [-5.47, +14.84] |
| gemini-3.8-flash | A0 high − A0 | mean reward | 44 | +0.38 | [-1.87, +2.76] |
| gemini-3.8-flash | A0 high − A0 | strict pass@1 | 44 | -2.27 | [-7.95, +3.41] |
| gemini-3.8-flash | A0 high − A0 | pass@1 (N-1) | 44 | +2.27 | [-3.41, +7.95] |

## Test split only (45 held-out tasks)

| model | arm | tasks | trials | mean reward | strict pass@1 | pass@1 (N-1) | board 10-31 | board 10-14 (strict) | rubric checks passed |
|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | A0 | 45 | 180 | 72.48 | 8.33 | 28.89 |  |  | 71.2% |
| claude-haiku-5.5 | A2 | 45 | 180 | 80.75 | 22.22 | 37.78 |  |  | 77.2% |
| claude-haiku-5.5 | A2+R | 45 | 179 | 85.74 | 31.11 | 52.22 |  |  | 83.6% |
| claude-haiku-5.5 | R | 45 | 180 | 82.72 | 23.33 | 42.78 |  |  | 83.4% |
| claude-haiku-5.5 | A3 (our gate) | 45 | 180 | 81.65 | 23.33 | 38.89 |  |  | 78.4% |
| claude-haiku-5.5 | A3+msgs | 45 | 180 | 81.36 | 20.56 | 40.56 |  |  | 77.5% |
| claude-haiku-5.5 | A1 text | 45 | 180 | 71.19 | 11.67 | 27.78 |  |  | 70.4% |
| claude-haiku-5.5 | A1 code | 45 | 180 | 80.81 | 24.44 | 33.89 |  |  | 77.9% |
| gpt-6-sol | A0 | 45 | 90 | 71.71 | 10.00 | 27.78 |  |  | 69.3% |
| gpt-6-sol | A2 | 45 | 90 | 74.07 | 20.00 | 30.00 |  |  | 67.6% |
| gpt-6-sol | A2+R | 45 | 89 | 87.27 | 32.22 | 55.56 |  |  | 82.5% |
| gpt-6-sol | R | 45 | 89 | 86.48 | 33.33 | 48.89 |  |  | 84.4% |
| gpt-6-luna | A0 | 45 | 90 | 66.71 | 5.56 | 21.11 |  |  | 63.8% |
| gpt-6-luna | A2 | 44 | 88 | 73.51 | 11.36 | 32.95 |  |  | 67.3% |
| gpt-6-luna | A2+R | 44 | 88 | 85.95 | 23.86 | 55.68 |  |  | 83.2% |
| gpt-6-luna | R | 45 | 90 | 84.89 | 20.00 | 44.44 |  |  | 82.4% |
| gpt-5.6-sol | A0 | 45 | 90 | 74.18 | 14.44 | 30.00 |  |  | 72.9% |
| gpt-5.6-sol | A2 | 44 | 87 | 83.20 | 29.55 | 51.14 |  |  | 77.9% |
| gpt-5.6-sol | A2+R | 45 | 89 | 89.50 | 33.33 | 57.78 |  |  | 85.7% |
| gpt-5.6-sol | R | 45 | 90 | 86.67 | 25.56 | 47.78 |  |  | 85.0% |
| claude-opus-5.5 | A0 | 45 | 168 | 88.55 | 34.44 | 55.37 | 52.3 |  | 85.7% |
| claude-opus-5.5 | A2 | 45 | 89 | 84.29 | 34.44 | 48.89 |  |  | 81.0% |
| claude-opus-5.5 | A2+R | 45 | 168 | 89.18 | 30.00 | 57.22 |  |  | 86.0% |
| claude-opus-5.5 | R | 45 | 90 | 87.11 | 31.11 | 53.33 |  |  | 86.2% |
| claude-sonnet-5.5 | A0 | 45 | 90 | 83.98 | 25.56 | 51.11 | 47.7 |  | 80.5% |
| claude-sonnet-5.5 | A2 | 45 | 90 | 83.83 | 21.11 | 42.22 |  |  | 80.7% |
| claude-sonnet-5.5 | A2+R | 45 | 90 | 89.66 | 30.00 | 58.89 |  |  | 86.8% |
| claude-sonnet-5.5 | R | 45 | 89 | 88.16 | 27.78 | 57.78 |  |  | 86.1% |
| gemini-4-argon | A0 | 45 | 89 | 91.63 | 45.56 | 68.89 | 36.6 |  | 87.8% |
| gemini-4-argon | A2 | 45 | 87 | 88.26 | 40.00 | 61.11 |  |  | 85.3% |
| gemini-4-argon | A2+R | 45 | 90 | 92.33 | 44.44 | 73.33 |  |  | 89.6% |
| gemini-4-argon | R | 45 | 89 | 92.04 | 40.00 | 71.11 |  |  | 90.0% |
| gemini-4-argon | A0 high | 45 | 89 | 91.25 | 42.22 | 66.67 |  |  | 87.1% |
| gemini-3.8-flash | A0 | 44 | 85 | 76.77 | 19.32 | 31.82 | 26.5 | 10.8 | 73.4% |
| gemini-3.8-flash | A2 | 45 | 90 | 84.14 | 26.67 | 45.56 |  |  | 79.7% |
| gemini-3.8-flash | A2+R | 45 | 83 | 90.69 | 28.89 | 65.56 |  |  | 85.5% |
| gemini-3.8-flash | R | 45 | 90 | 89.57 | 30.00 | 60.00 |  |  | 86.6% |
| gemini-3.8-flash | A0 high | 45 | 90 | 76.75 | 16.67 | 33.33 |  |  | 73.5% |

### Paired contrasts, test split only (45 held-out tasks) (task-level bootstrap, 95% CI; * = excludes 0)

| model | contrast | metric | tasks | diff | 95% CI |
|---|---|---|---|---|---|
| claude-haiku-5.5 | A2 − A0 | mean reward | 45 | +8.28 | [+3.36, +13.46] * |
| claude-haiku-5.5 | A2 − A0 | strict pass@1 | 45 | +13.89 | [+6.11, +22.78] * |
| claude-haiku-5.5 | A2 − A0 | pass@1 (N-1) | 45 | +8.89 | [-3.33, +21.67] |
| claude-haiku-5.5 | A2+R − A2 | mean reward | 45 | +4.98 | [+1.51, +8.27] * |
| claude-haiku-5.5 | A2+R − A2 | strict pass@1 | 45 | +8.89 | [+1.11, +17.78] * |
| claude-haiku-5.5 | A2+R − A2 | pass@1 (N-1) | 45 | +14.44 | [+3.89, +25.00] * |
| claude-haiku-5.5 | A2+R − A0 | mean reward | 45 | +13.26 | [+8.91, +17.92] * |
| claude-haiku-5.5 | A2+R − A0 | strict pass@1 | 45 | +22.78 | [+12.22, +34.44] * |
| claude-haiku-5.5 | A2+R − A0 | pass@1 (N-1) | 45 | +23.33 | [+12.22, +35.00] * |
| claude-haiku-5.5 | R − A0 | mean reward | 45 | +10.25 | [+5.78, +14.88] * |
| claude-haiku-5.5 | R − A0 | strict pass@1 | 45 | +15.00 | [+6.11, +25.00] * |
| claude-haiku-5.5 | R − A0 | pass@1 (N-1) | 45 | +13.89 | [+2.78, +25.56] * |
| claude-haiku-5.5 | A2+R − R | mean reward | 45 | +3.01 | [-1.45, +7.77] |
| claude-haiku-5.5 | A2+R − R | strict pass@1 | 45 | +7.78 | [-3.89, +20.00] |
| claude-haiku-5.5 | A2+R − R | pass@1 (N-1) | 45 | +9.44 | [-1.67, +21.11] |
| claude-haiku-5.5 | A3 (our gate) − A2 | mean reward | 45 | +0.89 | [-1.48, +3.20] |
| claude-haiku-5.5 | A3 (our gate) − A2 | strict pass@1 | 45 | +1.11 | [-2.22, +4.44] |
| claude-haiku-5.5 | A3 (our gate) − A2 | pass@1 (N-1) | 45 | +1.11 | [-5.00, +6.67] |
| claude-haiku-5.5 | A1 code − A1 text | mean reward | 45 | +9.62 | [+3.88, +15.19] * |
| claude-haiku-5.5 | A1 code − A1 text | strict pass@1 | 45 | +12.78 | [+2.22, +23.89] * |
| claude-haiku-5.5 | A1 code − A1 text | pass@1 (N-1) | 45 | +6.11 | [-6.67, +18.89] |
| gpt-6-sol | A2 − A0 | mean reward | 45 | +2.36 | [-5.00, +9.45] |
| gpt-6-sol | A2 − A0 | strict pass@1 | 45 | +10.00 | [+0.00, +20.00] |
| gpt-6-sol | A2 − A0 | pass@1 (N-1) | 45 | +2.22 | [-11.11, +15.56] |
| gpt-6-sol | A2+R − A2 | mean reward | 45 | +13.21 | [+7.89, +19.04] * |
| gpt-6-sol | A2+R − A2 | strict pass@1 | 45 | +12.22 | [+0.00, +24.44] |
| gpt-6-sol | A2+R − A2 | pass@1 (N-1) | 45 | +25.56 | [+14.44, +37.78] * |
| gpt-6-sol | A2+R − A0 | mean reward | 45 | +15.56 | [+9.65, +21.84] * |
| gpt-6-sol | A2+R − A0 | strict pass@1 | 45 | +22.22 | [+10.00, +34.44] * |
| gpt-6-sol | A2+R − A0 | pass@1 (N-1) | 45 | +27.78 | [+14.44, +41.11] * |
| gpt-6-sol | R − A0 | mean reward | 45 | +14.77 | [+9.06, +20.98] * |
| gpt-6-sol | R − A0 | strict pass@1 | 45 | +23.33 | [+11.11, +36.67] * |
| gpt-6-sol | R − A0 | pass@1 (N-1) | 45 | +21.11 | [+7.78, +35.56] * |
| gpt-6-sol | A2+R − R | mean reward | 45 | +0.79 | [-3.33, +5.40] |
| gpt-6-sol | A2+R − R | strict pass@1 | 45 | -1.11 | [-12.22, +10.00] |
| gpt-6-sol | A2+R − R | pass@1 (N-1) | 45 | +6.67 | [-4.44, +18.89] |
| gpt-6-luna | A2 − A0 | mean reward | 44 | +6.79 | [+0.23, +13.12] * |
| gpt-6-luna | A2 − A0 | strict pass@1 | 44 | +5.68 | [-3.41, +14.77] |
| gpt-6-luna | A2 − A0 | pass@1 (N-1) | 44 | +11.36 | [+0.00, +22.73] |
| gpt-6-luna | A2+R − A2 | mean reward | 44 | +12.44 | [+7.62, +17.62] * |
| gpt-6-luna | A2+R − A2 | strict pass@1 | 44 | +12.50 | [+2.27, +22.73] * |
| gpt-6-luna | A2+R − A2 | pass@1 (N-1) | 44 | +22.73 | [+9.09, +36.36] * |
| gpt-6-luna | A2+R − A0 | mean reward | 44 | +19.24 | [+13.92, +24.77] * |
| gpt-6-luna | A2+R − A0 | strict pass@1 | 44 | +18.18 | [+7.95, +29.55] * |
| gpt-6-luna | A2+R − A0 | pass@1 (N-1) | 44 | +34.09 | [+20.45, +47.73] * |
| gpt-6-luna | R − A0 | mean reward | 45 | +18.18 | [+13.21, +23.31] * |
| gpt-6-luna | R − A0 | strict pass@1 | 45 | +14.44 | [+4.44, +25.56] * |
| gpt-6-luna | R − A0 | pass@1 (N-1) | 45 | +23.33 | [+12.22, +35.56] * |
| gpt-6-luna | A2+R − R | mean reward | 44 | +0.97 | [-2.60, +4.12] |
| gpt-6-luna | A2+R − R | strict pass@1 | 44 | +3.41 | [-2.27, +10.23] |
| gpt-6-luna | A2+R − R | pass@1 (N-1) | 44 | +10.23 | [-2.27, +22.73] |
| gpt-5.6-sol | A2 − A0 | mean reward | 44 | +8.58 | [+2.19, +15.64] * |
| gpt-5.6-sol | A2 − A0 | strict pass@1 | 44 | +14.77 | [+1.14, +28.41] * |
| gpt-5.6-sol | A2 − A0 | pass@1 (N-1) | 44 | +20.45 | [+6.82, +34.09] * |
| gpt-5.6-sol | A2+R − A2 | mean reward | 44 | +6.71 | [+2.83, +11.18] * |
| gpt-5.6-sol | A2+R − A2 | strict pass@1 | 44 | +4.55 | [-4.55, +13.64] |
| gpt-5.6-sol | A2+R − A2 | pass@1 (N-1) | 44 | +7.95 | [-4.55, +20.45] |
| gpt-5.6-sol | A2+R − A0 | mean reward | 45 | +15.32 | [+9.24, +22.02] * |
| gpt-5.6-sol | A2+R − A0 | strict pass@1 | 45 | +18.89 | [+5.56, +32.22] * |
| gpt-5.6-sol | A2+R − A0 | pass@1 (N-1) | 45 | +27.78 | [+11.11, +44.44] * |
| gpt-5.6-sol | R − A0 | mean reward | 45 | +12.49 | [+6.89, +18.56] * |
| gpt-5.6-sol | R − A0 | strict pass@1 | 45 | +11.11 | [-1.11, +23.33] |
| gpt-5.6-sol | R − A0 | pass@1 (N-1) | 45 | +17.78 | [+1.11, +34.44] * |
| gpt-5.6-sol | A2+R − R | mean reward | 45 | +2.83 | [-0.84, +7.05] |
| gpt-5.6-sol | A2+R − R | strict pass@1 | 45 | +7.78 | [-1.11, +17.78] |
| gpt-5.6-sol | A2+R − R | pass@1 (N-1) | 45 | +10.00 | [-3.33, +23.33] |
| claude-opus-5.5 | A2 − A0 | mean reward | 45 | -4.26 | [-8.34, -0.52] * |
| claude-opus-5.5 | A2 − A0 | strict pass@1 | 45 | -0.00 | [-13.33, +13.15] |
| claude-opus-5.5 | A2 − A0 | pass@1 (N-1) | 45 | -6.48 | [-19.44, +6.48] |
| claude-opus-5.5 | A2+R − A2 | mean reward | 45 | +4.89 | [+1.69, +8.47] * |
| claude-opus-5.5 | A2+R − A2 | strict pass@1 | 45 | -4.44 | [-14.44, +5.00] |
| claude-opus-5.5 | A2+R − A2 | pass@1 (N-1) | 45 | +8.33 | [-3.70, +20.74] |
| claude-opus-5.5 | A2+R − A0 | mean reward | 45 | +0.62 | [-1.86, +3.06] |
| claude-opus-5.5 | A2+R − A0 | strict pass@1 | 45 | -4.44 | [-17.22, +7.59] |
| claude-opus-5.5 | A2+R − A0 | pass@1 (N-1) | 45 | +1.85 | [-12.04, +15.93] |
| claude-opus-5.5 | R − A0 | mean reward | 45 | -1.44 | [-5.04, +2.10] |
| claude-opus-5.5 | R − A0 | strict pass@1 | 45 | -3.33 | [-17.96, +11.67] |
| claude-opus-5.5 | R − A0 | pass@1 (N-1) | 45 | -2.04 | [-17.04, +13.15] |
| claude-opus-5.5 | A2+R − R | mean reward | 45 | +2.06 | [-1.03, +5.18] |
| claude-opus-5.5 | A2+R − R | strict pass@1 | 45 | -1.11 | [-12.78, +10.56] |
| claude-opus-5.5 | A2+R − R | pass@1 (N-1) | 45 | +3.89 | [-8.33, +15.56] |
| claude-sonnet-5.5 | A2 − A0 | mean reward | 45 | -0.15 | [-5.17, +5.15] |
| claude-sonnet-5.5 | A2 − A0 | strict pass@1 | 45 | -4.44 | [-20.00, +11.11] |
| claude-sonnet-5.5 | A2 − A0 | pass@1 (N-1) | 45 | -8.89 | [-25.56, +7.78] |
| claude-sonnet-5.5 | A2+R − A2 | mean reward | 45 | +5.83 | [+2.20, +9.84] * |
| claude-sonnet-5.5 | A2+R − A2 | strict pass@1 | 45 | +8.89 | [-1.11, +20.00] |
| claude-sonnet-5.5 | A2+R − A2 | pass@1 (N-1) | 45 | +16.67 | [+3.33, +30.00] * |
| claude-sonnet-5.5 | A2+R − A0 | mean reward | 45 | +5.68 | [+1.43, +10.61] * |
| claude-sonnet-5.5 | A2+R − A0 | strict pass@1 | 45 | +4.44 | [-7.78, +16.67] |
| claude-sonnet-5.5 | A2+R − A0 | pass@1 (N-1) | 45 | +7.78 | [-8.89, +24.44] |
| claude-sonnet-5.5 | R − A0 | mean reward | 45 | +4.18 | [-0.61, +9.35] |
| claude-sonnet-5.5 | R − A0 | strict pass@1 | 45 | +2.22 | [-11.11, +15.56] |
| claude-sonnet-5.5 | R − A0 | pass@1 (N-1) | 45 | +6.67 | [-7.78, +21.11] |
| claude-sonnet-5.5 | A2+R − R | mean reward | 45 | +1.50 | [-0.89, +3.99] |
| claude-sonnet-5.5 | A2+R − R | strict pass@1 | 45 | +2.22 | [-8.89, +13.33] |
| claude-sonnet-5.5 | A2+R − R | pass@1 (N-1) | 45 | +1.11 | [-12.22, +14.44] |
| gemini-4-argon | A2 − A0 | mean reward | 45 | -3.37 | [-7.24, +0.13] |
| gemini-4-argon | A2 − A0 | strict pass@1 | 45 | -5.56 | [-17.78, +7.78] |
| gemini-4-argon | A2 − A0 | pass@1 (N-1) | 45 | -7.78 | [-22.22, +5.56] |
| gemini-4-argon | A2+R − A2 | mean reward | 45 | +4.07 | [+0.93, +7.65] * |
| gemini-4-argon | A2+R − A2 | strict pass@1 | 45 | +4.44 | [-6.67, +16.67] |
| gemini-4-argon | A2+R − A2 | pass@1 (N-1) | 45 | +12.22 | [+0.00, +25.56] |
| gemini-4-argon | A2+R − A0 | mean reward | 45 | +0.69 | [-2.17, +3.64] |
| gemini-4-argon | A2+R − A0 | strict pass@1 | 45 | -1.11 | [-14.44, +13.33] |
| gemini-4-argon | A2+R − A0 | pass@1 (N-1) | 45 | +4.44 | [-7.78, +16.67] |
| gemini-4-argon | R − A0 | mean reward | 45 | +0.40 | [-2.65, +3.70] |
| gemini-4-argon | R − A0 | strict pass@1 | 45 | -5.56 | [-18.89, +7.78] |
| gemini-4-argon | R − A0 | pass@1 (N-1) | 45 | +2.22 | [-10.00, +14.44] |
| gemini-4-argon | A2+R − R | mean reward | 45 | +0.29 | [-1.52, +2.15] |
| gemini-4-argon | A2+R − R | strict pass@1 | 45 | +4.44 | [-6.67, +15.56] |
| gemini-4-argon | A2+R − R | pass@1 (N-1) | 45 | +2.22 | [-8.89, +13.33] |
| gemini-4-argon | A0 high − A0 | mean reward | 45 | -0.38 | [-1.72, +1.00] |
| gemini-4-argon | A0 high − A0 | strict pass@1 | 45 | -3.33 | [-11.11, +3.33] |
| gemini-4-argon | A0 high − A0 | pass@1 (N-1) | 45 | -2.22 | [-10.00, +5.56] |
| gemini-3.8-flash | A2 − A0 | mean reward | 44 | +8.35 | [+1.96, +15.25] * |
| gemini-3.8-flash | A2 − A0 | strict pass@1 | 44 | +7.95 | [-4.55, +20.45] |
| gemini-3.8-flash | A2 − A0 | pass@1 (N-1) | 44 | +14.77 | [+1.14, +29.55] * |
| gemini-3.8-flash | A2+R − A2 | mean reward | 45 | +6.54 | [+2.55, +11.01] * |
| gemini-3.8-flash | A2+R − A2 | strict pass@1 | 45 | +2.22 | [-7.78, +12.22] |
| gemini-3.8-flash | A2+R − A2 | pass@1 (N-1) | 45 | +20.00 | [+3.33, +36.67] * |
| gemini-3.8-flash | A2+R − A0 | mean reward | 44 | +13.91 | [+7.76, +20.50] * |
| gemini-3.8-flash | A2+R − A0 | strict pass@1 | 44 | +10.23 | [-2.27, +22.73] |
| gemini-3.8-flash | A2+R − A0 | pass@1 (N-1) | 44 | +32.95 | [+18.18, +47.73] * |
| gemini-3.8-flash | R − A0 | mean reward | 44 | +12.77 | [+6.67, +19.29] * |
| gemini-3.8-flash | R − A0 | strict pass@1 | 44 | +11.36 | [-2.27, +25.00] |
| gemini-3.8-flash | R − A0 | pass@1 (N-1) | 44 | +27.27 | [+9.09, +45.45] * |
| gemini-3.8-flash | A2+R − R | mean reward | 45 | +1.12 | [-1.60, +3.96] |
| gemini-3.8-flash | A2+R − R | strict pass@1 | 45 | -1.11 | [-12.22, +11.11] |
| gemini-3.8-flash | A2+R − R | pass@1 (N-1) | 45 | +5.56 | [-7.78, +18.89] |
| gemini-3.8-flash | A0 high − A0 | mean reward | 44 | +0.38 | [-1.87, +2.76] |
| gemini-3.8-flash | A0 high − A0 | strict pass@1 | 44 | -2.27 | [-7.95, +3.41] |
| gemini-3.8-flash | A0 high − A0 | pass@1 (N-1) | 44 | +2.27 | [-3.41, +7.95] |

