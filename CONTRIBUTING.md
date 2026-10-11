# Contributing to Lemon

Start with the README and AGENTS.md. Open an issue describing the user-visible problem before substantial changes.

Install the development dependencies and run the unit tests and lint checks listed in the README. Changes to the GIMP worker also need real GIMP integration evidence. Keep controller fake-adapter tests, browser observations, native integration, and human photo evaluation separate.

Never commit private photos, XCF projects, API keys, runtime logs, or local project databases. Use generated fixtures for mechanics tests and licensed/authorized photos for private human evaluation. Do not claim that a histogram distance proves photo quality.

Preserve the single-writer controller, exact approval binding, immutable checkpoints, and branch recovery. Do not expose general execution tools or substitute another renderer for GIMP.
