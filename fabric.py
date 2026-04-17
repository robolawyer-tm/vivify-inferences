"""
fabric.py — full FABRIC pipeline runner

Chains all four passes on a single inference text input.

Passes:
  1. vivify      — left semantic pass (Claude API -> keywords + clumps)
  2. right_pass  — right structural pass (normalize + attach pipeline keywords)
  3. categorize  — assign category_paths from co-occurrence graph across corpus
  4. tension     — score left/right divergence

Usage:
  python3 fabric.py 'inference text'
  echo 'inference text' | python3 fabric.py
  python3 fabric.py --source <name> 'inference text'
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from vivify_core import read_json, write_json

from vivify import vivify
from right_pass import apply_right_pass
from categorize import categorize_all
from tension_score import score_inference


def run(raw_text, source="manual", inferences_dir="inferences"):
    inferences_dir = str(inferences_dir)

    # Pass 1: left semantic keywords via Claude API
    inf, path = vivify(raw_text, source=source, inferences_dir=inferences_dir)
    print(f"[1] vivify      -> {path}")

    # Pass 2: right structural keywords + synonym normalization
    inf = apply_right_pass(inf)
    write_json(path, inf)
    print(f"[2] right_pass  -> left:{len(inf['left_keywords'])}  right:{len(inf['right_keywords'])}")

    # Pass 3: assign category paths from co-occurrence graph across corpus
    summary, tree = categorize_all(inferences_dir=inferences_dir)
    categorized = [c for c in summary["categorized"] if c["id"] == inf["id"]]
    if categorized:
        print(f"[3] categorize  -> {categorized[0]['paths']}")
    else:
        print(f"[3] categorize  -> unclustered (corpus too small to seed)")

    # Reload after categorize — file may have moved to a category subdir
    for p in Path(inferences_dir).rglob(f"{inf['id']}.json"):
        path = p
        break

    # Pass 4: tension score
    inf = read_json(path)
    inf = score_inference(inf)
    write_json(path, inf)
    print(f"[4] tension     -> {inf['tension_score']:.4f}")

    print()
    print(json.dumps(inf, indent=2))
    return inf


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("text", nargs="*")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--dir", default="inferences")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()

    if args.help:
        print(__doc__)
        sys.exit(0)

    if not sys.stdin.isatty():
        raw_text = sys.stdin.read().strip()
    elif args.text:
        raw_text = " ".join(args.text)
    else:
        print(__doc__)
        sys.exit(1)

    if not raw_text:
        print("Error: no inference text provided.")
        sys.exit(1)

    run(raw_text, source=args.source, inferences_dir=args.dir)


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-17 | repos/vivify-inferences/fabric.py | created — full FABRIC pipeline runner, chains vivify/right_pass/categorize/tension_score
