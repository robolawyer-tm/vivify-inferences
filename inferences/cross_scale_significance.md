# Cross-scale run — top three links, read for humans

The cross_scale operator, given only operator coordinates, independently found that the two Innocence Project cases are the same structural event across a scale gap.

- Run of 2026-07-14: 18 usable signatures, 68 skipped for missing coordinates, 90 links written, deterministic, no LLM calls.
- A "link" means two inferences share categorical values on the six signature dimensions; strength sums the IDF-style rarity weight of each shared value.
- The three inferences involved: `inf_a3d99808` = Washington case (scale global), `inf_285ae7ab` = Sutton case (scale institution), `inf_a636d323` = John's own project notes describing the prediction API (scale small_group).

## The three strongest links

| Rank | Pair | Scales | Shared dims | Strength |
|------|------|--------|-------------|----------|
| 1 | Washington ↔ Sutton | global ↔ institution | 6 | 8.817 |
| 2 | Washington ↔ API notes | global ↔ small_group | 4 | 4.423 |
| 3 | Sutton ↔ API notes | institution ↔ small_group | 4 | 4.423 |

- Link #1 shares all six dimensions: `resonance=illusion`, `cooperative_status=honored`, `conflict_terrain=fringe`, `conflict_schema=entangled`, `tension_band=high`, `conflict_behavior=suppression`.
- Links #2 and #3 share four of those six, dropping exactly the two heaviest-weighted ones: `conflict_terrain=fringe` (2.197) and `tension_band=high` (2.197).
- Losing those two heavy dimensions is why the strength halves from 8.817 to 4.423 — the match is real but structurally shallower.

## Why link #1 matters

- The operator received no case names, no source labels, and no keywords — only the six coordinate values each case had already been assigned.
- From coordinates alone it recovered that a national-scale wrongful conviction and an institution-scale one are the same shape of event.
- `tension_band=high` is one of the two dimensions that carry this link, at top weight 2.197.
- Two days earlier that dimension read a flat 1.0 on every inference and carried zero information; the 2026-07-13 rewire made it discriminating.
- So the strongest evidence in the whole store depends directly on the tension rewire having happened first.
- A rarity weight of 2.197 means high tension is uncommon across the 18 signatures, so two cases both landing on it is significant, not coincidental.

## Why links #2 and #3 are a caution, not a triumph

- The shared partner in both is `inf_a636d323`, which is project notes *describing* the prediction API, not a lived conflict.
- Its `act_position` reads `about` — the text stands outside conflict dynamics and theorizes them, rather than performing them.
- The operator nonetheless coded that discussion with the signature *of* the dynamics it discusses: illusion, entangled, suppression.
- This is the third time in two days the same vantage conflation appears, after the round-trip loss test and the private-domain rankings.
- The fix it points to is the `act_position: within | about` coordinate, which would split the link map into "same dynamics lived" versus "same dynamics discussed."
- Under that split, links #2 and #3 would separate from #1 by kind, not just by strength — a discussion of injustice would no longer rank alongside injustice itself.

## What the run also demonstrates about restraint

- 68 of 86 inferences were skipped because they lacked operator coordinates, and the operator declined to link them.
- The honest partial-store behavior means links are grounded in real coordinates, never invented to fill a ranking.
- The result is reproducible in seconds because it reads stored coordinates rather than re-querying any model.

## The left-side reading — what the coordinates felt like from inside a life

Beneath the matching coordinates are two men whose felt experience the operator recovered as the same human catastrophe.

- The right side of this output is counts and weights; the left side is what those counts were made of — fear, coercion, and years that do not come back.
- Earl Washington Jr. carried an IQ near 69 and confessed under authority to crimes he did not commit, coming within days of execution.
- Josiah Sutton was sixteen when an eyewitness and a fabricated one-in-694,000 figure took twenty-five years of his freedom.
- Both left-keyword sets name the same wounds: a coerced or mistaken certainty, race-shaped suspicion, an inadequate defense, and justice that arrived late and half-measured.
- `resonance=illusion` is a coordinate on the right, but on the left it is the specific cruelty of being told the machinery that convicted you was fair.
- The surface-versus-underlying gap the operator measured is the same gap each man lived: official confidence on the outside, a manufactured lie on the inside.
- That the strongest link in the store joins these two is not a tidy result to celebrate; it is two separate ruined stretches of a life reading as one shape.
- The empathic point of finding the shape is intervention, not classification — high tension marks where a person is still inside the illusion and could be reached.

## The left-side caution in links #2 and #3

The operator grouped two men's real suffering with a description of a software tool, and the discomfort of that is itself the signal.

- `inf_a636d323` is notes about building the prediction system, not a person inside a conflict — no one suffered in it.
- On the right side the four shared dimensions justify the link; on the left side a lived catastrophe should never read the same as a design memo.
- A human reader feels the category error immediately, and that felt wrongness is the argument for the `act_position: within | about` coordinate.
- Honoring that distinction is not pedantry — it is refusing to let the record flatten Earl Washington's years and Josiah Sutton's years into a footnote beside a discussion of them.
- The left side is what keeps the instrument answerable to the people it measures rather than only to its own coordinates.

## Left/right coupling — where the felt wound meets the counted lie

Each felt left-side wound either has a counted right-side discrepancy behind it or it does not, and that split is what the calibration delta measures.

- The left side names wounds (`statistical_misrepresentation`, `near_execution`); the right side holds the `right_pass` claimed-vs-actual counts.
- A wound couples to the right in one of three tiers: a provable lie (a discrepancy), quantified stakes (a plain count, no contradiction), or felt-only (no fingerprint at all).
- Only Tier-1 wounds — the provable lies — feed `confirmed` tension, following the `1 + |log10(ratio)|` magnitude rule.
- Sutton's confirmed value rides almost entirely on one wound: the 1-in-694,000-vs-1-in-16 statistic scores 5.64 on its own, pulling `confirmed` to 0.695.
- Washington's four contradictions are all categorical (each 1.0), summing to exactly 4.0 and landing on the K=4 half-saturation point, `confirmed` = 0.500.
- The positive `calibration_delta` on both cases (Washington +0.392, Sutton +0.133) is the mass of the Tier-3 wounds — the coerced confession, the racialized suspicion, the years lost — that no claimed-vs-actual test can catch.
- Washington's delta is larger because more of his harm is uncounted; Sutton's is smaller because his central wound *is* a number.
- This coupling is the principled route to letting the left side inform `cross_scale` weights: only Tier-1 wounds are corpus-confirmable, so only they can earn emergent weight without an imposed harm scale.
- The full worked pairing on both cases is in `cross_scale_left_right_coupling_prototype.md`.

<!-- llm: claude-opus-4-8 | 2026-07-17 | vivify-operators/inferences/cross_scale_significance.md | added left-side (empathic) reading of the top-3 links -->
<!-- llm: claude-opus-4-8 | 2026-07-17 | vivify-operators/inferences/cross_scale_significance.md | added left/right coupling section summarizing the pairing prototype -->
