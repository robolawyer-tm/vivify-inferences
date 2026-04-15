"""
tension_score — FABRIC analysis: left/right divergence scoring

Calculates tension between left (semantic) and right (digital) keyword sets
for each inference. High tension = left and right describe very different things
= prime zone for intervention and beneficial outcome prediction.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json
from keyword_graph import tension_score, build_graph, neighborhood


INFERENCES_DIR = Path("inferences")
INDEX_FILE = INFERENCES_DIR / "index.json"


def score_inference(inference):
    """Calculate and attach tension_score to a single inference.

    - tension = 1.0 - (shared_keywords / total_unique_keywords)
    - 1.0 = completely divergent (left and right share nothing)
    - 0.0 = identical (left and right are the same)
    - High tension signals high intervention opportunity
    - Returns updated inference with tension_score set
    """
    left = inference.get("left_keywords", [])
    right = inference.get("right_keywords", [])
    score = tension_score(left, right)
    inference = dict(inference)
    inference["tension_score"] = score
    return inference


def score_all(inferences_dir=None, dry_run=False):
    """Score all inferences and update their files.

    - Returns list of (id, path, tension_score) tuples sorted high to low
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    results = []

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue
        updated = score_inference(inference)
        if not dry_run:
            write_json(path, updated)
        results.append((
            updated["id"],
            str(path),
            updated["tension_score"]
        ))

    return sorted(results, key=lambda x: -x[2])


def beneficial_signals(inferences_dir=None, threshold=0.5):
    """Find inferences where tension exceeds threshold — intervention candidates.

    - High tension = left meaning and right structure are pulling apart
    - These are the zones where digital systems most betray analog human truth
    - Returns list of dicts with id, tension_score, left_keywords, category_paths
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    signals = []

    for path in inferences_dir.rglob("inf_*.json"):
        inference = read_json(path)
        if not inference:
            continue
        score = inference.get("tension_score")
        if score is not None and score >= threshold:
            signals.append({
                "id": inference["id"],
                "tension_score": score,
                "left_keywords": inference.get("left_keywords", []),
                "category_paths": inference.get("category_paths", []),
                "source": inference.get("source", "unknown")
            })

    return sorted(signals, key=lambda x: -x["tension_score"])


def prediction_output(inference):
    """Generate a Phase 5 bottled prediction API response for a single inference.

    - beneficial_score: inverted tension (high tension = high intervention value)
    - resolution_paths: category_paths from the inference
    - tension_signals: top left keywords by co-occurrence strength
    - Returns dict matching the Phase 5 API shape
    """
    score = inference.get("tension_score", 0.0)
    return {
        "id": inference["id"],
        "beneficial_score": score,
        "resolution_paths": inference.get("category_paths", []),
        "tension_signals": inference.get("left_keywords", [])[:4],
        "source": inference.get("source", "unknown")
    }


def usage():
    print("Usage: tension_score.py              score all inferences")
    print("       tension_score.py --signals     show high-tension intervention candidates")
    print("       tension_score.py --predict     show Phase 5 API output for all inferences")
    print("       tension_score.py --dry-run     score without writing files")
    sys.exit(1)


def main():
    dry_run = "--dry-run" in sys.argv

    if "--signals" in sys.argv:
        signals = beneficial_signals()
        if not signals:
            print("No high-tension inferences found. Score first.")
            return
        print(f"High-tension intervention candidates (tension >= 0.5):\n")
        for s in signals:
            print(f"  {s['id']}  tension: {s['tension_score']}")
            print(f"    source:   {s['source']}")
            print(f"    keywords: {', '.join(s['left_keywords'][:5])}")
            print(f"    paths:    {', '.join(s['category_paths'][:2])}")
            print()
        return

    if "--predict" in sys.argv:
        inferences_dir = INFERENCES_DIR
        print("Phase 5 — Bottled Prediction API output:\n")
        for path in inferences_dir.rglob("inf_*.json"):
            inference = read_json(path)
            if inference:
                output = prediction_output(inference)
                print(json.dumps(output, indent=2))
                print()
        return

    results = score_all(dry_run=dry_run)

    if not results:
        print("No inferences found.")
        return

    print(f"Scored {len(results)} inferences:\n")
    for inf_id, path, score in results:
        bar = "█" * int(score * 20)
        print(f"  {inf_id}  {score:.4f}  {bar}")
        print(f"    {path}")
    print()
    avg = sum(s for _, _, s in results) / len(results)
    print(f"Average tension: {avg:.4f}")
    print(f"Peak tension:    {results[0][2]:.4f}  ({results[0][0]})")


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/tension_score.py | created — left/right divergence scoring, beneficial signals, Phase 5 prediction output
