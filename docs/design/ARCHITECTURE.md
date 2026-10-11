# Photo Edit Agent — Architecture and Data Contracts

**Edition:** v0.3-en1 · October 10, 2026

> The interfaces below are proposed application contracts, not a list of existing GIMP MCP tools. The controller and adapters described here remain implementation work.

## 1. Minimum architecture

```text
Browser UI ------ local HTTP + event stream -----+
                                                 |
Codex + skill --- restricted application MCP -----+
                                                 v
                                      Photo Edit Agent Controller
                                        | validation / write queue
                                        | approvals / history / recovery
                                        v
                                      GIMP adapter + community MCP
                                        v
                                      GIMP
                                        | native edits / XCF / previews / export
                                        v
                                      Project directory + SQLite
```

**The controller is the only writer to the managed GIMP document.** Neither the UI nor Codex may bypass it. A skill describes the workflow; controller code enforces approvals, serialization, checkpointing, and commit rules.

The proposed implementation uses React and TypeScript for the UI and Python for the local service and adapter. Begin with a browser connecting to the local service. A Tauri/Electron wrapper is not required for the first working loop.

A simple tree can use ordinary HTML/CSS or SVG. React Flow is an optional node-and-edge renderer when richer graph presentation becomes useful; it does not implement project history [S1]. The earlier prototype is plain HTML/CSS/JavaScript, not the backend shown above.

The real local service requires authentication, exact Origin/Host checks, loopback binding, and a dedicated runtime directory.

## 2. Model integration and permissions

Initially, users can issue instructions in Codex while the UI displays controller-registered plans and collects approval. Embedding a model chat panel is a separate integration task, not a prerequisite for the native-editing loop.

Do not assume that a Codex subscription automatically provides a generic server-side model API. Integrations must use a supported, explicitly configured path.

The intended project skill path is `.agents/skills/photo-edit-agent/SKILL.md`. This package provides implementation instructions, not that completed skill or its backend tools.

Candidate restricted application tools include `propose_plan`, `execute_approved_step`, and `restore_checkpoint`. These names are proposed, not existing or discovered tool names. Codex's skills and MCP documentation are listed as references [S2, S3].

A project records its chosen provider and image-to-model consent. Photo processing, model inference, and UI display are separate trust boundaries. A local editor does not make a remote model local.

## 3. Persistent project data

```text
<user-workspace>/<project-id>/
  manifest.json              # Project/schema version, input hashes, color/precision metadata
  project.sqlite             # Nodes, branches, operations, events, session state
  inputs/                    # Read-only copies of source and reference
  nodes/<node-id>/
    checkpoint.xcf
    preview.png
    operation.json
  staging/<request-id>/      # Uncommitted artifacts for crash reconciliation
  exports/<export-id>/
    image.png
    provenance.json
```

Use collision-resistant node IDs; `S004` is a display alias. Each node has one parent. Derive children from the parent index instead of storing two relationship directions that can disagree.

A reference image is an asset, not a node in the edit tree. Bind its asset ID and hash to each relevant plan and operation. Replacing a project's current reference must not rewrite what an earlier edit used.

An abbreviated immutable node record:

```json
{
  "id": "<generated-unique-id>",
  "display_id": "S004",
  "parent_id": "<S001-node-id>",
  "operation_group_id": "<plan-id>",
  "operation_id": "<prepared-operation-id>",
  "label": "Cooler shadows",
  "checkpoint": {
    "asset_id": "<checkpoint-asset-id>",
    "sha256": "<verified-checkpoint-hash>"
  },
  "preview": {
    "asset_id": "<preview-asset-id>",
    "sha256": "<verified-preview-hash>"
  },
  "tool_invocation": {
    "name": "<discovered-tool-name>",
    "arguments": {}
  },
  "document_identity": {
    "logical_layer_id": "<managed-layer-id>"
  },
  "environment": {
    "gimp": "<observed-version>",
    "bridge_commit": "<verified-checkout-commit>"
  }
}
```

All angle-bracket values are placeholders, not real hashes, tool parameters, or execution evidence. Obtain actual arguments from the installed tool's discovered schema and compatibility tests. Do not pass a made-up field such as `shadows: +8` to an unrelated curves API.

Native GIMP image IDs and list indices are runtime identifiers, not durable project identities. Rebind after reopening. Before writing, verify the managed document, logical layer, source provenance, and expected session revision.

Where the bridge lacks strong revision detection, limit the workflow to a dedicated document, one operator, and explicit manual handoff. Do not claim universal concurrent-edit detection.

## 4. Request and state contracts

These HTTP routes are **proposed application APIs**.

| Route | Intent | Required server checks |
|---|---|---|
| `GET /projects/:id/history` | Read nodes, refs, and health. | Project authorization and schema compatibility. |
| `POST /projects/:id/plans` | Register a plan awaiting approval. | Base node, reference permissions, available tools, and revision. |
| `POST /projects/:id/plans/:plan/approve` | Approve exact displayed steps. | Exact plan hash, base node, permitted steps, and expected revision. |
| `POST /projects/:id/operations` | Execute one approved step. | Request ID, approval, expected base/revision, and exclusive write lock. |
| `POST /projects/:id/restore` | Restore a committed checkpoint. | Hash, health, session state, and unsaved/uncertain changes. |
| `POST /projects/:id/exports` | Export a named version. | Explicit node, supported format, verified project, and exclusive output path. |
| `GET /projects/:id/events` | Resume activity after reconnecting. | Authorization and last event ID; do not rely on a single live message. |

Clients pass `node_id` and `asset_id`, not arbitrary filesystem paths. Reusing a request ID returns the existing operation's status rather than executing a second edit. This is application-level deduplication, not an exactly-once guarantee from GIMP.

Operation lifecycle and committed nodes are different concepts:

```text
Operation:
  proposed -> approved -> prepared -> applying -> saving -> verifying -> committed
                               \----------- failure or uncertain outcome --------/

Node:
  created only after a verified commit;
  later health findings may mark it unavailable without rewriting its historical content.
```

Use separate state fields for selected node, verified working base, active branch, branch tips, and live session status. A remembered working-node ID does not prove the editor is connected or synchronized.

Approval binds to an exact plan and base. Parameter edits or a restored base invalidate any approval that no longer matches. Within an approved group, advance step by step only through the expected successful predecessor commits.

## 5. Commit publication and recovery

The intended successful sequence is:

1. Validate a healthy parent checkpoint and acquire the project's write lock.
2. Persist a prepared operation with its request ID, expected base, approved arguments, target, and before-checkpoint reference.
3. Execute one native edit in the managed GIMP document.
4. Save an XCF and corresponding preview into a fresh staging directory.
5. Validate file presence, hashes, source/target identity, image metadata, and the result of reopening through GIMP.
6. Publish artifacts to a new immutable node directory.
7. In one database transaction, record the node and committed event, advance the applicable branch, and update the verified working base.
8. Notify the UI from durable state. A lost notification does not erase the commit.

There is still a crash window between file publication and the database transaction. On restart, reconcile incomplete operations, staging directories, and orphaned node directories. Files alone are not proof of a committed version. Keep recoverable artifacts for inspection rather than silently deleting them or inventing commits.

A timed-out command may complete late. Before restoring, ensure it cannot alter the replacement working document: wait for confirmed quiescence, isolate documents using verified adapter guarantees, or restart the bridge/GIMP when necessary. Marking a request idle does not provide that guarantee.

Checkpoints form the recovery source of truth; the live editor is a working copy that may be disconnected, busy, dirty, or uncertain.

## 6. Native effects and checkpoints

The source design uses independent checkpoints because GIMP's undo history is not saved in XCF [S4]. Session-local Ctrl+Z is not the cross-restart recovery contract.

GIMP's non-destructive effects provide a possible later path, but each bridge operation must be verified to create and persist the intended editable effect [S5]. P0 may use verified native adjustments with complete XCF snapshots.

Even after editable effects are available, historical versions remain immutable. Changing an effect on an older version creates a new branch node rather than modifying an existing checkpoint.

Selective replay is not a merge. Reapplying the same later parameters after changing an earlier step can produce different pixels. Future replay must distinguish fixed parameters from values derived from the earlier image state.

## 7. Test layers

| Layer | Evidence | Does not establish |
|---|---|---|
| Documentation checks | Valid links, consistent identifiers, readable examples. | Runtime behavior. |
| Browser prototype | UI state changes, labels, branches, and injected-failure behavior. | Native editing or checkpoint recovery. |
| Controller tests with a fake adapter | Approval, parent/ref invariants, deduplication, failure handling. | Compatibility with a real GIMP build. |
| Real integration | Actual GIMP/bridge versions, invocation records, real XCF files, reopen and restoration evidence. | Subjective photo quality. |
| Human photo evaluation | Authorized source/reference examples and user judgments. | Generalized style-matching accuracy or market demand. |

Maintain the distinction in the README, CI output, issue completion notes, and demonstrations. Do not reuse earlier algorithm or browser test counts as proof of this controller's behavior.

## References

These references are carried forward from the source design, not freshly checked for this English rewrite.

- [S1: React Flow](https://reactflow.dev/learn)
- [S2: Codex skills](https://developers.openai.com/codex/skills/)
- [S3: Codex MCP](https://developers.openai.com/codex/mcp/)
- [S4: GIMP Undoing](https://docs.gimp.org/3.0/en/gimp-concepts-undo.html)
- [S5: GIMP 3.0 release notes](https://www.gimp.org/release-notes/gimp-3.0.html)
- [Community GIMP MCP source](https://github.com/maorcc/gimp-mcp/blob/main/gimp_mcp_server.py)
