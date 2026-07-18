#!/usr/bin/env python3
"""
act_type_operator.py — logos tagging pass: Austin/Searle speech act type

Reads a vivified inference, classifies it against the five speech act types via LLM,
attaches logos.act_type coordinates to the inference JSON.

_src: Austin (How to Do Things with Words, 1962), Searle (Speech Acts, 1969)
Schema: pillars/logos/logos_schema_v01.json#dimensions.act_type
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

SCHEMA_PATH = Path(__file__).parent.parent / "pillars/logos/logos_schema_v01.json"

PROMPT = """You are applying Austin and Searle's speech act theory to classify a text unit.
Researcher context: Austin (1962), Searle (1969), including Searle's five illocutionary categories.

The five act types:
  assertive   — claims something is true (stating, asserting, describing)
  directive   — attempts to get someone to do something (requesting, ordering, questioning)
  commissive  — commits the speaker to future action (promising, threatening, offering)
  expressive  — expresses a psychological state (thanking, apologizing, congratulating)
  declaration — changes reality by being said (a verdict, a ruling, a dismissal, a firing)

Note: declarations require institutional authority to function — a private person cannot
declare someone guilty. When a declaration is made without that authority, classify as
the underlying act type and note the authority mismatch.

Text:
{text}

Return ONLY valid JSON:
{{
  "act_type": "<assertive|directive|commissive|expressive|declaration>",
  "authority_mismatch": <true|false>,
  "rationale": "<one sentence — what this utterance does>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.act_type coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "act_type",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated act_type result into inference['logos']['act_type'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["act_type"] = {
        "value":              result["act_type"],
        "authority_mismatch": result.get("authority_mismatch", False),
        "rationale":          result.get("rationale"),
        "confidence":         result.get("confidence"),
        "_src":               ["Austin", "Searle"],
        "_operator":          "act_type_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with Austin/Searle speech act type"
    )
    parser.add_argument("file", nargs="?", help="inference JSON file to tag")
    parser.add_argument("--dry-run", action="store_true", help="print result, do not write")
    args = parser.parse_args()

    path = Path(args.file) if args.file else None
    inference = read_json(path) if path else json.load(sys.stdin)

    tagged = run(inference)

    if args.dry_run or not path:
        print(json.dumps(tagged, indent=2))
    else:
        write_json(path, tagged)
        print(f"logos.act_type tagged: {tagged['logos']['act_type']['value']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/act_type_operator.py | created — Austin/Searle speech act type logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/act_type_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/act_type_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/act_type_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/act_type_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
