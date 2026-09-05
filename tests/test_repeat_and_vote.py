#!/usr/bin/env python3
"""Focused test: repeat-and-vote stores the modal draw, with its spread.

Guards the 2026-09-03 change. A second reading of the legal corpus found 4 of 36
stored coordinates flipped between sessions and 6 more split within one session,
every one of them a move between LEGAL enum values that no gate can reject. Voting
is the answer to that; the enum gate is not, and this test keeps the two apart.

Also pins the newly gated structural.scale: valid accepted, out-of-enum rejected,
ABSENT still accepted so parse()'s layer fallback keeps working.

No real LLM calls — llm_call_model is monkeypatched.

Run standalone: python3 tests/test_repeat_and_vote.py  (exit 0 = pass)
"""
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import vivify_core as vc
from vivify_core import (call_and_vote, validate_coordinates, modal_choice,
                         CoordinateValidationError)

CONFIG = str(ROOT / "config")


def _script(responses):
    state = {"i": 0, "calls": 0}

    def fake(prompt, model_id, params=None, sensitive=False):
        state["calls"] += 1
        r = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return r
    return fake, state


def _with_llm(fake, fn):
    orig = vc.llm_call_model
    vc.llm_call_model = fake
    try:
        return fn()
    finally:
        vc.llm_call_model = orig


def test_majority_wins_and_records_spread():
    """2 of 3 draws agree -> that value is stored, and the split is recorded."""
    fake, state = _script(['{"act_type": "assertive"}',
                           '{"act_type": "directive"}',
                           '{"act_type": "assertive"}'])
    r = _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG, votes=3))
    assert r["act_type"] == "assertive", r
    v = r["_votes"]
    assert v["n"] == 3 and v["agreed"] == 2 and v["unanimous"] is False, v
    assert v["distribution"]["act_type"] == {"assertive": 2, "directive": 1}, v
    assert state["calls"] == 3, state
    print("  ok   majority wins; spread recorded in _votes")


def test_unanimous_is_flagged():
    fake, _ = _script(['{"act_type": "assertive"}'])
    r = _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG, votes=3))
    assert r["_votes"]["unanimous"] is True and r["_votes"]["agreed"] == 3
    print("  ok   unanimous draws flagged unanimous")


def test_winner_is_a_real_draw_not_an_assembly():
    """The stored block must be one draw, never a per-field Frankenstein.

    The legal re-read caught cooperative returning status=honored WITH a maxim
    named — individually legal, jointly incoherent. Field-wise assembly would
    manufacture that pairing whenever the two fields' pluralities disagree.
    """
    draws = [{"status": "honored", "maxim_violated": None},
             {"status": "violated", "maxim_violated": "quality"},
             {"status": "violated", "maxim_violated": "manner"}]
    idx, rec = modal_choice(
        draws, lambda d: (("status", d["status"]),
                          ("maxim_violated", d["maxim_violated"])))
    winner = draws[idx]
    assert winner in draws
    # status plurality is 'violated'; maxim plurality is None (1 each otherwise).
    # An assembly would emit violated + None. A real draw never pairs those here.
    assert not (winner["status"] == "violated" and winner["maxim_violated"] is None), \
        f"assembled an incoherent block: {winner}"
    print(f"  ok   winner is a real draw ({winner['status']}/{winner['maxim_violated']}),"
          f" not an assembly")


def test_failed_draw_is_dropped_not_fatal():
    """One invalid draw among valid ones: vote proceeds on the survivors."""
    fake, _ = _script(['{"act_type": "assertive"}',
                       '{"act_type": "NOT_AN_ENUM"}',   # fails, retried, dropped
                       '{"act_type": "NOT_AN_ENUM"}',
                       '{"act_type": "NOT_AN_ENUM"}',
                       '{"act_type": "assertive"}'])
    r = _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG, votes=3))
    assert r["act_type"] == "assertive"
    assert r["_votes"]["quarantined"] >= 1, r["_votes"]
    print(f"  ok   invalid draw dropped, vote survived "
          f"({r['_votes']['n']} usable, {r['_votes']['quarantined']} quarantined)")


def test_all_draws_failing_still_raises():
    fake, _ = _script(['{"act_type": "NOT_AN_ENUM"}'])
    try:
        _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG, votes=3))
    except CoordinateValidationError:
        print("  ok   all draws invalid -> fails closed, as before")
    else:
        raise AssertionError("should have raised")


def test_votes_1_is_single_draw():
    fake, state = _script(['{"act_type": "assertive"}'])
    r = _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG, votes=1))
    assert state["calls"] == 1, state
    assert "_votes" not in r, "votes=1 must behave exactly like call_and_validate"
    print("  ok   votes=1 is a single draw, no _votes stamp")


def test_env_controls_vote_count():
    prev = os.environ.get("VIVIFY_VOTES")
    try:
        os.environ["VIVIFY_VOTES"] = "2"
        fake, state = _script(['{"act_type": "assertive"}'])
        _with_llm(fake, lambda: call_and_vote("p", "act_type",
                                              capability="logos_operator",
                                              config_dir=CONFIG))
        assert state["calls"] == 2, state
        print("  ok   VIVIFY_VOTES controls the draw count")
    finally:
        if prev is None:
            os.environ.pop("VIVIFY_VOTES", None)
        else:
            os.environ["VIVIFY_VOTES"] = prev


def test_structural_scale_is_gated():
    ok = {"scale": "institution", "density": "archival", "persistence": "durable",
          "authority": "formal", "transmission": "archive",
          "memory_channel": "institutional", "language_mode": "formalized"}
    assert validate_coordinates(dict(ok), "structural", CONFIG)["scale"] == "institution"

    bad = dict(ok, scale="bureaucratic")     # a density value leaking into scale
    try:
        validate_coordinates(bad, "structural", CONFIG)
    except CoordinateValidationError:
        pass
    else:
        raise AssertionError("out-of-enum scale must be rejected, not coerced silently")

    absent = {k: v for k, v in ok.items() if k != "scale"}
    absent["layer"] = "global"
    validate_coordinates(absent, "structural", CONFIG)   # must not raise
    print("  ok   scale gated (valid ok, invalid rejected, absent ok for layer fallback)")


def test_gate_cannot_catch_the_instability():
    """The thing voting exists for: both sides of the observed flip are LEGAL.

    global -> institution is what actually happened between sessions. If the gate
    could reject it, voting would be unnecessary; it cannot, which is the argument
    for the vote.
    """
    base = {"density": "archival", "persistence": "durable", "authority": "formal",
            "transmission": "archive", "memory_channel": "institutional",
            "language_mode": "formalized"}
    for scale in ("global", "institution"):
        validate_coordinates(dict(base, scale=scale), "structural", CONFIG)
    print("  ok   both sides of the observed flip pass the gate — voting is the fix")


if __name__ == "__main__":
    test_majority_wins_and_records_spread()
    test_unanimous_is_flagged()
    test_winner_is_a_real_draw_not_an_assembly()
    test_failed_draw_is_dropped_not_fatal()
    test_all_draws_failing_still_raises()
    test_votes_1_is_single_draw()
    test_env_controls_vote_count()
    test_structural_scale_is_gated()
    test_gate_cannot_catch_the_instability()
    print("\nAll repeat-and-vote checks passed.")

# llm: claude-opus-5 | 2026-09-05 | repos/vivify-operators/tests/test_repeat_and_vote.py | created — guards repeat-and-vote (modal draw not field-wise assembly, spread recorded, failed draws dropped, votes=1 unchanged) and the newly gated structural.scale, including that the gate CANNOT catch the flip voting exists for
