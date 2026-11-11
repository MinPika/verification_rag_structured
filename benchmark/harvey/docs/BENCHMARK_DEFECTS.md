# Benchmark defects found in Harvey LAB firm-knowledge (verified by hand)

| Task | Criterion | Defect | How found |
|---|---|---|---|
| 189 | C-037 (precision) | The allowed set is not in the criterion text: "[same 37-entry set] ending '...; 1018-00003 (Penterra Pharma); 1022-00002 (Northgate Telecom).'" The judge cannot know the full set, so verdicts on it are guesses (sonnet-5 and gpt-5.6-sol split on luna's run). The only such criterion among all 2,623. | base-dev15 failure review; `grep "set]"` over all task.json files |
