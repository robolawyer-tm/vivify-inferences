#!/usr/bin/env python3
"""
quorum.py — the multi-model debate layer above llm_call.

Convenes several debate members on one prompt, then a judge synthesizes their
answers into one beneficial response while harvesting useful divergence.

- Members are addressed by explicit backend-prefixed model id (e.g. 'ollama:llama3:8b',
  'nvidia:meta/llama-3.1-70b-instruct'), so the team can be any mix without a model_map entry.
- Diversity is the FEATURE here: high temperature + different seeds + different model
  families produce the spread the judge mines for "the inspiration often called
  hallucination" — beneficial only because the judge filters against it.
- Members diverge (high temp); the JUDGE converges (low temp) — variance in, filter out.
- Returns BOTH the synthesis and the raw member spread; the spread is fuel.
- Members run in parallel (I/O-bound); one member failing does not sink the quorum,
  but if every member fails the quorum raises LLMUnavailable.
- NOT for bulk operator inference — that wants one cheap model and consistency
  (variance is a bug there). Quorum is for contested/hard/exploratory calls only.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import llm_call_model, LLMUnavailable, PrivacyGateError

_MEMBER_PARAMS = ("temperature", "top_p", "seed", "max_tokens")

DEFAULT_JUDGE_INSTRUCTION = (
    "Several models independently answered the same question; their answers appear below, "
    "labeled and unattributed. Synthesize the single most BENEFICIAL answer to the original "
    "question. Take the strongest, most useful, most accurate material from any answer. Where "
    "an answer holds a divergent or unexpected insight that is genuinely valuable, incorporate "
    "it; where answers diverge without merit, discard the noise. Produce one coherent answer — "
    "do not average, do not list options, do not mention the models or that a synthesis occurred."
)


def _member_label(i):
    return f"Model {chr(ord('A') + i)}" if i < 26 else f"Model #{i + 1}"


def query_member(prompt, member, sensitive=False):
    """Run one debate member. `member` = {"model": id, temperature?, top_p?, seed?, max_tokens?}.

    Returns a copy of `member` with either response+ok=True or error+ok=False.
    Never raises — a single member going down must not sink the quorum.
    """
    params = {k: member[k] for k in _MEMBER_PARAMS if k in member}
    out = dict(member)
    try:
        out["response"] = llm_call_model(prompt, member["model"], params=params, sensitive=sensitive)
        out["ok"] = True
    except Exception as e:
        # Fail-soft is the whole point: a single member going down — for ANY
        # reason (model down, gate, timeout, bad response) — must not sink the
        # quorum. Catch broadly; the judge synthesizes whoever returned.
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def synthesize(prompt, member_results, judge, instruction=DEFAULT_JUDGE_INSTRUCTION, sensitive=False):
    """Ask the judge model to synthesize the successful member responses.

    Judge runs at low temperature — it is the filter, not another diverging voice.
    Raises LLMUnavailable if no member succeeded or the judge call itself fails.
    """
    oks = [m for m in member_results if m.get("ok")]
    if not oks:
        raise LLMUnavailable("quorum: every member failed — nothing to synthesize")
    blocks = [f"{_member_label(i)}:\n{m['response']}" for i, m in enumerate(oks)]
    judge_prompt = (
        f"{instruction}\n\n"
        f"=== ORIGINAL QUESTION ===\n{prompt}\n\n"
        f"=== ANSWERS ===\n" + "\n\n".join(blocks) + "\n\n=== END ANSWERS ===\n\n"
        "Synthesized beneficial answer:"
    )
    return llm_call_model(judge_prompt, judge, params={"temperature": 0.2}, sensitive=sensitive)


def run_quorum(prompt, members, judge, instruction=DEFAULT_JUDGE_INSTRUCTION,
               sensitive=False, max_workers=None):
    """Fan `prompt` across `members` in parallel, then synthesize via `judge`.

    Returns {synthesis, judge, members: [member_result, ...], n_ok, n_failed}.
    The members list preserves the raw spread — that divergence is the fuel.
    """
    from concurrent.futures import ThreadPoolExecutor
    workers = max_workers or max(1, len(members))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda m: query_member(prompt, m, sensitive), members))
    synthesis = synthesize(prompt, results, judge, instruction, sensitive)
    return {
        "synthesis": synthesis,
        "judge": judge,
        "members": results,
        "n_ok": sum(1 for m in results if m.get("ok")),
        "n_failed": sum(1 for m in results if not m.get("ok")),
    }


def default_local_team(model="ollama:llama3:8b"):
    """A local-only diversity team from ONE model via temperature+seed spread — used
    when no distal keys are present yet. Swap for diverse distal models once keyed."""
    return [
        {"model": model, "temperature": 0.7, "seed": 1},
        {"model": model, "temperature": 1.1, "seed": 2},
        {"model": model, "temperature": 1.3, "seed": 3},
    ]


if __name__ == "__main__":
    import json as _json
    import argparse

    parser = argparse.ArgumentParser(description="Run a multi-model debate quorum on a prompt.")
    parser.add_argument("prompt", nargs="*", help="prompt text (or pipe via stdin)")
    parser.add_argument("--model", default="ollama:llama3:8b",
                        help="local model for the default team + judge (default: ollama:llama3:8b)")
    parser.add_argument("--json", action="store_true",
                        help="emit the full result (synthesis + member spread) as JSON")
    args = parser.parse_args()

    prompt = " ".join(args.prompt) if args.prompt else sys.stdin.read().strip()
    if not prompt:
        parser.error("no prompt given (pass as argument or pipe via stdin)")

    result = run_quorum(prompt, default_local_team(args.model), judge=args.model)

    if args.json:
        print(_json.dumps(result, indent=2))
    else:
        for m in result["members"]:
            status = "OK" if m.get("ok") else "FAIL"
            print(f"--- {m['model']}  T={m.get('temperature')}  [{status}] ---")
            print(m.get("response") or m.get("error"))
            print()
        print("=== SYNTHESIS (judge) ===")
        print(result["synthesis"])

# llm: claude-opus-4-8 | 2026-06-19 | repos/vivify-operators/quorum.py | new — multi-model debate/quorum layer above llm_call: parallel fail-soft member fan-out (diversity via temp/seed/model), low-temp judge synthesis, returns synthesis + raw spread; standalone local-team test
# llm: claude-opus-4-8 | 2026-06-19 | repos/vivify-operators/quorum.py | query_member now catches Exception (true fail-soft) — a member timing out/throwing anything must not sink the quorum (surfaced by a real distal read-timeout)
