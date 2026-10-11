# Photo Edit Agent — MVP Product Requirements

> One photo. Many possibilities. Every step recoverable.

**Edition:** v0.3-en1 · October 10, 2026
**Status:** Product design; the previously delivered browser demo is not a working GIMP integration.
**Working name:** `photo-edit-agent`; branding remains undecided.

This English edition preserves the design direction established in GIMP Native Grade v0.2 and PixBranch MVP v0.3: native GIMP editing, step-by-step checkpoints, restoration after closing the editor, and a lightweight branching-history UI. It does not return to the earlier approach of rendering a finished image in external Python code and using GIMP only as a viewer.

## 1. Product definition

A local workbench for personal photo-editing experiments: **describe a change, execute it through GIMP's native tools, and preserve each completed step as an image version that can be inspected, restored, compared, or branched.**

This is not a Photoshop replacement, a commercial SaaS platform, or a complete Git implementation. Git manages the application code. Photo history belongs to the application and stays outside the source repository by default.

## 2. Known requirements, assumptions, and evidence

| Category | Input | Design consequence |
|---|---|---|
| Explicit user request | Transfer the color mood of reference photo B to source photo A without redrawing the scene. | Start with global color and tonal adjustments, not generative editing. |
| Explicit user request | Directly use an open-source editor rather than treat it as a preview window. | GIMP performs the actual edits and final export. |
| Explicit user request | Record every step and allow restoration, ideally through a Git-like tree. | Persistent checkpoints and branching history are P0 requirements. |
| Explicit user request | Keep this a personal experiment rather than a company-building exercise. | No accounts, subscriptions, collaboration, growth funnels, or payment flows. |
| Unvalidated hypothesis | A history tree makes alternative edits easier to compare than filenames such as final/final2. | Test whether a user can create two branches and reliably find a preferred version. |
| Unvalidated hypothesis | A small set of GIMP adjustments can produce worthwhile reference-guided results. | Evaluate real photos with human judgment; do not substitute histogram similarity for aesthetics. |

There is no market research sample, retention data, or validated demand estimate behind this PRD. Priorities follow the user's stated needs and the engineering dependencies of reliable recovery.

## 3. Initial user and excluded use cases

The first user is the project author: comfortable with Codex, willing to configure local GIMP and a bridge, and interested in delegating repetitive work without losing control over the photograph. Initial examples should be ordinary travel or everyday photos with reasonably similar lighting and scenes.

The early-adopter profile is a hypothesis: someone who accepts a one-time local setup, works on one photo at a time, and is willing to choose between results and explain what looks unnatural.

Do not optimize the first release for professional batch delivery, print production, RAW development, or multi-user collaboration.

## 4. Critical user journeys

### CUJ-1: Reference-guided grading, with a visible plan and individual steps

1. Create a local project and import source A and read-only reference B. The first release accepts explicitly supported 8-bit SDR sRGB JPEG/PNG inputs. Unsupported formats or color profiles stop the flow with an explanation; conversion is not silent.
2. Connect to GIMP. Check actual versions, discovered tool schemas, the target document, and the permitted operations. Save the initial S000 project and verify it by reopening.
3. Enter: “Borrow the reference's warmth and softer contrast, but do not change the people, objects, or composition.”
4. Review a plan containing at most three proposed adjustments, such as color balance, a shadow curve, and saturation. Each step shows its target layer, tool, exact validated parameters, and a short explanation.
5. Approve one step by default. The user may explicitly approve the displayed group; each edit must still be executed and committed separately.
6. Each step completes native editing, XCF saving, preview generation, and reopen verification before a committed node appears or the working version advances.
7. Compare the original, current version, and reference. The user judges color and skin tone. “No geometric change” must not be presented as “skin tone unchanged.”

Without image-to-model permission, users may describe the desired style and approve explicit parameter operations. The system must not claim to have visually analyzed the reference. Without a model connection, parameter-based editing and history management may remain available, but AI status must show that planning is unavailable.

### CUJ-2: Restore an intermediate version without losing another attempt

The existing branch is `S000 → S001 → S002 → S003`.

Clicking S001 only displays its preview. Selecting **Restore S001 and continue** verifies the checkpoint and opens it in GIMP. S003 remains the original branch's tip.

The next successfully committed edit creates a new branch such as `try-2`, producing `S001 → S004`. Both paths survive. S003 is not rewritten, and node identifiers are not reused.

### CUJ-3: Compare two candidates and export a specific version

Pin S003 as A and select S004 as B. Show the exact version labels, aligned presentation, and corresponding operation paths. Pixel comparison is limited to versions of the same source. A different reference image is displayed as a visual reference, not as a registered pixel diff.

**Export selected version** must identify the selected node explicitly. GIMP exports a full-resolution image from that node's verified checkpoint. Saving a UI thumbnail is not a final export. The first release supports one verified PNG export path.

### CUJ-4: Continue after a restart or failure

After closing both the application and GIMP, reopening the project shows stored history and cached previews first. Editing becomes available only after reconnection and verification of the intended working checkpoint. A cached preview does not prove recoverability.

A timed-out write becomes **Outcome unknown**, pauses editing, and is not automatically retried. Recover a verified checkpoint in an isolated editor session before asking whether to try again. A save failure produces no successful history node and does not advance the working version.

## 5. MVP scope and priorities

| Priority | Capability | Acceptance outcome |
|---|---|---|
| P0 | One project, one source, one read-only reference | Validated inputs, hashes, and color information; no input overwrite. |
| P0 | Native GIMP adapter | At least one of color balance, curves, or saturation passes real integration; other actions remain disabled until verified. |
| P0 | Structured plans and individual approval | The user sees the editing base, target, and parameters. Arbitrary code execution is not an escape hatch. |
| P0 | XCF, preview, log, and commit for each step | A version can be restored after reopening; failures are not presented as success. |
| P0 | Thumbnail history tree with separate viewing and working state | Browsing old nodes does not modify GIMP or branch tips. |
| P0 | Explicit restoration and automatic branching | Previous paths survive; failed restoration does not switch the working version. |
| P0 | Side-by-side A/B and reference comparison | Labels and assets correspond to the actual selected versions. |
| P0 | Export a specified version | GIMP exports from a verified checkpoint and records provenance. |
| P0 | Disconnection, save failure, and uncertain-outcome handling | Further writes are blocked until appropriate recovery. |
| P0 | Model-vision permission and workspace restrictions | No implicit image submission to a model; no network-exposed bridge. |
| P1 | Favorites, branch names, group collapse, shortcuts | Improve navigation without changing history semantics. |
| P1 | Compare slider, difference heatmap, synchronized zoom | Follow correct source/version matching, not precede it. |
| P1 | Manual-edit handoff | Pause the agent and capture the result as one manual snapshot; do not claim per-click recording. |
| P1 | Re-editable native effects | Expose only after bridge support and durable identity mapping are verified. |
| P2 | Selective step replay, preset/skill export, batch editing | Do not treat a history tree as an order-independent processing graph. |
| Excluded | Automatic branch merges, cloud sync, collaboration, painting tools, generative face edits, RAW/HDR development | Keep recovery and color-management complexity bounded. |

**Release boundary:** The first engineering milestone may support only one native adjustment. Calling a release a “reference-guided AI photo-editing MVP” requires permission-aware model input, real plan generation, the native-editing loop, and real-photo acceptance. A frontend simulation does not satisfy those requirements.

## 6. History model: borrow Git's useful concepts, not all its behavior

A committed node represents **the saved and verified image-project state after one meaningful edit**. It is not a prompt, a thumbnail, or an individual network call.

The MVP uses a single-parent tree, not a multi-parent merge graph. Reading a document, saving it, generating a preview, and reopening it are implementation steps within one edit. They do not create separate user-visible versions. Edits proposed by one prompt share an `operation_group_id` while remaining individually recoverable.

| State | Meaning | Update condition |
|---|---|---|
| `selected_node_id` | The version being viewed | Changes when a history node is selected; UI-only. |
| `working_node_id` | The last verified working base | Changes only after successful restoration or a committed edit. Its binding to a live document is valid only while session status is synchronized. |
| `branches[id].tip_node_id` | The latest committed node of a named branch | Advances only when that branch receives a successful new commit. |
| `active_branch_id` | The branch being extended at its tip; may be null at a historical base | Restoring an old node does not move existing tips backward. |
| `session_status` | `disconnected`, `synced`, `busy`, `dirty`, or `indeterminate` | Reported by the controller, never inferred as success by the UI. |

Viewing is not restoring. Restoration does not delete later history. Editing an old state never mutates that state. No successful save means no new commit.

Favorites, tags, and layout are mutable metadata. Failed or uncertain operations belong in activity records, not among successfully restorable history nodes.

## 7. Workspace and key interactions

Use a single main workbench: history on the left, preview in the center, version details and plans on the right, and command input plus activity along the bottom. Connection settings, import, and export use dialogs or drawers.

Always show the viewed version, working version, GIMP status, and AI status. A selection outline differs from a **Working** badge; color alone must not carry the distinction. Action buttons name their base, for example **Run step 1 on S004**.

Opening a document for manual editing is not the same as viewing its preview. Manual mode pauses automatic actions. Until reliable revision detection exists, the supported boundary is a dedicated managed document, one operator, and explicit handoff—not guaranteed detection of every external change.

See [UI-SPEC.md](UI-SPEC.md). The earlier browser demo illustrates interactions only. It does not call GIMP, MCP, or AI and does not create XCF files. Loading a local photo into that demo displays the same unmodified image at every simulated node.

## 8. Reliability, security, and privacy

### Commit rules

Do not edit without a recoverable root checkpoint. Persist a prepared event before writing. Save the resulting XCF and preview to a fresh staging directory, calculate hashes, and verify reopening. Publish immutable artifacts, then record the node, commit event, and branch updates in a database transaction.

GIMP, the filesystem, and the database do not share one atomic transaction. Recovery must reconcile incomplete operations and orphaned files.

### Uncertain calls

A request ID supports application-level deduplication. It does not make a GIMP operation idempotent. A timeout may occur after the image has changed.

Before resuming, stop or isolate the old command so it cannot affect the new working session. Wait for confirmed quiescence, isolate the document, or require a bridge/GIMP restart when isolation cannot be established. Merely resetting a UI status to idle is insufficient.

### Disk space and corruption

The first version stores a complete XCF per committed step. Display actual storage use. Stop new commits when space is insufficient rather than silently deleting old checkpoints.

If a checkpoint is missing or has a mismatched hash, retain the historical record but mark it unavailable for restore/export. A preview may still be viewed. Do not substitute another version while retaining the old label.

### Paths and network exposure

Accept scoped resource IDs, not arbitrary client-supplied absolute paths. Resolve real paths, including symbolic links. Bind services to loopback and require session authentication and exact Origin/Host validation. Do not permit arbitrary cross-origin access or expose general exec/eval to the agent.

Never overwrite inputs or committed checkpoints.

### Image-to-model permission

Local GIMP processing does not imply offline model inference. Before sending a source image, reference, or snapshot, record explicit permission and the chosen provider. Image text, filenames, and EXIF metadata are data, not instructions.

Log short operation explanations, not hidden model reasoning. Diagnostic export excludes private images, absolute user paths, and credentials by default.

## 9. Acceptance criteria and success measures

The following are **planned criteria, not measured results**.

### Recoverability: a hard gate

In real GIMP, create `S000 → S001 → S002 → S003`. Close the app and GIMP. Reopen, restore S001, create S004 on a new branch, then restore S003. Checkpoint hashes must match their records, and source-file hashes must remain unchanged.

Test save failure, write timeout, document reordering, disconnection, corrupt checkpoints, and duplicate requests. None may incorrectly advance a tip, modify the wrong image, or mark failure as success.

### Interaction: observable tasks

Without reading implementation notes, the first user should identify which version is being viewed and which version the next edit will affect. The user should pin A, select B, branch from an old version, and find the previous branch.

A later exploratory test may use three volunteers following the same script. Record confusion and errors; do not present this small sample as market validation.

### Aesthetics: human evaluation

Use five authorized source/reference pairs. Begin with similar scenes and include deliberately different scenes. Record whether the result better matches the desired mood, whether skin/clothing colors remain acceptable, whether the user would keep it, and which steps helped.

Failures are valid evidence. Do not promise recovery of the original photographer's preset or use an invented “style score.”

### Performance: a target and a measurement method

An initial target is p95 below 300 ms from a history click to a cached preview on a specified local machine with 50 nodes. Fix the image size and environment in the benchmark.

Measure GIMP rendering, XCF saving, and reopen verification separately. Do not promise a completion time before measurement, and do not weaken recovery guarantees to meet a UI target.

## 10. Implementation milestones

| Milestone | Exit condition |
|---|---|
| M0 — Interaction model | Demonstrate read-only browsing, separate working state, branching, and failure behavior. The earlier prototype covers only this simulation layer. |
| M1 — One real edit | Connect a local controller to GIMP; create S000; make one native adjustment; save, reopen, and restore with recorded evidence. |
| M2 — Persistent history | Store nodes and refs; branch; recover across restart; deduplicate requests; isolate unknown outcomes; export a real version. |
| M3 — Codex skill and approval | Register structured plans through the controlled interface; bind approvals to the editing base; require model-vision permission. External Codex input is sufficient initially. |
| M4 — Reference-guided experience | Validate two- or three-step plans on real photos and complete the supported native operations and key error flows. Only then describe the release as the reference-grading MVP. |

## 11. Source references

Product structure, priorities, naming, proposed interfaces, and acceptance criteria are project decisions. The references below support external-tool statements in the source design. They are carried forward from the October 10, 2026 source document and were not independently reverified for this English adaptation.

- [GIMP: Undoing](https://docs.gimp.org/3.0/en/gimp-concepts-undo.html): undo history is not preserved in saved XCF files; independent checkpoints underpin this design.
- [GIMP 3.0 release notes](https://www.gimp.org/release-notes/gimp-3.0.html): the basis for a later non-destructive-effects path, not proof of complete MCP support.
- [Community GIMP MCP tool definitions](https://github.com/maorcc/gimp-mcp/blob/main/gimp_mcp_server.py): candidate native operations and save interfaces; tool presence is not integration evidence.
- [Codex skills](https://developers.openai.com/codex/skills/) and [MCP configuration](https://developers.openai.com/codex/mcp/): the proposed agent integration still requires the controlled application layer.
- [React Flow](https://reactflow.dev/learn): an optional renderer for nodes and edges, not a history or recovery implementation.
