#!/usr/bin/env python3
"""
inf_to_md — convert a directory of vivify inference JSON files to a single markdown doc

Reads all inf_*.json files from a directory (sorted by timestamp), renders each
inference as a markdown section: prose paragraph, keyword clumps, loose keywords.
Useful for comparing vivify-distilled session material against full conversation
transcripts from jsonl_to_md.py.

Usage:
  inf_to_md.py INFERENCES_DIR [--out OUTPUT.md]
  inf_to_md.py inferences/claude_code_sessions/unclustered --out ~/logs/claude/session-inferences.md
"""

import sys
import json
import argparse
from pathlib import Path


def render_inference(inf):
    """Render one inference as a markdown section."""
    inf_id = inf.get('id', '?')
    ts = inf.get('timestamp', '')[:19].replace('T', ' ')
    source = inf.get('source', '')
    raw_text = inf.get('raw_text', '').strip()
    clumps = inf.get('clumps', {})
    left_kw = inf.get('left_keywords', [])
    tension = inf.get('tension_score')

    lines = [f'## {inf_id}']
    if ts:
        meta = f'*{ts}*'
        if source:
            meta += f'  ·  source: {source}'
        if tension is not None:
            meta += f'  ·  tension: {tension:.2f}'
        lines.append(meta)
    lines.append('')
    lines.append(raw_text)

    if clumps:
        lines.append('')
        lines.append('**Clumps:**')
        for name, keywords in clumps.items():
            lines.append(f'- `{name}`: {", ".join(keywords)}')

    # Show any left_keywords not already in a clump
    clumped = {kw for kws in clumps.values() for kw in kws}
    loose = [kw for kw in left_kw if kw not in clumped]
    if loose:
        lines.append('')
        lines.append(f'**Loose keywords:** {", ".join(loose)}')

    return '\n'.join(lines)


def load_inferences(directory):
    """Load and sort all inf_*.json files by timestamp."""
    infs = []
    for path in sorted(Path(directory).glob('inf_*.json')):
        try:
            data = json.loads(path.read_text())
            data['_path'] = str(path)
            infs.append(data)
        except (json.JSONDecodeError, OSError) as e:
            print(f'Warning: skipping {path}: {e}', file=sys.stderr)
    infs.sort(key=lambda d: d.get('timestamp', ''))
    return infs


def build_md(inferences, title):
    parts = [f'# {title}\n', f'*{len(inferences)} inferences*\n']
    for inf in inferences:
        parts.append(render_inference(inf))
        parts.append('')
    return '\n'.join(parts)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('directory', help='Directory containing inf_*.json files')
    p.add_argument('--out', help='Output .md path (default: stdout)')
    return p.parse_args()


def main():
    args = parse_args()
    inferences = load_inferences(args.directory)
    if not inferences:
        print(f'No inf_*.json files found in {args.directory}', file=sys.stderr)
        sys.exit(1)

    title = f'Session inferences — {Path(args.directory).parent.name}/{Path(args.directory).name}'
    md = build_md(inferences, title)

    if args.out:
        Path(args.out).expanduser().write_text(md)
        print(f'→ {args.out}  ({len(inferences)} inferences)', file=sys.stderr)
    else:
        sys.stdout.write(md)


if __name__ == '__main__':
    main()

# llm: claude-sonnet-4-6 | 2026-06-11 | repos/vivify-inferences/inf_to_md.py | created — vivify inference JSON dir → single markdown doc for comparison
# llm: claude-opus-5 | 2026-08-31 | repos/vivify-operators/inf_to_md.py | migrated verbatim from vivify-inferences (stdlib only, no porting needed) — see that repo's inferences-lineage branch
