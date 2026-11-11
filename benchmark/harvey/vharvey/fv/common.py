"""Shared pieces of the offline FV build: text normalisation, verbatim-quote grounding, cached JSON LLM calls."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import json_repair

from .. import k0, paths, proxy

FV = paths.KB / "fv"
CACHE = paths.CACHE / "fv"

_MD_DROP = re.compile(r"\{\.[a-z-]+\}|[*_`\\\[\]]")  # pandoc markup: removed (it sits inside words/quotes)
_MD_SPACE = re.compile(r"[>#|]")  # block markers and table pipes: become spaces


def norm(s: str) -> str:
    """Normalise for quote matching: drop markdown/pandoc markup, unify quotes/dashes, collapse whitespace, lower."""
    s = _MD_SPACE.sub(" ", _MD_DROP.sub("", s or ""))
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u2014", "-").replace("\u2013", "-").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def key(s: object) -> str:
    """snake_case identifier for field names, vocabulary keys and enum values."""
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")


@lru_cache(maxsize=512)
def norm_text(path: str) -> str:
    return norm(k0.text(path))


def grounded(path: str, quote: str, min_len: int = 12) -> bool:
    """True if ``quote`` (normalised) occurs verbatim in the K0 text of ``path``."""
    q = norm(quote)
    if len(q) < min_len:
        return False
    t = norm_text(path)
    if q in t:
        return True
    # tolerate an ellipsis the model inserted: every segment must occur, in order
    parts = [p.strip() for p in re.split(r"\.\.\.|\u2026", q) if p.strip()]
    if len(parts) > 1 and all(len(p) >= 8 for p in parts):
        i = 0
        for p in parts:
            j = t.find(p, i)
            if j < 0:
                return False
            i = j + len(p)
        return True
    return False


def call_json(model: str, prompt: str, ns: str, *, max_tokens: int = 16000, retries: int = 3) -> dict:
    """One cached LLM call returning a JSON object. Cache key = model + prompt; failures are not cached."""
    key = hashlib.sha256(f"{model}\n{prompt}".encode()).hexdigest()
    cp = CACHE / ns / f"{key}.json"
    if cp.exists():
        return json.loads(cp.read_text())
    last: Exception | None = None
    for _ in range(retries):
        c = proxy.complete(model, [{"role": "user", "content": prompt}], max_tokens=max_tokens, timeout=900)
        text = c.message.get("content") or ""
        m = re.search(r"\{.*\}", text, re.S)
        try:
            out = json_repair.loads(m.group(0)) if m else None
            if isinstance(out, dict):
                cp.parent.mkdir(parents=True, exist_ok=True)
                cp.write_text(json.dumps(out))
                return out
            last = ValueError(f"no JSON object in reply: {text[:200]!r}")
        except Exception as e:  # malformed JSON: retry
            last = e
    raise RuntimeError(f"{ns}: no valid JSON after {retries} attempts: {last}")


def write_json(p: Path, obj: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    tmp.replace(p)
