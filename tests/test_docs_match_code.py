#!/usr/bin/env python3
"""Focused test: no document may restate the superseded lexical tension formula.

Regression guard, written after the failure it guards against. tension_score.py
was rewired on 2026-07-13 to three numbers — predicted / confirmed /
calibration_delta — because the original lexical score,

    1.0 - (shared_keywords / total_unique_keywords)

pinned at 1.0 storewide: the left and right vocabularies are disjoint by design,
so their intersection is empty by construction and the score carried no
information.

The code changed. Four documents did not. On 2026-09-15 an ingest bundle went to
three outside models; two of them read the stale documents rather than the
docstring and handed the dead formula back. One spent its longest section
re-deriving, correctly, why a formula that no longer exists cannot work. The
other quoted it approvingly as the project's "Core Insight". The instrument was
right and every description of it was wrong, and nothing in the repo noticed.

Instances found and closed on 2026-09-16:
  - README.md:14 and :98-109   (intro claim + the full formula section)
  - lib/keyword_graph.py:80    (orphaned implementation, imported by nothing)
  - FLOW.md                    (untracked May-8 copy of the retired repo's; deleted)
  - pillars/FLOW.md:17,41,51   (the declared source of truth the others derived from)

One deliberate mention survives: README.md's "Superseded — do not reintroduce"
paragraph, which keeps the dead formula visible with the reason it died. Deleting
it silently would leave the next reader free to re-derive it, which is exactly
what happened. That line is allowlisted by its marker.

Scope limit, stated rather than hidden: this scans THIS repo only. pillars/FLOW.md
was the root instance and lives in a sibling repo, so it is not covered here — a
test that reached across repos would fail for anyone who cloned only this one.

No LLM calls. No network. Pure filesystem scan.

Run standalone: python3 tests/test_docs_match_code.py  (exit 0 = pass)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

# The formula in every spelling it has actually appeared in: with and without
# the _keywords suffix, with and without parens, spaces or underscores as the
# word separator. Anchored on "1.0 -" followed by a shared/total ratio.
DEAD_FORMULA = re.compile(
    r"1\.0\s*[-−]\s*\(?\s*shared[ _]?(?:keywords)?\s*/\s*total[ _]?unique",
    re.IGNORECASE,
)

# The one sanctioned mention. A line carrying this marker may name the formula.
ALLOW_MARKER = "Superseded — do not reintroduce"

SKIP_DIRS = {".git", "__pycache__", "inferences", "experiments", ".claude"}
SCAN_SUFFIXES = {".md", ".py", ".json", ".txt"}

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        failures.append(label)
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def scan_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        if path.resolve() == SELF:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        yield path


print("no document restates the superseded lexical tension formula:")

# 1. the formula appears nowhere except the allowlisted Superseded note
offenders = []
allowed = 0
for path in scan_files():
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        continue
    for n, line in enumerate(lines, 1):
        if DEAD_FORMULA.search(line):
            if ALLOW_MARKER in line:
                allowed += 1
            else:
                offenders.append(f"{path.relative_to(ROOT)}:{n}")

check("formula absent outside the Superseded note",
      not offenders,
      f"found in {', '.join(offenders)}" if offenders else "")

# 2. the Superseded note itself is still there — the guard is worthless if the
#    deliberate mention was quietly deleted along with the accidental ones
check("the Superseded note still carries the dead formula",
      allowed == 1,
      f"expected exactly 1 allowlisted mention, found {allowed}")

# 3. no second tension implementation. keyword_graph.tension_score() was the
#    orphan; nothing must define one outside tension_score.py again.
second_impls = []
for path in scan_files():
    if path.suffix != ".py" or path.name == "tension_score.py":
        continue
    try:
        text = path.read_text(errors="replace")
    except OSError:
        continue
    if re.search(r"^def tension_score\s*\(", text, re.MULTILINE):
        second_impls.append(str(path.relative_to(ROOT)))

check("exactly one tension implementation in the repo",
      not second_impls,
      f"also defined in {', '.join(second_impls)}" if second_impls else "")

# 4. the live vocabulary is what the docs actually describe. A repo that passed
#    1-3 by deleting every mention of tension would be worse, not better.
readme = (ROOT / "README.md").read_text(errors="replace")
for name in ("predicted", "confirmed", "calibration_delta"):
    check(f"README documents `{name}`", name in readme)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All docs-match-code checks passed.")

# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/tests/test_docs_match_code.py | created — regression guard: the superseded lexical tension formula must not reappear in any document, and no second tension implementation may be defined
