"""
session_extract — extract discrete inferences from a cleaned script session transcript

Reads a Claude Code terminal session (after gzip + col -b cleaning) and runs an
LLM pass to identify distinct conceptual developments, decisions, and ideas.

Two output modes:
  JSONL (default)  — one JSON string per line, pipe into a shell loop → vivify.py
  --dir PATH       — calls vivify.py directly for each extracted block

Typical usage:
  zcat ~/logs/claude/claude-session.TIMESTAMP.gz \\
    | col -b \\
    | python3 session_extract.py --dir inferences/claude_code_sessions

Or composable:
  zcat session.gz | col -b | session_extract.py | while IFS= read -r line; do
    echo "$line" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()))" \\
      | vivify.py --source claude_session --dir inferences/claude_code_sessions
  done
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

EXTRACT_PROMPT = f"""You are reading a cleaned terminal session transcript from a Claude Code development session.

Extract 3-8 discrete inference units from this session.

Each inference unit must:
- Describe one distinct conceptual development, decision, or idea
- Be self-contained — readable without the surrounding session context
- Be written as a coherent paragraph (not bullet points or fragments)
- Capture WHAT was decided or developed and WHY, not HOW the code was written
- Be suitable for semantic keyword extraction by a vivify pipeline

Ignore: file contents, JSON blobs, tool outputs, error messages, shell commands, terminal UI chrome.
Focus on: architectural decisions, conceptual pivots, new ideas, problems solved, terminology established.

Output each inference as a plain paragraph. Separate each one with a line containing only:
{SEPARATOR}

No JSON, no bullet points, no numbering. Just paragraphs separated by the marker.

Session transcript:
"""


SYSTEM_FRAME = """You extract inference paragraphs from session transcripts. Output plain
text paragraphs separated by the marker the user specifies. No JSON, no markdown.

"""


def extract_inferences(session_text):
    """Extract discrete inference paragraphs from a session transcript.

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


def vivify_block(text, source, inferences_dir):
    """Call vivify.py as a subprocess, passing text on STDIN."""
    vivify_path = Path(__file__).parent / "vivify.py"
    subprocess.run(
        [sys.executable, str(vivify_path),
         "--source", source,
         "--dir", inferences_dir],
        input=text,
        text=True,
        check=True
    )


def usage(exit_code=0):
    print("Usage: zcat session.gz | col -b | session_extract.py [options]")
    print()
    print("Options:")
    print("  --dir PATH       Call vivify.py directly, saving to PATH (default: JSONL output)")
    print("  --source LABEL   Source label passed to vivify (default: claude_session)")
    print("  -h, --help       Show this help")
    sys.exit(exit_code)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dir", default=None)
    parser.add_argument("--source", default="claude_session")
    parser.add_argument("-h", "--help", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.help:
        usage()

    if sys.stdin.isatty():
        usage(exit_code=1)

    session_text = sys.stdin.read().strip()
    if not session_text:
        print("Error: empty input", file=sys.stderr)
        sys.exit(1)

    try:
        inferences = extract_inferences(session_text)
    except LLMUnavailable as e:
        print(f"Error: extraction model unavailable — {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Extracted {len(inferences)} inference(s)", file=sys.stderr)

    if args.dir:
        for i, text in enumerate(inferences, 1):
            print(f"Vivifying {i}/{len(inferences)}...", file=sys.stderr)
            vivify_block(text, args.source, args.dir)
    else:
        for text in inferences:
            print(json.dumps(text))


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-06-07 | repos/vivify-inferences/session_extract.py | created — session transcript → discrete inferences via LLM extraction pass
# llm: claude-sonnet-4-6 | 2026-06-07 | repos/vivify-inferences/session_extract.py | switched from anthropic.Anthropic() to claude -p subprocess — no API key needed
# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/session_extract.py | migrated from vivify-inferences; extraction ported off its own `claude -p` subprocess onto vivify_core.llm_call (capability session_extraction) — the direct call bypassed the privacy gate AND model_map; system prompt folded into the prompt head, LLMUnavailable handled in main()
