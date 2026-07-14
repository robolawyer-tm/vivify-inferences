"""
converge — merge near-duplicate left keywords so co-occurrence can connect inferences

Extraction batches invent fresh keyword strings per inference (father_logos_absence /
father_logos_removal / father_logos_restoration), leaving the co-occurrence graph as
disconnected islands that categorize cannot cluster. This pass proposes merge groups
(deterministic token overlap + LLM semantic judgment), each with one canonical name,
then rewrites left_keywords and clump members from a reviewed mapping. Two-step by
design: propose writes nothing; apply takes the eyeballed mapping file — the LLM
proposes, the human rules, machinery applies (meaning enters at the membrane).

Applied mappings also merge into config/synonyms.json, so right_pass normalizes
the same variants in all future extractions — one ruling, permanent effect.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json, llm_call, extract_json, LLMUnavailable

MIN_TOKEN_OVERLAP = 0.5   # Jaccard on underscore-tokens to flag a candidate pair

SYNONYMS_FILE = Path(__file__).parent / "config" / "synonyms.json"

LLM_SYSTEM = (
    "You are a keyword vocabulary normalization tool. Output only valid JSON — "
    "no preamble, no explanation, no markdown fences.\n\n"
)

LLM_PROMPT = """These are left-side semantic keywords from one domain of an inference store.
Different extraction batches invented different strings for the same concept, so
keywords that should connect inferences do not. Propose merge groups.

Rules:
- Group ONLY keywords that name the same concept; when unsure, leave ungrouped
- Every group member must be copied exactly from the list below
- canonical: pick the clearest existing member, or coin one in the same
  lowercase_underscore style
- Singleton keywords with no true duplicate must NOT appear in any group
- Output JSON only: {{"groups": [{{"canonical": "...", "members": ["...", "..."]}}]}}

Deterministic token-overlap candidates (verify, split, or extend these):
{hints}

All keywords:
{keywords}
"""


def tokens(kw):
    return set(kw.split("_"))


def candidate_groups(keywords):
    """Greedy token-overlap grouping — the deterministic tier, used as LLM hints."""
    groups, used = [], set()
    kws = sorted(keywords)
    for i, a in enumerate(kws):
        if a in used:
            continue
        group = [a]
        for b in kws[i + 1:]:
            if b in used:
                continue
            ta, tb = tokens(a), tokens(b)
            if len(ta & tb) / len(ta | tb) >= MIN_TOKEN_OVERLAP:
                group.append(b)
                used.add(b)
        if len(group) > 1:
            used.update(group)
            groups.append(group)
    return groups


def llm_groups(keywords, hints, sensitive=False):
    """Ask the LLM for verified merge groups; validate members; one retry on bad JSON.

    - Routed via llm_call capability 'keyword_normalization' (config/model_map.json)
    - sensitive=True engages the privacy gate for private field vocabularies
    """
    prompt = LLM_SYSTEM + LLM_PROMPT.format(
        hints=json.dumps(hints, indent=1),
        keywords="\n".join(sorted(keywords)),
    )
    for attempt in (1, 2):
        try:
            raw = llm_call(prompt, capability="keyword_normalization",
                           sensitive=sensitive)
            groups = extract_json(raw)["groups"]
            valid = []
            for g in groups:
                members = [m for m in g.get("members", []) if m in keywords]
                if len(members) > 1:
                    valid.append({"canonical": g["canonical"], "members": sorted(members)})
            return valid
        except LLMUnavailable as e:
            print(f"attempt {attempt}: LLM unavailable ({e})", file=sys.stderr)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"attempt {attempt}: invalid LLM output ({e}), retrying", file=sys.stderr)
    print("LLM output unusable after retry — falling back to deterministic groups only",
          file=sys.stderr)
    return [{"canonical": g[0], "members": g} for g in hints]


def domain_keywords(domain_dir):
    """Distinct left keywords and per-keyword inference counts for a domain."""
    df = Counter()
    for p in Path(domain_dir).rglob("inf_*.json"):
        inf = read_json(p)
        df.update(set(inf.get("left_keywords", [])))
    return df


def propose(domain_dir, no_llm=False, sensitive=False):
    """Build the merge proposal: mapping of old keyword -> canonical. Writes nothing."""
    df = domain_keywords(domain_dir)
    hints = candidate_groups(set(df))
    groups = ([{"canonical": g[0], "members": g} for g in hints] if no_llm
              else llm_groups(set(df), hints, sensitive=sensitive))
    mapping = {}
    for g in groups:
        for m in g["members"]:
            if m != g["canonical"]:
                mapping[m] = g["canonical"]
    connected_before = sum(1 for k, n in df.items() if n > 1)
    return {
        "domain": str(domain_dir),
        "distinct_keywords": len(df),
        "shared_across_inferences_before": connected_before,
        "groups": groups,
        "mapping": mapping,
    }


def apply_mapping(domain_dir, mapping):
    """Rewrite left_keywords and clump members through the mapping, in place."""
    changed = 0
    for p in Path(domain_dir).rglob("inf_*.json"):
        inf = read_json(p)
        before = json.dumps([inf.get("left_keywords"), inf.get("clumps")])
        seen, merged = set(), []
        for k in inf.get("left_keywords", []):
            k = mapping.get(k, k)
            if k not in seen:
                seen.add(k)
                merged.append(k)
        inf["left_keywords"] = merged
        inf["clumps"] = {
            name: sorted({mapping.get(k, k) for k in members})
            for name, members in inf.get("clumps", {}).items()
        }
        if json.dumps([inf["left_keywords"], inf["clumps"]]) != before:
            write_json(p, inf)
            changed += 1
    return changed


def update_synonyms(mapping):
    """Merge an applied mapping into config/synonyms.json for future extractions.

    - right_pass.normalize_keywords reads this file — one human ruling here
      normalizes the same variants in every extraction from now on
    - Existing entries win on conflict (earlier rulings stand)
    - Returns count of new entries added
    """
    data = read_json(SYNONYMS_FILE) or {}
    synonyms = data.get("synonyms", {})
    added = 0
    for variant, canonical in mapping.items():
        if variant not in synonyms:
            synonyms[variant] = canonical
            added += 1
    data["synonyms"] = synonyms
    write_json(SYNONYMS_FILE, data)
    return added


def usage():
    print("Usage: converge.py --dir PATH [--no-llm] [--sensitive]   propose (JSON to stdout)")
    print("       converge.py --dir PATH --apply MAP.json           apply a reviewed proposal")
    print()
    print("Two-step: propose > map.json, eyeball it, then --apply map.json.")
    print("--apply also merges the mapping into config/synonyms.json (go-forward normalization).")
    print("After applying: categorize.py --dir, store_nest --apply, build_index.py")
    sys.exit(1)


def main():
    if "--dir" not in sys.argv:
        usage()
    domain_dir = Path(sys.argv[sys.argv.index("--dir") + 1])
    if not domain_dir.is_dir():
        print(f"Error: directory not found: {domain_dir}")
        sys.exit(1)

    if "--apply" in sys.argv:
        map_path = Path(sys.argv[sys.argv.index("--apply") + 1])
        proposal = read_json(map_path)
        mapping = proposal.get("mapping", {})
        if not mapping:
            print(f"Error: no mapping in {map_path}")
            sys.exit(1)
        changed = apply_mapping(domain_dir, mapping)
        added = update_synonyms(mapping)
        df = domain_keywords(domain_dir)
        print(f"Applied {len(mapping)} merges: {changed} inferences rewritten")
        print(f"synonyms.json: {added} new go-forward entries")
        print(f"Distinct keywords now: {len(df)}; "
              f"shared across inferences: {sum(1 for n in df.values() if n > 1)}")
        print("Next: categorize.py --dir, store_nest --apply, build_index.py")
    else:
        proposal = propose(domain_dir, no_llm="--no-llm" in sys.argv,
                           sensitive="--sensitive" in sys.argv)
        print(json.dumps(proposal, indent=2))


if __name__ == "__main__":
    main()

# llm: claude-fable-5 | 2026-07-07 | repos/vivify-inferences/converge.py | created — left-keyword vocabulary convergence: token-overlap + LLM merge groups, propose/apply two-step
# llm: claude-fable-5 | 2026-07-14 | repos/vivify-operators/converge.py | ported to vivify-operators: LLM via llm_call(keyword_normalization) + privacy-gate --sensitive; --apply now merges mapping into config/synonyms.json for go-forward normalization
