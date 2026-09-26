---
description: Review the current diff or selected files for unnecessary complexity; report evidence-backed simplifications without applying fixes
argumentHint: "[<file-or-directory> ...]"
---

# /ponytail-review — review for unnecessary complexity

Adapted from [DietrichGebert/ponytail, v4.10.0](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/skills/ponytail-review/SKILL.md) (MIT; notice below).
One-shot analysis, explicitly invoked by the user. Find unnecessary complexity and propose the smallest correct replacement. Do not edit source files, settings or Git state, and do not enable a persistent Ponytail mode.

## Scope

- Explicit files / directories or an attached diff take precedence. Honour quoted paths; bound directory inspection to that subtree. Read current source around each candidate and its relevant usages before reporting it.
- With no explicit scope, review the final working-tree changes against `HEAD` (staged and unstaged tracked changes together). With no first commit, inspect the staged and unstaged diffs and reconcile overlapping changes against current files.
- Untracked files are outside the default diff: disclose that boundary and include them only when explicitly selected. Do not silently expand to a whole-repository audit.
- No diff and no explicit scope: report that there are no changes to review and explain that paths can be supplied. If Git or the requested source is unavailable, state the gap and request the missing diff / paths; never claim a review was completed.

## Review

1. Follow `AGENTS.md`. For BSL / metadata, load `content/rules/coding-standards.md` and `content/rules/tooling-playbooks.md → Code Review`. Discover usages through `content/rules/mcp-first-search.md`; direct reads of selected files remain allowed. Load the MCP router and operation skills before their tools, as required by `AGENTS.md`.
2. Look for these candidates; the tag describes the proposed simplification, not a defect severity:
   - `delete:` demonstrably unused code or flexibility; no replacement needed.
   - `stdlib:` custom implementation covered by the language's standard library.
   - `native:` custom code or a dependency covered by a verified platform mechanism, existing project code or БСП API.
   - `yagni:` an abstraction or configuration point with no demonstrated current requirement.
   - `shrink:` equivalent logic with less duplication or indirection and equal or better readability.
3. Establish why the existing structure is unnecessary and why the replacement preserves requirements and behaviour. A single implementation, one caller or a longer diff alone is not evidence. Check relevant contracts and indirect usages before suggesting deletion; unresolved reachability belongs in an evidence gap, not a confirmed finding. For 1C replacements, verify applicable API / version facts and template reuse through the tools required by `AGENTS.md` before naming a concrete replacement.
4. Preserve validation, error handling, security, data integrity, accessibility, public API documentation and project gates. Never suggest removing them merely to save lines. Existing module boundaries and conventions take precedence over code golf.
5. Keep this pass focused on complexity. Note a concrete correctness, security or performance problem separately with its evidence and route it to ordinary review; it must not disappear into a simplification score. This command neither approves release readiness nor replaces mandatory testing / review. Subsequent implementation follows normal triage and verification.

The parent can perform this review directly. Delegation, if useful, follows `content/rules/subagents.md`, including the reviewer-model gate; invoking this command does not select a reviewer model.

## Output

Reply in Russian. State the reviewed scope and any coverage limits. List only supported findings, ordered by maintenance benefit and risk, using this compact format (expand when needed to preserve evidence):

`<file>:<line> — <tag> <что избыточно>; <доказательство>; <чем заменить>; <условие / необходимая проверка>.`

Finish with the finding count and unresolved evidence gaps. Estimate removable lines or dependencies only when the proposed replacements make that count defensible; label it an estimate, never measured savings. Do not invent token, cost or speed gains. With no findings say «Подтвержденной избыточной сложности в проверенной области не найдено», retaining any coverage limits; this is not a correctness verdict. Preserve applicable evidence lines from `content/rules/verification-delivery.md`.

<!--
Upstream licence notice; retain in distributed copies of this adapted command.

MIT License

Copyright (c) 2026 DietrichGebert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->
