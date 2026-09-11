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
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import (read_json, write_json, call_and_validate, modal_choice,
                         categorical_signature, _vote_count,
                         CoordinateValidationError, LLMUnavailable)

# cwd-independent, like logos_fused.py:43 — a relative config path was the D-1 bug
CONFIG = str(Path(__file__).parent / "config")

# Each entry is a COORDINATE plus the fields that must travel with it: the enum that
# names it, and its dependents. This is the unit that comes from one draw.
# logos_fused votes its 8 dimensions independently for exactly this reason — one
# wobble must not discard the others' agreement (logos_fused.py:217-224). conflict
# previously voted all five jointly, so one unstable field decided the whole block,
# which is what made run 3 report `terrain 3/3 [block 2/3]`.
CONFLICT_DIMS = (
    ("schema",           ("schema",),           ("schema_signals",)),
    ("behavior",         ("behavior",),         ("behavior_signals",)),
    ("terrain",          ("terrain",),          ("terrain_distance", "terrain_hook")),
    ("window",           ("window",),           ()),
    ("escalation_phase", ("escalation_phase",), ()),
)


def vote_per_dimension(prompt, retries=2, votes=None):
    """Take N draws and choose the modal one PER COORDINATE, not per whole block.

    Each coordinate's enum and its dependent fields come from a SINGLE real draw, so
    nothing incoherent is assembled within a coordinate — the guarantee modal_choice
    exists to give (a status with a contradicting maxim beside it, and that class of
    result generally). What is assembled across coordinates is the same thing
    logos_fused already does across its eight dimensions.

    rationale and confidence describe the whole reading rather than any one
    coordinate, so they come from the overall modal draw — still a draw that really
    occurred.

    The record keeps its familiar shape (n / agreed / unanimous / distribution) so
    existing readers are unaffected, but `agreed` now means whole-block COHERENCE and
    no longer selects what is stored. `by_dim` carries the count that actually decided
    each coordinate.
    """
    votes = _vote_count() if votes is None else max(1, votes)
    draws, last_err = [], None
    for _ in range(votes):
        try:
            draws.append(call_and_validate(prompt, "conflict", "conflict_operator",
                                           True, None, retries, CONFIG))
        except (CoordinateValidationError, json.JSONDecodeError) as e:
            last_err = e
    if not draws:
        raise last_err

    primary_idx, record = modal_choice(
        draws, lambda d: categorical_signature(d, "conflict", CONFIG))
    merged = dict(draws[primary_idx])

    by_dim, distribution = {}, {}
    for name, enums, carried in CONFLICT_DIMS:
        key = (_terrain_key if name == "terrain"
               else lambda d, e=enums: tuple((f, d.get(f)) for f in e))
        idx, dim_record = modal_choice(draws, key)
        chosen = draws[idx]
        for field in enums + carried:
            if field in chosen:
                merged[field] = chosen[field]
        by_dim[name] = {k: dim_record[k] for k in ("n", "agreed", "unanimous")}
        distribution.update(dim_record["distribution"])

    # The stored terrain is DERIVED, so its vote above ran on the derived bin. Keep the
    # drawn label's spread beside it, and every draw's position, so the number itself
    # is measurable across sessions and the bin edges can be re-cut from the record.
    distribution["terrain_drawn"] = dict(Counter(str(d.get("terrain")) for d in draws))
    by_dim["terrain"]["distances"] = [d.get("terrain_distance") for d in draws]

    record["distribution"] = {**record.get("distribution", {}), **distribution}
    record["by_dim"] = by_dim
    record["quarantined"] = votes - len(draws)
    return merged, record

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

  terrain_distance — the SAME reading expressed as a position rather than a bin:
    0.0 = centre of the unified distribution, 1.0 = furthest fringe. Judge it directly
    from the text, not by translating the label above. The stored terrain is derived
    from this number, so a case sitting between two bins should read as a number
    between them rather than being rounded to whichever bin feels closer.
  terrain_hook — true ONLY if the position carries a social-neural connection to the
    OPPOSING fringe (the horseshoe). Distance alone never implies a hook.

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
  "terrain_distance": <0.0-1.0>,
  "terrain_hook":     <true|false>,
  "window":           "<closed|forming|open|rationalizing>",
  "escalation_phase": "<none|early|threshold|exponential>",
  "confidence":       <0.0-1.0>,
  "rationale":        "<one sentence — what structural conditions this communication reveals>"
}}
"""


# Bin edges on the 0.0-1.0 position. Thresholds are a modelling choice, not a
# measurement — change them here and nowhere else.
TERRAIN_DRIFTING_AT = 1 / 3
TERRAIN_FRINGE_AT = 2 / 3


def derive_terrain(distance, hook):
    """Terrain is a POSITION in the conflict distribution, not a free label.

    center -> drifting -> fringe is a walk outward from the centre of the bell curve,
    so asking for it as a 4-way categorical bins a continuous quantity and lets a case
    near a boundary flip bins between sittings while each sitting stays unanimous.
    Canonical Cotton did exactly that: fringe_hook (stored) -> drifting 3/3 (2026-09-07)
    -> fringe 3/3 (2026-09-10), same text each time. Deriving the bin from the number
    does NOT stop a flip — 0.32 one sitting and 0.35 the next still crosses an edge —
    but it makes the movement a measured change in distance, so a case sitting near
    an edge is visible as near an edge instead of reading as a confident bin.

    fringe_hook is NOT further out than fringe — it is fringe plus a connection to the
    opposing fringe, so it comes from the hook flag rather than from more distance.
    Same shape as social_field.quadrant deriving from grid/group, and as
    cross_scale.tension_band deriving from tension_score.
    """
    if isinstance(distance, bool) or not isinstance(distance, (int, float)):
        return None
    if distance < TERRAIN_DRIFTING_AT:
        return "center"
    if distance < TERRAIN_FRINGE_AT:
        return "drifting"
    return "fringe_hook" if hook else "fringe"


def _terrain_key(draw):
    """Vote on the bin that will be STORED — derived from the draw's position — not on
    the drawn label, which is the reading derive_terrain() replaced. Falls back to the
    drawn label only where run() would, when the position is missing or invalid."""
    derived = derive_terrain(draw.get("terrain_distance"), draw.get("terrain_hook"))
    return (("terrain", derived if derived is not None else draw.get("terrain")),)


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

    result, votes_record = vote_per_dimension(
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
        )
    )

    drawn_terrain = result["terrain"]
    distance = result.get("terrain_distance")
    hook = bool(result.get("terrain_hook"))
    derived_terrain = derive_terrain(distance, hook)

    inference.setdefault("conflict", {}).update({
        "schema":           result["schema"],
        "schema_signals":   result.get("schema_signals", []),
        "behavior":         result["behavior"],
        "behavior_signals": result.get("behavior_signals", []),
        "terrain":          derived_terrain if derived_terrain is not None else drawn_terrain,
        "terrain_drawn":    drawn_terrain,
        "terrain_agrees":   (derived_terrain == drawn_terrain) if derived_terrain is not None else None,
        "terrain_distance": distance,
        "terrain_hook":     hook,
        "window":           result["window"],
        "escalation_phase": result["escalation_phase"],
        "confidence":       result.get("confidence"),
        "rationale":        result.get("rationale"),
        "_model":           result.get("_model"),
        "_votes":           votes_record,
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
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/conflict_operator.py | parse() records _model beside _operator — which model produced the coordinate

# llm: claude-opus-5 | 2026-09-10 | repos/vivify-operators/conflict_operator.py | terrain is now DERIVED from a 0-1 position plus a hook flag: it is a position in the conflict distribution, and binning it as a 4-way categorical let canonical Cotton flip drifting 3/3 -> fringe 3/3 on identical text; drawn label kept as terrain_drawn/terrain_agrees

# llm: claude-opus-5 | 2026-09-10 | repos/vivify-operators/conflict_operator.py | vote PER COORDINATE not per whole block, matching logos_fused: each coordinate plus its dependent fields comes from one real draw, so one unstable field no longer decides the other four

# llm: claude-opus-5 | 2026-09-11 | repos/vivify-operators/conflict_operator.py | terrain votes on its DERIVED bin (it voted on the drawn label it had replaced); drawn spread kept as terrain_drawn, every draw position kept in by_dim.terrain.distances; derive_terrain docstring no longer claims derivation prevents flips
