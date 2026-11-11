"""Fixtures: load the in-container gate module against a throw-away policy package, seed and state directory."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

GATE_SRC = Path(__file__).resolve().parents[1] / "vrag" / "runtime" / "policy_pkg" / "gate.py"

SLACK_SEED = {
    "users": {
        "U001": {"id": "U001", "name": "sam.moreno", "real_name": "Sam Moreno",
                 "profile": {"email": "sam.moreno@example.com", "display_name": "smoreno"}},
        "U005": {"id": "U005", "name": "aontario", "real_name": "Alex Ontario",
                 "profile": {"email": "alex.ontario@example.com"}},
    },
    "channels": {
        "C001": {"id": "C001", "name": "hr-offboarding"},
        "D777": {"id": "D777", "is_im": True, "user": "U005"},
    },
    "messages": {"C001": [{"user": "U001", "text": "Approved: release the hold on CASE-7", "ts": "1.0"}]},
}
INBOX = {"emails": [{"email_id": "4", "subject": "Pest contamination at dock 2", "from_addr": "ops@example.com",
                     "body_text": "see photos", "attachments": [{"filename": "dock2.jpg"}]}]}
KB = {"templates": [
    {"id": "TPL-claim", "title": "Claim submission email", "kind": "email",
     "subject": "[CLAIM SUBMISSION] CareIG NPI: [NPI] | [Patient Last Name] | DOS: [DOS]",
     "body": "Please find the claim attached.", "to": ["claims@payer.example"], "blocks": ["D1.0001"]},
    {"id": "TPL-pa", "title": "PA request email", "kind": "email",
     "subject": "[PA REQUEST] CareIG | [Patient Last Name] | Dx: [Dx]", "body": "PA request.", "blocks": []},
    {"id": "TPL-sep", "title": "Separation post", "kind": "slack", "channel": "#hr-offboarding",
     "body": "SEPARATION: [Employee Name], [Employee ID], Last Day: [Date]",
     "placeholders": {"[Employee Name]": "roster", "[Employee ID]": "roster", "[Date]": "last day"}, "blocks": []},
]}


@pytest.fixture
def make_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """make_gate(guards=None, messages=None) -> fresh gate module; ``gate._test_state`` is its state dir."""
    counter = {"n": 0}

    def factory(guards: dict | None = None, messages: list[dict] | None = None):
        counter["n"] += 1
        root = tmp_path / f"g{counter['n']}"
        pkg, seed, state, work = root / "pkg", root / "seed", root / "state", root / "work"
        for d in (pkg / "data", seed / "slack", seed / "google_mail", state, work):
            d.mkdir(parents=True)
        (pkg / "data" / "kb.json").write_text(json.dumps(KB))
        (pkg / "data" / "guards.json").write_text(json.dumps(guards or {}))
        if messages is not None:
            (pkg / "data" / "messages.json").write_text(json.dumps({"messages": messages}))
        (seed / "slack" / "slack.json").write_text(json.dumps(SLACK_SEED))
        (seed / "google_mail" / "inbox.json").write_text(json.dumps(INBOX))
        for k, v in {"VRAG_PKG": pkg, "VRAG_SEED": seed, "VRAG_STATE": state, "VRAG_WORKDIR": work}.items():
            monkeypatch.setenv(k, str(v))
        name = f"gate_under_test_{counter['n']}"
        spec = importlib.util.spec_from_file_location(name, GATE_SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        mod._test_state = state
        mod._test_work = work
        return mod

    return factory


def write_ledger(state: Path, calls: list[tuple[str, dict, str]]) -> None:
    """calls: (tool, args, observation text); writes action/observation pairs as the runner callback does."""
    with open(state / "ledger.jsonl", "w") as fh:
        for i, (tool, args, obs) in enumerate(calls):
            fh.write(json.dumps({"type": "action", "call_id": f"c{i}", "tool": tool, "args": args}) + "\n")
            fh.write(json.dumps({"type": "observation", "call_id": f"c{i}", "tool": tool, "text": obs}) + "\n")
