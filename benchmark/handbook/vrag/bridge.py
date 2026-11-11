"""HTTP bridge from the task containers' Docker network to the host-local Copilot model proxy.

Replaces handbook/scripts/proxy_bridge.py (same listening address and content flattening) and adds:
- model aliases: the OpenHands SDK sends every model whose name contains "gpt-5" to the OpenAI Responses API
  (/v1/responses), which the proxy does not implement (404). Agents therefore use the alias ``gpt_5...`` (see
  run_arm.agent_model) and the bridge restores the real id before forwarding to /v1/chat/completions;
- content flattening for chat payloads (the proxy crashes on array-of-parts message content);
- a request log line per call (path, model, status, seconds) and broken-pipe-safe error replies.

    python -m vrag.bridge        # 172.17.0.1:3141 -> 127.0.0.1:3141
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_HOST = os.environ.get("LISTEN_HOST", "172.17.0.1")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "3141"))
TARGET_HOST = os.environ.get("TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "3141"))
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade"}
ALIASES = {"gpt_5": "gpt-5"}  # agent-side alias -> real proxy model id fragment


def real_model(name: str) -> str:
    for alias, real in ALIASES.items():
        name = name.replace(alias, real)
    return name


def flatten(content):
    """Array-of-parts message content -> plain string (non-text parts cannot be represented and are dropped)."""
    if not isinstance(content, list):
        return content
    out = []
    for part in content:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            out.append(part["text"])
    return "".join(out)


def transform(raw: bytes) -> tuple[bytes, str]:
    """(forwarded body, real model id) for a chat-completions payload; unparseable bodies pass through."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw, ""
    if not isinstance(payload, dict):
        return raw, ""
    if isinstance(payload.get("model"), str):
        payload["model"] = real_model(payload["model"])
    for msg in payload.get("messages") or []:
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            msg["content"] = flatten(msg["content"])
    return json.dumps(payload).encode("utf-8"), str(payload.get("model") or "")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # one structured line per request instead (see _proxy)
        pass

    def _reply_error(self, status: int, message: str) -> None:
        try:
            self.send_error(status, message)
        except OSError:  # client already gone
            pass

    def _proxy(self, method: str) -> None:
        t0, model = time.time(), ""
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if body and self.path.rstrip("/").endswith("/chat/completions"):
            body, model = transform(body)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "host"}
        if body:
            headers["Content-Length"] = str(len(body))
        try:
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=900)
            conn.request(method, self.path, body=body or None, headers=headers)
            resp = conn.getresponse()
        except OSError as exc:
            print(f"{time.strftime('%H:%M:%S')} {method} {self.path} {model} -> 502 ({exc})", flush=True)
            self._reply_error(502, f"upstream failed: {exc}")
            return
        try:
            self.send_response_only(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_BY_HOP and k.lower() != "content-length":
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := resp.read1(65536):
                self.wfile.write(chunk)
            self.wfile.flush()
        except OSError:
            pass
        finally:
            conn.close()
            self.close_connection = True
        print(f"{time.strftime('%H:%M:%S')} {method} {self.path} {model} -> {resp.status} "
              f"{time.time() - t0:.1f}s", flush=True)

    def do_GET(self) -> None:
        self._proxy("GET")

    def do_POST(self) -> None:
        self._proxy("POST")


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    server.daemon_threads = True
    print(f"[vrag.bridge] {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
