#!/usr/bin/env python3
"""Focused test: call_and_validate() retries on invalid/malformed operator output
and fails closed after exhausting retries — the recovery path for the small local
model so a recoverable miss isn't silently dropped as a missing dimension.

No real LLM calls — vivify_core.llm_call_model is monkeypatched to a scripted
sequence of responses. Validates against the real config/coordinates.json
(act_type enum).

Run standalone: python3 tests/test_retry_validation.py  (exit 0 = pass)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import vivify_core as vc
from vivify_core import call_and_validate, CoordinateValidationError, LLMUnavailable

CONFIG = str(ROOT / "config")
BAD = '{"act_type": "NOT_A_REAL_ENUM"}'   # out of the act_type enum -> rejected
GOOD = '{"act_type": "assertive"}'        # in the act_type enum -> accepted


def _script(responses):
    """Return a fake llm_call_model yielding responses in order (Exception -> raised),
    plus a state dict counting calls. The last response repeats if over-consumed.

    call_and_validate resolves the model once up front (so the result can record
    which model produced it) and calls llm_call_model directly — that is the seam."""
    state = {"i": 0, "calls": 0}

    def fake(prompt, model_id, params=None, sensitive=False):
        state["calls"] += 1
        r = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        if isinstance(r, Exception):
            raise r
        return r

    return fake, state


def _with_llm(fake, fn):
    """Run fn() with vc.llm_call_model swapped for fake, always restoring the original."""
    orig = vc.llm_call_model
    vc.llm_call_model = fake
    try:
        return fn()
    finally:
        vc.llm_call_model = orig


def test_retry_recovers_after_invalid():
    """First response is out-of-enum, second is valid -> returns valid in 2 calls."""
    fake, state = _script([BAD, GOOD])

    def run():
        result = call_and_validate("p", "act_type", capability="logos_operator",
                                   config_dir=CONFIG)
        assert result["act_type"] == "assertive", result
        assert state["calls"] == 2, state

    _with_llm(fake, run)


def test_retry_exhausts_then_raises():
    """All responses invalid -> CoordinateValidationError after retries+1 calls."""
    fake, state = _script([BAD])

    def run():
        try:
            call_and_validate("p", "act_type", capability="logos_operator",
                              retries=2, config_dir=CONFIG)
        except CoordinateValidationError:
            assert state["calls"] == 3, state  # 1 initial + 2 retries
            return
        raise AssertionError("expected CoordinateValidationError after exhausting retries")

    _with_llm(fake, run)


def test_malformed_json_is_retried():
    """Broken JSON (not just bad enum) is also retried, then recovers."""
    fake, state = _script(["not json at all {{{", GOOD])

    def run():
        result = call_and_validate("p", "act_type", capability="logos_operator",
                                   config_dir=CONFIG)
        assert result["act_type"] == "assertive", result
        assert state["calls"] == 2, state

    _with_llm(fake, run)


def test_llm_unavailable_not_retried():
    """LLMUnavailable propagates immediately — transport-down is fatal, no retry."""
    fake, state = _script([LLMUnavailable("quota")])

    def run():
        try:
            call_and_validate("p", "act_type", capability="logos_operator",
                              config_dir=CONFIG)
        except LLMUnavailable:
            assert state["calls"] == 1, state
            return
        raise AssertionError("expected LLMUnavailable to propagate without retry")

    _with_llm(fake, run)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tests/test_retry_validation.py | new: proves call_and_validate() retries CoordinateValidationError + malformed JSON, fails closed after exhausting, and never retries LLMUnavailable
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tests/test_retry_validation.py | patch seam moved llm_call -> llm_call_model (call_and_validate now resolves the model up front)
