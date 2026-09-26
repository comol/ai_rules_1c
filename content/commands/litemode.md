---
description: Compatibility alias for /sdlc profiles; preserves legacy on/off behaviour and UI-testing restoration on off
userOnly: true
argumentHint: "[on|off|full|standard|lite|status]"
---

# /litemode — compatibility alias for /sdlc

Use the named SDLC QA profiles from `content/commands/sdlc.md`. Load that command and `content/rules/verification-policy.md` before acting. Trim whitespace and compare case-insensitively; preserve the legacy mappings:

- Empty, `on`, or `lite` → `/sdlc lite` (including `UI_TESTING=off`).
- `standard` → `/sdlc standard`, preserving `UI_TESTING`.
- `full` → `/sdlc full`, preserving `UI_TESTING`.
- `status` → `/sdlc status`, with no changes.
- `off` → `/sdlc standard`, plus the legacy UI restore below.
- Any other argument → list accepted arguments and make no changes.

**Legacy `off` restore:** if the effective `UI_TESTING` is `off`, set it to `manual`; otherwise preserve it. Do not claim to restore the pre-lite value: a former `auto` value is unknown and must be selected separately. Apply the same persistence / session-only rules as `/sdlc` and issue one confirmation with the final profile and UI state.

Use the named profile in confirmations and point to `/sdlc lite|standard|full|status` as the primary interface. `off` means the **Стандартный** profile, never a disabled SDLC or skipped mandatory checks. This wrapper edits only the keys allowed by `/sdlc` and does not redefine its gates or budgets.
