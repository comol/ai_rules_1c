# Changes — active proposals

This folder contains in-flight change proposals. Each change is isolated in
its own sub-folder.

## Layout of a single change

```
changes/<change-name>/
├── proposal.md   # why this change exists, scope, approach
├── design.md     # technical decisions and architecture (optional)
├── tasks.md      # implementation checklist with checkboxes
└── specs/        # delta specs, mirroring the layout of ../specs/
    └── <domain>/
        └── spec.md
```

## Delta spec format

Delta specs use three top-level sections to describe changes relative to the
current state of `../specs/<domain>/spec.md`:

```markdown
# Delta for <domain>

## ADDED Requirements

### Requirement: <name>
...

## MODIFIED Requirements

### Requirement: <name>
... (replaces existing requirement of the same name)

## REMOVED Requirements

### Requirement: <name>
(why it is being removed)
```

When the change is archived (`/opsx:archive` or `openspec archive`):

- ADDED requirements are appended to the main spec.
- MODIFIED requirements replace the existing version.
- REMOVED requirements are deleted from the main spec.

The change folder is then moved to `archive/<YYYY-MM-DD>-<change-name>/`.

## Standard artifacts

| File | Purpose |
|------|---------|
| `proposal.md` | The "why" and "what" — captures intent, scope, and approach. |
| `specs/` | Delta specs (ADDED / MODIFIED / REMOVED requirements). |
| `design.md` | The "how" — technical approach and architecture decisions. Optional but recommended for non-trivial changes. |
| `tasks.md` | Implementation, testing, review and DoD reconciliation tasks with `- [ ]` checkboxes and evidence. |

## Definition of Done for full-cycle changes

`proposal.md` contains `## Definition of Done`: criterion IDs linked to
delta requirements/scenarios, applicable gates, acceptance/regression tests,
and final review. Each delta requirement carries its verification method and
expected outcome inside the requirement block (see the
[spec template](../specs/README.md)). Specify required test data/environment.

Map every criterion to a verification task, for example:

```markdown
## 2. Verification and completion
- [ ] 2.1 Run acceptance and regression scenarios for DoD-1; compare actual results with the linked expectations.
- [ ] 2.2 Run applicable validation gates on the final artifacts (DoD-2).
- [ ] 2.3 Review requirements, correctness, regressions, security and test coverage; resolve blocking findings (DoD-3).
- [ ] 2.4 Reconcile all DoD criteria with current evidence before declaring apply complete.

## Verification evidence
- DoD-1: <passed / failed / blocked-unverified / waived by user>; <artifact state>; <check, expected vs actual outcome, report/log>.
```

Testing and review are required unless explicitly waived by the user. Record
the waiver's source, scope and criterion IDs in both DoD and the task; never
label it a passed check. Missing tools, an unavailable test environment or
`VERIFICATION_DEPTH=lite` do not waive either obligation. Browser testing and
reviewer subagents retain their separate execution policies.

`apply` continues through verification and fixes; all checked implementation
tasks or CLI `all_done` do not prove DoD. Failed, stale or unavailable required
evidence leaves the change incomplete. Archive readiness uses the same DoD
evidence. Details: [`sdd-integrations.md`](../../content/rules/sdd-integrations.md).

See the [parent `README.md`](../README.md) for the full workflow and the
recommended slash commands.
