"""
vivify — FABRIC component: raw inference text → autovivified JSON structure

Left-LLM semantic pass: extracts 8-12 keyword clumps from raw text using the
Claude API, then builds an autovivified inference unit and saves it to inferences/.

Accepts text from arguments, STDIN, or a file.
"""

import sys
import json
import fileinput
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from inference import new_inference, save_inference, update_inference
from vivify_core import write_json, read_json


KEYWORDS_PROMPT = """You are the left-semantic pass of a vivify pipeline.

Read the inference text below. Extract 8-12 keyword clumps that capture the
felt meaning — the semantic core — of the text.

Rules:
- Keywords must be concept-level tokens, not surface words
- Good: conflict_asymmetry, perjury_pattern, therapeutic_potential, emotional_truth
- Bad: lie, unfair, thing, happened
- Normalize: lowercase, underscores for spaces, strip punctuation
- Merge near-duplicates locally
- Never use external taxonomies — all grouping must emerge from this text only
- Group related keywords into named clumps (3-6 clumps, 2-4 keywords each)

Return ONLY valid JSON in this exact shape:
{
  "left_keywords": ["keyword_one", "keyword_two", ...],
  "clumps": {
    "clump_name": ["keyword_one", "keyword_two"],
    ...
  }
}

Inference text:
"""


def extract_keywords_via_api(raw_text):
    """Call the Claude API for the left-semantic keyword pass.

    - Uses claude-sonnet-4-6 for semantic extraction
    - Returns dict with left_keywords and clumps
    - Raises on API error or malformed response
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": KEYWORDS_PROMPT + raw_text}]
        )
        return json.loads(message.content[0].text)
    except ImportError:
        raise RuntimeError("anthropic package not installed — pip install anthropic")


def extract_keywords_manual(keywords_str, clumps_str=None):
    """Accept pre-extracted keywords as comma-separated string (no API required).

    - keywords_str: 'keyword_one,keyword_two,...'
    - clumps_str: optional JSON string of clumps dict
    - Useful for testing without API access
    """
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    clumps = json.loads(clumps_str) if clumps_str else {}
    return {"left_keywords": keywords, "clumps": clumps}


def vivify(raw_text, keywords=None, source="manual", inferences_dir="inferences"):
    """Run the full vivify pass on raw text.

    - Creates inference unit
    - Extracts keywords (API or manual)
    - Saves to inferences/unclustered/
    - Returns the saved inference and its path
    """
    inf = new_inference(raw_text, source=source)

    if keywords:
        inf = update_inference(inf, keywords)
    else:
        kw = extract_keywords_via_api(raw_text)
        inf = update_inference(inf, kw)

    path = save_inference(inf, inferences_dir=inferences_dir)
    return inf, path


def usage():
    print("Usage: vivify.py [options] 'inference text'")
    print("       echo 'inference text' | vivify.py")
    print("       vivify.py --keywords 'kw1,kw2,kw3' 'inference text'")
    print()
    print("Options:")
    print("  --keywords <csv>     Pre-extracted keywords (skips API call)")
    print("  --clumps <json>      Pre-extracted clumps as JSON string")
    print("  --source <name>      Source label (default: manual)")
    print("  --dir <path>         Inferences directory (default: inferences)")
    print("  -h, --help           Show this help")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("text", nargs="*")
    parser.add_argument("--keywords")
    parser.add_argument("--clumps")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--dir", default="inferences")
    parser.add_argument("-h", "--help", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.help:
        usage()

    # Read text from args or STDIN
    if not sys.stdin.isatty():
        raw_text = sys.stdin.read().strip()
    elif args.text:
        raw_text = " ".join(args.text)
    else:
        usage()

    if not raw_text:
        print("Error: no inference text provided.")
        usage()

    # Keyword source: manual or API
    keywords = None
    if args.keywords:
        keywords = extract_keywords_manual(args.keywords, args.clumps)

    inf, path = vivify(raw_text, keywords=keywords, source=args.source, inferences_dir=args.dir)

    print(f"Saved: {path}")
    print(json.dumps(inf, indent=2))


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/vivify.py | created — FABRIC vivify component, left-semantic pass via Claude API or manual keywords
