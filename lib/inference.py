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


def new_inference(raw_text, source="manual", case_id=None):
    """Create a new inference unit from raw text.

    - id: unique identifier in inf_XXX format
    - timestamp: ISO-8601 UTC
    - source: origin of the text (manual, api, file)
    - case_id: the underlying case this text describes, when the same case can be
      told more than once (a second telling from a different document). Two
      inferences sharing a case_id are VARIANTS, not independent observations —
      see case_key() for what reads it. None = this text stands alone.
    - All keyword/category fields start empty — filled by pipeline passes
    """
    uid = uuid.uuid4().hex[:8]
    return {
        "id": f"inf_{uid}",
        "version": INFERENCE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "case_id": case_id,
        "raw_text": raw_text.strip(),
        "left_keywords": [],
        "right_keywords": [],
        "clumps": {},
        "category_paths": [],
        "tension_score": None,
        "guardrail_actions": {}
    }


def case_key(inference):
    """The identity of the case an inference describes — its de-duplication key.

    - Returns case_id when set; otherwise falls back to the inference's own id,
      so an untagged inference is always its own case and can never be collapsed
      with another by accident (fail-open for independence, closed for variants)
    - Store-level passes group by this, never by id, when they must count each
      underlying case once: cross_scale link eligibility, the calibration gradient
    """
    return inference.get("case_id") or inference.get("id")


def is_canonical(inference):
    """True when this telling is explicitly marked as the one to count its case by.

    - Absence is not "no" — it means nobody has chosen, and consumers fall back to
      their own rule (the gradient uses earliest timestamp). Only an explicit
      `canonical: true` overrides that.
    - Needed because the first telling of a case is not necessarily the best one:
      a later re-telling from a cleaner source should be able to take over as the
      case's data point without deleting the earlier one from the store.
    """
    return inference.get("canonical") is True


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
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/lib/inference.py | case_id field on new_inference + case_key() — variant tellings of one case share an identity, untagged falls back to own id
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/lib/inference.py | is_canonical() — explicit canonical mark on a telling; absence means unchosen, not false
