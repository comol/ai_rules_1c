# Design

## Context

At the pinned baseline the runner produces 53/61 PASS and eight failures. A direct PowerShell experiment shows untyped null converts to an empty extension, retaining a trailing dot. Git discovery reaches the dirty containing repository. Windows FileShare.Read is not a portable rename blocker; cmd.exe junction creation is Windows-only.

## Goals / Non-Goals

Goals: fix only proven host failures; retain precise negative checks and evidence.
Non-goals: change metadata models, install-files-update Windows launch contract, production deletion logic or runtime; use actual infobases; broaden the upstream synchronization task.

## Decisions

- Use explicit parent + filename-without-extension for the subsystem payload directory. This avoids PowerShell's null-to-string binding and Windows trailing-dot normalization, rather than trimming arbitrary path text.
- Set a Git discovery ceiling at each generated case root for that case and its child processes, restoring the prior environment in finally. Repositories created below it remain discoverable. Avoid /tmp and altering the production wrapper's Git detection.
- Keep native Windows sharing and junction cases unchanged in their bodies, with platform prerequisites registered as skip reasons. Add a separate Linux symlink case.
- Add a test-only driver that shadows publish Move-Item and root-restore Copy-Item, throwing distinct deterministic faults while forwarding other calls to the real cmdlets. Execute the unchanged production remove-form script. Assert both faults, exit, original backup hash, recovery paths and restored payload bytes. No injectable production option, permissions race or weakened expectation.
- Preserve encoding and source line endings; keep the runner ASCII for Windows PowerShell 5.1.
- The required cf-edit smoke proved that its unconditional final exit 0 masks a real cf-validate exit 1. Exit immediately on a nonzero child exit, keeping host selection and explicit NoValidate behavior unchanged. Add a real-validator regression, not just a launch-banner assertion.
- Keep per-tool stdout/stderr and invocation/exit JSON outside fixture trees when KeepWorkDir is requested, so evidence does not affect byte snapshots.

## Risks / Trade-offs

- Windows runtime unavailable → retain original native tests and old host selection; report unverified Windows execution explicitly.
- Injected faults do not prove a particular Linux kernel failure → identify them as deterministic transaction tests, separately prove why the former FileShare assumption fails.
- Historical 55/61 log is unavailable → reproduce only the Git-context delta now; do not retrospectively certify historical results.

## Migration Plan

Local worktree branch only. No deployment. Rollback is simply not adopting the isolated commits; preserve evidence and existing worktrees until user acceptance.

## Context sources

Pinned source, baseline logs, handoff and direct ChangeExtension probe. This design concerns PowerShell/filesystem test behavior, not new 1C platform claims.
