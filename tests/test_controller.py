import pytest

from lemon.store import Controller, uid


def commit(controller, project_id, plan, index):
    result = controller.run_step(project_id, plan["id"], plan["hash"], index, uid())
    assert result["status"] == "committed"
    return result["node_id"]


def test_restart_restore_branch_and_keep_old_tip(controller, project):
    pid = project["id"]
    root = project["working_node_id"]
    plan = controller.plan(pid, 0.55)
    nodes = [commit(controller, pid, plan, i) for i in range(3)]
    controller = Controller(controller.root, controller.adapter)
    state = controller.restore(pid, nodes[0])
    assert state["active_branch_id"] is None
    branch_plan = controller.plan(pid, 0.3)
    fork = commit(controller, pid, branch_plan, 0)
    state = controller.restore(pid, nodes[-1])
    assert state["nodes"][fork]["parent_id"] == nodes[0]
    assert {b["tip_node_id"] for b in state["branches"].values()} == {nodes[-1], fork}
    assert root in state["nodes"]
    assert len(state["nodes"]) == 5


def test_duplicate_request_does_not_repeat_edit(controller, project):
    pid = project["id"]
    plan = controller.plan(pid, 0.5)
    request = uid()
    first = controller.run_step(pid, plan["id"], plan["hash"], 0, request)
    count = len(controller.adapter.calls)
    assert controller.run_step(pid, plan["id"], plan["hash"], 0, request) == first
    assert len(controller.adapter.calls) == count
    with pytest.raises(ValueError, match="different operation"):
        controller.run_step(pid, plan["id"], plan["hash"], 1, request)


def test_failed_save_keeps_refs_and_requires_restore(controller, project):
    pid = project["id"]
    plan = controller.plan(pid, 0.5)
    controller.adapter.fail = True
    result = controller.run_step(pid, plan["id"], plan["hash"], 0, uid())
    assert result["status"] == "failed"
    after = controller.history(pid)
    assert after["working_node_id"] == project["working_node_id"]
    assert after["branches"] == project["branches"]
    assert len(after["nodes"]) == 1
    assert after["session_status"] == "recovery_required"
    with pytest.raises(ValueError, match="stale"):
        controller.run_step(pid, plan["id"], plan["hash"], 0, uid())
    controller.adapter.fail = False
    controller.restore(pid, project["working_node_id"])
    with pytest.raises(ValueError, match="stale"):
        controller.run_step(pid, plan["id"], plan["hash"], 0, uid())


def test_history_read_never_calls_editor(controller, project):
    before = len(controller.adapter.calls)
    controller.history(project["id"])
    assert len(controller.adapter.calls) == before


def test_corrupt_checkpoint_is_unavailable(controller, project):
    pid = project["id"]
    node = project["working_node_id"]
    (controller.project(pid) / "nodes" / node / "checkpoint.xcf").write_text("corrupt")
    assert not controller.history(pid)["nodes"][node]["healthy"]
    with pytest.raises(ValueError, match="corrupt"):
        controller.restore(pid, node)
    with pytest.raises(ValueError, match="corrupt"):
        controller.export(pid, node)


def test_plan_hash_and_revision_are_enforced(controller, project):
    pid = project["id"]
    plan = controller.plan(pid, 0.5)
    with pytest.raises(ValueError, match="match"):
        controller.run_step(pid, plan["id"], "wrong", 0, uid())
    controller.restore(pid, project["working_node_id"])
    with pytest.raises(ValueError, match="stale"):
        controller.run_step(pid, plan["id"], plan["hash"], 0, uid())


def test_restart_reconciles_prepared_without_commit(controller, project):
    path = controller.project(project["id"])
    state = controller.read(path)
    state["operations"][uid()] = {"status": "prepared", "kind": "edit"}
    controller.write(path, state)
    recovered = Controller(controller.root, controller.adapter).history(project["id"])
    assert recovered["session_status"] == "recovery_required"
    assert len(recovered["nodes"]) == 1
    assert any(op["status"] == "interrupted" for op in recovered["operations"].values())


def test_export_targets_selected_node(controller, project):
    pid = project["id"]
    root = project["working_node_id"]
    plan = controller.plan(pid, 0.5)
    commit(controller, pid, plan, 0)
    result = controller.export(pid, root)
    assert result["node_id"] == root
    assert controller.adapter.calls[-1]["input"].endswith(root + "/checkpoint.xcf")
    assert controller.history(pid)["working_node_id"] != root


def test_scoped_paths(controller, project, tmp_path):
    for bad in ["../outside", "/etc/passwd", "a" * 32 + "/.."]:
        with pytest.raises(ValueError):
            controller.project(bad)
    folder = controller.project(project["id"])
    original = folder / "inputs" / project["inputs"]["reference"]["file"]
    original.unlink()
    original.symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError):
        controller.asset(project["id"], "reference")


def test_modified_stored_plan_cannot_reuse_approval(controller, project):
    pid = project["id"]
    plan = controller.plan(pid, 0.5)
    path = controller.project(pid)
    state = controller.read(path)
    state["plans"][plan["id"]]["steps"][0]["arguments"]["values"] = [0.5] * 256
    controller.write(path, state)
    with pytest.raises(ValueError, match="match"):
        controller.run_step(pid, plan["id"], plan["hash"], 0, uid())


def test_concurrent_approvals_only_commit_once(controller, project):
    from concurrent.futures import ThreadPoolExecutor

    pid = project["id"]
    plan = controller.plan(pid, 0.5)

    def run():
        try:
            return controller.run_step(pid, plan["id"], plan["hash"], 0, uid())["status"]
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sorted(results) == ["committed", "rejected"]
    assert len(controller.history(pid)["nodes"]) == 2
