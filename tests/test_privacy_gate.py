#!/usr/bin/env python3
"""Focused test: the privacy gate blocks sensitivity-tagged data from leaving the box.

Proves the single enforcement point (_enforce_privacy_gate) and its wiring through
llm_call_model behave per non-negotiables #1/#2, and that all operators pass
sensitive=True so the gate can actually protect their field data. No real LLM calls —
transports are monkeypatched so only the gate decision is exercised.

Run standalone: python3 tests/test_privacy_gate.py  (exit 0 = pass)
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import vivify_core as vc
from vivify_core import PrivacyGateError, llm_call_model, _enforce_privacy_gate


def _gate(state):
    """Set PRIVACY_GATE env to a known state for one assertion."""
    if state is None:
        os.environ.pop("PRIVACY_GATE", None)
    else:
        os.environ["PRIVACY_GATE"] = state


def test_gate_blocks_sensitive_remote():
    """Gate on + sensitive + remote backend -> blocked."""
    _gate("on")
    try:
        _enforce_privacy_gate("claude", sensitive=True)
    except PrivacyGateError:
        return
    raise AssertionError("expected PrivacyGateError for sensitive call to remote claude")


def test_gate_allows_local():
    """Gate on + sensitive + local backend -> allowed (no raise)."""
    _gate("on")
    for backend in vc.LOCAL_BACKENDS:
        _enforce_privacy_gate(backend, sensitive=True)  # must not raise


def test_gate_allows_nonsensitive():
    """Gate on + remote but NOT sensitive -> allowed."""
    _gate("on")
    _enforce_privacy_gate("claude", sensitive=False)  # must not raise


def test_gate_off_is_relaxed():
    """Gate EXPLICITLY off (the dev opt-out) -> sensitive remote call passes."""
    _gate("off")
    _enforce_privacy_gate("claude", sensitive=True)  # must not raise


def test_gate_unset_fails_closed():
    """Gate UNSET (the forgot-to-set case) -> sensitive remote call BLOCKED.
    The safe default: absence of a decision protects the data, never leaks it.
    Only an explicit PRIVACY_GATE=off relaxes the gate."""
    _gate(None)
    try:
        _enforce_privacy_gate("claude", sensitive=True)
    except PrivacyGateError:
        return
    raise AssertionError("expected PrivacyGateError when PRIVACY_GATE is unset")


def test_gate_garbage_fails_closed():
    """An unrecognized PRIVACY_GATE value is treated as unset -> blocked, not relaxed."""
    _gate("maybe")
    try:
        _enforce_privacy_gate("claude", sensitive=True)
    except PrivacyGateError:
        return
    raise AssertionError("expected PrivacyGateError for unrecognized PRIVACY_GATE value")


def test_llm_call_model_enforces_before_transport():
    """The gate fires inside llm_call_model BEFORE any transport runs."""
    _gate("on")
    called = {"hit": False}

    def spy(prompt, model, params):
        called["hit"] = True
        return "{}"

    orig = vc.TRANSPORTS.get("claude")
    vc.TRANSPORTS["claude"] = spy
    try:
        try:
            llm_call_model("hi", "claude-haiku-4-5-20251001", sensitive=True)
        except PrivacyGateError:
            assert not called["hit"], "transport ran before the gate blocked it"
            return
        raise AssertionError("expected PrivacyGateError; transport should never run")
    finally:
        if orig is not None:
            vc.TRANSPORTS["claude"] = orig


def test_all_operators_pass_sensitive():
    """Contract: every operator that calls an LLM passes sensitive=True so the gate
    can protect its field data. Covers BOTH entry points — the bare llm_call and the
    retry wrapper call_and_validate. Guards against a new operator skipping the flag."""
    missing = []
    checked = []
    for op in sorted(ROOT.glob("*_operator.py")):
        src = op.read_text()
        if "llm_call(" not in src and "call_and_validate(" not in src:
            continue
        checked.append(op.name)
        if "sensitive=True" not in src:
            missing.append(op.name)
    assert checked, "no operators exercised the LLM-call contract — wrong call-site match?"
    assert not missing, f"operators missing sensitive=True on the LLM call: {missing}"


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
    _gate(None)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/tests/test_privacy_gate.py | new: focused test proving privacy gate blocks sensitive remote calls + all-operators-pass-sensitive contract
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tests/test_privacy_gate.py | added unset/garbage fail-closed cases — safe-default gate blocks sensitive off-box calls unless PRIVACY_GATE is explicitly off
