# Tasks

## 1. Baseline and implementation

- [x] 1.1 Record pinned baseline with project-local temp and true exit; D1 baseline is 53/61, exit 1.
- [x] 1.2 Prove the Git ceiling delta, implement per-case isolation and verify copy/Git/dirty preview tests (D1).
- [x] 1.3 Correct descriptor directory construction and verify all dump-validate positive and negative cases (D3).
- [x] 1.4 Register explicit Windows prerequisites, add deterministic rollback and Linux symlink tests; verify exit codes, bytes, recovery evidence and distinct skips (D2).

## 2. Verification and delivery

- [x] 2.1 Run two sequential complete suites after the last code edit; save stdout/stderr/exits and compare PASS/SKIP sets (D3).
- [x] 2.2 Run cf-edit smoke proving real validator output and nonzero failure propagation, structural validation and source BOM/EOL comparison (D3).
- [x] 2.3 Review final diff for correctness, negative cases, security boundaries and compatibility; resolve any blockers and reverify (D3).
- [x] 2.4 Commit locally, prove main/user files unchanged, write complete requested report and reconcile D1-D4 against evidence (D4).

## Verification evidence

Code state: `c953f1c08c7271c677d289cd6c86184b0ac96693`. Evidence root: `/home/l7777/Проекты/ai_rules_1c/.scratch/metadata-linux-evidence-20261026`.

- D1 passed: baseline 53 PASS / 8 FAIL, exit 1; changing only Git ceiling gives 55 PASS / 6 FAIL, exit 1. Exactly the copy-backend and non-Git cases change status. Focused preview group 8/8 and both final full runs pass.
- D2 passed for Linux scope: two explicitly reasoned Windows-native skips, plus real Unix symlink refusal exit 2 and deterministic publish/restore faults exit 1 with recovery bytes and both paths verified. Native FileShare probe demonstrates rename succeeds on Linux with a held Read-sharing handle.
- D3 partially passed, structural gate FAILED: full runs final-1 and final-2 both 62 PASS / 2 SKIP / 0 FAIL, exits 0 and 0, identical case sets and code patches. Standalone cf-edit smoke and the new full-suite regression prove validator output and exit 1 propagation; NoValidate remains explicit. BOM/EOL and ParseFile checks pass. Final scoped diff review has no blocking findings.
- D3 residual: validate-rules exits 1 on both pristine 84d2d54f and final tree, with the same unrelated qa-testclient.ps1 missing-BOM error; standards-body checks are unavailable in both. Do not call this gate passed or waived. No archive until its disposition is separately authorized/resolved. Windows execution is unverified, not passed.
- D4 passed: local code commit above; main HEAD/status/tracked diff and all preexisting untracked hashes outside .scratch unchanged before adding the sole requested report. Full report: [metadata-linux-regression-20261026.md](</home/l7777/Проекты/ai_rules_1c/docs/metadata-linux-regression-20261026.md>). No publication, deployment, runtime mutation or nested delegation.

## 3. Deferred repository-wide gate

- [ ] 3.1 Resolve the preexisting QA-script BOM failure in a separately authorized task and re-evaluate archive readiness; no changes to that unrelated file in this repair.

## Context sources

Pinned source, both baseline logs, two full final logs, direct host experiments and authorized handoff. No delegation or live-system actions.
