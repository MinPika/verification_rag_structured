"""Firm Verifier over HTTP, for harnesses outside this Python process (DSH's fv-gate plugin).

    python -m vharvey.fv.server            # 127.0.0.1:3150;  POST /fv/<tool> with the tool's JSON arguments

Tools: fv_check, fv_check_many, fv_matter, fv_doc, fv_check_complete. The reply is the same JSON the in-process
arms return (vharvey/fv/arm.py), computed by vharvey/fv/api.py from the frozen index; GET /health returns the
index freeze digest so a run can record which index answered.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .. import paths
from . import api
from .arm import MAX_CHECKS

HOST = os.environ.get("FV_HOST", "127.0.0.1")
PORT = int(os.environ.get("FV_PORT", "3150"))


def dispatch(tool: str, args: dict) -> Any:
    if tool == "fv_check":
        return api.check(str(args.get("matter_id", "")), str(args.get("field", "")), args.get("value"))
    if tool == "fv_check_many":
        return [{"matter_id": c.get("matter_id"), **api.check(str(c.get("matter_id", "")), str(c.get("field", "")),
                                                              c.get("value"))}
                for c in (args.get("checks") or [])[:MAX_CHECKS] if isinstance(c, dict)]
    if tool == "fv_matter":
        return api.matter(str(args.get("matter_id", "")))
    if tool == "fv_doc":
        return api.doc(str(args.get("path", "")))
    if tool == "fv_check_complete":
        return api.check_complete(args.get("conditions") or [], [str(m) for m in args.get("matters") or []])
    return {"error": f"unknown tool {tool}"}


FREEZE_TAG = os.environ.get("FV_FREEZE_TAG", "")


def freeze_manifest() -> dict | None:
    """The served freeze: ``FV_FREEZE_TAG`` if set, else the newest FREEZE_fv_*.json."""
    if FREEZE_TAG:
        return json.loads((paths.RUNS / f"FREEZE_fv_{FREEZE_TAG}.json").read_text())
    freezes = sorted(paths.RUNS.glob("FREEZE_fv_*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(freezes[-1].read_text()) if freezes else None


def freeze_digest() -> str | None:
    man = freeze_manifest()
    return man["digest"] if man else None


def verify_freeze(man: dict) -> list[str]:
    """Files whose current hash differs from the freeze (index data, verifier code, harness files)."""
    import hashlib
    want = man["files"] | man["code"] | man.get("dsh_files", {})
    return [k for k, h in want.items()
            if not (paths.ROOT / k).exists() or hashlib.sha256((paths.ROOT / k).read_bytes()).hexdigest() != h]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "freeze_tag": FREEZE_TAG or None, "freeze_digest": freeze_digest()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/fv/"):
            self._send(404, {"error": "not found"})
            return
        try:
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            self._send(200, dispatch(self.path[len("/fv/"):], args if isinstance(args, dict) else {}))
        except Exception as e:  # a verifier bug must never crash the agent's run
            self._send(200, {"error": f"{type(e).__name__}: {e}"})


def main() -> None:
    if FREEZE_TAG:
        stale = verify_freeze(freeze_manifest() or {})
        if stale:
            raise SystemExit(f"working tree differs from freeze {FREEZE_TAG} in {len(stale)} files, e.g. {stale[:5]}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    print(f"FV server on http://{HOST}:{PORT} (index {freeze_digest()})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
