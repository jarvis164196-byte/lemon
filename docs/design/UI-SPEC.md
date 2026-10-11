# Photo Edit Agent — UI and Interaction Specification

**Edition:** v0.3-en1 · October 10, 2026
**Status:** English design specification. The earlier interactive prototype has not been translated or connected to GIMP by this documentation update.

The goal is not to copy GIMP's toolbar. It is to make three things continuously clear: **What am I viewing? What will the next edit change? Are my earlier attempts still available?**

## 1. Main workbench wireframe

```text
+------------------------------------------------------------------------------------------------+
| Photo Edit Agent / Color study     GIMP: Synced   AI: Vision off      Import   Export selected   |
+------------------------+-------------------------------------------+---------------------------+
| HISTORY                | Viewing: S004       Working: S003         | VERSION / PLAN            |
|                        |                                           |                           |
| o S000 Original        | [Single] [A/B compare] [Reference]        | S004 Cooler shadows       |
| |                      |                                           | Parent: S001              |
| o S001 Warm midtones   | +---------------------------------------+ | Operation: Color balance  |
| |\                     | |                                       | | Target: Working layer     |
| | o S004 Cool shadows  | |                                       | |                           |
| | |                    | |          Selected preview             | | Parameters / explanation  |
| | o S005 Soft contrast | |                                       | | Checkpoint: Verified      |
| |                      | |                                       | |                           |
| o S002 Lift shadows    | +---------------------------------------+ | [Pin as A]                |
| |                      |                                           | [Restore and continue]    |
| o S003 Low saturation  | A: S003                    B: S004       |                           |
|   [Working] [Favorite] |                                           |                           |
+------------------------+-------------------------------------------+---------------------------+
| Edits will start from S003 on natural      [Describe a change...]             [Propose plan]    |
| Plan: 1. Warm midtones -> 2. Shadow curve -> 3. Reduce saturation    [Approve step] [Approve all] |
| Activity: S003 saved / Saving checkpoint / Outcome unknown; recovery required                   |
+------------------------------------------------------------------------------------------------+
```

Use a restrained, neutral workspace so the photograph remains the visual focus. The tree needs a limited set of highlights, not a saturated background that competes with the image. Desktop use comes first; narrow layouts must remain readable without hiding the editing base or error state.

## 2. Five workspace regions

### A. Top bar

Keep the working title, project name, and connection states visible. GIMP states should distinguish at least:

- Disconnected.
- Connected, no document bound.
- Synced to a verified working version.
- Running an operation.
- Outcome unknown.
- Manual changes awaiting capture.

Show model availability and permission separately. A single green indicator must not imply that GIMP, the model, and the saved checkpoint are all healthy.

Export binds to `selected_node_id`, not implicitly to the working document. Confirm the source node before export. A demonstration that only exports JSON must label that action **Export demo JSON**, not **Export photo**.

### B. History tree

One node represents one committed image state. Show a short ID, readable edit label, thumbnail, branch/tip indicator, and health status. Parent relationships define the editing path; timestamps are secondary.

Use an outline for selection and a text badge for the working version. Keep technical fields in the inspector rather than crowding every node. Lay out parent-child paths automatically from top to bottom. Do not allow users to reconnect nodes by dragging edges.

A click changes viewing state only. A double-click must not trigger a write either. For up to 50 nodes, automatic layout, scrolling, and **Locate working version** are sufficient. Free-positioning, minimaps, and advanced graph zoom are enhancements.

The frontend may cache history, but that cache cannot establish that GIMP is currently synchronized.

### C. Preview area

**Single** shows the selected node. **A/B compare** identifies two specific versions of the same source. **Reference** shows the reference next to the selected version without pretending the two images are pixel-aligned.

Each image has a node label, title, preview resolution, and loading status. Preserve aspect ratios. When loading another preview, show a loading state rather than leave the old image under a new label.

Mouse and keyboard comparison controls never modify the project. P0 requires correct side-by-side comparison. A slider, magnifier, and difference heatmap can follow later.

The earlier demo displays the same unmodified local photo at every simulated node. Its color swatches describe intended edits, not actual results. Retain a visible **Layout demo — no color editing** label when using such fixtures.

### D. Version inspector and operation plan

Version details are read-only by default: node, parent, edit, target, parameters, short explanation, and checkpoint health. Place hashes, software versions, and invocation records in an expandable technical section.

Changing a historical step must not overwrite it. A later feature may propose a new edit from that step's parent and produce a new branch. Until that exists, do not show freely editable historical parameter fields that imply in-place mutation is supported.

A plan shows its base node, reference asset, target layer, exact proposed parameters, and expected impact. Show the number of edits before approval. A multi-step prompt may be displayed as a collapsible task group, but its versions remain individually saved and recoverable.

### E. Command input and activity

The command panel always says **Edits will start from Sxxx**. Browsing another version does not silently change that base.

When a user says “from the current version” while viewing and working states differ, name the intended base in the plan and require approval. Do not guess and immediately execute.

The controller may expose stages such as `prepared`, `applying`, `saving`, `verifying`, and `committed`; show plain-English explanations alongside them. Store a concise operation explanation, not hidden model reasoning.

## 3. Interaction contract

| User action | Immediate effect | Must not happen |
|---|---|---|
| Select S001 | Display its cached preview and details. | No GIMP call, working-base change, or branch-tip movement. |
| Pin as A | Store the comparison baseline and switch to A/B. | No change to the editing base. |
| Restore and continue | Verify the checkpoint and restore it in GIMP; update working state only on success. | No history deletion or blind retry of uncertain writes. |
| Execute at a historical base | Create a new branch on the first successful commit. | No overwrite of an existing tip and no reused node IDs. |
| Propose plan | Create a visible plan awaiting approval. | No immediate pixel modification. |
| Approve group | Execute the displayed steps serially, committing each separately. | No continuation after failure or uncertainty. |
| Cancel remaining steps | Stop scheduling further operations; await the current operation's outcome. | No unsupported claim that an in-flight GIMP operation was canceled. |
| Enter manual editing | Pause agent writes and hand control to the user. | No concurrent automatic edits to the managed document. |
| Finish manual editing | Capture one new manual snapshot after verification. | No claim to have recorded every individual mouse action. |

## 4. Required states and messages

### Viewing a historical node

Show **Viewing S001 · Working version remains S003**. Offer **Restore S001 and continue**. The command panel still names S003 until restoration succeeds.

### Unknown edit outcome

Keep a persistent warning:

> GIMP may have applied this step, but the result could not be confirmed. Further editing is paused.

Preserve the operation record. Offer recovery that isolates the uncertain editor session before restoring a saved version. Do not dismiss a toast and return to a healthy status automatically.

### Missing or corrupt checkpoint

Keep the node in history and allow its cached preview to be viewed. Mark it **Unavailable for restore** and disable restore/export. A different healthy node may be chosen, but the unavailable node must not be silently replaced.

### Save failure

> This edit was not saved as a recoverable version. History remains at S003.

The failed operation appears in activity, not as a successful child node. Even when the saved working base remains S003, the live document must not be shown as synchronized until recovery has verified it.

### GIMP disconnected

History and cached previews remain browsable. Native edits, restoration, and full-resolution export are disabled. Demo mode must be visibly different from a real connection.

### Model vision not permitted

The user may view local images. The model receives only permitted text and structured information. Do not display **Reference analyzed** when the model has not received the image.

## 5. English dialog and button copy

| Context | Copy |
|---|---|
| Restore confirmation | Restore the image-project state saved at S001? Your saved S003 version will remain available. Further edits will create a new branch. Unsaved manual changes must be captured first. |
| Branch created | Created try-2 from S001. S003 on the original branch is still available. |
| Group approval | This plan contains 3 native editing steps. Each step will be saved separately. If a step fails or its outcome is unknown, the remaining steps will stop. |
| Export confirmation | Export S004, not the current working version S003. Format: PNG. The image will use the full resolution of S004's saved project. |
| Prototype banner | Interaction demo — GIMP and AI are not connected. |
| Prototype operation | Simulate step 1 on S003. |
| Recovery action | Isolate session and restore saved version. |
| Comparison action | Pin as A. |
| Read-only navigation | View version. |
| Explicit restoration | Restore and continue. |

Demo exports must include `demo: true`. They must not contain invented XCF paths or fabricated hashes.

## 6. Accessibility and responsive behavior

Controls are reachable by Tab and have visible focus. If the history uses ordinary buttons, do not assign an ARIA tree role without implementing the corresponding keyboard model. Supplement color with labels and badges. Keep errors visible and announce status changes through an appropriate live region.

Images need alternative text. Icon-only controls need accessible names. Do not distort images to fill a container.

Wide screens use three columns. Medium layouts move the inspector below the main work area. Narrow layouts stack history, preview, and details. The working base, unknown-outcome warning, and connection state must survive every layout.

## 7. Earlier prototype coverage

The separately delivered browser demo supports fixture history navigation, pinning A, side-by-side layout, simulated restoration, simulated automatic branching, fixed-template plans, stepwise simulation, save-failure and unknown-outcome injection, favorites, and demo JSON export.

Local JPEG/PNG selection is for layout inspection only. It does not upload, edit, or persist the images. Refreshing resets the demo.

It does not implement MCP, Codex inference, native GIMP editing, XCF saving or verification, disk-backed project recovery, or real image export. It is an aid to understanding this specification, not evidence that M1 or M2 is complete.
