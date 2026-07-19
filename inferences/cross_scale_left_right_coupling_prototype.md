# Left-wound ↔ right-discrepancy coupling — prototype on the two field cases

Each felt left-side wound either has a counted right-side fingerprint or it does not, and that split is exactly what `calibration_delta` measures.

- Left values are `left_keywords` — nouns from felt experience (`statistical_misrepresentation`, `near_execution`).
- Right values are the `right_pass` claimed-vs-actual `discrepancies` and the plain `right_facts` counts.
- The coupling sorts every left wound into three tiers by how strongly the right side confirms it.
- Tier 1 = a claimed-vs-actual discrepancy exists — the wound is a *provable lie* and feeds `confirmed` tension.
- Tier 2 = a plain count exists but no contradiction — the wound is *quantified stakes*, not a lie.
- Tier 3 = no right-side fingerprint at all — the wound is *felt-only*, real but unconfirmed from the text.
- The prototype is hand-built here to show the relationship; it is not yet wired into any operator.

## Method — how a magnitude is assigned

The confirmed magnitude of a Tier-1 discrepancy follows `tension_score.py` exactly, so the per-case totals reproduce the stored numbers.

- Numeric-vs-numeric discrepancy: `1.0 + |log10(max_claimed / max_actual)|` — a scale-ratio lie.
- Either side non-numeric: `1.0` — a categorical contradiction that counts once.
- `confirmed = total / (total + 4.0)` — four solid contradictions read 0.5 (half-saturation at K=4).
- Tier 2 and Tier 3 wounds contribute `0` to `confirmed` — nothing counted, nothing confirmed.

## Sutton — left wounds paired to right discrepancies

Sutton's confirmed tension is high because one felt wound — the statistics — carries an enormous counted lie.

| Left wound (felt) | Right discrepancy (counted) | Claimed → actual | Magnitude |
|---|---|---|---|
| statistical_misrepresentation | match_probability | 1 in 694,000 → 1 in 16 | 5.64 |
| forensic_fabrication | number_of_semen_profiles | two → single | 1.30 |
| wrongful_conviction / dna_exoneration | dna_match_vs_exclusion | "exact match" → excluded | 1.00 |
| physical_evidence_contradiction | suspect_build_vs_sutton | 5'7"/135 lb → 6'/200 lb | 1.17 |

- Tier-1 total = 9.11 → `confirmed` = 9.11 / 13.11 = **0.6949** (matches the stored value).
- Tier 2 (quantified stakes, no lie): `custodial_years_lost` ↔ `years_served`=5 / `sentence_length`=25.
- Tier 2 borderline: `racial_disparity` ↔ the actual figure "1 in 16 *Black men*" — the racialization rides inside a right-side number.
- Tier 3 (felt-only, uncounted): `eyewitness_misidentification`, `institutional_incompetence`, `exculpatory_neglect`, `inadequate_defense`, `delayed_justice`.

## Washington — left wounds paired to right discrepancies

Washington's confirmed tension sits at the half-saturation point because every one of his contradictions is categorical, not numeric.

| Left wound (felt) | Right discrepancy (counted) | Claimed → actual | Magnitude |
|---|---|---|---|
| interrogator_fed_facts | confession_crime_details | wrong facts → fed by interrogators | 1.00 |
| false_confession / confession_as_sole_evidence | confession_evidence_validity | genuine → fabricated | 1.00 |
| evidence_contradiction_ignored | 1993_dna_result_characterization | ambiguous → not the source | 1.00 |
| true_perpetrator_identified | perpetrator_identity | Earl Washington Jr. → Kenneth Tinsley | 1.00 |

- Tier-1 total = 4.00 → `confirmed` = 4 / 8 = **0.500** (exactly the K=4 half-saturation point).
- Tier 2 (quantified stakes, no lie): `intellectual_disability_exploitation` ↔ `washington_iq`=69; `near_execution` ↔ `days_before_execution`=9.
- Tier 3 (felt-only, uncounted): `suggestibility_under_authority`, `delayed_justice`, `half_measure_clemency`, `institutional_inertia`, `systemic_acknowledgment_failure`, `racialized_suspicion`.

## What the coupling reveals — the delta is the uncounted felt mass

The positive `calibration_delta` on both cases is precisely the weight of the Tier-3 wounds that the right side never fingerprinted.

- `predicted` reads the whole left field through `resonance=illusion` (both cases score the felt wound near-maximal).
- `confirmed` counts only the Tier-1 subset that surfaced a claimed-vs-actual pair.
- `calibration_delta = predicted − confirmed` is therefore the felt-minus-counted gap: Washington 0.892 − 0.500 = **+0.392**, Sutton 0.828 − 0.695 = **+0.133**.
- Washington's delta is larger because more of his harm is Tier 3 — a coerced confession and a near-execution leave felt wounds with no numeric contradiction to catch.
- Sutton's delta is smaller because his central wound *is* a number — the 1-in-694,000 lie pulls felt harm down into the counted column.
- So the delta is not noise: it is the systematic residue of wounds that are real to a human but invisible to a claimed-vs-actual test.
- This is why the coupling matters for weighting — a left wound with a Tier-1 fingerprint is corpus-confirmable, and only those can earn emergent weight without an imposed harm scale.

## Promotion path — how the Tier-1 coupling should reach cross_scale, and when

The coupling stays a prototype until a validated corpus can justify the blend, at which point it enters `cross_scale.py` as a separate field, never as a replacement of structural strength.

- Prototype run 2026-07-17 (`cross_scale_tier1_prototype.py`) proved the plumbing and the safety property: only `innocence_project` sources carry `confirmed`, so only validated ground truth can move a weight.
- It did not prove ranking improvement — the store holds one confirmed-on-both-ends link (Sutton↔Washington), so the boost widened one margin (8.817 → 14.014) and re-ordered nothing.
- Do not fold confirmation into the `strength` scalar: structural rarity and ground-truth anchoring are different axes, and merging them destroys the ability to read either alone.
- Instead add `confirmation_factor` (and optionally `confirmed_strength`) as separate link fields, leaving base `strength` a pure `-log(df/N)` rarity sum so downstream consumers do not silently shift.
- Expose confirmation as a flag or distinct ranking (`--rank-by confirmed`, a ground-truth lens), not the default sort — the gated variant erased 89 of 90 links and is a lens, not a replacement.
- Keep the blend coefficient out of code until the calibration corpus can fit it; a hand-set `λ` is the imposed constant the non-negotiable forbids, merely relocated.
- Promotion trigger: several validated field cases in the store, enough that confirmation re-orders links rather than widening a single margin.
- Editing `cross_scale.py` requires `backit` and explicit sign-off first; the prototype harness imports `cross_scale` and cannot stand in for the operator.

<!-- llm: claude-opus-4-8 | 2026-07-17 | vivify-operators/inferences/cross_scale_left_right_coupling_prototype.md | new prototype pairing left_keywords to right_pass discrepancies on Washington + Sutton -->
<!-- llm: claude-opus-4-8 | 2026-07-17 | vivify-operators/inferences/cross_scale_left_right_coupling_prototype.md | added promotion-path note (prototype run result + conditions for wiring into cross_scale) -->
