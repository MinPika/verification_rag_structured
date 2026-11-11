"""Chat client for the local Copilot proxy (OpenAI format). Plain-string message content only (the proxy crashes on
content arrays), exact model-id check (the proxy silently falls back to its first model otherwise), disk cache,
retries."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request

from . import paths

URL = "http://127.0.0.1:3141/v1"
_served: set[str] | None = None


def served() -> set[str]:
    global _served
    if _served is None:
        with urllib.request.urlopen(f"{URL}/models", timeout=20) as r:
            _served = {m["id"] for m in json.load(r)["data"]}
    return _served


def chat(model: str, messages: list[dict], max_tokens: int = 16000, temperature: float | None = None,
         cache: str | None = "default", timeout: int = 900, retries: int = 4) -> str:
    if model not in served():
        raise ValueError(f"model {model!r} not served by proxy")
    for m in messages:
        if not isinstance(m.get("content"), str):
            raise TypeError("message content must be a plain string for this proxy")
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    cpath = paths.CACHE / "llm" / (cache or "_") / f"{key}.json"
    if cache and cpath.exists():
        return json.loads(cpath.read_text())["text"]
    err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{URL}/chat/completions", json.dumps(body).encode(),
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            if d.get("model") not in (None, model):
                raise RuntimeError(f"proxy answered with model {d.get('model')!r}, wanted {model!r}")
            text = d["choices"][0]["message"].get("content") or ""
            if not text.strip():
                raise RuntimeError("empty completion")
            if cache:
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps({"model": model, "text": text, "t": time.time()}))
            return text
        except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError, json.JSONDecodeError) as e:
            err = e
            time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"chat failed after {retries} attempts: {err}")


def extract_json(text: str):
    """Parse the last fenced ```json block, else the outermost {...} span."""
    blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for cand in reversed(blocks):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i:j + 1])
        except json.JSONDecodeError:
            pass
    # last resort: repair near-JSON (typically unescaped quotes inside long quoted strings)
    import json_repair

    for cand in list(reversed(blocks)) + ([text[i:j + 1]] if i >= 0 and j > i else []):
        out = json_repair.loads(cand)
        if isinstance(out, dict) and out:
            return out
    raise ValueError("no JSON found")


def chat_json(model: str, messages: list[dict], **kw):
    text = chat(model, messages, **kw)
    try:
        return extract_json(text)
    except (ValueError, json.JSONDecodeError):
        fix = messages + [{"role": "assistant", "content": text},
                          {"role": "user", "content": "Your reply was not valid JSON. Return the complete JSON "
                                                      "object only, in one ```json block."}]
        return extract_json(chat(model, fix, **kw))
