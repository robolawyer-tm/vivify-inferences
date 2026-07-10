"""
promote.py — file categorized inferences out of the unclustered/ holding area

Moves each inference that categorize.py assigned a category to from
<dir>/unclustered/ into its category directory <dir>/<category_paths[0]>/, so the
corpus keeps its physical two-level domain/category layout on disk.

- Reads only <dir>/unclustered/inf_*.json — never disturbs already-filed inferences
- Destination is <dir>/<category_paths[0]>/<file> — the inference's top category path
- Unmatched inferences (empty category_paths) stay in unclustered/ as the holding pen
- Idempotent: a file already filed (absent from unclustered/) is simply skipped
- Pairs with categorize.py, which assigns category_paths but keeps storage flat
- Runs as a pipeline stage after categorize, before tension scoring
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from vivify_core import read_json, write_json

DEFAULT_DIR = "inferences"


def promote_all(inferences_dir=DEFAULT_DIR, dry_run=False):
    """Move categorized inferences from unclustered/ into their category directory.

    - Scans <inferences_dir>/unclustered/ for inf_*.json files
    - Files with category_paths -> <inferences_dir>/<category_paths[0]>/<name>
    - Files with no category_paths stay in unclustered/
    - Returns a summary dict: {"promoted": [{"id", "dest"}], "kept": [id]}
    """
    inferences_dir = Path(inferences_dir)
    unclustered = inferences_dir / "unclustered"
    summary = {"promoted": [], "kept": []}

    if not unclustered.is_dir():
        return summary

    for path in sorted(unclustered.glob("inf_*.json")):
        inference = read_json(path)
        if not inference:
            continue

        paths = inference.get("category_paths", [])
        if not paths:
            # No category matched — leave it in the holding pen
            summary["kept"].append(inference.get("id"))
            continue

        dest = inferences_dir / paths[0] / path.name
        if dest.resolve() == path.resolve():
            summary["kept"].append(inference.get("id"))
            continue

        if not dry_run:
            write_json(dest, inference)
            path.unlink()

        summary["promoted"].append({"id": inference.get("id"), "dest": str(dest)})

    return summary


def usage():
    print("Usage: promote.py [--dir <path>] [--dry-run]")
    print()
    print("File categorized inferences out of unclustered/ into their category dir.")
    print("Inferences with no category_paths stay in unclustered/.")
    print()
    print("  --dir <path>   Inferences directory (default: inferences)")
    print("  --dry-run      Show what would move without moving anything")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dir", default=DEFAULT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()

    if args.help:
        usage()
        sys.exit(0)

    summary = promote_all(inferences_dir=args.dir, dry_run=args.dry_run)

    verb = "Would promote" if args.dry_run else "Promoted"
    print(f"{verb}: {len(summary['promoted'])}")
    for item in summary["promoted"]:
        print(f"  {item['id']}  ->  {item['dest']}")
    print(f"Kept in unclustered: {len(summary['kept'])}")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-07-10 | repos/vivify-operators/promote.py | created — promote stage: files categorized inferences from unclustered/ into <dir>/<category_paths[0]>/, unmatched stay in unclustered
