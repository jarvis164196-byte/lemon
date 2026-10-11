# Validation evidence

Evidence recorded during the initial Lemon implementation on October 11, 2026. These layers are intentionally separate.

| Layer | Result | Boundary |
|---|---|---|
| Controller, API, planner, and adapter tests | 25 tests passed (`pytest -q`) | Most controller tests use an explicit fake adapter; provider calls are mocked. |
| Python lint/format and JavaScript syntax | Passed | Static checks do not establish runtime photo quality. |
| Real GIMP 3.2.4 on macOS arm64 | Passed; see `gimp-integration.json` | Synthetic gradients only. Input 1600×1200; preview 1400×1050; export retains 1600×1200. |
| Browser walkthrough | Two-file import, original checkpoint, recipe approval, three committed edits, version browsing, before/after comparison | Real local backend and GIMP. Browser observations are not human photo evaluation. |
| Optional OpenAI vision | Consent scope/revocation, fixed-provider request contract, rejected invalid model output, sanitized errors tested | No live provider request was made. API-key presence alone does not prove account/model access. |
| Human photo evaluation | **Not performed** | Requires authorized real photo pairs and subjective user judgments. |

The native test verifies root save/reopen, three adjustments, changed output pixels, duplicate-request handling, fresh controller/adapter loading persisted state, restoration of S001, branching to S004, restoration of S003, preserved branch tips, selected-version export, and unchanged input hashes. Each GIMP process exits before the next operation. No persistent runtime image IDs are reused.

Unit tests cover failed save, interrupted prepared-operation recovery, corrupted checkpoints, stale and modified plans, concurrent approvals, scoped paths, explicit-version export, network authentication and Origin/Host restrictions, input compatibility, planner limits, isolated-process timeout, and the optional vision boundary.

`design-documentation-checks.json` is copied from the supplied design package. Its old hashes and checks describe that package, **not this implementation**. The imported documents remain historical specifications.

The original native browser restore confirmation stalled the in-app test tab. It was replaced with an accessible in-page dialog. The new dialog passes static checks but its final browser interaction check remains pending until that old prompt is dismissed. Backend restoration and export passed the independent real-GIMP checks.

## Reproduce

```sh
python -m pytest -q
ruff check lemon tests scripts
ruff format --check lemon tests scripts
node --check lemon/static/app.js
python scripts/integration.py --workspace work/integration --evidence validation/gimp-integration.json
```

The native command requires GIMP 3 and may take a few minutes because every operation starts an isolated editor. Test assets and logs remain in ignored `work/`; the JSON report contains synthetic-image hashes, discovered schemas, real editor versions, and per-operation verification timings. Do not replace these fixtures with private photos and publish their resulting data without reviewing it.

## Import feedback follow-up

Browser verification on October 11, 2026 confirmed that an unsupported grayscale fixture now produces an inline error directly below the import button, retaining both file selections and re-enabling the form. Replacing it with a supported synthetic RGB source successfully created a verified S000 through the running GIMP backend. Pending imports show “Working…” and checkpoint progress beside the button. All 25 existing tests and JavaScript syntax checks passed. This does not establish the cause of the reported failure with the user’s private photo pair.

## Camera orientation and real-photo test

On October 11, 2026, a user-authorized local photo pair completed upright import, three committed GIMP edits at 55% strength, and a 3648×5472 PNG export. Source and reference SHA-256 values were unchanged; the final preview differed from the original preview. Private photographs, hashes, filenames, and project records are excluded from this repository. This verifies mechanics on a real pair, not human acceptance of the aesthetic match.

All eight EXIF transforms passed native GIMP 3.2.4 checks using asymmetric synthetic corner-color PNG fixtures compared against an in-memory orientation oracle. Reproduce with `python scripts/check_orientation.py --workspace work/orientation-test`. Unit tests now total 33 passing tests.

## RAW import extension

On October 11, 2026, an authorized Canon CR2 completed multipart upload through the authenticated running API, LibRaw development, GIMP root save/reopen, three committed edits, and a 3670×5496 PNG export. The original RAW hash remained unchanged and matched the preserved RAW in export provenance. The larger dimensions than the camera JPEG reflect decoded sensor-edge pixels. Decoder: rawpy 0.27.1 / LibRaw 0.22.1. No other RAW family has been exercised with a real fixture. Private originals and outputs remain outside this repository.

38 automated tests pass. New coverage includes source/reference RAW routing and preserved provenance (mocked conversion), rejection of a malformed RAW by the real decoder, no published project on conversion failure, preserved RAW tamper detection, and timeout process-group termination/reaping.

## Export and retouch verification

GIMP 3.2.4 native tests on synthetic textures passed: all three retouch tools changed pixels inside an off-center selected region while preserving a distant outside region exactly; previews left the working pointer and history unchanged, and explicit acceptance committed a version. JPEG qualities 35/95 at 400×300 produced 21,047/92,853 bytes. PNG compression 0/9 produced 361,375/211,690 bytes with identical decoded pixels. Reproduce using `python scripts/check_features.py --workspace work/features`. Installed schemas are in `gimp-feature-schema.json`.

44 automated tests pass, including aspect-ratio/no-upscale checks, option bounds, correct JPEG download headers, explicit preview approval, idempotent acceptance, stale/tampered preview rejection, and failed-preview isolation. Browser export of the real RAW-based version at JPEG quality 80 and 1080-pixel long edge completed at 721×1080. Browser selected-area smoothing preview is checked separately from human aesthetic evaluation.
