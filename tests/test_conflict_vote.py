#!/usr/bin/env python3
"""Focused test: conflict votes PER COORDINATE, and terrain votes on its DERIVED bin.

Guards two 2026-09 changes. conflict used to vote all five enums as one block, so one
unstable field decided the other four (run 3 reported `terrain 3/3 [block 2/3]`). And
terrain is now derived from a 0-1 position, so its vote must run on the derived bin —
voting on the drawn label would report agreement on the reading derive_terrain()
replaced, while storing something else.

No real LLM calls — conflict_operator.call_and_validate is monkeypatched.

Run standalone: python3 tests/test_conflict_vote.py  (exit 0 = pass)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import conflict_operator as co


def _draw(schema, drawn_terrain, distance, hook=False, window="open"):
    return {"schema": schema, "schema_signals": [f"sig-{schema}"],
            "behavior": "suppression", "behavior_signals": [],
            "terrain": drawn_terrain, "terrain_distance": distance, "terrain_hook": hook,
            "window": window, "escalation_phase": "threshold",
            "confidence": 0.8, "rationale": f"{schema}/{distance}"}


def _script(draws):
    state = {"i": 0}

    def fake(*args, **kwargs):
        d = draws[state["i"]]
        state["i"] += 1
        return dict(d)
    return fake


def test_terrain_votes_on_derived_bin():
    # Drawn label says fringe all three times; positions say drifting, drifting, fringe.
    co.call_and_validate = _script([_draw("activated", "fringe", 0.50),
                                    _draw("latent",    "fringe", 0.55),
                                    _draw("activated", "fringe", 0.90)])
    merged, rec = co.vote_per_dimension("prompt", votes=3)
    assert rec["by_dim"]["terrain"]["agreed"] == 2, rec["by_dim"]["terrain"]
    assert rec["distribution"]["terrain"] == {"drifting": 2, "fringe": 1}, rec["distribution"]
    assert rec["distribution"]["terrain_drawn"] == {"fringe": 3}
    assert rec["by_dim"]["terrain"]["distances"] == [0.50, 0.55, 0.90]
    assert merged["terrain_distance"] == 0.50        # from a draw that derives drifting
    assert co.derive_terrain(merged["terrain_distance"], merged["terrain_hook"]) == "drifting"


def test_one_wobble_does_not_decide_the_others():
    co.call_and_validate = _script([_draw("activated", "drifting", 0.5, window="open"),
                                    _draw("latent",    "drifting", 0.5, window="open"),
                                    _draw("entangled", "drifting", 0.5, window="open")])
    merged, rec = co.vote_per_dimension("prompt", votes=3)
    assert rec["by_dim"]["window"]["unanimous"] is True
    assert rec["by_dim"]["terrain"]["unanimous"] is True
    assert rec["by_dim"]["schema"]["agreed"] == 1
    # schema and its signals travel together from one real draw
    assert merged["schema_signals"] == [f"sig-{merged['schema']}"]


def test_missing_position_falls_back_to_drawn_label():
    co.call_and_validate = _script([_draw("activated", "center", None)] * 3)
    merged, rec = co.vote_per_dimension("prompt", votes=3)
    assert rec["distribution"]["terrain"] == {"center": 3}


def test_run_stores_derived_terrain_with_derived_agreement():
    co.call_and_validate = _script([_draw("activated", "fringe", 0.50),
                                    _draw("activated", "fringe", 0.55),
                                    _draw("activated", "fringe", 0.90)])
    # run() returns early on an inference with no logos, so give it the minimum
    inf = {"id": "inf_test", "raw_text": "x", "logos": {"act_type": {"value": "assertive"}}}
    c = co.run(inf)["conflict"]
    assert c["terrain"] == "drifting" and c["terrain_drawn"] == "fringe"
    assert c["terrain_agrees"] is False
    assert c["_votes"]["by_dim"]["terrain"]["agreed"] == 2


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} passed")

# llm: claude-opus-5 | 2026-09-11 | repos/vivify-operators/tests/test_conflict_vote.py | created — per-coordinate conflict voting, terrain voted on its derived bin, per-draw positions recorded
