"""The per-task interwhen verifier modules as the SOP's code representation (retrieve the code, not the text).

Each module (handbook/docker/openhands-runner/interwhen_sop/verifiers/<task>.py) was written offline by a frontier
model from the SOP and the task's data and tested on synthetic traces. It is made of SOP references
``R_X = (section, paragraph start, label)``, task constants, message specs ``Comm(...)`` and rules
``RULES += pre_rule/state_rule/forbid_writes/append_only(...)``. This module cuts it into self-contained code units
(one per message spec / rule, with the references, constants and helper functions it uses), and maps every unit to
the SOP blocks its references point at (paragraph-start text match in the K0 corpus). The module docstring - the
verifier author's task analysis - is not served (parity with the R arm, which never shows it).

    python -m vrag.vcode [--tasks a,b | --split dev|test|all]
Output: kb/<task>/vcode.json in the policy server's code format {"source": "verifiers", "procedures": {...},
"block_map": {block: [unit ids]}}
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys

from . import paths
from .compile import load_k0
from .sopcode import _GATE

VERIFIERS = paths.HANDBOOK / "docker" / "openhands-runner" / "interwhen_sop" / "verifiers"
BUILDERS = {"pre_rule", "state_rule", "forbid_writes", "append_only", "append_only_rule", "no_placeholders"}
# comm_rules(...) is served message spec by message spec (Comm units)


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _is_ref(value: ast.AST) -> tuple | None:
    """SOP reference literal: (section, paragraph start[, label]) with a short section id containing a digit."""
    if not isinstance(value, ast.Tuple) or len(value.elts) < 2:
        return None
    try:
        lit = ast.literal_eval(value)
    except ValueError:
        return None
    if all(isinstance(x, str) for x in lit) and len(lit[0]) <= 12 and re.search(r"\d", lit[0]):
        return tuple(lit)
    return None


def _ref_list(value: ast.AST) -> list[tuple]:
    """A reference literal, or a list/tuple of reference literals."""
    one = _is_ref(value)
    if one:
        return [one]
    if isinstance(value, (ast.List, ast.Tuple)) and value.elts:
        many = [_is_ref(e) for e in value.elts]
        if all(many):
            return many
    return []


def _inline_refs(node: ast.AST) -> list[tuple]:
    return [r for n in ast.walk(node) if isinstance(n, ast.Tuple) for r in [_is_ref(n)] if r]


def _unit_id(call: ast.Call, fallback: str) -> str:
    first = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg in ("key", "rule_id")), None)
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else fallback


def parse(src: str) -> tuple[dict, dict, dict, list[dict]]:
    """(refs {name: [(section, start, label), ...]}, constants {name: src}, functions {name: node}, units). Handles the
    layouts the verifier builder produced: ``R_X = (...)`` / ``R_X: Ref = (...)`` / unprefixed reference names,
    ``RULES += builder(...)``, ``RULES = [...]`` or ``(... + ...)`` lists, and ``@rule(...)`` functions."""
    tree = ast.parse(src)
    refs, consts, funcs, units = {}, {}, {}, []
    for node in tree.body:
        target = value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target, value = node.target.id, node.value
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
            for el in node.targets[0].elts:  # EMP, EID, LAST = ...
                if isinstance(el, ast.Name):
                    consts[el.id] = ast.get_source_segment(src, node)
            continue
        if target and target != "RULES":
            ref = _ref_list(value)
            if ref:
                refs[target] = ref
            else:
                consts[target] = ast.get_source_segment(src, node)
        elif isinstance(node, ast.FunctionDef):
            funcs[node.name] = node
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", getattr(d.func, "attr", "")) == "rule":
                    units.append({"id": f"rule:{_unit_id(d, node.name)}", "node": node,
                                  "src": ast.get_source_segment(src, node), "kind": "rule"})
    for fn in funcs.values():
        for call in ast.walk(fn):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "Comm":
                units.append({"id": f"message:{_unit_id(call, f'comm{len(units)}')}", "node": call,
                              "src": ast.get_source_segment(src, call), "kind": "message spec"})
    calls = [call for node in tree.body
             if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))
             for call in ast.walk(node)
             if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in BUILDERS]
    for call in sorted(calls, key=lambda c: (c.lineno, c.col_offset)):  # source order
        units.append({"id": f"rule:{_unit_id(call, call.func.id)}", "node": call,
                      "src": ast.get_source_segment(src, call), "kind": call.func.id.replace("_", " ")})
    seen: set[str] = set()
    for u in units:  # unique ids (a builder may be reused with the same id)
        base, n = u["id"], 2
        while u["id"] in seen:
            u["id"], n = f"{base}#{n}", n + 1
        seen.add(u["id"])
    return refs, consts, funcs, units


def _helpers(names: set[str], funcs: dict, src: str, seen: set[str] | None = None) -> list[str]:
    """Source of the module's own helper functions a unit uses (transitively), in definition order."""
    seen = seen if seen is not None else set()
    out = []
    for n in sorted(names & set(funcs), key=lambda x: funcs[x].lineno):
        if n in seen or n == "specs":
            continue
        seen.add(n)
        out += _helpers(_names(funcs[n]), funcs, src, seen)
        out.append(ast.get_source_segment(src, funcs[n]))
    return out


def ref_blocks(ref: tuple, blocks: dict, order: list[str]) -> list[str]:
    """K0 block(s) a verifier reference points at: the paragraph whose text contains its start, else the heading
    of its section."""
    section, start = str(ref[0]), str(ref[1]) if len(ref) > 1 else ""
    key = _GATE.mloose(start)
    if len(key) >= 8:
        hits = [b for b in order if key in _GATE.mloose(blocks[b]["text"])]
        in_sec = [b for b in hits if str(blocks[b].get("section", "")).startswith(section)]
        if in_sec or hits:
            return (in_sec or hits)[:1]
    rx = re.compile(rf"^\s*(section\s*)?{re.escape(section)}\b", re.I)
    return [b for b in order if blocks[b]["kind"] == "heading" and rx.match(blocks[b]["text"])][:1]


def build(task: str) -> dict:
    src = (VERIFIERS / f"{task}.py").read_text()
    refs, consts, funcs, units = parse(src)
    _, blocks, order = load_k0(task)
    ref_map = {name: list(dict.fromkeys(b for r in rs for b in ref_blocks(r, blocks, order)))
               for name, rs in refs.items()}
    procs, block_map = {}, {}
    for u in units:
        names = _names(u["node"])
        helpers = _helpers(names, funcs, src)
        used = names.union(*(_names(ast.parse(h)) for h in helpers)) if helpers else names
        used_refs = [n for n in refs if n in used]
        used_consts = [n for n in consts if n in used]
        parts = [f"{n} = {(refs[n][0] if len(refs[n]) == 1 else refs[n])!r}  # SOP reference(s): (section, paragraph "
                 "start, label)" for n in used_refs]
        parts += list(dict.fromkeys(consts[n] for n in used_consts)) + helpers + [u["src"]]
        inline = _inline_refs(u["node"]) + [r for h in helpers for r in _inline_refs(ast.parse(h))]
        ids = list(dict.fromkeys([b for n in used_refs for b in ref_map[n]]
                                 + [b for r in inline for b in ref_blocks(r, blocks, order)]))
        labels = [r[2] if len(r) > 2 else r[0] for n in used_refs for r in refs[n]] + \
                 [r[2] if len(r) > 2 else r[0] for r in inline]
        procs[u["id"]] = {"fn": u["id"], "code": "\n\n".join(parts), "ok": True, "runnable": False, "blocks": ids,
                          "title": f"{u['kind']} for SOP " + ", ".join(dict.fromkeys(labels))[:200]}
        for b in ids:
            block_map.setdefault(b, []).append(u["id"])
    out = {"task": task, "source": "verifiers", "common": "", "procedures": procs, "block_map": block_map,
           "unmapped_refs": [n for n, b in ref_map.items() if not b]}
    refs_total = sum(len(v) for v in refs.values())
    (paths.KB / task / "vcode.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return {"task": task, "units": len(procs), "mapped_units": sum(bool(p["blocks"]) for p in procs.values()),
            "refs": refs_total, "unmapped_refs": len(out["unmapped_refs"]), "mapped_blocks": len(block_map)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--split", default="all", choices=("dev", "test", "all"))
    a = ap.parse_args()
    tasks = a.tasks.split(",") if a.tasks else [t for t in paths.all_tasks()
                                                 if a.split == "all" or paths.split(t) == a.split]
    for t in tasks:
        try:
            print(json.dumps(build(t)), flush=True)
        except Exception as e:  # noqa: BLE001 - report and continue with the next task
            print(json.dumps({"task": t, "error": f"{type(e).__name__}: {e}"[:300]}), flush=True)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
