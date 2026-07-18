#!/usr/bin/env python3
"""
social_field_operator.py — logos tagging pass: Douglas grid/group axes

Reads a vivified inference, scores it on Douglas's grid/group axes,
attaches logos.social_field coordinates to the inference JSON.

_src: Douglas (Purity and Danger, 1966; Natural Symbols, 1970)
Schema: pillars/logos/logos_schema_v01.json#dimensions.social_field
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

PROMPT = """You are applying Mary Douglas's grid/group framework to score a text unit.
Researcher context: Douglas (Purity and Danger 1966, Natural Symbols 1970).

Two independent axes, each 0.0 to 1.0:

  grid  — degree to which behavior is constrained by explicit rules and classifications
          0.0 = unconstrained, personal, negotiable, improvised
          1.0 = rigid, rule-bound, role-defined, hierarchically prescribed

  group — degree to which individual identity is defined by group membership
          0.0 = individual, autonomous, weak boundary between self and outside
          1.0 = collective, strong boundary, identity inseparable from group

The four quadrants this produces:
  low grid / low group   — individualist, competitive, negotiated order
  high grid / low group  — isolated, role-defined but not group-belonging
  low grid / high group  — egalitarian, strong boundary, internal negotiation
  high grid / high group — hierarchical, role and group together, most institutionalized

Score the social constraint field in which this communication occurs, not the
content of the communication itself.

Text:
{text}

Return ONLY valid JSON:
{{
  "grid":      <0.0-1.0>,
  "group":     <0.0-1.0>,
  "quadrant":  "<individualist|isolate|egalitarian|hierarchical>",
  "rationale": "<one sentence — what social field this communication occurs in>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.social_field coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "social_field",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated social_field result into inference['logos']['social_field'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["social_field"] = {
        "grid":       result["grid"],
        "group":      result["group"],
        "quadrant":   result.get("quadrant"),
        "rationale":  result.get("rationale"),
        "confidence": result.get("confidence"),
        "_src":       ["Douglas"],
        "_operator":  "social_field_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with Douglas grid/group social field scores"
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
        print(f"logos.social_field tagged: grid={tagged['logos']['social_field']['grid']} group={tagged['logos']['social_field']['group']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/social_field_operator.py | created — Douglas grid/group social field logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/social_field_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/social_field_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/social_field_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/social_field_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
