"""LAB judge routed through the Copilot proxy, keeping LAB's prompt, parsing and scoring code unchanged.

LAB's ``Judge`` calls the Anthropic/OpenAI SDKs directly; the proxy only speaks Chat Completions, so this subclass
replaces the transport only. Differences from LAB, all recorded in scores metadata:
- judge models are the proxy-served ones (LAB default claude-sonnet-4-6 + gpt-5.5 are not served);
- no structured-output schema (unsupported by the proxy); LAB's own ``_parse_json`` parses the verdict;
- prompts above ``MAX_PROMPT_CHARS`` are not sent and score ``fail`` with an explicit reason (evo-harness LAB-002),
  so an over-long deliverable cannot silently drop a run.
"""

from __future__ import annotations

import time

from lab_core.evaluation.judge import Judge

from . import proxy

MAX_PROMPT_CHARS = 240_000
DEFAULT_JUDGES = ("claude-sonnet-5", "gpt-5.6-sol")


class ProxyJudge(Judge):
    def __init__(self, model: str, retries: int = 3):
        if model not in proxy.served_models():
            raise proxy.ProxyError(f"judge model {model!r} is not served by the proxy")
        self.model = model
        self.provider = "proxy"
        self.retries = retries

    def evaluate(self, prompt_template: str, variables: dict, temperature: float = 0.0, _retries: int = 2) -> dict:
        prompt = prompt_template.format(**variables)
        if len(prompt) > MAX_PROMPT_CHARS:
            return {"reasoning": f"Judge prompt is {len(prompt)} characters, above the {MAX_PROMPT_CHARS} cap; "
                                 "scored fail without a judge call.", "verdict": "fail"}
        last: Exception | None = None
        for attempt in range(self.retries):
            c = proxy.complete(self.model, [{"role": "user", "content": prompt}], max_tokens=64000,
                               temperature=temperature if self.model.startswith("claude") else None)
            try:
                out = self._parse_json(c.message.get("content") or "")
                if out.get("verdict") in ("pass", "fail"):
                    return out
                last = ValueError(f"bad verdict {out.get('verdict')!r}")
            except ValueError as e:
                last = e
            time.sleep(2 * (attempt + 1))
        raise ValueError(f"Judge {self.model} returned no parseable verdict after {self.retries} attempts: {last}")
