#!/usr/bin/env python3
"""
logos_narrative.py — human-readable synthesis of functional logos coordinates

Reads all completed functional coordinates from inference["logos"] and produces
one plain-English sentence describing what the communication is doing. No jargon.
Runs after all seven functional operators have attached their coordinates.
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, llm_call, extract_json

PROMPT = """You are reading functional coordinates that describe what a communication act does.
The coordinates come from a theoretical analysis — your job is to translate them into one plain sentence
that a thoughtful non-specialist could read and immediately understand.

Do NOT use academic terms like "assertive", "commissive", "implicature", "Gricean", "grid/group".
DO use plain language: "claims", "asks", "promises", "expresses", "declares", "honest", "misleading", "evasive".

Coordinates:
  act_type:     {act_type}
  cooperative:  {cooperative_status}{maxim_note}
  transmission: {transmission}
  resonance:    {resonance}
  authority:    {authority}
  utility:      {utility}
  social_field: grid={grid}, group={group}

Context (if available): {context}

Raw text: {raw_text}

Write ONE sentence. It should describe what the communication is doing — not summarize the text.
The sentence should feel like a perceptive human observation, not a label.

Return ONLY valid JSON:
{{"narrative": "one sentence here"}}
"""


def run(inference: dict) -> dict:
    """Attach logos.narrative to an inference with completed functional coordinates."""
    logos = inference.get("logos", {})

    act = logos.get("act_type", {}).get("value", "unknown")
    coop = logos.get("cooperative", {})
    coop_status = coop.get("status", "unknown")
    maxim = coop.get("maxim_violated")
    maxim_note = f" (maxim violated: {maxim})" if maxim else ""
    tx = logos.get("transmission", {}).get("value", "unknown")
    res = logos.get("resonance", {}).get("value", "unknown")
    auth = logos.get("authority", {}).get("value", "unknown")
    util = logos.get("utility", {}).get("value", "unknown")
    sf = logos.get("social_field", {})
    grid = sf.get("grid", "?")
    group = sf.get("group", "?")

    raw = llm_call(
        PROMPT.format(
            act_type=act,
            cooperative_status=coop_status,
            maxim_note=maxim_note,
            transmission=tx,
            resonance=res,
            authority=auth,
            utility=util,
            grid=grid,
            group=group,
            context=inference.get("context", "none"),
            raw_text=inference.get("raw_text", ""),
        ),
        capability="logos_operator",
    )
    result = extract_json(raw)

    logos["narrative"] = {
        "text":      result["narrative"],
        "_operator": "logos_narrative.py",
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Synthesize logos coordinates into a human-readable narrative"
    )
    parser.add_argument("file", nargs="?", help="inference JSON file")
    parser.add_argument("--dry-run", action="store_true", help="print result, do not write")
    args = parser.parse_args()

    path = Path(args.file) if args.file else None
    inference = read_json(path) if path else json.load(sys.stdin)

    tagged = run(inference)

    if args.dry_run or not path:
        print(json.dumps(tagged, indent=2))
    else:
        write_json(path, tagged)
        print(f"logos.narrative: {tagged['logos']['narrative']['text']}")
# llm: claude-sonnet-4-6 | 2026-05-23 | repos/vivify-operators/logos_narrative.py | created — human-readable synthesis of all functional logos coordinates into one plain-English sentence
