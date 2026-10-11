# Prototype and Validation Status

## What was previously delivered

The earlier PixBranch MVP package contains a standalone HTML/CSS/JavaScript interaction demo. It illustrates version selection, separate working state, comparison, simulated restoration, branching, plan approval, and selected failure states.

That earlier package also contains a report of 20 browser interaction checks using Playwright and Chromium. The accompanying validation note says the checks passed. The browser received the standalone HTML through `page.set_content()` because the environment blocked `file://` navigation; double-clicking the HTML file was not directly tested there.

These are statements about the previously supplied artifacts. **Those browser checks were not rerun for this English documentation update.**

## What those checks do not establish

The previous browser checks do not establish a real GIMP or MCP connection, native color processing, XCF checkpoint saving or reopening, persistent project recovery, model-based image analysis, full-resolution photo export, aesthetic quality, or performance on real photographs.

The old screenshots are UI fixtures, not GIMP screenshots or processed user photos. The demo JSON is simulated history. Loading a photo into the demo only changes the layout preview; all versions show the same unmodified image.

## What this English edition changes

This package rewrites the README, PRD, UI specification, architecture, backlog, and agent instructions in English. It adds an updated creative naming shortlist while keeping `photo-edit-agent` as a working label.

It does not change the original artifacts, translate the prototype's interface, install software, connect to GIMP, create a repository, or claim that the backend exists. The prototype and its historical test outputs are not duplicated into this docs-only bundle.

## Editorial clarifications

The English edition makes two existing safety distinctions explicit: a remembered working-node ID does not prove a live synchronized editor, and a failed save can leave the live document unsynchronized even when history remains at the last committed node.

Approvals remain tied to an exact plan and editing base. All application APIs and future effect-editing controls remain proposals, not discovered upstream tools.

## Validation of this package

The accompanying `validation/documentation-checks.json` records only checks actually run on this English package: document inventory, local Markdown link targets, JSON example syntax, absence of untranslated CJK text, and archive integrity.

Those checks are editorial and packaging checks. They are not browser, controller, editor-integration, or photo-quality tests.

## Source and reference handling

The content is adapted from the attached `pixbranch-mvp.zip`, especially its README, `AGENTS.md`, PRD, UI specification, architecture, backlog, and validation note. Names in the old files remain unchanged in the original archive.

External documentation references have been carried forward from the source design. This translation did not independently revisit those websites or verify current upstream versions. Real implementation must discover capabilities, lock verified versions, and produce fresh integration evidence.
