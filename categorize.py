"""
categorize — assign category_paths to inferences from emergent graph seeds

Reads the co-occurrence graph, identifies seed keywords, builds category paths,
and assigns inferences to paths based on keyword membership. No external taxonomies.
All structure emerges from the data.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json
from keyword_graph import build_graph, top_seeds, neighborhood


INFERENCES_DIR = Path("inferences")
MIN_COOCCURRENCE = 1   # lower threshold while corpus is small
MIN_SEED_DEGREE  = 5   # minimum connections to qualify as a seed
MAX_DEPTH        = 3   # maximum category path depth


def build_category_tree(graph, min_weight=MIN_COOCCURRENCE, min_degree=MIN_SEED_DEGREE,
                        left_keywords_only=None):
    """Build a 2-3 layer category tree from graph seeds.

    - Seeds come from left_keywords only — right structural keywords support but never seed
    - Layer 1 seeds: highest-degree left keywords
    - Layer 2: strong neighbors of each seed (left or right)
    - Layer 3: strong neighbors of layer 2 nodes (if distinct)
    - Returns dict: {seed: {sub: [sub_sub, ...], ...}}
    """
    all_candidates = [kw for kw, deg in top_seeds(graph, n=40, min_weight=min_weight)
                      if deg >= min_degree]

    # If left_keywords provided, restrict seeds to left side only
    if left_keywords_only:
        seeds = [kw for kw in all_candidates if kw in left_keywords_only]
    else:
        seeds = all_candidates

    tree = {}
    for seed in seeds:
        subs = {}
        for sub, w in neighborhood(graph, seed, min_weight=min_weight):
            if sub == seed or sub in tree:
                continue
            sub_subs = [
                s for s, sw in neighborhood(graph, sub, min_weight=min_weight)
                if s != seed and s != sub and s not in tree and s not in subs
            ][:4]
            subs[sub] = sub_subs
        if subs:
            tree[seed] = subs

    return tree


def paths_for_inference(inference, tree):
    """Find all category paths an inference qualifies for.

    - Inference qualifies for seed/sub path if it contains the seed keyword
      plus at least one sub keyword
    - Returns list of path strings e.g. ['beneficial_outcome_modeling/tension_score_calculation']
    """
    all_keywords = set(
        inference.get("left_keywords", []) +
        inference.get("right_keywords", [])
    )

    paths = []
    for seed, subs in tree.items():
        if seed not in all_keywords:
            continue
        for sub in subs:
            if sub in all_keywords:
                paths.append(f"{seed}/{sub}")

    return sorted(set(paths))


def paths_for_synthesis(inference, tree, graph):
    """For synthesis inferences: composite paths from the corpus's top seeds.

    A synthesis spans the whole corpus, so its paths are derived from the
    corpus's dominant seeds by graph degree — not from its own keywords.
    Returns pairwise composite paths for the top 3 seeds, reflecting which
    threads the synthesis holds simultaneously.
    """
    ranked = sorted(
        tree.keys(),
        key=lambda s: len(graph.get(s, {})),
        reverse=True
    )
    top = ranked[:3]

    if len(top) < 2:
        return []

    return sorted(f"{s1}/{s2}" for i, s1 in enumerate(top) for s2 in top[i+1:])


def categorize_all(inferences_dir=None, dry_run=False):
    """Assign category_paths to all inferences and move them out of unclustered/.

    - Builds graph and category tree from current corpus
    - Updates each inference file with category_paths
    - Moves categorized inferences to inferences/{category_path}/
    - Inferences with no match stay in unclustered/
    - Returns summary dict
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    graph = build_graph(inferences_dir)

    if not graph:
        print("No inferences found.")
        return {}

    # Collect all left keywords across corpus — seeds must come from left side only
    left_keywords_corpus = set()
    for path in inferences_dir.rglob("inf_*.json"):
        inf = read_json(path)
        left_keywords_corpus.update(inf.get("left_keywords", []))

    tree = build_category_tree(graph, left_keywords_only=left_keywords_corpus)
    summary = {"categorized": [], "unclustered": [], "tree_seeds": list(tree.keys())}

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue

        if inference.get("source") == "synthesis":
            paths = paths_for_synthesis(inference, tree, graph)
        else:
            paths = paths_for_inference(inference, tree)
        inference["category_paths"] = paths

        if paths and not dry_run:
            # Move to first category path directory
            dest_dir = inferences_dir / Path(paths[0])
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / path.name

            write_json(dest, inference)

            # Remove from unclustered if moving elsewhere
            if "unclustered" in str(path) and dest != path:
                path.unlink()

            summary["categorized"].append({
                "id": inference["id"],
                "paths": paths,
                "dest": str(dest)
            })
        elif paths and dry_run:
            summary["categorized"].append({
                "id": inference["id"],
                "paths": paths
            })
        else:
            write_json(path, inference)
            summary["unclustered"].append(inference["id"])

    return summary, tree


def usage():
    print("Usage: categorize.py            categorize all inferences")
    print("       categorize.py --dry-run  show what would be assigned without moving files")
    print("       categorize.py --tree     show the category tree only")
    sys.exit(1)


def main():
    dry_run = "--dry-run" in sys.argv
    tree_only = "--tree" in sys.argv

    graph = build_graph()
    if not graph:
        print("No inferences found.")
        return

    tree = build_category_tree(graph)

    left_keywords_corpus = set()
    for path in INFERENCES_DIR.rglob("inf_*.json"):
        inf = read_json(path)
        left_keywords_corpus.update(inf.get("left_keywords", []))

    tree = build_category_tree(graph, left_keywords_only=left_keywords_corpus)

    if tree_only or "--tree" in sys.argv:
        print("Category tree (seeded from left keywords only):")
        for seed, subs in tree.items():
            print(f"\n  {seed}/")
            for sub, sub_subs in subs.items():
                print(f"    {sub}/")
                for ss in sub_subs[:3]:
                    print(f"      {ss}")
        return

    summary, tree = categorize_all(dry_run=dry_run)

    print(f"Category seeds: {len(summary['tree_seeds'])}")
    print(f"Categorized:    {len(summary['categorized'])}")
    print(f"Unclustered:    {len(summary['unclustered'])}")

    if summary["categorized"]:
        print()
        for item in summary["categorized"]:
            print(f"  {item['id']}")
            for p in item["paths"][:3]:
                print(f"    → {p}")

    if summary["unclustered"]:
        print()
        print("Still unclustered:")
        for inf_id in summary["unclustered"]:
            print(f"  {inf_id}")


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/categorize.py | created — emergent category assignment from co-occurrence graph seeds
