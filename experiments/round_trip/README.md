# round_trip — coordinate → prose loss test

Measures what survives when a case is reduced to its operator coordinates and a blind model reconstructs the situation from those coordinates alone.

- Encoder = the operator stack (logos_fused + conflict), already run; decoder = fresh `claude -p` with no context.
- Test case: inf_285ae7ab (Josiah Sutton exoneration), coordinates from `inferences/field/`.
- Tier A input = coordinate values only: enums, numbers, confidences, conflict signals.
- Tier B input = tier A plus left_keywords and clumps (the semantic index layer).
- Stripped from both tiers: raw_text, all rationales, resonance surface/underlying, implicature, authority source, `source` label, `_src`, `_operator` — every field carrying prose or provenance.
- right_keywords excluded everywhere: known stub, pipeline vocabulary, not content.
- Decoder prompt asks for THE READING (reconstruct the situation) and THE RESIDUE (what the coordinates cannot say).
- Decoder model = whatever the CLI default is at run time (`claude -p` inherits it).
- Expected result: tier A preserves structural dynamics (institutional authority, false surface, suppression, entangled conflict) but loses all particulars; the gap between tiers isolates what keywords add.
- Loss is judged three ways: against raw_text facts, against the original left-pass reading, against John's felt sense of the case (the analogic-chord check).
- Known v1 gap (accepted): no operator-vocabulary legend is given to the decoder, so the test also measures how self-evocative the enum terms are; a legend-included variant is a possible tier C.
- Comparison writeup goes to `loss_report.md` after the runs.

<!-- llm: claude-fable-5 | 2026-07-13 | repos/vivify-operators/experiments/round_trip/README.md | created: experiment design doc -->
