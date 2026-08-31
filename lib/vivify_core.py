"""
vivify_core — autovivification engine

Perl-style hash-of-hashes in Python. Builds nested JSON structures from
key paths without requiring a predefined schema. Structure emerges from data.
"""

import json
from collections import defaultdict
from pathlib import Path


def autovivify():
    """Return a deeply nestable defaultdict — the core autovivification primitive."""
    return defaultdict(autovivify)


def deep_update(base, update):
    """Merge update into base recursively, creating nested keys as needed.

    - Existing keys are updated in place, not overwritten at the top level
    - New keys are created at any depth without prior declaration
    - Leaf values (non-dict) are replaced by the incoming value
    """
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def to_dict(obj):
    """Recursively convert autovivified defaultdicts to plain dicts for serialization.

    - Required before JSON serialization — defaultdict is not JSON-serializable
    - Safe to call on plain dicts (no-op)
    - Handles arbitrary nesting depth
    """
    if isinstance(obj, defaultdict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def write_json(path, data, indent=2, dry_run=False):
    """Write data to a JSON file, creating parent directories as needed.

    - path: str or Path
    - data: dict (will be serialized via to_dict first)
    - indent: pretty-print indent level
    - dry_run: if True, print what would be written without touching the filesystem
    """
    path = Path(path)
    if dry_run:
        print(f"[DRY RUN] would write to {path}:")
        print(json.dumps(to_dict(data), indent=indent))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(to_dict(data), f, indent=indent)


def add_dry_run_arg(parser):
    """Add --dry-run to an argparse parser — standard facility for scripts with side effects.

    Usage:
        add_dry_run_arg(parser)
        args = parser.parse_args()
        write_json(path, data, dry_run=args.dry_run)
    """
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be written or published without committing any changes"
    )


def read_json(path):
    """Read a JSON file and return as a plain dict.

    - Returns empty dict if file does not exist
    - Raises JSONDecodeError if file is malformed
    """
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


class LLMUnavailable(RuntimeError):
    """The claude CLI itself failed — quota exhausted, auth lost, or not installed.

    - Distinct from a per-inference content error (bad/missing JSON in a good response)
    - Signals that retrying further operators or inferences is futile until resolved
    - Callers running batches should catch this and abort rather than burn calls
    """


class PrivacyGateError(RuntimeError):
    """A sensitivity-tagged call was routed to a non-local backend while the
    privacy gate is on — data would leave the box. Blocked before any send.

    - Raised when sensitive=True AND backend not local AND the gate is not
      explicitly relaxed (PRIVACY_GATE is anything but 'off' — including unset)
    - Fail-closed by default: an unset gate BLOCKS sensitive off-box calls. The dev
      relaxation is the explicit opt-out PRIVACY_GATE=off, not the absence of a value
    - See project_model_routing.md
    """


class CoordinateValidationError(ValueError):
    """An operator's LLM output failed the inbound validation gate — an unknown
    enum value, an out-of-range number, a wrong type, or an over-long string
    (the injection guard). The counterpart to PrivacyGateError: that one guards
    what LEAVES the box, this one guards what a (possibly distal, untrusted) model
    is allowed to put INTO the inference store.

    - Fail-closed: a rejected result must NOT be merged; the caller quarantines it
    - Distinct from LLMUnavailable (transport down) — here the response arrived
      but its content is not a legal coordinate
    - Raised by validate_coordinates() against config/coordinates.json
    """


def _claude_transport(prompt, model, params=None):
    """Transport for the claude: backend — the claude CLI subprocess.

    No API key — uses Claude Code's own authentication. The original (and default)
    transport; bare model ids with no backend prefix route here. `params` (sampling
    knobs like temperature) are ignored — the `claude -p` CLI exposes no per-call
    sampling, so claude is not used as a diversity source in the quorum.
    """
    import subprocess
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise LLMUnavailable(result.stderr.strip() or f"claude exited {result.returncode}")
    return result.stdout.strip()


def _make_openai_transport(provider, base_url, env_key, extra_headers=None):
    """Build a transport for ANY OpenAI-compatible chat-completions endpoint.

    The whole distal team (deepseek, nvidia, openrouter, groq, mistral, …) is just
    instances of this — only base_url and env_key differ. Defined once, registered
    per provider from config/providers.json (see _load_providers).

    - Reads the key from `env_key` in the environment (sourced from the sealed
      keys.env.age — see project secrets seam). Key rides in the Authorization
      header, never in the prompt body.
    - Remote backend: excluded from LOCAL_BACKENDS, so the privacy gate blocks
      sensitivity-tagged data from reaching it when PRIVACY_GATE is on.
    - Raises LLMUnavailable on missing key, network failure, or malformed response.
    """
    def _transport(prompt, model, params=None):
        import os
        import urllib.request
        import urllib.error
        key = os.environ.get(env_key)
        if not key:
            raise LLMUnavailable(f"{env_key} not set — source the sealed keys.env first")
        payload_obj = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        # OpenAI-compatible sampling knobs go straight in the body (temperature,
        # top_p, seed, max_tokens) — this is how the quorum gets its diversity.
        for k in ("temperature", "top_p", "seed", "max_tokens"):
            if params and params.get(k) is not None:
                payload_obj[k] = params[k]
        body = json.dumps(payload_obj).encode()
        # Explicit User-Agent: some providers (e.g. Groq) sit behind Cloudflare, which
        # blocks the default 'Python-urllib/x' UA with a 403 (error 1010). Any real UA passes.
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                   "User-Agent": "vivify-operators/1.0"}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(base_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
        except OSError as e:
            # URLError, read TimeoutError, and socket errors are all OSError —
            # a slow free-tier model that times out must fail-soft, not crash.
            raise LLMUnavailable(f"{provider} request failed: {e}")
        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as e:
            raise LLMUnavailable(f"{provider} response malformed: {e}")
    return _transport


def _ollama_transport(prompt, model, params=None):
    """Transport for the ollama: backend — a LOCAL Ollama server. Data never leaves the box.

    - Talks to the Ollama HTTP API (default http://localhost:11434, override via
      OLLAMA_HOST; a host without scheme is assumed http). No API key — local service.
    - This is the privacy-safe tier: 'ollama' is in LOCAL_BACKENDS, so sensitivity-
      tagged data may route here even when the privacy gate is on.
    - `params` sampling knobs go in Ollama's "options" (temperature/top_p/seed,
      max_tokens -> num_predict) — this is what gives a single local model spread
      across quorum members.
    - Raises LLMUnavailable when the server is unreachable or the response is
      malformed (fail-fast, consistent with the other transports).
    """
    import os
    import urllib.request
    import urllib.error
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    host = host.rstrip("/")
    body_obj = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    options = {}
    if params:
        for k in ("temperature", "top_p", "seed"):
            if params.get(k) is not None:
                options[k] = params[k]
        if params.get("max_tokens") is not None:
            options["num_predict"] = params["max_tokens"]
    if options:
        body_obj["options"] = options
    body = json.dumps(body_obj).encode()
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read())
    except OSError as e:  # URLError / TimeoutError / socket errors are all OSError
        raise LLMUnavailable(f"ollama request failed (is the server running at {host}?): {e}")
    try:
        return payload["message"]["content"].strip()
    except (KeyError, TypeError) as e:
        raise LLMUnavailable(f"ollama response malformed: {e}")


def _gemini_transport(prompt, model, params=None):
    """Transport for the gemini: backend — Google Gemini's NATIVE generateContent API
    with Google Search grounding ALWAYS ON. This is the freshness channel: a query
    here is answered against live web results, covering for any model's training cutoff
    (e.g. 'which free LLM tiers exist / got cancelled now?').

    - Native API (not the OpenAI-compat shim): the shim rejects the grounding tool
      ('Unknown name google_search') and drops the source URLs. Native returns
      groundingMetadata, so we can hand back the citations — the valuable part.
    - Grounding needs Gemini 3+ (route model_map at e.g. gemini-3-flash). Free tier
      gives 5,000 grounded prompts/month, so keep this for occasional research, not bulk.
    - REMOTE backend (not in LOCAL_BACKENDS): the privacy gate blocks sensitivity-tagged
      data from reaching it when PRIVACY_GATE is on. A freshness probe is public info —
      callers leave sensitive=False (the default).
    - params sampling knobs map into generationConfig; LLMUnavailable on failure/empty.
    """
    import os
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMUnavailable("GEMINI_API_KEY not set — source the sealed keys.env first")
    body_obj = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }
    gen = {}
    if params:
        if params.get("temperature") is not None:
            gen["temperature"] = params["temperature"]
        if params.get("top_p") is not None:
            gen["topP"] = params["top_p"]
        if params.get("seed") is not None:
            gen["seed"] = params["seed"]
        if params.get("max_tokens") is not None:
            gen["maxOutputTokens"] = params["max_tokens"]
    if gen:
        body_obj["generationConfig"] = gen
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body_obj).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key,
                 "User-Agent": "vivify-operators/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read())
    except OSError as e:  # URLError / TimeoutError / socket errors are all OSError
        raise LLMUnavailable(f"gemini request failed: {e}")
    try:
        cand = payload["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        # empty candidates also happens on a safety block — surface, don't crash
        raise LLMUnavailable(f"gemini response malformed or blocked: {e}; {str(payload)[:200]}")
    if not text:
        raise LLMUnavailable("gemini returned no text (likely safety-blocked)")
    # Append grounding citations — the point of using the grounded channel.
    sources = []
    for chunk in cand.get("groundingMetadata", {}).get("groundingChunks", []):
        web = chunk.get("web", {})
        uri = web.get("uri")
        if uri:
            sources.append(f"- {web.get('title', uri)} ({uri})")
    if sources:
        text += "\n\nSources:\n" + "\n".join(sources[:8])
    return text


# Transport registry: backend prefix -> callable(prompt, model) -> response text.
# claude (CLI), ollama (local, no key) and gemini (native grounding) are bespoke —
# each has its own auth and response shape. Every hosted OpenAI-compatible provider is
# added from config/providers.json by _load_providers() below — a JSON line, no code.
TRANSPORTS = {
    "claude": _claude_transport,
    "ollama": _ollama_transport,
    "gemini": _gemini_transport,
}


def _load_providers():
    """Register every OpenAI-compatible provider in config/providers.json as a
    transport. The path is module-relative (cwd-independent). A missing or empty
    file is fine — claude + ollama still work; the distal team just isn't wired yet.
    """
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "providers.json"
    if not cfg_path.exists():
        return
    for name, cfg in read_json(cfg_path).items():
        if name in TRANSPORTS:
            # a bespoke transport already owns this backend (e.g. gemini's native
            # grounding transport) — don't silently clobber it with the generic shim
            continue
        TRANSPORTS[name] = _make_openai_transport(
            name, cfg["base_url"], cfg["env_key"], cfg.get("extra_headers"))


_load_providers()

# Backends where data never leaves the box. Sensitivity-tagged calls may go ONLY
# to these when the privacy gate is on. All OpenAI-compatible providers are remote
# and excluded; only local services belong here.
LOCAL_BACKENDS = {"ollama", "lok"}


def _privacy_gate_state():
    """Read PRIVACY_GATE as an explicit tristate: 'on', 'off', or None (unset).

    None (unset or an unrecognized value) is deliberately distinct from 'off'. The
    old silent 'off by default' meant one forgotten env var could leak real field
    data off-box; now only an EXPLICIT 'off' relaxes the gate, so forgetting it
    fails closed instead. See project_model_routing.md.
    """
    import os
    raw = os.environ.get("PRIVACY_GATE")
    if raw is None:
        return None
    v = raw.strip().lower()
    if v in ("on", "1", "true", "yes"):
        return "on"
    if v in ("off", "0", "false", "no"):
        return "off"
    return None  # unrecognized -> treat as unset, fail closed


def _enforce_privacy_gate(backend, sensitive):
    """Block sensitivity-tagged work from leaving the box unless the gate is
    EXPLICITLY relaxed. The single enforcement point for non-negotiables #1/#2.

    No-op when the call is not sensitive, or the backend is local. Otherwise the
    sensitive-data-leaving-the-box path is fail-closed: allowed ONLY when
    PRIVACY_GATE is explicitly 'off'. 'on', unset, and any unrecognized value all
    block — so forgetting to set the gate protects the data instead of leaking it.
    """
    if not sensitive or backend in LOCAL_BACKENDS:
        return
    state = _privacy_gate_state()
    if state == "off":
        return  # explicit development relaxation — the only path sensitive data leaves
    reason = ("PRIVACY_GATE is on" if state == "on"
              else "PRIVACY_GATE is unset — refusing to route sensitive data off-box "
                   "without an explicit decision (set PRIVACY_GATE=off to allow in dev)")
    raise PrivacyGateError(
        f"sensitivity-tagged call blocked: backend {backend!r} is not local "
        f"(local = {sorted(LOCAL_BACKENDS)}); {reason}"
    )


def split_backend(model_id):
    """Split a model id into (backend, model).

    The token before the first ':' selects a transport (e.g. 'deepseek:deepseek-chat',
    'ollama:qwen2.5:7b' -> split on the FIRST colon, so the model keeps its own tag
    colon). A bare id with no colon ('claude-sonnet-4-6') routes to claude, so existing
    model_map entries keep working unchanged. A colon-prefixed id whose prefix is NOT a
    registered backend is an error (typo or unregistered backend) — raised here rather
    than silently misrouted to claude, since no real model id contains a colon.
    """
    if ":" in model_id:
        prefix, rest = model_id.split(":", 1)
        if prefix in TRANSPORTS:
            return prefix, rest
        raise ValueError(
            f"unknown backend prefix {prefix!r} in model id {model_id!r}; "
            f"registered backends: {sorted(TRANSPORTS)}"
        )
    return "claude", model_id


def llm_call_model(prompt, model_id, params=None, sensitive=False):
    """Dispatch to an explicit backend-prefixed model id, bypassing capability
    routing. Used by quorum.py to address debate members directly (e.g.
    'ollama:llama3:8b', 'nvidia:meta/llama-3.1-70b-instruct') without needing a
    model_map entry. Same gate, transport, and fence-stripping as llm_call.

    - params: optional sampling knobs ({temperature, top_p, seed, max_tokens}) —
      how the quorum gets spread/divergence; ignored by transports that can't honor
      them (claude CLI).
    - Raises LLMUnavailable (model down) / PrivacyGateError (sensitive call leaving box).
    """
    import re
    backend, model = split_backend(model_id)
    _enforce_privacy_gate(backend, sensitive)
    text = TRANSPORTS[backend](prompt, model, params)
    # strip markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return text.strip()


def llm_call(prompt, capability="default", config_dir="config", sensitive=False, params=None):
    """Call an LLM for a capability and return the response text.

    - resolve_model() picks the model id; dispatch + gate + fence-strip via
      llm_call_model() (which split_backend()s and routes to the transport)
    - sensitive=True marks private field data; with PRIVACY_GATE on it may route
      only to a local backend (see _enforce_privacy_gate). Default False — callers
      handling private legal data pass sensitive=True so the gate can protect it.
    - params: optional sampling knobs passed through to the transport
    - Raises LLMUnavailable when a transport reports the model is down (not the data)
    - Raises PrivacyGateError when a sensitive call would leave the box (gate on)
    """
    return llm_call_model(prompt, resolve_model(capability, config_dir), params, sensitive)


def extract_json(text):
    """Extract the first valid JSON object from a string.

    Handles responses where the LLM adds explanation before or after the JSON.
    Raises json.JSONDecodeError if no valid JSON object is found.
    """
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise json.JSONDecodeError("Unterminated JSON object", text, start)


_coordinates_cache = {}

# The repo root — lib/vivify_core.py sits one level below it. Relative config_dir
# values are anchored here, never to the cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _config_path(config_dir, filename):
    """Resolve a config file, anchoring a relative config_dir to the repo root.

    Previously these were read as Path("config")/... — relative to the CWD — so
    running an operator from any other directory found nothing, and read_json's
    empty-dict-for-missing-file turned that into two silent failures rather than an
    error: model_map fell through to the hardcoded default model, and the
    coordinates spec went empty, disabling the enum gate entirely (out-of-enum
    values then validated clean). Both were invisible in the store.

    An absolute config_dir is honored as given, so callers can still point at a
    different config set deliberately.
    """
    base = Path(config_dir)
    if not base.is_absolute():
        base = _REPO_ROOT / base
    return base / filename


def _load_coordinates(config_dir="config"):
    """Read config/coordinates.json (the allowed-value spec), cached per path.
    Cwd-independent: a relative config_dir resolves against the repo root, not the
    cwd. Cached because operators call the gate once per inference in bulk runs."""
    path = _config_path(config_dir, "coordinates.json")
    key = str(path.resolve())
    if key not in _coordinates_cache:
        _coordinates_cache[key] = read_json(path)
    return _coordinates_cache[key]


def validate_coordinates(result, operator, config_dir="config"):
    """The inbound validation gate: check an operator's parsed LLM output against
    the allowed values in config/coordinates.json before it may enter the store.

    Returns the same dict on success, so callers write:
        result = validate_coordinates(extract_json(raw), "conflict")
    Raises CoordinateValidationError on the FIRST failure — fail-closed; a rejected
    result must NOT be merged. An operator with no spec entry still gets the global
    string-length guard, so a new operator is never silently blocked — only its
    declared fields are enforced, and only when present (presence of required keys
    is still enforced by the operator's own result[...] access).

    Checks, cheapest first:
      - global: every string value (declared or not) under _max_string_len — the
        injection guard, so a coordinate can't smuggle a paragraph or a command in
      - enums:  value in the operator's allowed set (or null if field is nullable)
      - floats: numeric (not bool) and within [lo, hi]
      - bools:  an actual bool
      - lists:  a list whose string elements obey the length cap
    """
    spec = _load_coordinates(config_dir)
    max_len = spec.get("_max_string_len", 600)
    op_spec = spec.get("operators", {}).get(operator, {})
    nullable = set(op_spec.get("nullable", []))

    def fail(field, why):
        raise CoordinateValidationError(
            f"{operator}.{field}: {why} (got {result.get(field)!r})")

    # global injection guard — cap every string the model returned, declared or not
    for field, val in result.items():
        if isinstance(val, str) and len(val) > max_len:
            fail(field, f"string exceeds {max_len} chars (injection guard)")

    for field, allowed in op_spec.get("enums", {}).items():
        if field not in result:
            continue
        val = result[field]
        # nullable fields accept JSON null and the common string stand-ins a small
        # model emits instead ("null"/"none"/empty) — don't reject those as enums
        if field in nullable and (val is None or
                (isinstance(val, str) and val.strip().lower() in ("null", "none", ""))):
            continue
        if val not in allowed:
            fail(field, f"not in {allowed}")

    for field, bounds in op_spec.get("floats", {}).items():
        if field not in result or result[field] is None:
            continue
        val = result[field]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            fail(field, "not a number")
        lo, hi = bounds
        if not (lo <= val <= hi):
            fail(field, f"outside [{lo}, {hi}]")

    for field in op_spec.get("bools", []):
        if field in result and not isinstance(result[field], bool):
            fail(field, "not a boolean")

    for field in op_spec.get("lists", []):
        if field not in result or result[field] is None:
            continue
        val = result[field]
        if not isinstance(val, list):
            fail(field, "not a list")
        for el in val:
            if isinstance(el, str) and len(el) > max_len:
                fail(field, f"list element exceeds {max_len} chars")

    return result


def call_and_validate(prompt, operator, capability="default", sensitive=False,
                      params=None, retries=2, config_dir="config"):
    """Call an LLM, parse and validate its output, retrying on invalid/malformed
    output before giving up. The standard operator entry point — replaces the bare
    validate_coordinates(extract_json(llm_call(...))) so a RECOVERABLE miss isn't
    silently dropped as a missing dimension.

    The privacy-safe tier (a small local model, e.g. ollama:llama3:8b) emits an
    out-of-enum value or broken JSON more often than a frontier model; one or two
    re-asks recover most of these. Retries re-issue the same prompt with a small
    temperature bump (on backends that honor it) to break out of a stuck wrong
    answer; the caller's prompt and validation rules are unchanged.

    - Retries CoordinateValidationError and json.JSONDecodeError only.
    - Does NOT retry LLMUnavailable — transport-down is fatal; it propagates so the
      batch can fail fast (re-asking a dead CLI just burns quota).
    - After `retries` extra attempts all fail, the last validation/parse error is
      raised, so the caller still quarantines exactly as before (fail-closed).
    - The validated result carries `_model`: the model id this call actually used,
      resolved ONCE up front rather than re-derived later, so an operator's parse()
      records what produced the coordinate instead of what the config says now.
    """
    model = resolve_model(capability, config_dir)
    last_err = None
    for attempt in range(retries + 1):
        call_params = dict(params or {})
        if attempt > 0 and "temperature" not in call_params:
            # nudge diversity only on retries; the first attempt honors caller intent
            call_params["temperature"] = round(0.3 * attempt, 2)
        raw = llm_call_model(prompt, model, call_params or None, sensitive=sensitive)
        try:
            result = validate_coordinates(extract_json(raw), operator, config_dir)
            result["_model"] = model
            return result
        except (CoordinateValidationError, json.JSONDecodeError) as e:
            last_err = e
    raise last_err


def model_override(capability):
    """Read VIVIFY_MODEL_OVERRIDE — the model-comparison arm switch, env-scoped.

    Swapping models by editing config/model_map.json is the wrong mechanism for an
    experiment: a forgotten revert silently re-models every later run, and nothing
    in the store would say so. An env var dies with the shell.

    Two forms:
      VIVIFY_MODEL_OVERRIDE=claude-fable-5
          every capability, including web_research — the blunt whole-pipeline arm
      VIVIFY_MODEL_OVERRIDE=logos_operator=claude-fable-5,conflict_operator=claude-fable-5
          named capabilities only; everything else keeps its mapped model. This is
          the form that isolates one variable — swap the coordinate producers and
          hold semantic_extraction fixed, so left keywords stay comparable.

    - Returns the override model id for this capability, or None
    - Malformed entries are skipped rather than raising: a typo'd arm must not
      take down a run, and _model in the store records what was ACTUALLY used
    """
    import os
    raw = os.environ.get("VIVIFY_MODEL_OVERRIDE", "").strip()
    if not raw:
        return None
    if "=" not in raw:
        return raw
    for entry in raw.split(","):
        cap, _, model = entry.partition("=")
        if cap.strip() == capability and model.strip():
            return model.strip()
    return None


def resolve_model(capability, config_dir="config"):
    """Return the model ID for a named capability from config/model_map.json.

    - VIVIFY_MODEL_OVERRIDE wins over the map when it names this capability
      (see model_override) — the experiment switch, never a config edit
    - Falls back to 'default' if capability not found
    - Falls back to claude-sonnet-4-6 if config missing. A relative config_dir is
      anchored to the repo root (see _config_path), so this fallback now means the
      map is genuinely absent — not merely that the caller ran from elsewhere.
    """
    override = model_override(capability)
    if override:
        return override
    model_map = read_json(_config_path(config_dir, "model_map.json"))
    return model_map.get(capability) or model_map.get("default", "claude-sonnet-4-6")


if __name__ == "__main__":
    import sys
    import fileinput

    print("vivify_core — autovivification engine self-test")
    print()

    # Demo: build a nested structure from scratch
    store = autovivify()
    store["conflict"]["legal"]["perjury"] = "detected"
    store["conflict"]["legal"]["timeline"] = ["2024-01", "2024-03"]
    store["outcome"]["prediction"] = "adverse"

    result = to_dict(store)
    print(json.dumps(result, indent=2))

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/lib/vivify_core.py | created — autovivification engine, deep_update, JSON I/O
# llm: claude-sonnet-4-6 | 2026-04-27 | repos/vivify-inferences/lib/vivify_core.py | added resolve_model() — capability-to-model routing via config/model_map.json
# llm: claude-sonnet-4-6 | 2026-05-18 | repos/vivify-inferences/lib/vivify_core.py | added dry_run param to write_json(); add_dry_run_arg() helper for argparse
# llm: claude-opus-4-8 | 2026-06-20 | repos/vivify-operators/lib/vivify_core.py | added inbound validation gate: CoordinateValidationError, _load_coordinates(), validate_coordinates() against config/coordinates.json
# llm: claude-sonnet-4-6 | 2026-05-22 | repos/vivify-inferences/lib/vivify_core.py | added llm_call() — claude CLI subprocess, no API key required, strips markdown fences
# llm: claude-opus-4-8 | 2026-06-15 | repos/vivify-operators/lib/vivify_core.py | added LLMUnavailable exception — llm_call raises it on CLI failure (quota/auth) so batches can fail-fast
# llm: claude-opus-4-8 | 2026-06-17 | repos/vivify-operators/lib/vivify_core.py | step 1 multi-backend dispatch — TRANSPORTS registry + split_backend(); claude is a transport, bare ids backward-compatible; gate seam left for step 2
# llm: claude-opus-4-8 | 2026-06-17 | repos/vivify-operators/lib/vivify_core.py | step 2 privacy gate — PrivacyGateError + LOCAL_BACKENDS + _enforce_privacy_gate(); llm_call gains sensitive flag; gated behind PRIVACY_GATE env (off by default, one-flip to reinstate)
# llm: claude-opus-4-8 | 2026-06-17 | repos/vivify-operators/lib/vivify_core.py | step 3 deepseek transport — stdlib urllib, key from DEEPSEEK_API_KEY (header not prompt), LLMUnavailable on failure; split_backend now raises on unregistered colon-prefix instead of misrouting to claude
# llm: claude-opus-4-8 | 2026-06-17 | repos/vivify-operators/lib/vivify_core.py | step 4 ollama transport — local HTTP /api/chat (OLLAMA_HOST override), no key, in LOCAL_BACKENDS so privacy-gate-safe for sensitive data; LLMUnavailable when server down
# llm: claude-opus-4-8 | 2026-06-19 | repos/vivify-operators/lib/vivify_core.py | generalized deepseek into _make_openai_transport factory + config/providers.json loader (_load_providers); distal team (deepseek/nvidia/openrouter/groq/mistral/cerebras/gemini) now data-driven — adding a provider is one JSON line
# llm: claude-opus-4-8 | 2026-06-19 | repos/vivify-operators/lib/vivify_core.py | threaded params (temperature/top_p/seed/max_tokens) through all transports (openai body, ollama options, claude ignores); added llm_call_model() direct-model entry for quorum.py
# llm: claude-opus-4-8 | 2026-06-19 | repos/vivify-operators/lib/vivify_core.py | broadened transport network except URLError->OSError so read TimeoutError fails-soft as LLMUnavailable (was crashing the quorum on a slow free-tier member)
# llm: claude-opus-4-8 | 2026-06-21 | repos/vivify-operators/lib/vivify_core.py | added native Gemini grounding transport (_gemini_transport, Google Search always-on + citations) as the web-research freshness channel; _load_providers no longer clobbers bespoke transports
# llm: claude-opus-4-8 | 2026-06-21 | repos/vivify-operators/lib/vivify_core.py | send explicit User-Agent on OpenAI-compat + gemini transports — Groq is behind Cloudflare which 403s (error 1010) the default Python-urllib UA
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/lib/vivify_core.py | safe-default privacy gate: _privacy_gate_state() tristate, unset/unrecognized now fails CLOSED for sensitive off-box calls (only explicit PRIVACY_GATE=off relaxes) — forgetting the env protects data instead of leaking it
# llm: claude-opus-4-8 | 2026-06-24 | repos/vivify-operators/lib/vivify_core.py | added call_and_validate() — retries CoordinateValidationError/JSONDecodeError (temp bump on retry) before fail-closing, so a recoverable small-model miss isn't dropped as a missing dimension; LLMUnavailable still propagates
# llm: claude-opus-5 | 2026-08-13 | repos/vivify-operators/lib/vivify_core.py | VIVIFY_MODEL_OVERRIDE (bare = all capabilities, scoped = capability=model pairs) via model_override(); call_and_validate resolves the model once, calls llm_call_model directly, stamps result["_model"]
# llm: claude-opus-5 | 2026-08-27 | repos/vivify-operators/lib/vivify_core.py | _config_path(): relative config_dir now anchors to the repo root, not the cwd — fixes silent model downgrade to the hardcoded default AND a silently disabled coordinate enum gate when run from any other directory
