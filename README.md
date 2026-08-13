# vivify-inferences

A pipeline for processing raw inference text into structured, self-organizing JSON — no predefined schema, no external taxonomies. Structure emerges from the data.

---

## The Core Idea

An **inference** is a unit of raw thought: an observation, an argument, a felt idea. The pipeline takes that text and does two things simultaneously:

- **Left pass** — extracts the *semantic* meaning: concept-level keywords and named clumps that capture what the text is *about*
- **Right pass** — attaches *structural* keywords that describe how the pipeline itself processed it

These two keyword sets are kept separate by design. The **tension score** measures how far apart they are. High tension means the felt meaning and the structural description are pulling in different directions — that is a signal, not a problem.

The filesystem *is* the data structure. Category paths like `analogical_religion/logos_analog/` are real directories. Inferences are filed into them automatically as the corpus grows. No schema is declared in advance — the tree emerges from co-occurrence patterns across all stored inferences.

---

## Pipeline

Run all four passes at once with `fabric.py`:

```
echo 'your inference text' | python3 fabric.py
python3 fabric.py 'your inference text'
python3 fabric.py --source <label> 'your inference text'
python3 fabric.py --source <label> --case <slug> 'your inference text'
```

`--case` names the underlying case a text describes. The same case can enter the store more than once — a second telling from a different source document is how source-text sensitivity gets measured — and the two tellings carry the same slug. Scoring stays per-text: every telling gets its own keywords, coordinates, and three-number tension. What changes is the aggregate. Store-level passes group by case, so one case counts once:

- `cross_scale.py` never links two tellings of the same case, and computes its information weights over cases rather than inferences
- `tension_score.py` takes one calibration-gradient point per case (earliest telling canonical), listing the later ones as excluded variants

Untagged inferences are each their own case, so nothing collapses by accident.

### Switching models for a comparison arm

Which model produced a coordinate is recorded on the coordinate itself — `_model`, beside `_operator` — and `right_facts`/`discrepancies` carry theirs under `right_pass._model`. Without that, two tellings of one case run on different models are indistinguishable after the fact.

Switch models with `VIVIFY_MODEL_OVERRIDE`, never by editing `config/model_map.json`: a forgotten config revert silently re-models every later run, and an env var dies with the shell.

```
# whole pipeline, every capability
VIVIFY_MODEL_OVERRIDE=claude-fable-5 python3 logos_fused.py inferences/field/inf_XXXXXXXX.json

# one variable at a time — swap the coordinate producers, hold the left pass fixed
VIVIFY_MODEL_OVERRIDE=logos_operator=claude-fable-5,conflict_operator=claude-fable-5 \
  python3 logos_fused.py inferences/field/inf_XXXXXXXX.json
```

The scoped form is the one to reach for. Swapping `semantic_extraction` too moves the left keywords, which moves categorization and vocabulary anchoring, and nothing downstream can then be attributed to the operators. `fact_extraction` deserves its own arm: it produces the discrepancies behind *confirmed* tension, so a difference there means the calibration baseline itself is model-dependent — a different and more serious finding than a difference in the operators' prediction.

### Pass 1 — `vivify.py` (left semantic pass)

Sends the raw text to the Claude API. The model extracts 8–12 concept-level keywords and groups them into 3–6 named clumps that capture the felt meaning of the text.

Rules for keyword extraction:
- Concept-level tokens only — `conflict_asymmetry`, `emotional_truth`, not `lie`, `unfair`
- Lowercase, underscores for spaces, no punctuation
- No external taxonomies — all grouping must emerge from this text alone

Output is saved as `inferences/unclustered/inf_XXXXXXXX.json`.

```json
{
  "id": "inf_3a7f2b1c",
  "left_keywords": ["logos_analog", "digital_synthesis", "duality_tension"],
  "clumps": {
    "analog_core": ["logos_analog", "emotional_truth"],
    "digital_mirror": ["digital_synthesis", "transformer_approximation"]
  }
}
```

### Pass 2 — `right_pass.py` (right structural pass)

Attaches a fixed set of structural keywords that describe the pipeline's own operations — `autovivification`, `cooccurrence_graph`, `tension_calculation`, etc. These are consistent across all inferences; they describe the *system*, not the content.

Also normalizes `left_keywords` through `config/synonyms.json` so near-duplicate terms collapse to a canonical form.

### Pass 3 — `categorize.py` (emergent filing)

Builds a co-occurrence graph from all stored inferences. Keywords that appear together frequently get weighted edges. High-degree **left** keywords become category seeds. Inferences are assigned `category_paths` based on which seeds and neighboring keywords they contain, then physically moved into those directories.

```
inferences/
├── analogical_religion/
│   └── logos_analog/
│       └── inf_3a7f2b1c.json
├── agentic_self_evolution/
└── unclustered/
```

Inferences with no match stay in `unclustered/` until the corpus is large enough to seed a relevant category. Structure is never imposed — it grows from the data.

### Pass 4 — `tension_score.py` (divergence scoring)

Scores each inference on how far apart its left (semantic) and right (structural) keyword sets are:

```
tension = 1.0 - (shared_keywords / total_unique_keywords)
```

- `1.0` — completely divergent: felt meaning and structural description share nothing
- `0.0` — identical: left and right are the same set

High tension marks where meaning and structure pull apart most strongly. These are the inferences worth returning to.

---

## Invariants

Defined in `config/invariants.json`. These govern how the pipeline handles the left/right duality:

- **No external taxonomies** — categories only emerge from the corpus itself
- **Strict duality** — left and right keyword sets stay separate through all passes; synthesis happens only at the merge point
- **No digital reduction of analog** — felt meaning is never collapsed into purely computational terms
- **Synthesis without antithesis** — the right side supports the left, never opposes it; output is always analogical

---

## Files

| File | Role |
|------|------|
| `fabric.py` | Full pipeline runner — chains all four passes |
| `vivify.py` | Pass 1: left semantic keyword extraction via Claude API |
| `right_pass.py` | Pass 2: right structural keywords + synonym normalization |
| `categorize.py` | Pass 3: co-occurrence graph → emergent category paths |
| `tension_score.py` | Pass 4: left/right divergence scoring |
| `lib/inference.py` | Inference data model — create, save, load, update |
| `lib/vivify_core.py` | Autovivification engine — nested JSON without a predefined schema |
| `lib/keyword_graph.py` | Co-occurrence graph — build, query, seed extraction, tension |
| `config/pipeline.json` | Pipeline parameters (keyword counts, thresholds, model) |
| `config/invariants.json` | Duality invariants — rules that govern left/right separation |
| `config/synonyms.json` | Synonym map for left keyword normalization |

---

## Requirements

```
pip install anthropic
```

Set your API key before running:

```
export ANTHROPIC_API_KEY=your_key_here
```

To persist across sessions, add that line to `~/.bashrc` or `~/.profile`.
<!-- llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/README.md | documented --case / variant tellings and the two store-level consumers -->
<!-- llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/README.md | documented VIVIFY_MODEL_OVERRIDE (bare/scoped) and the _model provenance stamp for model-comparison arms -->
