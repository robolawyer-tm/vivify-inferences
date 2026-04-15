"""
right_pass — FABRIC digital analysis pass

Adds right_keywords (structural/process terms) to an inference and normalizes
left_keywords using a synonym map. Completes the dual-keyword extraction layer.
"""

import sys
import json
import fileinput
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import write_json, read_json


# Right keywords describe the pipeline's own structural operations.
# These are consistent across inferences — they describe the system, not the content.
RIGHT_KEYWORDS = [
    "json_indexing",
    "keyword_clumping",
    "cooccurrence_graph",
    "autovivification",
    "filesystem_path",
    "tension_calculation",
    "index_aggregation",
    "api_output",
    "inference_storage",
    "category_path_assignment"
]

SYNONYMS_FILE = Path(__file__).parent / "config" / "synonyms.json"


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


def apply_right_pass(inference, right_keywords=None):
    """Add right_keywords and normalize left_keywords on an inference dict.

    - right_keywords: list of digital/structural terms (defaults to RIGHT_KEYWORDS)
    - left_keywords are normalized via synonyms.json
    - Returns updated inference
    """
    synonyms = load_synonyms()
    inference = dict(inference)

    inference["left_keywords"] = normalize_keywords(
        inference.get("left_keywords", []), synonyms
    )

    if not inference.get("right_keywords"):
        inference["right_keywords"] = right_keywords or RIGHT_KEYWORDS

    if "clumps" in inference:
        normalized_clumps = {}
        for clump_name, kws in inference["clumps"].items():
            normalized_clumps[clump_name] = normalize_keywords(kws, synonyms)
        inference["clumps"] = normalized_clumps

    return inference


def process_inference_file(path):
    """Apply right pass to an inference file in place.

    - Reads, updates, and overwrites the file
    - Returns updated inference
    """
    inference = read_json(path)
    if not inference:
        print(f"Warning: could not read {path}")
        return None
    updated = apply_right_pass(inference)
    write_json(path, updated)
    return updated


def usage():
    print("Usage: right_pass.py < inference.json        apply to single inference via STDIN")
    print("       right_pass.py --all                   apply to all inferences in inferences/")
    print("       right_pass.py <path/to/inf_XXX.json>  apply to specific file")
    sys.exit(1)


def main():
    if "--all" in sys.argv:
        inferences_dir = Path("inferences")
        count = 0
        for path in inferences_dir.rglob("inf_*.json"):
            updated = process_inference_file(path)
            if updated:
                print(f"Updated: {path}  left_keywords: {len(updated['left_keywords'])}  right_keywords: {len(updated['right_keywords'])}")
                count += 1
        print(f"\nDone. {count} inferences updated.")
        return

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        path = Path(sys.argv[1])
        updated = process_inference_file(path)
        if updated:
            print(json.dumps(updated, indent=2))
        return

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        inference = json.loads(raw)
        updated = apply_right_pass(inference)
        print(json.dumps(updated, indent=2))
        return

    usage()


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/right_pass.py | created — right keyword extraction and left keyword synonym normalization
