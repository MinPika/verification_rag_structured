"""Model-invoked SOP checks (the exec tool): run the task's registered verifier code - the per-task interwhen
verifier module, used read-only - on demand, with no monitor. The policy server's verify_action / verify_completion
tools call this file; with the finish check on, the runner's hooks call it too.

Runs under the agent runner's python with the interwhen runner directory on PYTHONPATH and INTERWHEN_TASK /
INTERWHEN_STATE_DIR set (its ledger callback records the conversation there, as in the R arm, so the checks see the
same state its hooks would).

    python iw_exec.py action      # stdin {"tool_name": ..., "arguments": {...}} -> text (OK or problems + fixes)
    python iw_exec.py completion  # stdin {}  -> text (OK or open SOP obligations)
    python iw_exec.py hook-pre    # OpenHands PreToolUse hook: only `finish` is checked (one completion check)
    python iw_exec.py hook-stop   # OpenHands Stop hook: completion check
Every call is logged to $VRAG_STATE/exec.jsonl. Errors fall open (a check that cannot run never blocks).
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

LOG = os.path.join(os.environ.get("VRAG_STATE", "/logs/agent/vrag"), "exec.jsonl")


def _log(entry: dict) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), **entry}, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def _run(stage: str, action=None):
    from interwhen_sop import config, framework, ledger, sopdata, state

    ctx = framework.Context(sopdata.load(), state.build(ledger.read()), [])
    return framework.run(framework.load_rules(config.task_id()), stage, ctx, action)


def _format(findings: list, head: str) -> str:
    lines = [head, ""]
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. [{f.rule}] {f.problem}")
        lines += [f"   - {r}" for r in f.refs]
    fixes = list(dict.fromkeys(x for f in findings for x in f.fix))
    if fixes:
        lines += ["", "Fix:"] + [f"- {x}" for x in fixes]
    return "\n".join(lines)


def check_action(tool: str, args: dict) -> str:
    from interwhen_sop.actions import classify

    args = args.get("data") if isinstance(args.get("data"), dict) else args
    action = classify(tool, args)
    if not action.is_write:
        return f"OK: {tool} does not change anything, so no SOP check applies."
    findings, errors = _run("pre", action)
    _log({"mode": "action", "tool": tool, "kind": action.kind, "findings": [f.__dict__ for f in findings],
          "errors": errors})
    if not findings:
        return f"OK: no registered SOP check objects to this {action.kind} (nothing was executed)."
    return _format(findings, f"SOP CHECK: this {action.kind} would violate the SOP (nothing was executed).")


def check_completion() -> str:
    findings, errors = _run("completion")
    _log({"mode": "completion", "findings": [f.__dict__ for f in findings], "errors": errors})
    if not findings:
        return "OK: every registered SOP end-state check is satisfied."
    return _format(findings, f"SOP CHECK: {len(findings)} SOP requirement(s) still open in the current state.")


def hook(mode: str, event: dict) -> dict:
    from interwhen_sop import engine

    if mode == "hook-pre" and (event.get("tool_name") or "") != "finish":
        return {"decision": "allow"}
    out = engine.completion("finish_tool" if mode == "hook-pre" else "stop_hook")
    _log({"mode": mode, "decision": out.get("decision")})
    return out


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if mode == "action":
            print(check_action(str(payload.get("tool_name") or ""), payload.get("arguments") or {}))
        elif mode == "completion":
            print(check_completion())
        elif mode in ("hook-pre", "hook-stop"):
            print(json.dumps(hook(mode, payload)))
        else:
            print(f"unknown mode {mode!r}")
    except Exception:  # noqa: BLE001 - fall open
        _log({"mode": mode, "error": traceback.format_exc()[-2000:]})
        if mode.startswith("hook"):
            print(json.dumps({"decision": "allow"}))
        else:
            print("The SOP checks could not run for this call; rely on the SOP text (policy__read).")


if __name__ == "__main__":
    main()
