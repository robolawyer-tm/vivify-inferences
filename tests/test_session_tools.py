#!/usr/bin/env python3
"""Focused test: the migrated session tools call the shared, gated transport.

Regression guard for the 2026-08-31 migration from vivify-inferences. Both extract
tools previously ran their own `subprocess.run(["claude", "-p", ...])`, which bypassed
config/model_map.json AND the privacy gate — the same defect fixed in vivify.py's left
pass on 2026-08-13. This asserts they now go through vivify_core.llm_call under the
session_extraction capability, that the folded-in system frame leads the prompt, and
that LLMUnavailable reaches main() rather than being swallowed.

Also pins the subprocess contract with vivify.py (--source/--dir), which is how both
tools hand blocks to the left pass.

No real LLM calls — llm_call is monkeypatched. Deliberately does NOT chdir, so config
resolution is exercised from the caller's cwd (see test_config_cwd_independence.py).

Run standalone: python3 tests/test_session_tools.py  (exit 0 = pass)
"""
import sys
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import vivify_core
from vivify_core import LLMUnavailable, resolve_model

EXTRACT_TOOLS = ("session_extract", "session_extract_op")
STDLIB_TOOLS = ("session_to_chat", "inf_to_md", "jsonl_to_md")

FAKE_RESPONSE = "First development.\n---INFERENCE---\nSecond development.\n---INFERENCE---\n  \n"


def test_capability_is_mapped():
    """session_extraction must be a real model_map entry, not the 'default' fallback.

    resolve_model() falls back to 'default' for an unknown capability, so a passing
    resolve alone proves nothing — the key itself has to be there.
    """
    from vivify_core import read_json, _config_path
    model_map = read_json(_config_path("config", "model_map.json"))
    assert "session_extraction" in model_map, \
        "config/model_map.json has no session_extraction entry — the tools would " \
        "silently fall back to 'default'"
    model = resolve_model("session_extraction")
    assert model == model_map["session_extraction"], \
        f"resolve_model gave {model!r}, map says {model_map['session_extraction']!r}"
    print(f"  ok   session_extraction is a mapped entry -> {model}")


def test_extract_tools_use_shared_transport():
    for name in EXTRACT_TOOLS:
        mod = importlib.import_module(name)
        calls = []

        def fake(prompt, capability="default", **kw):
            calls.append({"capability": capability, "prompt": prompt, "kw": kw})
            return FAKE_RESPONSE

        mod.llm_call = fake
        blocks = mod.extract_inferences("a transcript about porting tools")

        assert len(calls) == 1, f"{name}: {len(calls)} llm calls, expected 1"
        call = calls[0]
        assert call["capability"] == "session_extraction", \
            f"{name}: capability {call['capability']!r} — must route through model_map"
        assert call["prompt"].startswith(mod.SYSTEM_FRAME), \
            f"{name}: system frame not folded into the prompt head"
        assert "a transcript about porting tools" in call["prompt"], \
            f"{name}: transcript never reached the prompt"
        assert not call["kw"].get("sensitive"), \
            f"{name}: sensitive must stay False — 'claude' is not in LOCAL_BACKENDS, " \
            f"so a sensitive call would be blocked outright"
        assert blocks == ["First development.", "Second development."], \
            f"{name}: separator split -> {blocks}"
        print(f"  ok   {name}: gated transport, frame prepended, {len(blocks)} blocks")


def test_llm_unavailable_propagates():
    """A dead model must surface as an error, not an empty extraction."""
    for name in EXTRACT_TOOLS:
        mod = importlib.import_module(name)

        def boom(prompt, capability="default", **kw):
            raise LLMUnavailable("model down")

        mod.llm_call = boom
        try:
            mod.extract_inferences("x")
        except LLMUnavailable:
            print(f"  ok   {name}: LLMUnavailable propagates to main()")
        else:
            raise AssertionError(f"{name}: LLMUnavailable was swallowed")


def test_vivify_subprocess_contract():
    """Both tools shell out to vivify.py with --source/--dir; pin those flags."""
    vivify_py = ROOT / "vivify.py"
    assert vivify_py.exists(), "vivify.py is gone — both session tools shell out to it"
    source = vivify_py.read_text()
    for flag in ('"--source"', '"--dir"'):
        assert flag in source, \
            f"vivify.py no longer accepts {flag} — the session tools invoke it with these"
    print("  ok   vivify.py still accepts --source and --dir")


def test_all_tools_importable():
    """Every migrated tool must import cleanly from the repo root."""
    for name in EXTRACT_TOOLS + STDLIB_TOOLS:
        importlib.import_module(name)
    print(f"  ok   all {len(EXTRACT_TOOLS + STDLIB_TOOLS)} migrated tools import")


if __name__ == "__main__":
    test_capability_is_mapped()
    test_all_tools_importable()
    test_extract_tools_use_shared_transport()
    test_llm_unavailable_propagates()
    test_vivify_subprocess_contract()
    print("\nAll session-tool migration checks passed.")

# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/tests/test_session_tools.py | created — regression guard for the session-tool migration: extract tools must use the gated llm_call under session_extraction, not their own claude -p subprocess
