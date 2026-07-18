#!/usr/bin/env python3
"""
transmission_operator.py — logos tagging pass: transmission channel

Reads a vivified inference, classifies how the communication moves through the
social field, attaches logos.transmission coordinates to the inference JSON.

_src: Logos Core Tree synthesis (project)
Schema: pillars/logos/logos_schema_v01.json#dimensions.transmission
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

PROMPT = """You are classifying the transmission channel of a text unit — how the
communication moves through the social field, not what it says.

The three transmission types:
  broadcast — one-to-many, public, low fidelity to source (news, rulings, announcements)
  leak      — restricted recipients, high emotional charge, unofficial, not meant to travel further
  archive   — past-to-future, preserved, institutional, resistant to revision (records, filed documents)

Note: the same content can be transmitted differently in different contexts.
Classify the transmission as it appears in this text, not how it could be used.

Text:
{text}

Return ONLY valid JSON:
{{
  "transmission": "<broadcast|leak|archive>",
  "rationale": "<one sentence — how this communication moves>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.transmission coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "transmission",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated transmission result into inference['logos']['transmission'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["transmission"] = {
        "value":      result["transmission"],
        "rationale":  result.get("rationale"),
        "confidence": result.get("confidence"),
        "_src":       ["Logos Core Tree"],
        "_operator":  "transmission_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with transmission channel"
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
        print(f"logos.transmission tagged: {tagged['logos']['transmission']['value']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/transmission_operator.py | created — transmission channel logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/transmission_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/transmission_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/transmission_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/transmission_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
