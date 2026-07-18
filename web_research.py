#!/usr/bin/env python3
"""
web_research.py — grounded web query via retrieve-then-generate (Tavily + a free LLM)

Answers a question against LIVE web results, covering for any model's training cutoff.
Primary use: tracking the moving free-LLM landscape (which tiers exist now, which got
cancelled), but the query is open.

Two stages, deliberately decoupled (RAG-as-memory):
  1. RETRIEVE — Tavily (purpose-built for LLM/RAG, 1,000 searches/mo free, no card)
     returns ranked, LLM-ready source snippets. Needs TAVILY_API_KEY.
  2. GENERATE — a free synthesis model (the `web_research` capability in model_map,
     e.g. groq:llama-3.3-70b-versatile) answers using ONLY those snippets, then we
     append the source URLs so the output is citable.

Why not a provider's bundled web search? Empirically (2026-06-21) the free bundled
options are walled: Gemini grounding is billing-gated; Groq Compound free-tier 413s
when search content inflates the request. Decoupling search from synthesis sidesteps
both — search is swappable, synthesis stays on any free LLM.

A grounded web query is public information, so it is NOT sensitivity-tagged — the
privacy gate does not apply. Source the sealed keys.env first (TAVILY_API_KEY + the
synthesis model's key, e.g. GROQ_API_KEY).

Usage:
    ./web_research.py "which free LLM API tiers were discontinued recently?"
    echo "what changed in Groq's free tier?" | ./web_research.py
    ./web_research.py --model groq:openai/gpt-oss-120b "..."   # override synth model
    ./web_research.py --max-results 8 "..."
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import llm_call, llm_call_model, LLMUnavailable


class SearchUnavailable(RuntimeError):
    """Tavily retrieval failed — missing key, network error, or malformed response.
    Distinct from LLMUnavailable (the synthesis LLM failed)."""


def tavily_search(query: str, max_results: int = 5) -> list:
    """Retrieve ranked, LLM-ready web results via Tavily. Returns a list of
    {title, url, content}. Reads TAVILY_API_KEY (sourced from the sealed keys.env).
    Raises SearchUnavailable on missing key, network failure, or malformed response."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise SearchUnavailable("TAVILY_API_KEY not set — source the sealed keys.env first")
    body = json.dumps({
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
    except OSError as e:  # URLError / TimeoutError / socket errors are all OSError
        raise SearchUnavailable(f"tavily request failed: {e}")
    results = payload.get("results")
    if not results:
        raise SearchUnavailable(f"tavily returned no results: {str(payload)[:200]}")
    return [{"title": r.get("title", ""), "url": r.get("url", ""),
             "content": r.get("content", "")} for r in results]


def _synthesis_prompt(query: str, sources: list) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(f"[{i}] {s['title']}\n{s['url']}\n{s['content']}")
    context = "\n\n".join(blocks)
    return (
        "You are answering a question using ONLY the web search results below. "
        "Be specific and include dates where the sources give them. If the results "
        "do not answer the question, say so rather than guessing. Cite sources by "
        "their [number].\n\n"
        f"=== WEB SEARCH RESULTS ===\n{context}\n\n=== QUESTION ===\n{query}"
    )


def research(query: str, model: str = None, max_results: int = 5) -> str:
    """Retrieve via Tavily, synthesize via a free LLM, return the answer with sources
    appended. `model`: optional backend-prefixed id (e.g. 'groq:llama-3.3-70b-versatile')
    to override the routed `web_research` synthesis model. sensitive stays False — a
    grounded web query is public by definition. Raises SearchUnavailable / LLMUnavailable."""
    sources = tavily_search(query, max_results=max_results)
    prompt = _synthesis_prompt(query, sources)
    if model:
        answer = llm_call_model(prompt, model, sensitive=False)
    else:
        answer = llm_call(prompt, capability="web_research", sensitive=False)
    cited = "\n".join(f"[{i}] {s['title']} ({s['url']})" for i, s in enumerate(sources, 1))
    return f"{answer}\n\nSources:\n{cited}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Grounded web query: Tavily retrieve + free-LLM synthesize"
    )
    parser.add_argument("query", nargs="*", help="the question (or pipe it on stdin)")
    parser.add_argument("--model", help="override synth model id (e.g. groq:openai/gpt-oss-120b)")
    parser.add_argument("--max-results", type=int, default=5, help="Tavily results to retrieve")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query and not sys.stdin.isatty():
        query = sys.stdin.read().strip()
    if not query:
        parser.error("no query given (pass as arguments or pipe on stdin)")

    try:
        print(research(query, model=args.model, max_results=args.max_results))
    except (SearchUnavailable, LLMUnavailable) as e:
        print(f"web_research unavailable: {e}", file=sys.stderr)
        sys.exit(1)

# llm: claude-opus-4-8 | 2026-06-21 | repos/vivify-operators/web_research.py | rebuilt as retrieve-then-generate: Tavily search (no-card free) + free-LLM synthesis; bundled provider search was walled (Gemini billing-gated, Groq free 413s)
