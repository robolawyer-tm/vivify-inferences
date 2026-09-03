# Second-Session Stability of the Legal-Corpus Coordinates

**Read twice, the legal corpus does not hold: 4 of 36 stored coordinates flipped outright and 6 more split within the session, and the two findings that phase-2's gel-indicators rest on — the cross_scale isomorphism and the tension gradient — both depend on fields that failed.**

- Run 2026-09-03 against all four `inferences/field/` inferences; stored values are session 1 (2026-07-10, 07-12, 08-13).
- `claude-opus-4-8` throughout, 3 repeats per operator per specimen, 48 calls.
- Store never written — verified by md5 before and after. Harness `session_stability.py`, comparison `session_stability_report.py`, raw `inferences/session_stability_runs.json`.
- Method follows the rule established by the outside-view re-run: within-session repeats measure sampling; only a second session measures reproducibility.

## Per-field result

| | stable | split within session 2 | flipped vs session 1 |
|---|---|---|---|
| `conflict.*` (5 fields × 4) | **18** | 0 | 2 |
| `cooperative.status` | 3 | 1 | 0 |
| `cooperative.maxim_violated` | 2 | 2 | 0 |
| `resonance.value` | 2 | 2 | 0 |
| `structural.scale` | 1 | 1 | 2 |
| **total** | **26** | **6** | **4** |

**`conflict` is the strong performer.** Every one of its five fields was unanimous across all three repeats on all four cases. Note the design though: `conflict` was deliberately run against the **stored** logos, so this measures only its own sampling, with its input held fixed. It is stable *given* stable inputs — which the rest of this document shows it does not have.

**`structural.scale` is the weakest**, and it is the one that is deliberately not enum-gated (`config/coordinates.json` notes layer/scale are coerced against `VALID_SCALES` rather than gated). Both Cotton tellings flipped `global` → `institution`; Washington split 2:1.

## Consequence 1 — the cross_scale isomorphism does not survive

`cross_scale.py:150` — `if a["scale"] == b["scale"] or a["case"] == b["case"]: return (0, {})`. **A cross-scale link requires the two scales to differ.**

| case | scale, session 1 | scale, session 2 |
|---|---|---|
| josiah_sutton | institution | institution 3/3 |
| earl_washington_jr | global | institution 2/3, global 1/3 |
| ronald_cotton (analysis) | global | institution 3/3 |
| ronald_cotton (canonical) | global | institution 3/3 |

Session 1 placed Sutton at `institution` against Cotton and Washington at `global` — which is exactly what produced the top-ranked links, Washington↔Sutton and Cotton↔Sutton, both 6/6 shared dimensions. **Under session 2 all four cases land on `institution`, so every legal↔legal pair is same-scale and the operator returns zero links.** The isomorphism I reported on 2026-08-31 as "a second all-six-dimension legal pair" is an artifact of a scale assignment that does not reproduce.

Counted directly over the eligible legal pairs (same-case pairs excluded, as the operator excludes them): **session 1 had 3 of 5 pairs on differing scales; session 2 has 0 of 5.**

This is gel-indicator 1 ("cross-scale isomorphism replicates across several independent case pairs"). It is not merely unreplicated; the single existing replication is withdrawn.

## Consequence 2 — the tension gradient is not stable at single draws

`tension_score.py` makes no LLM call, so `predicted_tension` moves only as its inputs move. Taking the **majority** value per field, it barely moves at all:

| case | stored | session 2 (majority) | delta |
|---|---|---|---|
| earl_washington_jr | 0.892 | 0.892 | 0.0000 |
| josiah_sutton | 0.828 | 0.828 | 0.0000 |
| ronald_cotton (analysis) | 0.828 | 0.828 | 0.0000 |
| ronald_cotton (canonical) | 0.678 | 0.712 | +0.0340 |

That reassurance is an artifact of majority-voting, which the pipeline does not do. Across **all 81 rep combinations** per case — every combination the single-draw pipeline could actually have produced:

| case | stored | min | max | spread |
|---|---|---|---|---|
| earl_washington_jr | 0.892 | **0.524** | 0.928 | 0.404 |
| josiah_sutton | 0.828 | 0.852 | 0.876 | 0.024 |
| ronald_cotton (analysis) | 0.828 | 0.820 | 0.860 | 0.040 |
| ronald_cotton (canonical) | 0.678 | **0.189** | 0.796 | **0.607** |

**The ranges overlap, so the ordering is not safe.** Washington can read 0.524 — below both Cotton tellings and below Sutton. Canonical Cotton can read anywhere from 0.189 to 0.796, straddling every other case. The gradient 0.892 > 0.828 > 0.678 that the deception-keying question was built on is one draw from a distribution wide enough to reorder it.

This is gel-indicator 2 ("the tension gradient is stable and discriminating on LEGAL cases specifically"). Measured: at n=3, with single draws, it is neither.

## What this does not overturn

- The **source-sensitivity** result stands on its own terms: `confirmed` tension halved when composed analysis was removed (0.452 → 0.200) because two of three discrepancies were quoted from that paragraph. That is a `right_pass` measurement over quoted text, not a coordinate read, and nothing here touches it.
- `cooperative.status` = honored and `conflict.behavior` = suppression held on three of four cases — the suppression signature itself is the most durable thing in the corpus.
- Every case still reads as high-tension. The instrument agrees with itself about *kind*; it is *magnitude and placement* that wobble.

## Anomaly worth a look

Washington returned `cooperative: {status: honored, maxim_violated: quantity}` on one repeat — a maxim named while the status says none was violated. The enum gate accepts it because both fields are individually legal; nothing checks their coherence. A cross-field constraint (`maxim_violated` must be null when `status == honored`) would have caught it.

## What follows

1. **Repeat-and-vote before storing.** The cheapest fix available: run each operator 3× and store the majority, with the distribution recorded. On this evidence it converts a 0.607 spread into a 0.034 one.
2. **Gate `structural.scale`.** It is the least stable field, it is ungated by choice, and cross_scale's entire output is a function of it.
3. **Re-run cross_scale only after 1 and 2.** Its current output is built on single-draw scales.
4. **Treat the tension gradient as unmeasured** until predicted tension is stored with a spread, not a point.
5. Add the `honored` + `maxim_violated` coherence check.

<!-- llm: claude-opus-5 | 2026-09-03 | repos/vivify-operators/inferences/session_stability.md | created — second-session re-read of the legal corpus: 4 flips, 6 splits, cross_scale isomorphism withdrawn (all cases collapse to one scale), tension gradient shown unstable at single draws (spread up to 0.607) -->
