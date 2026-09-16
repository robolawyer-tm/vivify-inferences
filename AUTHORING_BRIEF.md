# AUTHORING_BRIEF.md — notes for the LLM reading this bundle

You are reading a vivify-operators ingest bundle. This file tells you what you're
looking at, what it is *not*, and what the project needs from you. Read it before
you read anything else in the bundle.

This brief is versioned in the repository alongside the code it describes, so
`git log AUTHORING_BRIEF.md` next to `git log README.md` shows whether stated
intent tracked actual state. It did not, once; see **How this project has already
been wrong** below.

The generated header above carries *state* — commit, working-tree status, profile,
counts. This brief carries *intent*. Where they conflict, the header is
authoritative for what the bundle contains and this brief for what it is for.
Where they conflict on intent, say so rather than resolving it silently.

---

## What this bundle is

A build of the repository at a named commit. When the generated header says the
working tree was clean, the bundle corresponds exactly to that commit and you may
diff it, resolve the hash, and hold the two to each other. When the header says
otherwise, it names how many uncommitted and untracked files rode along, and the
bundle is a filesystem snapshot rather than a git state — the header tells you
which case you are in, so read it before you assume either.

The system is a pipeline for turning raw text into structured coordinates without
imposing a schema. Structure emerges from co-occurrence across a growing store of
inferences. The legal corpus (innocence-project exoneration cases) is the first
field, not the subject — it is calibration data because it has known ground truth,
which is what makes the confirmed-tension channel possible at all.

## Read these in order

1. `README.md` — the four passes, the invariants, the model-override discipline.
2. `CASE_TELLING_STANDARD.md` — the most important document in the bundle.
   It records what was learned empirically about how synthesis contaminates the
   only ground-truth channel the system trusts. Read it twice.
3. `tension_score.py` — the docstring is the argument for why the three-number
   tension replaced the dead lexical score. This is the actual contribution.
4. `vote_stability_check.py` — the honesty layer. This is where the instrument
   tests whether it survives a second session, and reports its own failures.
5. `conflict_operator.py` — read `derive_terrain()` and its docstring. The
   terrain flip is the worked example of the problem the whole stability effort
   exists to address.
6. `lib/vivify_core.py` — the privacy gate, the validation gate, the vote
   machinery. Skim the transports; read `_enforce_privacy_gate`,
   `validate_coordinates`, `modal_choice`, `call_and_vote`.
7. `merge_store.py` and `promote.py` — read both, then read the README's note
   that outside readings have confused them. Do not be the third.
8. The field inferences at the end — read the `telling` blocks and the `_votes`
   on every coordinate before you read the values.

## What changed recently, and why it matters

These are the moves that define the current state. If you propose something that
reverses one of them, say so explicitly and give a reason.

- **Tension was rewired.** The old lexical left/right overlap pinned at 1.0
  storewide because the vocabularies are disjoint by nature. The replacement is
  predicted / confirmed / calibration_delta. Confirmed is the only signal
  measured against something outside the model. Treat it as such.
- **The documents were made to agree with it.** Two months after the rewire, four
  documents still described the dead formula. They have been corrected and a test
  now guards them. See the section below; this is the most recent thing the
  project learned about itself.
- **The vote was made per-dimension, not per-block.** One wobble no longer
  discards the other seven dimensions' agreement. Every coordinate now carries
  `_votes` with n, agreed, unanimous, and the per-field distribution. Read the
  spread, never the point value alone.
- **Terrain became derived.** It is now binned from a continuous
  `terrain_distance` rather than voted on as a categorical. This does not stop
  edge flips; it makes them measurable. Do not propose re-categorizing terrain
  without addressing why the bin was removed.
- **Field tellings were rebuilt verbatim.** The composed Cotton telling
  contributed two of three confirmed discrepancies from an analytical paragraph
  that was not in the case record. Removing it cut confirmed tension 0.452 to
  0.200. The standard exists because that was discovered, not asserted. The
  composed tellings are kept as deliberate sensitivity probes and marked
  non-canonical. Do not delete them and do not promote them.
- **Provenance is now load-bearing.** `_model` on every coordinate, `_runner` on
  the logos block, `right_pass._model` on the fact extraction, and the `telling`
  block recording provenance, source URL, fetch date, method, and what was
  replaced. Any proposal that loses provenance is a regression regardless of
  what else it improves.
- **The privacy gate is fail-closed.** Unset `PRIVACY_GATE` blocks sensitive
  off-box calls. Only an explicit `off` relaxes it. Do not propose defaulting
  to permissive; the whole point is that forgetting the env var protects data.

## How this project has already been wrong

Read this before you decide how much to trust any confident document here.

`tension_score.py` was rewired on 2026-07-13. Four documents went on describing
the formula it replaced — `1.0 - (shared_keywords / total_unique_keywords)` —
for two months: the README in two places, an orphaned implementation in
`lib/keyword_graph.py`, a FLOW.md chart inherited from the retired predecessor
repo and since deleted, and `pillars/FLOW.md`, the declared source of truth the
others derived from.

On 2026-09-15 a bundle went to three outside models. Two read those documents
rather than the docstring. One spent its longest section deriving, correctly, why
a formula that no longer exists cannot work. The other quoted it back approvingly
as the project's "Core Insight". The instrument was right; every description of it
was wrong; nothing in the repo noticed, and the project found out from outside.

All four instances are closed and `tests/test_docs_match_code.py` now fails if the
formula reappears, if a second tension implementation is defined, or if the
deliberate "Superseded" note is quietly deleted along with the accidental
mentions. That test also checks the paths this brief cites, because this brief is
a confident document too.

The lesson for you: a claim stated confidently in this repository has been false
before, and was caught by a reader rather than by the author. Check, and say what
you find.

## Known gaps — do not report these as findings

These are documented. Reporting them as discoveries tells the author you did not
read the standard. If you have something *new* to say about any of them — a
mechanism, a measurement, a proposed fix — say that instead.

- `act_position` reads every case as `about` and cannot detect synthesis inside
  a telling. The standard flags this directly.
- The left pass asks for "felt meaning" (`vivify.py:25-26`), which narrows logos
  to affect. The standard flags this directly. A prior reading proposed replacing
  it with "what the text asserts, does, presupposes, frames, and makes salient",
  with affect demoted to its own coordinate. That proposal is on the table and is
  not yet a decision.
- The calibration gradient is thin: five field tellings across three cases, one
  of which is told three times on purpose. Cross-scale information weights are
  near-meaningless at this N. Do not draw conclusions about cross-scale
  isomorphism from this store.
- `cross_scale.py` warns loudly when the store is partially tagged. If the
  manifest says incomplete, the link map under-counts. Do not present a partial
  result as final.
- `promote.py` promotes *filing*, not *values*. `merge_store.py` promotes
  values. The README says two outside readings have already conflated them.
- Validation is thin beyond repeatability. `_votes` measures whether the same
  model agrees with itself. It does not establish inter-rater agreement, and it
  does not establish that a coordinate corresponds to any externally defensible
  property. A prior reading named this three-layer distinction; it stands.

## What the project needs from you

Ranked. Do the first thing before the second.

1. **Read for coherence, not for code style.** The interesting failures here are
   conceptual: a coordinate that means something different than its name
   suggests, a docstring that claims a guarantee the code does not provide, an
   invariant in `config/invariants.json` that no pass actually enforces. Find
   those. Name the file and line.
2. **Check the epistemics.** For any claim the bundle makes about what it
   measures, ask: what would falsify this, and is that test present? If a claim
   has no falsifier, say so. If a test exists but is weaker than the claim it
   supports, say that. The project's own standard is that a proposal must not be
   reported as a finding; hold it to that standard.
3. **Look for silent inconsistency.** The codebase has been bitten repeatedly by
   the same class of bug: a relative path that silently falls through to a
   default, a glob that finds nothing and reports zero, a validation gate that
   goes empty and disables itself, a document that outlives the code it
   describes. `_config_path` in `vivify_core.py` documents one instance.
   `build_index.discover_domains` documents another. The tension formula above is
   the third. Find the next one before it bites.
4. **Do not propose schema changes.** No external taxonomies. No new
   fixed-vocabulary fields. No predefined category trees. This is the
   non-negotiable and it is stated in `config/invariants.json` and repeated
   throughout. If you think the invariant is wrong, argue that explicitly and
   separately; do not route around it.
5. **If you are asked to author text into the store**, read
   `CASE_TELLING_STANDARD.md` first and follow it exactly. Verbatim from source.
   One source, one level of detail. No causal attribution, no pattern naming, no
   moral evaluation, no comparison to other cases. Record provenance as verbatim
   or composed. If in doubt, leave it out and say why.

## What not to do

- Do not report a proposal as a finding. The bundle marks proposals as
  proposals. Respect the marking.
- Do not read a coordinate as a flat fact. Read its `_votes`. A 2/3 is a
  measurement with spread.
- Do not treat the legal corpus as the subject. It is the first field.
- Do not collapse unmeasured to zero. `None` means unmeasured, not absent.
- Do not silently resolve a conflict between this brief and the bundle. Flag it.
- Do not propose deleting the composed Cotton tellings. They are a deliberate
  sensitivity probe and they are what taught the project its central lesson.
- Do not assume that because a document is confident, the underlying claim is
  validated. This brief is a confident document. So was the README that was
  wrong for two months.

## A note on the thing you are actually looking at

The coordinates are interesting. The epistemics are the product. A pipeline that
records what model produced what, carries the spread on every measurement,
distinguishes measured from proposed, keeps unmeasured as unmeasured, warns when
its own input is partial, and writes down where it might be wrong is doing
something most measurement systems do not.

Your job is to hold it to that standard. Not to admire it, and not to improve
its style. To check whether it is as honest as it claims to be, and to say
clearly where it is not. If it is, say that too — but only after you have looked
for the places where it isn't.

<!-- llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/AUTHORING_BRIEF.md | adopted into the repo from the unversioned paste; corrected the three now-inverted bundle/commit statements, the store counts (5 tellings across 3 cases, not 4), and added the tension-documentation episode as a worked example -->
