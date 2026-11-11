"""Client for the local GH Copilot proxy (OpenAI Chat Completions format) and a lab_core ModelAdapter on top of it.

Known proxy behaviour this module defends against (see docs/SETUP.md):
- it silently falls back to another model on an unknown id -> exact model check on every response;
- it crashes on content arrays -> every message content is a plain string;
- unpatched builds ignore the reasoning effort and silently cut prompts longer than about 270K tokens; the proxy
  must carry the patch in docs/proxy_patch (it then honours ``reasoning.effort`` and the model's real window);
  the adapter still refuses a prompt above the model's advertised window minus CONTEXT_MARGIN, raising the
  ``context_length_exceeded`` error LAB's agent loop treats as a clean context overflow (as a provider would);
- transient outages (window reloads) -> bounded retries with backoff on transport errors and 5xx.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from functools import cache
from typing import Any

import httpx
import tiktoken
from lab_core.harness.adapters.base import ModelAdapter, ModelResponse, ToolCall

URL = os.environ.get("FRONTIER_URL", "http://127.0.0.1:3141/v1").rstrip("/")
CONTEXT_MARGIN = 0.05  # o200k is an estimate for Claude/Gemini tokenizers; stay 5% below the advertised window


def window_limit(model: str) -> int:
    """Safe prompt limit: the model's advertised max input tokens (patched proxy honours it) minus the margin."""
    return int(served_models()[model] * (1 - CONTEXT_MARGIN))
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class ProxyError(RuntimeError):
    """Non-retryable proxy failure (unknown model, malformed response)."""


class ContextOverflow(RuntimeError):
    """Prompt exceeds the safe context; the message contains LAB's overflow marker."""


@cache
def served_models() -> dict[str, int]:
    """Model id -> advertised max input tokens."""
    r = httpx.get(f"{URL}/models", timeout=30)
    r.raise_for_status()
    return {m["id"]: int(m.get("max_input_tokens") or 0) for m in r.json()["data"]}


@cache
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("o200k_base")


def count_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    """o200k_base estimate of the prompt (messages + tool schemas). Exact for GPT, close for Claude/Gemini."""
    enc = _encoder()
    n = 0
    for m in messages:
        n += 4 + len(enc.encode(m.get("content") or "", disallowed_special=()))
        for tc in m.get("tool_calls") or []:
            n += len(enc.encode(json.dumps(tc), disallowed_special=()))
    if tools:
        n += len(enc.encode(json.dumps(tools), disallowed_special=()))
    return n


@dataclass
class Completion:
    message: dict
    finish_reason: str | None
    seconds: float


def complete(model: str, messages: list[dict], *, tools: list[dict] | None = None, effort: str | None = None,
             max_tokens: int | None = None, temperature: float | None = None, timeout: float = 900,
             retries: int = 6) -> Completion:
    """One chat completion with exact-model check and retries on transient failures."""
    if model not in served_models():
        raise ProxyError(f"model {model!r} is not served by the proxy at {URL}")
    for m in messages:
        if not isinstance(m.get("content"), str):
            raise TypeError(f"message content must be a plain string (role={m.get('role')})")
    body: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools
    if effort:
        body["reasoning"] = {"effort": effort}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    last: Exception | None = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            r = httpx.post(f"{URL}/chat/completions", json=body, timeout=timeout)
            if r.status_code >= 400:
                text = r.text[:500]
                if "not available" in text or r.status_code not in _RETRYABLE_STATUS:
                    raise ProxyError(f"HTTP {r.status_code}: {text}")
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}: {text}", request=r.request, response=r)
            d = r.json()
            if d.get("model") != model:
                raise ProxyError(f"proxy answered with model {d.get('model')!r}, requested {model!r}")
            choice = d["choices"][0]
            return Completion(choice["message"], choice.get("finish_reason"), round(time.time() - t0, 2))
        except ProxyError:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError, json.JSONDecodeError, KeyError, IndexError) as e:
            last = e
            time.sleep(min(120, 10 * 2**attempt))
    raise RuntimeError(f"proxy call failed after {retries} attempts: {type(last).__name__}: {last}")


def to_openai_tools(tools: list[dict]) -> list[dict]:
    """LAB canonical tool definitions (name/description/parameters) -> Chat Completions function tools."""
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("parameters", {"type": "object"})}} for t in tools]


class ProxyAdapter(ModelAdapter):
    """lab_core ModelAdapter speaking Chat Completions to the Copilot proxy."""

    def __init__(self, model: str, temperature: float = 0.0, reasoning_effort: str | None = None,
                 context_limit: int | None = None, max_tokens: int | None = None):
        super().__init__(model, temperature, reasoning_effort)
        self.context_limit = context_limit or window_limit(model)
        self.max_tokens = max_tokens
        self.calls: list[dict] = []

    def chat(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        oa_tools = to_openai_tools(tools) if tools else None
        n = count_tokens(messages, oa_tools)
        if n > self.context_limit:
            raise ContextOverflow(f"context_length_exceeded: prompt ~{n} tokens > safe limit {self.context_limit}")
        c = complete(self.model, messages, tools=oa_tools, effort=self.reasoning_effort, max_tokens=self.max_tokens)
        msg = c.message
        calls = [ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=tc["function"].get("arguments") or "{}")
                 for tc in msg.get("tool_calls") or []]
        text = msg.get("content") or ""
        history: dict[str, Any] = {"role": "assistant", "content": text}
        if calls:
            history["tool_calls"] = [{"id": t.id, "type": "function",
                                      "function": {"name": t.name, "arguments": t.arguments}} for t in calls]
        self.calls.append({"prompt_tokens_est": n, "seconds": c.seconds, "finish_reason": c.finish_reason,
                           "n_tool_calls": len(calls)})
        # The proxy reports usage as 0, so token counts are o200k estimates.
        out_tokens = count_tokens([{"content": text, "tool_calls": history.get("tool_calls")}])
        return ModelResponse(message=history, tool_calls=calls, text=text, input_tokens=n,
                             output_tokens=out_tokens, finish_reason=c.finish_reason)

    def make_tool_result_messages(self, results: list[tuple[str, str]]) -> list[dict]:
        return [{"role": "tool", "tool_call_id": cid, "content": str(res)} for cid, res in results]

    def make_system_message(self, content: str) -> dict:
        return {"role": "system", "content": content}

    def make_user_message(self, content: str) -> dict:
        return {"role": "user", "content": content}

