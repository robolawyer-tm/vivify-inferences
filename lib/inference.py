"""
inference — inference data model

Defines the atomic unit of the vivify pipeline. Each inference is a raw text
input paired with its left/right keyword passes, category paths, and tension score.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from vivify_core import deep_update, write_json, read_json


INFERENCE_VERSION = "1.0"


def new_inference(raw_text, source="manual"):
    """Create a new inference unit from raw text.

    - id: unique identifier in inf_XXX format
    - timestamp: ISO-8601 UTC
    - source: origin of the text (manual, api, file)
    - All keyword/category fields start empty — filled by pipeline passes
    """
    uid = uuid.uuid4().hex[:8]
    return {
        "id": f"inf_{uid}",
        "version": INFERENCE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "raw_text": raw_text.strip(),
        "left_keywords": [],
        "right_keywords": [],
        "clumps": {},
        "category_paths": [],
        "tension_score": None,
        "guardrail_actions": {}
    }


def save_inference(inference, inferences_dir="inferences"):
    """Write an inference to the unclustered holding area as inf_XXX.json.

    - Inferences go to unclustered/ until categorized by a pipeline pass
    - Returns the path written
    """
    path = Path(inferences_dir) / "unclustered" / f"{inference['id']}.json"
    write_json(path, inference)
    return path


def load_inference(inference_id, inferences_dir="inferences"):
    """Load an inference by ID, searching unclustered/ and category subdirs.

    - Searches unclustered/ first, then walks the full inferences/ tree
    - Returns None if not found
    """
    base = Path(inferences_dir)

    # Check unclustered first
    candidate = base / "unclustered" / f"{inference_id}.json"
    if candidate.exists():
        return read_json(candidate)

    # Walk full tree
    for path in base.rglob(f"{inference_id}.json"):
        return read_json(path)

    return None


def update_inference(inference, updates):
    """Apply updates to an inference dict using deep_update.

    - Updates can add/replace any field including nested clumps and category_paths
    - Returns the updated inference
    """
    return deep_update(inference, updates)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        raw = " ".join(sys.argv[1:])
    else:
        print("Usage: inference.py <raw text>")
        print("       echo 'raw text' | inference.py")
        sys.exit(1)

    import fileinput
    if not sys.stdin.isatty():
        raw = "".join(fileinput.input())

    inf = new_inference(raw)
    print(json.dumps(inf, indent=2))

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/lib/inference.py | created — inference data model, save/load/update
