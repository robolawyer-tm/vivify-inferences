#!/usr/bin/env python3
"""Focused test: case_id keeps two tellings of one case from voting twice.

The store must be able to hold the same case more than once — a second telling
from a different source document is how source-sensitivity gets measured. Per-text
scoring stays per-text; what must NOT double is the store-level aggregate. This
proves the three places that changes: case_key() identity, cross_scale link
eligibility (incl. information weights), and the calibration gradient.

No LLM calls, no store writes — fixtures are built in a temp dir.

Run standalone: python3 tests/test_case_id.py  (exit 0 = pass)
"""
import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from inference import new_inference, case_key, is_canonical

import cross_scale
import tension_score

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}  {detail}")
        failures.append(label)


def tagged(case_id, scale, resonance, behavior, delta=None, timestamp=None,
           canonical=None):
    """A minimal inference carrying just the fields the two consumers read."""
    inf = new_inference("fixture text", source="innocence_project", case_id=case_id)
    if canonical is not None:
        inf["canonical"] = canonical
    inf["logos"] = {
        "structural": {"scale": scale},
        "resonance": {"value": resonance},
        "cooperative": {"status": "violated"},
    }
    inf["conflict"] = {"schema": "entangled", "behavior": behavior, "terrain": "fringe"}
    inf["tension_score"] = 0.8
    if delta is not None:
        inf["tension"] = {"predicted": 0.8, "confirmed": 0.8 - delta,
                          "calibration_delta": delta}
    if timestamp:
        inf["timestamp"] = timestamp
    return inf


def write_store(inferences):
    """Write fixtures to a temp inferences dir; returns the Path."""
    tmp = Path(tempfile.mkdtemp(prefix="case_id_test_"))
    for inf in inferences:
        (tmp / f"{inf['id']}.json").write_text(json.dumps(inf, indent=2))
    return tmp


# --- case_key identity -------------------------------------------------------

print("case_key():")

untagged = new_inference("stands alone")
check("untagged inference is its own case",
      case_key(untagged) == untagged["id"], case_key(untagged))

a = new_inference("telling one", case_id="earl_washington_jr")
b = new_inference("telling two", case_id="earl_washington_jr")
check("two tellings share a case key", case_key(a) == case_key(b))
check("two tellings keep distinct ids", a["id"] != b["id"])

c = new_inference("other case", case_id="josiah_sutton")
check("different cases do not collide", case_key(a) != case_key(c))

check("case_id defaults to None", untagged["case_id"] is None)

# --- cross_scale link eligibility --------------------------------------------

print("\ncross_scale:")

# Same case, told twice, landing on DIFFERENT scales — the pair the old
# same-scale guard would have let through, with an identical signature.
variants = [
    tagged("earl_washington_jr", "institution", "illusion", "suppression"),
    tagged("earl_washington_jr", "individual", "illusion", "suppression"),
]
store = write_store(variants)
usable, _ = cross_scale.load_signed(store)
check("both variants are usable", len(usable) == 2, f"got {len(usable)}")

links = cross_scale.find_links(usable, threshold=2)
check("same-case pair produces no link", links == [], f"got {len(links)} link(s)")

count, _ = cross_scale.isomorphism(usable[0], usable[1])
check("isomorphism() rejects same case", count == 0, f"got {count}")

# A genuine cross-scale pair still links, with a variant of one of them present.
mixed = variants + [tagged("josiah_sutton", "individual", "illusion", "suppression")]
usable, _ = cross_scale.load_signed(write_store(mixed))
links = cross_scale.find_links(usable, threshold=2)
pairs = {frozenset(i["id"] for i in link["inferences"]) for link in links}
check("genuine cross-case link survives", len(links) == 1, f"got {len(links)}")
check("the surviving link crosses cases",
      links and len({u["case"] for u in usable
                     if u["id"] in list(pairs)[0]}) == 2 if links else False)

# Information weights: the duplicated case must not make its own values look
# twice as common. All three fixtures share resonance=illusion, but only two
# CASES do — so the weight must be -log(2/2) = 0, not -log(3/3) computed over a
# store where one case was counted twice.
weights = cross_scale.info_weights(usable)
n_cases = len({u["case"] for u in usable})
check("weights are counted over cases, not inferences",
      n_cases == 2, f"got {n_cases} cases from {len(usable)} inferences")
check("shared-by-all-cases value carries no signal",
      abs(weights[("resonance", "illusion")]) < 1e-9,
      weights[("resonance", "illusion")])

# --- calibration gradient ----------------------------------------------------

print("\ncalibration gradient:")

points, excluded = tension_score.gradient(write_store([
    tagged("earl_washington_jr", "institution", "illusion", "suppression",
           delta=0.392, timestamp="2026-07-13T10:00:00+00:00"),
    tagged("earl_washington_jr", "institution", "illusion", "suppression",
           delta=0.120, timestamp="2026-08-20T10:00:00+00:00"),
    tagged("josiah_sutton", "individual", "illusion", "suppression",
           delta=0.133, timestamp="2026-07-13T11:00:00+00:00"),
]))
check("one gradient point per case", len(points) == 2, f"got {len(points)}")
check("one variant excluded", len(excluded) == 1, f"got {len(excluded)}")
check("canonical telling is the earliest",
      all(p["delta"] in (0.392, 0.133) for p in points),
      [p["delta"] for p in points])
check("excluded telling is the later one",
      excluded and excluded[0]["delta"] == 0.120)

# Untagged inferences must each stand as their own gradient point.
points, excluded = tension_score.gradient(write_store([
    tagged(None, "institution", "illusion", "suppression", delta=0.4),
    tagged(None, "institution", "illusion", "suppression", delta=0.5),
]))
check("untagged inferences are independent points", len(points) == 2, f"got {len(points)}")
check("nothing excluded when untagged", excluded == [], excluded)

# An explicit canonical mark beats arrival order — the case that motivated the
# field: the LATER telling came from the cleaner source, so it must be the point.
points, excluded = tension_score.gradient(write_store([
    tagged("ronald_cotton", "global", "illusion", "suppression",
           delta=0.3759, timestamp="2026-08-13T14:10:25+00:00"),
    tagged("ronald_cotton", "global", "illusion", "suppression",
           delta=0.4780, timestamp="2026-08-13T14:26:59+00:00", canonical=True),
]))
check("marked telling wins over the earlier one",
      len(points) == 1 and points[0]["delta"] == 0.4780,
      [p["delta"] for p in points])
check("the unmarked earlier telling becomes the variant",
      len(excluded) == 1 and excluded[0]["delta"] == 0.3759,
      [e["delta"] for e in excluded])

check("is_canonical: absent means unchosen, not false",
      is_canonical({}) is False and is_canonical({"canonical": True}) is True)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All case_id checks passed.")

# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tests/test_case_id.py | created — case_key identity, cross_scale same-case exclusion + case-counted weights, gradient variant dedup
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/tests/test_case_id.py | canonical-mark cases: later marked telling wins, earlier becomes variant, absent != false
