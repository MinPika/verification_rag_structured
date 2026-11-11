"""Bridge payload rewriting: content flattening and model aliases."""

from __future__ import annotations

import json

from vrag.bridge import flatten, real_model, transform
from vrag.run_arm import agent_model


def test_alias_round_trip():
    assert agent_model("gpt-5.6-sol") == "gpt_5.6-sol" and "gpt-5" not in agent_model("gpt-5.6-sol")
    assert real_model(agent_model("gpt-5.6-sol")) == "gpt-5.6-sol"
    assert agent_model("claude-opus-5.5") == "claude-opus-5.5" and real_model("gpt-6-sol") == "gpt-6-sol"


def test_transform_flattens_and_restores_model():
    raw = json.dumps({"model": "gpt_5.6-sol", "messages": [
        {"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "image_url"}, "b"]},
        {"role": "assistant", "content": "c"}]}).encode()
    body, model = transform(raw)
    out = json.loads(body)
    assert model == "gpt-5.6-sol" and out["model"] == "gpt-5.6-sol"
    assert [m["content"] for m in out["messages"]] == ["ab", "c"]


def test_transform_passes_through_non_json():
    assert transform(b"not json") == (b"not json", "")
    assert flatten("plain") == "plain"
