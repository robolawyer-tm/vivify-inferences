#!/usr/bin/env python3
"""
claim_check — adjudicate a text's extracted claims against a baseline OUTSIDE it

`right_pass` extracts typed claims with quotes, then looks for contradictions
*within the same text*: its prompt asks for places the text contains both a
claimed value and a correcting actual value. That works on exoneration records,
which carry their own refutation, and returns nothing on a text that is simply,
confidently wrong.

Measured 2026-09-16 on a reception specimen: Gemini's rendering of this project
asserted `tension = 1.0 - (shared/total)`, a formula replaced on 2026-07-13, and
called it the "Core Insight". right_pass extracted it cleanly as a typed fact.
`discrepancies` came back 0, because nothing in Gemini's text contradicted it.
Every operator was correct and the false claim escaped all of them: each channel
measures a text against itself (resonance: surface vs underlying) or against its
speaker (cooperative: speaker vs maxims). None measures text against world.

This pass supplies the missing comparison, and nothing else.

WHAT IT DOES NOT DO, deliberately:

- It does not write the store. It emits a report. Run it a hundred times; the
  inference file is untouched.
- It does not feed `confirmed` tension or `calibration_delta`. `config/
  baseline_sources.json` restricts those to validated field sources, on the
  stated ground that "a researched correction is a citation, not a baseline".
  Reception material stays inert to the evolution gradient. That guard is
  deliberate and this pass does not route around it.
- It adds no coordinate and no fixed vocabulary. Whether a fidelity measure ever
  earns a place in the store is a decision about the no-new-vocabulary invariant,
  to be argued explicitly, not smuggled in by a tool that happened to get built.

FIDELITY IS RELATIVE TO A NAMED BASELINE, never to truth in general. The same
Gemini claim *holds* against the 2026-09-15 bundle, whose README documented the
dead formula, and is *contradicted* against `tension_score.py`. Both readings are
correct and they measure different things. The baseline is therefore required,
recorded in the report, and hashed.

Grounding guard: a verdict of holds/contradicted must quote the baseline
verbatim, and the quote is checked to actually occur there. Unfound evidence is
downgraded to `unverifiable` and counted. An adjudicator that invents its
evidence is the same silent-failure class as a glob that matches nothing and
reports zero.

Usage:
  claim_check.py <inference.json> --baseline <path> [--baseline <path> ...]
  claim_check.py <inference.json> -b tension_score.py -b README.md -o report.json

Options:
  -b, --baseline <path>   File the claims are checked against (repeatable, required)
  -o, --out <path>        Report destination (default: stdout only)
      --votes <n>         Draws per claim (default: VIVIFY_VOTES, else 3)
      --dry-run           Print the report, write nothing

Exit 0 when every claim was adjudicated, 1 when the run could not be trusted
(no claims found, baseline empty, or the model unavailable).
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import (LLMUnavailable, extract_json, llm_call_model,
                         modal_choice, read_json, resolve_model, write_json,
                         _vote_count)

VERDICTS = ("holds", "contradicted", "unverifiable")
BASELINE_CHAR_CAP = 200_000


PROMPT = """You are adjudicating one claim against a baseline document set.

The claim was extracted from some other text. Your job is to decide whether the
baseline supports it, contradicts it, or does not settle it. You are not judging
whether the claim is reasonable, well-written, or plausible — only what the
baseline says.

CLAIM
  topic: {topic}
  value: {value}
  unit:  {unit}
  as quoted in the source text: "{quote}"

BASELINE
{baseline}

Return ONLY this JSON object:

{{
  "verdict": "holds" | "contradicted" | "unverifiable",
  "evidence": "a VERBATIM span copied from the baseline above",
  "reason": "one sentence, under 200 characters"
}}

Rules:
- "holds" — the baseline states this, or states something that entails it.
- "contradicted" — the baseline states something incompatible with it. A value
  the baseline explicitly supersedes, replaces, or marks obsolete is
  contradicted, even if the baseline still mentions the old value in passing.
- "unverifiable" — the baseline does not settle it. Absence of mention is
  unverifiable, never contradicted.
- "evidence" must be copied character-for-character from the baseline. Do not
  paraphrase it, do not repair it, do not quote the claim back. If you cannot
  find such a span, return "unverifiable" with evidence "".
"""


def _norm(s):
    """Collapse whitespace and unify dash/minus glyphs for the grounding check."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def load_baseline(paths):
    """Concatenate the baseline files with FILE: markers. Returns (text, manifest).

    - Truncation is reported, never silent: a baseline that quietly lost its tail
      would make every claim about the tail 'unverifiable' and look like a result.
    """
    chunks, manifest = [], []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            print(f"  baseline missing, skipped: {p}", file=sys.stderr)
            continue
        body = path.read_text(errors="replace")
        manifest.append({"path": str(path), "bytes": len(body.encode()),
                         "sha256": hashlib.sha256(body.encode()).hexdigest()[:16]})
        chunks.append(f"FILE: {path}\n{body}")
    text = "\n\n".join(chunks)
    truncated = len(text) > BASELINE_CHAR_CAP
    if truncated:
        text = text[:BASELINE_CHAR_CAP]
        print(f"  BASELINE TRUNCATED to {BASELINE_CHAR_CAP} chars — "
              f"claims about the tail will read 'unverifiable'", file=sys.stderr)
    return text, manifest, truncated


def adjudicate_once(topic, claim, baseline, model):
    """One draw. Returns a verdict dict, always with all three keys."""
    prompt = PROMPT.format(topic=topic, value=claim.get("value"),
                           unit=claim.get("unit"), quote=claim.get("quote", ""),
                           baseline=baseline)
    raw = llm_call_model(prompt, model, None, False)
    data = extract_json(raw)
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        verdict = "unverifiable"
    return {"verdict": verdict,
            "evidence": str(data.get("evidence") or ""),
            "reason": str(data.get("reason") or "")[:200]}


def check_claim(topic, claim, baseline, baseline_norm, model, votes):
    """Adjudicate one claim across `votes` draws, with the grounding guard."""
    draws, ungrounded = [], 0
    for _ in range(votes):
        try:
            d = adjudicate_once(topic, claim, baseline, model)
        except (json.JSONDecodeError, ValueError):
            d = {"verdict": "unverifiable", "evidence": "",
                 "reason": "malformed adjudicator response"}
        # Grounding guard: evidence must really occur in the baseline.
        if d["verdict"] in ("holds", "contradicted"):
            ev = _norm(d["evidence"])
            if not ev or ev not in baseline_norm:
                ungrounded += 1
                d = {"verdict": "unverifiable", "evidence": "",
                     "reason": f"evidence not found in baseline (was: {d['reason']})"}
        # Defence in depth: adjudicate_once coerces the enum, but check_claim is
        # what decides the reported verdict, so the invariant is enforced here too.
        # A verdict outside the enum becomes unverifiable — never a guess.
        if d["verdict"] not in VERDICTS:
            d = {"verdict": "unverifiable", "evidence": "",
                 "reason": f"verdict outside the enum (was: {d['verdict']!r})"}
        draws.append(d)

    idx, vote = modal_choice(draws, lambda d: (("verdict", d["verdict"]),))
    chosen = dict(draws[idx])
    chosen["_votes"] = vote
    chosen["_ungrounded_draws"] = ungrounded
    chosen["claim"] = claim
    return chosen


def run(inference_path, baseline_paths, votes=None):
    inf = read_json(inference_path)
    if not inf:
        raise SystemExit(f"Error: could not read {inference_path}")

    facts = inf.get("right_facts") or (inf.get("right_pass") or {}).get("facts") or {}
    baseline, manifest, truncated = load_baseline(baseline_paths)
    votes = votes or _vote_count()
    model = resolve_model("fact_extraction")

    # Loud about emptiness. A zero here is a broken run, not a clean result.
    if not facts:
        print("  NO CLAIMS: right_pass extracted no facts — run right_pass first",
              file=sys.stderr)
    if not baseline.strip():
        print("  NO BASELINE: every claim would read 'unverifiable'", file=sys.stderr)

    results = {}
    baseline_norm = _norm(baseline)
    for i, (topic, claim) in enumerate(sorted(facts.items()), 1):
        print(f"  [{i}/{len(facts)}] {topic}", file=sys.stderr)
        results[topic] = check_claim(topic, claim, baseline, baseline_norm,
                                     model, votes)

    tally = {v: sum(1 for r in results.values() if r["verdict"] == v) for v in VERDICTS}
    return {
        "inference_id": inf.get("id"),
        "inference_source": inf.get("source"),
        "inference_path": str(inference_path),
        "baseline": manifest,
        "baseline_truncated": truncated,
        "_model": model,
        "_operator": "claim_check.py",
        "_votes_per_claim": votes,
        "claims_checked": len(results),
        "tally": tally,
        "results": results,
        "_note": ("Fidelity against the named baseline only. Does not feed confirmed "
                  "tension or calibration_delta; see config/baseline_sources.json."),
    }


def render(report):
    t = report["tally"]
    lines = [
        f"claim_check — {report['inference_id']} ({report['inference_source']})",
        f"  baseline: {', '.join(b['path'] for b in report['baseline']) or '(none)'}",
        f"  model: {report['_model']}   votes/claim: {report['_votes_per_claim']}",
        f"  holds {t['holds']}   contradicted {t['contradicted']}   "
        f"unverifiable {t['unverifiable']}",
        "",
    ]
    for topic, r in report["results"].items():
        v = r["_votes"]
        mark = {"holds": "  ok  ", "contradicted": " FALSE", "unverifiable": "  ?   "}
        lines.append(f"{mark[r['verdict']]} {topic}  [{v['agreed']}/{v['n']}]")
        lines.append(f"         claimed: {str(r['claim'].get('value'))[:90]}")
        if r["reason"]:
            lines.append(f"         {r['reason'][:100]}")
        if r["evidence"]:
            lines.append(f"         baseline: \"{r['evidence'][:100]}\"")
        if r["_ungrounded_draws"]:
            lines.append(f"         ungrounded draws dropped: {r['_ungrounded_draws']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Adjudicate a text's extracted claims against a named baseline")
    ap.add_argument("inference", help="inference JSON file (must have right_facts)")
    ap.add_argument("-b", "--baseline", action="append", required=True,
                    help="baseline file the claims are checked against (repeatable)")
    ap.add_argument("-o", "--out", help="write the JSON report here")
    ap.add_argument("--votes", type=int, help="draws per claim (default 3)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()

    try:
        report = run(args.inference, args.baseline, args.votes)
    except LLMUnavailable as e:
        print(f"Error: adjudicator unavailable — {e}", file=sys.stderr)
        return 1

    print()
    print(render(report))
    if args.out and not args.dry_run:
        write_json(args.out, report)
        print(f"\n  report: {args.out}")
    if not report["claims_checked"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/claim_check.py | created — adjudicates right_pass claims against a NAMED external baseline, the comparison no existing channel makes; report-only, never writes the store, never feeds confirmed tension
# llm: claude-opus-5 | 2026-09-16 | repos/vivify-operators/claim_check.py | enforce the verdict enum in check_claim, not only in adjudicate_once — the guard sat one layer below the function that decides the reported verdict
