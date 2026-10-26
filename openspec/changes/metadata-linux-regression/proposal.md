# Proposal

## Why

The Linux metadata regression baseline at `84d2d54f4dcc58a0eb33414c2fd871dcc48d8a90` has eight reproducible failures. A nested Git checkout and Windows-specific test assumptions obscure a real descriptor-path defect.

## What Changes

- Correct extension removal without a trailing dot in the dump validator.
- Preserve the actual cf-validate failure exit in cf-edit; the required smoke reproduced a validator exit 1 masked by the caller's exit 0.
- Isolate test Git discovery within the generated fixture root.
- Identify Windows-only native fault/junction tests explicitly; add deterministic rollback-failure coverage and Linux symlink containment coverage without production injection hooks.
- Preserve negative assertions, source encoding, Windows host selection and local-only execution.

## Capabilities

### New Capabilities

- `portable-metadata-regression`: reproducible host-aware offline regression evidence.

### Modified Capabilities

None. Existing tool contracts are retained.

## Impact

Only the dump-validator implementation, cf-edit exit propagation, regression runner, and this isolated change. No main checkout implementation changes, installations, runtime, infobases, publication or delegation. Test fixtures are copies under the authorized evidence directory. No new dependency.

## Definition of Done

- [x] D1: portable-metadata-regression / Nested fixture isolation — reproduce baseline, then prove Git/non-Git paths independently.
- [x] D2: portable-metadata-regression / Honest host coverage — preserve Windows cases with explicit skip reasons on Linux; test Linux symlink refusal and rollback quarantine preservation with real exits and bytes.
- [ ] D3: portable-metadata-regression / Stable acceptance — two sequential full Linux runs after the last code edit, zero failures, identical explained coverage; separate cf-edit validator success/failure smoke, structural validation, BOM/EOL proof and final self-review without blockers.
- [x] D4: portable-metadata-regression / Local evidence — local commit and complete report with source SHA, stdout/stderr/exits, unchanged main/user-file proof and explicit Windows runtime limitation.

D3 is not fully green: the requested Linux runs, smoke, encoding checks and scoped review passed; the overall structural validator still fails on the same preexisting QA-script BOM defect reproduced at the pristine baseline. See tasks for exact evidence and the deferred, out-of-scope repository gate. This change is not declared archive-ready.

## Context sources

User handoff dated 2026-10-26; local baseline stdout/stderr/exit; existing runner and dump-validator source; direct PowerShell ChangeExtension experiment. These are host/tooling requirements, not new 1C platform or metadata-model claims. knowledge_1c returned no matching facts.
