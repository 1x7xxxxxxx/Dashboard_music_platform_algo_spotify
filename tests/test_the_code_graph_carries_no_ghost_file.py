"""R269 — the code graph never keeps the nodes of a file that is gone.

Type: Test
Uses: tools/dev/graphify_prune.py (prune), Makefile (graph-update)

`graphify update` adds and never removes: 24 ghost files / 177 nodes on 2026-09-11, the
residue growing at each regeneration. `make graph-update` now prunes after updating.

Mutation record (2026-09-27) : `prune` keeping the links of a dead node → red ; the prune
step removed from `graph-update` → red.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("graphify_prune", ROOT / "tools/dev/graphify_prune.py")
gp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gp)


def test_a_ghost_file_loses_its_nodes_and_links():
    graph = {"nodes": [{"id": "a", "source_file": "live.py"}, {"id": "b", "source_file": "gone.py"},
                       {"id": "c"}],
             "links": [{"source": "a", "target": "b"}, {"source": "a", "target": "c"}]}
    pruned, ghosts = gp.prune(graph, lambda p: p == "live.py")
    assert ghosts == ["gone.py"]
    assert [n["id"] for n in pruned["nodes"]] == ["a", "c"]
    assert pruned["links"] == [{"source": "a", "target": "c"}]
    same, none = gp.prune(pruned, lambda p: True)
    assert none == [] and same is pruned


def test_graph_update_prunes_after_updating():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = text[text.index("\ngraph-update:"):].split("\n\n")[0]
    assert "graphify update" in recipe and "graphify_prune.py" in recipe
    assert recipe.index("graphify update") < recipe.index("graphify_prune.py")
