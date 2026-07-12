"""
refile.py — move already-filed inferences whose category_paths have changed

The complement of promote.py: promote moves unclustered/ -> filed; refile moves
filed -> refiled (or demotes to unclustered/ when no category remains). Runs after
anything that re-stamps category_paths on filed inferences — an approved synonym
merge re-normalizes keywords and shifts paths[0]; a clean re-categorize can empty
the paths of previously-filed accounts.

- Scans filed inf_*.json under <dir>, skipping the unclustered/ holding pen
- Canonical address is <dir>/<category_paths[0]>/ — the promote.py convention
- Empty category_paths -> demoted to <dir>/unclustered/ (honest latency restored)
- Sibling files move with the inference: any file beside it carrying the same
  hex id (reify_<id>.md and future res_/rendering siblings)
- Emptied directories are retired up to (never including) <dir>
- Idempotent: a file already at its canonical address is left alone
- Run PER DOMAIN (--dir inferences/<domain>), matching categorize/promote:
  category_paths are domain-relative, so running at a multi-domain root would
  strip the domain layer. A guard detects domain roots and refuses to move.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from vivify_core import read_json

DEFAULT_DIR = "inferences"


def _is_domains_root(base):
    """True if base looks like a multi-domain root rather than a single domain.

    - A domain child is a subdirectory carrying its own unclustered/ holding pen
    - category_paths are domain-relative, so refiling from a domains root would
      strip the domain prefix off every address
    """
    return any(
        (child / "unclustered").is_dir()
        for child in base.iterdir()
        if child.is_dir() and child.name != "unclustered"
    )


def refile_all(inferences_dir=DEFAULT_DIR, dry_run=False):
    """Move filed inferences (and their siblings) to their current canonical address.

    - Filed = any inf_*.json under <dir> outside unclustered/
    - Destination: <dir>/<category_paths[0]>/, or <dir>/unclustered/ if paths empty
    - Returns summary dict: {"refiled": [...], "demoted": [...], "kept": [id, ...]}
      where refiled/demoted entries carry id, from, to, and sibling count
    """
    base = Path(inferences_dir)
    summary = {"refiled": [], "demoted": [], "kept": []}

    if not base.is_dir():
        return summary

    if _is_domains_root(base):
        print(f"{base} looks like a multi-domain root (children carry their own "
              f"unclustered/). category_paths are domain-relative — run per domain:")
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "unclustered").is_dir():
                print(f"  refile.py --dir {child}")
        return summary

    for path in sorted(base.rglob("inf_*.json")):
        rel_parent = path.parent.relative_to(base)
        if rel_parent.parts[:1] == ("unclustered",):
            continue  # the holding pen is promote.py's territory

        inference = read_json(path)
        if not inference:
            continue

        paths = inference.get("category_paths", [])
        dest_dir = base / paths[0] if paths else base / "unclustered"
        if dest_dir.resolve() == path.parent.resolve():
            summary["kept"].append(inference.get("id"))
            continue

        # Siblings: files beside the inference carrying its hex id (reify_*.md etc.)
        stem = (inference.get("id") or path.stem).replace("inf_", "")
        moves = [path] + [
            p for p in path.parent.iterdir()
            if p != path and p.is_file() and stem and stem in p.name
        ]

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in moves:
                f.rename(dest_dir / f.name)
            # Retire emptied directories up to (never including) the base
            d = path.parent
            while d != base and d.exists() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent

        entry = {
            "id": inference.get("id"),
            "from": str(path.parent),
            "to": str(dest_dir),
            "siblings": len(moves) - 1,
        }
        summary["demoted" if not paths else "refiled"].append(entry)

    return summary


def usage():
    print("Usage: refile.py [--dir <path>] [--dry-run]")
    print()
    print("Move filed inferences whose category_paths changed to their canonical")
    print("address (<dir>/<category_paths[0]>/). Empty paths demote to unclustered/.")
    print("Siblings (reify_*.md etc.) move with the inference; emptied dirs retire.")
    print()
    print("  --dir <path>   Single-domain inferences directory (run per domain,")
    print("                 e.g. --dir inferences/field — never a multi-domain root)")
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

    summary = refile_all(inferences_dir=args.dir, dry_run=args.dry_run)

    verb = "Would refile" if args.dry_run else "Refiled"
    print(f"{verb}: {len(summary['refiled'])}")
    for item in summary["refiled"]:
        tag = f"  (+{item['siblings']} sibling)" if item["siblings"] else ""
        print(f"  {item['id']}  {item['from']}  ->  {item['to']}{tag}")
    verb = "Would demote" if args.dry_run else "Demoted"
    print(f"{verb} to unclustered: {len(summary['demoted'])}")
    for item in summary["demoted"]:
        print(f"  {item['id']}  {item['from']}")
    print(f"Kept in place: {len(summary['kept'])}")


if __name__ == "__main__":
    main()

# llm: claude-fable-5 | 2026-07-12 | repos/vivify-operators/refile.py | created — refile pass per reify_phase2_spec_r1 step 2: filed->refiled/demoted complement of promote.py, moves id-matched siblings, retires emptied dirs
