"""build_index — rebuild the global roll-up index across all domains.

Recomputes corpus-wide keyword and co-occurrence stats from every stored
inference and nests each domain's emergent category tree under a domains key.
The root inferences/index.json becomes a single whole-corpus surface; the
per-domain index.json files remain the authoritative category source.

- discover_domains: domain dirs are immediate subdirs holding inf_*.json files
- global_stats: corpus-wide left-keyword frequency + co-occurrence
- build: (re)categorize each domain, then write the rolled-up root index
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import read_json, write_json
from categorize import categorize_all
from reify import reify_domain_voice

INFERENCES_DIR = Path("inferences")

# Discovery surface settings
SITE_URL = "https://robolawyer-tm.github.io"
PRIVATE_DOMAINS = {"private"}   # never published to the public JSON-LD surface
JSONLD_FILE = INFERENCES_DIR / "discovery.jsonld"


def discover_domains(inferences_dir):
    """Return domain names — immediate subdirs of inferences/ holding inf_*.json."""
    return [
        d.name for d in sorted(Path(inferences_dir).iterdir())
        if d.is_dir() and any(d.glob("inf_*.json"))
    ]


def global_stats(inferences_dir):
    """Corpus-wide left-keyword frequency and co-occurrence over all domains.

    - Matches server._update_index semantics (left_keywords only)
    - Returns (total_inferences, keywords, cooccurrence)
    """
    keywords, cooccurrence, total = {}, {}, 0
    for path in Path(inferences_dir).rglob("inf_*.json"):
        inf = read_json(path)
        if not inf:
            continue
        total += 1
        kws = inf.get("left_keywords", [])
        for kw in kws:
            keywords[kw] = keywords.get(kw, 0) + 1
        for i, a in enumerate(kws):
            for b in kws[i + 1:]:
                pair = f"{a}::{b}"
                cooccurrence[pair] = cooccurrence.get(pair, 0) + 1
    return total, keywords, cooccurrence


def build(inferences_dir=None, recategorize=True, voices=False, dry_run=False):
    """Rebuild per-domain categories then the global roll-up root index.

    - recategorize: refresh each domain's index.json categories first
    - voices: synthesize a reify domain voice for each public domain (LLM calls)
    - Returns the assembled root index dict
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    domains = discover_domains(inferences_dir)

    domain_blocks = {}
    for name in domains:
        ddir = inferences_dir / name
        if recategorize and not dry_run:
            categorize_all(ddir)
        cats = (read_json(ddir / "index.json").get("categories") or {})
        block = {
            "count": len(list(ddir.glob("inf_*.json"))),
            "tree": cats.get("tree", {}),
            "paths": cats.get("paths", {}),
        }
        # Voices only for public domains — never spend a call on private data
        if voices and not dry_run and name not in PRIVATE_DOMAINS:
            print(f"  reifying voice for '{name}' ...", flush=True)
            block["voice"] = reify_domain_voice(ddir, name)
        domain_blocks[name] = block

    total, keywords, cooccurrence = global_stats(inferences_dir)
    index = {
        "version": "4.0",
        "total_inferences": total,
        "keywords": keywords,
        "cooccurrence": cooccurrence,
        "domains": domain_blocks,
    }

    if dry_run:
        write_json(inferences_dir / "index.json", index, dry_run=True)
        return index

    write_json(inferences_dir / "index.json", index)
    return index


def to_jsonld(index, site_url=SITE_URL, exclude=PRIVATE_DOMAINS):
    """Render the roll-up index as a schema.org DataCatalog discovery surface.

    - One Dataset per public domain (private domains excluded)
    - Each domain's emergent category tree becomes a DefinedTermSet
    - Domain descriptions default to deterministic text; reify voices can replace
    - Returns a JSON-LD dict ready to serialize
    """
    catalog_id = f"{site_url}/#catalog"
    org_id = f"{site_url}/#org"

    datasets = []
    for name, block in index.get("domains", {}).items():
        if name in exclude:
            continue
        seeds = sorted(block.get("tree", {}).keys())
        count = block.get("count", 0)
        datasets.append({
            "@type": "Dataset",
            "@id": f"{site_url}/#dataset-{name}",
            "name": name,
            "description": block.get(
                "voice",
                f"Domain '{name}' — {count} inferences across "
                f"{len(seeds)} emergent categories."
            ),
            "isPartOf": {"@id": catalog_id},
            "isAccessibleForFree": True,
            "creativeWorkStatus": "emergent",
            "keywords": seeds,
            "variableMeasured": {
                "@type": "DefinedTermSet",
                "name": f"{name} emergent categories",
                "hasDefinedTerm": [
                    {"@type": "DefinedTerm", "name": s} for s in seeds
                ],
            },
        })

    public_total = sum(
        block.get("count", 0)
        for n, block in index.get("domains", {}).items() if n not in exclude
    )

    return {
        "@context": "https://schema.org",
        "@type": "DataCatalog",
        "@id": catalog_id,
        "name": "robolawyer-tm inference store",
        "description": (
            "Emergent inference store — beneficial-outcome inferences organized by "
            f"self-arising categories with no external taxonomy. {public_total} "
            "public inferences across emergent domains."
        ),
        "url": site_url,
        "isAccessibleForFree": True,
        "publisher": {"@type": "Organization", "@id": org_id, "name": "robolawyer-tm"},
        "dataset": datasets,
    }


def emit_jsonld(inferences_dir=None, out_path=None, dry_run=False):
    """Read the roll-up index and write the JSON-LD discovery surface.

    - Returns the JSON-LD dict
    """
    inferences_dir = Path(inferences_dir or INFERENCES_DIR)
    index = read_json(inferences_dir / "index.json")
    jsonld = to_jsonld(index)
    out_path = Path(out_path or (inferences_dir / JSONLD_FILE.name))
    write_json(out_path, jsonld, dry_run=dry_run)
    return jsonld


def usage():
    print("Usage: build_index.py [--no-recategorize] [--jsonld] [--dry-run]")
    print("       build_index.py                 recategorize all domains, write roll-up")
    print("       build_index.py --no-recategorize  roll up existing per-domain indexes only")
    print("       build_index.py --jsonld        also emit the JSON-LD discovery surface")
    print("       build_index.py --voices        reify a voice per public domain (LLM calls)")
    print("       build_index.py --dry-run       show the roll-up without writing")
    sys.exit(1)


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        usage()

    recategorize = "--no-recategorize" not in sys.argv
    dry_run = "--dry-run" in sys.argv
    do_jsonld = "--jsonld" in sys.argv
    voices = "--voices" in sys.argv

    index = build(recategorize=recategorize, voices=voices, dry_run=dry_run)

    print(f"total_inferences: {index['total_inferences']}")
    print(f"keywords:         {len(index['keywords'])}")
    print(f"cooccurrence:     {len(index['cooccurrence'])}")
    print("domains:")
    for name, block in index["domains"].items():
        print(f"  {name}: count={block['count']} "
              f"seeds={len(block['tree'])} paths={len(block['paths'])}")

    if do_jsonld:
        jsonld = emit_jsonld(dry_run=dry_run)
        public = [d["name"] for d in jsonld["dataset"]]
        excluded = sorted(PRIVATE_DOMAINS & set(index["domains"]))
        print(f"\nJSON-LD discovery surface: {JSONLD_FILE}")
        print(f"  public datasets: {public}")
        print(f"  excluded (private): {excluded}")


if __name__ == "__main__":
    main()

# llm: claude-opus-4-8 | 2026-06-26 | repos/vivify-inferences/build_index.py | created — global roll-up index: corpus-wide stats + per-domain category trees nested under domains key
# llm: claude-opus-4-8 | 2026-06-26 | repos/vivify-inferences/build_index.py | added --jsonld discovery surface (schema.org DataCatalog from index; private domains excluded)
# llm: claude-opus-4-8 | 2026-06-28 | repos/vivify-operators/build_index.py | ported from vivify-inferences — global roll-up + JSON-LD discovery surface
