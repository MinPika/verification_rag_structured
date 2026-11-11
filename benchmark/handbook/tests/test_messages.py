"""Message specs: one definition drives the pre-call check, the completion check and the checklist."""

from __future__ import annotations

from conftest import write_ledger

OK = "[Tool 'x' executed.]{\"ok\": true}"
T13 = {"key": "M1", "status": "required", "what": "Template 13 for Teodoor", "kinds": ["email_send"],
       "to": ["j.park@crestwood.edu"], "about": {"to_any": ["j.park@crestwood.edu"], "text_rx": "Teodoor"},
       "subject_rx": "Template 13.*Teodoor", "subject_hint": "Template 13 - Teodoor, 10741",
       "quotes": [{"text": "Please revoke all system access for [Name] effective [Date]."}],
       "values": ["10741"], "attach": [], "blocks": ["D1.0203"]}
FORBID = {"key": "M2", "status": "forbidden", "what": "COBRA notice to Teodoor", "kinds": ["email_send"],
          "about": {"text_rx": "COBRA.*Teodoor|Teodoor.*COBRA"}, "why": "the user excluded SOP 12.2"}
GOOD = {"to": "j.park@crestwood.edu", "subject": "Template 13 — Teodoor, 10741",
        "body": "Hi Jenna,\nPlease  revoke all system access for Gerta Teodoor (10741) effective 04/19/2026."}


def test_quote_matching_tolerates_spacing_and_fills(make_gate):
    g = make_gate()
    rx = g.quote_rx("Yourinsurancehasapproved your [Drug] infusion. Wehave the following")
    assert rx.search(g.mloose("Your insurance has approved your IVIG infusion.\n\nWe have the following:"))
    assert g.quote_rx("[A] [B]") is None  # nothing literal to check


def test_conforming_message_passes_and_counts_as_done(make_gate):
    g = make_gate(messages=[T13])
    a = g.classify("google_mail__send_email", GOOD)
    assert g.check_messages(a, []) == []
    assert [f.key for f in g.message_obligations([])] == ["m:M1"]
    assert g.message_obligations([a]) == []


def test_nonconforming_message_lists_every_problem(make_gate):
    g = make_gate(messages=[T13])
    a = g.classify("google_mail__send_email", {"to": "j.park@crestwood.edu", "subject": "Access for Teodoor",
                                               "body": "Hi Jenna, please remove Teodoor's access."})
    (f,) = g.check_messages(a, [])
    assert f.key == "m:M1"
    assert "Subject must follow" in f.problem and "Missing the SOP wording" in f.problem and "10741" in f.problem
    assert g.message_obligations([a]) != []


def test_unrelated_message_is_not_checked(make_gate):
    g = make_gate(messages=[T13])
    other = g.classify("google_mail__send_email", {"to": "j.park@crestwood.edu", "subject": "Lunch", "body": "Hi"})
    assert g.check_messages(other, []) == []


def test_second_conforming_copy_is_a_duplicate(make_gate):
    g = make_gate(messages=[T13])
    a = g.classify("google_mail__send_email", GOOD)
    (f,) = g.check_messages(a, [a])
    assert "already sent" in f.problem


def test_forbidden_message_blocks_once(make_gate):
    g = make_gate(messages=[FORBID])
    event = {"tool_name": "google_mail__send_email",
             "tool_input": {"to": "g.teodoor@crestwood.edu", "subject": "COBRA notice", "body": "Teodoor COBRA"}}
    first = g.pre(event)
    assert first["decision"] == "deny" and "must not be sent" in first["reason"]
    assert g.pre(event)["decision"] == "allow"


def test_dm_spec_matches_resolved_recipient(make_gate):
    spec = {"key": "M3", "status": "required", "what": "DM Alex about CASE-7", "kinds": ["slack_dm"],
            "to": ["alex.ontario@example.com"], "about": {"to_any": ["alex.ontario@example.com"]}, "values": ["CASE-7"]}
    g = make_gate(messages=[spec])
    write_ledger(g._test_state, [("slack__send_dm", {"user_id": "U005", "text": "CASE-7 needs review"}, OK)])
    assert g.message_obligations(g.executed(g.ledger())) == []


def test_message_specs_supersede_communication_guards(make_gate):
    guards = {"guards": [{"id": "G1", "type": "forbid", "match": {"kinds": ["email_send"], "to_any": ["x@y.com"]}}],
              "obligations": [{"id": "O1", "type": "action", "match": {"kinds": ["slack_post"]}},
                              {"id": "O2", "type": "action", "match": {"kinds": ["jira_create"]}}]}
    g = make_gate(guards, messages=[T13])
    mail = g.classify("google_mail__send_email", {"to": "x@y.com", "subject": "s", "body": "b"})
    assert g.check_guards(mail, []) == []
    assert {f.key for f in g.obligations([])} == {"m:M1", "o:O2"}


def test_checklist_lists_required_and_forbidden(make_gate):
    g = make_gate()
    text = g.checklist_text([T13 | {"enabled": True}, FORBID | {"enabled": True}])
    assert "SEND: Template 13 for Teodoor" in text and "j.park@crestwood.edu" in text
    assert "DO NOT SEND: COBRA notice to Teodoor" in text
