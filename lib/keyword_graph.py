"""
keyword_graph — co-occurrence graph operations

Builds and queries the keyword co-occurrence graph from stored inferences.
Seeds for emergent categories are keywords with high degree (many co-occurring pairs).
"""

import json
from pathlib import Path
from collections import defaultdict

from vivify_core import read_json, write_json


INFERENCES_DIR = Path("inferences")
INDEX_FILE = INFERENCES_DIR / "index.json"


def build_graph(inferences_dir=None):
    """Build a co-occurrence graph from all stored inferences.

    - Nodes are keywords. Edges are co-occurrence in the same inference.
    - Edge weight = number of inferences sharing both keywords.
    - Returns dict: {keyword: {co_keyword: weight, ...}, ...}
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    graph = defaultdict(lambda: defaultdict(int))

    for path in inferences_dir.rglob("inf_*.json"):
        inf = read_json(path)
        keywords = inf.get("left_keywords", []) + inf.get("right_keywords", [])
        for i, kw1 in enumerate(keywords):
            for kw2 in keywords[i + 1:]:
                graph[kw1][kw2] += 1
                graph[kw2][kw1] += 1

    return {k: dict(v) for k, v in graph.items()}


def degree(graph):
    """Return each keyword's degree — number of unique co-occurring keywords.

    - High-degree keywords are category seed candidates.
    - Returns dict: {keyword: degree_count}
    """
    return {kw: len(neighbors) for kw, neighbors in graph.items()}


def top_seeds(graph, n=10, min_weight=1):
    """Return top n category seed candidates by degree, filtered by min edge weight.

    - Seeds are keywords with the most connections above min_weight
    - Returns list of (keyword, degree) tuples, sorted descending
    """
    deg = {}
    for kw, neighbors in graph.items():
        strong = sum(1 for w in neighbors.values() if w >= min_weight)
        if strong > 0:
            deg[kw] = strong
    return sorted(deg.items(), key=lambda x: -x[1])[:n]


def neighborhood(graph, keyword, min_weight=1):
    """Return all keywords that co-occur with keyword above min_weight.

    - Used to build sub-category clusters around a seed
    - Returns list of (co_keyword, weight) sorted by weight descending
    """
    neighbors = graph.get(keyword, {})
    return sorted(
        [(kw, w) for kw, w in neighbors.items() if w >= min_weight],
        key=lambda x: -x[1]
    )


def tension_score(left_keywords, right_keywords):
    """Calculate tension between left and right keyword sets.

    - tension = 1.0 - (shared / total_unique)
    - High tension = left and right describe very different things → intervention signal
    - Returns float 0.0 to 1.0
    """
    left = set(left_keywords)
    right = set(right_keywords)
    if not left and not right:
        return 0.0
    shared = len(left & right)
    total = len(left | right)
    return round(1.0 - (shared / total), 4)


if __name__ == "__main__":
    import sys

    graph = build_graph()
    if not graph:
        print("No inferences found. Store some inferences first.")
        sys.exit(0)

    print(f"Graph nodes (unique keywords): {len(graph)}")
    print()
    print("Top seed candidates:")
    for kw, deg in top_seeds(graph, n=15, min_weight=1):
        print(f"  {kw}: degree {deg}")

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/lib/keyword_graph.py | created — co-occurrence graph, degree analysis, tension scoring
