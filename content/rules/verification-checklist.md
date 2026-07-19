---
description: Router for 1C verification — directs triage, hard gates, and delivery checks to focused companion rules
alwaysApply: false
category: quality
---

# Verification Checklist — Router

This file is a compatibility router. It contains no duplicated normative gate text. Load only the companion required for the current stage:

| Stage / need | Canonical rule |
|---|---|
| `VERIFICATION_DEPTH`, quick-fix eligibility, promotion triggers, quick-fix gate | [`verification-policy.md`](verification-policy.md) |
| Evidence reuse, syntax / logic / style validators, impact analysis, metadata XML | [`verification-gates.md`](verification-gates.md) |
| Reproduction, plan adherence, optional review / UI test, delivery report | [`verification-delivery.md`](verification-delivery.md) |

Existing references to `verification-checklist.md → <section>` remain valid through the compatibility headings below. The linked companion is authoritative.

## Gate execution and evidence reuse

Canonical content: [`verification-gates.md`](verification-gates.md).

## Verification depth levels (`VERIFICATION_DEPTH`)

Canonical content: [`verification-policy.md`](verification-policy.md).

## Triage details — quick-fix eligibility and promotion triggers

Canonical content: [`verification-policy.md`](verification-policy.md).

## Quick-fix gate

Canonical content: [`verification-policy.md`](verification-policy.md).

## Hard gates — run on every full-cycle change

Canonical content: [`verification-gates.md`](verification-gates.md).

### Gate 1 — Syntax (`syntaxcheck`)

See [`verification-gates.md`](verification-gates.md).

### Gate 2 — Logic & performance (`check_1c_code`)

See [`verification-gates.md`](verification-gates.md).

### Gate 3 — Style & ITS compliance (`review_1c_code`)

See [`verification-gates.md`](verification-gates.md).

### Graceful degradation for Gates 1–3 — when a validator is not exposed

See [`verification-gates.md`](verification-gates.md).

### Gate 4 — Impact analysis (only when public surface changed)

See [`verification-gates.md`](verification-gates.md).

### Gate 5 — Metadata XML validation (only when XML was edited)

See [`verification-gates.md`](verification-gates.md).

## Soft gates — run when applicable

Canonical content: [`verification-delivery.md`](verification-delivery.md).

### Soft gate A — Reproduction case (debug tasks only)

See [`verification-delivery.md`](verification-delivery.md).

### Soft gate B — Plan adherence (any change with a written plan)

See [`verification-delivery.md`](verification-delivery.md).

### Soft gate C — User-explicit code review (only when user asks)

See [`verification-delivery.md`](verification-delivery.md).

### Soft gate D — UI testing (configurable, off by default)

See [`verification-delivery.md`](verification-delivery.md).

## Delivery summary — what the user sees

Canonical content: [`verification-delivery.md`](verification-delivery.md).

## Anti-patterns

Canonical content: [`verification-delivery.md`](verification-delivery.md).
