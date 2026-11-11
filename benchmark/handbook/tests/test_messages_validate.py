"""Compile-time validation of message specs against a real dev task's SOP and data (skipped without the KB)."""

from __future__ import annotations

import copy

import pytest

from vrag import paths
from vrag.messages import validate

TASK = "hr_crestwood_university_2071c562"
pytestmark = pytest.mark.skipif(not (paths.KB / TASK / "env.txt").exists(), reason="local KB not built")

BASE = {"key": "M1", "status": "required", "what": "Template 13 for Teodoor", "kinds": ["email_send"],
        "to": ["j.park@crestwood.edu"], "about": {"to_any": ["j.park@crestwood.edu"], "text_rx": "Teodoor"},
        "subject_rx": "Teodoor", "quotes": [{"text": "Please revoke all system access for the following employee"}],
        "values": ["10741"],
        "sample": {"kind": "email_send", "to": ["j.park@crestwood.edu"], "subject": "Template 13 - Teodoor, 10741",
                   "text": "Hi Jenna, Please revoke all system access for the following employee: Gerta Teodoor, "
                           "10741."}}


def run(*specs):
    return validate({"messages": [copy.deepcopy(s) for s in specs]}, TASK)


def test_grounded_spec_is_kept():
    (m,) = run(BASE)["messages"]
    assert m["enabled"] and m["pre"] and m["quotes"] and m["values"] == ["10741"]


def test_ungrounded_quote_value_and_instruction_are_removed():
    spec = copy.deepcopy(BASE)
    spec["quotes"] += [{"text": "This sentence does not appear anywhere in the handbook at all"},
                       {"text": "Email j.park@crestwood.edu using Template 13 (subject: [Template Name])"}]
    spec["values"] += ["NOT-IN-DATA-123"]
    (m,) = run(spec)["messages"]
    assert len(m["quotes"]) == 1 and m["values"] == ["10741"]


def test_requirements_the_sample_fails_are_dropped():
    spec = copy.deepcopy(BASE)
    spec["sample"]["text"] = "Hi Jenna, please cut access for Gerta Teodoor, 10741."
    (m,) = run(spec)["messages"]
    assert m["quotes"] == [] and m["values"] == ["10741"]


def test_unknown_recipient_drops_the_spec():
    spec = copy.deepcopy(BASE) | {"to": ["nobody@nowhere.example"]}
    res = run(spec)
    assert res["messages"] == [] and "recipients" in res["dropped"][0]["drop_reason"]


def test_forbidden_needs_allowed_lookalikes_it_does_not_catch():
    forbid = {"key": "M2", "status": "forbidden", "what": "COBRA to Teodoor", "kinds": ["email_send"],
              "about": {"text_rx": "COBRA"},
              "sample": {"kind": "email_send", "to": ["g.teodoor@crestwood.edu"], "text": "COBRA notice"}}
    assert run(forbid)["messages"] == []
    ok = forbid | {"allowed": [{"kind": "email_send", "to": ["j.park@crestwood.edu"], "text": "Access request"}]}
    assert [m["key"] for m in run(ok)["messages"]] == ["M2"]
    bad = forbid | {"allowed": [{"kind": "email_send", "to": ["n.ashford@crestwood.edu"], "text": "COBRA question"}]}
    assert run(bad)["messages"] == []


def test_overlapping_required_specs_lose_the_pre_call_check():
    other = copy.deepcopy(BASE) | {"key": "M9", "what": "another email to Jenna about Teodoor"}
    msgs = run(BASE, other)["messages"]
    assert [m["pre"] for m in msgs] == [False, False]
