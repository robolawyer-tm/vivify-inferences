#!/usr/bin/env python3
"""
resonance_operator.py — logos tagging pass: emotional field resonance

Reads a vivified inference, classifies the emotional field the communication
carries or creates, attaches logos.resonance coordinates to the inference JSON.

_src: Logos Core Tree synthesis (project); Machin (affective field, structural layer)
Schema: pillars/logos/logos_schema_v01.json#dimensions.resonance
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

PROMPT = """You are classifying the emotional field resonance of a text unit — the
affective state the communication carries or creates in the local social environment.

The three resonance types:
  harmony  — synchronization, shared understanding, empathic alignment between parties
  friction — disconnection, dissonance, unempathic states, parties pulling apart
  illusion — apparent harmony masking underlying friction; surfaces as agreement
             but contains suppressed conflict or false alignment

Note: illusion is the most structurally significant for conflict analysis.
Surface-level politeness concealing adversarial intent is illusion, not harmony.
A document that uses cooperative language while making false claims is illusion.

Text:
{text}

Return ONLY valid JSON:
{{
  "resonance": "<harmony|friction|illusion>",
  "surface":   "<what the communication presents>",
  "underlying": "<what the communication masks, or null if no masking>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.resonance coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "resonance",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated resonance result into inference['logos']['resonance'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["resonance"] = {
        "value":      result["resonance"],
        "surface":    result.get("surface"),
        "underlying": result.get("underlying"),
        "confidence": result.get("confidence"),
        "_model":     result.get("_model"),
        "_src":       ["Logos Core Tree", "Machin"],
        "_operator":  "resonance_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with emotional field resonance"
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
        print(f"logos.resonance tagged: {tagged['logos']['resonance']['value']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/resonance_operator.py | created — emotional field resonance logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/resonance_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/resonance_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/resonance_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/resonance_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/resonance_operator.py | parse() records _model beside _operator — which model produced the coordinate
