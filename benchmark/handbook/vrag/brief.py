"""Compact SOP brief (A2/A3 system-prompt addendum) rendered deterministically from a PolicyKB."""

from __future__ import annotations

SCOPE = " [this item only; complete all other required work]"


def _rule(r: dict, softstop: bool = False) -> str:
    s = f"- [{r.get('kind', '')}] {r.get('statement', '')}"
    if r.get("unless"):
        s += f" (unless {r['unless']})"
    if softstop and r.get("kind") in ("stop", "escalation"):
        s += SCOPE
    return s


def make_brief(kb: dict, max_chars: int = 9000, softstop: bool = False) -> str:
    """softstop: stop/hold/escalation rules are scoped to the item they name (the agent records what is pending
    and completes the rest) instead of reading as a halt of the whole task."""
    out = []
    defs = kb.get("definitions", [])
    if defs:
        out.append("Definitions: " + " | ".join(f"{d['term']}: {d['meaning']}" for d in defs[:25]))
    procs = kb.get("procedures", [])
    if procs:
        out.append("Procedures (policy__procedure(id)):")
        out += [f"- {p['id']} {p['title']}: {p.get('trigger', '')}" for p in procs]
    auth = [p for p in kb.get("people", []) if p.get("authority")]
    if auth:
        out.append("Who may authorize/approve:")
        out += [f"- {p['name']} ({p.get('role', '')}): {'; '.join(p['authority'])}" for p in auth[:30]]
    hard = [r for r in kb.get("rules", []) if r.get("severity", "hard") == "hard"
            and r.get("kind") in ("prohibition", "authority", "stop", "escalation", "ordering")]
    if hard:
        out.append("Hard rules (do not break; check each before acting):")
        out += [_rule(r, softstop) for r in hard]
    text = "\n".join(out)
    return text if len(text) <= max_chars else text[:max_chars] + "\n... (more: policy__rules, policy__overview)"
