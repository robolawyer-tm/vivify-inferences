#!/usr/bin/env python3
"""
structural_operator.py — logos tagging pass: structural social-space coordinates

Locates a communication act in social space using the structural layer model
from logos_combined_v01.json. Assigns the primary layer and all 7 axis values.
Also identifies cross-cutting overlays (family, culture, religion, society).

Schema: pillars/logos/logos_combined_v01.json#structural
_src: Dunbar, Tönnies, Ostrom, Douglas, Machin, Benedict
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, call_and_validate

# The canonical scale axis (logos_combined_v01.json#structural). scale == layer by
# design. Smaller models sometimes leak a value from another axis (e.g. the density
# value "bureaucratic") into scale; we coerce against this set rather than trust it.
VALID_SCALES = ["self", "dyad", "small_group", "local_network", "institution", "global"]

PROMPT = """You are locating a communication act in social space.

The structural layer model has six named positions on a scale from self to global:

  self         — internal, private, momentary; language points to immediate experience
  dyad         — two people, direct, relational; language builds connection
  small_group  — up to ~15 people, shared norms, informal; language enforces belonging
  local_network — up to ~150 people, customary, elder-led; language carries symbolic meaning
  institution  — formal, bureaucratic, rule-governed, persistent; language is contractual
  global       — archival, durable, formal authority; language is codified

Cross-cutting overlays (can span multiple layers):
  family    — spans self/dyad/small_group; features: kin relation, reciprocity, shared memory
  culture   — spans local_network/institution/global; features: symbolic stability, norm reproduction
  religion  — spans small_group through global; features: shared cosmology, ritual, nonlocal authority
  society   — spans local_network/institution/global; features: role systems, rule systems, mass transmission

Text:
{raw_text}

Context (if available): {context}

Assign the primary layer and any overlays that apply. The 7 axis values follow from the layer
(use the standard values for that layer unless something in the text clearly deviates).

Return ONLY valid JSON:
{{
  "layer": "<self|dyad|small_group|local_network|institution|global>",
  "scale": "<same as layer>",
  "density": "<embodied|proximal|shared|distributed|bureaucratic|archival>",
  "persistence": "<momentary|short_term|routine|customary|institutional|durable>",
  "authority": "<self|pair|group|elders|system|formal>",
  "transmission": "<direct|leak|ritual|broadcast|archive|code>",
  "memory_channel": "<episodic|shared|semantic|procedural|institutional|global>",
  "language_mode": "<indexical|relational|normative|symbolic|contractual|formalized>",
  "overlays": ["<overlay names that apply, or empty list>"],
  "confidence": <0.0-1.0>
}}
"""


def run(inference: dict) -> dict:
    """Attach logos.structural coordinates to an inference."""
    text = inference.get("raw_text", "")
    if not text:
        return inference

    result = call_and_validate(
        PROMPT.format(
            raw_text=text,
            context=inference.get("context", "none"),
        ),
        "structural",
        capability="logos_operator",
        sensitive=True,
    )
    return parse(result, inference)


def parse(result: dict, inference: dict) -> dict:
    """Map a validated structural result into inference['logos']['structural'],
    including the scale/layer coercion against VALID_SCALES.

    Split out from run() so the fused logos pass (logos_fused.py) can reuse this
    mapping — coercion and all — with a pre-fetched sub-result, no LLM re-call."""
    # Coerce scale/layer to the valid enum: prefer scale, fall back to layer, else
    # null (cross_scale skips null-scale inferences rather than grouping on garbage).
    raw_scale, raw_layer = result.get("scale"), result.get("layer")
    canonical = raw_scale if raw_scale in VALID_SCALES else (raw_layer if raw_layer in VALID_SCALES else None)
    coerced = {"raw_scale": raw_scale, "raw_layer": raw_layer} if canonical not in (raw_scale, raw_layer) or raw_scale != raw_layer else None

    logos = inference.setdefault("logos", {})
    logos["structural"] = {
        "layer":          canonical,
        "scale":          canonical,
        "_coerced":       coerced,
        "density":        result["density"],
        "persistence":    result["persistence"],
        "authority":      result["authority"],
        "transmission":   result["transmission"],
        "memory_channel": result["memory_channel"],
        "language_mode":  result["language_mode"],
        "overlays":       result.get("overlays", []),
        "confidence":     result.get("confidence"),
        "_model":         result.get("_model"),
        "_src":           ["Dunbar", "Tonnies", "Ostrom", "Douglas"],
        "_operator":      "structural_operator.py",
    }
    return inference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tag an inference with structural social-space coordinates"
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
        s = tagged["logos"]["structural"]
        overlays = f" overlays={s['overlays']}" if s["overlays"] else ""
        print(f"logos.structural: layer={s['layer']}{overlays}")
# llm: claude-sonnet-4-6 | 2026-05-23 | repos/vivify-operators/structural_operator.py | created — structural social-space coordinate operator using logos_combined_v01 layer model
# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/structural_operator.py | validate scale against VALID_SCALES enum — coerce to layer or null, record _coerced; stops small-model density-value leaks (e.g. "bureaucratic")
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/structural_operator.py | wired inbound validation gate: validate_coordinates() gates the six non-scale fields; scale/layer keep their own coercion
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/structural_operator.py | wired sensitive=True into llm_call so the privacy gate protects field data
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/structural_operator.py | retry-on-invalid: run() uses call_and_validate() so a recoverable small-model miss is re-asked, not dropped as a missing dimension
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/structural_operator.py | split result->logos mapping into parse() so logos_fused.py reuses it without re-calling the LLM (run = call_and_validate + parse); behavior unchanged
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/structural_operator.py | parse() records _model beside _operator — which model produced the coordinate
