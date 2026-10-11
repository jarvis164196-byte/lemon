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
