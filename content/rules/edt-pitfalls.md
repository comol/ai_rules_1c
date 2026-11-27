---
description: "1C:EDT operational pitfalls and AI-EDT facade routing — safe write_module_source, thick-client monopoly, zip:/// export traps, large configs, rphost cache."
alwaysApply: false
category: tooling
---

# 1C:EDT Operational Pitfalls and Plugin Variants

Load **only** when `USE_EDT=true` (or editing an MDO tree) and performing BSL/metadata writes, DB updates, exports, storage refreshes, or diagnosing EDT errors. Entry and routing: `content/rules/edt-workflow.md`.

## 1. Safe BSL Writes (`write_module_source`)

- **Prefer scoped modes:** use `searchReplace` (unique `oldSource` proving you read current code), `replaceMethod`, or `replaceLines` (always with `expectedText`).
- **Never use `replace` to edit a single method:** `replace` overwrites the entire module with no built-in undo. Allow `replace` only for a brand-new module, a tiny module (<50 lines) passed in full, or an explicit user-approved full rewrite.
- **Keep rollback state in context:** hold `oldSource` until the write response confirms clean syntax; if the wrong block changed, revert immediately with the inverse `searchReplace`. Never pass `skipSyntaxCheck=true` to silence block-balance errors.

## 2. Thick-Client Monopoly and `.cf` / `.cfe` Export

- An open EDT workspace holds an active Configurator (`AgentMode`) lock on its attached file infobase. **Never** run raw `1cv8 DESIGNER` batch commands against that infobase — they block or hang waiting for the lock.
- Run DB updates, `.cf`/`.cfe` exports, and extension admin exclusively through the EDT MCP server so EDT releases and reclaims its session cleanly.
- **Export reads the infobase, not the workspace:** run `update_database` *before* exporting `.cf` / `.cfe`, otherwise the archive contains the pre-edit configuration.

## 3. Incremental `zip:///` Export and Metadata Traps

A clean `get_project_errors` does **not** guarantee `update_database` succeeds (EDT static validation skips some XDTO and restructuring checks):

- **New own `Subsystem` with `includeInCommandInterface=true`:** missing `CommandInterface.cmi` beside the `.mdo` triggers `RuntimeCoreException: Файл не обнаружен 'zip:///Ext/CommandInterface.xml'`. Create minimal `<cmi:CommandInterface xmlns:cmi="http://g5.1c.ru/v8/dt/cmi"/>` and revalidate.
- **Run `resync_to_disk` before `update_database` / export** when objects were modified in memory so disk matches the model.
- **Common silent breakers:** register attribute without `<type>` (drops session on first write); `Date` attribute with `UndefinedValue` instead of minimal `DateValue` (export NPE); new `AccumulationRegister` with no registrar document (`update_database` fails — use `InformationRegister` with `writeMode=Independent` for processor-filled tables); `CheckBoxField` bound to a non-`Boolean` attribute; common module missing platform flags (`server`, `clientOrdinaryApplication`, `externalConnection` per std469).
- **Scheduled jobs:** schedule lives in sibling `Schedule.schedule`, not inside `.mdo`.

## 4. Large Configurations (ERP / УХ), `rphost` Cache and Storage Sync

- **Never run `clean_project` on a large (thousands-of-objects) configuration:** it times out and leaves EDT stuck in `building` until restarted. Batch edits, rely on per-write syntax checks, then run one targeted `revalidate_objects` + `get_project_errors` scoped to modified FQNs.
- **`rphost` cache:** after changing a scheduled-job method signature or renaming a common module (which std706 discourages), `rphost` can keep serving the old signature ("Метод задания не найден" / "Слишком много фактических параметров") despite `ОбновитьПовторноИспользуемыеЗначения()`. Fix via rewriting the job item (`НаименованиеМетода = ...; Записать()`) or asking the operator to restart `rphost` — never propose restarts for ordinary method-body edits.
- **After 1C repository update into EDT:** check borrowed objects in extensions for `extendedConfigurationObject` UUID drift, verify string qualifiers were not truncated, and renormalize EOL per `content/rules/git-safety.md` before reviewing mass diffs.

## 5. EDT MCP Plugin Variants (`EDT-MCP` vs `ai-edt`)

`content/rules/edt-workflow.md` names standalone tools of `DitriXNew/EDT-MCP` (`modify_metadata`, `get_project_errors`, `update_database`). Projects may instead run **`Desko77/ai-edt`**, which groups 100+ operations into facade tools (`code_search`, `edit_metadata`, `diagnostics`, `launch_debugger`, `project_admin`, `infobase_admin`, `config_io`, `insights`, `security_audit`, `git`) routed via `operation=` (with built-in `operation=help` and `aiedt://guidance` resource).

- **Always inspect actual `tools/list`** for the session; never invent standalone names against a facade server or facade names against a standalone server. All safety, model-vs-disk, single-deployment-owner, and destructive-consent rules apply identically to both plugins.
