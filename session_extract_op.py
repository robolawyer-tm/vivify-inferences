#!/usr/bin/env python3
"""
session_extract_op — operator-aware inference extraction from a Claude Code session

Reads a cleaned session transcript and extracts 3-8 inference paragraphs framed
through the logos operator schema dimensions (act_type, transmission, resonance,
authority, utility, cooperative/Grice, social_field). This makes vivify's left-
semantic pass extract operator-calibrated keywords rather than surface technical
terms — enabling a proper claude_code_sessions domain with its own FABRIC pipeline,
parallel to but isolated from the logos/social-science coordinate space.

Usage:
  cat session-clean.md | python3 session_extract_op.py --dir inferences/claude_code_sessions
  python3 session_extract_op.py --input session-clean.md --dir inferences/claude_code_sessions
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from vivify_core import llm_call, LLMUnavailable


MAX_CHARS = 100_000

SEPARATOR = "---INFERENCE---"

OPERATOR_VOCAB = """
Operator dimensions — use this vocabulary to frame each inference:

ACT_TYPE — what the communication performs:
  assertive:   claims something is true
  directive:   attempts to get someone to act
  commissive:  commits the speaker to future action
  expressive:  expresses psychological state
  declaration: changes reality by being said (a verdict, a pivot, a naming)

TRANSMISSION — how the communication moves:
  broadcast:  one-to-many, public, low fidelity to source
  leak:       restricted, few recipients, high emotional charge, unofficial
  archive:    past-to-future, preserved, resistant to revision

RESONANCE — the field the communication creates:
  harmony:    synchronization, shared understanding, empathic alignment
  friction:   disconnection, dissonance, unempathic states
  illusion:   apparent harmony masking underlying friction

AUTHORITY — what power structure it draws on to be heard:
  sovereign:  top-down, institutional, formal
  tribal:     horizontal, peer, normative, earned through practice
  occult:     hidden, not publicly acknowledged, known only within a restricted group

UTILITY — its functional payload:
  instruction: actionable, enabling — tells how or what to do
  narrative:   meaning-making, contextualizing, mythologizing
  currency:    value-tracking, social capital, ledger of obligation

COOPERATIVE (Grice's maxims — violation generates tension):
  quantity: say enough, not too much
  quality:  say what you believe to be true
  relation: say what is relevant
  manner:   be clear and orderly
  A violated maxim creates implicature — meaning beyond the words — which is a tension signal.

SOCIAL_FIELD (Douglas grid/group):
  grid:  degree to which behavior is rule-constrained (0.0=free, 1.0=rigid)
  group: degree to which identity is defined by group membership (0.0=individual, 1.0=collective)
"""

EXTRACT_PROMPT = f"""You are reading a Claude Code development session transcript.

Your task: extract 3-8 discrete inference units from this session.

Each inference unit must:
- Identify one distinct architectural decision, conceptual pivot, or structural development
- Frame it using the operator vocabulary below — use operator terms naturally in the prose
- Describe: what tension drove this development, what act-type it represents, what restoration
  move was made, what resonance state resulted (harmony restored, friction named, etc.)
- Be self-contained — readable without surrounding session context
- Be a coherent prose paragraph (not bullet points or fragments)
- Capture the WHY and the structural meaning, not the HOW of implementation

Write with operator vocabulary woven naturally into the prose, so terms like
friction_state, authority_resolution, tribal_knowledge, directive_commissive,
harmony_restoration, occult_dependency appear as semantic anchors.

Ignore: file contents, JSON blobs, tool outputs, error messages, shell commands, terminal chrome.
Focus on: architectural decisions, conceptual pivots, terminology established, problems solved,
domain boundaries drawn, tensions named and resolved.

Operator vocabulary:
{OPERATOR_VOCAB}
Output each inference as a plain paragraph. Separate each with a line containing only:
{SEPARATOR}

No JSON, no bullet points, no numbering. Just paragraphs separated by the marker.

Session transcript:
"""


SYSTEM_FRAME = """You extract operator-calibrated inference paragraphs from development
session transcripts. Use the operator vocabulary provided to frame decisions as
communicative acts in a social field. Output plain text paragraphs separated by the
marker the user specifies. No JSON, no markdown.

"""


def extract_inferences(session_text):
    """Extract operator-framed inference paragraphs from a session transcript.

    Routed through vivify_core.llm_call rather than this tool's own `claude -p`
    subprocess. The direct call bypassed BOTH the privacy gate and config/model_map.json
    — the same defect fixed in vivify.py's left pass on 2026-08-13 — so this tool was
    the last place in the pipeline where neither applied.

    Two behaviour changes fall out of using the shared transport:
      - the CLI's --system-prompt has no equivalent, so the system frame is folded
        into the head of the prompt
      - --no-session-persistence is likewise dropped (the transport does not persist)

    sensitive stays False, matching this tool's previous ungated behaviour: session
    transcripts are project-internal, not field data. Passing sensitive=True here
    would BLOCK the call, since 'claude' is not in LOCAL_BACKENDS.
    """
    truncated = session_text[:MAX_CHARS]
    if len(session_text) > MAX_CHARS:
        print(f"Warning: session truncated from {len(session_text)} to {MAX_CHARS} chars",
              file=sys.stderr)

    text = llm_call(SYSTEM_FRAME + EXTRACT_PROMPT + truncated,
                    capability="session_extraction")
    blocks = [b.strip() for b in text.split(SEPARATOR)]
    return [b for b in blocks if b]


def vivify_block(text, source, inferences_dir, retries=3):
    """Call vivify.py as a subprocess, passing text on STDIN. Retries on failure."""
    import time
    vivify_path = Path(__file__).parent / "vivify.py"
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                [sys.executable, str(vivify_path),
                 "--source", source,
                 "--dir", inferences_dir],
                input=text,
                text=True,
                check=True
            )
            return
        except subprocess.CalledProcessError as e:
            if attempt < retries:
                print(f"  vivify failed (attempt {attempt}), retrying in 5s...", file=sys.stderr)
                time.sleep(5)
            else:
                print(f"  vivify failed after {retries} attempts — skipping block", file=sys.stderr)
                print(f"  Block text (first 200 chars): {text[:200]}", file=sys.stderr)


def usage(exit_code=0):
    print("Usage: cat session-clean.md | python3 session_extract_op.py [options]")
    print("       python3 session_extract_op.py --input session-clean.md [options]")
    print()
    print("Options:")
    print("  --input PATH     Input clean markdown session file")
    print("  --dir PATH       Vivify directly, saving to PATH (default: JSONL output)")
    print("  --source LABEL   Source label passed to vivify (default: claude_session_op)")
    print("  -h, --help       Show this help")
    sys.exit(exit_code)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--input", default=None)
    parser.add_argument("--dir", default=None)
    parser.add_argument("--source", default="claude_session_op")
    parser.add_argument("-h", "--help", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.help:
        usage()

    if args.input:
        session_text = Path(args.input).expanduser().read_text().strip()
    elif not sys.stdin.isatty():
        session_text = sys.stdin.read().strip()
    else:
        usage(exit_code=1)

    if not session_text:
        print("Error: empty input", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting operator-aware inferences from {len(session_text)} chars...",
          file=sys.stderr)
    try:
        inferences = extract_inferences(session_text)
    except LLMUnavailable as e:
        print(f"Error: extraction model unavailable — {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Extracted {len(inferences)} inference(s)", file=sys.stderr)

    if args.dir:
        Path(args.dir).mkdir(parents=True, exist_ok=True)
        for i, text in enumerate(inferences, 1):
            print(f"Vivifying {i}/{len(inferences)}...", file=sys.stderr)
            vivify_block(text, args.source, args.dir)
    else:
        for text in inferences:
            print(json.dumps(text))


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-06-11 | repos/vivify-inferences/session_extract_op.py | created — operator-aware session inference extraction; logos schema vocabulary woven into extraction prompt for operator-calibrated coordinates
# llm: claude-sonnet-4-6 | 2026-06-11 | repos/vivify-inferences/session_extract_op.py | added retry logic to vivify_block (3 attempts, 5s sleep)
# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/session_extract_op.py | migrated from vivify-inferences; same transport port as session_extract.py (llm_call, capability session_extraction) — gate + model_map now apply; operator vocabulary prompt unchanged
