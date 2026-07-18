#!/usr/bin/env python3
"""
cooperative_operator.py — logos tagging pass: Grice cooperative principle

Reads a vivified inference, scores it against Grice's cooperative maxims via LLM,
attaches logos.cooperative coordinates to the inference JSON.

_src: Grice (Cooperative Principle, 1975) + neo-Gricean extensions
Schema: pillars/logos/logos_schema_v01.json#dimensions.cooperative
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

SCHEMA_PATH = Path(__file__).parent.parent / "pillars/logos/logos_schema_v01.json"

PROMPT = """You are applying Grice's Cooperative Principle (1975) to tag a text unit.
Researcher context: Grice, including Levinson, Horn, Sperber & Wilson (relevance theory).

The four maxims:
  quantity — say enough, not too much
  quality  — say what you believe to be true
  relation — say what is relevant
  manner   — be clear and orderly

Text:
{text}

Return ONLY valid JSON:
{{
  "status": "<honored|violated|suspended>",
  "maxim_violated": "<quantity|quality|relation|manner|null>",
  "implicature": "<what is meant beyond what is said, or null>",
  "confidence": <0.0-1.0>
}}

If multiple maxims are violated, name the primary one.
suspended = cooperative frame is off (irony, ritual, fiction).
"""


def run(inference: dict) -> dict:
    """Attach logos.cooperative coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "cooperative",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated cooperative result into inference['logos']['cooperative'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["cooperative"] = {
        "status":         result["status"],
        "maxim_violated": result.get("maxim_violated"),
        "implicature":    result.get("implicature"),
        "confidence":     result.get("confidence"),
        "_src":           ["Grice"],
        "_operator":      "cooperative_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with Grice cooperative maxim scores"
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
        print(f"logos.cooperative tagged: {tagged['logos']['cooperative']['status']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/cooperative_operator.py | created — Grice cooperative maxim logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/cooperative_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/cooperative_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/cooperative_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/cooperative_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
