#!/usr/bin/env python3
"""
utility_operator.py — logos tagging pass: communication utility/payload

Reads a vivified inference, classifies what the communication is functionally
for — its payload — attaches logos.utility coordinates to the inference JSON.

_src: Logos Core Tree synthesis (project)
Schema: pillars/logos/logos_schema_v01.json#dimensions.utility
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

PROMPT = """You are classifying the utility (functional payload) of a text unit —
what the communication is fundamentally for, independent of its surface form.

The three utility types:
  instruction — actionable, enabling; tells someone how or what to do;
                the receiver is expected to act differently after receiving it
  narrative   — meaning-making, contextualizing, mythologizing; constructs or
                reinforces a story about what is happening and why
  currency    — value-tracking, social capital, ledger of obligation; marks who
                owes what to whom, who has standing, who has acted well or badly

Note: a single communication can carry multiple utilities. Classify the primary one.
Currency is common in conflict contexts — statements that position parties in a
social ledger even when they appear to be informational.

Text:
{text}

Return ONLY valid JSON:
{{
  "utility":   "<instruction|narrative|currency>",
  "secondary": "<instruction|narrative|currency|null>",
  "rationale": "<one sentence — what this communication is for>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.utility coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "utility",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated utility result into inference['logos']['utility'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["utility"] = {
        "value":      result["utility"],
        "secondary":  result.get("secondary"),
        "rationale":  result.get("rationale"),
        "confidence": result.get("confidence"),
        "_model":     result.get("_model"),
        "_src":       ["Logos Core Tree"],
        "_operator":  "utility_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with communication utility/payload"
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
        print(f"logos.utility tagged: {tagged['logos']['utility']['value']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/utility_operator.py | created — communication utility/payload logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/utility_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/utility_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/utility_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/utility_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/utility_operator.py | parse() records _model beside _operator — which model produced the coordinate
