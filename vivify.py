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
from vivify_core import write_json, read_json, resolve_model


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
"""


def established_vocabulary(inferences_dir="inferences", min_count=2, cap=150):
    """Keywords already used by 2+ inferences in this store — the emerged vocabulary.

    - Read from the store's own index.json; NOT an external taxonomy (it emerged
      from prior extractions here), so anchoring on it honors the non-negotiable
    - Sorted most-established first, capped to keep the prompt lean
    - Empty list when the index is missing — anchoring degrades to nothing
    """
    index = read_json(Path(inferences_dir) / "index.json")
    if not index:
        return []
    kws = [(k, n) for k, n in index.get("keywords", {}).items() if n >= min_count]
    kws.sort(key=lambda x: -x[1])
    return [k for k, _ in kws[:cap]]


def anchored_prompt(raw_text, vocab):
    """Assemble the extraction prompt, anchoring on the store's emerged vocabulary.

    - Reuse-if-apt, mint-if-needed: fixes vocabulary divergence at the source
      without imposing a taxonomy (the terms emerged from this store's own data)
    """
    anchor = ""
    if vocab:
        anchor = (
            "\nVocabulary that has already emerged from prior inferences in this "
            "store (not an external taxonomy). Reuse a term ONLY when it names the "
            "same concept in this text; otherwise mint a new keyword as usual:\n"
            + ", ".join(vocab) + "\n"
        )
    return KEYWORDS_PROMPT + anchor + "\nInference text:\n" + raw_text


def extract_keywords_via_api(raw_text, vocab=None):
    """Call the Claude API for the left-semantic keyword pass.

    - Model resolved from config/model_map.json via 'semantic_extraction' capability
    - vocab: emerged corpus keywords to anchor on (reuse-if-apt, mint-if-needed)
    - Returns dict with left_keywords and clumps
    - Raises on API error or malformed response
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=resolve_model("semantic_extraction"),
            max_tokens=1024,
            messages=[{"role": "user", "content": anchored_prompt(raw_text, vocab or [])}]
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
        vocab = established_vocabulary(inferences_dir)
        kw = extract_keywords_via_api(raw_text, vocab=vocab)
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
# llm: claude-sonnet-4-6 | 2026-04-27 | repos/vivify-inferences/vivify.py | replaced hardcoded model string with resolve_model("semantic_extraction")
# llm: claude-fable-5 | 2026-07-14 | repos/vivify-operators/vivify.py | vocabulary anchoring: established_vocabulary() from index.json (count>=2, cap 150) injected into extraction prompt as reuse-if-apt/mint-if-needed
