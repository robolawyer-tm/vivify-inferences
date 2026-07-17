#!/usr/bin/env python3
"""
act_position_operator.py — logos tagging pass: the text's position relative to its events

Reads a vivified inference, classifies whether the text is itself a move INSIDE
the events it describes (within) or a report standing OUTSIDE them (about), and
attaches logos.act_position coordinates to the inference JSON.

Emergent coordinate: forced by three observed conflations in 2026-07 field work —
the round-trip decoder read an archival case account as the suppressive ruling
itself; research documenting illusion ranked as illusion; cross_scale linked
texts about conflict dynamics to texts living them. Without this axis the
instrument cannot distinguish a deceptive document from a document describing
deception.

_src: vivify-operators round-trip loss test (2026-07-13, experiments/round_trip)
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, call_and_validate

PROMPT = """You are classifying a text unit's position relative to the events it describes.

The two positions:
  within — the text is itself a move inside those events: it acts on the
           situation (a ruling, testimony, a lab report, a demand letter, an
           affidavit, an argument addressed to an opponent). Removing the text
           would change the events themselves.
  about  — the text stands outside the events and reports, summarizes, analyzes,
           or theorizes them (a case summary, a news account, research, a
           retrospective, project or session notes). Removing the text leaves
           the events unchanged.

Judge the text's own position, never its subject matter: a calm summary OF a
suppression is 'about'; the suppressing document itself is 'within'. A text can
describe terrible dynamics and still be 'about'; a polite cover letter can be
'within'.

Text:
{text}

Return ONLY valid JSON:
{{
  "act_position": "<within|about>",
  "rationale": "<one sentence: what the text does relative to its events>",
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.act_position coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(PROMPT.format(text=text), "act_position",
                               capability="logos_operator", sensitive=True)
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated act_position result into inference['logos']['act_position'].

    Split out from run() so a future fused pass can reuse this mapping with a
    pre-fetched sub-result, without re-calling the LLM (resonance pattern)."""
    logos = inference.setdefault("logos", {})
    logos["act_position"] = {
        "value":      result["act_position"],
        "rationale":  result.get("rationale"),
        "confidence": result.get("confidence"),
        "_src":       ["round_trip loss test 2026-07-13"],
        "_operator":  "act_position_operator.py"
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with its position relative to described events"
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
        print(f"logos.act_position tagged: {tagged['logos']['act_position']['value']}")
# llm: claude-fable-5 | 2026-07-17 | repos/vivify-operators/act_position_operator.py | created — within|about vantage coordinate, forced by three observed conflations (round-trip tier A, research-tops-tension, cross_scale about-links)
