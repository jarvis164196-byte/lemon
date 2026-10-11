"""Real GIMP acceptance. Synthetic fixtures establish mechanics, not aesthetic quality."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from lemon.gimp import GimpAdapter
from lemon.store import Controller, digest, uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source, reference = root / "source.png", root / "reference.png"
    # Purpose-built gradients are fixtures, not edited photo output.
    size = (1600, 1200)
    y, x = np.mgrid[0 : size[1], 0 : size[0]]
    for path, warm in [(source, False), (reference, True)]:
        rgb = np.stack(
            [
                x / size[0] * 175 + 45 + (25 if warm else 0),
                y / size[1] * 130 + 45,
                (x / size[0] + y / size[1]) * 80 + 20 - (15 if warm else 0),
            ],
            axis=-1,
        )
        Image.fromarray(np.clip(rgb, 0, 255).astype("uint8")).save(path)
    before = {str(p.name): digest(p) for p in [source, reference]}
    adapter = GimpAdapter(root / "runtime")
    controller = Controller(root / "projects", adapter)
    state = controller.create("Real GIMP acceptance", source, reference)
    pid = state["id"]
    original = state["working_node_id"]
    print("Verified root", flush=True)
    plan = controller.plan(pid, 0.65)
    nodes = []
    evidence = []
    for i in range(3):
        request = uid()
        op = controller.run_step(pid, plan["id"], plan["hash"], i, request)
        assert op["status"] == "committed", op
        nodes.append(op["node_id"])
        assert controller.run_step(pid, plan["id"], plan["hash"], i, request) == op
        print("Committed step", i + 1, flush=True)
    state = controller.history(pid)
    original_preview = controller.asset(pid, "preview", original)
    final_preview = controller.asset(pid, "preview", nodes[-1])
    assert digest(original_preview) != digest(final_preview), "Native adjustment did not change output pixels"
    # Every job has exited GIMP. Construct a fresh controller and adapter to simulate restart.
    controller = Controller(root / "projects", GimpAdapter(root / "runtime-restarted"))
    controller.restore(pid, nodes[0])
    print("Restored S001 after restart", flush=True)
    branch_plan = controller.plan(pid, 0.3)
    fork = controller.run_step(pid, branch_plan["id"], branch_plan["hash"], 0, uid())
    assert fork["status"] == "committed", fork
    state = controller.restore(pid, nodes[-1])
    print("Created S004 branch and restored S003", flush=True)
    assert {b["tip_node_id"] for b in state["branches"].values()} == {nodes[-1], fork["node_id"]}
    assert state["nodes"][fork["node_id"]]["parent_id"] == nodes[0]
    exported = controller.export(pid, original)
    with Image.open(controller.asset(pid, "export", exported["export_id"])) as im:
        assert im.size == size
    with Image.open(original_preview) as preview:
        assert max(preview.size) == 1400
        assert preview.size != size
    assert before == {str(p.name): digest(p) for p in [source, reference]}
    for node in state["nodes"].values():
        evidence.append(
            {
                "version": node["display_id"],
                "checkpoint_sha256": node["checkpoint_hash"],
                "preview_sha256": node["preview_hash"],
                "operation": node["step"]["tool"],
                "verification": node["evidence"],
            }
        )
    report = {
        "scope": "Real GIMP integration with synthetic fixtures; no human photo-quality claims",
        "passed": True,
        "checks": [
            "root save/reopen",
            "three native edits",
            "distinct output pixels",
            "application deduplication",
            "controller and editor restart",
            "restore S001",
            "branch S004",
            "restore S003",
            "both branch tips preserved",
            "explicit S000 full-resolution export",
            "unchanged source and reference hashes",
        ],
        "inputs": before,
        "nodes": evidence,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(report, indent=2))
    print("PASS: all real GIMP checks", flush=True)


if __name__ == "__main__":
    main()
