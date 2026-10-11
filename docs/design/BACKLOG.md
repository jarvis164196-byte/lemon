# Photo Edit Agent — Initial GitHub Issue Drafts

**Status:** Copy-ready planning notes. These issues have not been created on GitHub. Priorities and order follow implementation dependencies, not time estimates.

## Issue 01 — One real native edit with a recoverable checkpoint [P0]

**Goal:** Prove the complete path with real GIMP before building more UI.

Import one supported photo, discover the installed tool schema, save and reopen S000, execute one verified native color adjustment, and save S001 with its preview. Reopen both versions and verify the managed source/document identity. Preserve the original file hash.

If GIMP or the required native action is unavailable, stop with a clear error. Do not replace the edit with external Python or browser processing.

**Done when:** Actual environment versions, tool invocations, real XCF files, previews, reopen checks, and restoration evidence are recorded. A fake adapter is insufficient.

## Issue 02 — Immutable history and branch storage [P0]

**Goal:** Preserve every successful attempt without confusing the selected preview with the working version.

Implement nodes, branches, operations, events, and session revisions. Use unique persistent IDs and separate display aliases. Keep selected, working, active-branch, and branch-tip state separate. Create a new branch when the first edit from a historical base commits.

Repeated request IDs return the existing request state rather than executing another edit. An existing commit is never overwritten.

**Done when:** For `S000 → S001 → S002 → S003`, restoring S001 and committing S004 leaves the original tip at S003. Failed saves and duplicate requests produce no extra successful nodes.

**Dependency:** Issue 01 establishes the real adapter contract; storage unit tests may be written independently.

## Issue 03 — Connect the workbench to the controller [P0]

**Goal:** Replace simulated state with durable controller state and scoped preview assets.

Make history selection read-only, restoration explicit, and the working base continuously visible. Display actual connection and session status. Bind export to the selected node, with an explicit confirmation. Disable writes when disconnected or uncertain.

Preserve node IDs in labels and loading states so old previews are never shown under a newly selected version's name.

**Done when:** A real native edit creates the expected visible node; clicking an older node makes no editor write; reconnecting reloads durable state without claiming premature synchronization.

**Dependency:** Issues 01–02.

## Issue 04 — Fault isolation and restart recovery [P0]

**Goal:** Recover safely when the editor, storage, or bridge fails.

Cover save failure, unknown write outcomes, bridge disconnection, hash mismatch, reordered document indices, late-completing writes, and process restarts. Never advance a tip without a verified commit.

Recovery must prevent an old uncertain command from affecting the replacement working session. Require a bridge/GIMP restart when isolation cannot be established. Reconcile staging artifacts and published files with durable operation records.

**Done when:** Fault-injection tests show no wrong-document writes, no false success nodes, and no blind retries. The real close/reopen/restore/branch/restore test passes with recorded evidence.

**Dependency:** Issues 01–03.

## Issue 05 — Codex skill and controlled plan approval [P0]

**Goal:** Turn instructions into bounded proposals without bypassing history.

Create structured plans only from discovered capabilities. Bind approval to the exact plan hash, base node, expected revision, and permitted steps. Route all writes through the controller. Expose no unrestricted editor or exec/eval bypass.

Default to approval of one step. Group approval runs the displayed steps serially with individual commits and stops on failure. Require explicit permission before sending images to a model provider.

**Done when:** Stale or modified plans cannot execute under old approvals. No image reaches a model without recorded consent. Missing model or editor capabilities remain visible rather than silently simulated.

**Dependency:** Issues 01–04; UI-embedded chat is not required.

## Issue 06 — Comparison, explicit-version export, and photo trials [P0]

**Goal:** Help the user choose and retain a real result.

Limit same-source A/B comparison to compatible versions. Keep reference comparison distinct. Export full-resolution PNG from the selected healthy XCF through GIMP, and record node/source provenance.

Evaluate five authorized source/reference pairs. Record the user's assessment of the intended mood, skin/clothing colors, and willingness to keep a result. Preserve negative feedback rather than inventing a style-similarity score.

**Done when:** Exported images trace to the specified node, not a thumbnail or the wrong working version. The real-photo evaluation notes exist and are separate from integration tests.

**Dependency:** Issues 01–05.

## Issue 07 — Favorites, branch names, and task groups [P1]

**Goal:** Make longer histories easier to navigate.

Add favorites, readable branch names, group collapse, and navigation shortcuts. Treat these as mutable display metadata. Do not alter immutable parents or rewrite operations through graph dragging.

**Done when:** Display edits survive reload without changing any checkpoint, historical invocation, or parent relationship.

**Dependency:** Issue 02 and a functioning workbench.

## Issue 08 — Manual handoff and editable native effects [P1]

**Goal:** Allow controlled human intervention and later parameter editing.

Pause the agent before manual edits and capture the result as one verified snapshot. Do not promise to intercept every manual action.

Separately verify effect creation, configuration reads, persistence, visibility changes, and logical identity mapping through the chosen GIMP bridge. Do not expose historical-parameter editing before those capabilities exist. Editing an old version must still create a new version, not overwrite its checkpoint.

**Done when:** Manual handoff preserves the prior branch, and every supported effect operation has real save/reopen evidence. Unsupported controls remain unavailable.

**Dependency:** Reliable recovery and the tested native adapter.
