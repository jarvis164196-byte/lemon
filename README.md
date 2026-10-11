# Lemon

**Borrow the mood. Keep the moment.**

Lemon is a local photo-grading workbench: give it a source photo and a reference, review a small editing recipe, and let GIMP apply the adjustments. Every successful step becomes a verified version you can compare, restore, branch from, and export.

**Status: working engineering alpha.** Real GIMP editing, checkpoint recovery, branching, and PNG export are implemented and tested. The default planner uses deterministic local image analysis. An optional OpenAI vision planner accepts a description of the desired mood, with explicit project-scoped permission and an API key; its provider contract is unit-tested, but a live paid request has not been validated in this checkout. It matches global tone, warmth/tint, and saturation; it cannot move light sources, reproduce a photographer's exact preset, or judge aesthetics. Human photo evaluation is still outstanding.

## Run locally

Requires **Python 3.11+** and **GIMP 3** with its Python batch interpreter. Native integration has been tested on macOS arm64 with GIMP 3.2.4. Linux is supported by the adapter design but has not been integration-tested. Windows is not supported yet (POSIX process isolation and file locks).

1. Install [GIMP from its official site](https://www.gimp.org/downloads/).
2. Clone and install Lemon:

```sh
git clone https://github.com/jarvis164196-byte/lemon.git
cd lemon
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
lemon
```

Lemon opens a browser at `127.0.0.1:8765` using a private session link. If your browser does not open, copy the **private launch URL** printed in the terminal. Do not share that link. The server binds only to loopback, checks the exact Host and Origin, and authenticates private project routes. Local mode makes no cloud requests and needs no accounts or API keys. There is no telemetry. Optional OpenAI planning sends only the consented previews and your instruction.

GIMP is detected at `/Applications/GIMP.app/Contents/MacOS/gimp` on macOS or through `gimp` / `gimp-3.0` on PATH. Override if needed:

```sh
export LEMON_GIMP="/path/to/gimp"
lemon --data-dir /path/outside/your/repository --port 8765
```

Projects default to `~/.local/share/lemon`. They contain private source/reference copies, XCF checkpoints, GIMP-rendered previews, an SQLite history database, and exports with provenance. Keep this directory outside your source checkout. Checkpoints are never automatically pruned; runtime logs and uncommitted artifacts also remain local for diagnosis.

## Two photos → a new look

1. Import your source and reference. Supported: single-image **8-bit sRGB RGB/RGBA PNG or RGB JPEG**, up to 40 MB and 32 MP each. Untagged files are treated as sRGB. Camera EXIF orientation is applied by GIMP to the managed copy; original files remain unchanged. Wide-gamut JPEG/PNG profiles, HDR, grayscale, and indexed inputs are rejected. RAW source and reference files up to 128 MB are developed locally with LibRaw into an 8-bit sRGB working copy (camera white balance, automatic brightness, camera orientation). Original RAW bytes and conversion provenance are preserved. RAW sensor dimensions, including borders, must fit within 32 MP.
2. GIMP creates and reopens the original XCF checkpoint. No editing starts without it.
3. Choose a match strength and select **Analyze reference**. Local statistics propose three bounded adjustments: a monotonic brightness curve, midtone color balance, and saturation.
4. Inspect exact parameters. Approve one step, or explicitly approve the remaining recipe. Each step saves and verifies its own version; any failure stops the group.
5. Compare with the reference or pin a version as **Before**. Selecting history only changes the preview.
6. **Restore and continue** verifies an earlier checkpoint. The next successful edit creates a branch, preserving the old tip.
7. **Export selected** produces a full-resolution PNG through GIMP from that exact checkpoint. EXIF, GPS, XMP, and comments are omitted from export; the color profile is retained.

Use photos with similar scenes and lighting for the first experiments. Large scene differences can produce unwanted color casts. Review skin and clothing colors yourself. Lower the strength, restore, and try another branch when a result feels wrong.

## Optional AI direction

Local reference matching works without a model. To enable the vision planner, set `OPENAI_API_KEY` in your shell before starting Lemon. Never paste it into an issue or commit it. `LEMON_VISION_MODEL` defaults to `gpt-4.1-mini` and can be set to another model that supports image input and structured Responses output.

Open **Optional AI direction** in the project, choose **OpenAI vision**, describe the desired feeling, and explicitly allow that provider to receive this project's working and reference previews. Only **Analyze reference** sends the request; granting permission alone sends nothing. Permission is stored per project and can be revoked. API usage may incur charges. The request sets `store: false`; this is not a promise of zero provider retention.

GIMP renders both previews and strips EXIF/XMP/IPTC metadata before transmission. The backend validates the returned bounded recipe and shows it for edit approval. The model has no tools, filesystem access, or execution capability. A provider failure never silently falls back to a claimed AI result or edits the image.

## What is implemented

- Native GIMP curves, color balance, and hue/saturation, with installed procedure-schema discovery.
- A controller that alone dispatches allowlisted edits. No HTTP exec/eval or arbitrary file-path endpoint.
- Separate viewing state, working version, branch tips, and editor status.
- Durable prepared operations, application-level request deduplication, exact plan-hash/base/revision approval, per-project process locks, and transactional history updates.
- Immutable XCF/preview artifacts, hashes, persistent document identity, native reopen verification, and full-resolution export provenance.
- One isolated GIMP process per operation. An interrupted job can write only into its own fresh staging directory; it cannot change an existing checkpoint or a replacement session. Timed-out process groups are stopped. Recovery explicitly reopens a healthy checkpoint.
- Browser UI with source/reference import, recipe review, before/after comparison, history, branching, failure messages, and export.

## Architecture

```text
Browser → authenticated loopback API → controller → private GIMP batch process
                                          │                 │
                                          └─ SQLite + XCF + native PNG previews
```

Python/FastAPI serves a small dependency-free browser UI. LibRaw/rawpy handles RAW development in a private subprocess with a timeout. Pillow encodes its RGB array as PNG and also validates/reads statistics; it never applies photo edits. The fixed worker in `lemon/gimp_worker.py` renders all subsequent edits, checkpoints, previews and exports. GIMP's existing batch interface avoids requiring a separate community MCP bridge.

The original design package is preserved in [docs/design](docs/design/README.md). [Implementation decisions](docs/IMPLEMENTATION.md) explain the smaller alpha scope and differences from that proposal.

## Verification

```sh
python -m pytest -q
ruff check lemon tests scripts
ruff format --check lemon tests scripts
node --check lemon/static/app.js

# Requires a real installed GIMP. All image artifacts stay in ignored work/.
python scripts/integration.py --workspace work/integration --evidence validation/gimp-integration.json
```

See [validation/README.md](validation/README.md) for the evidence boundary. Unit tests use an explicit fake adapter; they do not prove GIMP behavior. The real integration test creates three edits, restarts, restores S001, creates S004 on a branch, restores S003, and checks both tips and the untouched inputs. It also verifies export of a named version at full source resolution. Synthetic fixtures establish mechanics, not photo quality.

## Next milestones

- Evaluate five authorized real-photo pairs with recorded human feedback.
- Validate the optional vision planner with a configured provider and authorized real photos; improve its proposals from human feedback.
- Add a restricted agent/MCP interface, cancellation between steps, and more informative long-running progress.
- Expand color-profile support and verify Linux packaging.
- Improve history layout for large trees and measure preview latency on large projects.

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE). GIMP is a separate dependency with its own license; it is not bundled in this repository.

## RAW compatibility

The bundled `rawpy` dependency wraps LibRaw; no separate darktable installation is required. File selection accepts CR2, CR3, CRW, NEF/NRW, ARW/SRF/SR2, RAF, DNG, ORF, RW2, PEF, SRW, and additional RAW extensions. Actual camera and compression support depends on [LibRaw](https://www.libraw.org/supported-cameras), not just the extension. Unsupported or damaged files produce an import error. Only Canon CR2 has been exercised with a real user-provided file so far; other families are decoder-backed, not individually verified.

RAW import uses the decoded sensor image (which can include more edge pixels than the camera JPEG), rather than an embedded JPEG preview. The conversion is a starting rendition, not a promise to match the camera JPEG. The current grading workflow is 8-bit sRGB; it is not a high-bit-depth RAW editor. RAW previews appear after import. Existing sidecars and user editor presets are not read.
