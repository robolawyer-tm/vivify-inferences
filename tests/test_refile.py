"""test_refile — verify refile_all moves filed inferences to their canonical address.

- A filed inference whose paths[0] changed moves, and its reify_* sibling moves with it
- The emptied source directory chain is retired (never the base)
- A filed inference with empty category_paths demotes to unclustered/
- A file already at its canonical address is kept; unclustered/ files are untouched
- refile_all is idempotent: a second run moves nothing
Run: python3 tests/test_refile.py
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refile import refile_all


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) if isinstance(obj, dict) else obj)


def test_refile():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "inferences"

        # stale address: paths[0] now says seedA/subNEW
        _write(base / "seedA" / "subOLD" / "inf_aaa.json",
               {"id": "inf_aaa", "category_paths": ["seedA/subNEW", "seedB/subX"]})
        _write(base / "seedA" / "subOLD" / "reify_aaa.md", "# portrait")

        # paths emptied by a clean re-categorize
        _write(base / "seedB" / "subY" / "inf_bbb.json",
               {"id": "inf_bbb", "category_paths": []})

        # already canonical
        _write(base / "seedC" / "subZ" / "inf_ccc.json",
               {"id": "inf_ccc", "category_paths": ["seedC/subZ"]})

        # unclustered is promote's territory — untouched even with paths
        _write(base / "unclustered" / "inf_ddd.json",
               {"id": "inf_ddd", "category_paths": ["seedC/subZ"]})

        summary = refile_all(inferences_dir=base)

        # refiled with sibling
        assert (base / "seedA" / "subNEW" / "inf_aaa.json").exists()
        assert (base / "seedA" / "subNEW" / "reify_aaa.md").exists(), \
            "sibling must move with the inference"
        assert not (base / "seedA" / "subOLD").exists(), "emptied dir chain retired"
        assert (base / "seedA").exists(), "non-empty ancestor kept"

        # demoted
        assert (base / "unclustered" / "inf_bbb.json").exists()
        assert not (base / "seedB").exists(), "fully emptied seed dir retired"

        # kept + untouched
        assert (base / "seedC" / "subZ" / "inf_ccc.json").exists()
        assert (base / "unclustered" / "inf_ddd.json").exists(), \
            "unclustered files are never refiled"

        assert [e["id"] for e in summary["refiled"]] == ["inf_aaa"], summary
        assert summary["refiled"][0]["siblings"] == 1, summary
        assert [e["id"] for e in summary["demoted"]] == ["inf_bbb"], summary
        assert summary["kept"] == ["inf_ccc"], summary

        # idempotent
        summary2 = refile_all(inferences_dir=base)
        assert summary2["refiled"] == [] and summary2["demoted"] == [], summary2
        assert sorted(summary2["kept"]) == ["inf_aaa", "inf_ccc"], summary2

    print("test_refile: PASS")


if __name__ == "__main__":
    test_refile()
