"""Arm V: the plain LAB agent plus the Firm Verifier API as callable tools (the code-API design: no hooks; the agent
decides when to verify). Tools run host-side as deterministic lookups over the frozen FV cards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..arms import ARMS, Arm
from . import api

MAX_CHECKS = 40

TOOLS: list[dict] = [
    {"name": "fv_check",
     "description": ("Firm Verifier: check ONE condition about ONE matter against the firm's offline-verified index. "
                     "Returns verdict TRUE / FALSE / SECONDARY / NOT_FOUND / UNKNOWN with evidence (file path + "
                     "verbatim quote). "
                     + api.FIELDS_HELP),
     "parameters": {"type": "object", "properties": {
         "matter_id": {"type": "string", "description": "DMS folder id, e.g. 1003-00001"},
         "field": {"type": "string", "description": "e.g. outcome, practice_area, term.earnout, issue.stark_law"},
         "value": {"type": "string", "description": "the value you want confirmed, e.g. dismissed, "
                                                   "capital_markets, present, analysed, 2023"}},
         "required": ["matter_id", "field"]}},
    {"name": "fv_check_many",
     "description": "Firm Verifier: run several fv_check calls at once (max 40). Use it to verify a candidate list.",
     "parameters": {"type": "object", "properties": {"checks": {"type": "array", "items": {
         "type": "object", "properties": {"matter_id": {"type": "string"}, "field": {"type": "string"},
                                          "value": {"type": "string"}}, "required": ["matter_id", "field"]}}},
         "required": ["checks"]}},
    {"name": "fv_matter",
     "description": ("Firm Verifier: the verified card of one matter (client, practice areas, the firm client's role, "
                     "status, outcome, dates, relief sought, executed vs draft-only terms, issues analysed vs only "
                     "mentioned, people)."),
     "parameters": {"type": "object", "properties": {"matter_id": {"type": "string"}}, "required": ["matter_id"]}},
    {"name": "fv_doc",
     "description": ("Firm Verifier: the card of one file: type, date, stage (draft / redline / execution_version / "
                     "executed / filed / final / unsigned), signed, summary, terms, issues."),
     "parameters": {"type": "object", "required": ["path"], "properties": {"path": {
         "type": "string", "description": "<matter>/<folder>/<file>, e.g. 1003-00001/Memos/x.docx"}}}},
]

PROMPT = """

## Firm Verifier (fv_* tools)

You also have **verifier tools** built offline from every document in the DMS. They answer narrow questions about a
matter or a file with TRUE / FALSE / SECONDARY / NOT_FOUND / UNKNOWN plus evidence (path + verbatim quote):

- `fv_check(matter_id, field, value)` / `fv_check_many(checks)`: fields `practice_area`, `client_role`, `status`,
  `outcome`, `closed_year`, `opened_year`, `relief_sought_by_client`, `term.<key>` (terms in **executed/filed**
  documents; drafts are reported separately), `issue.<key>` (value `analysed` or `mentioned`).
- `fv_matter(matter_id)`: the matter's verified card. `fv_doc(path)`: a file's stage (draft vs executed), date, terms.

How to use them:
0. **The verifier does not find matters and does not tell you when you have found them all.** Search the DMS
   exactly as thoroughly as you would without it (questions often need many matters); verification comes after,
   and a few TRUE verdicts are not a reason to stop searching.
1. Find candidate matters with your usual search — all of them.
2. **Before you list a matter as qualifying, verify each condition of the question for it** (one `fv_check_many` call
   for the whole candidate list is cheapest). Typical conditions: practice area, outcome (settled ≠ dismissed), the
   firm client's role / relief sought, executed vs draft documents, a specific term (an earnout is not a CVR), an
   issue analysed vs merely mentioned, status/closing year.
3. FALSE with evidence → drop the matter or explain in one line why the question still covers it. NOT_FOUND → the
   index has no record of it; drop only after reading the matter's key document confirms it is absent.
   SECONDARY (practice_area) → the matter belongs to another practice group and only touched this one; a question
   about "our <practice> matters" usually means the group's own (primary) matters.
   UNKNOWN → decide from the documents yourself; UNKNOWN is never a reason to drop a matter.
4. In `response.md`, list only qualifying matters as the answer; do not present non-qualifying matters as part of
   the answer (if you mention them, label them clearly as excluded).
"""


class _Exec:
    """Wraps LAB's ToolExecutor: handles fv_* tools host-side, delegates everything else unchanged."""

    def __init__(self, inner: Any, log: list[dict]):
        self._inner, self._log = inner, log

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def execute(self, tool_name: str, arguments: str | dict) -> str:
        if not tool_name.startswith("fv_"):
            return self._inner.execute(tool_name, arguments)
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
            if tool_name == "fv_check":
                out: Any = api.check(str(args.get("matter_id", "")), str(args.get("field", "")), args.get("value"))
            elif tool_name == "fv_check_many":
                checks = (args.get("checks") or [])[:MAX_CHECKS]
                out = [{"matter_id": c.get("matter_id"), **api.check(str(c.get("matter_id", "")),
                                                                     str(c.get("field", "")), c.get("value"))}
                       for c in checks if isinstance(c, dict)]
            elif tool_name == "fv_matter":
                out = api.matter(str(args.get("matter_id", "")))
            elif tool_name == "fv_doc":
                out = api.doc(str(args.get("path", "")))
            elif tool_name == "fv_check_complete":
                out = api.check_complete(args.get("conditions") or [], [str(m) for m in args.get("matters") or []])
            else:
                out = {"error": f"unknown tool {tool_name}"}
        except Exception as e:  # a verifier bug must never crash the run
            out = {"error": f"{type(e).__name__}: {e}"}
        self._log.append({"tool": tool_name, "args": arguments, "result": out})
        return json.dumps(out, ensure_ascii=False)


class VArm(Arm):
    name = "V"

    def prepare(self, *, task_id: str, executor: Any, tools: list[dict], system_prompt: str,
                trial_dir: Path) -> tuple[Any, list[dict], str]:
        return _Exec(executor, self.log), tools + TOOLS, system_prompt + PROMPT


ARMS["V"] = VArm


COMPLETE_TOOL = {
    "name": "fv_check_complete",
    "description": ("Firm Verifier: verify the claim 'these are ALL the matters satisfying these conditions' against "
                    "the offline index. Returns index matches missing from your list (leads to confirm in the "
                    "documents), listed matters the index contradicts, and possible matches with unknown fields."),
    "parameters": {"type": "object", "required": ["conditions", "matters"], "properties": {
        "conditions": {"type": "array", "description": "the question's conditions as fv_check fields",
                       "items": {"type": "object", "properties": {"field": {"type": "string"},
                                                                  "value": {"type": "string"}},
                                 "required": ["field"]}},
        "matters": {"type": "array", "items": {"type": "string"}, "description": "your current answer list"}}}}

COMPLETE_PROMPT = """
5. **Completeness check (before writing response.md).** Call `fv_check_complete(conditions, matters)` with the
   question's conditions and your current list. For each matter in `missing_from_your_list`, open its key document
   and add it only if the document confirms it; for each `listed_but_contradicted`, re-check it. The index can be
   wrong in both directions, so the documents decide. For superlative questions ("most recent", "largest") use it
   to make sure you compared all candidates.
"""


class VCArm(VArm):
    name = "VC"

    def prepare(self, *, task_id: str, executor: Any, tools: list[dict], system_prompt: str,
                trial_dir: Path) -> tuple[Any, list[dict], str]:
        ex, tl, sp = super().prepare(task_id=task_id, executor=executor, tools=tools, system_prompt=system_prompt,
                                     trial_dir=trial_dir)
        return ex, tl + [COMPLETE_TOOL], sp + COMPLETE_PROMPT


ARMS["VC"] = VCArm


LATE_MSG = """Before you finish: verify the matters in your response.md with the Firm Verifier tools, which are now
available to you (they were not shown earlier so they would not change how you searched).
""" + PROMPT.replace("## Firm Verifier (fv_* tools)", "").replace("How to use them:", "How to use them now:") + """
Then update response.md if any matter fails verification (or if a check leads you to a matter you missed), and call
finish again. You will not be asked again."""


class _LateExec(_Exec):
    """A0 until the first ``finish``: that call is refused once, the fv_* tools are added to the live tool list, and
    the agent is asked to verify its answer; the next ``finish`` goes through."""

    def __init__(self, inner: Any, log: list[dict], tools: list[dict], extra: list[dict], msg: str):
        super().__init__(inner, log)
        self._tools, self._extra, self._msg, self._asked = tools, extra, msg, False

    def execute(self, tool_name: str, arguments: str | dict) -> str:
        if tool_name == "finish" and not self._asked:
            self._asked = True
            self._tools.extend(self._extra)  # run_agent passes this same list to every model call
            self._log.append({"tool": "late_gate", "args": arguments, "result": {"note": "verification requested"}})
            return self._msg
        if tool_name.startswith("fv_") and not self._asked:
            return "Error: unknown tool: " + tool_name
        return super().execute(tool_name, arguments)


class VLArm(Arm):
    name = "VL"
    extra: list[dict] = TOOLS
    msg = LATE_MSG

    def prepare(self, *, task_id: str, executor: Any, tools: list[dict], system_prompt: str,
                trial_dir: Path) -> tuple[Any, list[dict], str]:
        live = list(tools)
        return _LateExec(executor, self.log, live, list(self.extra), self.msg), live, system_prompt


class VLCArm(VLArm):
    name = "VLC"
    extra = TOOLS + [COMPLETE_TOOL]
    msg = LATE_MSG.replace("Then update response.md", COMPLETE_PROMPT.strip().replace("5. ", "") + "\n\nThen update "
                                                                                                    "response.md")


ARMS["VL"] = VLArm
ARMS["VLC"] = VLCArm
