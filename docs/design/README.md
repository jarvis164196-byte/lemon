# Photo Edit Agent

**One photo. Many possibilities. Every step recoverable.**

A proposed local-first workbench for AI-assisted photo editing with a Git-like history tree. Describe a change, review the plan, and use GIMP to perform the edit. Preserve each completed step as a version you can inspect, restore, compare, or branch from.

> **Status: design documentation and a previously delivered browser interaction demo. The real controller, GIMP/MCP integration, AI planning, XCF checkpointing, and full-resolution export have not been implemented or validated in that demo.**

`photo-edit-agent` is a working repository name, not a final branding decision. [Naming options](NAMING.md) explore the multiverse and parallel-versions theme. No remote repository has been created or renamed by this documentation update.

## What this package contains

| Document | Purpose |
|---|---|
| [Product requirements](PRD.md) | Goals, user journeys, priorities, history semantics, and acceptance criteria. |
| [UI specification](UI-SPEC.md) | English wireframe, navigation, controls, approval flow, and error-state copy. |
| [Architecture](ARCHITECTURE.md) | Component boundaries, single-writer control, persistence, and proposed API contracts. |
| [Implementation backlog](BACKLOG.md) | Initial GitHub issue drafts, dependencies, and completion evidence. |
| [Naming exploration](NAMING.md) | Straightforward and multiverse-inspired names, with a recommendation. |
| [Prototype status](PROTOTYPE-STATUS.md) | What the earlier demo illustrates and what it does not prove. |
| [Agent instructions](../../AGENTS.md) | Constraints for implementing the project without bypassing its safety and history guarantees. |

This is an **English documentation package**, adapted from the previously delivered PixBranch MVP v0.3. It does not include a translated prototype, an application installer, or a working backend. The earlier prototype remains a separate artifact.

## The core experience

Start with a source photo and an optional reference photo. Propose a small plan, approve a step, and let the managed editor execute it. A version becomes part of the history only after its project checkpoint and preview have been saved and verified.

```text
S000 Original
  └─ S001 Warmer midtones
       ├─ S002 Softer contrast
       │    └─ S003 Lower saturation
       └─ S004 Cooler shadows
            └─ S005 A different interpretation
```

Selecting S001 previews it without changing the working document. Restoring S001 explicitly changes the editing base after verification. A new edit from that historical state creates another branch; S003 remains available.

## Principles

- **GIMP does the editing.** Do not replace native editing with an external pixel-processing engine or browser filters.
- **Browsing is not restoring.** The selected preview, verified working version, and branch tips are separate states.
- **A saved checkpoint makes a version.** A successful tool response or a thumbnail alone is not a committed edit.
- **History is preserved.** Never overwrite inputs, committed checkpoints, or previous branches.
- **An uncertain result is not a retry invitation.** Isolate the uncertain editor state and restore a verified checkpoint before continuing.
- **Local editing does not imply an offline AI model.** Obtain explicit permission before sending photos or snapshots to a model provider.

## Two different kinds of version control

Git manages this project's source code, documentation, and skills. The application manages the user's photo history in a separate local workspace. Photos, XCF files, previews, prompts, and private logs do not belong in the source repository by default.

The included `.gitignore` provides basic guardrails, not a complete privacy or data-loss prevention system.

## Where implementation starts

Read the [PRD](PRD.md) and [architecture](ARCHITECTURE.md), then complete Backlog Issue 01: use a real GIMP instance to perform one native adjustment, save a checkpoint, reopen it, and restore the original version.

The defining acceptance test is:

> Make three real edits, close the application and GIMP, reopen the project, restore an earlier step, create a new branch, and restore the old branch again without losing either outcome.

Do not delay that test to build accounts, billing, cloud storage, a desktop installer, or a sophisticated node canvas.

## Documentation conventions

This edition uses English for requirements, UI copy, operation labels, and agent instructions. `S001` is a display label; persistent identifiers must be collision-resistant. A **version** is a committed image-project state, a **checkpoint** is its saved editor project, and a **branch** preserves a line of edits.

Requirements and examples describe the intended product, not completed implementation. External references are carried forward from the source design; they were not independently rechecked during this English rewrite. GIMP remains the proposed editor, not a confirmed identification of the original WeChat article's project.
