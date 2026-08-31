#!/usr/bin/env python3
"""
jsonl_to_md — convert Claude Code JSONL session to LLM-friendly markdown

Extracts the main conversation thread from a Claude Code .jsonl session file.
Renders user messages, assistant text, and tool calls as clean markdown.
Skips thinking blocks, metadata records, and sidechain branches.

Usage:
  jsonl_to_md.py SESSION.jsonl [--out OUTPUT.md]
  cat session.jsonl | jsonl_to_md.py > session.md
"""

import sys
import json
import argparse
from pathlib import Path


SKIP_TYPES = {'mode', 'permission-mode', 'file-history-snapshot',
              'ai-title', 'system', 'last-prompt', 'attachment'}

MAX_TOOL_OUTPUT = 800   # chars before truncating tool result content


def render_tool_use(block):
    """One-line tool call summary."""
    name = block.get('name', '?')
    inp = block.get('input', {})
    # Show the most informative input field
    if 'command' in inp:
        detail = inp['command']
    elif 'file_path' in inp:
        detail = inp['file_path']
    elif 'query' in inp:
        detail = inp['query']
    elif inp:
        detail = ', '.join(f'{k}={v}' for k, v in list(inp.items())[:2])
    else:
        detail = ''
    if detail and len(detail) > 120:
        detail = detail[:117] + '...'
    return f'`{name}({detail})`' if detail else f'`{name}`'


def render_tool_result(block):
    """Tool result in a fenced code block."""
    content = block.get('content', '')
    if isinstance(content, list):
        # Structured content blocks
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'text':
                parts.append(c.get('text', ''))
        content = '\n'.join(parts)
    content = str(content).strip()
    if not content or content == '(Bash completed with no output)':
        return ''
    if len(content) > MAX_TOOL_OUTPUT:
        content = content[:MAX_TOOL_OUTPUT] + f'\n... [{len(content) - MAX_TOOL_OUTPUT} chars truncated]'
    return f'```\n{content}\n```'


def render_user(message):
    """Render a user message (text or tool_result array)."""
    content = message.get('content', '')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            t = block.get('type')
            if t == 'text':
                text = block.get('text', '').strip()
                if text:
                    parts.append(text)
            elif t == 'tool_result':
                rendered = render_tool_result(block)
                if rendered:
                    parts.append(rendered)
        return '\n\n'.join(parts)
    return ''


def render_assistant(message):
    """Render an assistant message: text paragraphs + tool calls (no thinking)."""
    content = message.get('content', [])
    if not isinstance(content, list):
        return str(content).strip()

    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        t = block.get('type')
        if t == 'text':
            text = block.get('text', '').strip()
            if text:
                parts.append(text)
        elif t == 'tool_use':
            parts.append(render_tool_use(block))
        # 'thinking' blocks intentionally skipped
    return '\n\n'.join(parts)


def load_records(source):
    """Load JSONL records, skipping malformed lines."""
    if source:
        lines = Path(source).read_text().splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    records = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def build_md(records, title):
    """Convert records to markdown string."""
    parts = [f'# {title}\n']
    turn_num = 0

    for rec in records:
        rec_type = rec.get('type')

        if rec_type in SKIP_TYPES:
            continue
        if rec.get('isSidechain'):
            continue

        if rec_type == 'user':
            msg = rec.get('message', {})
            # Skip pure tool_result-only messages (already shown via assistant tool_use)
            content = msg.get('content', '')
            if isinstance(content, list):
                if all(isinstance(b, dict) and b.get('type') == 'tool_result'
                       for b in content if isinstance(b, dict)):
                    # Pure tool results — show compactly under previous tool call
                    rendered = render_user(msg)
                    if rendered:
                        parts.append(rendered + '\n')
                    continue
            rendered = render_user(msg)
            if not rendered:
                continue
            turn_num += 1
            parts.append(f'---\n\n**You:** {rendered}\n')

        elif rec_type == 'assistant':
            msg = rec.get('message', {})
            rendered = render_assistant(msg)
            if not rendered:
                continue
            parts.append(f'\n**Claude:** {rendered}\n')

    return '\n'.join(parts)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input', nargs='?', help='Input .jsonl file (default: stdin)')
    p.add_argument('--out', help='Output .md path (default: stdout)')
    return p.parse_args()


def main():
    args = parse_args()

    if args.input is None and sys.stdin.isatty():
        print('Usage: jsonl_to_md.py SESSION.jsonl [--out OUTPUT.md]', file=sys.stderr)
        sys.exit(1)

    records = load_records(args.input)

    src = args.input or 'stdin'
    stem = Path(src).stem if args.input else 'session'
    title = f'Claude session — {stem}'

    md = build_md(records, title)

    if args.out:
        Path(args.out).write_text(md)
        print(f'→ {args.out}', file=sys.stderr)
    else:
        sys.stdout.write(md)


if __name__ == '__main__':
    main()

# llm: claude-sonnet-4-6 | 2026-06-11 | repos/vivify-inferences/jsonl_to_md.py | created — Claude Code JSONL session → LLM-friendly markdown
# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/jsonl_to_md.py | migrated verbatim from vivify-inferences (stdlib only, no porting needed) — see that repo's inferences-lineage branch
