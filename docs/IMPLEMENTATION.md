# Lemon alpha: implementation decisions

The user selected **Lemon** as the product and repository name and chose a two-photo reference-grading workflow as the first milestone. The supplied documents are prior design material, not evidence of completed implementation. Their earlier product names and proposed tools are historical context.

## Deliberate scope

The alpha implements a complete local reference-analysis → approval → native edit → verified checkpoint → restore/branch/export loop. It also implements an optional OpenAI vision planner behind explicit project-scoped consent and server-side API-key configuration. Without that configuration the UI says that cloud AI is not configured. No images were sent to a provider during development. A single-prompt AI proposal composer is implemented; conversational memory, an external agent skill, and an MCP server remain future work.

This is an engineering alpha, not completion of the design package's M4 release gate. In particular, human real-photo evaluation is missing. The planning algorithm is a bounded heuristic, not semantic understanding or a style-quality metric.

## Native adapter

A trusted fixed batch worker uses GIMP's installed Python introspection API. Schema discovery records procedure names, property types, method signatures, and the actual GIMP version. Every root, edit, restore, and export runs with `--new-instance`, a private profile, and dedicated job/output paths. A process group is killed and reaped on timeout. A previously interrupted worker has no path to a later worker's output or document, even if the controller itself crashes. Checkpoints are opened as inputs and never used as save destinations.

Reference matching uses three validated operations; selected-area retouching has its own bounded allowlist. The backend never accepts Python code, procedure names outside its allowlist, arbitrary filesystem paths, or user-controlled command fragments. The adapter itself invokes a fixed trusted worker with `runpy`; this is an internal implementation mechanism, not an exposed agent capability. This process separation is not an OS security sandbox against a compromised native plugin.

GIMP 3.2 deprecates the drawable convenience adjustment methods in favor of filters, but retains them. The alpha uses their verified installed behavior; a future filter-based adapter needs its own save/reopen evidence before replacing it. This alpha saves complete XCF versions rather than promising re-editable effects.

## Persistence and approval

A project's SQLite database holds a versioned JSON state in one row, updated with a transaction and FULL synchronous mode. This favors auditable atomic updates over premature relational schema complexity. A process-level file lock serializes writers. Each version's parent, artifacts, operation, hashes, and environment are immutable after publication. A manifest records input identity and hashes.

A plan binds its original base, revision, exact step parameters, strength, and reference hash. The browser's approval call identifies the exact plan hash and step. The controller persists approval and a prepared operation before executing. Group approval is serial individual approval/execution of the displayed remaining steps. Restoring any version increments the revision and invalidates older approvals.

On failure, no node/ref updates are committed. Startup marks prepared operations interrupted and requires recovery. Orphan files remain available for inspection; directory presence alone never creates history. A damaged checkpoint remains in history as unavailable. Reads cannot change the editor or the working base. The selected preview and pinned comparison live only in the frontend; the working version and branch tips are durable.

The UI presents a parent-linked version list rather than a draggable node canvas. Per-version details show the exact parent. Historical selection has no editing side effect.

## Planner limitations

The planner samples pixels in memory, estimates value quantiles, and blends a monotonic mapping toward the reference. Tonal movement is capped at 18% before strength blending. Midtone color balance uses median chromatic offsets, capped at ±20; saturation movement is capped at ±30. These are global edits and cannot infer scene geometry, light direction, masks, subject semantics, or ideal skin tones. Strength is a recipe-generation parameter, not a post-render opacity effect.

## Supported platforms and data

The tested environment is macOS arm64, Python 3.14, GIMP 3.2.4. POSIX locks and process groups preclude Windows support in this release. Linux paths are supported but real integration evidence is pending. Each process's private runtime directory and logs are retained; this consumes disk and is documented, not silently garbage-collected. HTTP services bind to exact IPv4 loopback with authentication, same-origin checks, no CORS, and a restrictive content security policy.

Inputs are limited to 8-bit sRGB images. Valid EXIF orientation tags (1–8) are applied once through native GIMP rotation/flip operations on import, with upright dimensions recorded for checkpoint verification. Untagged inputs are explicitly interpreted as sRGB; an embedded profile must identify sRGB. This is a conservative compatibility check, not a full color-management certification. Future profile support must verify conversion behavior through GIMP.

## Optional vision boundary

The model returns a structured recipe, not edited pixels or executable tools. The controller rejects invalid/non-monotonic curves and out-of-range parameters, blends the approved strength, and converts the recipe into the same three allowlisted GIMP operations. Consent and submission records are durable and scoped to the project/reference hash. Disabling consent blocks future requests; it cannot retract a previously submitted request.

The provider destination is fixed to OpenAI's Responses endpoint, redirects are disabled, the API key stays server-side, and requests are not automatically retried. Both image inputs are native GIMP PNG previews without private metadata. Only short edit explanations are saved, never hidden reasoning. `store: false` is set, without claiming it overrides the provider's retention policies. The API implementation follows [image inputs](https://developers.openai.com/api/docs/guides/images-vision) and [structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). The selected default model's [official capabilities](https://developers.openai.com/api/docs/models/gpt-4.1-mini) include image input and structured outputs. Model access is account-dependent and not verified by the presence of an API key.

## RAW import extension

The user expanded the original MVP scope to camera RAW. `rawpy` / LibRaw develops a private copy in a separate, timed subprocess, with camera white balance, automatic brightness, camera orientation, and sRGB output (`gamma=(2.4,12.92)`, 8 bits). Pillow only encodes this decoded array. GIMP remains responsible for all subsequent image editing and artifacts. Conversion happens before creating the managed GIMP document. Failed conversion creates no project checkpoint. Uploaded filenames supply only an allowlisted suffix; their paths are never used. The managed inputs preserve both the RAW bytes and the developed PNG, their hashes, and decoder version/settings. Both originals are integrity-checked before commits. Export provenance includes the input conversion records. Private temporary decode files are removed after import; preserved project originals are retained.

The documented [rawpy parameters](https://letmaik.github.io/rawpy/api/rawpy.Params.html) and installed rawpy 0.27.1 / LibRaw 0.22.1 were used. Compatibility is camera/compression dependent. This conversion intentionally does not add editable RAW parameters, sidecar import, HDR, or a 16-bit editing pipeline.

## Export and selected-area retouch extension

Native PNG/JPEG export schemas and three GEGL filter schemas were inspected on installed GIMP 3.2.4; see `validation/gimp-feature-schema.json`. JPEG uses explicit quality and white alpha flattening; PNG uses lossless compression 0–9. The controller resolves a bounded long edge without upscaling, verifies output dimensions, and records format/size/settings. Legacy PNG exports remain accessible.

Retouch previews use `gegl:bilateral-filter`, `gegl:gaussian-blur`, or `gegl:whirl-pinch` under a feathered elliptical selection. Parameters are bounded and allowlisted. A candidate is persisted before rendering into its own staging directory. GIMP saves and reopens the candidate checkpoint and generates its preview. No history node or working pointer changes until explicit acceptance. Acceptance requires unchanged project revision, healthy parent/input hashes, and matching candidate artifact hashes. It persists a prepared commit operation, then uses the existing immutable publish path. Duplicate acceptance returns existing history; crash uncertainty uses existing recovery behavior. Unaccepted candidates consume staging space and are retained; no automatic deletion is claimed. Reshaping is a geometric pinch, not a semantic body model.

## Prompt-directed edits and muscle volume

The agent planner shares the consent, prepared-submission, fixed-provider, and immutable-plan boundaries of vision grading. Structured output chooses a bounded grade or one normalized oval retouch; unknown actions, invalid regions, and unsupported requests cannot become native edits. Retouch proposals open the preview dialog and require explicit save. Muscle volume uses the installed GEGL whirl-pinch operation with negative pinch, bounded to 0.32 magnitude, on a feathered selection. This is localized volume reshaping, not generative anatomy. Provider contract tests are mocked; no live paid AI request has been validated.

Validation for this extension: 46 automated tests passed, including mocked muscle proposals, invalid regions/actions, unsupported requests, and consent gating. Native GIMP 3.2.4 synthetic integration passed skin, wrinkle, muscle, and pinch previews, explicit acceptance, and JPEG/PNG export. The muscle fixture changed 100,878 pixels inside/near its feathered selection with the distant region unchanged. Browser verification confirmed the composer configuration message and selectable muscle tool. This is engineering validation, not human aesthetic acceptance or a live AI trial.
