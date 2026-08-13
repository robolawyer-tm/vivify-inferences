#!/usr/bin/env python3
"""
logos_fused.py — all 8 independent logos operators in ONE LLM call.

The per-operator path (logos_operator.py) makes 8 separate `claude -p` calls per
inference, each re-sending the full raw_text — 8x the document through the plan's
rate limit. The 8 logos dimensions are independent (they only read raw_text), so
they can be classified in a single request. This collapses 8 calls -> 1 (and the
raw_text is sent once), ~8x more inferences per rate window, entirely in-plan.
`conflict` is NOT fused: it reads the logos outputs, so it stays a second call.

Source-of-truth discipline (no silent drift):
  - the allowed enum VALUES are injected from config/coordinates.json at import,
    not hand-copied — the same spec validate_coordinates() enforces;
  - each dimension's result -> logos[dim] MAPPING is reused from the operator's own
    parse() (incl. structural's scale coercion) — never re-implemented here.
So this module owns only the fused prompt and the single-call/validate/retry loop;
the operators remain authoritative for both vocabulary and mapping.

Schema: pillars/logos/logos_schema_v01.json
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import (read_json, write_json, llm_call_model, resolve_model,
                         extract_json, validate_coordinates,
                         CoordinateValidationError, LLMUnavailable)

import act_type_operator
import cooperative_operator
import transmission_operator
import resonance_operator
import authority_operator
import utility_operator
import social_field_operator
import structural_operator

CONFIG = str(Path(__file__).parent / "config")

# (dimension key in the fused JSON, operator module that owns its parse()).
# Order mirrors logos_operator.py minus narrative; conflict is a separate pass.
LOGOS_DIMS = [
    ("act_type",     act_type_operator),
    ("cooperative",  cooperative_operator),
    ("transmission", transmission_operator),
    ("resonance",    resonance_operator),
    ("authority",    authority_operator),
    ("utility",      utility_operator),
    ("social_field", social_field_operator),
    ("structural",   structural_operator),
]

_SPEC = read_json(Path(CONFIG) / "coordinates.json").get("operators", {})


def _vals(op, field):
    """Allowed enum values for op.field as 'a|b|c', read from coordinates.json so
    the fused prompt can never list a value the validation gate would reject."""
    return "|".join(_SPEC[op]["enums"][field])


def _required_fields(op):
    """The coordinate fields a dimension block MUST carry for its parse() to map it:
    every enum field plus every float except the optional confidence. A block missing
    one is treated as invalid (triggers a retry) rather than crashing parse() later."""
    enums = list(_SPEC.get(op, {}).get("enums", {}))
    floats = [f for f in _SPEC.get(op, {}).get("floats", {}) if f != "confidence"]
    return enums + floats


# Concise glosses (definitions stay inline — they carry the classification quality);
# the value lists come from coordinates.json via _vals so they cannot drift.
PROMPT_TEMPLATE = f"""You are tagging one communication act on EIGHT independent logos dimensions
at once. Read the text, then return ONE JSON object with a block per dimension.
Judge each dimension on its own terms; do not let one dimension's answer bias another.

1. act_type ({_vals('act_type','act_type')}) — Austin/Searle speech act.
   assertive=claims truth; directive=gets someone to act; commissive=commits speaker;
   expressive=expresses a state; declaration=changes reality by being said (needs
   institutional authority — if absent, use the underlying type and set authority_mismatch).

2. cooperative — Grice's Cooperative Principle. The four maxims: quantity (say enough,
   not too much), quality (say what you believe true), relation (be relevant), manner
   (be clear and orderly). status ({_vals('cooperative','status')}): honored=all upheld;
   violated=a maxim breached — set maxim_violated to the primary one
   ({_vals('cooperative','maxim_violated')}); suspended=cooperative frame off (irony,
   ritual, fiction). Misleading, evasive, or false-claiming text is VIOLATED, not honored.

3. transmission ({_vals('transmission','transmission')}) — how it moves.
   broadcast=one-to-many public; leak=restricted, charged, unofficial; archive=preserved,
   institutional, past-to-future.

4. resonance ({_vals('resonance','resonance')}) — affective field.
   harmony=alignment; friction=dissonance; illusion=surface harmony masking friction
   (most significant for conflict). underlying = what it masks, or null.

5. authority ({_vals('authority','authority')}) — trust source.
   sovereign=institutional/formal/legal; tribal=peer/communal/normative; occult=real but
   unacknowledged in the official record (not supernatural).

6. utility ({_vals('utility','utility')}) — functional payload (primary).
   instruction=enables action; narrative=makes meaning; currency=tracks social
   standing/obligation. secondary = same set or null.

7. social_field — Douglas grid/group, each 0.0-1.0.
   grid=constraint by explicit rules/roles; group=identity defined by membership.
   quadrant ({_vals('social_field','quadrant')}). Score the field the act occurs in,
   not its content.

8. structural — locate the act in social space. Pick the primary layer/scale
   ({"|".join(structural_operator.VALID_SCALES)}) and set scale = layer:
     self=internal/private/momentary; dyad=two people, direct, relational;
     small_group=~15 people, shared norms, informal; local_network=~150, customary,
     elder-led; institution=formal, bureaucratic, rule-governed, persistent;
     global=archival, durable, codified formal authority.
   The other axes FOLLOW from the layer — use the standard value for that layer unless
   the text clearly deviates: density ({_vals('structural','density')});
   persistence ({_vals('structural','persistence')}); authority ({_vals('structural','authority')});
   transmission ({_vals('structural','transmission')}); memory_channel ({_vals('structural','memory_channel')});
   language_mode ({_vals('structural','language_mode')}).
   overlays = any of [family, culture, religion, society] that apply, or [].

Text:
<<TEXT>>

Context (if available): <<CONTEXT>>

Return ONLY valid JSON, exactly these keys (confidence is 0.0-1.0 per block):
{{
  "act_type":     {{"act_type": "", "authority_mismatch": false, "rationale": "", "confidence": 0.0}},
  "cooperative":  {{"status": "", "maxim_violated": null, "implicature": null, "confidence": 0.0}},
  "transmission": {{"transmission": "", "rationale": "", "confidence": 0.0}},
  "resonance":    {{"resonance": "", "surface": "", "underlying": null, "confidence": 0.0}},
  "authority":    {{"authority": "", "source": "", "rationale": "", "confidence": 0.0}},
  "utility":      {{"utility": "", "secondary": null, "rationale": "", "confidence": 0.0}},
  "social_field": {{"grid": 0.0, "group": 0.0, "quadrant": "", "rationale": "", "confidence": 0.0}},
  "structural":   {{"layer": "", "scale": "", "density": "", "persistence": "", "authority": "",
                   "transmission": "", "memory_channel": "", "language_mode": "", "overlays": [], "confidence": 0.0}}
}}
"""


def _validate_fused(result):
    """Validate every dimension block in a fused result against coordinates.json,
    and require the fields each parse() needs. Raises CoordinateValidationError on
    the first problem so the caller can retry."""
    for key, _mod in LOGOS_DIMS:
        block = result.get(key)
        if not isinstance(block, dict):
            raise CoordinateValidationError(f"fused: missing or non-object block for {key!r}")
        validate_coordinates(block, key, CONFIG)
        missing = [f for f in _required_fields(key) if f not in block]
        if missing:
            raise CoordinateValidationError(f"fused: {key} block missing fields {missing}")
    return result


def _fused_call(prompt, retries=2):
    """One LLM call returning all 8 dimensions, retried on invalid/malformed output
    (same recovery contract as call_and_validate, but across the whole fused block).
    LLMUnavailable is NOT caught here — transport-down stays fatal/fail-fast.

    Each per-dimension block is stamped with `_model` before it reaches the
    operators' parse(), mirroring call_and_validate on the per-operator path — the
    fused path is the one the field runs actually use, so it must not be the path
    that loses provenance."""
    model = resolve_model("logos_operator")
    last_err = None
    for attempt in range(retries + 1):
        params = {"temperature": round(0.3 * attempt, 2)} if attempt > 0 else None
        raw = llm_call_model(prompt, model, params, sensitive=True)
        try:
            result = _validate_fused(extract_json(raw))
            for key, _mod in LOGOS_DIMS:
                result[key]["_model"] = model
            return result
        except (CoordinateValidationError, json.JSONDecodeError) as e:
            last_err = e
    raise last_err


def run(inference: dict, retries=2) -> dict:
    """Attach all 8 logos dimensions to an inference in a single LLM call.

    Drop-in for running the 8 logos operators via logos_operator.py, but 1 call
    instead of 8. Reuses each operator's parse() for the mapping, so the output is
    byte-identical in shape to the per-operator path (conflict + cross_scale read it
    unchanged). Raises LLMUnavailable (fail-fast) or CoordinateValidationError
    (after retries) — caller quarantines, exactly like the per-operator path.
    """
    text = inference.get("raw_text", "")
    if not text:
        return inference

    prompt = PROMPT_TEMPLATE.replace("<<TEXT>>", text).replace(
        "<<CONTEXT>>", str(inference.get("context", "none")))
    result = _fused_call(prompt, retries=retries)

    for key, module in LOGOS_DIMS:
        module.parse(result[key], inference)

    logos = inference.setdefault("logos", {})
    logos["_runner"] = "logos_fused.py"
    # A successful fused pass authoritatively re-wrote all 8 dimensions, so any error
    # recorded against them by an earlier (per-operator) run is now obsolete — drop it,
    # otherwise the stale marker wedges logos_complete() forever. Clear the _errors map
    # if nothing un-fused (e.g. a retired narrative dim) is left.
    errs = logos.get("_errors")
    if errs:
        for key, _mod in LOGOS_DIMS:
            errs.pop(key, None)
        if not errs:
            logos.pop("_errors", None)
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with all 8 logos dimensions in one LLM call"
    )
    parser.add_argument("file", nargs="?", help="inference JSON file to tag")
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
        s = tagged.get("logos", {})
        dims = [k for k, _ in LOGOS_DIMS if k in s]
        print(f"logos (fused): {len(dims)}/8 dimensions tagged")

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/logos_fused.py | created — fused logos pass: all 8 independent logos dimensions in ONE claude -p call (8->1, raw_text sent once) for in-plan throughput; enums injected from coordinates.json, mapping reused from each operator's parse(), one-call validate+retry loop; conflict stays a separate pass
# llm: claude-opus-4-8 | 2026-06-29 | repos/vivify-operators/logos_fused.py | run() now clears stale per-dimension _errors for the 8 dims it re-tags on a successful pass (prevents an old per-operator error from wedging logos_complete forever)
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/logos_fused.py | fused path stamps _model on all 8 blocks before parse() (the per-operator path got it from call_and_validate; the fused path is what field runs use)
