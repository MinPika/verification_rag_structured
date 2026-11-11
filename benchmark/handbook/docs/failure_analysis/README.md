# Failure analysis (criterion level)

Pipeline (run from the project root):
1. `.venv/bin/python -m vrag.failures` writes criterion metadata, the pass matrix per model × arm, the overlap
   (A2 / R / A2+R), the criteria that no trial ever passed, rescored metrics and final root-cause labels to `data/`.
2. Annotation inputs: `.venv/bin/python docs/failure_analysis/build_bundles.py --batches 5` writes one evidence bundle
   per residual failure (Haiku A2+R) and task-grouped batches. Root causes follow [PROTOCOL.md](PROTOCOL.md).
3. Figures: `~/.venv_deck/bin/python docs/failure_analysis/figures.py` writes `fig/*.png|pdf`.
4. Deck: `~/.venv_deck/bin/python docs/failure_analysis/build_deck.py` writes `HANDBOOK_failure_analysis.pptx`.

Inputs written by hand (kept in `data/`):
- `defects.json`: rubric defects verified by hand in grader code and task data, tiered T1 (cannot be passed by any
  SOP-consistent output), T2 (contradicts the SOP, or SOP names do not match the environment), T3 (brittle exact
  match). Each entry has its evidence.
- `labels.jsonl`: root-cause labels (5 annotators, 145 criteria). `labels_agreement.jsonl` holds a second,
  independent annotator's labels on a random 30, which give Cohen's κ.
- `labels_a2_regressions.jsonl`: why structure alone (A2) breaks criteria the plain agent passes, for the strong
  models (gpt-6-sol, Sonnet, Opus, Argon): 132 criteria that pass in A0 and fail (solid) in A2, labelled by 5
  annotators (mechanism PLAN-WRONG / PLAN-OMIT / PLAN-OVERREACH / KB-WRONG / EXECUTION / RUBRIC / NOISE / OTHER,
  with plan relation, A0-vs-A2 difference and evidence).
- `labels_opus_verifier_regressions.jsonl`: the 21 criteria Opus passes as a plain agent but fails in all four arms
  with the interwhen verifiers (R, A2+R, A2 noplan+R, A1 code+exec), labelled by 2 annotators (CHECKLIST-OMISSION /
  VERIFIER-REDIRECT / V-WRONG-SPEC / RUBRIC-DEFECT / NOISE, who the SOP sides with, what A0 and R did).

Definitions: solid failure = criterion passed in ≤ 25% of an arm's trials; pass@1 (N−1) = at most one failed
criterion; ceilings count defective criteria as impossible.
