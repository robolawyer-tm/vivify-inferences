#!/usr/bin/env python3
"""Focused test: claim_check's guards actually fire.

claim_check adjudicates extracted claims against a named baseline. Its value
rests entirely on three behaviours that are invisible when they work:

  - the grounding guard downgrades a verdict whose evidence is not really in
    the baseline (an adjudicator that invents evidence is the silent-failure
    class this codebase keeps meeting: a glob that matches nothing and reports
    zero, a validation gate that goes empty and disables itself)
  - normalisation bridges the glyphs that differ between a model's prose and
    the source: Gemini wrote U+2212 MINUS, tension_score.py writes ASCII '-',
    and a literal comparison would have dropped the one true finding
  - emptiness is loud: no claims, no baseline, or a truncated baseline must
    announce themselves rather than returning a clean-looking zero

None of these can be observed from a passing run, so they are exercised here
with a stubbed adjudicator. No LLM calls. No network.

Run standalone: python3 tests/test_claim_check.py  (exit 0 = pass)
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
os.chdir(ROOT)

import claim_check

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        failures.append(label)
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def stub(verdict, evidence, reason="stubbed"):
    """Replace the single LLM call with a fixed answer."""
    def _adj(topic, claim, baseline, model):
        return {"verdict": verdict, "evidence": evidence, "reason": reason}
    return _adj


# FIXTURE: known-false formula strings — the superseded lexical tension score,
# kept verbatim because the glyph pair below is the real one that nearly hid the
# only true finding. test_docs_match_code.FIXTURE_FILES exempts this file.
BASELINE = "The score is 1.0 - (shared_keywords / total_unique_keywords) today."
CLAIM = {"value": "1.0−(shared keywords/total unique keywords)",
         "unit": "formula", "quote": "Calculated as 1.0−(shared...)"}

original = claim_check.adjudicate_once
print("claim_check guards:")

# 1. evidence genuinely present -> verdict survives
claim_check.adjudicate_once = stub("contradicted", "The score is 1.0 - (shared_keywords")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("grounded evidence keeps its verdict", r["verdict"] == "contradicted", r["verdict"])
check("grounded evidence drops no draws", r["_ungrounded_draws"] == 0)

# 2. evidence invented -> downgraded, and the downgrade is counted
claim_check.adjudicate_once = stub("contradicted", "a sentence never written anywhere")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("invented evidence is downgraded", r["verdict"] == "unverifiable", r["verdict"])
check("every invented draw is counted", r["_ungrounded_draws"] == 3,
      f"counted {r['_ungrounded_draws']}")
check("the downgrade says why", "not found in baseline" in r["reason"])

# 3. empty evidence cannot carry a verdict
claim_check.adjudicate_once = stub("holds", "")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("empty evidence is downgraded", r["verdict"] == "unverifiable", r["verdict"])

# 4. unverifiable needs no evidence — the guard must not punish an honest abstention
claim_check.adjudicate_once = stub("unverifiable", "")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("honest abstention is left alone", r["verdict"] == "unverifiable"
      and r["_ungrounded_draws"] == 0)

# 5. a bad verdict string falls to unverifiable, never to a guess
claim_check.adjudicate_once = stub("BANANA", "The score is 1.0")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("unknown verdict falls back to unverifiable", r["verdict"] == "unverifiable")

# 6. every claim carries its own _votes — per-claim, never per-block
claim_check.adjudicate_once = stub("holds", "The score is 1.0")
r = claim_check.check_claim("t", CLAIM, BASELINE, claim_check._norm(BASELINE), "m", 3)
check("claims carry per-claim _votes", r["_votes"]["n"] == 3 and r["_votes"]["unanimous"])

claim_check.adjudicate_once = original

# 7. the glyph that would have hidden the one real finding
minus = "1.0−(shared keywords/total unique keywords)"
ascii_ = "1.0 - (shared_keywords / total_unique_keywords)"
check("U+2212 minus normalises to ASCII hyphen",
      claim_check._norm("a − b") == claim_check._norm("a - b"))
check("en/em dashes normalise too",
      claim_check._norm("a – b") == claim_check._norm("a — b"))
check("whitespace runs collapse", claim_check._norm("a \n\t  b") == "a b")
check("the real-world glyph pair is not falsely equal",
      claim_check._norm(minus) != claim_check._norm(ascii_),
      "normalisation must not erase the underscore/space difference")

# 8. emptiness is loud, never a clean-looking zero
with tempfile.TemporaryDirectory() as td:
    empty = Path(td) / "inf.json"
    empty.write_text('{"id": "inf_test", "source": "t", "right_facts": {}}')
    err = io.StringIO()
    with redirect_stderr(err):
        rep = claim_check.run(str(empty), [str(ROOT / "README.md")])
    check("no claims announces itself", "NO CLAIMS" in err.getvalue())
    check("no claims yields an empty, honest report", rep["claims_checked"] == 0)

    err = io.StringIO()
    with redirect_stderr(err):
        claim_check.run(str(empty), [str(Path(td) / "nope.md")])
    check("a missing baseline file is reported", "baseline missing" in err.getvalue())
    check("an empty baseline announces itself", "NO BASELINE" in err.getvalue())

# 9. truncation is reported — a baseline that lost its tail would make every
#    claim about the tail 'unverifiable' and look like a result
with tempfile.TemporaryDirectory() as td:
    big = Path(td) / "big.md"
    big.write_text("x" * (claim_check.BASELINE_CHAR_CAP + 5000))
    err = io.StringIO()
    with redirect_stderr(err):
        text, manifest, truncated = claim_check.load_baseline([str(big)])
    check("oversized baseline is truncated", truncated and
          len(text) == claim_check.BASELINE_CHAR_CAP)
    check("truncation announces itself", "BASELINE TRUNCATED" in err.getvalue())
    check("baseline manifest records a hash", manifest[0]["sha256"]
          and len(manifest[0]["sha256"]) == 16)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All claim_check guard checks passed.")

# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/tests/test_claim_check.py | created — exercises the grounding guard, glyph normalisation, and loud-emptiness behaviours that a passing run cannot demonstrate
