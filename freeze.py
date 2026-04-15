"""
freeze — FABRIC component: serialize inference payload for IP transit

Converts an inference dict to bytes for transport, and restores it on receipt.
This layer was implicit in secret-server (bare JSON); made explicit here.
"""

import sys
import json
import base64
import fileinput


def freeze(inference):
    """Serialize an inference dict to a base64-encoded JSON string for transit.

    - Produces a single-line string safe for HTTP body or socket transport
    - Reversible with thaw()
    - Returns bytes
    """
    raw = json.dumps(inference, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def thaw(frozen):
    """Deserialize a frozen (base64-encoded JSON) string back to a dict.

    - Reverses freeze()
    - Raises ValueError on malformed input
    """
    try:
        raw = base64.urlsafe_b64decode(frozen.encode("utf-8"))
        return json.loads(raw)
    except Exception as e:
        raise ValueError(f"thaw failed: {e}")


def usage():
    print("Usage: freeze.py freeze < inference.json")
    print("       freeze.py thaw   < frozen_string.txt")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    mode = sys.argv[1]

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
    else:
        usage()

    if mode == "freeze":
        inference = json.loads(raw)
        print(freeze(inference))
    elif mode == "thaw":
        result = thaw(raw)
        print(json.dumps(result, indent=2))
    else:
        usage()


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/freeze.py | created — FABRIC freeze component, base64 JSON serialization for transit
