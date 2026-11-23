"""Record real model answers into samples/golden.json.

Run:  python -m tools.record_golden          (uses the Claude Code CLI adapter)
The default tests replay these recordings, so they need no network.
"""

import json
from pathlib import Path

from server.ai.interpreter import SYSTEM_PROMPT, ClaudeCliInterpreter
from server.ai.prompt import build_user_message
from server.core.spec import Segment, ShaftSpec

GOLDEN = Path(__file__).resolve().parent.parent / "samples" / "golden.json"


def spec_of(before) -> ShaftSpec:
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=d, length=length) for d, length in before])


def main():
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cli = ClaudeCliInterpreter()
    for case in cases:
        raw = cli._complete(SYSTEM_PROMPT, build_user_message(spec_of(case["before"]), case["utterance"]))
        case["recorded"] = raw
        print(f"{case['name']}: {raw!r}")
    GOLDEN.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
