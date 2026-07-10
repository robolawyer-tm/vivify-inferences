"""test_promote — verify promote_all files categorized inferences and keeps unmatched ones.

- A categorized inference (non-empty category_paths) moves into <dir>/<category_paths[0]>/
- An uncategorized inference (empty category_paths) stays in unclustered/
- promote_all is idempotent: a second run over the same dir moves nothing
Run: python3 tests/test_promote.py
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promote import promote_all


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_promote():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "inferences"
        unclustered = base / "unclustered"

        _write(unclustered / "inf_aaa.json",
               {"id": "inf_aaa", "category_paths": ["seedA/subB"]})
        _write(unclustered / "inf_bbb.json",
               {"id": "inf_bbb", "category_paths": []})

        summary = promote_all(inferences_dir=base)

        filed = base / "seedA" / "subB" / "inf_aaa.json"
        assert filed.exists(), "categorized inference should be filed into its category dir"
        assert not (unclustered / "inf_aaa.json").exists(), \
            "categorized inference should leave unclustered/"
        assert (unclustered / "inf_bbb.json").exists(), \
            "uncategorized inference should stay in unclustered/"
        assert [p["id"] for p in summary["promoted"]] == ["inf_aaa"], summary
        assert summary["kept"] == ["inf_bbb"], summary

        # Idempotent: nothing left in unclustered/ to promote
        summary2 = promote_all(inferences_dir=base)
        assert summary2["promoted"] == [], summary2
        assert summary2["kept"] == ["inf_bbb"], summary2

    print("test_promote: PASS")


if __name__ == "__main__":
    test_promote()
