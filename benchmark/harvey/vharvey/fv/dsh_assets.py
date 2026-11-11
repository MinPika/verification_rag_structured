"""Firm Verifier assets for the DSH harness (dsh-bench-harness, branch vrag/harvey-fv).

    python -m vharvey.fv.dsh_assets OUT.json

Writes the fv_* tool schemas and the verification messages that the DSH plugin
``benchmarks/harvey/plugins/fv-gate.mjs`` uses, generated from the same constants as the LAB arms (vharvey/fv/arm.py)
so both harnesses give the agent identical tools and instructions. Only the ending differs: DSH has no ``finish``
tool, a turn ends when the model replies without a tool call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .arm import COMPLETE_TOOL, LATE_MSG, PROMPT, TOOLS

DSH_END = "and then end your turn (reply without calling a tool). You will not be asked again."
LAB_END = "and call\nfinish again. You will not be asked again."

COMPLETE_DSH = """
**Completeness check.** Call `fv_check_complete(conditions, matters)` with the question's conditions and your current
list. Each matter in `missing_from_your_list` comes with evidence (file path + quote) for each condition: open that
file and add the matter only if the document confirms it (cite the file as evidence). For each matter in
`listed_but_contradicted`, re-check it in its documents. If the reply warns that the conditions are too broad, add the
question's specific condition and call again. The index can be wrong in both directions, so the documents decide. For
superlative questions ("most recent", "largest") use it to make sure you compared all candidates.
"""


def build() -> dict:
    if LAB_END not in LATE_MSG:
        raise RuntimeError("LATE_MSG changed: update dsh_assets.LAB_END")
    late = LATE_MSG.replace(LAB_END, DSH_END)
    late_c = late.replace("\nThen update response.md", COMPLETE_DSH + "\nThen update response.md")
    return {"tools": TOOLS, "complete_tool": COMPLETE_TOOL, "start_prompt": PROMPT,
            "start_prompt_complete": PROMPT + COMPLETE_DSH, "late_message": late, "late_message_complete": late_c}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=1) + "\n")
    print(out)
