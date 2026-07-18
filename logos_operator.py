#!/usr/bin/env python3
"""
logos_operator.py — run all logos tagging operators against a single inference

Chains all seven functional dimension operators in sequence, attaching a complete
logos coordinate set to the inference JSON. Each operator is independent — a
failure in one does not block the rest.

Schema: pillars/logos/logos_schema_v01.json
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, LLMUnavailable

import cooperative_operator
import act_type_operator
import transmission_operator
import resonance_operator
import authority_operator
import utility_operator
import social_field_operator
import structural_operator
import logos_narrative

OPERATORS = [
    ("act_type",      act_type_operator),
    ("cooperative",   cooperative_operator),
    ("transmission",  transmission_operator),
    ("resonance",     resonance_operator),
    ("authority",     authority_operator),
    ("utility",       utility_operator),
    ("social_field",  social_field_operator),
    ("structural",    structural_operator),
    ("narrative",     logos_narrative),
]


def run(inference: dict, skip: list = None) -> dict:
    """Run all logos operators against an inference.

    - Each operator attaches its result to inference["logos"][dimension]
    - Failures are caught and recorded in inference["logos"]["_errors"]
    - skip: list of dimension names to omit (e.g. ["social_field"])
    """
    skip = skip or []
    errors = {}

    for name, module in OPERATORS:
        if name in skip:
            continue
        try:
            inference = module.run(inference)
        except LLMUnavailable:
            # The CLI is down (quota/auth) — remaining operators will fail too.
            # Abort the whole inference rather than recording 8 identical errors.
            raise
        except Exception as e:
            errors[name] = str(e)

    if errors:
        inference.setdefault("logos", {})["_errors"] = errors

    inference.setdefault("logos", {})["_runner"] = "logos_operator.py"
    return inference


def summary(inference: dict) -> str:
    """One-line summary of logos coordinates for terminal output."""
    logos = inference.get("logos", {})
    parts = []

    act = logos.get("act_type", {}).get("value")
    if act:
        mismatch = " [authority mismatch]" if logos["act_type"].get("authority_mismatch") else ""
        parts.append(f"act={act}{mismatch}")

    coop = logos.get("cooperative", {})
    if coop.get("status"):
        violated = f":{coop['maxim_violated']}" if coop.get("maxim_violated") else ""
        parts.append(f"cooperative={coop['status']}{violated}")

    tx = logos.get("transmission", {}).get("value")
    if tx:
        parts.append(f"tx={tx}")

    res = logos.get("resonance", {}).get("value")
    if res:
        parts.append(f"resonance={res}")

    auth = logos.get("authority", {}).get("value")
    if auth:
        parts.append(f"authority={auth}")

    util = logos.get("utility", {}).get("value")
    if util:
        parts.append(f"utility={util}")

    sf = logos.get("social_field", {})
    if sf.get("grid") is not None:
        parts.append(f"grid={sf['grid']:.2f} group={sf['group']:.2f}")

    struct = logos.get("structural", {})
    if struct.get("layer"):
        overlays = f"+{','.join(struct['overlays'])}" if struct.get("overlays") else ""
        parts.append(f"layer={struct['layer']}{overlays}")

    errors = logos.get("_errors", {})
    if errors:
        parts.append(f"ERRORS={list(errors.keys())}")

    coords = " | ".join(parts) if parts else "no logos coordinates"

    narrative = logos.get("narrative", {}).get("text")
    if narrative:
        return f"{coords}\n  → {narrative}"
    return coords


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run all logos operators against an inference"
    )
    parser.add_argument("file", nargs="?", help="inference JSON file to tag")
    parser.add_argument("--dry-run", action="store_true", help="print result, do not write")
    parser.add_argument("--skip", nargs="+", metavar="DIM",
                        help="dimensions to skip (e.g. --skip social_field)")
    args = parser.parse_args()

    path = Path(args.file) if args.file else None
    inference = read_json(path) if path else json.load(sys.stdin)

    try:
        tagged = run(inference, skip=args.skip)
    except LLMUnavailable as e:
        print(f"LLM unavailable (quota/auth?): {e}", file=sys.stderr)
        print("Aborting — fix the CLI before re-running. Exit code 3.", file=sys.stderr)
        sys.exit(3)

    if args.dry_run or not path:
        print(json.dumps(tagged, indent=2))
    else:
        write_json(path, tagged)
        print(summary(tagged))
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/logos_operator.py | created — runner chaining all seven functional logos operators with error isolation and summary output
# llm: claude-sonnet-4-6 | 2026-05-23 | repos/vivify-operators/logos_operator.py | added logos_narrative as 8th operator; summary() prints narrative below coordinate line
# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/logos_operator.py | fail-fast on LLMUnavailable — abort inference instead of recording 8 identical errors; main exits 3
