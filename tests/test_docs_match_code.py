#!/usr/bin/env python3
"""Focused test: no document may restate the superseded lexical tension formula,
and no document may cite a path that has gone away.

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

Two deliberate mentions survive, each required to carry its own marker on the same
line: README.md's "Superseded — do not reintroduce" note, and AUTHORING_BRIEF.md's
account of the episode. Keeping the dead formula visible with the reason it died is
what stops the next reader re-deriving it — which is what a reader did.

What check 5 does and does not catch. It verifies that every repo-local path a
document cites still exists, and that a cited line number is within that file. It
catches a deleted or renamed file — FLOW.md is the worked example — and a citation
that points past the end of a truncated one. It does NOT catch semantic drift: when
lib/keyword_graph.py:80 stopped being the tension implementation, the file still
existed and still had eighty lines. Verifying that a cited line still means what the
citing document claims is not attempted here.

Scope limit, stated rather than hidden: this scans THIS repo only. pillars/FLOW.md
was the root instance and lives in a sibling repo, so it is not covered here — a
test that reached across repos would fail for anyone who cloned only this one.
Citations beginning "pillars/" are skipped for the same reason.

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

# The only sanctioned mentions: file -> marker that must sit on the same line.
# Anywhere else, in any file, is a regression.
SANCTIONED = {
    "README.md": "Superseded — do not reintroduce",
    "AUTHORING_BRIEF.md": "the formula it replaced",
}

# A backticked repo path, with an optional :line or :line-line suffix.
CITATION = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md|json))(?::(\d+)(?:-(\d+))?)?`")

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

# 1. the formula appears nowhere except its sanctioned, marked lines
offenders = []
sanctioned_hits = {name: 0 for name in SANCTIONED}
for path in scan_files():
    rel = str(path.relative_to(ROOT))
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        continue
    marker = SANCTIONED.get(rel)
    for n, line in enumerate(lines, 1):
        if not DEAD_FORMULA.search(line):
            continue
        if marker and marker in line:
            sanctioned_hits[rel] += 1
        else:
            offenders.append(f"{rel}:{n}")

check("formula absent outside its sanctioned lines",
      not offenders,
      f"found in {', '.join(offenders)}" if offenders else "")

# 2. each sanctioned mention is still there, exactly once. A repo that passed
#    check 1 by quietly deleting the "why it died" notes is worse, not better.
for name, marker in SANCTIONED.items():
    check(f"{name} still carries the dead formula with its marker",
          sanctioned_hits[name] == 1,
          f"expected 1 marked mention, found {sanctioned_hits[name]}")

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

# 5. every repo-local path the reading instructions cite still resolves. FLOW.md
#    sat in the bundle for months naming a pipeline that no longer existed.
brief = ROOT / "AUTHORING_BRIEF.md"
check("AUTHORING_BRIEF.md is present", brief.is_file(),
      "the bundle would ship with no reading instructions")

if brief.is_file():
    text = brief.read_text(errors="replace")
    dangling = []
    for cited, start, end in CITATION.findall(text):
        if cited.startswith("pillars/"):      # sibling repo, deliberately unscanned
            continue
        target = ROOT / cited
        if not target.is_file():
            # a bare filename may legitimately live in a subdirectory
            matches = [p for p in ROOT.rglob(Path(cited).name)
                       if p.is_file()
                       and not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)]
            if not matches:
                dangling.append(f"{cited} (no such file)")
                continue
            target = matches[0]
        last = max(int(start or 0), int(end or 0))
        if last:
            n_lines = len(target.read_text(errors="replace").splitlines())
            if last > n_lines:
                dangling.append(f"{cited} (cites line {last}, file has {n_lines})")

    check("every path AUTHORING_BRIEF.md cites still resolves",
          not dangling,
          "; ".join(dangling) if dangling else "")

print()
if failures:
    print(f"FAILED: {len(failures)} check(s) — {', '.join(failures)}")
    sys.exit(1)
print("All docs-match-code checks passed.")

# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/tests/test_docs_match_code.py | created — regression guard: the superseded lexical tension formula must not reappear in any document, and no second tension implementation may be defined
# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/tests/test_docs_match_code.py | two sanctioned formula mentions (README + AUTHORING_BRIEF), each marker-gated; added check 5 — every repo-local path the brief cites must resolve and cited line numbers must be in range
