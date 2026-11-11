"""Unit tests for the deterministic interwhen gate (vrag/runtime/policy_pkg/gate.py)."""

from __future__ import annotations

import io
import json

import pytest
from conftest import write_ledger

OK = "[Tool 'x' executed.]{\"ok\": true}"


# ---- action classification ---------------------------------------------------------------------------------

def test_dm_resolves_recipient_identity(make_gate):
    g = make_gate()
    a = g.classify("slack__send_dm", {"user_id": "U005", "text": "Please review CASE-7"})
    assert a.kind == "slack_dm"
    assert a.to == ["alex.ontario@example.com"]
    assert {"aontario", "alexontario", "u005"} <= set(a.people)


@pytest.mark.parametrize("channel_id", ["U005", "D777"])
def test_post_into_user_or_im_channel_is_a_dm(make_gate, channel_id):
    g = make_gate()
    a = g.classify("slack__post_message", {"channel_id": channel_id, "text": "hi"})
    assert a.kind == "slack_dm"
    assert a.to == ["alex.ontario@example.com"]


def test_channel_post_stays_a_post(make_gate):
    g = make_gate()
    a = g.classify("slack__post_message", {"channel_id": "C001", "text": "SEPARATION: A, 1, Last Day: 01/02/2026"})
    assert (a.kind, g.channel_name(a.channel)) == ("slack_post", "hr-offboarding")


@pytest.mark.parametrize("key", ["file_path", "path"])
def test_write_file_records_file_name(make_gate, key):
    g = make_gate()
    a = g.classify("syntara__writeFile", {key: "/workdir/closed_workbooks.txt", "content": "x"})
    assert (a.kind, a.files) == ("file_write", ["closed_workbooks.txt"])


def test_python_write_detects_target_file(make_gate):
    g = make_gate()
    a = g.classify("syntara__executePython", {"code": "open('/workdir/out.txt','w').write('x')"})
    assert a.kind == "file_write" and "out.txt" in a.files


def test_reply_and_forward_take_subject_and_sender_from_seed_mail(make_gate):
    g = make_gate()
    fwd = g.classify("google_mail__forward_email", {"email_id": "4", "to": "boss@example.com", "body": "FYI"})
    rep = g.classify("google_mail__reply_to_email", {"email_id": "4", "body": "Thanks"})
    assert fwd.subject == "Fwd: Pest contamination at dock 2" and fwd.to == ["boss@example.com"]
    assert rep.subject == "Re: Pest contamination at dock 2" and rep.to == ["ops@example.com"]


def test_forward_carries_original_attachments(make_gate):
    g = make_gate()
    a = g.classify("google_mail__forward_email", {"email_id": "4", "to": "boss@example.com"})
    assert a.files == ["dock2.jpg"]


def test_email_attachments_become_files(make_gate):
    g = make_gate()
    a = g.classify("google_mail__send_email", {"to": "a@b.com", "subject": "s", "body": "b",
                                               "attachments": ["/workdir/claim_2026.pdf"]})
    assert a.files == ["claim_2026.pdf"]


# ---- matching ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("spec, expected", [
    ({"kinds": ["slack_dm"], "to_any": ["alex.ontario@example.com"]}, True),
    ({"kinds": ["slack_dm"], "channel": "@aontario"}, True),
    ({"kinds": ["slack_dm", "slack_post"], "to_any": ["Alex.Ontario@example.com"], "text_rx": "CASE-7"}, True),
    ({"kinds": ["slack_dm"], "to_any": ["sam.moreno@example.com"]}, False),
    ({"kinds": ["slack_dm"], "channel": "hr-offboarding"}, False),
])
def test_dm_matching(make_gate, spec, expected):
    g = make_gate()
    a = g.classify("slack__send_dm", {"user_id": "U005", "text": "Please review CASE-7"})
    assert g._match(spec, a) is expected


def test_channel_matching_ignores_punctuation(make_gate):
    g = make_gate()
    a = g.classify("slack__post_message", {"channel_id": "C001", "text": "x"})
    assert g._match({"kinds": ["slack_post"], "channel": "#HR_Offboarding"}, a)


def test_text_rx_accepts_bracket_free_variant(make_gate):
    g = make_gate()
    a = g.classify("google_mail__send_email", {"to": "c@p.com", "subject": "[CLAIM SUBMISSION] CareIG", "body": ""})
    assert g._match({"kinds": ["email_send"], "subject_rx": "CLAIM SUBMISSION CareIG"}, a)


# ---- execution outcome ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, ok", [
    ("[Tool 'x' executed.]{\"ok\": false, \"error\": \"channel_not_found\"}", False),
    ("[Tool 'x' executed.]{\"status\": \"success\", \"event\": {\"id\": 1}}", True),
    ("[Tool 'x' executed.]{\"stdout\": \"\", \"returncode\": 1}", False),
    ("Error: file not found", False),
    ("[Tool 'x' executed.]{\"key\": \"OPS-4\", \"note\": \"error budget not found in description\"}", True),
])
def test_succeeded(make_gate, text, ok):
    assert make_gate().succeeded(text) is ok


def test_executed_skips_failed_and_rejected_calls(make_gate):
    g = make_gate()
    write_ledger(g._test_state, [
        ("slack__send_dm", {"user_id": "U005", "text": "a"}, OK),
        ("slack__send_dm", {"user_id": "U001", "text": "b"}, "[Tool 'x' executed.]{\"ok\": false}"),
    ])
    with open(g._test_state / "ledger.jsonl", "a") as fh:
        fh.write(json.dumps({"type": "action", "call_id": "r", "tool": "slack__send_dm", "args": {"user_id": "U001"}})
                 + "\n" + json.dumps({"type": "rejection", "call_id": "r"}) + "\n")
    assert [a.to for a in g.executed(g.ledger())] == [["alex.ontario@example.com"]]


# ---- formats, guards, obligations ------------------------------------------------------------------------------

def _email(g, subject, to="claims@payer.example"):
    return g.classify("google_mail__send_email", {"to": to, "subject": subject, "body": "Please find attached."})


def test_subject_template_is_chosen_by_literal_tag(make_gate):
    g = make_gate()
    assert g._subject_template("[CLAIM SUBMISSION] CareIG NPI: 1 | Doe | DOS: 2026-03-15")["id"] == "TPL-claim"
    assert g._subject_template("[PA REQUEST] CareIG | Doe | Dx: G61")["id"] == "TPL-pa"
    assert g._subject_template("Re: hello") is None


def test_email_subject_format(make_gate):
    g = make_gate()
    assert g.check_email_format(_email(g, "[CLAIM SUBMISSION] CareIG NPI: 1 | Doe | DOS: 2026-03-15")) == []
    assert g.check_email_format(_email(g, "[CLAIMSUBMISSION] CareIGNPI: 1 | Doe | DOS: 2026-03-15")) == []
    bad = g.check_email_format(_email(g, "[CLAIM SUBMISSION] CareIG | Doe"))
    assert [f.key for f in bad] == ["subj:TPL-claim"]
    wrong_to = g.check_email_format(_email(g, "[CLAIM SUBMISSION] CareIG NPI: 1 | Doe | DOS: x", to="x@y.com"))
    assert [f.key for f in wrong_to] == ["to:TPL-claim"]


def test_unfilled_placeholder_is_flagged_but_tags_are_not(make_gate):
    g = make_gate()
    bad = g.classify("slack__post_message", {"channel_id": "C001", "text": "SEPARATION: [Employee Name], 1"})
    good = g.classify("slack__post_message", {"channel_id": "C001", "text": "[OUT OF SCOPE] SEPARATION: A, 1"})
    assert [f.key for f in g.check_placeholders(bad)] == ["placeholders"]
    assert g.check_placeholders(good) == []


def test_require_text_ignores_formatting(make_gate):
    g = make_gate({"guards": [{"id": "G1", "type": "require_text", "match": {"kinds": ["slack_post"]},
                               "must_contain": ["4153.75", "CASE-1001"]}]})
    ok = g.classify("slack__post_message", {"channel_id": "C001", "text": "case-1001 billed $4,153.75"})
    bad = g.classify("slack__post_message", {"channel_id": "C001", "text": "CASE-1001 billed $4,340.25"})
    assert g.check_guards(ok, []) == []
    assert [f.key for f in g.check_guards(bad, [])] == ["g:G1"]


def test_forbid_guard_blocks_once_then_allows_identical_retry(make_gate):
    g = make_gate({"guards": [{"id": "G1", "type": "forbid", "match": {"kinds": ["email_send"],
                                                                     "to_any": ["legal@x.com"]}}]})
    event = {"tool_name": "google_mail__send_email", "tool_input": {"to": "legal@x.com", "subject": "s", "body": "b"}}
    assert g.pre(event)["decision"] == "deny"
    assert g.pre(event)["decision"] == "allow"


def test_authorization_guard(make_gate):
    spec = {"guards": [{"id": "G1", "type": "require_authorization", "match": {"kinds": ["slack_post"],
                                                                             "text_rx": "release"},
                        "people": ["sam moreno"], "about_rx": "CASE-7"}]}
    g = make_gate(spec)
    post = g.classify("slack__post_message", {"channel_id": "C001", "text": "Hold released for CASE-7"})
    assert g.check_guards(post, []) == []  # Sam's seed Slack message authorizes CASE-7
    spec["guards"][0]["about_rx"] = "CASE-9"
    g2 = make_gate(spec)
    assert [f.key for f in g2.check_guards(post, [])] == ["g:G1"]


def test_dm_obligation_is_satisfied_by_send_dm(make_gate):
    g = make_gate({"obligations": [{"id": "O1", "type": "action", "message": "DM Alex",
                                    "match": {"kinds": ["slack_dm"], "to_any": ["alex.ontario@example.com"]}}]})
    assert [f.key for f in g.obligations(g.ledger())] == ["o:O1"]
    write_ledger(g._test_state, [("slack__send_dm", {"user_id": "U005", "text": "hi"}, OK)])
    assert g.obligations(g.ledger()) == []


def test_unmet_obligation_points_at_near_miss(make_gate):
    g = make_gate({"obligations": [{"id": "O1", "type": "action", "message": "Ticket missing", "fix": "Create it.",
                                    "match": {"kinds": ["jira_create"], "text_rx": "OFFBOARD-Teodoor"}}]})
    write_ledger(g._test_state, [("jira__create_issue", {"project_key": "OFFBOARD", "summary": "Ticket for Teodoor"},
                                  "[Tool 'x' executed.]{\"key\": \"OFFBOARD-1\"}")])
    (finding,) = g.obligations(g.ledger())
    assert "Ticket for Teodoor" in finding.fix


def test_row_obligation_reads_live_workbook(make_gate):
    openpyxl = pytest.importorskip("openpyxl")
    g = make_gate({"obligations": [{"id": "O1", "type": "row", "file_rx": r"log\.xlsx",
                                    "where": {"Case": "CASE-7"}, "expect": {"Status": "^Closed$"}}]})
    wb = openpyxl.Workbook()
    wb.active.append(["Case", "Status"])
    wb.active.append(["CASE-7", "Open"])
    wb.save(g._test_work / "log.xlsx")
    assert [f.key for f in g.obligations([])] == ["o:O1"]
    wb.active["B2"] = "Closed"
    wb.save(g._test_work / "log.xlsx")
    assert g.obligations([]) == []


# ---- stop hook and fail-open -----------------------------------------------------------------------------------

def test_stop_refuses_until_stale_then_allows(make_gate):
    g = make_gate({"obligations": [{"id": "O1", "type": "action", "message": "DM Alex",
                                    "match": {"kinds": ["slack_dm"]}}]})
    assert [g.stop()["decision"] for _ in range(3)] == ["deny", "deny", "allow"]


def test_stop_allows_when_done(make_gate):
    g = make_gate({"obligations": [{"id": "O1", "type": "action", "match": {"kinds": ["slack_dm"]}}]})
    write_ledger(g._test_state, [("slack__send_dm", {"user_id": "U005", "text": "hi"}, OK)])
    assert g.stop()["decision"] == "allow"


def test_hook_fails_open_on_bad_input(make_gate, monkeypatch, capsys):
    g = make_gate()
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    monkeypatch.setattr("sys.argv", ["gate", "pre"])
    g.main()
    assert json.loads(capsys.readouterr().out) == {"decision": "allow"}
