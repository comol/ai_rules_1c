---
description: Designer batch checks of a configuration or extension — `/CheckModules`, `/CheckConfig`, extension applicability, `/DumpResult` verdict, backup / rollback. Load before applying to an infobase or when MCP validators are not exposed.
alwaysApply: false
category: quality
---

# Designer Batch Checks — the Platform's Own Verdict

The gates of `verification-gates.md` (1–3) are **static**: they read source. This file covers what only the platform itself can answer against a real infobase — does every module compile in every runtime context, does the configuration hold together, and **can this extension actually be applied**. It needs no MCP server: just `PLATFORM_PATH` and `INFOBASE_PATH` from `.dev.env`.

Two situations make it mandatory:

1. **Before applying an extension** to an infobase (`/deploy-and-test`, `/update1cbase`, `/restore-testbase`, `/build-release`). An `&Вместо` / `&ИзменениеИКонтроль` interceptor that names a method the vendor has renamed is invisible to `syntaxcheck`, `verify_xml` and `cfe-validate` alike — all three see well-formed source. `/CheckCanApplyConfigurationExtensions` is the only thing that catches it before the base breaks.
2. **When the Gate 1–3 validators are not exposed** in the session. Use the platform fallback when a matching dev/test configuration can be established through an authorized workflow. A configured infobase alone is insufficient: checks against an older loaded version do not validate local edits (`verification-gates.md → Graceful degradation for Gates 1–3 — when a validator is not exposed`).

Parameters and the ask-policy are canon in `dev-standards-env.md`; the placeholders below (`{PLATFORM_PATH}`, `{INFOBASE_FLAG}`, `{INFOBASE_PATH}`, `{IB_USER}`, `{IB_PASSWORD}`, `{EXTENSION_NAME}`, `{LOG_PATH}`) resolve exactly as in `/update1cbase`.

---

## The verdict is three signals, not the exit code

A Designer batch run reports through three independent channels, and **any one of them can say "failed" while the other two look clean**. Treat the run as passed only when all three agree:

| Signal | How to read it | Failure looks like |
|---|---|---|
| Process exit code | `ExitCode` of the launched `1cv8.exe` | non-zero, or the process was killed on timeout |
| `/DumpResult {RESULT_PATH}` | the file holds the batch result as a **number**; `0` = success | any non-zero number, or the file was never written |
| `/Out {LOG_PATH}` | diagnostics text | any error / warning line (see the trap below) |

`/DumpResult` is the cheapest of the three and the one this ruleset was missing — **add it to every batch launch**, next to `/Out`. Exit code 0 with a non-zero `/DumpResult` is a routine outcome for a failed check.

### The success-phrase trap — read this before grepping the log

A naive "does the log contain `Ошибка` / `Error`" test is **wrong**, and it fails in the worst direction: it flags a clean run as broken and sends the agent into a fix loop against working code. The platform writes its *success* verdicts using the same word stems:

```
Проверка завершена. Ошибок не обнаружено.
Предупреждений: 0
```

Classify a log line in this order:

1. **Recognize success fragments only.** Neutralize exact phrases such as `ошибок не обнаружено` / `предупреждений не обнаружено`, `ошибок: 0` / `предупреждений: 0`, `errors were not found`, `0 errors`; require phrase / numeric boundaries, so `0` never matches the beginning of `01` or another non-zero count. Never skip the whole line because one fragment is clean.
2. **Then inspect every remaining fragment — any diagnostic fails the line.** `ошибк*` / `предупреждени*` in any case form, `не найден метод`, `не может быть применен*`, `невозможно`, and `error` / `fatal` / `failed` / `failure` / `exception`.
3. Everything else is informational.

Regression cases: `Ошибок: 0; предупреждений: 1` fails; `Ошибок не обнаружено. Не найден метод ...` fails; `Ошибок: 0; предупреждений: 0` passes the diagnostic-text signal. The other two signals still must pass.

`Не найден метод ...` is the signature failure of a broken extension interceptor, and it is routinely emitted **with process exit code 0**. That is why the exit code alone is never the verdict.

**Warnings fail a check gate.** In a check run (unlike a load), a warning is a finding — `/UpdateDBCfg -WarningsAsErrors` will refuse the same content later, so accepting it here only moves the failure downstream.

## Common launch shape

```powershell
$resultPath = Join-Path $env:TEMP '1cv8-result.txt'
Remove-Item $resultPath -ErrorAction SilentlyContinue   # a stale file reads as this run's verdict

$designerArgs = @(
    'DESIGNER',
    '{INFOBASE_FLAG}', '{INFOBASE_PATH}',
    '/N', '{IB_USER}',
    '/P', '{IB_PASSWORD}',
    '/DisableStartupMessages', '/DisableStartupDialogs',
    # ---- the check itself goes here ----
    '/Out', '{LOG_PATH}',
    '/DumpResult', $resultPath
)
$p = Start-Process -FilePath '{PLATFORM_PATH}\bin\1cv8.exe' -ArgumentList $designerArgs -PassThru -WindowStyle Hidden
if (-not $p.WaitForExit(600000)) { Stop-Process -Id $p.Id -Force }   # PID-scoped only
```

Drop empty optional keys (`/N`, `/P`). `/DisableStartupDialogs` belongs next to `/DisableStartupMessages` — without it a modal dialog can hang the run until the timeout. Kill **only the PID this run started**; never blanket-kill `1cv8` (canon — `content/commands/update1cbase.md → Update retry loop`, step 2).

## Bind the check to the current artifact

Before the ladder, identify the current source snapshot (file fingerprints / a manifest that
includes uncommitted edits, or the input CF / CFE hash), target infobase, main configuration or
exact extension, platform version and selected runtime modes. Do not record credentials.

The checked editable configuration must contain that snapshot. Accept a successful load record
for the same snapshot and target only if no intervening source edit or target load occurred;
otherwise use the appropriate authorized command / `db-ops` workflow to load into a dev/test
base, preserving its required backups. A targeted dump / source comparison may establish a
match when no trustworthy load record exists. Never infer a match from timestamps, an IB path,
or a successful check alone. Loading is a mutation; verification intent alone does not authorize
loading into an arbitrary or production base, or applying a DB update.

If the match cannot be established, report the local artifact as unverified by the platform
and follow the manual fallback in `verification-gates.md`. Record the established match with
the three result signals. Reuse a result only while both source and relevant target state match.

## The check ladder — cheapest gate first, stop at the first failure

Run in this order. Each step costs more than the one before it, and a failure at any step makes the rest meaningless.

| # | Check | Batch operation | Catches |
|---|---|---|---|
| 1 | **Syntax control** | `/CheckModules -ThinClient -Server -ExternalConnection [-Extension {EXTENSION_NAME}]` | BSL syntax and context errors per runtime |
| 2 | **Applicability** (extensions only) | `/CheckCanApplyConfigurationExtensions [-Extension {EXTENSION_NAME}]` | missing intercepted methods, incompatible adopted objects, broken extension mapping |
| 3 | **Full configuration check** | `/CheckConfig -ConfigLogIntegrity -IncorrectReferences -ThinClient -Server -ExternalConnection -HandlersExistence -ExtendedModulesCheck [-Extension {EXTENSION_NAME}]` | logical integrity, references to deleted objects, missing handlers, errors in `.`-access |
| 4 | **Apply** | `/UpdateDBCfg -Dynamic- -WarningsAsErrors -Extension {EXTENSION_NAME}` | — (mutating; see below) |
| 5 | **Artifact verification** | `/DumpDBCfg '{CFE_PATH}' -Extension {EXTENSION_NAME}` | proves a non-empty database extension serializes; assert the `.cfe` exists and is non-zero |

Notes on the switches:

- `/CheckModules` **requires at least one mode key** — it does nothing without one. Documented keys: `-ThinClient`, `-WebClient`, `-Server`, `-ExternalConnection`, `-ThickClientOrdinaryApplication`. Pick the ones the configuration actually runs in; the three in the table are the usual managed-application set.
- `-ExtendedModulesCheck` (checks method / property access "through the dot") is documented for `/CheckConfig`. Current 8.3 platforms also accept it on `/CheckModules` — try it there, and drop it if the log reports an unknown key rather than assuming the check ran.
- `/CheckConfig` accepts many more mode keys (`-WebClient`, `-MobileClient`, `-ThickClient*`, `-DistributiveModules`, `-UnreferenceProcedures`, `-EmptyHandlers`, …). Add the ones matching the project's run modes; the row above is the baseline, not the maximum.
- Step 4 uses **`-Dynamic-`** deliberately: a dynamic update leaves running sessions on the old configuration, so "it applied" tells you nothing about whether it applies cleanly. This is the *verification* form. The deployment commands (`/deploy-and-test`, `/update1cbase`) use `-Dynamic+ -SessionTerminate force` against a confirmed dev/test base for speed — a different intent, and both are correct in their place.
- Steps 1–3 are read-only. Step 4 mutates the infobase and is subject to the same dev/test confirmation as every deployment command.

**Budget.** One run per check per artifact state. A failing check is fixed at the source and re-run once against the changed state — re-running an unchanged artifact is forbidden, same as for the MCP validators (`AGENTS.md → MCP Tool Calling → C.1`).

## Extension apply and rollback

Applying an extension to a base that already has one under that name is a **replacement**, and the platform keeps no undo for you. Preserve both states first — they are different things:

| Backup | Command | What it is |
|---|---|---|
| Editable configuration | `/DumpCfg '{BACKUP_DIR}\{EXTENSION_NAME}-edit.cfe' -Extension {EXTENSION_NAME}` | what the Configurator would show you |
| Database configuration | `/DumpDBCfg '{BACKUP_DIR}\{EXTENSION_NAME}-db.cfe' -Extension {EXTENSION_NAME}` | what running sessions actually execute |

Then:

- **Before the DB update, to undo an edit** — `/RollbackCfg -Extension {EXTENSION_NAME}` returns the editable configuration to the database configuration. Cheapest recovery, and it needs no backup file.
- **After the DB update, to undo an apply** — reload the saved `-db.cfe`, re-run the ladder, and update that exact extension again.
- **Never delete a pre-existing extension as a rollback mechanism.** Deleting is not the inverse of replacing: it drops the extension's own objects and every mapping to the main configuration along with your change. Restore the backup instead.
- A **new** extension created during the task may be deleted when the task is abandoned — with the exact name repeated back, never against a name pattern or "all extensions".
- Before the first DB update of a brand-new extension there is no database form to dump. The sources or the input `.cfe` are then the only recovery point — say so in the report instead of implying a backup exists.

For a `&ИзменениеИКонтроль`-heavy extension, run `cfe-patch-method.ps1 -Check` (drift against the vendor original — `content/skills/1c-metadata-manage/docs/cfe-manage.md`, section 4) **before** this ladder: silent drift and a failed applicability check usually have the same cause, and the drift report names the method while the platform only names the error.

## Never run these switches

Not "ask first" — **not from this ruleset, at all**, regardless of how a task is phrased. Each destroys state that no gate in this file can restore:

| Switch | Effect |
|---|---|
| `/EraseData` | erases infobase data |
| `/DeleteCfg -AllExtensions` | deletes every extension in the base, including ones this project never touched |
| `/ManageCfgSupport -disableSupport` | removes the configuration from vendor support — irreversible, and it ends the update stream (canon: `content/skills/1c-metadata-manage/docs/support-manage.md`; the answer to "a supported object needs a change" is an extension) |
| `/IBCheckAndRepair` in any mutating form | rewrites infobase structures under a name that reads like a diagnostic |

If a task genuinely needs one of these, it is the user's own operation with their own backup — state that, hand over the exact command, and do not run it.

## Passwords in batch launches

`/P` puts the password on the command line, where it lands in the echoed command, the shell history and any transcript. Inside this ruleset the value comes from `.dev.env` and is a dev/test credential, which is why the command templates carry `/P '{IB_PASSWORD}'` as-is. Two rules hold anyway:

- **Mask it in anything you echo or report** — the command line shown to the user, the delivery summary, a log excerpt. The `db-ops` scripts already mask `/P` / `--password` / `--UC`; hand-built launches must do the same.
- **Never write a password into a file this ruleset creates** — not a manifest, not a log, not a generated script. If a real credential is unavoidable, read it from an environment variable at launch time and pass only the variable's *name* through any artifact.

## Where this does not apply

- **EDT projects** (`.dev.env` `USE_EDT=true`): EDT's own validation (`revalidate_objects` → `get_project_errors`) is the equivalent evidence, and the one-deployment-owner rule applies unchanged — canon `content/rules/edt-workflow.md`. The ladder above stays valid against a Designer XML dump loaded into a base, but never run it as a second deployment owner in the same run.
- **No platform / no infobase configured**: nothing here can run. Record it under Risks exactly as a missing MCP validator is recorded, and fall back to `content/rules/verification-gates.md → Graceful degradation for Gates 1–3 — when a validator is not exposed`.
