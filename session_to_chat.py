#!/usr/bin/env python3
"""
session_to_chat — convert col-b terminal session to styled HTML chat + clean markdown

Reads a script(1) typescript file after col -b cleaning. col strips the ESC byte and
[ from CSI sequences, leaving orphaned parameter strings like 38;2;255;255;255m and
12G. This script classifies lines by those signatures, strips them, and produces:
  .html  — styled web chat with user/Claude turns and artifacts in boxes
  --md   — clean markdown chat (optional; useful as input to session_extract.py)

Usage:
  session_to_chat.py INPUT.md [--out OUTPUT.html] [--md OUTPUT_clean.md]
  cat session.md | session_to_chat.py > session.html
"""

import sys
import re
import gzip
import argparse
from html import escape
from pathlib import Path


def write_file(path, text):
    """Write text to path; gzip if path ends in .gz."""
    p = Path(path)
    if p.suffix == '.gz':
        p.write_bytes(gzip.compress(text.encode()))
    else:
        p.write_text(text)


# ---------------------------------------------------------------------------
# ANSI / terminal code stripping
# ---------------------------------------------------------------------------

def strip_codes(text):
    """Strip residual terminal codes left after col -b processing."""
    # SGR color/attr: digits;...m (col left these after stripping ESC[)
    text = re.sub(r'\d+(?:;\d+)*m', '', text)
    # Cursor horizontal absolute: \d+G — replace with space (word boundaries)
    text = re.sub(r'\d+G', ' ', text)
    # Cursor movement: up/down/forward/backward (require digit prefix so bare letters survive)
    text = re.sub(r'\d+[ABCD]', '', text)
    # Erase line/display, cursor home (with or without digit)
    text = re.sub(r'\d*[KHJ]', '', text)
    # DEC private mode sequences: ?digits[hl$p]
    text = re.sub(r'\?[0-9;]+[hl$p]', '', text)
    # Bare mode codes without ? (col sometimes strips the leading ?)
    text = re.sub(r'\d+[hl]', '', text)
    # Other terminal remnants: >0q  c0;  r? at line start
    text = re.sub(r'^r\?', '', text)
    text = re.sub(r'>0q|c0;', '', text)
    # Claude Code UI box-drawing chrome
    text = re.sub(r'[▐▛▜▌▝▘▙▟▞◼◻]+', '', text)
    # Residual control chars (keep printable + tab + newline)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Braille control picture — appears in task-progress chrome, never real content
    text = text.replace('⠐', '')
    # Trailing padding spaces/tabs from 80-col terminal layout
    text = re.sub(r'[ \t]{3,}$', '', text)
    # Normalise internal whitespace
    text = re.sub(r'[ \t]+', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# Line classification by escape code signatures
# ---------------------------------------------------------------------------

def classify(raw):
    """Return turn type from colour-code patterns in the raw line."""
    # Orange/amber = spinner animation or notification chrome — always discard
    if '38;2;255;153;51m' in raw or '38;2;255;183;101m' in raw:
        return 'spinner'
    if '48;2;55;55;55m' in raw:           # dark bg = user input
        return 'user'
    if '38;2;153;153;153m' in raw:        # gray = Claude Code UI chrome
        if '✻' in raw:  return 'status'
        if '※' in raw:  return 'recap'
        if '⎿' in raw:  return 'tool_output'
        return 'meta'
    if '38;2;51;153;255m' in raw and '●' in raw:   # blue ● = tool call
        return 'tool_call'
    if '38;2;255;255;255m' in raw and '●' in raw:  # white ● = Claude text
        return 'claude'
    if '⎿' in raw:
        return 'tool_output'
    if raw.strip():
        return 'continuation'
    return 'blank'


# ---------------------------------------------------------------------------
# Session parsing → blocks
# ---------------------------------------------------------------------------

def is_chrome(clean):
    """True for UI chrome lines we should discard."""
    if not clean:
        return True
    if clean.startswith('Script started') or clean.startswith('Script done'):
        return True
    # Very short lines — almost always terminal-code residue or single-char prompts
    if len(clean) <= 2:
        return True
    # Horizontal rule anywhere in the line (may have cursor residue as prefix/suffix)
    if re.search(r'[─━]{8,}', clean):
        return True
    # Status bar footer: "esc to interrupt … ● high · /effort"
    if '●' in clean and 'effort' in clean:
        return True
    # "esc to interrupt" status bar
    if 'esc' in clean and 'interrupt' in clean:
        return True
    # Input prompt marker standing alone
    if clean == '❯' or clean.startswith('❯ ─'):
        return True
    # Prompt placeholder "Try "how does…""
    if clean.startswith('Try') and 'work?' in clean:
        return True
    # Claude Code tool summary UI (gray meta lines between turns)
    if re.match(r'^(Searched|Listed|Read|Wrote|Ran|Checked|Found|Executed)', clean) \
            and 'ctrl+o' in clean:
        return True
    # UI tips — may have ⎿ prefix (rendered like tool output in the terminal)
    if re.search(r'Tip:\s+(ctrl|Name|Run|Connect|Use|Add|Enable)\b', clean):
        return True
    # Keyboard shortcut bar (? for shortcuts · ← for agents)
    if re.match(r'^[?]\s+for\s+shortcuts', clean):
        return True
    # Lines that are pure terminal-code residue (digits + bare letters, no real words)
    if re.match(r'^[\d\s]+$', clean):
        return True
    # Session-close / task-progress chrome that uses 0; prefix
    if clean.startswith('0;'):
        return True
    return False


def flush(current, blocks):
    if current and current.get('lines'):
        blocks.append(current)
    return None


def parse_file(source):
    """Parse raw col-b session into conversation blocks."""
    if source:
        text = Path(source).read_text(errors='replace')
    else:
        text = sys.stdin.read()

    blocks = []
    current = None

    for raw in text.splitlines():
        kind = classify(raw)
        clean = strip_codes(raw)

        if kind == 'spinner' or is_chrome(clean):
            continue

        if kind == 'blank':
            # Blank line closes a tool_output run
            if current and current['kind'] == 'tool_output':
                current = flush(current, blocks)
            continue

        if kind == 'user':
            body = re.sub(r'^[❯\s]+', '', clean)
            if current and current['kind'] == 'user':
                if body:
                    current['lines'].append(body)
            else:
                current = flush(current, blocks)
                current = {'kind': 'user', 'lines': [body] if body else []}

        elif kind == 'claude':
            current = flush(current, blocks)
            # Strip task-progress garbage that precedes the ● marker
            idx = clean.find('●')
            body = clean[idx+1:].strip() if idx >= 0 else re.sub(r'^[● ]+', '', clean)
            current = {'kind': 'claude', 'lines': [body] if body else []}

        elif kind == 'tool_call':
            current = flush(current, blocks)
            body = re.sub(r'^[● ]+', '', clean)
            current = {'kind': 'tool_call', 'lines': [body] if body else []}

        elif kind == 'tool_output':
            # Flush any non-tool_output block (including tool_call)
            if current and current['kind'] != 'tool_output':
                current = flush(current, blocks)
                current = None
            if current is None:
                current = {'kind': 'tool_output', 'lines': []}
            body = re.sub(r'^[⎿ ]+', '', clean)
            if body:
                current['lines'].append(body)

        elif kind == 'status':
            current = flush(current, blocks)
            body = re.sub(r'^[✻ ]+', '', clean)
            # Status is single-line; flush immediately
            blocks.append({'kind': 'status', 'lines': [body]})

        elif kind == 'recap':
            current = flush(current, blocks)
            body = re.sub(r'^[※ ]+(recap:\s*)?', '', clean, flags=re.I)
            # Keep as current so continuation lines accumulate
            current = {'kind': 'recap', 'lines': [body] if body else []}

        elif kind == 'meta':
            pass  # Gray UI meta lines are always chrome — discard

        elif kind == 'continuation':
            # Only extend blocks where continuation makes semantic sense.
            # Tool output is always complete on ⎿ lines — continuation here
            # is UI chrome (autocomplete, prompts, session-close noise).
            if current and clean and current['kind'] in ('claude', 'tool_call', 'recap'):
                current['lines'].append(clean)

    flush(current, blocks)
    return blocks


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
  font-size: 15px; line-height: 1.55;
  background: #f0f0f0; color: #222;
  max-width: 860px; margin: 0 auto; padding: 24px 16px;
}
h1 { font-size: 1em; font-weight: 400; color: #888; margin-bottom: 18px; }
.turn { margin: 10px 0; }

/* User bubble */
.user-wrap { display: flex; flex-direction: column; align-items: flex-end; }
.user-label { font-size: 0.7em; color: #888; margin-bottom: 3px; }
.user-bubble {
  background: #1c1c1e; color: #e8e8e8;
  border-radius: 16px 16px 4px 16px;
  padding: 9px 14px; max-width: 78%;
  white-space: pre-wrap; word-break: break-word;
}

/* Claude bubble */
.claude-wrap { display: flex; flex-direction: column; align-items: flex-start; margin-right: 6%; }
.claude-label { font-size: 0.7em; color: #c07020; font-weight: 600; margin-bottom: 3px; }
.claude-bubble {
  background: #ffffff;
  border-left: 3px solid #d97706;
  border-radius: 0 12px 12px 0;
  padding: 10px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  white-space: pre-wrap; word-break: break-word;
}

/* Tool call */
.tool-wrap { margin: 6px 0 2px 0; }
.tool-label { font-size: 0.68em; color: #5b6cf8; font-weight: 600; margin-bottom: 2px; }
.tool-box {
  background: #f4f4ff; border: 1px solid #c7d2fe;
  border-radius: 6px; padding: 6px 12px;
  font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 0.82em;
  white-space: pre-wrap; word-break: break-all;
}

/* Artifact / tool output */
.artifact {
  background: #1e1e2e; color: #cdd6f4;
  font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 0.82em;
  padding: 10px 14px; border-radius: 8px; margin: 4px 0 8px 0;
  overflow-x: auto; white-space: pre;
  border: 1px solid #313244;
}

/* Status / thinking */
.status { color: #aaa; font-style: italic; font-size: 0.78em; padding: 2px 8px; }

/* Recap */
.recap-box {
  background: #fffbeb; border-left: 3px solid #f59e0b;
  border-radius: 0 6px 6px 0; padding: 8px 14px; margin: 8px 0;
}
.recap-label { font-size: 0.68em; color: #92400e; font-weight: 700;
               text-transform: uppercase; margin-bottom: 3px; }
"""


def blocks_to_html(blocks, title):
    parts = [
        f'<!DOCTYPE html>\n<html lang="en">\n<head>',
        f'<meta charset="UTF-8">',
        f'<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{escape(title)}</title>',
        f'<style>{CSS}</style>',
        f'</head>\n<body>',
        f'<h1>{escape(title)}</h1>',
    ]

    for b in blocks:
        kind = b['kind']
        lines = [l for l in b['lines'] if l.strip()]
        if not lines:
            continue
        text = ' '.join(lines)

        if kind == 'user':
            parts.append(
                '<div class="turn">'
                '<div class="user-wrap">'
                '<div class="user-label">You</div>'
                f'<div class="user-bubble">{escape(text)}</div>'
                '</div></div>'
            )

        elif kind == 'claude':
            inner = '\n'.join(escape(l) for l in lines)
            parts.append(
                '<div class="turn">'
                '<div class="claude-wrap">'
                '<div class="claude-label">Claude</div>'
                f'<div class="claude-bubble">{inner}</div>'
                '</div></div>'
            )

        elif kind == 'tool_call':
            parts.append(
                '<div class="tool-wrap">'
                '<div class="tool-label">Tool call</div>'
                f'<div class="tool-box">{escape(text)}</div>'
                '</div>'
            )

        elif kind == 'tool_output':
            code = '\n'.join(lines)
            parts.append(f'<div class="artifact">{escape(code)}</div>')

        elif kind == 'status':
            parts.append(f'<div class="status">⟳ {escape(text)}</div>')

        elif kind == 'recap':
            parts.append(
                '<div class="recap-box">'
                '<div class="recap-label">Recap</div>'
                f'{escape(text)}'
                '</div>'
            )

    parts.append('</body></html>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Markdown rendering (clean, for session_extract.py)
# ---------------------------------------------------------------------------

def blocks_to_md(blocks, title):
    parts = [f'# {title}\n']
    for b in blocks:
        kind = b['kind']
        lines = [l for l in b['lines'] if l.strip()]
        if not lines:
            continue
        text = ' '.join(lines)

        if kind == 'user':
            parts.append(f'**You:** {text}\n')
        elif kind == 'claude':
            parts.append(f'**Claude:** {chr(10).join(lines)}\n')
        elif kind == 'tool_call':
            parts.append(f'`Tool: {text}`\n')
        elif kind == 'tool_output':
            parts.append('```\n' + '\n'.join(lines) + '\n```\n')
        elif kind == 'status':
            parts.append(f'*{text}*\n')
        elif kind == 'recap':
            parts.append(f'> **Recap:** {text}\n')

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input', nargs='?', help='Input .md file (default: stdin)')
    p.add_argument('--out', help='HTML output path (default: stdout)')
    p.add_argument('--md', help='Clean markdown output path (optional)')
    return p.parse_args()


def main():
    args = parse_args()

    if args.input is None and sys.stdin.isatty():
        print('Usage: session_to_chat.py INPUT.md [--out OUTPUT.html] [--md OUTPUT_clean.md]',
              file=sys.stderr)
        sys.exit(1)

    blocks = parse_file(args.input)

    src = args.input or 'stdin'
    title = f'Claude session — {Path(src).stem}' if args.input else 'Claude session'

    html = blocks_to_html(blocks, title)
    if args.out:
        write_file(args.out, html)
        print(f'HTML → {args.out}', file=sys.stderr)
    else:
        sys.stdout.write(html)

    if args.md:
        write_file(args.md, blocks_to_md(blocks, title))
        print(f'Markdown → {args.md}', file=sys.stderr)


if __name__ == '__main__':
    main()

# llm: claude-sonnet-4-6 | 2026-06-11 | repos/vivify-inferences/session_to_chat.py | created — col-b terminal session → HTML chat + clean markdown
# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/session_to_chat.py | migrated verbatim from vivify-inferences (stdlib only, no porting needed) — see that repo's inferences-lineage branch
