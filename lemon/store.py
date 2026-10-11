"""Serialized controller and transactional history; pixels remain GIMP-owned."""

import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from .imaging import validate_image
from .planner import propose, validate_step


def uid():
    return uuid.uuid4().hex


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid resource ID.")
    return value


class Controller:
    def __init__(self, root, adapter, vision=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.adapter = adapter
        self.vision = vision
        self.reconcile()

    def project(self, project_id):
        path = self.root / identifier(project_id)
        if path.resolve().parent != self.root or not (path / "project.sqlite").is_file():
            raise ValueError("Project not found.")
        return path

    @contextlib.contextmanager
    def lock(self, path):
        with (path / ".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self, path):
        with sqlite3.connect(path / "project.sqlite") as db:
            row = db.execute("SELECT body FROM state WHERE id=1").fetchone()
            if not row:
                raise ValueError("Project is incomplete.")
            state = json.loads(row[0])
            if state.get("schema") != 1:
                raise ValueError("Unsupported project schema. This version of Lemon cannot modify it.")
            return state

    def write(self, path, state):
        with sqlite3.connect(path / "project.sqlite") as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)"
            )
            db.execute(
                "INSERT INTO state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (canonical(state),),
            )

    def reconcile(self):
        for path in self.root.iterdir():
            if (
                not path.is_dir()
                or not re.fullmatch(r"[a-f0-9]{32}", path.name)
                or not (path / "project.sqlite").exists()
            ):
                continue
            with self.lock(path):
                state = self.read(path)
                pending = [op for op in state["operations"].values() if op["status"] == "prepared"]
                for op in pending:
                    op["status"] = "interrupted"
                    op["error"] = "Controller stopped before a verified commit. No automatic retry."
                if pending:
                    state["session_status"] = "recovery_required"
                    self.write(path, state)
                # Orphan staging/published directories are deliberately retained, never invented as nodes.

    def list_projects(self):
        projects = []
        for path in self.root.iterdir():
            if (
                path.is_dir()
                and re.fullmatch(r"[a-f0-9]{32}", path.name)
                and (path / "project.sqlite").exists()
            ):
                state = self.read(path)
                projects.append(
                    {
                        "id": state["id"],
                        "name": state["name"],
                        "created": state["created"],
                        "versions": len(state["nodes"]),
                    }
                )
        return sorted(projects, key=lambda p: p["created"], reverse=True)

    def check_space(self, path, size):
        if shutil.disk_usage(path).free < max(100 * 1024**2, size[0] * size[1] * 40):
            raise ValueError(
                "Not enough disk space for a verified checkpoint. Existing versions have been preserved."
            )

    def verify_files(self, path, node):
        folder = path / "nodes" / node["id"]
        for name, key in [("checkpoint.xcf", "checkpoint_hash"), ("preview.png", "preview_hash")]:
            file = folder / name
            if not file.is_file() or file.is_symlink() or digest(file) != node[key]:
                raise ValueError(
                    "This version is unavailable: a checkpoint or preview is missing or corrupt."
                )
        return folder / "checkpoint.xcf"

    def verify_inputs(self, path, state):
        for item in state["inputs"].values():
            if digest(path / "inputs" / item["file"]) != item["sha256"]:
                raise ValueError("A preserved input has changed. Editing is blocked.")

    def job(self, state, action, input_path, **kwargs):
        return {
            "action": action,
            "input": str(input_path),
            "identity": state["identity"],
            "size": state["size"],
            "orientation": state["inputs"]["source"].get("orientation", 1) if action == "root" else 1,
            **{k: str(v) if isinstance(v, Path) else v for k, v in kwargs.items()},
        }

    def publish(self, path, state, stage, node_id, parent, step, evidence):
        if (
            not evidence.get("reopened")
            or evidence.get("identity") != state["identity"]
            or evidence.get("size") != state["size"]
        ):
            raise ValueError("Editor verification did not match the managed document.")
        checkpoint, preview = stage / "checkpoint.xcf", stage / "preview.png"
        if not checkpoint.is_file() or not preview.is_file() or checkpoint.stat().st_size == 0:
            raise ValueError("GIMP did not produce both required artifacts.")
        validate_image(preview)
        node = {
            "id": node_id,
            "display_id": f"S{len(state['nodes']):03d}",
            "parent_id": parent,
            "label": step["label"],
            "step": step,
            "checkpoint_hash": digest(checkpoint),
            "preview_hash": digest(preview),
            "created": time.time(),
            "evidence": evidence,
        }
        (stage / "operation.json").write_text(canonical(node))
        # Flush artifacts before publishing the immutable directory and committing the database.
        for file in stage.iterdir():
            if file.is_file():
                with file.open("rb") as stream:
                    os.fsync(stream.fileno())
        destination = path / "nodes" / node_id
        stage.rename(destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        state["nodes"][node_id] = node
        branch = state["active_branch_id"]
        if not branch or state["branches"][branch]["tip_node_id"] != parent:
            branch = uid()
            state["branches"][branch] = {
                "id": branch,
                "name": "main" if parent is None else f"try-{len(state['branches']) + 1}",
                "tip_node_id": node_id,
            }
        state["branches"][branch]["tip_node_id"] = node_id
        state["active_branch_id"] = branch
        state["working_node_id"] = node_id
        state["revision"] += 1
        state["session_status"] = "ready"
        return node

    def create(self, name, source, reference):
        if not name.strip() or len(name) > 100:
            raise ValueError("Project names must contain 1–100 characters.")
        source_meta, ref_meta = validate_image(source), validate_image(reference)
        project_id = uid()
        path = self.root / project_id
        path.mkdir(mode=0o700)
        for directory in ["inputs", "nodes", "staging", "exports"]:
            (path / directory).mkdir()
        state = {
            "schema": 1,
            "id": project_id,
            "name": name.strip(),
            "identity": uid(),
            "size": [source_meta["width"], source_meta["height"]],
            "created": time.time(),
            "nodes": {},
            "branches": {},
            "active_branch_id": None,
            "working_node_id": None,
            "revision": 0,
            "plans": {},
            "operations": {},
            "session_status": "creating",
            "inputs": {},
        }
        for role, original, meta in [("source", source, source_meta), ("reference", reference, ref_meta)]:
            filename = role + (".png" if meta["format"] == "PNG" else ".jpg")
            target = path / "inputs" / filename
            shutil.copyfile(original, target)
            target.chmod(0o400)
            state["inputs"][role] = {"file": filename, "sha256": digest(target), **meta}
        (path / "manifest.json").write_text(
            canonical({key: state[key] for key in ["schema", "id", "identity", "size", "inputs"]})
        )
        self.write(path, state)
        with self.lock(path):
            operation_id = uid()
            state["operations"][operation_id] = {
                "id": operation_id,
                "status": "prepared",
                "kind": "root",
                "created": time.time(),
            }
            self.write(path, state)
            stage = path / "staging" / uid()
            try:
                stage.mkdir()
                self.check_space(path, state["size"])
                evidence = self.adapter.call(
                    self.job(
                        state,
                        "root",
                        path / "inputs" / state["inputs"]["source"]["file"],
                        checkpoint=stage / "checkpoint.xcf",
                        preview=stage / "preview.png",
                    )
                )
                self.verify_inputs(path, state)
                node = self.publish(
                    path,
                    state,
                    stage,
                    uid(),
                    None,
                    {"label": "Original", "tool": "import", "arguments": {}},
                    evidence,
                )
                state["operations"][operation_id].update(status="committed", node_id=node["id"])
                self.write(path, state)
            except Exception as exc:
                state = self.read(path)
                state["session_status"] = "recovery_required"
                state["operations"][operation_id].update(status="failed", error=str(exc))
                self.write(path, state)
                raise
        return self.history(project_id)

    def history(self, project_id):
        path = self.project(project_id)
        state = self.read(path)
        for node in state["nodes"].values():
            try:
                self.verify_files(path, node)
                node["healthy"] = True
            except ValueError:
                node["healthy"] = False
        state["storage_bytes"] = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return state

    def consent(self, project_id, granted):
        if type(granted) is not bool:
            raise ValueError("Consent must be explicit.")
        path = self.project(project_id)
        with self.lock(path):
            state = self.read(path)
            record = {
                "provider": "OpenAI",
                "granted": granted,
                "created": time.time(),
                "scope": "current and future working previews plus reference preview in this project",
                "reference_hash": state["inputs"]["reference"]["sha256"],
            }
            state["vision_consent"] = record
            state.setdefault("consent_events", []).append(record)
            self.write(path, state)
            return record

    def plan(self, project_id, strength, planner="local", instruction=""):
        if not math.isfinite(strength) or not 0.05 <= strength <= 1:
            raise ValueError("Strength must be between 0.05 and 1.")
        if planner not in {"local", "openai"}:
            raise ValueError("Unknown planner.")
        if len(instruction) > 500:
            raise ValueError("Keep instructions under 500 characters.")
        path = self.project(project_id)
        with self.lock(path):
            state = self.read(path)
            if state["session_status"] != "ready":
                raise ValueError("Restore a verified version before planning another edit.")
            self.verify_inputs(path, state)
            node = state["nodes"][state["working_node_id"]]
            self.verify_files(path, node)
            source_preview = path / "nodes" / node["id"] / "preview.png"
            reference = path / "inputs" / state["inputs"]["reference"]["file"]
            if planner == "openai":
                consent = state.get("vision_consent", {})
                if (
                    not consent.get("granted")
                    or consent.get("provider") != "OpenAI"
                    or consent.get("reference_hash") != state["inputs"]["reference"]["sha256"]
                ):
                    raise ValueError(
                        "Explicit project-scoped permission is required before sending previews to OpenAI."
                    )
                if not self.vision or not self.vision.available:
                    raise ValueError(
                        "OpenAI vision planning is not configured. Use local analysis or set OPENAI_API_KEY."
                    )
                analysis = path / "staging" / uid()
                analysis.mkdir()
                reference_preview = analysis / "reference.png"
                self.adapter.call(
                    {
                        "action": "thumbnail",
                        "input": str(reference),
                        "output": str(reference_preview),
                        "orientation": state["inputs"]["reference"].get("orientation", 1),
                    }
                )
                validate_image(reference_preview)
                submission = {
                    "id": uid(),
                    "provider": "OpenAI",
                    "model": self.vision.model,
                    "base_node_id": node["id"],
                    "source_preview_hash": digest(source_preview),
                    "reference_preview_hash": digest(reference_preview),
                    "created": time.time(),
                    "status": "prepared",
                }
                state.setdefault("vision_submissions", []).append(submission)
                self.write(path, state)
                try:
                    steps = self.vision.propose(source_preview, reference_preview, strength, instruction)
                except Exception:
                    submission["status"] = "unconfirmed_or_failed"
                    self.write(path, state)
                    raise
                submission["status"] = "completed"
                planner_name = "openai:" + self.vision.model
            else:
                steps = propose(source_preview, reference, strength)
                planner_name = "local-statistics-v1"
            plan = {
                "id": uid(),
                "base_node_id": node["id"],
                "revision": state["revision"],
                "reference_hash": state["inputs"]["reference"]["sha256"],
                "strength": strength,
                "planner": planner_name,
                "instruction": instruction if planner == "openai" else "",
                "steps": steps,
            }
            plan["hash"] = fingerprint(plan)
            plan.update(next_step=0, expected_base=node["id"], expected_revision=state["revision"])
            state["plans"][plan["id"]] = plan
            self.write(path, state)
            return plan

    def run_step(self, project_id, plan_id, plan_hash, step_index, request_id):
        identifier(request_id)
        if type(step_index) is not int or not 0 <= step_index <= 2:
            raise ValueError("Invalid step index.")
        path = self.project(project_id)
        with self.lock(path):
            state = self.read(path)
            signature = fingerprint([plan_id, plan_hash, step_index])
            prior = state["operations"].get(request_id)
            if prior:
                if prior.get("signature") != signature:
                    raise ValueError("Request ID already belongs to a different operation.")
                return prior
            plan = state["plans"].get(plan_id)
            if (
                not plan
                or plan["hash"] != plan_hash
                or fingerprint(
                    {
                        k: v
                        for k, v in plan.items()
                        if k not in {"hash", "next_step", "expected_base", "expected_revision"}
                    }
                )
                != plan_hash
                or plan["next_step"] != step_index
                or step_index >= len(plan["steps"])
            ):
                raise ValueError("The approved plan or step does not match.")
            if (
                state["session_status"] != "ready"
                or state["working_node_id"] != plan["expected_base"]
                or state["revision"] != plan["expected_revision"]
            ):
                raise ValueError("This plan is stale. Propose a new plan from the working version.")
            self.verify_inputs(path, state)
            parent = state["working_node_id"]
            checkpoint = self.verify_files(path, state["nodes"][parent])
            step = validate_step(plan["steps"][step_index])
            self.check_space(path, state["size"])
            operation = {
                "id": request_id,
                "signature": signature,
                "kind": "edit",
                "status": "prepared",
                "created": time.time(),
                "parent_id": parent,
                "plan_id": plan_id,
                "approved_plan_hash": plan_hash,
                "step_index": step_index,
                "step": step,
            }
            state["operations"][request_id] = operation
            state["session_status"] = "busy"
            self.write(path, state)
            stage = path / "staging" / uid()
            try:
                stage.mkdir()
                evidence = self.adapter.call(
                    self.job(
                        state,
                        "edit",
                        checkpoint,
                        step=step,
                        checkpoint=stage / "checkpoint.xcf",
                        preview=stage / "preview.png",
                    )
                )
                self.verify_inputs(path, state)
                self.verify_files(path, state["nodes"][parent])
                node = self.publish(path, state, stage, uid(), parent, step, evidence)
                operation.update(status="committed", node_id=node["id"])
                plan.update(
                    next_step=step_index + 1, expected_base=node["id"], expected_revision=state["revision"]
                )
                self.write(path, state)
            except Exception as exc:
                # Reload prepared state so publication failures cannot accidentally commit in-memory refs.
                state = self.read(path)
                operation = state["operations"][request_id]
                operation.update(status="failed", error=str(exc))
                state["session_status"] = "recovery_required"
                self.write(path, state)
            return operation

    def restore(self, project_id, node_id):
        path = self.project(project_id)
        with self.lock(path):
            state = self.read(path)
            node = state["nodes"].get(node_id)
            if not node:
                raise ValueError("Version not found.")
            checkpoint = self.verify_files(path, node)
            self.verify_inputs(path, state)
            self.adapter.call(self.job(state, "verify", checkpoint))
            state["working_node_id"] = node_id
            state["active_branch_id"] = next(
                (key for key, value in state["branches"].items() if value["tip_node_id"] == node_id), None
            )
            state["session_status"] = "ready"
            state["revision"] += 1
            self.write(path, state)
        return self.history(project_id)

    def export(self, project_id, node_id):
        path = self.project(project_id)
        with self.lock(path):
            state = self.read(path)
            node = state["nodes"].get(node_id)
            if not node:
                raise ValueError("Version not found.")
            checkpoint = self.verify_files(path, node)
            self.check_space(path, state["size"])
            export_id = uid()
            folder = path / "exports" / export_id
            folder.mkdir()
            self.adapter.call(self.job(state, "export", checkpoint, output=folder / "image.png"))
            meta = validate_image(folder / "image.png", max_bytes=256 * 1024 * 1024)
            if [meta["width"], meta["height"]] != state["size"]:
                raise ValueError("Export resolution does not match the saved version.")
            provenance = {
                "export_id": export_id,
                "node_id": node_id,
                "checkpoint_hash": node["checkpoint_hash"],
                "source_hash": state["inputs"]["source"]["sha256"],
                "export_hash": digest(folder / "image.png"),
                "created": time.time(),
            }
            (folder / "provenance.json").write_text(canonical(provenance))
            return provenance

    def asset(self, project_id, role, asset_id=None):
        path = self.project(project_id)
        state = self.read(path)
        if role in {"source", "reference"}:
            result = path / "inputs" / state["inputs"][role]["file"]
        elif role == "preview" and asset_id in state["nodes"]:
            result = path / "nodes" / identifier(asset_id) / "preview.png"
        elif role in {"export", "provenance"}:
            folder = path / "exports" / identifier(asset_id)
            if not (folder / "provenance.json").is_file():
                raise ValueError("Export not found.")
            result = folder / ("image.png" if role == "export" else "provenance.json")
        else:
            raise ValueError("Asset not found.")
        if result.is_symlink() or not result.resolve().is_relative_to(path) or not result.is_file():
            raise ValueError("Asset not found.")
        return result
