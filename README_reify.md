# reify

**FABRIC inverse pass: JSON inference → regenerated text**

The vivify pipeline moves from language to structure: raw text enters, keywords
and clumps emerge, the inference is filed into a category tree, and a tension score
measures how far the felt meaning has drifted from its structural capture. reify
runs that process in reverse. It takes a stored inference — already compressed into
left_keywords, clumps, category_paths, and tension_score — and asks the Claude API
to reconstruct the analog original: the felt thought the structure was built from.

This is not summarization or paraphrase. The model is instructed to speak from
inside the meaning, not about it. The tension_score shapes the output — a score of
1.0 means left and right keyword sets share nothing, so the felt meaning completely
resists its structural capture; the reconstruction leans into that gap rather than
smoothing it over.

---

## Modes

### single

Reconstructs prose from one inference. The model receives left_keywords, clumps,
and a slice of category_paths, plus the tension score. Output is 3-6 dense
sentences in first person. Use this to test whether vivify actually captured
what was meant — if the reconstruction feels foreign, the keywords drifted.

```
python3 reify.py inferences/autovivification/analogical_religion/inf_c8e1ac73.json
```

### synthesize

Takes two inference files and generates a single passage that holds both
simultaneously. Not alternating, not summarizing — finding the place where they
are the same thought. If the two inferences pull in different directions the
model writes from that tension. Use this to discover connections the corpus
has not yet made explicit.

```
python3 reify.py --synthesize inferences/.../inf_A.json inferences/.../inf_B.json
```

### voice

Walks an entire category directory and generates a passage that speaks for the
whole category — a distillation of what all its inferences are reaching toward
together. This is the most generative mode: the emergent category tree, built
by co-occurrence across the full corpus, becomes the source material for new
prose that could not have come from any single inference.

```
python3 reify.py --voice autovivification/analogical_religion
```

---

## Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Print the full prompt without calling the API. No billing. Use this to inspect what the model will receive before committing to a call. |
| `--dir <path>` | Inferences directory (default: `inferences`). Used with `--voice`. |

---

## Requirements

```
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here
```

Each call to reify bills against your Anthropic API account. Use `--dry-run` first.
