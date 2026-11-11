# Root-cause annotation protocol (residual failures of A2+R)

Unit: one rubric criterion that is a solid failure (passed in ≤ 25% of trials) for a model × arm. Each criterion gets
exactly one primary cause, an optional secondary cause, and the structured fields below. Annotators use only artefacts
that exist offline: the criterion and its grader code, the failing trials (trajectory, interwhen decisions and checklist,
grader feedback), the interwhen baseline's verifier module, our drafted plan, and the task's SOP and seed data.

## Primary cause (pick the earliest point in the pipeline where the failure became inevitable)
| Code | Meaning | Decisive test |
|---|---|---|
| SOURCE | The SOP plus data do not determine what the rubric requires (ambiguous, contradictory, unstated convention, rubric stricter than the SOP, or arithmetic/derivation the SOP does not define as the rubric does) | A careful human reading only the SOP and data could reasonably do otherwise |
| V-GAP | The requirement is determined by the SOP, but the interwhen baseline's module has no check covering it | No Comm, pre_rule or state_rule targets this object or field |
| V-WEAK | The module checks the object, but not the detail the rubric tests (field, value, wording, count), so the wrong output passes the verifier | The check exists but would accept the failing output |
| V-WRONG | The module's spec conflicts with the rubric or SOP (wrong value, wording, recipient or rule; over-literal), and the agent followed it | The agent complied with a verifier message or checklist item that encodes the wrong thing |
| A-IGNORED | The verifier flagged it (pre-call denial, completion refusal, or explicit checklist item) and the agent did not comply in the end (gave up, hit the budget, or a stale denial let it through) | Evidence of a flag, and the final state still violates it |
| A-EXEC | The model attempted the right action and the requirement was determined and checked loosely or not at all, but it made an execution slip (wrong cell or row, typo, format, missing attachment, extra or duplicate item) | The intended action is visible in the trajectory |
| A-REASON | The model misjudged the case despite the information being available and read (wrong decision, branch, authority or eligibility), and no verifier corrected it | The model read the relevant SOP or data and still decided wrongly |
| READ | The needed SOP passage or data was never opened or was skipped (retrieval or reading miss) | No tool call read the needed passage or file |
| PLAN | Our drafted plan or structure stated something wrong or omitted it, and the agent followed the plan | The plan text shows the error and the agent's action matches it |
| INFRA | A tool or harness limitation (the tool cannot perform the needed action, a service error, a context or condenser artefact) | The evidence shows the tool could not do it |

## Structured fields (all required)
- `verifier_coverage`: full | partial | none (does the module check exactly what the rubric checks?)
- `verifier_flagged`: yes | no (in a failing trial, did a denial or refusal, or a checklist line, address this item?)
- `plan_status`: correct | wrong | silent (does our plan address it, and is it right?)
- `sop_determines`: yes | ambiguous | no (does the SOP plus data determine the rubric's expectation?)
- `agent_read`: yes | no | unknown (did the agent read the SOP or data needed?)
- `rubric_issue`: yes | no (is the rubric itself questionable: stricter than the SOP, inconsistent, or arbitrary?)
- `evidence`: at most 3 sentences with short quotes and file references
- `confidence`: high | medium | low
