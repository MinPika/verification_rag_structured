"""Cutting a verifier module into SOP-mapped code units."""

from __future__ import annotations

from vrag.vcode import parse

SRC = '''
EMP, EID = "Gerta Teodoor", "10741"
R_T13 = ("18", "Please revoke all system access", "Template 13")
LIST_REFS = [("12.4", "Step 1: Email j.park", "12.4 Step 1"), ("19", "When composing", "19 Subject")]
FOLDERS = ("Offboarding", "General")


def _about(a) -> bool:
    return EMP in a.text


def specs(ctx):
    return [Comm("t13", "email", lambda a: _about(a), f"Template 13 for {EMP}", [R_T13], to=["j.park@x.edu"])]


def _no_dm(ctx, a):
    return "use the channel" if a.kind == "slack_dm" else None


RULES = (comm_rules("comms", specs)
         + pre_rule("slack.no_dm", _no_dm, LIST_REFS)
         + state_rule("mail.read", _no_dm, [("17", "Mark as read", "17")]))
'''


def test_parse_finds_messages_rules_refs_and_constants():
    refs, consts, funcs, units = parse(SRC)
    assert set(refs) == {"R_T13", "LIST_REFS"} and len(refs["LIST_REFS"]) == 2
    assert {"EMP", "EID", "FOLDERS"} <= set(consts)
    assert [u["id"] for u in units] == ["message:t13", "rule:slack.no_dm", "rule:mail.read"]
    assert {"_about", "specs", "_no_dm"} <= set(funcs)
