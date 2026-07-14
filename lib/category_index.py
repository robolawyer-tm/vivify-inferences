"""category_index — persist and query the emergent category tree in index.json.

Replaces filesystem directory nesting as the categorization mechanism: storage
stays flat (one file per inference, partitioned only by domain), while the
revisable 2-3 layer arrangement lives in index.json's categories slot.

- write_categories: persist the tree + path->ids map produced by categorize.py
- ids_for_path: query inference ids for a category path (prefix-matched)
- load_by_id: load a flat-stored inference by id, domain-agnostic
- materialize_to_filesystem: optionally project the index tree back into real
  directories, for applications that want filesystem-as-categorization again
"""

from pathlib import Path

from vivify_core import read_json, write_json


def write_categories(index_file, tree, path_to_ids):
    """Persist the category tree + path->ids map into index.json's categories slot.

    - Preserves existing keywords / cooccurrence stats; only categories is replaced
    - Creates index.json if it does not exist
    """
    index = read_json(index_file)
    if not index:
        index = {
            "version": "3.0", "total_inferences": 0,
            "keywords": {}, "cooccurrence": {}, "categories": {},
        }
    index["categories"] = {"tree": tree, "paths": path_to_ids}
    write_json(index_file, index)
    return index


def ids_for_path(index, category):
    """Return inference ids indexed under a category path, prefix-matched.

    - 'seed' returns ids under seed and any deeper seed/sub/... path
    - 'seed/sub' returns that exact path's ids
    - Returns a sorted, de-duplicated list
    """
    paths = (index.get("categories") or {}).get("paths", {})
    ids = []
    for path, id_list in paths.items():
        if path == category or path.startswith(category + "/"):
            ids.extend(id_list)
    return sorted(set(ids))


def load_by_id(inferences_dir, inf_id):
    """Locate and load a flat-stored inference by id, across all domain dirs.

    - Returns dict, or None if not found
    """
    for p in Path(inferences_dir).rglob(f"{inf_id}.json"):
        return read_json(p)
    return None


def materialize_to_filesystem(inferences_dir, link=True, dry_run=False):
    """Project the index category tree back into real directories.

    For applications that want filesystem-as-categorization: reads paths from
    index.json and creates inferences/{seed}/{sub}/{id}.json pointing at the
    flat originals. Symlinks by default (link=True) so flat storage stays the
    single source of truth; copies if link=False.

    - Returns list of created destination paths
    """
    inferences_dir = Path(inferences_dir)
    index = read_json(inferences_dir / "index.json")
    paths = (index.get("categories") or {}).get("paths", {})
    created = []

    for category, ids in paths.items():
        for inf_id in ids:
            src = None
            for p in inferences_dir.rglob(f"{inf_id}.json"):
                if "/" not in str(p.relative_to(inferences_dir).parent):
                    src = p  # prefer a flat (domain-level) original
                    break
            if src is None:
                continue
            dest = inferences_dir / category / f"{inf_id}.json"
            if dry_run:
                created.append(str(dest))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            if link:
                dest.symlink_to(src.resolve())
            else:
                write_json(dest, read_json(src))
            created.append(str(dest))

    return created

# llm: claude-opus-4-8 | 2026-06-26 | repos/vivify-inferences/lib/category_index.py | created — index-based categorization: write/query category tree in index.json, flat storage; optional materialize back to f/s
# llm: claude-opus-4-8 | 2026-06-28 | repos/vivify-operators/lib/category_index.py | ported from vivify-inferences — index-based categorization helpers for the real-data runtime
