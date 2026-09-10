#!/usr/bin/env python3
"""
merge_store.py — promote selected coordinates from a re-derived store into the active store

Step 2 of the stabilisation sequence is a SPLIT promotion, not a file swap: some
dimensions reproduce across sessions and some do not, so re-deriving everything and
copying it over would overwrite the coordinates that are being deliberately held.
`tag_store.py` re-tags IN PLACE and has no notion of promoting a subset, and
`promote.py` is unrelated (it files inferences out of unclustered/ into category
directories). This is the missing piece between them.

  1. cp -r inferences /tmp/store_voted
  2. python3 tag_store.py --dir /tmp/store_voted --force     # re-derive under voting
  3. python3 merge_store.py --from /tmp/store_voted --promote ...        # review
  4. python3 merge_store.py --from /tmp/store_voted --promote ... --apply

THE UNIT OF PROMOTION IS THE BLOCK, NEVER A SCALAR. `logos.authority` promotes the
whole authority block — value, confidence, rationale, _model, _votes — because a
block is what a draw actually produced. Promoting individual fields across blocks
would assemble combinations no draw ever returned, which is the same failure
`modal_choice` was written to avoid.

Dry-run by default: nothing is written without --apply, and --apply first copies
every file it will touch to ~/backups/ (mirroring the repo path) so a bad promotion
is recoverable independently of git.

Refuses to promote a block that carries no `_votes`, so a single-draw value cannot
reach the store through this path by accident.
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

BACKUP_ROOT = Path.home() / "backups" / "vivify-operators"

# Promotable blocks, as dotted paths. `tension` is derived arithmetic — prefer
# --rescore-tension over promoting it, so it follows whatever conflict/resonance land on.
DEFAULT_LOGOS = ("act_type", "authority", "cooperative", "transmission", "utility",
                 "resonance", "structural", "social_field")


def verdict_of(path, block):
    """Short human-readable identity of a block, for the diff report."""
    if not isinstance(block, dict):
        return repr(block)
    if path == "logos.structural":
        return block.get("scale")
    if path == "logos.cooperative":
        return f"{block.get('status')}/{block.get('maxim_violated')}"
    if path == "logos.social_field":
        return block.get("quadrant")
    if path == "conflict":
        return f"terrain={block.get('terrain')} window={block.get('window')}"
    if path == "tension":
        return f"predicted={block.get('predicted')} delta={block.get('calibration_delta')}"
    return block.get("value")


def spread_of(block):
    """The vote spread a block carries, or None if it was never voted."""
    if not isinstance(block, dict):
        return None
    votes = block.get("_votes")
    if not isinstance(votes, dict):
        return None
    return f"{votes.get('agreed')}/{votes.get('n')}"


def get_block(inf, path):
    node = inf
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def set_block(inf, path, value):
    parts = path.split(".")
    node = inf
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def load_store(directory):
    """Map inference id -> (path, parsed). Matches on id, not filename, because the
    two stores may file the same inference under different category directories."""
    store = {}
    for p in sorted(Path(directory).rglob("inf_*.json")):
        try:
            inf = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ! unreadable, skipped: {p} ({e})")
            continue
        if isinstance(inf, dict) and inf.get("id"):
            store[inf["id"]] = (p, inf)
    return store


def parse_excludes(raw):
    """--exclude inf_f39647fd:logos.structural -> {sid: {path, ...}}"""
    out = {}
    for item in raw or []:
        if ":" not in item:
            sys.exit(f"--exclude needs <inference_id>:<path>, got {item!r}")
        sid, path = item.split(":", 1)
        out.setdefault(sid, set()).add(path)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="source", required=True,
                    help="re-derived store to promote FROM")
    ap.add_argument("--to", dest="target", default=str(ROOT / "inferences"),
                    help="active store to promote INTO (default: inferences)")
    ap.add_argument("--promote", default="",
                    help="comma-separated block paths, e.g. "
                         "logos.act_type,logos.authority,conflict")
    ap.add_argument("--exclude", action="append", metavar="ID:PATH",
                    help="hold one block on one inference, e.g. "
                         "inf_f39647fd:logos.structural (repeatable)")
    ap.add_argument("--rescore-tension", action="store_true",
                    help="recompute tension after merging instead of promoting it "
                         "(it is derived from conflict + resonance)")
    ap.add_argument("--list-paths", action="store_true",
                    help="show the block paths present in the source store and exit")
    ap.add_argument("--apply", action="store_true",
                    help="write the merge (default is dry-run)")
    args = ap.parse_args()

    source = load_store(args.source)
    if not source:
        sys.exit(f"no inferences found in {args.source}")

    if args.list_paths:
        paths = set()
        for _, inf in source.values():
            for dim in (inf.get("logos") or {}):
                if dim.startswith("_"):      # _runner and friends are metadata, not coordinates
                    continue
                paths.add(f"logos.{dim}")
            for top in ("conflict", "tension"):
                if top in inf:
                    paths.add(top)
        print(f"block paths in {args.source}:")
        for p in sorted(paths):
            print(f"  {p}")
        return

    if not args.promote:
        sys.exit("--promote is required (or use --list-paths). Nothing is promoted by default.")

    target = load_store(args.target)
    promote = [p.strip() for p in args.promote.split(",") if p.strip()]
    excludes = parse_excludes(args.exclude)

    print(f"from   : {args.source}  ({len(source)} inferences)")
    print(f"into   : {args.target}  ({len(target)} inferences)")
    print(f"promote: {', '.join(promote)}")
    if excludes:
        print(f"hold   : " + "; ".join(f"{s}:{','.join(sorted(p))}" for s, p in excludes.items()))
    print(f"mode   : {'APPLY (writes)' if args.apply else 'dry-run'}\n")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = BACKUP_ROOT / f"merge_{stamp}"
    changes = unchanged = refused = 0
    touched = {}

    for sid, (tpath, tinf) in sorted(target.items()):
        if sid not in source:
            print(f"=== {sid}  (not in source store — untouched)")
            continue
        _, sinf = source[sid]
        held = excludes.get(sid, set())
        lines = []
        for path in promote:
            if path in held:
                lines.append(f"  {path:22} HELD by --exclude")
                continue
            new = get_block(sinf, path)
            old = get_block(tinf, path)
            if new is None:
                lines.append(f"  {path:22} absent in source — skipped")
                continue
            if spread_of(new) is None:
                lines.append(f"  {path:22} REFUSED — no _votes (single draw)")
                refused += 1
                continue
            ov, nv = verdict_of(path, old), verdict_of(path, new)
            if ov == nv:
                unchanged += 1
                lines.append(f"  {path:22} {str(nv):26} unchanged  [{spread_of(new)}]")
            else:
                changes += 1
                lines.append(f"  {path:22} {str(ov):26} -> {str(nv)}  [{spread_of(new)}]")
            if args.apply:
                set_block(tinf, path, new)
                touched[sid] = (tpath, tinf)

        if args.rescore_tension:
            import tension_score
            rescored = tension_score.score_inference(tinf)
            tinf["tension"] = rescored["tension"]
            tinf["tension_score"] = rescored.get("tension_score")
            lines.append(f"  {'tension':22} rescored -> {verdict_of('tension', tinf['tension'])}")
            if args.apply:
                touched[sid] = (tpath, tinf)

        print(f"=== {sid}  {tinf.get('case_id') or ''}")
        print("\n".join(lines) + "\n")

    print(f"{changes} changed, {unchanged} already equal, {refused} refused (unvoted)")

    if not args.apply:
        print("\ndry-run — nothing written. Re-run with --apply to commit the merge.")
        return
    if not touched:
        print("nothing to write.")
        return

    for sid, (tpath, tinf) in touched.items():
        try:
            rel = Path(tpath).resolve().relative_to(ROOT)
        except ValueError:                    # target store outside the repo
            rel = Path(*Path(tpath).resolve().parts[1:])
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tpath, dest)
    print(f"backed up {len(touched)} file(s) to {backup_dir}")

    for sid, (tpath, tinf) in touched.items():
        Path(tpath).write_text(json.dumps(tinf, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(touched)} inference file(s)")
    print("next: python3 build_index.py --voices   (WITHOUT --voices the index drops voices)")


if __name__ == "__main__":
    main()

# llm: claude-opus-5 | 2026-09-10 | repos/vivify-operators/merge_store.py | created — the per-field (per-BLOCK) promotion step 2 needs and neither tag_store.py (re-tags in place) nor promote.py (files unclustered/) provides; dry-run by default, backs up before writing, refuses blocks carrying no _votes
