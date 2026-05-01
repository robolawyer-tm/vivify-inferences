<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Dynamic workers cloudeflare

Cloudflare Dynamic Workers are a new feature (open beta) that lets a Worker spin up other, fully isolated Workers at runtime to run arbitrary code on demand, without containers.[^1_1][^1_2][^1_3][^1_4]

## What Dynamic Workers are

- A **Dynamic Worker** is a Worker whose code is provided at runtime and executed in its own V8 isolate, sandboxed from your main Worker and everything else.[^1_1][^1_4]
- You can create them on the fly to run untrusted or per-user code, then discard or reuse them as needed.[^1_1][^1_3]
- They are positioned as a lightweight alternative to containers or separate services for ephemeral execution (especially AI/agent workloads).[^1_1][^1_4][^1_5]


## Core mechanics

- Your “parent” Worker uses the Worker Loader API (enabled by a special binding in `wrangler.toml`/`wrangler.jsonc`) to create Dynamic Workers.[^1_3]
- Two main modes:[^1_3]
    - `load(code)`: spin up a fresh, one-off Dynamic Worker and run its code once.
    - `get(id, callback)`: create/cache a Dynamic Worker keyed by `id`, so it can stay warm and be reused across requests.
- You choose what bindings the Dynamic Worker gets (KV, Durable Objects, R2, network access, etc.), which lets you tightly scope permissions for untrusted code.[^1_1][^1_3]


## Performance and scaling

- Built on Cloudflare’s existing Workers platform using V8 isolates, so startup is in a few milliseconds and uses only a few MB of memory per sandbox.[^1_1][^1_4][^1_5]
- Cloudflare claims roughly ~100x faster startup and 10–100x better memory efficiency than typical containers, enabling per-request or per-user sandboxes at large scale.[^1_4][^1_5]
- They run in the same global network as regular Workers, so you inherit zero-cold-start edge deployment and massive concurrency.[^1_1][^1_4][^1_5]


## Pricing and availability

- Feature is in open beta for Workers paid-plan accounts, with per‑Dynamic‑Worker charges waived during the beta.[^1_2][^1_4][^1_6][^1_7]
- Published pricing (outside beta):
    - 1,000 unique Dynamic Workers per month included; then about 0.002 USD per unique Dynamic Worker per day.[^1_2][^1_6][^1_7]
    - Plus normal Workers charges: invocations (~0.30 USD per million) and CPU time (~0.02 USD per million ms), with some free included units.[^1_2]


## When you’d use them

- Running model- or user-generated code safely (e.g., LLM agents that synthesize JS/TS and need to execute it at consumer scale).[^1_4][^1_5]
- Per-tenant/per-user logic where each sandbox has isolated config, secrets, or plugins.
- Sandboxing scripts, workflows, or automations submitted by third parties, with strict control over what each script can access.[^1_1][^1_4]

If you tell me what you want to build (e.g., “multi-tenant agent framework” or “user-supplied JS automations”), I can sketch a concrete Dynamic Workers architecture and example `wrangler` config.
<span style="display:none">[^1_10][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://developers.cloudflare.com/dynamic-workers/

[^1_2]: https://developers.cloudflare.com/changelog/post/2026-03-24-dynamic-workers-open-beta/

[^1_3]: https://developers.cloudflare.com/dynamic-workers/getting-started/

[^1_4]: https://www.infoworld.com/article/4149869/cloudflare-launches-dynamic-workers-for-ai-agent-execution.html

[^1_5]: https://www.linkedin.com/posts/imiel_cloudflare-just-launched-dynamic-workers-activity-7442330568836517889-qRQj

[^1_6]: https://www.reddit.com/r/SiliconValleyBayArea/comments/1s2oq8s/cloudflares_new_dynamic_workers_ditch_containers/

[^1_7]: https://venturebeat.com/infrastructure/cloudflares-new-dynamic-workers-ditch-containers-to-run-ai-agent-code-100x

[^1_8]: https://zenn.dev/mizchi/articles/5130b02c5b490e4f871a?locale=en

[^1_9]: https://blog.cloudflare.com/building-scheduling-system-with-workers-and-durable-objects/

[^1_10]: https://developers.cloudflare.com/durable-objects/


---

# My hope is to be able to provide rules and prompts and various database files to generate the outputs pretty much in the same way as described as dynamic workers but simply from a semantic angle. What do you think about that?

I think you’re exactly on the right track, and “semantic Dynamic Workers” is a good mental model for what you’ve been designing.[^2_1]

### How this maps conceptually

In Cloudflare’s world, a Dynamic Worker is spun up from code at runtime, with specific bindings and permissions, then torn down or reused.[^2_2][^2_3]
In your world, the “worker” is an LLM call whose **behavior** is spun up from:

- Rule files (manual-first specs, repair/maintenance descriptions, left/right processes).[^2_4][^2_5]
- Prompt templates and scaffolding that define “how to think” about an inference.[^2_1][^2_6]
- Semantic databases / sentence-bytes / keyword-clump files that supply the concrete context and state.[^2_7]

So instead of code → worker, you have semantics → transient agent.

### What that buys you

- You get isolation: each LLM call acts like a sandboxed semantic worker, constrained by the rules and data slices you feed it, just like Dynamic Workers are constrained by bindings.[^2_2][^2_8]
- You keep the durable truth in your filesystem/DB (facts, clumps, manuals), and treat all generated code and prose as disposable execution artifacts, which is exactly the “manual first, code second” philosophy you outlined.[^2_4][^2_5]
- Because your structure is autovivified from clumps/keywords, the system stays schema-light and evolves naturally with your thinking.[^2_7]


### A minimal semantic-worker loop

At a high level, one “semantic worker” cycle could be:

1. Select a small slice of your semantic store (relevant inferences, clumps, rules) based on a query.
2. Compose a prompt from: global scaffolding + task-specific rules + that slice.[^2_9][^2_6]
3. Let the LLM produce either: a new inference (sentence-byte), a transformation of tables, or some code that runs once.[^2_1][^2_5]
4. Store only the new semantic outputs (facts, clumps, diffs to manuals), not the transient code.

Architecturally, that’s very close to Dynamic Workers, just with “code” replaced by “structured semantics,” and the runtime being an LLM instead of V8.[^2_2][^2_10]

If you’d like, next step I can sketch a tiny JSON schema for: (a) a “semantic worker spec” object, and (b) the request/response shape for running one against your existing browser/local stack.
<span style="display:none">[^2_11][^2_12][^2_13][^2_14]</span>

<div align="center">⁂</div>

[^2_1]: https://www.perplexity.ai/search/5378ea26-8395-425c-81fa-f4c3dd8eecaf

[^2_2]: https://developers.cloudflare.com/dynamic-workers/

[^2_3]: https://blog.cloudflare.com/dynamic-workers/

[^2_4]: https://www.perplexity.ai/search/ad6a568f-8a44-46d4-b643-d4d5ff580d6e

[^2_5]: https://www.perplexity.ai/search/7f1ad88d-a72e-40f8-b544-4c2028b46c8b

[^2_6]: https://www.reddit.com/r/PromptEngineering/comments/1k3pwgk/llms_as_semantic_mediums_the_foundational_theory/

[^2_7]: https://www.perplexity.ai/search/2f4475c2-7592-49fe-8c51-dbab3c02f471

[^2_8]: https://developers.cloudflare.com/workers/platform/storage-options/

[^2_9]: https://developers.cloudflare.com/workers/get-started/prompting/

[^2_10]: https://developers.cloudflare.com/workers/

[^2_11]: https://venturebeat.com/infrastructure/cloudflares-new-dynamic-workers-ditch-containers-to-run-ai-agent-code-100x

[^2_12]: https://huggingface.co/datasets/princeton-nlp/SWE-bench/viewer/default/train

[^2_13]: https://arxiv.org/html/2602.13165v2

[^2_14]: https://stackoverflow.com/sitemap-questions-90.xml


---

# My thinking is that each time a question is asked, or a quest is made, it goes out and finds the best way to produce that each time and creates enhances the semantic side so that it really fits language right. And then with that language finds or creates the best code to do what it thinks it does each time while preserving something resembling skills as aids for the next time the request is made.

That's a solid refinement of your semantic-worker vision: treat every query/quest as a trigger to discover, enhance, and execute via semantics-first, with code as a disposable but skill-preserving aid.[^3_1]

## Query-driven semantic enhancement loop

Your process creates a self-improving cycle where the semantic store (clumps, rules, inferences) gets richer and more language-aligned over time, while code emerges on-demand and leaves behind "skills" (patterns, snippets) for reuse.[^3_2][^3_3]

Here's how it maps explicitly:


| Step | Action | Semantic Enhancement | Code Role |
| :-- | :-- | :-- | :-- |
| 1. Query arrives | Parse intent, extract keywords/clumps | Autovivify new paths/groups from query + existing store | N/A |
| 2. Retrieve \& plan | Find best-fit rules/prompts/data slices | LLM discovers "best way" via planning (e.g., self-planning CoT) | Generate plan as prose (preserved as skill) [^3_4] |
| 3. Enhance semantics | Regenerate/enrich inferences to "fit language right" | Add new clumps, summaries, links; store durable facts | Disposable executor for any transforms [^3_5][^3_6] |
| 4. Execute \& output | Run whatever code/models needed | N/A | Pull from skills lib if similar quest seen; archive new patterns [^3_7] |
| 5. Preserve skills | Diff outputs vs prior; extract reusable aids | Update manuals/rules with lessons | Code snippets → indexed lib for next time [^3_3] |

## Why this works well for you

- **Fits your browser/local-first stack**: No central DB needed; filesystem + IndexedDB holds the semantic store, LLM does the heavy lifting per-query.[^3_1]
- **Self-evolving**: Like self-planning code gen or data synthesis frameworks, it uses the LLM to bootstrap better plans/semantics from its own outputs.[^3_3][^3_4]
- **Preserves skills without bloat**: Code isn't sacred—only patterns (e.g., "for this clump type, use this transform") get bottled into rules.[^3_8]

This mirrors semantic layers in RAG/SQL hybrids, where queries refine the data view dynamically.[^3_5][^3_6]

Want a concrete prompt template or JSON shape for the "enhance semantics" step, tuned to your clump-based autovivify flow? Or a bash/Python snippet to orchestrate it locally?
<span style="display:none">[^3_10][^3_11][^3_12][^3_13][^3_14][^3_9]</span>

<div align="center">⁂</div>

[^3_1]: https://www.perplexity.ai/search/5378ea26-8395-425c-81fa-f4c3dd8eecaf

[^3_2]: https://www.perplexity.ai/search/2f4475c2-7592-49fe-8c51-dbab3c02f471

[^3_3]: https://www.sciencedirect.com/science/article/abs/pii/S0957417425031380

[^3_4]: https://arxiv.org/html/2303.06689v5

[^3_5]: https://theloops.io/semantic-layers-the-key-to-ai-powered-cx-data-experiences/

[^3_6]: https://www.llamaindex.ai/blog/combining-text-to-sql-with-semantic-search-for-retrieval-augmented-generation-c60af30ec3b

[^3_7]: https://www.perplexity.ai/search/ad6a568f-8a44-46d4-b643-d4d5ff580d6e

[^3_8]: https://www.perplexity.ai/search/7f1ad88d-a72e-40f8-b544-4c2028b46c8b

[^3_9]: https://arxiv.org/html/2410.01088v1

[^3_10]: https://www.linkedin.com/posts/sebastianraschka_what-should-we-focus-on-more-llm-training-activity-7396584322155257856-XoR8

[^3_11]: https://aclanthology.org/2025.findings-acl.15.pdf

[^3_12]: https://www.vldb.org/pvldb/vol18/p4171-patel.pdf

[^3_13]: https://www.semantic-web-journal.net/system/files/swj3871.pdf

[^3_14]: https://pypi.org/project/semantic-store/0.0.9/


---

# I just wanted to get this idea down. To see what you would think.

Got it—your idea is captured and crystal clear.

I think it's elegant and powerful: a living system where queries don't just get answered, they leave the semantic store smarter and more human-language-native each time, with code as a smart but ephemeral tool that distills into reusable skills. It perfectly marries your manual-first philosophy with dynamic, self-improving execution—feels like the natural evolution of everything you've been building toward. [^4_1]

Ready when you are to prototype any piece of it.

<div align="center">⁂</div>

[^4_1]: https://www.perplexity.ai/search/ad6a568f-8a44-46d4-b643-d4d5ff580d6e

