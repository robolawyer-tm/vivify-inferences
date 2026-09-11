# Case Telling Standard

A case telling carries the logos of the case, the acts people performed, and keeps synthesis out of raw_text.

- Logos is the evolved language structure of humanity; synthesis is the digital side recombining what exists.
- Identifications, confessions, testimony, verdicts and recantations are logos acts, and together they are the case.
- Analytical conclusions, pattern names and causal attributions are synthesis, whoever or whatever writes them.
- Evidence: the composed Cotton paragraph supplied 2 of 3 confirmed discrepancies, none from the case record.
- Removing that paragraph cut confirmed tension from 0.452 to 0.200 (commit d7871ab).
- Confirmed tension is the only ground-truth channel the evolution gradient trusts, so synthesis there counts as truth.
- The two Cotton tellings also split `structural.scale`, and that split held across voted sessions.
- Terrain differed between them too, but run 3 flipped terrain on identical text, so terrain proves nothing here.
- Enter every act verbatim from the source record, because paraphrase re-describes logos as synthesis.
- Include dates, named actors and outcomes with dates, each grounded in a quotable source as `right_facts` expects.
- Exclude causal attribution, pattern naming, moral evaluation and comparison to other cases.
- Exclude any sentence whose truth rests on the writer's judgement rather than on the record.
- Selection still happens, so use one source and one level of detail for every case.
- A shared level of detail replaces a length band, because length may reflect the case's real scale.
- Record each telling's provenance in the inference as either verbatim from source or composed.
- The inference store records the model behind every coordinate but never recorded who wrote raw_text.
- Keep exactly one canonical telling per case; the `canonical` flag is load-bearing in `cross_scale` and the gradient.
- Mark deliberate retellings non-canonical and keep them out of `cross_scale`.
- Keep the Cotton pair deliberately, as a probe of how sensitive the instrument is to the telling.
- Field text in the wild arrives already mixed, so the instrument must eventually separate logos from synthesis itself.
- Put genuinely needed interpretation in its own field, never in raw_text.
- `act_position` reads every case as `about`, so it cannot yet detect synthesis inside a telling.
- The left-pass prompt still asks for "felt meaning" (`vivify.py:25-26`), which narrows logos to affect.
- Bring the four field tellings under this standard before run 4 sets the first terrain and social_field baselines.
- After editing any telling, re-read its left pass and tension to measure what the edit moved.

<!-- llm: claude-opus-5 | 2026-09-07 | repos/vivify-operators/CASE_TELLING_STANDARD.md | PROPOSED, not adopted — drafted after the Cotton pair showed an analytical paragraph moves conflict.terrain (drifting vs fringe, each unanimous across three draws) and splits structural.scale; length band left as an open decision -->
<!-- llm: claude-opus-5 | 2026-09-11 | repos/vivify-operators/CASE_TELLING_STANDARD.md | ADOPTED by John in revised shape: reframed as logos vs synthesis, ground-truth contamination leads the evidence, refuted unanimity argument removed, verbatim rule, level-of-detail rule replaces length band, telling provenance field, Cotton pair kept as sensitivity probe -->
