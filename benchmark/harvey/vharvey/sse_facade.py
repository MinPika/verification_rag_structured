"""OpenAI Chat Completions facade in front of the Copilot proxy, for harnesses that stream (DSH's pi-ai).

    python -m vharvey.sse_facade            # 127.0.0.1:3142 -> 127.0.0.1:3141

The Copilot proxy answers non-streaming JSON only, reads the effort from ``reasoning.effort``, accepts only string
message content, and crashes or ignores several OpenAI fields. This facade:
- normalises the request: ``developer`` role -> ``system``; content arrays -> joined text; ``reasoning_effort`` ->
  ``reasoning: {effort}``; ``max_completion_tokens`` -> ``max_tokens``; drops ``stream``/``stream_options`` and
  other fields the proxy does not know;
- calls the proxy without streaming, with retries on transport errors and 5xx (exact model check on the reply);
- replies as an SSE stream when the client asked for one (one content chunk, tool-call chunks, finish chunk, usage
  chunk, ``[DONE]``), else as plain JSON. Usage is estimated with o200k (the proxy reports 0), so harness-side
  context accounting works.
Every call is logged as one JSON line (time, model, effort, messages, prompt-token estimate, seconds, status) to
``runs/sse_facade.log``.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from . import paths, proxy

LISTEN = (os.environ.get("FACADE_HOST", "127.0.0.1"), int(os.environ.get("FACADE_PORT", "3142")))
UPSTREAM = proxy.URL
PASS = {"model", "messages", "tools", "tool_choice", "temperature", "max_tokens", "top_p", "stop", "reasoning",
        "thinking"}
LOG = paths.RUNS / "sse_facade.log"
_lock = threading.Lock()


def _text(content) -> str:
    if isinstance(content, str) or content is None:
        return content or ""
    parts = []
    for p in content:
        if isinstance(p, dict):
            parts.append(p.get("text") or p.get("content") or ("[image omitted]" if p.get("type", "").startswith(
                "image") else ""))
        else:
            parts.append(str(p))
    return "\n".join(x for x in parts if x)


def normalise(body: dict) -> dict:
    out = {k: v for k, v in body.items() if k in PASS}
    if "max_completion_tokens" in body and "max_tokens" not in out:
        out["max_tokens"] = body["max_completion_tokens"]
    effort = body.get("reasoning_effort")
    if effort and "reasoning" not in out:
        out["reasoning"] = {"effort": effort}
    msgs = []
    for m in body.get("messages") or []:
        m = dict(m)
        if m.get("role") == "developer":
            m["role"] = "system"
        m["content"] = _text(m.get("content"))
        for k in ("reasoning_content", "reasoning", "thinking", "name", "cache_control"):
            m.pop(k, None)
        msgs.append(m)
    out["messages"] = msgs
    return out


def call(body: dict, retries: int = 6) -> dict:
    last = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"{UPSTREAM}/chat/completions", json=body, timeout=1800)
            if r.status_code >= 500 or r.status_code == 429:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if "not available" in r.text:
                    break
                time.sleep(min(120, 10 * 2 ** attempt))
                continue
            d = r.json()
            if r.status_code >= 400:
                return {"_error": r.status_code, "_body": d}
            if d.get("model") != body.get("model"):
                return {"_error": 502, "_body": {"error": {"message": f"proxy answered model {d.get('model')!r}, "
                                                                      f"requested {body.get('model')!r}"}}}
            return d
        except (httpx.TransportError, json.JSONDecodeError) as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(min(120, 10 * 2 ** attempt))
    return {"_error": 502, "_body": {"error": {"message": f"upstream failed after {retries} attempts: {last}"}}}


def _usage(body: dict, msg: dict) -> dict:
    p = proxy.count_tokens(body["messages"], body.get("tools"))
    c = proxy.count_tokens([{"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls")}])
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def sse_chunks(d: dict, usage: dict) -> list[dict]:
    choice = d["choices"][0]
    msg = choice["message"]
    base = {"id": d.get("id", "chatcmpl-facade"), "object": "chat.completion.chunk", "created": int(time.time()),
            "model": d["model"]}
    chunks = [{**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": msg.get("content") or ""},
                                    "finish_reason": None}]}]
    for i, tc in enumerate(msg.get("tool_calls") or []):
        chunks.append({**base, "choices": [{"index": 0, "finish_reason": None, "delta": {"tool_calls": [{
            "index": i, "id": tc.get("id"), "type": "function",
            "function": {"name": tc["function"]["name"], "arguments": tc["function"].get("arguments") or "{}"}}]}}]})
    finish = "tool_calls" if msg.get("tool_calls") else (choice.get("finish_reason") or "stop")
    chunks.append({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    chunks.append({**base, "choices": [], "usage": usage})
    return chunks


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet; we log JSON lines ourselves
        pass

    def _send(self, code: int, payload: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        r = httpx.get(f"{UPSTREAM}/models", timeout=60)
        self._send(r.status_code, r.content)

    def do_POST(self):  # noqa: N802
        t0 = time.time()
        raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        stream = bool(raw.get("stream"))
        body = normalise(raw)
        d = call(body)
        status = d.get("_error", 200)
        entry = {"t": round(t0, 1), "model": body.get("model"), "effort": (body.get("reasoning") or {}).get("effort"),
                 "n_messages": len(body["messages"]), "n_tools": len(body.get("tools") or []), "stream": stream,
                 "status": status, "secs": None}
        try:
            if status != 200:
                self._send(status, json.dumps(d["_body"]).encode())
                return
            usage = _usage(body, d["choices"][0]["message"])
            entry["prompt_tokens_est"] = usage["prompt_tokens"]
            if not stream:
                self._send(200, json.dumps({**d, "usage": usage}).encode())
                return
            payload = "".join(f"data: {json.dumps(c)}\n\n" for c in sse_chunks(d, usage)) + "data: [DONE]\n\n"
            self._send(200, payload.encode(), "text/event-stream")
        except (BrokenPipeError, ConnectionResetError):
            entry["status"] = "client_gone"
        finally:
            entry["secs"] = round(time.time() - t0, 2)
            with _lock, LOG.open("a") as f:
                f.write(json.dumps(entry) + "\n")


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(LISTEN, Handler)
    srv.daemon_threads = True
    print(f"SSE facade on http://{LISTEN[0]}:{LISTEN[1]}/v1 -> {UPSTREAM}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
