#!/usr/bin/env python3
"""Focused test: tag_store.py resume/skip/fail-fast logic, with the LLM-bearing
passes (logos_fused, conflict_operator) stubbed — no real calls. Proves the driver
behaviors that keep a quota runout from corrupting the store:

  - skip an already-complete inference;
  - RESUME: if only conflict is missing, the fused logos call is NOT re-made;
  - FAIL-FAST: LLMUnavailable propagates (so main() can exit 3) and earlier progress
    is already on disk;
  - a per-inference content error is recorded, not fatal;
  - the completeness manifest reflects complete vs incomplete.

Run standalone: python3 tests/test_tag_store.py  (exit 0 = pass)
"""
import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import tag_store as ts
from vivify_core import LLMUnavailable, CoordinateValidationError, read_json

LOGOS_BLOCK = {k: {"_operator": f"{k}.py"} for k in ts.LOGOS_KEYS}
CONFLICT_BLOCK = {k: "none" for k in ts.CONFLICT_KEYS}


def _stub_logos(calls):
    def run(inf, retries=2):
        calls.append("logos")
        inf.setdefault("logos", {}).update(LOGOS_BLOCK)
        inf["logos"]["_runner"] = "logos_fused.py"
        return inf
    return run


def _stub_conflict(calls, fail=None):
    def run(inf):
        calls.append("conflict")
        if fail:
            raise fail
        inf.setdefault("conflict", {}).update(CONFLICT_BLOCK)
        return inf
    return run


def _write(path, **extra):
    inf = {"id": path.stem, "raw_text": "some text"}
    inf.update(extra)
    path.write_text(json.dumps(inf))


def _patch(logos_run, conflict_run):
    ts.logos_fused.run = logos_run
    ts.conflict_operator.run = conflict_run


def test_full_tag_then_skip():
    """Untagged inference -> complete; second pass -> skipped, no calls made."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "inf_a.json"
        _write(p)
        calls = []
        _patch(_stub_logos(calls), _stub_conflict(calls))
        assert ts.tag_one(p) == "complete", "first pass should complete"
        assert calls == ["logos", "conflict"], calls
        inf = read_json(p)
        assert ts.is_complete(inf) and inf["_tagged"]["complete"] is True
        calls.clear()
        assert ts.tag_one(p) == "skipped", "already-complete -> skipped"
        assert calls == [], "skip must make no LLM calls"


def test_resume_skips_logos_call():
    """Inference with logos done but conflict missing -> only conflict runs."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "inf_b.json"
        _write(p, logos={**LOGOS_BLOCK, "_runner": "logos_fused.py"})
        calls = []
        _patch(_stub_logos(calls), _stub_conflict(calls))
        assert ts.tag_one(p) == "complete"
        assert calls == ["conflict"], f"logos should be skipped on resume, got {calls}"


def test_fail_fast_preserves_progress():
    """conflict raises LLMUnavailable -> tag_one re-raises, logos already on disk."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "inf_c.json"
        _write(p)
        calls = []
        _patch(_stub_logos(calls), _stub_conflict(calls, fail=LLMUnavailable("quota")))
        try:
            ts.tag_one(p)
        except LLMUnavailable:
            inf = read_json(p)
            assert ts.logos_complete(inf), "logos must be persisted before conflict failed"
            assert not ts.conflict_complete(inf)
            return
        raise AssertionError("expected LLMUnavailable to propagate (fail-fast)")


def test_content_error_recorded_not_fatal():
    """A validation failure in logos is recorded and returned, never raised."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "inf_d.json"
        _write(p)

        def bad_logos(inf, retries=2):
            raise CoordinateValidationError("never legal")
        _patch(bad_logos, _stub_conflict([]))
        status = ts.tag_one(p)
        assert status.startswith("error:"), status
        inf = read_json(p)
        assert inf["logos"]["_errors"]["tag_store"], "error must be recorded on the inference"
        assert inf["_tagged"]["complete"] is False


def test_manifest_counts():
    """Manifest separates complete vs incomplete across the store."""
    with tempfile.TemporaryDirectory() as d:
        store = Path(d)
        rows = [
            {"id": "inf_1", "status": "complete"},
            {"id": "inf_2", "status": "skipped"},
            {"id": "inf_3", "status": "error: incomplete after tagging"},
        ]
        m = ts.write_manifest(store, rows)
        assert m["total"] == 3 and m["complete"] == 2 and m["incomplete"] == 1, m
        assert (store / ts.MANIFEST_NAME).exists()
        assert m["incomplete_ids"][0]["id"] == "inf_3"


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

# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/tests/test_tag_store.py | new: proves tag_store resume (skips logos call when only conflict missing), skip-if-complete, fail-fast on LLMUnavailable with progress preserved, content-error recorded-not-fatal, manifest counts
