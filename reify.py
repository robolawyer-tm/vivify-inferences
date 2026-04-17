"""
reify — FABRIC inverse pass: JSON inference → regenerated text

The vivify pipeline moves from language to structure: raw text enters, keywords
and clumps emerge, the inference is filed into a category tree, and a tension score
measures how far the felt meaning has drifted from its structural capture. reify
runs that process in reverse. It takes a stored inference — already compressed into
left_keywords, clumps, category_paths, and tension_score — and asks the Claude API
to reconstruct the analog original: the felt thought the structure was built from.

This is not summarization or paraphrase. The model is instructed to speak from
inside the meaning, not about it. The tension_score shapes the output — a score of
1.0 means left and right keyword sets share nothing, so the felt meaning completely
resists its structural capture; the reconstruction leans into that gap rather than
smoothing it over.

Three modes:

  single
    Reconstructs prose from one inference. The model receives left_keywords, clumps,
    and a slice of category_paths, plus the tension score. Output is 3-6 dense
    sentences in first person. Use this to test whether vivify actually captured
    what was meant — if the reconstruction feels foreign, the keywords drifted.

  synthesize
    Takes two inference files and generates a single passage that holds both
    simultaneously. Not alternating, not summarizing — finding the place where they
    are the same thought. If the two inferences pull in different directions the
    model writes from that tension. Use this to discover connections the corpus
    has not yet made explicit.

  voice
    Walks an entire category directory and generates a passage that speaks for the
    whole category — a distillation of what all its inferences are reaching toward
    together. This is the most generative mode: the emergent category tree, built
    by co-occurrence across the full corpus, becomes the source material for new
    prose that could not have come from any single inference.

Options:
  --dry-run    Print the full prompt without calling the API. No billing. Use this
               to inspect what the model will receive before committing to a call.
  --dir        Inferences directory (default: inferences). Used with --voice.

Usage:
  python3 reify.py <path/to/inf_XXX.json>
  python3 reify.py --synthesize <path/to/inf_A.json> <path/to/inf_B.json>
  python3 reify.py --voice <category/path>
  python3 reify.py --dry-run <path/to/inf_XXX.json>
  python3 reify.py --dir <inferences_dir> --voice <category/path>
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json


REIFY_PROMPT = """You are the inverse pass of a vivify pipeline.

You will receive a structured inference: left_keywords (felt semantic meaning),
clumps (grouped keyword clusters), category_paths (emergent filing), and
tension_score (how far left and right keyword sets diverge).

Your task is to reconstruct the felt thought — the analog original — from this
structure. Do not explain the keywords. Do not describe what the pipeline did.
Speak from inside the meaning, not about it.

Rules:
- Write in first person, direct voice
- Do not mention keywords by name — let them shape the prose, not appear in it
- Do not reference the pipeline, categories, or JSON
- The tension_score tells you how much left and right diverge: high tension means
  the felt meaning resists its own structural capture — lean into that gap
- Length: 3-6 sentences. Dense. No hedging.

Inference:
"""

SYNTHESIZE_PROMPT = """You are the synthesis pass of a vivify pipeline.

You will receive two structured inferences. Each has left_keywords capturing its
felt meaning and clumps grouping those keywords. Your task is to generate a single
passage of prose that holds both inferences simultaneously — not alternating between
them, not summarizing them, but finding the place where they are the same thought.

Rules:
- Write in first person, direct voice
- Do not mention keywords by name
- Do not reference the pipeline, categories, or JSON
- If the two inferences pull in different directions, find the tension and write from it
- Length: 4-8 sentences. The synthesis should feel inevitable, not constructed.

Inference A:
{inf_a}

Inference B:
{inf_b}
"""

VOICE_PROMPT = """You are the category voice pass of a vivify pipeline.

You will receive a set of inferences that share a category. Each has left_keywords
capturing its felt meaning. Your task is to generate a single passage of prose that
speaks for the whole category — a distillation of what all these inferences are
reaching toward together.

Rules:
- Write in first person, direct voice
- Do not mention keywords by name
- Do not reference the pipeline, categories, or JSON
- This is not a summary — it is a synthesis. Find the irreducible core.
- Length: 4-8 sentences.

Category: {category}

Inferences:
{inferences}
"""


def call_api(prompt, dry_run=False):
    if dry_run:
        print("[dry-run] prompt:\n")
        print(prompt)
        sys.exit(0)
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except ImportError:
        raise RuntimeError("anthropic package not installed — pip install anthropic")


def reify_single(inference, dry_run=False):
    """Reconstruct prose from a single inference's structure."""
    payload = {
        "left_keywords": inference.get("left_keywords", []),
        "clumps": inference.get("clumps", {}),
        "category_paths": inference.get("category_paths", [])[:4],
        "tension_score": inference.get("tension_score")
    }
    prompt = REIFY_PROMPT + json.dumps(payload, indent=2)
    return call_api(prompt, dry_run=dry_run)


def reify_synthesize(inf_a, inf_b, dry_run=False):
    """Generate text holding two inferences simultaneously."""
    def slim(inf):
        return {
            "left_keywords": inf.get("left_keywords", []),
            "clumps": inf.get("clumps", {}),
            "tension_score": inf.get("tension_score")
        }
    prompt = SYNTHESIZE_PROMPT.format(
        inf_a=json.dumps(slim(inf_a), indent=2),
        inf_b=json.dumps(slim(inf_b), indent=2)
    )
    return call_api(prompt, dry_run=dry_run)


def reify_voice(category, inferences_dir="inferences", dry_run=False):
    """Generate text that speaks for an entire category directory."""
    category_path = Path(inferences_dir) / category
    if not category_path.exists():
        raise FileNotFoundError(f"Category path not found: {category_path}")

    inferences = []
    for path in category_path.rglob("inf_*.json"):
        inf = read_json(path)
        if inf:
            inferences.append({
                "id": inf["id"],
                "left_keywords": inf.get("left_keywords", []),
                "clumps": inf.get("clumps", {}),
                "tension_score": inf.get("tension_score")
            })

    if not inferences:
        raise ValueError(f"No inferences found in {category_path}")

    prompt = VOICE_PROMPT.format(
        category=category,
        inferences=json.dumps(inferences, indent=2)
    )
    return call_api(prompt, dry_run=dry_run)


def usage():
    print(__doc__)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument("--voice", metavar="CATEGORY")
    parser.add_argument("--dir", default="inferences")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()

    if args.help:
        usage()

    dry_run = args.dry_run

    if args.voice:
        text = reify_voice(args.voice, inferences_dir=args.dir, dry_run=dry_run)
        print(f"[voice: {args.voice}]\n")
        print(text)
        return

    if args.synthesize:
        if len(args.paths) != 2:
            print("Error: --synthesize requires exactly two inference paths.")
            usage()
        inf_a = read_json(args.paths[0])
        inf_b = read_json(args.paths[1])
        if not inf_a or not inf_b:
            print("Error: could not read one or both inference files.")
            sys.exit(1)
        text = reify_synthesize(inf_a, inf_b, dry_run=dry_run)
        print(f"[synthesis: {inf_a['id']} + {inf_b['id']}]\n")
        print(text)
        return

    if len(args.paths) == 1:
        inf = read_json(args.paths[0])
        if not inf:
            print(f"Error: could not read {args.paths[0]}")
            sys.exit(1)
        text = reify_single(inf, dry_run=dry_run)
        print(f"[reify: {inf['id']}  tension: {inf.get('tension_score', 'unscored')}]\n")
        print(text)
        return

    usage()


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-17 | repos/vivify-inferences/reify.py | created — inverse pass, JSON inference → prose via Claude API; single/synthesize/voice modes
