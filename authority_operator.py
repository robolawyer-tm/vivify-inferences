#!/usr/bin/env python3
"""
authority_operator.py — logos tagging pass: authority source

Reads a vivified inference, classifies what power structure or trust source the
communication draws on to be heard, attaches logos.authority coordinates.

_src: Logos Core Tree synthesis (project); Weber (authority typology, background)
Schema: pillars/logos/logos_schema_v01.json#dimensions.authority
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, resolve_model, call_and_validate

PROMPT = """You are classifying the authority source of a text unit — what power
structure or trust source the communication draws on to be heard and believed.

The three authority types:
  sovereign — top-down, institutional, formal, legal; derives legitimacy from
              official position (court, employer, government, credentialed expert)
  tribal    — horizontal, peer, normative, cultural; derives legitimacy from
              shared membership, community standards, what "we" do
  occult    — hidden, not publicly acknowledged; known only within a restricted
              group; operates outside official channels (back-channel agreements,
              informal power, undisclosed relationships)

Note: occult authority is not supernatural — it is authority that is real but
unacknowledged in the official record. Institutional actors frequently exercise
occult authority while maintaining sovereign framing.

Text:
{text}

Return ONLY valid JSON:
{{
  "authority": "<sovereign|tribal|occult>",
  "source":    "<what specific institution, group, or hidden structure is invoked>",
  "rationale": "<one sentence>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.authority coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "authority",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated authority result into inference['logos']['authority'].

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping with a pre-fetched sub-result, without re-calling the LLM."""
    logos = inference.setdefault("logos", {})
    logos["authority"] = {
        "value":      result["authority"],
        "source":     result.get("source"),
        "rationale":  result.get("rationale"),
        "confidence": result.get("confidence"),
        "_src":       ["Logos Core Tree", "Weber"],
        "_operator":  "authority_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with authority source"
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
        print(f"logos.authority tagged: {tagged['logos']['authority']['value']}")
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/authority_operator.py | created — authority source logos tagging operator
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/authority_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/authority_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/authority_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/authority_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
