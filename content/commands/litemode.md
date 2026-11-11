---
description: Compatibility alias for /sdlc profile names; UI testing is controlled separately by /uitests
userOnly: true
argumentHint: "[on|off|full|standard|lite|status]"
---

# /litemode — compatibility alias for /sdlc

Use the named SDLC QA profiles from `content/commands/sdlc.md`. Load that command and `content/rules/verification-policy.md` before acting. Trim whitespace and compare case-insensitively; preserve these argument mappings:

- Empty, `on`, or `lite` → `/sdlc lite`, preserving `UI_TESTING`.
- `standard` → `/sdlc standard`, preserving `UI_TESTING`.
- `full` → `/sdlc full`, preserving `UI_TESTING`.
- `status` → `/sdlc status`, with no changes.
- `off` → `/sdlc standard`, preserving `UI_TESTING`.
- Any other argument → list accepted arguments and make no changes.

**UI independence:** the former implicit UI disable/restore is retired. Never change `UI_TESTING` here, including when an older `/litemode` run left it `off`. Explicit control is `/uitests essential|on|manual|off|status` (`content/commands/uitests.md`). Apply the same persistence / session-only rules as `/sdlc` and confirm the profile and preserved UI state.

Use the named profile in confirmations and point to `/sdlc lite|standard|full|status` as the primary interface. `off` means the **Стандартный** profile, never a disabled SDLC or skipped mandatory checks. This wrapper edits only the keys allowed by `/sdlc` and does not redefine its gates or budgets.
