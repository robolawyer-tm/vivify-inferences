#!/usr/bin/env python3
"""
tag_store.py — resumable batch driver: tag the whole inference store with logos + conflict.

The piece that was missing. Tagging used to mean running logos_operator and
conflict_operator by hand, per file, with no fail-fast and no way to tell a
half-tagged store from a finished one — so a quota runout mid-batch left the store
silently inconsistent (the 3/31 stall). This driver fixes that:

  - one pass over the store: fused logos (8->1 call, logos_fused.py) then conflict;
  - RESUMABLE — skips inferences already complete, and skips the logos call alone if
    only conflict is missing; writes after each sub-step so progress always persists;
  - FAIL-FAST — LLMUnavailable (quota/auth) aborts the run with exit 3, leaving every
    inference tagged so far intact; just re-run to continue where it stopped;
  - per-inference content errors (validation after retries) are recorded and skipped,
    not fatal — one bad inference doesn't sink the batch;
  - writes a completeness MANIFEST (_tagging_manifest.json) so cross_scale.py can see
    whether it is reading a finished store or a partial one.

Usage:
  python3 tag_store.py                 tag the public store (skips inferences/private/*)
  python3 tag_store.py --include-private   also tag inferences/private/*
  python3 tag_store.py --force         re-tag everything, even already-complete
  python3 tag_store.py --dir DIR       tag a different store root
  python3 tag_store.py --limit N       stop after N freshly-tagged inferences (batch a quota window)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, LLMUnavailable, CoordinateValidationError

import logos_fused
import conflict_operator

MANIFEST_NAME = "_tagging_manifest.json"

# The 8 logos dimensions a fully-tagged inference must carry, and the conflict fields.
LOGOS_KEYS = {"act_type", "cooperative", "transmission", "resonance",
              "authority", "utility", "social_field", "structural"}
CONFLICT_KEYS = ("schema", "behavior", "terrain", "window", "escalation_phase")


def _now():
    return datetime.now(timezone.utc).isoformat()


def logos_complete(inf):
    """True when all 8 logos dimensions are present and none of them carries an error.

    Only errors against the 8 managed dimensions count — a vestigial error from a
    retired dimension (e.g. narrative, no longer tagged by logos_fused) must not wedge
    a store the fused pass has fully tagged."""
    logos = inf.get("logos", {})
    if not LOGOS_KEYS.issubset(logos.keys()):
        return False
    errors = logos.get("_errors") or {}
    return not (LOGOS_KEYS & errors.keys())


def conflict_complete(inf):
    """True when the conflict pass has written its five coordinate fields."""
    c = inf.get("conflict", {})
    return all(k in c for k in CONFLICT_KEYS)


def is_complete(inf):
    return logos_complete(inf) and conflict_complete(inf)


def tag_one(path, force=False):
    """Tag a single inference file in place, resuming from whatever is already done.

    Returns a status string: 'complete' | 'skipped' | 'no_text' | 'error: ...'.
    Raises LLMUnavailable to signal the caller to abort the whole run (fail-fast).
    Writes after each sub-step so a later failure never loses earlier progress.
    """
    inf = read_json(path)
    if not inf:
        return "error: unreadable"
    if not inf.get("raw_text"):
        return "no_text"
    if is_complete(inf) and not force:
        return "skipped"

    try:
        if force or not logos_complete(inf):
            inf = logos_fused.run(inf)
            write_json(path, inf)              # persist logos before attempting conflict
        if force or not conflict_complete(inf):
            inf = conflict_operator.run(inf)
    except LLMUnavailable:
        raise                                  # transport/quota down -> abort the batch
    except (CoordinateValidationError, Exception) as e:
        # per-inference content failure (e.g. a model that never returns a legal
        # coordinate even after retries): record, keep going to the next inference.
        inf.setdefault("logos", {}).setdefault("_errors", {})["tag_store"] = str(e)
        inf["_tagged"] = {"at": _now(), "complete": False, "logos_runner": "logos_fused.py"}
        write_json(path, inf)
        return f"error: {e}"

    inf["_tagged"] = {"at": _now(), "complete": is_complete(inf), "logos_runner": "logos_fused.py"}
    write_json(path, inf)
    return "complete" if is_complete(inf) else "error: incomplete after tagging"


def iter_inferences(store, include_private):
    """Yield inf_*.json paths under the store, skipping private/ unless asked."""
    for path in sorted(store.rglob("inf_*.json")):
        if not include_private and "private" in path.parts:
            continue
        yield path


def write_manifest(store, rows):
    """Write the completeness manifest the cross_scale pass reads before running."""
    complete = [r["id"] for r in rows if r["status"] == "complete"]
    incomplete = [{"id": r["id"], "status": r["status"]} for r in rows
                  if r["status"] not in ("complete", "skipped")]
    skipped = [r["id"] for r in rows if r["status"] == "skipped"]
    manifest = {
        "_manifest": "tag_store.py",
        "at": _now(),
        "store": str(store),
        "total": len(rows),
        "complete": len(complete) + len(skipped),   # already-complete count as complete
        "incomplete": len(incomplete),
        "incomplete_ids": incomplete,
    }
    write_json(store / MANIFEST_NAME, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Resumable logos+conflict tagging over the inference store")
    parser.add_argument("--dir", default="inferences", help="store root (default: inferences)")
    parser.add_argument("--include-private", action="store_true", help="also tag inferences/private/*")
    parser.add_argument("--force", action="store_true", help="re-tag even already-complete inferences")
    parser.add_argument("--limit", type=int, help="stop after N freshly-tagged inferences (batch a quota window)")
    args = parser.parse_args()

    store = Path(args.dir)
    if not store.exists():
        print(f"store not found: {store}", file=sys.stderr)
        sys.exit(1)

    rows, fresh = [], 0
    for path in iter_inferences(store, args.include_private):
        inf_id = path.stem
        try:
            status = tag_one(path, force=args.force)
        except LLMUnavailable as e:
            # fail-fast: everything tagged so far is on disk; record the partial manifest and stop.
            write_manifest(store, rows)
            print(f"\nLLM unavailable (quota/auth?): {e}", file=sys.stderr)
            print(f"Aborted after {fresh} freshly tagged. Progress saved — re-run to resume. Exit 3.",
                  file=sys.stderr)
            sys.exit(3)

        rows.append({"id": inf_id, "status": status})
        if status == "complete":
            fresh += 1
            print(f"  [{fresh}] {inf_id}  complete")
        elif status == "skipped":
            pass  # quiet — already done
        else:
            print(f"      {inf_id}  {status}")

        if args.limit and fresh >= args.limit:
            print(f"\nReached --limit {args.limit}; stopping (resume later to continue).")
            break

    manifest = write_manifest(store, rows)
    print(f"\nStore: {manifest['total']} inferences | {manifest['complete']} complete | "
          f"{manifest['incomplete']} incomplete")
    print(f"Manifest -> {store / MANIFEST_NAME}")
    if manifest["incomplete"]:
        print("cross_scale will warn until the store is fully tagged (re-run to finish).")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tag_store.py | created — resumable store-level tagging driver: fused logos + conflict per inference, skip-if-complete (and skip logos alone if only conflict missing), write-after-each-substep, fail-fast exit 3 on LLMUnavailable, per-inference content errors recorded not fatal, completeness manifest for cross_scale
# llm: claude-opus-4-8 | 2026-06-29 | repos/vivify-operators/tag_store.py | logos_complete() now scopes its error check to the 8 managed dimensions, so a vestigial error from a retired dim (narrative) no longer marks a fully-fused inference incomplete
