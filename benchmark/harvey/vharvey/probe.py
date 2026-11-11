"""Probe the proxy: does the requested reasoning effort take effect, and is a long prompt delivered intact?

    python -m vharvey.probe --models gpt-5.6-luna claude-haiku-5.5 gemini-3.8-flash

Effort: the same counting puzzle at effort "none"/"low" vs "high"; with effort honoured, low is much faster and
often wrong. Context: a random code placed at the start of a ~300K-token prompt must be recalled (the unpatched
proxy cut long prompts from the start). Results go to docs/proxy_patch/probe_<date>.json.
"""

from __future__ import annotations

import argparse
import json
import random
import string
import time
from datetime import UTC, datetime

from . import paths, proxy

PUZZLE = ("How many 7x7 binary matrices with exactly two 1s in every row and every column are there? "
          "Answer with only the number.")
PUZZLE_ANSWER = "3110940"


def effort_probe(model: str, efforts: tuple[str, ...] = ("low", "high")) -> list[dict]:
    out = []
    for e in efforts:
        t0 = time.time()
        c = proxy.complete(model, [{"role": "user", "content": PUZZLE}], effort=e, retries=2)
        text = (c.message.get("content") or "").strip()
        out.append({"effort": e, "seconds": round(time.time() - t0, 1), "answer": text[:40],
                    "correct": PUZZLE_ANSWER in text.replace(",", "")})
    return out


def context_probe(model: str, target_tokens: int = 300_000) -> dict:
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    filler_line = "The quarterly filing schedule was reviewed and no changes were recorded for this period.\n"
    per_line = proxy.count_tokens([{"content": filler_line}]) - 4
    filler = filler_line * max(1, target_tokens // max(per_line, 1))
    prompt = (f"SECRET CODE: {code}\nRemember the secret code above.\n\n{filler}\n"
              "What was the secret code at the very start of this message? Reply with the code only, or UNKNOWN.")
    n = proxy.count_tokens([{"content": prompt}])
    t0 = time.time()
    c = proxy.complete(model, [{"role": "user", "content": prompt}], retries=2)
    text = (c.message.get("content") or "").strip()
    return {"prompt_tokens_est": n, "seconds": round(time.time() - t0, 1), "recalled": code in text,
            "answer": text[:40]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gpt-5.6-luna", "claude-haiku-5.5", "gemini-3.8-flash"])
    ap.add_argument("--context-tokens", type=int, default=300_000)
    a = ap.parse_args()
    res = {}
    for m in a.models:
        res[m] = {"max_input_tokens": proxy.served_models().get(m), "effort": effort_probe(m)}
        try:
            res[m]["context"] = context_probe(m, a.context_tokens)
        except Exception as e:  # report, do not hide
            res[m]["context"] = {"error": f"{type(e).__name__}: {e}"[:300]}
        print(m, json.dumps(res[m]), flush=True)
    out = paths.ROOT / "docs" / "proxy_patch" / f"probe_{datetime.now(UTC):%Y%m%d_%H%M}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
