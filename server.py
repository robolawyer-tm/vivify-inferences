"""
server — FABRIC component: receive frozen payload, strip layers, store inference

Receives a frozen inference payload over HTTP, thaws it, strips packaging,
and stores to the filesystem-as-database. Gleaned from secret-server/web_server.py.
Runs locally only — no external access.
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from vivify_core import write_json, read_json, deep_update
from freeze import thaw

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

INFERENCES_DIR = Path("inferences")
INDEX_FILE = INFERENCES_DIR / "index.json"


# ── Storage functions (usable standalone without Flask) ──────────────────────

def store_inference(inference):
    """Strip packaging and store an inference to the filesystem.

    - Unclustered inferences land in inferences/unclustered/
    - Category-assigned inferences go to inferences/{category}/{sub}/
    - Returns the path written
    """
    inf_id = inference.get("id", "inf_unknown")
    category_paths = inference.get("category_paths", [])

    if category_paths:
        # Store under first category path
        dest = INFERENCES_DIR / Path(category_paths[0]) / f"{inf_id}.json"
    else:
        dest = INFERENCES_DIR / "unclustered" / f"{inf_id}.json"

    write_json(dest, inference)
    _update_index(inference)
    return str(dest)


def retrieve_inference(inf_id):
    """Find and return an inference by ID, searching the full inferences/ tree.

    - Returns dict or None if not found
    """
    for path in INFERENCES_DIR.rglob(f"{inf_id}.json"):
        return read_json(path)
    return None


def _update_index(inference):
    """Update the master index with keywords from a new inference.

    - Increments co-occurrence counts for all keyword pairs
    - Creates index.json if it does not exist
    """
    index = read_json(INDEX_FILE)
    if not index:
        index = {"version": "1.0", "total_inferences": 0, "keywords": {}, "cooccurrence": {}}

    index["total_inferences"] = index.get("total_inferences", 0) + 1

    keywords = inference.get("left_keywords", [])
    for kw in keywords:
        index["keywords"][kw] = index["keywords"].get(kw, 0) + 1

    for i, kw1 in enumerate(keywords):
        for kw2 in keywords[i + 1:]:
            pair = f"{kw1}::{kw2}"
            index["cooccurrence"][pair] = index["cooccurrence"].get(pair, 0) + 1

    write_json(INDEX_FILE, index)


# ── Flask server ─────────────────────────────────────────────────────────────

def create_app():
    """Create and configure the Flask server app."""
    app = Flask(__name__)

    @app.before_request
    def localhost_only():
        """Restrict to localhost — no external access."""
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify({"error": "Access denied"}), 403

    @app.route("/store", methods=["POST"])
    def store():
        """Receive a frozen inference payload, thaw it, and store it.

        - Accepts: {"payload": "<frozen_string>"}
        - Returns: {"success": true, "id": "inf_XXX", "path": "..."}
        """
        data = request.json
        frozen = data.get("payload")
        if not frozen:
            return jsonify({"error": "No payload"}), 400
        try:
            inference = thaw(frozen)
            path = store_inference(inference)
            return jsonify({"success": True, "id": inference["id"], "path": path})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/retrieve/<inf_id>", methods=["GET"])
    def retrieve(inf_id):
        """Retrieve an inference by ID."""
        inference = retrieve_inference(inf_id)
        if not inference:
            return jsonify({"error": "Not found"}), 404
        return jsonify(inference)

    @app.route("/index", methods=["GET"])
    def index():
        """Return the master keyword co-occurrence index."""
        return jsonify(read_json(INDEX_FILE))

    return app


def usage():
    print("Usage: server.py [--port 5002]   start the Flask server")
    print("       server.py store < inference.json   store directly (no HTTP)")
    sys.exit(1)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "store":
        # Direct store mode — no Flask needed
        if not sys.stdin.isatty():
            inference = json.loads(sys.stdin.read().strip())
            path = store_inference(inference)
            print(f"Stored: {path}")
        else:
            usage()
        return

    if not FLASK_AVAILABLE:
        print("Error: Flask not installed — pip install flask")
        sys.exit(1)

    port = 5002
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    app = create_app()
    print(f"server.py listening on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/server.py | created — FABRIC server component, gleaned from secret-server/web_server.py
