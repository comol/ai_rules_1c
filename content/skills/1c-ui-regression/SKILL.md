---
name: 1c-ui-regression
description: "Create or maintain reusable UI regression tests for a 1C web client, runnable without an AI agent. Optional: choose when repeatable coverage is useful; ordinary interactive UI checks remain with 1c-tester."
argument-hint: "<feature or existing UI test>"
---

# 1c-ui-regression — reusable UI tests

Turn a relevant acceptance scenario into a saved, executable test with deterministic assertions. The model decides whether this is worth doing for the current task: recurring workflows, a reproduced UI regression or a requested automated suite are good candidates. Do not create a suite for every UI edit. Prefer extending the project's existing tests over introducing another framework.

## Scope and execution

Authoring test files and running a browser are separate operations. The skill can be selected implicitly; selection neither changes `UI_TESTING` nor authorizes deployment, writes to an infobase or installation of a new service.

- Read `content/rules/dev-standards-env.md → UI_TESTING` for the target and effective UI policy. `manual` permits a run on an explicit UI-test request; `auto` permits applicable runs with a configured publication; `essential` permits only the cases covering the important new or changed behaviour, never a regression sweep; `off` prevents execution. For thin-client scenarios, including saved pytest tests, use `content/skills/1c-qa-testing/SKILL.md`. Do not enable UI tests as a side effect of selecting this skill.
- Use an authorized dev/test infobase with the current feature loaded. Resolve the main configuration / extension and source-to-target match through `content/rules/extension-workspace.md`. Missing runtime prerequisites leave execution unverified; useful local authoring may continue.
- Interactive discovery uses `content/rules/ui-testing-tools.md` and `content/rules/web-client-driving.md`. A saved suite uses its verified runner and the applicable `TOOL_BROWSER` / driver policies. Do not use it to bypass an `off` or unavailable `required` provider. A reusable Playwright runner does not require replacing a project's interactive driver.
- Read connection values from the project's `.dev.env` through an existing loader or explicit runtime environment mapping. Never copy URLs from another project or embed credentials / saved authentication state in a committed test.
- A suite that brings up its own stand — contexts as roles, a reference `.dt` with a manifest and delta load, a `down` step that frees licences — follows [regression-stand.md](docs/regression-stand.md).

## Build the smallest useful suite

1. **Specify the observation.** Use the task's acceptance criteria or an existing OpenSpec scenario. Record initial state, user action and expected visible result before coding. Include the negative or boundary case that exposed the regression. No visual effect to assert means choose a business-logic check; do not change the product just to make a test possible.
2. **Choose the runner.** Inspect the existing package manifest, lockfile, test configuration and helpers. Reuse them. If none exists and a saved UI suite is useful, create a minimal Playwright Test setup in the target project, merging existing configuration instead of overwriting it. Check the installed version and its official documentation at <https://playwright.dev/docs/intro> before relying on APIs. Retain a lockfile and document the setup/run command. Run the 1C web client headed (`headless: false`): headless runs usually render only the login page. Do not auto-install services or browsers outside the authorized task.
3. **Establish real controls.** Use a current authorized browser observation and, when relevant, `content/skills/1c-form-inspect/SKILL.md`. Form metadata identifies logical elements; it does not prove their DOM selectors. Prefer observed accessible roles/names, scoped to the intended form/grid. Do not save ephemeral snapshot refs or generated form-instance IDs as reusable locators. If selectors cannot be verified, report that limit instead of emitting a runnable-looking stub or a passing empty test.
4. **Write independent cases.** Save tests in the project's established directory (otherwise `tests/ui/`). Wait for the relevant UI state, not a fixed sleep. Follow the verified input behavior from `web-client-driving.md`, then assert the value retained after leaving the field. Reuse existing login and data helpers. Each case owns its data or starts from a documented stable fixture; test order must not carry business state between cases.
5. **Make failures machine-detectable.** Use runner assertions and retain its nonzero exit code. Missing controls, setup failures, timeouts and zero executed cases cannot produce a pass. Emit the runner's JSON/JUnit report, or bounded JSONL observations alongside it, with case ID and expected/actual values. Capture permitted failure evidence without secrets. Logs complement assertions; an AI reading a log is not the test oracle.
6. **Run when allowed.** Execute the focused suite against the verified target. If test actions write/post/delete, establish the authorized test-data and cleanup scope first; cleanup can remove only artifacts owned by this run. Deployment, if needed and authorized, stays with `/update1cbase` or `/deploy-and-test`, never a hidden fixture hook. Preserve failure status even if cleanup also fails.

## Completion

The deliverable names the test files, covered acceptance criteria, setup/run command, required target and actual result. Distinguish `authored`, `executed: passed`, `executed: failed` and `blocked/unverified`. A suite that only loads or lists its cases has not verified the feature. State the checked source / deployed state and report path for a live run.

Fix an in-scope defect through normal project gates. Re-run affected cases only after a relevant source, test or environment change; do not weaken an expected result to make the test green. Repeated deploy/fix cycles remain the explicitly requested `/test-fix-loop` workflow.

For reusable server-side checks use `content/skills/1c-business-tests/SKILL.md`; neither skill replaces applicable static validators or the existing focused Gate 3a check.
