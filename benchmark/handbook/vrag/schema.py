"""Policy KB schema (one per task corpus). Typed data, not code: one generic interpreter consumes it for agent tools,
checklists and gates. Every item cites K0 block ids and a verbatim quote that lint checks against the source."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class M(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _coerce(cls, v: Any, info):
        """Authors sometimes emit numbers / nulls / dicts where the schema wants strings: coerce, don't reject."""
        f = cls.model_fields.get(info.field_name)
        ann = str(f.annotation) if f else ""
        args = getattr(f.annotation, "__args__", None) if f else None
        if ann.startswith("typing.Literal") and args and v not in args:
            d = f.default
            return d if d in args else args[0]
        if v is None:
            return [] if ann.startswith("list") else {} if ann.startswith("dict") else "" if "str" in ann else v
        if ann == "<class 'str'>" and not isinstance(v, str):
            return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        if ann.startswith("dict[str, str]") and isinstance(v, dict):
            return {str(k): (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)) for k, x in v.items()}
        if ann.startswith("list[str]") and isinstance(v, list):
            return [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in v]
        if ann.startswith("list[str]") and isinstance(v, str):
            return [v]
        return v


class Ref(M):
    blocks: list[str] = Field(default_factory=list)
    quote: str = ""


class Definition(M):
    term: str
    meaning: str
    refs: list[Ref] = Field(default_factory=list)


class Person(M):
    name: str
    role: str = ""
    email: str = ""
    slack: str = ""
    aliases: list[str] = Field(default_factory=list)
    authority: list[str] = Field(default_factory=list)  # what this person may authorize / approve / receive
    refs: list[Ref] = Field(default_factory=list)


class Channel(M):
    name: str  # "#intake-alerts", "pa@payer.com", "Jira project FIN", ...
    kind: Literal["slack_channel", "email", "jira", "calendar", "phone", "fax", "portal", "other"] = "other"
    purpose: str = ""
    refs: list[Ref] = Field(default_factory=list)


class FileSpec(M):
    name: str  # file name or pattern, e.g. "audit_log.xlsx", "intake_<CASE_ID>.xlsx"
    purpose: str = ""
    columns: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)  # e.g. "append-only", "copy blank template first"
    refs: list[Ref] = Field(default_factory=list)


class Template(M):
    id: str
    title: str
    kind: Literal["email", "slack", "dm", "jira", "calendar", "document", "log_row", "other"] = "other"
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    channel: str = ""
    blocks: list[str] = Field(default_factory=list)  # K0 blocks holding the template (pointer form)
    subject: str = ""  # verbatim with [Placeholders]; exact substring of the corpus
    body: str = ""  # verbatim with [Placeholders]; exact substring (inline format) or rebuilt from blocks
    placeholders: dict[str, str] = Field(default_factory=dict)  # placeholder -> where its value comes from
    refs: list[Ref] = Field(default_factory=list)


ActionKind = Literal["send_email", "reply_email", "forward_email", "draft_email", "post_slack", "send_dm",
                     "create_jira", "update_jira", "comment_jira", "calendar_event", "write_cells", "append_row",
                     "create_file", "copy_file", "rename_file", "move_email", "label_email", "none"]


class Action(M):
    kind: ActionKind
    target: str = ""  # channel / recipient / file / jira project
    template: str = ""  # Template.id when the SOP prescribes wording
    literal: str = ""  # exact text the SOP prescribes inline (e.g. a Slack tag line)
    fields: dict[str, str] = Field(default_factory=dict)  # column/field -> value or source
    note: str = ""


class Step(M):
    id: str
    kind: Literal["check", "decide", "act", "compute", "stop", "escalate", "wait", "info"] = "act"
    blocks: list[str] = Field(default_factory=list)  # verbatim source of the step (pointer form)
    instruction: str = ""  # optional short gloss; the verbatim text comes from blocks
    when: str = "always"
    actions: list[Action] = Field(default_factory=list)
    on_fail: str = ""
    refs: list[Ref] = Field(default_factory=list)


class Procedure(M):
    id: str
    title: str
    sections: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)  # block ids / ranges "D1.0100..D1.0160" the procedure spans
    trigger: str = ""
    steps: list[Step] = Field(default_factory=list)
    done_when: str = ""
    refs: list[Ref] = Field(default_factory=list)


RuleKind = Literal["prohibition", "obligation", "authority", "threshold", "deadline", "ordering", "stop",
                   "format", "escalation", "exception", "definition"]


class Rule(M):
    id: str
    kind: RuleKind
    statement: str  # faithful paraphrase, one sentence
    blocks: list[str] = Field(default_factory=list)
    when: str = "always"
    then: str = ""
    unless: str = ""
    params: dict[str, str] = Field(default_factory=dict)  # thresholds, amounts, durations, allowed people ...
    procedures: list[str] = Field(default_factory=list)
    severity: Literal["hard", "soft"] = "hard"
    refs: list[Ref] = Field(default_factory=list)


class Table(M):
    id: str
    title: str
    blocks: list[str] = Field(default_factory=list)  # header + row blocks (pointer form)
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    refs: list[Ref] = Field(default_factory=list)


class PolicyKB(M):
    company: str = ""
    summary: str = ""
    definitions: list[Definition] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    files: list[FileSpec] = Field(default_factory=list)
    templates: list[Template] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
