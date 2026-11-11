"""Policy server: code-first retrieval with text fallback, policy__run, and the tool catalogue."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from vrag import gen_tools

PKG_SRC = Path(__file__).resolve().parents[1] / "vrag" / "runtime" / "policy_pkg"
BLOCKS = [("D1.0001", "heading", "12.5 Exit Interview", 2), ("D1.0002", "para", "Exit interviews are offered to "
          "all voluntarily separating employees.", 0), ("D1.0003", "heading", "13 Holidays", 2),
          ("D1.0004", "para", "No meetings on Presidents Day.", 0)]
CODE = '''def p14_exit_interview(case: dict, today: str = "") -> list[dict]:
    """Exit interview. [D1.0002]"""
    if case.get("separation_type") != "Voluntary":  # [D1.0002]
        return [stop("not voluntary")]
    return [send_email(case["email"], "Exit Interview", "x")]  # [D1.0002]
'''


def _server(tmp_path: Path, code_mode: bool):
    fake = types.ModuleType("fastmcp")

    class FastMCP:  # minimal stand-in: @app.tool returns the function unchanged
        def __init__(self, name):
            self.name = name

        def tool(self, fn):
            return fn

    fake.FastMCP = FastMCP
    sys.modules["fastmcp"] = fake
    pkg = tmp_path / ("code" if code_mode else "text")
    (pkg / "data").mkdir(parents=True)
    for f in ("policy_server.py", "sop_exec.py", "gate.py"):
        shutil.copy(PKG_SRC / f, pkg / f)
    blocks = [{"id": i, "kind": k, "text": t, "level": lv, "section": "12.5", "header": []} for i, k, t, lv in BLOCKS]
    (pkg / "data" / "corpus.json").write_text(json.dumps([{"name": "sop.pdf", "role": "policy", "blocks": blocks}]))
    (pkg / "data" / "kb.json").write_text(json.dumps({"procedures": [
        {"id": "P14", "title": "Exit interview", "trigger": "voluntary separation", "blocks": ["D1.0002"],
         "steps": [{"id": "P14.S1", "kind": "check", "blocks": ["D1.0002"], "instruction": "Voluntary only."}]}]}))
    if code_mode:
        (pkg / "data" / "sop_code.json").write_text(json.dumps({
            "common": "HOLIDAYS = []\n", "block_map": {"D1.0002": "P14"},
            "procedures": {"P14": {"fn": "p14_exit_interview", "code": CODE, "ok": True, "runnable": True,
                                   "blocks": ["D1.0002"], "title": "Exit interview"}}}))
    name = f"policy_server_{pkg.name}"
    spec = importlib.util.spec_from_file_location(name, pkg / "policy_server.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def call(fn, *a, **kw):
    return asyncio.run(fn(*a, **kw))


@pytest.fixture
def code_server(tmp_path):
    return _server(tmp_path, True)


def test_procedure_returns_code_in_code_mode_and_text_otherwise(tmp_path, code_server):
    out = call(code_server.procedure, "P14")
    assert "def p14_exit_interview" in out and 'policy__run("p14_exit_interview"' in out
    text = call(_server(tmp_path, False).procedure, "P14")
    assert "def " not in text and "Voluntary only." in text


def test_find_returns_code_for_mapped_blocks_and_text_for_the_rest(code_server):
    out = call(code_server.find, "exit interviews voluntarily")
    assert "is implemented by" in out and "def p14_exit_interview" in out
    assert "Presidents Day" in call(code_server.find, "Presidents Day meetings")


def test_read_mixes_code_and_uncompiled_text(code_server):
    out = call(code_server.read, "12.5")
    assert "def p14_exit_interview" in out and "Exit interviews are offered" not in out
    assert "No meetings on Presidents Day." in call(code_server.read, "13")


def test_run_executes_the_compiled_procedure(code_server):
    acts = json.loads(call(code_server.run, "p14_exit_interview", {"separation_type": "Voluntary", "email": "a@b.c"}))
    assert acts == [{"action": "send_email", "to": "a@b.c", "subject": "Exit Interview", "body": "x"}]
    assert "not voluntary" in call(code_server.run, "P14", {"separation_type": "Involuntary"})
    assert "No such compiled procedure" in call(code_server.run, "nope", {})


def test_tool_catalogue_matches_server_source():
    want = gen_tools.generate(gen_tools.SERVER.read_text())
    assert json.loads(gen_tools.OUT.read_text()) == want
    assert {"run", "procedure", "find", "read"} <= {t["name"] for t in want["tools"]}
