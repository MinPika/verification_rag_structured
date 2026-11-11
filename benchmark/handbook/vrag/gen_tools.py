"""Regenerate the policy package's MCP tool catalogue (mcp-tools.generated.json) from policy_server.py.

The MCP proxy lists tools from this file (it does not introspect the server at run time). FastMCP is only
installed inside the task image, so the catalogue is derived from the server source with ``ast``: every
``@app.tool`` function contributes its name, its docstring (inspect.cleandoc) and a JSON schema built the way FastMCP
builds it for the simple parameter types the server uses (str, int, dict, ``dict | None``).

    python -m vrag.gen_tools [--check]     # --check: exit 1 if the committed file is out of date
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import sys
from pathlib import Path

from .package import RUNTIME

SERVER = RUNTIME / "policy_pkg" / "policy_server.py"
OUT = RUNTIME / "policy_pkg" / "mcp-tools.generated.json"
_TYPES = {"str": {"type": "string"}, "int": {"type": "integer"}, "float": {"type": "number"},
          "bool": {"type": "boolean"}, "dict": {"additionalProperties": True, "type": "object"}}


def _schema(ann: ast.expr | None) -> dict:
    if ann is None:
        return {}
    if isinstance(ann, ast.Name) and ann.id in _TYPES:
        return dict(_TYPES[ann.id])
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):  # X | None
        if isinstance(ann.right, ast.Constant) and ann.right.value is None:
            return {"anyOf": [_schema(ann.left), {"type": "null"}]}
        return {"anyOf": [_schema(ann.left), _schema(ann.right)]}
    raise ValueError(f"unsupported annotation: {ast.unparse(ann)}")


def _tool(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> dict:
    args = fn.args.args
    defaults = [None] * (len(args) - len(fn.args.defaults)) + list(fn.args.defaults)
    props, required = {}, []
    for a, d in zip(args, defaults, strict=True):
        prop = _schema(a.annotation)
        if d is None:
            required.append(a.arg)
        else:
            prop = {"default": ast.literal_eval(d), **prop}
        props[a.arg] = prop
    schema: dict = {"additionalProperties": False, "properties": props}
    if required:
        schema["required"] = required
    schema["type"] = "object"
    return {"name": fn.name, "description": inspect.cleandoc(ast.get_docstring(fn, clean=False) or ""),
            "inputSchema": schema}


def generate(src: str) -> dict:
    tools = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Attribute) and d.attr == "tool" for d in node.decorator_list):
            tools.append(_tool(node))
    return {"schema_version": "v1", "tools": tools}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = json.dumps(generate(SERVER.read_text()), indent=1, ensure_ascii=False) + "\n"
    if a.check:
        sys.exit(0 if OUT.exists() and json.loads(OUT.read_text()) == json.loads(text) else 1)
    Path(OUT).write_text(text)
    print(OUT)


if __name__ == "__main__":
    main()
