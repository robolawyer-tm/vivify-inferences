#!/usr/bin/env python3
"""
conflict_operator.py — conflict tagging pass: structural conditions and behavioral signals

Reads completed logos coordinates from a tagged inference and outputs conflict-specific
signals to inference["conflict"]. Causation is structural, not individual — behaviors
appear chaotic but are predictable given the societal schema present.

_src: Granovetter (threshold models, 1978); Glasl (conflict escalation);
      Durkheim (social facts, structural causation); Bandura (moral disengagement)
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, call_and_validate, LLMUnavailable

PROMPT = """You are reading logos coordinates already attached to an inference and
identifying structural conflict signals. Causation is structural, not individual —
your job is to read the terrain, not attribute blame.

Two distinct layers:

  SCHEMA — societal structural conditions present (slow-moving, background, constitutive).
  These create the terrain and entanglement. Exists independently of any individual action.

  BEHAVIOR — predictable actions occurring within the schema. Appear chaotic when read
  as individual choices; fully predictable given the schema conditions.

Windows of opportunity open at the intersection of schema conditions + behavioral trigger.
Actions seemingly unrelated to conflict can open windows through social entanglement —
structural connections in the societal schema that are non-obvious but traceable.

Logos coordinates to read:
  act_type:      {act_type}
  cooperative:   {cooperative} (maxim violated: {maxim_violated})
  transmission:  {transmission}
  resonance:     {resonance} (underlying: {resonance_underlying})
  authority:     {authority}
  utility:       {utility}
  social_field:  grid={grid}, group={group}, quadrant={quadrant}
  structural:    layer={structural_layer}

Raw text: {raw_text}
Context: {context}

Assess the five conflict dimensions:

  schema — societal structural conditions present:
    none         — no conflict-relevant structural conditions detected
    latent       — structural conditions present but not yet activated
    activated    — schema conditions actively shaping behavior
    entangled    — non-obvious structural connections to conflict terrain present

  behavior — predictable actions within the schema:
    none         — no conflict-relevant behaviors detected
    positioning  — parties establishing relative positions (utility=currency signals)
    suppression  — conflict masked as cooperation (resonance=illusion signals)
    escalating   — behaviors consistent with Glasl escalation stages
    rationalizing — damage being explained away (moral disengagement signals)

  terrain — position in the conflict distribution:
    center       — within the unified bell curve, reasoning capacity intact
    drifting     — moving toward fringe, ambiguity tolerance reducing
    fringe       — fringe attractor; certainty-seeking, threat-response dominant
    fringe_hook  — fringe with social-neural connection to opposing fringe (horseshoe)

  window — structural opportunity for harm (not prediction of action):
    closed       — no window present
    forming      — conditions accumulating, not yet open
    open         — structural conditions sufficient for harm; individuals may still choose not to act
    rationalizing — window open, harm occurring and being explained as something else

  Note: window=open means the opportunity exists at the structural level. An individual or
  small group that recognizes the window and declines to use it is doing something morally
  significant — a counter-force in the terrain and a potential restoration signal. The model
  does not predict individual action, only structural availability.

  escalation_phase — Granovetter threshold position:
    none         — no escalation dynamic detected
    early        — below threshold, isolated signals
    threshold    — at the tipping point; cascade possible
    exponential  — self-reinforcing, threshold crossed, restoration requires structural shift

Return ONLY valid JSON:
{{
  "schema":           "<none|latent|activated|entangled>",
  "schema_signals":   ["<which logos coordinates drove this>"],
  "behavior":         "<none|positioning|suppression|escalating|rationalizing>",
  "behavior_signals": ["<which logos coordinates drove this>"],
  "terrain":          "<center|drifting|fringe|fringe_hook>",
  "window":           "<closed|forming|open|rationalizing>",
  "escalation_phase": "<none|early|threshold|exponential>",
  "confidence":       <0.0-1.0>,
  "rationale":        "<one sentence — what structural conditions this communication reveals>"
}}
"""


def run(inference: dict) -> dict:
    """Attach conflict coordinates to a logos-tagged inference."""
    logos = inference.get("logos", {})
    if not logos:
        return inference

    act = logos.get("act_type", {}).get("value", "unknown")
    coop = logos.get("cooperative", {})
    tx = logos.get("transmission", {}).get("value", "unknown")
    res = logos.get("resonance", {})
    auth = logos.get("authority", {}).get("value", "unknown")
    util = logos.get("utility", {}).get("value", "unknown")
    sf = logos.get("social_field", {})
    struct = logos.get("structural", {})

    result = call_and_validate(
        PROMPT.format(
            act_type=act,
            cooperative=coop.get("status", "unknown"),
            maxim_violated=coop.get("maxim_violated") or "none",
            transmission=tx,
            resonance=res.get("value", "unknown"),
            resonance_underlying=res.get("underlying") or "none",
            authority=auth,
            utility=util,
            grid=sf.get("grid", "?"),
            group=sf.get("group", "?"),
            quadrant=sf.get("quadrant", "unknown"),
            structural_layer=struct.get("layer", "unknown"),
            raw_text=inference.get("raw_text", ""),
            context=inference.get("context", "none"),
        ),
        "conflict",
        capability="conflict_operator",
        sensitive=True,
    )

    inference.setdefault("conflict", {}).update({
        "schema":           result["schema"],
        "schema_signals":   result.get("schema_signals", []),
        "behavior":         result["behavior"],
        "behavior_signals": result.get("behavior_signals", []),
        "terrain":          result["terrain"],
        "window":           result["window"],
        "escalation_phase": result["escalation_phase"],
        "confidence":       result.get("confidence"),
        "rationale":        result.get("rationale"),
        "_src":             ["Granovetter", "Glasl", "Durkheim", "Bandura"],
        "_operator":        "conflict_operator.py",
    })
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with structural conflict coordinates"
    )
    parser.add_argument("file", nargs="?", help="logos-tagged inference JSON file")
    parser.add_argument("--dry-run", action="store_true", help="print result, do not write")
    args = parser.parse_args()

    path = Path(args.file) if args.file else None
    inference = read_json(path) if path else json.load(sys.stdin)

    try:
        tagged = run(inference)
    except LLMUnavailable as e:
        print(f"LLM unavailable (quota/auth?): {e}", file=sys.stderr)
        print("Aborting — fix the CLI before re-running. Exit code 3.", file=sys.stderr)
        sys.exit(3)

    if args.dry_run or not path:
        print(json.dumps(tagged, indent=2))
    else:
        write_json(path, tagged)
        c = tagged["conflict"]
        print(f"conflict: schema={c['schema']} behavior={c['behavior']} terrain={c['terrain']} window={c['window']} phase={c['escalation_phase']}")
        if c.get("rationale"):
            print(f"  → {c['rationale']}")
# llm: claude-sonnet-4-6 | 2026-05-26 | repos/vivify-operators/conflict_operator.py | created — structural conflict tagging operator reading logos coordinates
# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/conflict_operator.py | fail-fast: main exits 3 on LLMUnavailable instead of recording a doomed error
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/conflict_operator.py | wired inbound validation gate: validate_coordinates() on extract_json output
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/conflict_operator.py | wired sensitive=True into llm_call; fixed missing validate_coordinates import
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/conflict_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped
