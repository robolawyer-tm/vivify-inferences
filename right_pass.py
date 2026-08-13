"""
right_pass — FABRIC digital analysis pass

Extracts the quantifiable, checkable facets of an inference's actual content —
the right/digital side — via an analytical LLM pass, replacing the former
static-keyword stub. Also normalizes left_keywords using the synonym map.

Spec origin: the round-trip loss test (experiments/round_trip/loss_report.md).
The blind decoder's residue — what coordinates and keywords could NOT recover —
was proper nouns, magnitudes, claimed-vs-actual statistics, time spans. Those
lost particulars are exactly what this pass captures:

- right_facts: named quantities grounded in verbatim quotes from the text
- discrepancies: claimed-vs-actual value pairs — the un-truth as a measurable
  deviation from baseline (the project's core reframe, 2026-07-13)
- right_keywords: derived fact names, so categorize/tension_score keep working

Fact names emerge from the content itself — no fixed vocabulary (non-negotiable:
no external taxonomies). Every fact must carry a quote that appears verbatim in
the source text; ungrounded facts are dropped (fail-closed on hallucination).
"""

import re
import sys
import json
import fileinput
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import (write_json, read_json, llm_call_model, resolve_model,
                         extract_json, LLMUnavailable)


# The former stub stamped these pipeline-vocabulary terms onto every inference.
# Recognized here so re-runs purge them from stores written before the real pass.
OLD_STUB_KEYWORDS = {
    "json_indexing",
    "keyword_clumping",
    "cooccurrence_graph",
    "autovivification",
    "filesystem_path",
    "tension_calculation",
    "index_aggregation",
    "api_output",
    "inference_storage",
    "category_path_assignment",
}

SYNONYMS_FILE = Path(__file__).parent / "config" / "synonyms.json"

FACTS_PROMPT = '''You are the digital/right-side extraction pass of an analysis pipeline. Extract the QUANTIFIABLE, COUNTABLE, CHECKABLE facets from the text below — the facts a database could hold and a fact-checker could verify.

Extract two things:

1. "right_facts" — every concrete quantity or countable fact present in the text: durations, counts, dates, statistics, measurements, physical descriptions, sentences, ages, sums of money.
   - Name each fact in snake_case; let names emerge from this content itself — never use a fixed vocabulary
   - "value": the quantity (a number where possible, otherwise a short string)
   - "unit": the unit or kind (years, count, probability, date, inches, usd, ...)
   - "quote": the shortest verbatim phrase from the text that contains the fact

2. "discrepancies" — every place the text contains BOTH a claimed/asserted value AND a contradicting actual/corrected value for the same thing. These claimed-vs-actual pairs are the most important output.
   - "topic": snake_case name for what the values describe
   - "claimed": the asserted value
   - "actual": the corrected/true value
   - "quote": the shortest verbatim phrase showing the correction or contradiction

Rules:
- Only facts actually present in the text — never infer, compute, or combine
- Quotes must be verbatim; they will be checked against the source and ungrounded facts discarded
- If the text contains no quantifiable facts, return empty structures

Return ONLY valid JSON in this exact shape:
{
  "right_facts": {
    "fact_name": {"value": 5, "unit": "years", "quote": "..."},
    ...
  },
  "discrepancies": [
    {"topic": "topic_name", "claimed": "...", "actual": "...", "quote": "..."},
    ...
  ]
}

Text:
"""
'''


def load_synonyms():
    """Load the synonym map from config/synonyms.json.

    - Returns a flat dict mapping variant → canonical
    - Returns empty dict if file missing
    """
    data = read_json(SYNONYMS_FILE)
    return data.get("synonyms", {})


def normalize_keywords(keywords, synonyms):
    """Replace keyword variants with their canonical forms.

    - Deduplicates after normalization
    - Preserves order of first occurrence
    - Unknown keywords pass through unchanged
    """
    seen = set()
    result = []
    for kw in keywords:
        canonical = synonyms.get(kw, kw)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _snake(name):
    """Coerce a fact name to snake_case: lowercase, non-alphanumerics collapse to _."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def _grounded(quote, raw_text):
    """True if quote appears verbatim in raw_text (case- and whitespace-insensitive)."""
    if not quote:
        return False
    flat = lambda s: " ".join(str(s).lower().split())
    return flat(quote) in flat(raw_text)


def extract_facts(raw_text, sensitive=False, config_dir="config"):
    """Run the analytical LLM pass and return grounded right_facts + discrepancies.

    - Model resolved from config/model_map.json via 'fact_extraction' capability
      (or VIVIFY_MODEL_OVERRIDE), and returned as the third element: discrepancies
      feed CONFIRMED tension, the ground truth the whole calibration gradient is
      measured against, so which model read the text is not a footnote here
    - Facts whose quote is not found verbatim in raw_text are DROPPED with a
      warning — the grounding gate against hallucinated particulars
    - Raises LLMUnavailable / json.JSONDecodeError upward; callers decide
      fail-soft (bulk) vs fail-fast (single file)
    - Returns (facts, discrepancies, model)
    """
    model = resolve_model("fact_extraction", config_dir)
    raw = llm_call_model(FACTS_PROMPT + raw_text + '\n"""', model, None,
                         sensitive=sensitive)
    data = extract_json(raw)

    facts = {}
    for name, fact in (data.get("right_facts") or {}).items():
        if not isinstance(fact, dict):
            continue
        if not _grounded(fact.get("quote"), raw_text):
            print(f"  dropped ungrounded fact: {name}", file=sys.stderr)
            continue
        facts[_snake(name)] = {
            "value": fact.get("value"),
            "unit": fact.get("unit"),
            "quote": fact.get("quote"),
        }

    discrepancies = []
    for d in (data.get("discrepancies") or []):
        if not isinstance(d, dict):
            continue
        if not _grounded(d.get("quote"), raw_text):
            print(f"  dropped ungrounded discrepancy: {d.get('topic')}", file=sys.stderr)
            continue
        discrepancies.append({
            "topic": _snake(d.get("topic", "unnamed")),
            "claimed": d.get("claimed"),
            "actual": d.get("actual"),
            "quote": d.get("quote"),
        })

    return facts, discrepancies, model


def derive_right_keywords(facts, discrepancies):
    """Build right_keywords from extracted content: fact names + <topic>_discrepancy.

    - Derived, never free-standing — keeps categorize/tension_score consuming
      content-based terms without schema changes
    """
    keywords = list(facts.keys())
    for d in discrepancies:
        kw = f"{d['topic']}_discrepancy"
        if kw not in keywords:
            keywords.append(kw)
    return keywords


def apply_right_pass(inference, sensitive=False, force=False, config_dir="config"):
    """Extract right_facts/discrepancies from content and normalize left_keywords.

    - Skips extraction if right_facts already present (idempotent — no double
      spend on model calls) unless force=True
    - Old stub right_keywords are purged unconditionally
    - No raw_text → left normalization only, right side left empty
    - Returns updated inference; raises LLMUnavailable/JSONDecodeError on
      extraction failure (callers choose fail-soft or fail-fast)
    """
    synonyms = load_synonyms()
    inference = dict(inference)

    inference["left_keywords"] = normalize_keywords(
        inference.get("left_keywords", []), synonyms
    )
    if "clumps" in inference:
        inference["clumps"] = {
            name: normalize_keywords(kws, synonyms)
            for name, kws in inference["clumps"].items()
        }

    # purge stub-era keywords regardless of what else happens
    existing_right = [kw for kw in inference.get("right_keywords", [])
                      if kw not in OLD_STUB_KEYWORDS]
    inference["right_keywords"] = existing_right

    if inference.get("right_facts") and not force:
        return inference

    raw_text = inference.get("raw_text", "")
    if not raw_text.strip():
        print(f"  no raw_text on {inference.get('id', '?')} — right side left empty",
              file=sys.stderr)
        return inference

    facts, discrepancies, model = extract_facts(raw_text, sensitive=sensitive,
                                                config_dir=config_dir)
    inference["right_facts"] = facts
    inference["discrepancies"] = discrepancies
    inference["right_keywords"] = derive_right_keywords(facts, discrepancies)
    inference["right_pass"] = {"_model": model, "_operator": "right_pass.py"}
    return inference


def process_inference_file(path, sensitive=False, force=False):
    """Apply right pass to an inference file in place.

    - Reads, updates, and overwrites the file
    - Returns updated inference, or None on read/extraction failure (fail-soft)
    """
    inference = read_json(path)
    if not inference:
        print(f"Warning: could not read {path}")
        return None
    try:
        updated = apply_right_pass(inference, sensitive=sensitive, force=force)
    except (LLMUnavailable, json.JSONDecodeError) as e:
        print(f"Warning: extraction failed for {path}: {e}")
        return None
    write_json(path, updated)
    return updated


def usage():
    print("Usage: right_pass.py < inference.json        apply to single inference via STDIN")
    print("       right_pass.py --all                   apply to all inferences in inferences/")
    print("       right_pass.py <path/to/inf_XXX.json>  apply to specific file")
    print()
    print("Options:")
    print("  --force        re-extract even if right_facts already present")
    print("  --sensitive    tag content as private field data (privacy gate applies)")
    sys.exit(1)


def main():
    force = "--force" in sys.argv
    sensitive = "--sensitive" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if "--all" in sys.argv:
        inferences_dir = Path("inferences")
        count = 0
        for path in inferences_dir.rglob("inf_*.json"):
            updated = process_inference_file(path, sensitive=sensitive, force=force)
            if updated:
                print(f"Updated: {path}  facts: {len(updated.get('right_facts', {}))}  "
                      f"discrepancies: {len(updated.get('discrepancies', []))}  "
                      f"right_keywords: {len(updated['right_keywords'])}")
                count += 1
        print(f"\nDone. {count} inferences updated.")
        return

    if args:
        path = Path(args[0])
        updated = process_inference_file(path, sensitive=sensitive, force=force)
        if updated:
            print(json.dumps(updated, indent=2))
        else:
            sys.exit(1)
        return

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        inference = json.loads(raw)
        updated = apply_right_pass(inference, sensitive=sensitive, force=force)
        print(json.dumps(updated, indent=2))
        return

    usage()


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/right_pass.py | created — right keyword extraction and left keyword synonym normalization
# llm: claude-fable-5 | 2026-07-13 | repos/vivify-operators/right_pass.py | replaced static-keyword stub with real content extraction: right_facts + claimed-vs-actual discrepancies via llm_call(fact_extraction), quote-grounding gate, stub purge; spec from experiments/round_trip loss test residue
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/right_pass.py | extract_facts returns the model it used; apply_right_pass records inference["right_pass"]._model — provenance for the confirmed-tension ground-truth channel
