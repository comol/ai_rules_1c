# Portable metadata regression

## Purpose

Provide trustworthy offline regression results across supported hosts, including fixtures created inside another Git checkout.

## ADDED Requirements

### Requirement: Nested fixture isolation

The regression runner SHALL keep non-Git fixtures outside ancestor repository discovery while retaining detection of repositories created within a test case.

**Definition of Done (D1):** Baseline failures are saved; both copy-backend and Git-backend preview tests pass under a project-local temp directory without weakening dirty-tree refusal or exit propagation.

#### Scenario: Temp root inside a checkout
- **WHEN** the full runner uses a temp directory inside a dirty parent repository
- **THEN** copy preview restores fixture bytes, clean Git preview restores its own tree, and dirty Git preview is refused without losing the dirty bytes

### Requirement: Honest host coverage

The runner MUST distinguish unsupported native host tests from passes and MUST retain Linux containment and rollback-failure checks.

**Definition of Done (D2):** Windows-only tests have explicit reasons on Linux; a real Linux directory symlink is refused with exit 2 and unchanged victim bytes; deterministic publish plus restore faults produce exit 1, a surviving original backup, recovery paths and restored form payloads.

#### Scenario: Linux native prerequisites
- **WHEN** the suite runs without Windows junction or sharing-violation semantics
- **THEN** those native cases are reported as SKIP, not PASS, while separate Linux symlink and deterministic rollback cases execute

### Requirement: Stable acceptance

Acceptance MUST preserve existing valid and invalid fixture expectations and require two complete sequential runs on the final implementation state.

**Definition of Done (D3):** Both runs exit 0 with identical PASS/SKIP names and no FAIL; cf-edit smoke proves validator output and nonzero propagation; structural checks and encoding inspection pass; self-review finds no unresolved blocker.

#### Scenario: Nested descriptor validation
- **WHEN** healthy or deliberately invalid nested fixture descriptors are validated
- **THEN** healthy input is accepted and malformed/version/missing-reference cases retain their expected findings without false trailing-dot paths

### Requirement: Local evidence

Evidence MUST identify tested source, commands, environment, outputs and true process exit codes, without claiming unexecuted Windows or live-platform verification.

**Definition of Done (D4):** Local commit SHA and complete report include evidence links, unchanged main/user-file proof and explicit limits; no publication or live-environment mutation occurs.

#### Scenario: Delivery
- **WHEN** the isolated repair is delivered
- **THEN** the report distinguishes observed results from historical unknowns and leaves all evidence available for acceptance

## Context sources

User handoff, observed offline baseline, existing regression expectations and direct host-path experiment; no new 1C API or metadata shape is specified.
