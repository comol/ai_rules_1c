# 1c-metadata-manage — sync history of the vendored scripts

The PowerShell tools under `tools/` are vendored from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (MIT). This file holds the per-document sync notes that used to close each `docs/*.md` (what each upstream sync changed, what was cross-checked and what stays deliberately local). It is maintainer history — nothing loads it during a task; the operational description of every tool lives in the domain doc named by each heading.

## bsp-manage.md

### Upstream sync `2026-07-30`

Re-checked against upstream `epf-bsp-init` / `epf-bsp-add-command` at the `2026-07-30` sync: **no drift** — kinds, default command types, the `СведенияОВнешнейОбработке` skeleton, `Назначение` / `Модификатор` sections, `НСтр` literals for additional commands, and every handler template (`ВыполнитьКоманду` branches, `Печать` with `УправлениеПечатью.СведенияОПечатнойФорме`) still match Sections 1–2 below. Nothing to port; both skills remain no-script upstream.

### Earlier Additions (upstream `w-2026-05-17`)

The upstream `cc-1c-skills` skills `epf-bsp-init` and `epf-bsp-add-command` are no-script (the agent does the work directly via Read / Edit / Glob / Grep). Their content is already covered by Sections 1–2 of this document, in English. Cross-checked against upstream `w-2026-05-17`:

- Kind mapping (six kinds: `ДополнительнаяОбработка`, `ДополнительныйОтчет`, `ЗаполнениеОбъекта`, `Отчет`, `ПечатнаяФорма`, `СозданиеСвязанныхОбъектов`) — aligned.
- Default command type per kind — aligned.
- Free-form command types (open form, client method, server method, form filling, safe-mode script) — aligned.
- `СведенияОВнешнейОбработке` skeleton, `Назначение` section for assignable kinds, `Модификатор` for `ПечатнаяФорма` — aligned.
- Server handlers (`ВыполнитьКоманду` for `ЗаполнениеОбъекта` / `СозданиеСвязанныхОбъектов` / global processors, `Печать` for `ПечатнаяФорма`) — aligned.

No script files were brought into `tools/` — the operations are pure module-text edits performed by the agent, which is how upstream ships them as well.

## cf-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`cf-edit` v1.12 → **v1.33**, `cf-info` v1.4 → **v1.10**, `cf-init` v1.3 → **v1.17**, `cf-validate` v1.4 → **v1.14**; `tools/1c-cf-manage/cf-edit-reference.md` refreshed.

- **`cf-edit sort-childObjects`** (new): sorts `ChildObjects` by name inside a kind (1C tree order: case-insensitive, `_` < digits < letters, Latin before Cyrillic, ё = е). Empty value — all kinds except `CommonAttribute`, `Subsystem`, `CommandGroup`, `Language`, plus canonical order of the kind groups; a kind named explicitly is always sorted. Only values are swapped, indentation stays.
- `cf-edit`: `Bot` sits after `DefinedType`, `PaletteColor` added to the kind order; a new kind group is inserted at its canonical place, not at the end of the block; operation values are case-insensitive; one-line JSON input errors; ISO dates stay strings on pwsh 7.5+; the save inherits the source's BOM / EOL / final newline.
- `cf-init`: `-FormatVersion` (tested range 2.17–2.21, 2.18 / 2.19 accepted, outside = warning, non-numeric = error); 2.21 writes `TextToSpeech` and the `xmlns:pal` header; `CompatibilityMode DontUse` warns (the platform stores it as `Version8_3_8`); empty elements are self-closing.
- `cf-validate`: **check 10** — every stamped `Ext/*.xml` body must carry the `Configuration.xml` version (the platform refuses mixed formats); check 1 warns outside 2.17–2.21 instead of rejecting 2.18 / 2.19; check 5 knows `Bot` / `PaletteColor`; enum values follow the platform (`MainClientApplicationWindowMode`: `Workplace`, `FullscreenWorkplace`, `EmbeddedWorkplace`; no `Fullscreen`).
- All four: `[CmdletBinding(PositionalBinding=$false)]`, `ProviderPath` for UNC paths.

Local deltas re-applied: `.dev.env` `SUPPORT_GUARD` first, fail-closed on an unreadable `ParentConfigurations.bin`, stderr notice when the guard itself fails; `.dev.env` `NEW_OBJECT_POSITION` first inside upstream's own `Get-NewObjectPosition` (upstream adopted the same `end|byName` design, so our separate copies of it, of `Compare-MetadataNames` and of `Test-OrderSensitiveType` were dropped); sibling `cf-validate` from the same `scripts` dir, its exit (or absence) is the exit code; the compact-tag pass also skips `<?…?>`. `sort-childObjects` is the only operation that reorders existing entries; default insertion still follows `NEW_OBJECT_POSITION`. Pinned by a new regression case.

### Local fix `2026-10-19` — `add-childObject` follows `NEW_OBJECT_POSITION`

`cf-edit` v1.11 → **v1.12** (support ticket 4e6f4e67, item 4): `add-childObject` always inserted a new entry by name inside its kind group (culture-aware `-gt`), whatever `NEW_OBJECT_POSITION` said. It now resolves the setting as `meta-compile` does — `end` (default) after the last object of the kind, as Configurator; `byName` with the 1C-tree comparator; order-sensitive kinds never sorted. Pinned by `tools/tests/metadata-tools-regression.ps1`.

### Local fix `2026-10-01` — sibling validators are found

The auto-validation of `cf-edit`, `interface-edit`, `subsystem-compile` and `subsystem-edit` looked for the validator at upstream's `..\..\<validator>\scripts\` path, which does not exist in this layout, so it was skipped silently; `xdto-edit` looked for `xdto-decompile` / `xdto-compile` / `xdto-validate` the same way and refused every structural operation. All five now take the sibling script from their own `scripts` directory.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `cf-edit` v1.4 → **v1.11**, `cf-info` v1.2 → **v1.4**, `cf-init` v1.2 → **v1.3**, `cf-validate` v1.3 → **v1.4**.

- **`cf-edit` now enforces the vendor support gate** — it refuses to edit a configuration whose "possibility of modification" is off, and points at `support-edit`. See [support-manage.md](support-manage.md).
- **`cf-info` reports the support state** of the configuration (read from `Ext/ParentConfigurations.bin`) — whether it is on vendor support and whether modification is allowed.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-cf-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

#### `cf-init`

- Generates a default panel layout aligned with stock ERP/БП ≥ 8.3.24: open windows on top, sections on the left. Without this layout the web client renders sections as icons only — `web-test` could not see them. Modern interface mode + 8.2-style backward compatibility is the default.

#### `cf-edit` — new operations

- **`set-panels`** — configure the configuration panels via JSON. Aliases by name (`sections`, `open`, `favorites`, `history`, `functions`), panel stacking via `{group: [...]}`, multiple panels side-by-side. Russian aliases (`Открытых`, `Разделов`, `Избранного`, `История`, `Функций`) are accepted and silently mapped to canonical English aliases.
- **`set-home-page`** — rewrite the home page: one or two columns, list of forms with height / visibility / role overrides.
- **`add-childObject`** — now requires the object file to exist on disk; otherwise the script fails with a hint to call `/meta-compile`, `/role-compile`, `/subsystem-compile` first. Previously `Configuration.xml` could end up referencing a missing file and the platform would silently refuse to load. The legacy mode (root XML lost while files survive) is preserved for the rare rollback scenario.

#### `cf-info`

- Configuration overview shows the panel layout (panel stacks within one side and side-by-side panels). With `-Section home-page` — full home page contents with layout and role overrides.

#### `cf-validate`

- Cross-references `Form` references in the home page and in default-form properties of configuration objects — broken links are now caught at validation time, not at load time.
- Platform 8.5 support — new compatibility-mode and interface-mode values plus the new XML header format. (Same upgrade in `cfe-validate`, `epf-validate`, `skd-validate`.)

## cfe-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

Versions: `cfe-borrow` v1.12 → **v1.58**, `cfe-validate` v1.5 → **v1.33**, `cfe-patch-method` v2.5 → **v2.14**, `cfe-diff` v1.0 → **v1.8**, `cfe-init` v1.2 → **v1.13**. `cfe-diff`, `cfe-init` and `cfe-patch-method` had no local delta and were taken as is; `cfe-borrow` was rebuilt on upstream HEAD with the local deltas re-applied; `cfe-validate` is upstream HEAD plus its two local hunks. No sibling calls, Designer launches or `.v8-project.json` reads besides `newObjectPosition` (now `.dev.env` first). Every script got `[CmdletBinding(PositionalBinding=$false)]`.

Behaviour that changes for the agent:

- **Shells load** (8925bd58, 902b643a): `<ChildObjects/>` for data processors, reports, document journals, HTTP / web services, subsystems and the other container kinds; full generated-type sets (`Characteristic` of a chart of characteristic types, chart-of-accounts and calculation-type sets, `Manager` of sequences, filter criteria, settings storages, integration services, WS references).
- **Re-borrow never rewrites** an already borrowed object (8fe727e3); `-Module ObjectModule,ManagerModule,…|None` creates empty modules with their `PropertyState` mark (format 2.19+); merges insert only into the object's own `ChildObjects` (b5662a38). The form `PropertyState` (`Form` / `Extended`) is now written from 2.19 only — the platform drops it below.
- **`-BorrowMainAttribute` is generalized** (d3ea8262, e570ee84, 3fafa099, 83bb5b6f, a424e9cd, c9272cf7, c0e20f75, ecd6010c, 53ee51a3): the source main attribute is copied whole (`Объект`, `Список`, `Запись`, … with `UseAlways` / `Columns`), attributes come from the object in its type, the dynamic-list query text counts as a reference, deep paths borrow each target object with its sub-attribute, standard-field properties are carried, `NumberPeriodicity` is not (otherwise `/UpdateDBCfg` fails), list fields get `~` when the list does not resolve in the extension. The value is now required (03161e1c).
- **Common forms** are borrowed with their content (fdd3bfa4); `cfe-patch-method` accepts `CommonForm.X` (11307082), `cfe-diff` sees its interceptors (d070d65c).
- **Subobjects without a form** (a67314ec): `Type.Name.<Kind>.<Name>` for `Attribute`, `TabularSection` (no columns), `Dimension`, `Resource`, `AddressingAttribute`, `AccountingFlag`, and `TabularSection.T.Attribute.A`. The whole batch is resolved before anything is written; a refusal names the missing child (`Attribute 'X' not found in Document.Y. Extension not changed`).
- **Form body**: element pictures are copied as files (65106509), the `<Form>` / `BaseForm` tag carries the extension's version (53c1d59e), properties naming a form attribute are dropped, conditional appearance is copied.
- **`cfe-validate`**: 13 → 19 checks — GeneratedType completeness and own objects / subobjects the platform will not add (9, 10), `AdditionalColumns` without a section (12), data paths of every extension form against the extension's objects (14), default roles with rights on borrowed objects (15), module / `PropertyState` agreement (16), format-version agreement (17), comparison with the source configuration via the new `-ConfigPath` (18), references to objects missing from the extension (19). A borrowed element without `ExtendedConfigurationObject` is now one summarized warning.
- **`cfe-patch-method -Check`**: the platform's comparison rule (case and inter-token whitespace count, blank lines and indentation do not), parameter-count drift, marker lines with trailing comments, English BSL (533dd0de, d4832ce3, 1b2c9388, 9b1bf22e). **`cfe-diff`** knows `HTTPService`, `WebService`, `XDTOPackage`, `Style`, `WSReference`, `Bot` (a0a91a4e). **`cfe-init`** takes the default language (name, UUID, `LanguageCode`) from the base configuration (39d3a8f4).

Local deltas re-applied: `<RegisterRecords/>` on a borrowed document; no empty `Module.bsl` for a borrowed form (object or common) and no check-11 warning for it; check 12 reports a missing `CommonPicture` / non-platform `StyleItem` as an ERROR; `-BorrowMainAttribute Only`; an unknown `style:` reference is stripped (now also scanned in the `AutoCommandBar` and form properties); Russian kind segments (`Реквизит`, `ТабличнаяЧасть`, …); `NEW_OBJECT_POSITION` from `.dev.env` (cfe-borrow now honours it in the extension's `ChildObjects`, default `end` as before). The `BaseForm` multi-line rule (10-01), the link encoder (10-28) and `Detect-FormatVersion` (10-18) equal upstream now.

Deliberate deviations from upstream, each checked on 8.3.27.2130 by loading into a throwaway file infobase (`/LoadConfigFromFiles -Extension`, `/UpdateDBCfg`, `/CheckCanApplyConfigurationExtensions`, then `/DumpConfigToFiles` and a diff):

- **Element `CommandSet`** (ticket 2b392369, against 0737a795 / fdd3bfa4): kept with its `ExcludedCommand` list while the element keeps its `DataPath` — the round-trip dump keeps it. The 10-19 rule "always keep" was narrowed: in a skeleton form the table loses its binding, and the platform rejects its `Add` / `Copy` («Неверное имя команды элемента формы»), so an unbound element's set is dropped whole, as upstream does.
- **`<Type>` layout**: borrowed attributes and columns keep the source line layout — byte-equal to the round-trip dump; upstream writes `<Type>` on one line.
- **`Only`**: the copied main attribute loses `UseAlways` / `Columns` (they name attributes `Only` does not borrow); a main-attribute object other than the owner is borrowed as a shell.

Tests: `tools/tests/cfe-borrow-regression.ps1` 13 → 18 cases (re-borrow and `-Module`, merge into the own `ChildObjects`, data-processor and chart-of-characteristic-types shells, `.dev.env` `byName`; the CommandSet case now covers both bound and unbound tables). Fixture updates: the extension shell `Catalog.Zeta` got its full generated-type set (the new check 9 flagged it), the base form's table is bound to `Объект.Tovary` (a table without `DataPath` cannot exclude `Add` / `Copy`), `DataProcessor.Obrabotka` and `ChartOfCharacteristicTypes.VidySvoystv` were added. Two assertions follow upstream text: the subobject refusal message and the multi-line main-attribute `<Type>`.

### Local fix `2026-10-28` — choice-parameter and type-link paths

`cfe-borrow` v1.11 → **v1.12** (GitHub issue 33, platform 8.3.27): a borrowed form kept readable `ChoiceParameterLinks` / `TypeLink` paths (`Объект.<Attribute>`, `Items.<Table>.CurrentData.<Field>`). The platform rejects the load with «Неверный путь к полю» when that attribute is not borrowed. The link encoder from upstream `cfe-borrow` is now applied to both the form and `BaseForm`. A borrowed attribute stays readable (`All`, or `Form` when the form references it). Anything else is written as the source form's link code: `<source main id>/0:<uuid>`, a standard-field code, or the source main-attribute id alone when the main attribute is borrowed but the target is not. The extension's own main-attribute id `1000001` is not used. A path that cannot be coded is removed, with a warning. The rest of the local borrow behaviour is unchanged. Pinned by `tools/tests/cfe-borrow-regression.ps1`.

### Local fix `2026-10-19` — an element `CommandSet` keeps its `ExcludedCommand` list

`cfe-borrow` v1.10 → **v1.11** (support ticket 2b392369, an addition to 4e6f4e67): `Borrow-Form` removed every `ExcludedCommand` inside `ChildItems`, so an element whose base form excludes standard commands (a tabular-section table without `Add` / `Copy`) got an empty `<CommandSet></CommandSet>` in the form and in `BaseForm`. Configurator keeps the element's `CommandSet` with its `ExcludedCommand` list in both parts and drops an empty one on load, so the check dump after a partial load differed from the source directory. The element `CommandSet` is now copied as is. Pinned by `tools/tests/cfe-borrow-regression.ps1`.

### Local fix `2026-10-18` — borrowing follows Configurator 2.20

`cfe-borrow` v1.9 → **v1.10**, `cfe-validate` v1.4 → **v1.5** (support ticket 4e6f4e67):

- A borrowed form's `Forms/<Form>.xml` gets the `InternalInfo` `PropertyState` (`Form` / `Extended`) instead of an empty `<InternalInfo/>`.
- `CommandSet` no longer ends the form-property copy: it, its `ExcludedCommand` list and every property after it up to `AutoCommandBar` reach the form and `BaseForm`.
- One attribute (`Type.Name.Attribute.A`) or one tabular-section column (`Type.Name.TabularSection.T.Attribute.A`) can be borrowed: source uuid, source `<Type>`, type objects as shells, no cascade. `-BorrowMainAttribute Only` adds the form attribute `Объект` without the cascade and strips the data paths in both parts.
- A new extension `ChildObjects` entry is appended to the end of its type group instead of being sorted by name. `cf-edit` / `meta-compile` keep the by-name order (APK:1108) for the main configuration.
- No empty `Ext/Form/Module.bsl` for a borrowed form; an existing module is kept.
- A borrowed `Document` gets an empty `<RegisterRecords/>`.
- `cfe-validate` check 12 reports an unborrowed `CommonPicture` or a `StyleItem` outside the platform style list as an error (the form will not load with `Configuration.xml`); check 11 no longer warns about a borrowed form without `Module.bsl`. `cfe-borrow` borrows a referenced style item when the source file exists, and strips a `style:` reference that is neither borrowed nor a platform style item.
- `Detect-FormatVersion` takes the string length after reading. A short UTF-8 `Configuration.xml` with Cyrillic no longer throws on `Substring` (file length is bytes).

Pinned by `tools/tests/cfe-borrow-regression.ps1`.

### Local fix `2026-10-01` — `BaseForm` keeps multi-line texts

`cfe-borrow` shifted every line of the borrowed `AutoCommandBar` / `ChildItems` one tab deeper for `BaseForm`, including the continuation line of a multi-line `v8:content`, so the copy of the base form no longer matched the configuration (support ticket bc42b89c). Only line breaks between two tags are indentation now; the texts keep their bytes.

### Recent Additions (upstream sync `2026-07-30`)

The PowerShell scripts under `tools/1c-cfe-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights of this sync (previous base: late May 2026):

#### `cfe-patch-method` — v1.1 → v2.5, the biggest change in this group

- **Source-aware generation**: the original method is read from the source configuration (`-ConfigPath`, auto-detectable via `.dev.env` `EXPORT_PATH`), so the interceptor gets the real signature, context directive and — for `ModificationAndControl` — the full original body. `ModulePath` may now be a path to the source `.bsl` instead of a logical name.
- **`Instead` (`&Вместо`)** interceptor type with a `ПродолжитьВызов(...)` scaffold; works for functions too.
- **Drift control** — `-Check` / `-Actualize` over controlled (`&ИзменениеИКонтроль`) methods, extension-wide or narrowed to a module / method. Re-applies your `#Вставка` / `#Удаление` edits onto a changed vendor original, reports what moved, what conflicted and what the vendor has already adopted. Conflicts land in a merge workspace with anchored `conflict.md` files instead of being lost. **Run `-Check` after every vendor update** — the platform never reports this drift itself.
- Repeated interception of an already patched method is skipped instead of duplicated.

Full description in section 4 above.

#### `cfe-borrow` — borrowing forms now matches Configurator output

- The borrowed form gets the **complete `ChildItems` tree** (not the previously empty skeleton). Loadable into the target base without manual XML fixes for complex ERP forms.
- **Dependencies are auto-borrowed**: shared pictures, style elements, enums, and enum values used by the borrowed form. No more cascade of "object not found" errors after the first load.
- `DataPath`, `Events`, `TitleDataPath`, `TypeLink`, `CommandName` are stripped from the borrowed form (these caused "invalid data path" / "event not loaded" errors on real ERP forms, also for command-bar buttons).
- Form-level properties (`AutoTitle`, `WindowOpeningMode`, …) are preserved both in the main section and in `BaseForm`.
- **`-BorrowMainAttribute`** (`Form` or `All`) — borrows the form's main attribute (`Object`) and transitively all its attributes, tabular sections, and dependent types. Closes the manual-collection workflow when adding an attribute to a borrowed form.

#### `cfe-validate`

- New checks for borrowed-form structure, their dependencies (shared pictures, style elements, enums), and the extension's own subobjects (attributes, tabular sections, enum values, forms).
- False positives removed: `DataPath` / `TitleDataPath` inside `BaseForm` are correct (Configurator emits them); the extension's own subobjects (own attributes, own enum values) are no longer validated as borrowed.

#### `cfe-init`

- Interface mode and compatibility mode are inherited from the base configuration (resolved via `-ConfigPath`). The extension matches the base's behaviour by default.

#### Vendor support

An extension is the **default answer** when a typical object on vendor support needs a change: support state stays untouched and vendor updates keep flowing. The mutating tools of this skill now enforce that — they refuse to edit a locked object directly and point here. See [support-manage.md](support-manage.md).

## db-manage.md

### Local fix `2026-11-02` — `db-update -SessionTerminate`

`db-update` v1.28 → **v1.29**: the script could not end open sessions. `-AdditionalV8Arguments '-SessionTerminate','force'` lands at the end of the command line, after `/Out` and `/DumpResult`, where the platform ignores it, so the update failed with the exclusive-lock error whenever any session was open. New `-SessionTerminate disable|prompt|force`: for `1cv8` it is emitted right after `/UpdateDBCfg` and its `-Dynamic…` option (`/UpdateDBCfg -Dynamic+ -SessionTerminate force`, the form `/update1cbase` uses), for `ibcmd` as `--session-terminate=<mode>` (the `config apply` key `/deploy-and-test` uses). Both spellings are also in the owned-key lists, so passing them through the additional-argument parameters is refused with a hint to the new parameter. `/update1cbase` Step 3b still runs Designer directly and is unchanged. Pinned by `tools/tests/db-tools-regression.ps1` (the fake platform records the command line).

### Upstream sync 2026-11-01 (2e75b0f)

Scripts under `tools/1c-db-ops/scripts/` refreshed from upstream `2e75b0f`: `db-create` v1.10 → **v1.21**, `db-dump-cf` v1.12 → **v1.23**, `db-dump-dt` v1.11 → **v1.22**, `db-dump-xml` v1.14 → **v1.29**, `db-load-cf` v1.13 → **v1.25**, `db-load-dt` v1.12 → **v1.23**, `db-load-git` v1.18 → **v1.36**, `db-load-xml` v1.19 → **v1.38**, `db-run` v1.7 → **v1.16**, `db-update` v1.14 → **v1.28**; new **`db-cfe-admin` v1.8** (section 11). `install-files-update.ps1` is our own tool and was not touched.

Behaviour changes:

- **No false exit 0** (eb1796ef): a top-level `trap { …; exit 1 }` — an unhandled error inside `try/finally` used to end the script with code 0 and no platform run (reproduced on PS 5.1).
- **No hang on 8.5** (ff894f29, 1c04962b, 3d54652b): the platform is started by a small C# `PlatformProcess` with an explicit inherited-handle list, so `crashpad_handler` cannot hold the caller's pipe; `Process.Start` fallback when `Add-Type` is blocked.
- **Load mode from the list** (989f4c55): `db-load-xml -Files` / `-ListFile` without `-Mode` is a partial load on 1cv8 too (it was `Full` and replaced the whole configuration). `db-dump-xml -Objects` / new `-ObjectsFile` always means `Partial`; `Changes` is `-update` without `-force` (f98e7e9e), a first dump into an empty directory is `Full`, a dump without `ConfigDumpInfo.xml` is refused.
- **`-AllExtensions` with a file list is refused** (647c633a) in `db-load-xml` / `db-load-git`.
- **Silent rejections** (a024b7da): `Find-SilentRejections` (8 patterns, incl. «Для работы с конфигурацией необходима версия платформы не меньше») in `db-load-xml`, `db-load-git`, `db-update`; `db-load-git` reports deletions it cannot apply (80618f0b).
- **Smuggled batch commands** (59438282): `V8BatchKeys` refuse `/CheckConfig`, `/DeleteCfg`, … in `PLATFORM_ARGS` / `-AdditionalV8Arguments`; `/ConfigurationRepositoryP` is a secret key in every copy.
- **Repository credentials** (478e7489, 19d62afb): `db-load-xml`, `db-load-git`, `db-dump-xml`, `db-update`, `db-cfe-admin` pass `/ConfigurationRepositoryF/N/P`; three repository hints in the loaders.
- **Relative paths** (8d9e6c46, c4429ba9, 593b58b0): only absolute paths reach the platform. `[CmdletBinding(PositionalBinding=$false)]` and `ProviderPath` everywhere.

Local deltas re-applied (one variant of every shared function across the family, `db-*` / `epf-*` / `stub-db-create` / `db-cfe-admin`):

- `.dev.env` first in `Get-ProjectExtraArgs`, `Find-ProjectV8Path` (order: `-V8Path` → `PLATFORM_PATH` → record `v8path` → root `v8path` → auto-detect) and the install-dir → `bin\1cv8.exe` substitution; the `.dev.env` directory is also a project root for relative infobase paths. New: `REPOSITORY_PATH` / `REPOSITORY_USER` / `REPOSITORY_PASSWORD` before the registry record (main configuration only; an extension repository stays registry-only). Passing them to an unbound infobase is harmless (8.3.27.2130).
- `/DumpResult` on every Designer launch, now through one shared `Get-DumpResultError`, including the new launches: the applicability check, `db-cfe-admin`.
- `db-update -Dynamic`: upstream's `on/off/yes/no/+/-` plus our `auto/disable`. Log failure lines raise the exit code (not only with `-StrictLog`): the 8 upstream patterns plus «Ошибка [при] обновлени… конфигурации базы данных».
- Repository hints point at `1c-repository-manage` and `.dev.env` instead of upstream `/db-repo` / `.v8-project.json`.

Deliberate deviations from upstream:

- **Extension applicability check is opt-in** (`-ApplyCheck`; `.v8-project.json` `extensionApplyCheck: true` as fallback): `/update1cbase` Step 2c is the gate, so `db-load-*` / `db-update` do not add a second Designer pass by default. With `-ApplyCheck` a refusal exits 1.
- **`db-cfe-admin`**: `-Extension` alias of `-Name`; `delete` / `set-properties` need `-Force`, `-DryRun` prints the plan, neither → exit 2. `/DeleteCfg -Extension ""` deleting the first extension was reproduced on 8.3.27.2130 and added to `designer-batch-checks.md → Never run these switches`.
- Not ported: upstream `db-repo` (our `1c-repository-manage` owns repository operations), the Python ports of `db-*`, CRLF-only fixes.

Pinned by `tools/tests/db-tools-regression.ps1` (fake `1cv8.exe`, no platform). Live on throwaway file bases in `%TEMP%`: 8.3.27.2130 — `db-create`, full and partial `db-load-xml`, `db-update`, `db-dump-xml` (`Changes`, `-Objects`), `db-load-git`, `db-cfe-admin list / check / delete`; 8.5.1.1522 — `db-create` + `db-dump-cf` through a pipe return at once (the hang itself did not reproduce: a `crashpad_handler` was already resident).

### Local fix `2026-10-20` — `-Dynamic` takes `auto` / `disable`

`db-update` v1.13 → **v1.14** (support ticket 7557c7cf): through `powershell.exe -File` a lone `-Dynamic "-"` never reaches the script — Windows PowerShell 5.1 exits with a non-zero code and no output, so the agent saw a silent failure instead of `/UpdateDBCfg -Dynamic-`. `-Dynamic` now also accepts `auto` and `disable` (the ibcmd spellings), mapped to `+` / `-`; `+` / `-` keep working in-process, and `-Dynamic:-` works through `-File` as well. Checked on a throwaway 8.3.27.2130 file base: `-File … -Dynamic disable` → `-Dynamic-`, `auto` → `-Dynamic+`, both exit 0.

### Recent Additions (upstream sync `2026-07-30`)

The PowerShell scripts under `tools/1c-db-ops/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights of this sync (previous base: late May 2026):

- **`db-dump-dt` / `db-load-dt`** — new: full infobase snapshot (configuration + data). See sections 9 and 10.
- **All `db-*` / `epf-*`** — `-AdditionalV8Arguments` / `-AdditionalIbcmdArguments` with per-engine validation and secret masking (see *Common Parameters*); project-wide defaults via `v8args` / `ibcmdargs` in `.v8-project.json`.
- **Platform resolution** — unified across the scripts: explicit `-V8Path` → project config → auto-detect the newest `C:\Program Files\1cv8\*\bin\1cv8.exe`. Locally patched so the project config is read from **`.dev.env`** (`PLATFORM_PATH`, `PLATFORM_ARGS`, `IBCMD_ARGS`, `SUPPORT_GUARD`) before upstream's `.v8-project.json`, and so a **version install directory** — the shape `PLATFORM_PATH` uses — resolves via `bin\1cv8.exe`.
- **`db-load-xml`** — strict log parsing. Catches "Неверное свойство объекта метаданных", "Неизвестное имя типа" and similar messages that the platform writes to the log despite a formal "success" exit. Previously a partial silent metadata loss was reported as a green run.
- **`db-load-xml` / `db-load-git`** — `-UpdateDB` flag combines load + database update in a single Configurator launch (was two separate calls).
- **`db-load-git`** — picks up changes to HTML help (`ru.html` and similar) via partial load even without the accompanying `Help.xml` in the commit. Previously such edits were silently dropped and the help text in the base stayed stale. Fixed search for changed files when sources live in a nested folder of the repo (`src/cf` etc.); path normalisation for the configuration directory is corrected.
- **db-list** — already fully described in Part 1 of this doc (registry of `.v8-project.json`). It is a no-script skill in upstream — the agent reads / writes the JSON directly. No script files were added under `tools/`.

## epf-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

`epf-build` v1.12 → **v1.26**, `stub-db-create` v1.7 → **v1.17**, `epf-dump` v1.11 → **v1.22**, `epf-validate` v1.2 → **v1.12**, `epf-init` v1.1 → **v1.9**, `erf-init` v1.1 → **v1.9**.

- **Source check before the build** (448f05ed, 06bdee3e, 63634466, e2c7f385): the processor is embedded into a stub configuration and `/CheckConfig` runs first; `-Checks`, `-Context`, `-ConfigSrc`. On by default as upstream; ~11 s against ~4–5 s with `-Checks off` for a minimal processor on 8.3.27.2130.
- **`stub-db-create`** (beaa75c7, 614206bc): format version and compatibility mode come from the sources; logs live in the unique stub directory.
- **`epf-validate`** (5d1b5cdf, fbcf65e1): `Command` in `ChildObjects` and `Ext/ManagerModule.bsl` are errors; check 11 — format version of stamped bodies.
- **`epf-init` / `erf-init`** (974ca3aa, 3ef9e76f): synonym XML-escaped; `-FormatVersion`.
- `trap`, `PlatformProcess` and the stub launched with `Start-Process -PassThru` + `WaitForExit` instead of `-Wait` (8.5 hang), as in the `db-manage.md` entry above.

Local deltas re-applied: `.dev.env` first (as in `db-*`); `/DumpResult` on the build, the `/CheckConfig` pre-check and the stub's `/LoadConfigFromFiles` / `/UpdateDBCfg`; the stub runs under `pwsh` on PowerShell Core; the 2026-10-07 common-forms delta (`epf-validate` check 5, `stub-db-create` stubs — now stamped with the stub format version, `erf-init -BspForms`) — checked with the pre-check on: an `erf-init -BspForms` report builds on 8.3.27.2130. Deviation: common modules for the pre-check come from `.dev.env` `EXPORT_PATH` before the registry `configSrc`, and the printed check command line is masked.

### Local fix `2026-10-07` — common forms in external reports

External reports and data processors may name configuration common forms in `DefaultForm` / `DefaultSettingsForm` / `DefaultVariantForm` (БСП reports: `CommonForm.ФормаОтчета`). Checked on 8.3.27.2130: such an ERF builds in an infobase that has the form, and the reference survives a dump in another infobase with a same-named form (it is stored by name); without the form the build fails with «Неизвестный объект метаданных».

- `epf-validate` check 5 accepts `CommonForm.<Name>` in `DefaultForm` instead of warning about an unexpected prefix.
- `stub-db-create` creates an empty managed common form for every `CommonForm.<Name>` named by those properties, so a build without an explicit infobase passes.
- `erf-init` gained `-BspForms`: the three main forms are the БСП common forms.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `epf-build` v1.0 → **v1.12**, `epf-dump` v1.0 → **v1.11**, `stub-db-create` v1.0 → **v1.7**, `erf-init` → **v1.1** (full ERF scaffold — the local copy was a truncated variant).

- **Build / dump via `ibcmd`** — full EPF *and* ERF assembly and disassembly without launching the Designer, when the platform path points at `ibcmd`.
- **`-AdditionalV8Arguments` / `-AdditionalIbcmdArguments`** with per-engine validation and secret masking — same contract as the `db-*` tools ([db-manage.md](db-manage.md)).
- Platform resolution unified with the `db-*` tools (explicit path → `.dev.env` → `.v8-project.json` → auto-detect), locally patched to accept the version install directory shape used by `.dev.env` `PLATFORM_PATH`.
- Autonomous external objects (EPF/ERF) are explicitly exempt from the vendor support gate — they are never part of a configuration on support.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-epf-validate/scripts/epf-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Format version auto-detection** from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Platform 8.5** support across `epf-validate` and `erf-validate` (new compatibility-mode and interface-mode values, new XML header format).
- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both an XML file and a folder path as the primary argument; universal `-Path` parameter alongside legacy `-ObjectPath`.
- The same script handles `erf-validate` — upstream `erf-validate` is a thin pass-through to `epf-validate.ps1`, the script auto-detects `ExternalReport` vs `ExternalDataProcessor` from the root XML element. No separate `erf-validate.ps1` is shipped.

## form-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) `2e75b0f`: `form-compile` v1.176 → **v1.224** (both runtimes), `form-edit` v1.6 → **v1.46**, `form-validate` v1.10 → **v1.39**, `form-info` v1.5 → **v1.14**, `form-add` v1.12 → **v1.34** (both runtimes), `remove-form` v1.4 → **v1.11** (both runtimes, reference check only). `tools/1c-form-compile/form-dsl-spec.md` is re-merged with upstream `docs/form-dsl-spec.md`. The scripts read no new data files: the event catalog, handler-stub templates, enum sets and child-tag orders are embedded; `presets/erp-standard.json` is unchanged upstream and keeps the local posting properties.

Behaviour changes to expect:

- **Handler stubs in `Module.bsl`** — `form-compile` and `form-edit` append an empty procedure (catalog directive and parameters, BSP region) for every bound handler the module lacks; no switch. `content/rules/form-module.md` and `forms.md` tell the agent to expect it.
- **Event catalog** from vendor configurations replaces the hand lists: per-element handler suffixes (`Selection` → `Выбор`, `OnEditEnd` → `ПриОкончанииРедактирования`, `DragEnd` → `ОкончаниеПеретаскивания` — the local suffix fixes are upstream's now), `[WARN]` for an event of another element, an 8.5-only event or a dynamic-list-only event.
- **Enum values by XSD** (7c1a3318, 14f1126b, afd863a4, 24429b46): case fixed silently, synonyms mapped (button `TextPicture` ↔ command `PictureAndText`, `single` → `SingleRow`), unknown value refused, platform defaults not written; button / command children in platform order (bd0081c2); `Enum.X.EnumValue.Y` design-time values fixed and checked (6b00da9a, 9181692f, check 26); no `RowPictureDataPath = <List>.DefaultPicture` on a dynamic list with an explicit `keyType` and no `mainTable` — «Неверный путь к данным» (0bba1719).
- **Usual group without `showTitle`** hides its title unless `title` / `titleDataPath` is set (af28bbb8, 36ae6195, 5f9490b2); `form-compile.py` no longer breaks on Python < 3.12 (5f9490b2), reads DSL keys case-insensitively (57b0f95b), refuses a cp1251 JSON file instead of mangling it (229e66b9) and registers the form in the object's top-level `ChildObjects`, not a tabular section's (11602f8b).
- **`form-edit` 1.46** — move / set / remove / rename of elements, attributes, commands, parameters and columns, form title / properties / events / excluded commands / conditional appearance / command interface; elements by the `form-compile` emitters; extension handler names with prefix and call type (cd1cf252).
- **`form-add`** — purpose table per kind: `Folder`, `FolderChoice`, `RecordSet`, `Save`, `Load`, `Custom`, document journals (`List` → `DefaultForm`, no more `cfg:.Журнал`), accumulation / accounting / calculation registers, external-source tables (45353afc, 53fc16d2, fb211a61); empty `-Purpose` = the kind's primary form. An information register has no `Object` purpose any more — use `Record` (the main attribute is `Запись`, which was the local fix).
- **`form-info -Handlers`** (7d776798) — handler line ranges in `Module.bsl`.
- **`form-validate`** — upstream checks 13, 15–27 and the reworked version check 14: the form must match its descriptor `Forms/<Name>.xml` and the `<BaseForm version>` stamp (c943acef, b20276fa); a mismatch with the rest of the dump is only a warning. A command without `Action` and an `AutoCommandBar` id ≠ −1 are warnings now (e1d5d1f9, af00aa47).

Local deltas re-applied: `.dev.env` `SUPPORT_GUARD` and fail-closed guard in every form script; `-FromObject` guard target `Ext/Form.xml`; from-object `ChoiceMode` on the document choice form, document item preset `AutoTime` / `UsePostingMode` / `RepostOnWrite` in Configurator order, `Description` only when `DescriptionLength > 0`, `[WARN]` on a missing `Configuration.xml`; the one event normalizer (standalone `handlers`, refusal on two spellings and on a `handlers` key absent from `on`) in both `form-compile` runtimes; injection-safe registration lookup; processing instructions protected by the compact-tag pass in `form-compile`, `form-edit`, `form-add` (upstream protects CDATA and comments only); `form-edit` refusal of a `DynamicList` without `mainTable` / `query`; `form-add` `-FormName` identifier check and XML escaping; `remove-form` hardening unchanged.

`form-validate` numbering, merged: upstream numbers stay; local checks get numbers after upstream's last — **12b → 28** (owner of a default form), **14 → 29** (`РеквизитФормыВЗначение` context). Local **13** is merged into upstream **22**: a missing handler is now an **error** (upstream severity), duplicate declaration (error), missing / wrong directive and arity (warnings) are kept. Local **15** (`Representation`) is covered by upstream **15** and dropped; local **1** (version against `Configuration.xml`) is replaced by upstream **14**. `export folder name` stays inside 12, the DynamicList-without-source error stays among the unnumbered checks.

Deliberate deviations from upstream:

- **Unknown events**: an event name that no element has in the catalog is refused (exit 1, no file) in `form-compile` — upstream warns. Catalog-known events of other elements, 8.5-only and dynamic-list-only events keep upstream's `[WARN]`. `form-edit` keeps upstream's warning.
- **`remove-form`**: only 93d9511a is taken (full-reference match — the old `Form.<Name>` tail match blanked `DocumentJournal.J.Form.<Name>` and `CommonForm.<Name>` slots — and the configuration-wide scan). Upstream's `-Force` also cleans the foreign references; here `-Force` stays the deletion gate after `-DryRun`, foreign references block it with exit 2, and the new `-CleanReferences` switch clears them inside the same quarantine transaction (backups of every touched file, link-free path chain checked). Without `Configuration.xml` the object's own directory is scanned and a `[WARN]` says so. Upstream's delete-first order and its implicit cleaning are not taken.
- `form-add` / `form-compile` / `form-edit` keep upstream's XmlWriter save but with the processing-instruction branch of the local compact-tag fix.

`tools/tests/python-ports-regression.py` gained cases for enum spelling and button / command order, journal and record-set forms, and the foreign-reference block / clean (both runtimes each); `metadata-tools-regression.ps1` for the `form-edit` DynamicList refusal and the new check numbers. Verified live on 8.3.27.2130: a dump built with `cf-init` / `meta-compile` / `form-add` / `form-compile -FromObject` / `form-edit` loaded into a throwaway file infobase with `/LoadConfigFromFiles` + `/UpdateDBCfg`; the dumped-back choice and list forms were identical to the generated ones.

### Local fix `2026-10-14` — input-field events and pass-through keys

`form-compile` refused the input-field events `Tuning` (Регулирование), `Opening` and `StartListChoice`, which vendor forms use (ZUP dump: 333, 195 and 2 input fields; support ticket 0225a24c, ERP 2.5 `Документ.НачислениеЗарплаты.ФормаДокумента`). They are allowed for `input` in the PowerShell and Python compilers and in `form-edit`, with the handler suffixes `Регулирование` / `НачалоВыбораИзСписка`. The pass-through scalars of `genericScalars` (`markNegatives`, `threeState`, `choiceListHeight` and 30 more) were written to `Form.xml` yet reported as «unknown key … ignored»; they now count as known keys. `form-compile-dsl.md` lists the `input` and `picField` events separately, as the compiler checks them.

### Local fix `2026-10-01` — button and command order, command `Representation`

`form-edit` wrote a button's `CommandName` before its `Representation`, a command's `Action` before its `Picture` and a command's picture-and-text `Representation` as `PictureAndText`; the platform refused such a borrowed form with «Исключение XDTO произошло при чтении файла» (support ticket bc42b89c, 8.3.27.2170). Button children now follow the platform order (`Type`, `Visible`, `Representation`, `DefaultButton`, `Enabled`, `CommandName`, `Picture`, `Title`, `LocationInCommandBar`) and command children `Title`, `Shortcut`, `Picture`, `Action`, `Representation`, taken from every `Form.xml` of the ZUP dump; a command's `PictureAndText` is written as `TextPicture` (and a button's `TextPicture` as `PictureAndText`). `form-validate` check 15 reports a `Representation` outside the element's own enumeration. `form-compile` still writes a command's `Action` before `Shortcut` / `Picture` and a button's `Representation` after `CommandName` — not changed here.

### Local fix `2026-09-25` — vendor-shaped defaults, closed enum values, Form.xml against Module.bsl

Rules taken from the static checks of [AzeevAN/mcp-1c](https://github.com/AzeevAN/mcp-1c) (Apache-2.0; rules re-implemented, no code copied) and calibrated on the ERP (8.3.27) and ZUP Designer dumps so that vendor forms raise no errors.

- **`form-compile` v1.176** (both runtimes): the from-object document choice form sets `ChoiceMode` on its list table like the catalog one; the `document.item` preset (hard-coded default and `presets/erp-standard.json`) writes `AutoTime=CurrentOrLast`, `UsePostingMode=Auto`, `RepostOnWrite=true` in Configurator order; `Description` is bound only when `DescriptionLength > 0`. `windowOpeningMode` / `autoTime` / `usePostingMode` accept only the platform enum values — `form-dsl-spec.md` listed `Modeless`, `Current`, `Postings`, `Movements`, which do not exist. A missing `Configuration.xml` is a `[WARN]` naming the assumed 2.17 instead of a silent guess.
- **`form-add` v1.12** (both runtimes): `-FormName` must be a 1C identifier (exit 2 before any path or XPath is built from it); the object form of an information register names its `RecordManager` main attribute `Запись`, as the Configurator does.
- **`form-validate` v1.10**: version equal to `Configuration.xml` (check 1); `cfg:Catalogs.X` is an error (12); owner type of the main attribute in default object / record forms and no zero-length `Description` / `Code` binding (12b); handlers against `Module.bsl` (13 — duplicate declaration is an error, the rest are warnings because ERP ships them); `РеквизитФормыВЗначение` / `ЗначениеВРеквизитФормы` only in `&НаСервере` (14).

### Local fix `2026-09-14` — compact XML across the reported writers

`form-edit.ps1` normalizes empty tags to Configurator's `<Tag/>` spelling and retains the input EOL. The same save-time behavior covers `form-add`, `remove-form`, parent registration by `form-compile`, `cf-edit`, object registration/merge by `cfe-borrow`, `subsystem-edit`, parent registration by `subsystem-compile`, `interface-edit`, `add-template` and `add-help`. `skd-edit` already normalized tags; its normalization now protects CDATA, comments and processing instructions. No shared runtime dependency was added.

Focused regressions exercise each reported writer on temporary fixtures. Command-add checks compare unrelated form text byte-for-byte for LF and CRLF; template checks cover absolute/relative XML paths and the existing name/EPF lookup. The remove-form quarantine and rollback remain intact.

### Local fix `2026-09-10` — DynamicList settings in `form-edit`

`form-edit` v1.5 wrote a `DynamicList` attribute as Type only. The platform then opened the form with «не задан ни текст запроса, ни основная таблица». `form-edit` v1.6 requires `settings.mainTable` or `settings.query` and emits `<Settings xsi:type="DynamicList">` (`ManualQuery`, `DynamicDataRead`, optional `QueryText`, `MainTable`). `form-validate` v1.9 reports the same gap on an existing form. Full DCS list settings remain `form-compile`.

### Python runtime for `form-remove` (`2026-09-04`)

`remove-form.py` is vendored from the same upstream repository, pinned at commit `ecd289fe11733028d87b55284ea9fb5feff8f513` — the state the PowerShell family below was synced from, so both runtimes are the same tool generation. It exists so a Linux / macOS install is not left with a script it cannot run.

The upstream port needed the same local hardening the PowerShell script carries, and one ordering fix on top: upstream rejects `-DryRun` as an unknown argument, deletes without `-Force`, and deletes the form files **before** parsing the root XML, so a parse failure leaves a half-removed tree. The vendored copy follows the shipped contract instead — parse → plan → gate → atomic root-XML write → delete. Both runtimes are pinned against each other by `tools/tests/python-ports-regression.py`.

The safety hardening is applied to **both** runtimes, so a Windows user is not left with the weaker tool: identifier validation, path containment and the transactional mutation path live in `remove-form.ps1` as well.

The Python port keeps upstream's round-trip style preservation (BOM, EOL, `encoding` case, `<Tag/>`). Since the local 2026-09-14 fix, `remove-form.ps1` also keeps the input EOL and compact empty tags when it stages the parent XML; the quarantine and rollback sequence is unchanged. The `ChildObjects` indentation is identical in both.

Licence: the vendored upstream code is MIT; the full notice ships with the skill as [`NOTICE.md`](../NOTICE.md) and is installed alongside it.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `form-compile` v1.23 → **v1.175**, `form-add` v1.5 → **v1.11**, `form-edit` v1.0 → **v1.5**, `form-info` v1.3 → **v1.5**, `form-validate` v1.6 → **v1.8**, `form-remove` → **v1.4**.

- **`form-compile` is the big one** — 150+ upstream releases since the previous base. The DSL grew well past what [form-compile-dsl.md](form-compile-dsl.md) describes: dynamic-list settings (filters, order, conditional appearance, groupings, calculated fields, typed parameter values), forgiving platform types (`StandardPeriod`, `StandardBeginningDate`, `UUID`), roles by GUID for borrowed / extension forms, `SettingsStorage`. **The complete grammar is vendored as [`form-dsl-spec.md`](../tools/1c-form-compile/form-dsl-spec.md)** — read it when a key is missing from the local reference.
- **Support gate** — `form-compile`, `form-edit`, `form-add` refuse to touch a form of a locked object of a typical configuration. See [support-manage.md](support-manage.md).
- **`form-add`** — `DocumentJournal` support.
- **`form-validate`** — dangling-binding checks; paired with the `cfe-borrow` re-borrow idempotency fix.
- **`form-info`** — prints the object's support state.
- **`form-remove`** — clears **every** `Default*Form` slot pointing at the removed form (previously only the generic `DefaultForm`, which left a dangling reference to a deleted form). Local `-DryRun` / `-Force` safety gate is preserved on top.

### Earlier Additions (upstream `w-2026-05-17`)

In addition to the form-compile / form-info / form-add / form-edit / form-remove changes already documented in sections 2–5, **`form-validate`** got the following improvements (script `tools/1c-form-validate/scripts/form-validate.ps1`):

- Stops false-flagging real ERP and БП forms — `Items.<Table>.CurrentData.<Field>` and `~<DynamicList>.<Field>` paths are now correctly resolved through the table's data attribute. Missing table → error; third segment ≠ `CurrentData` → warning.
- Opaque platform paths (`"10"`, `"1000003"`, `"N/M: "`) are skipped without an error. Previously Check 5 reported "attribute not found" on these.
- New attribute-type check in `data`: error on intentionally invalid types, warning on unrecognised ones. Context is honoured — `ExternalDataProcessorObject` / `ExternalReportObject` are valid only inside an external data processor / report; in regular configuration object forms it is an error with a hint to use the inner object type.
- Platform 8.5 support — new compatibility / interface mode values and the new XML header format.
- Brief output by default; full per-check trace via `-Detailed`. The `-Path` parameter accepts both a `Form.xml` file and a `Forms/<Name>` folder (auto-resolves to `Forms/<Name>/Ext/Form.xml`).

### What's New in `form-compile` (vs the previous local snapshot)

- **`-FromObject` mode** — produces a typical form from object metadata; purpose (`Object`/`List`/`Choice`/`Folder`/`Record`) is inferred from `OutputPath`. Document list forms get the standard `Number` and `Date` columns automatically; ChartOfAccounts pulls accounting flags / sub-account kinds correctly.
- **New element types** — `radio` (RadioButtonField with `radioButtonType`: `Auto` / `RadioButtons` / `Tumbler`, `choiceList`); `autoCmdBar` (fills the form's main AutoCommandBar id=-1); `columnGroup` (column grouping inside table `columns` — `horizontal` / `vertical` / `inCell`, nestable).
- **New input keys** — `textEdit: false` (disable free text editing on reference fields), `maxWidth` / `maxHeight` (hard caps, usually with `autoMaxWidth: false`).
- **New group key** — `collapsed: true` for `"group": "collapsible"` (group starts collapsed).
- **Multilingual strings** — any title / presentation may be `{ "ru": "...", "en": "..." }`.
- **Auto-titles** — attributes, commands, pages, popups and decorations without explicit `title` get a humanised title from the name (`НомерСчёта` → "Номер счёта").
- **Format version** — auto-detected from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Presets** — `tools/1c-form-compile/presets/erp-standard.json` is shipped; project-level override at `<projectRoot>/presets/skills/form/<name>.json`.
- **Defaults aligned with real ERP/БП forms** — multi-line inputs are not auto-width-bounded by default; checkbox title is on the right; `autoTitle` is suppressed when `title` is set; objects with editable state save the input state (`Esc → confirm`).

## help-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`help-add` v1.9 → **v1.26**.

- `Help.xml` takes the **owner's format version**: the object descriptor first (EPF / ERF root included, trailing slash in `-ObjectName` handled), then `Configuration.xml`; it used to be 2.17 for every EPF / ERF.
- `-Lang` is validated before any write: letters, digits, `-`, `_` only, Windows device names refused — `-Lang ../../x` no longer writes outside `Ext/Help`.
- An existing `Help/<lang>.html` is kept when `Help.xml` is missing (it used to be overwritten by the skeleton with exit 0); paired `<meta>` / `<link>` in the page.

Local: `.dev.env` `SUPPORT_GUARD` first with fail-closed parsing; `<?…?>` skipped by the compact-tag pass; `[CmdletBinding(PositionalBinding=$false)]` added (upstream left this tool without it). The doc's `-ProcessorName` call was wrong — the parameter is `-ObjectName`. Regression cases: EPF stamped 2.20, refused `-Lang` traversal / device name.

### Upstream sync `2026-07-30`

Script refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `help-add` v1.4 → **v1.9**. It now enforces the vendor support gate — adding help to a locked object of a typical configuration is refused with a pointer to `support-edit` ([support-manage.md](support-manage.md)).

## interface-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`interface-edit` v1.8 → **v1.26**, `interface-validate` v1.1 → **v1.7**.

- `interface-validate` **check 14**: the file's format version equals its owner's (subsystem descriptor or `Configuration.xml`) — ERROR; differs only from the rest of the dump — WARN. `-Detailed`; a `-MaxErrors` stop is reported.
- `interface-edit`: operation values case-insensitive, more Russian kind names, `Detect-FormatVersion` measures characters (a short Cyrillic `Configuration.xml` no longer throws), the save inherits BOM / EOL.

Local deltas re-applied: `.dev.env` `SUPPORT_GUARD` first with fail-closed parsing; sibling `interface-validate`, its exit is the exit code; `<?…?>` skipped by the compact-tag pass.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `interface-edit` v1.3 → **v1.8**, `interface-validate` → **v1.1**. `interface-edit` now enforces the vendor support gate — it refuses to edit the command interface of a locked typical configuration ([support-manage.md](support-manage.md)).

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-interface-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`interface-edit`** — operations `place` / `order` accept the value as an object (not only as a string). Command names in `hide` / `show` / `place` / `order` are normalised: `Catalogs.X` and `Справочник.X` map to canonical `Catalog.X`.
- **`interface-validate`** — universal validator improvements (one-liner output by default, `-Detailed`, folder path auto-resolution) — see `role-manage.md` → "Recent Additions".

## meta-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) `2e75b0f`: `meta-compile` v1.69 → **v1.126**, `meta-edit` v1.24 → **v1.73** (`meta-edit.py` to the same commit), `meta-validate` v1.13 → **v1.45** (both runtimes), `meta-info` v1.4 → **v1.16**, `meta-remove` v1.5 → **v1.15**. `meta-dsl-spec.md` and the `meta-edit` references (`json-dsl.md`, `child-operations.md`, `properties-reference.md`) follow upstream HEAD. External data sources (compile / edit / info / remove / validate) and format 2.21 (8.5) come with HEAD; every script has `[CmdletBinding(PositionalBinding=$false)]`.

- **`meta-compile`** — XML the platform refused is no longer written: a `Constant` without `valueType` is `String(10)` (was `<v8:Type>Constant</v8:Type>`, which failed the whole load); `numberLength: 0` drops `Number` from the default `InputByString`; an unknown bare type name is refused with the valid forms instead of reaching the XML verbatim, DBMS spellings (`varchar(n)`, `numeric(p,s)`, `integer`, `timestamp`, `bytea`, …) are translated and `BinaryData` is its own type; `WebService` writes `XDTOPackages` as a list plus `DescriptorFileName`, multilingual service synonyms are language items, `HTTPService` accepts `ReuseSessions=Use`; lower-case kinds, `"Документ.Имя"`, `None` periodicity, `FillChecking=ShowWarning`, dimension `TypeReductionMode` and ISO dates on pwsh 7.5+ are handled; the labels `meta-info` prints are accepted as input; `Detect-FormatVersion` measures characters.
- **`meta-edit`** — a failed operation is exit 1 with nothing written (was `[WARN]` and exit 0: a missing element, `add-registerRecord` on a borrowed document); `modify-property` normalizes enum values, matches keys case-insensitively, writes empty multilingual properties as XML and handles `CodeLength` / `NumberLength` `0`; removing forms / templates is refused; external-source fields, tables and functions; `meta-edit.py` compares DSL keys case-insensitively.
- **`meta-validate`** — false ERRORs removed: empty `<Type/>`, IntegrationService / Bot, subscription sources as `v8:TypeSet`, `xr:Item` journal content, `TypeReductionMode` (a 2.18 property, was declared 2.20 — an error on nearly every 8.3.25 / 8.3.26 object). New checks 7b (standard-attribute and `LineNumber` names), 15 (commands), 20 (default / choice form references), 21 (external-source tables), 22 (type-name grammar), 23 (type sets), 24 (format versions), 25 (multilingual strings); tested format range 2.17–2.21.
- **`meta-info`** — standard-attributes block (owner, code, number, value type), type sets shown as types, clean command names, external data sources.
- **`meta-remove`** — `Configuration.xml` is scanned for references (configuration-level form slots are listed, cleared only with `-Force`); external-source tables removed as `ExternalDataSource.<Source>.Table.<Table>`; one pass over the configuration instead of two.

Local deltas re-applied: `.dev.env` first for `SUPPORT_GUARD` (fail-closed on an unreadable support state) and `NEW_OBJECT_POSITION` in every guard / registration copy (`.v8-project.json` stays the fallback; upstream now uses the same `end` / `byName` design and byte-preserving registration); `meta-compile` exit 3 for an unregistered object and batch runs in the same PowerShell edition; `meta-edit` (both runtimes) refuses `add-form` / `add-template` before any write, resolves its validator under `1c-meta-validate`, refuses before the write when it is missing, keeps `-NoValidate` as the only opt-out and propagates the validator's exit code; upstream's new EPF / ERF auto-validation (`372510bb`) is mapped to `1c-epf-validate` with the same refusal (Python runs the PowerShell script, refuses without a host); `meta-validate` keeps 6a–6d, 2, 6f, 6g, 6h, 8, 12, 16a.

Deliberate deviations:
- **No silent overwrite** — `meta-compile` on an object whose XML exists exits 1 before writing unless `-Force` is passed. Upstream only warns (`123d6e32`); a recompile gives the object a new uuid and breaks the link to the infobase object.
- **Versions** — the local 1e / 6e (every file carries the `Configuration.xml` version, ERROR) are replaced by upstream check 24, measured on 8.3.27 (`a9086180`, `f421ce3d`): a body out of step with its descriptor is an ERROR, a descriptor out of step with the dump a WARN.
- **No double reports** — 6f keeps only the form-role rule (resolution is check 20, which also accepts foreign and common forms the old 6f rejected); upstream's cross-kind name block is folded into the local 8, which also covers addressing attributes and accounting flags; check 22 skips types 16a already reported.

Verified: a configuration of seven objects built by `meta-compile` (catalog with DBMS-typed attributes, `Constant` without `valueType`, enum, document with `numberLength: 0`, periodic information register, HTTP service with `ReuseSessions=Use`, common module) loads with `/UpdateDBCfg` into a fresh file infobase on 8.3.27.2130, and both `meta-validate` runtimes accept every object.

### Local fix `2026-09-25` — versions, generated types, default forms, name clashes

`meta-validate` v1.13, both runtimes with identical messages: object, form descriptor and `Form.xml` versions equal `Configuration.xml` (1e, 6e); every GeneratedType category is required and named exactly (2); `Default*Form` / `Auxiliary*Form` resolve to a declared form of the right role (6f); no `Description` / `Code` binding when the length is 0 (6g) and a warning when the default object form hides a mandatory `Description` nobody assigns (6h); case-insensitive name uniqueness shared by attributes, tabular sections, dimensions and resources (8); `Periodicity` and `DefaultRecordSetForm` forbidden in an information register (12); `cfg:Catalogs.X` is an error (16a). Over all 10 965 ERP objects none of the new error checks fires; 6h warns on 6 attached-file / exchange catalogs.

### Local fix `2026-09-13` — refuse false-success template additions

Both `meta-edit` runtimes refuse `add-template` before any write, including aliases and mixed JSON. The error points to the existing PowerShell template scaffold and requires an explicit template type. No partial registration is presented as a completed template.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `meta-compile` v1.12 → **v1.68**, `meta-edit` v1.6 → **v1.23**, `meta-validate` v1.3 → **v1.12**, `meta-info` v1.2 → **v1.4**, `meta-remove` v1.1 → **v1.5**.

- **Support gate** — `meta-edit` / `meta-compile` refuse to touch an object of a typical configuration that is locked ("на замке"); `meta-remove` refuses to delete an object still on support. See [support-manage.md](support-manage.md).
- **`meta-compile`** — many more object types authorable from the DSL (`CommonPicture`, `CommonTemplate`, `SessionParameter`, `CommonCommand`, `CommandGroup`, `CommonAttribute`, `FunctionalOptionsParameter`, `WSReference`), format 2.20 properties (platform 8.3.27), command-group validation, better auto-synonym derivation. Full grammar: [`meta-dsl-spec.md`](../tools/1c-meta-compile/meta-dsl-spec.md).
- **`meta-edit`** — structural attribute properties are now editable point-wise: `Format` / `EditFormat` / `ToolTip` / `ChoiceForm`, `MinValue` / `MaxValue`, `LinkByType` / `ChoiceParameterLinks`, `ChoiceParameters`, `FillValue`; list properties `DataLockFields` / `RegisteredDocuments`; `add-predefined` for predefined items; create-if-missing for properties with a type guard.
- **`meta-validate`** — checks that referenced types exist, validates object commands (group + parameter rule), version-dependent properties and the `LineNumberLength` range, `MDObjectRef` reference shape, and rejects reserved attribute names in a type-aware way.
- **`meta-info`** — prints the object's support state and the type presentation for reference objects.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-meta-{compile,edit,info,remove,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

#### `meta-compile` — new properties and stricter type rules

- **Catalog properties** are now driven by JSON (no more hard-coded values): `limitLevelCount`, `levelCount`, `foldersOnTop`, `subordinationUse`, `codeSeries`, `quickChoice`, `choiceMode`. Hand-edit of XML is no longer required for non-default settings.
- **`owners`** — array of catalog owners with shorthand syntax.
- **`multiLine: true`** (or flag `| multiline`) on an attribute marks it as multiline.
- **`choiceHistoryOnInput`** on attributes — controls history-based auto-completion when entering a reference value.
- **Default for `quickChoice`** aligned with real configurations: catalogs / chart-of-characteristic-types / chart-of-accounts / chart-of-calculation-types / exchange plans default to `false`; enums default to `true` (≈95% / ≈99% match across real configs).
- **Manager modules** are now created alongside the object module for **reports and data processors** — required for reports that override `НастроитьВариантыОтчета`. Constants get manager and value-manager modules; enums get a manager module.
- **Empty `Ext/` folders** no longer created for constants, enums and document journals — they previously caused the platform to wipe extension modules on load.
- **Register-attribute properties** are filtered by register kind: AccumulationRegister / AccountingRegister / CalculationRegister attributes no longer get attribute-only properties the platform silently dropped. InformationRegister keeps the full set.
- **System enum values** in properties (`RegisterType`, `WriteMode`, `Periodicity`, …≈20 more) now accept synonyms and are case-insensitive — typical model errors like `Balances` → `Balance` or Russian variants no longer break the build.
- **Strict validation of enum values**: an unknown value for a known property gives a clear error instead of leaking into XML.
- **Format version** auto-detected from the nearest `Configuration.xml` (8.3.27+, 8.5).

#### `meta-edit`

- Same synonym dictionary and case-insensitivity for system enum values, applied in `modify-attribute` / `modify-property` and when parsing `fillChecking` / `indexing`.

#### `meta-validate`

- Empty register check (no dimensions, no resources, no attributes — platform refuses to load).
- Document-movements pointing to a non-existent register are reported.

#### `meta-remove`

- Returns exit code 1 when the object is not found (was silently 0).

## mxl-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) `2e75b0f`, compiler and decompiler together (they share the DSL): `mxl-compile` v1.4 → **v1.61**, `mxl-decompile` v1.0 → **v1.32**, `mxl-info` v1.2 → **v1.7**, `mxl-validate` v1.1 → **v1.11**. The DSL is now described in our own reference [`mxl-dsl-spec.md`](../tools/1c-mxl-compile/mxl-dsl-spec.md) (English, written from upstream's `docs/mxl-dsl-spec.md` and `mxl-compile/reference/*.md`; upstream's test snapshots are not vendored); [mxl-manage.md](mxl-manage.md) was rewritten around it.

- **Fixes:** `parameter`, `detailParameter`, area / drawing names and `faceName` are XML-escaped (9b202555, upstream #121 — `Discount <> 0` gave an unloadable layout); `mxl-decompile` writes to an absolute `-OutputPath` (ccbbecbc — it was glued onto the cwd); `mxl-compile` creates the destination directory (4833c3b7); a cell without `col` is laid out instead of becoming column −1 (f33436ad); texts in every template language, not only `ru` (fc792bfe); fractional font sizes are kept (f6a478c8); a cell with only a drill-down parameter is kept (66bb2856).
- **New DSL:** column layouts (`columnSets`, area `columnSet`) and named areas bound to them (`namedAreas`, b32bb589); `columnStyles`; row format; every format property in styles; multilingual text and `textLanguages`; input-field cells — `valueType`, `controlType` (the key was `control` upstream for a while, renamed after our pin, so it never existed here), `value`; cell notes; row / column groups; header, footer and `printSettings`; the picture palette and drawings; font references. `mxl-validate` gained checks 13 (input-field cells) and 14 (groups) and reports malformed XML with its location; `mxl-info` too.
- **Format:** the version is taken from the target `Configuration.xml` / external-object root (2.17 outside a configuration); 2.21 adds `xmlns:pal` (5c3449d6).
- **Behaviour changes:** an unknown enum value, line style, `printSettings` key, `controlType` or drawing type is now exit 1 instead of being dropped (v1.4 silently ignored e.g. `valign: "bottom"`, which is now honoured); enum values are case-insensitive; the old spellings `align`, `valign`, `wrap`, `border` as a side list and `borderWidth` are synonyms; a format gets a font only from a style's `font` key (`fonts.default` is no longer applied to every format); unstyled cells reference no format. The decompiler emits canonical keys and positional cells.
- **Round trip:** upstream rebuilds 7 of 10 platform-made layouts of its control set byte-for-byte; the other three differ only in stale column widths left in cell formats. With our scripts, 13 of upstream's 14 Configurator-saved round-trip fixtures rebuild byte-for-byte (the 14th, a vendor print form, loses only palette leftovers: stale widths / heights in cell formats, a zero-height row format). Merges not bound to a cell, chart contents and the print area are still lost.
- **Local deltas kept:** `.dev.env` `SUPPORT_GUARD` first and fail-closed on an unreadable `ParentConfigurations.bin` in `mxl-compile` (the one merge conflict — kept beside upstream's `ProviderPath` / `GetFullPath` lookup).
- **Local deviations, new:** `mxl-compile` runs the support guard *before* creating the destination directory (upstream created it first, so a refusal left an empty directory); writes `printSettings` after the named items, where 8.3.27 and 8.5.1 put it (upstream wrote it before `<merge>`; its only platform fixture had neither merges nor named items); refuses a control kind such as `"checkbox"` in the base64 `control` key (it went into the XML as garbage settings). `mxl-decompile`: a layout with exactly one row group (and no column groups) threw "A hash table can only be added to another hash table" — the PowerShell port unrolled the single-group array; fixed at the call site.
- **Verified** on throwaway file infobases: a compiled layout with header / footer, print settings, input-field cells, a note, a row group, a bound column layout, a picture and escaped `<` / `&` builds into an EPF and dumps back on 8.3.27 and 8.5.1; the platform's dump decompiles and recompiles byte-for-byte (8.5.1 into a 2.21 tree, with `xmlns:pal`). Pinned by `tools/tests/metadata-tools-regression.ps1` (eight MXL cases).

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `mxl-compile` v1.1 → **v1.4**, `mxl-info` v1.0 → **v1.2**; `mxl-decompile` / `mxl-validate` unchanged. `mxl-compile` enforces the vendor support gate ([support-manage.md](support-manage.md)); `mxl-info` prints the support state of the layout's owner.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-mxl-validate/scripts/mxl-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both `Template.xml` and a folder path; universal `-Path` parameter alongside legacy `-TemplatePath`.

The compile/decompile/info scripts (`mxl-compile`, `mxl-decompile`, `mxl-info`) were not refreshed — no significant upstream changes for them in this period.

## role-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `role-compile` v1.8 → **v1.49**, `role-info` v1.2 → **v1.7**, `role-validate` v1.1 → **v1.10**; new tool **`role-edit` v1.11** (`tools/1c-role-edit/scripts/`).

- **`role-edit`** edits an existing role in place (rights with cascade, deny, RLS rows by field list, templates, flags, synonym / comment, `@file` values, `-DefinitionFile` batches); the UUID and the other entries are kept. The `SKILL.md → Hard rule` exception for hand-editing `Rights.xml` is withdrawn; `metadata-xml-workarounds.md` follows.
- **Services:** `HTTPService.X: Use` (and `WebService` / `IntegrationService`) is expanded to one entry per URL-template method / operation / channel from the service metadata; a right on the service root is an error in `role-validate` (the routes answered 403). The old docs taught the root form.
- **Warnings became errors:** a type without rights (`Enum`, `CommonModule`, …), an unknown type or right, an impossible nested kind — `role-compile` refuses before writing (all reasons at once, exit 1), `role-validate` exits 1. A rights block on an enum made the configuration hang on load.
- **Platform shape:** rights closure (`Edit` → `Read`, `Update`, `View`, …), the platform order of `<right>` and `<object>` nodes, values equal to the role default not stored from format 2.19.
- `role-compile`: RLS condition and template body from `@file`; format version from `Configuration.xml` measured in characters (fae22435).
- `role-validate`: `PositionalBinding=$false` — a second positional argument no longer binds to `-OutFile` and overwrites e.g. `Roles/X.xml` with the report (83d63fac); the `Rights.xml` version must equal `Roles/<Name>.xml` (error), a role version different from the dump is a warning; `-MaxErrors` really stops; messages in English.
- Docs: the compile section named `-RolePath` — the parameter is `-JsonPath`. Rights tables replaced with upstream's; `dsl-reference.md` re-vendored from `2e75b0f`.

Local deltas re-applied: support guard from `.dev.env` `SUPPORT_GUARD`, fail-closed on an unreadable support state, stderr notice on other guard errors (`role-compile`, `role-edit`); `role-compile` registration position from `.dev.env` `NEW_OBJECT_POSITION` (as `cf-edit`). Deviations in `role-edit`: the sibling validator is `..\..\1c-role-validate\scripts\role-validate.ps1`, its absence is refused before the edit (upstream skipped it silently) and its exit code is the run's result (upstream ignored it); the compact-tag pass keeps processing instructions verbatim, as in `skd-edit` / `cf-edit`. The rights tables of `role-edit` and `role-compile` are identical. No Python port is shipped.

Platform check (8.3.27.2130, throwaway file infobase): a role made by `role-compile` and changed by `role-edit` (`add-rights` on two reports, `deny-rights` on an attribute) keeps its UUID, passes `role-validate`, loads with `/UpdateDBCfg` and dumps back byte-identical; `role-compile` refuses `Enum.X: Read` with exit 1.

Local gate (same sync): `role-compile` refuses an existing `Roles/<Name>.xml` unless `-Force` (exit 1, nothing written) — a recompile gives the role a new uuid, as `meta-compile` does for objects; existing roles are changed with `role-edit`. Upstream overwrites. Regression case: refusal without `-Force`, replacement with it.

### Local fix `2026-10-14` — `role-validate` parameters, rights-only edits

The validate section described `-MetadataPath`, which `role-validate.ps1` does not have (the call failed with a PowerShell parameter error; support ticket d3372592): the metadata file is located from the `Rights.xml` path. The section now lists the real parameters (`-RightsPath` / `-Path`, `-OutFile`, `-Detailed`, `-MaxErrors`). The manual fallback for rights-only edits of an existing role contradicted `SKILL.md → Hard rule`; it is now one of its documented exceptions, because no tool edits a role in place.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `role-compile` v1.5 → **v1.8**, `role-info` v1.0 → **v1.2**, `role-validate` → **v1.1**. `role-compile` enforces the vendor support gate ([support-manage.md](support-manage.md)); `role-info` prints the support state.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-role-{compile,info,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`role-compile`** — `OutputDir` now accepts the source root of the configuration; `Roles/` is created automatically. Legacy behaviour (path already ending in `Roles`) is preserved. The DSL key `rights` is accepted as a synonym of `objects`.
- **`role-validate`** — auto-discovers metadata from the path to `Rights.xml`; `-MetadataPath` is no longer required, metadata-driven checks always run when the file is present.
- **All 10 validators** (`role-validate`, `meta-validate`, `epf-validate`, `skd-validate`, `cf-validate`, `cfe-validate`, `form-validate`, `mxl-validate`, `subsystem-validate`, `interface-validate`) now emit a single one-liner by default; the full per-check trace is available via `-Detailed`. Each accepts a folder path as the primary file argument and resolves to the canonical XML file (e.g. `Roles/MyRole` → `Roles/MyRole/Ext/Rights.xml`). The universal `-Path` parameter is supported in addition to the legacy named parameters (`-RolePath`, `-FormPath`, `-TemplatePath`, `-ObjectPath`, …).

## skd-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `skd-compile` v1.109 → **v1.141**, `skd-edit` v1.30 → **v1.50**, `skd-decompile` v0.91 → **v0.108**, `skd-info` v1.8 → **v1.14**, `skd-validate` v1.2 → **v1.9**; new tool `v8-xsd-fetch` **v1.2** (`tools/1c-v8-xsd-fetch/`, PowerShell only, with `templates/README.md`). Full DSL spec re-vendored.

- **XSD element order** (#101): calculated field `valueType` last, `useRestriction` flags in field/condition/group/order, `dataParameters` right after `filter`, grouping `filter` before `order` / `selection`, booleans as `true` / `false`. Before, the platform refused such a schema through XDTO ("Нарушен порядок следования значений свойств").
- **`skd-edit` inserts at the XSD position** (#119): `modify-filter` / `modify-dataParameter` no longer append `use` / `value` after `userSettingID` (an XDTO load error); `modify-dataParameter` removes every old list value, not only the first.
- **Value lists in `dataParameters`**: one `<dcscor:value>` per item instead of one glued `"A B C"` string; numbers take the schema parameter's type instead of `xs:string`; comma-separated shorthand lists in `skd-compile` and `skd-edit`.
- **Default variant** (#115): without `settingsVariants` the variant "Основной" now selects the declared fields with detail records — it used to produce an empty report; `[INFO]` / `[WARN]` hints name what was built or what is missing. `skd-decompile` keeps that variant.
- **`useRestriction` object form** of a data-set field is emitted (was ignored silently). `skd-info -Mode variant` prints `DataParams` again (`dcscor:item`). Decompile → compile keeps `autoFillFields` / `useQueryGroupIfPossible` (new DSL key) and the data-set `source`.
- **`skd-validate` checks against the platform XSD** when schemas are present, with fix hints (`must come before <X>`, `duplicate`, `not allowed in <P>`); without schemas the summary says `XSD not checked: <reason>` instead of a bare OK. Boolean values are checked without schemas; a lower-case root is a warning.
- Every script carries `[CmdletBinding(PositionalBinding=$false)]`.

Local deltas re-applied: the `.dev.env` `SUPPORT_GUARD` support guard (fail-closed on an unreadable support state) in `skd-compile` / `skd-edit` — the only conflict was `Get-EditMode`, resolved as our `.dev.env` block plus upstream's `ProviderPath` lookup; `skd-edit`'s compact-tag pass keeps skipping processing instructions as well as CDATA and comments (upstream's 4c64b97c guards only the latter two).

New local deltas:
- **`V8_XSD_PATH`** in `.dev.env` (relative to the `.dev.env` directory) is the schema directory of both `skd-validate` and `v8-xsd-fetch`; without it — `.v8-project.json` `xsdPath`, then `.v8-xsd` next to `.dev.env`. The "XSD not checked" note names the directory it looked in.
- **`v8-xsd-fetch` resolves the ref to a commit SHA** (`commits/<ref>`, media type `.sha`) before listing `git/trees/<commit>`; raw URLs and `source.json` carry that commit. Upstream took `sha` of `git/trees/<ref>`, documented as the tree SHA: today the API echoes the commit SHA there, so it works, but `raw.githubusercontent.com` answers 404 for a real tree SHA (checked 2026-11-01). A truncated tree listing is refused. `User-Agent` is set before every request — .NET Framework `WebClient` drops it after a request, and the API answers 403 without it.
- **`v8-xsd-fetch` writes `.gitignore` (`*`)** into the schema directory: the schemas are 1C-Soft property and are never committed.

Platform check (8.3.27.2130, throwaway file infobase): two reports built by `skd-compile` (calculated field with type and format, value lists of numbers and enum references in `dataParameters`, default variant) and edited by `skd-edit` (`modify-filter`, `modify-dataParameter`) pass `skd-validate` against the fetched 2.20 XSD, load with `/LoadConfigFromFiles` + `/UpdateDBCfg`, and dump back identical except a generated `dNp1` prefix.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `skd-compile` v1.104 → **v1.109**, `skd-edit` v1.24 → **v1.30**, `skd-info` v1.5 → **v1.8**, `skd-decompile` v0.90 → **v0.91**, `skd-validate` → **v1.2**.

- **Support gate** — `skd-compile` / `skd-edit` refuse to modify a schema of a locked typical configuration ([support-manage.md](support-manage.md)).
- **`skd-edit`** — parameter value lists in shorthand (paired with `skd-compile`).
- **`skd-info`** — `-Raw` flag for lossless round-trip extraction of the query text; prints the support state.
- Full DSL grammar vendored as [`skd-dsl-spec.md`](../tools/1c-skd-compile/skd-dsl-spec.md).

### Earlier Additions (upstream sync `w-2026-05-31`)

The PowerShell scripts under `tools/1c-skd-{compile,edit,info,validate}/scripts/` were refreshed again from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (`skd-compile` → v1.104, `skd-edit` → v1.24, `skd-info` → v1.5, `skd-validate` → v1.2), and the new `1c-skd-decompile` tool (draft, v0.90 — see section 5) was added. Highlights from the prior `w-2026-05-17` batch still apply:

#### `skd-edit` — new operations and flags

- `set-field-role` — replace a field role in one line with flag tokens (`@balance`, `@dimension`, `@account`, `@period`, `@required`, `@autoOrder`, `@ignoreNullValues`) and kv params (`balanceGroupName`, `balanceType`, `accountTypeExpression`, …). Closes the "temporarily disable role to debug" pattern.
- `modify-structure` — change groupings by name while preserving selection, order, filters, and conditional appearance.
- `clear-conditionalAppearance` — drop conditional appearance for a field.
- `add-drilldown` — wire detail processing to DCS resources across all named templates.
- `rename-parameter` — atomically rename a parameter and update `&Name` references in other parameters and in all variants.
- `reorder-parameters` — partial list (named ones go first in the given order, the rest keep relative order).
- `modify-parameter` — `use`, `denyIncompleteValues`, `availableValues` (single shot replaces the full list).
- `patch-query` `@once` flag — fail when the substring is missing or appears more than once. Multiline replacements are now correct; empty replacement (`old =>`) deletes the substring.
- `add-total` shortcut: `Func`, `Func(expr)`, or just a field name (non-aggregate functions become an identity expression).
- `set-structure`: comma in shorthand for several fields on one level; quotes in `@name=` are stripped on write; reference parameter types serialise with the right `xsi:type`; batch with `;;` is trimmed.
- `add-selection` accepts `@group=Name` and nested `Folder(...)`.
- `modify-filter` / `modify-dataParameter` preserve `Use=false` when the `@off` / `@on` flag is omitted (no longer silently flipped).
- `conditionalAppearance` — `OrGroup`, `DesignTimeValue`, `Format`. `#noFilter` / `#noOrder` / `#noGroup` flags now also work in `add-calculated-field`.

#### `skd-compile` — DSL upgrades

- `@autoDates` emits the canonical БСП pattern (`НачалоПериода` / `КонецПериода`, two date pickers, `useRestriction`). Shortcut requires the period filled (`use=Always` + `denyIncompleteValues=true`).
- Composite reference types: `"type": ["CatalogRef.A", "CatalogRef.B"]`.
- Multilingual titles / presentations: `{ "ru": "...", "en": "..." }`.
- Horizontal cell merge in templates via `>` (mirror of `|` for vertical) — two-level headers without hand-editing XML.
- Parameters: shorthand `[Title]`, array `availableValues`, `denyIncompleteValues`, flag `@hidden` (auto-`useRestriction`), `@valueList` / `valueListAllowed`, `dataParameters: "auto"` (preserves defaults across all parameter kinds).
- Templates: `drilldown` via `DetailsAreaTemplateParameter`, `groupHeaderTemplate`, `groupName`.
- Structure: `"GroupName[Field] > details"` for named groupings; object form `{ "items": [...] }`; `useRestriction` as an object `{ field: true }`.
- Reference values (chart of accounts, catalog, enum, document) in filters and conditional appearance auto-receive predefined presentations. `Format` parameter as multilingual string. `OrGroup` in conditional appearance via `or`.
- `Folder(Title: f1, f2)` in selection — for `SelectedItemFolder` with nested fields.
- Standard period parameter always serialised in canonical form — no diff after first re-save in Configurator.
- External SQL files via `"@path/to/file.sql"`.
- Compact area templates DSL: `rows`, `widths`, `style` with built-in presets (`header` / `data` / `subheader` / `total`), vertical merging, parameters in cells.
- Project-level user style preset at `<projectRoot>/presets/skills/skd/skd-styles.json` (auto-discovered by `skd-compile`).
- `dataSetLinks` accepts both DSL keys (`sourceExpr`, `destExpr`, `source`, `dest`) and XML keys (`sourceExpression`, `destinationExpression`, ...).
- `--from-object`-like discovery: pass a path to a report or processor folder to `skd-info`, the script finds the embedded DCS template by itself; if multiple — it lists them.
- 8.5 platform support across `cf-validate`, `cfe-validate`, `epf-validate`, `skd-validate`.

#### `skd-info`

- Field detail view (`-Mode fields -Name <Field>`) prints kv role parameters (`balanceGroupName`, `balanceType`, `accountTypeExpression`, …) on the Role line.
- Section `query` of `-Mode full` prints external dataset names when no queries exist (no more anonymous "(no query datasets)").

## subsystem-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`subsystem-compile` v1.9 → **v1.37**, `subsystem-edit` v1.7 → **v1.29**, `subsystem-info` v1.2 → **v1.7**, `subsystem-validate` v1.2 → **v1.8**.

- `subsystem-validate` **check 14**: stamped bodies (`Ext/CommandInterface.xml`, `Ext/Help.xml`) in the descriptor's version — ERROR; descriptor differs from the dump — WARN.
- `subsystem-compile` registers in the parent by raw-text insertion (the parent stays byte-identical except one line) and puts a new kind group at its canonical place; child stubs and the descriptor follow the configuration's format version (2.21 `xmlns:pal`); `Detect-FormatVersion` measures characters.
- Both: quotes in text are no longer escaped, missing kinds restored, operation values case-insensitive.

Local deltas re-applied: `.dev.env` `SUPPORT_GUARD` first with fail-closed parsing; sibling `subsystem-validate`, its exit is the exit code. Dropped as superseded: our DOM compact-XML save in `subsystem-compile` (upstream's raw-text insertion is stricter); `subsystem-edit` keeps the `<?…?>` branch of the compact-tag pass.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `subsystem-compile` v1.5 → **v1.9**, `subsystem-edit` v1.2 → **v1.7**, `subsystem-info` v1.0 → **v1.2**, `subsystem-validate` → **v1.2**.

- **Support gate** — `subsystem-compile` / `subsystem-edit` refuse to modify subsystems of a locked typical configuration; see [support-manage.md](support-manage.md).
- **`subsystem-info`** — prints the support state of the subsystem.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-subsystem-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`subsystem-compile` / `subsystem-edit`** — content of a subsystem accepts Russian and plural prefixes (`Справочник`, `Справочники`, `Catalogs`) and normalises them to the canonical `Catalog`. `subsystem-validate` flags surviving plural forms as an error.
- **Stub-files for child subsystems** are created automatically when the parent declares a child. Previously the `<Subsystems>` reference existed but the file did not — the platform silently ignored it, and stricter loaders started failing.
- Subsystem `objects` accepts `content` as a synonym (and vice versa).
- Validators got the universal improvements described in `role-manage.md` → "Recent Additions" (one-liner output by default, `-Detailed`, folder path auto-resolution).

## support-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`support-edit` v1.0 → **v1.3** (positional binding off; no behaviour change).

- `xdto-compile` / `xdto-edit` replaced their trimmed guard ("`ParentConfigurations.bin` exists → deny") with the shared per-object one: a configuration with modification on and nothing on support (header `{6,0,0,…}`, e.g. ERP) is allowed, as `meta-compile` allows it; a read-only one is still refused, now with the `support-edit` steps.
- The shared guard resolves `configSrc` from the `.v8-project.json` directory (fallback path only).

Local: `.dev.env` `SUPPORT_GUARD` wins in every copy, fail-closed on an unreadable bin. Regression case: `xdto-compile` on a K=0 configuration and on a locked one.

Local fix (same sync): the fail-closed branch also caught a `ParentConfigurations.bin` of 32 bytes or less — the empty container a configuration keeps once vendor support was removed completely (upstream spec: ~16 bytes; the `*-info` tools already reported it as "removed") — and refused every edit of such a configuration. All 19 PowerShell copies of `Assert-EditAllowed`, the three Python copies and the Claude Code hook now treat it as "nothing on support"; an unparseable larger file stays fail-closed. Pinned by `metadata-tools-regression.ps1` (meta-edit on both shapes) and the hook parity test.

## template-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`template-add` v1.10 → **v1.30**, `template-remove` v1.3 → **v1.9**.

- **HTML templates use the platform layout**: descriptor `Ext/Template.xml` (`<Help>` with `<Page>` entries) plus `Ext/Template/<lang>.html`. The old single `Ext/Template.html` is silently ignored by the platform (the template loads empty). Verified live on 8.3.27.2130: two pages survive `/LoadConfigFromFiles` + `/DumpConfigToFiles` with their text.
- **`-Lang`**: a repeated call adds a page in another language (the metadata and existing pages are never rewritten); a legacy `Ext/Template.html` is migrated to `Template/ru.html` with a warning, an ambiguous tree is refused; the code is validated before any write.
- Format version from the owner (EPF / ERF root first), 2.21 `xmlns:pal`; `<Template>` is inserted at the owner kind's canonical place; `Detect-FormatVersion` measures characters; an empty SpreadsheetDocument is a self-closing root.
- `template-remove`: an emptied `ChildObjects` becomes `<ChildObjects/>`; compact tags and EOL are kept.

Local deltas re-applied: `-ObjectName` as an absolute / relative object XML path (Local fix `2026-09-13`); `.dev.env` `SUPPORT_GUARD` first with fail-closed parsing; `template-remove` preflight parse, atomic root-XML write via a temp file, `-DryRun` / `-Force` (the missing-`-Force` refusal now really exits `2` — `Write-Error` under `Stop` used to end it with `1`); `<?…?>` skipped by the compact-tag pass; `[CmdletBinding(PositionalBinding=$false)]` added to both (upstream left them without it). Regression cases: HTML layout + second language, refused `-Lang`, removal gates.

### Local fix `2026-09-13` — object XML paths

`add-template.ps1 -ObjectName` accepts absolute and relative object XML paths and places the template beside the resolved object. Name-only configuration lookup and the EPF `ProcessorName` alias remain supported.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `template-add` v1.5 → **v1.10**, `template-remove` → **v1.3**. `template-add` enforces the vendor support gate — it refuses to add a template to a locked object of a typical configuration ([support-manage.md](support-manage.md)). `template-remove` keeps the local hardening (preflight parse, atomic root-XML write, `-DryRun` / `-Force`).

## web-manage.md

### Upstream sync 2026-11-01 (2e75b0f)

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `web-publish` v1.4 → **v1.17**, `web-info` v1.0 → **v1.7**, `web-stop` v1.0 → **v1.4**, `web-unpublish` v1.0 → **v1.4**. The Python ports stay ours; only `web_common.py` changed.

- **Extension SOAP services are published** (1eeea204): `publishExtensionsByDefault="true"` is now on `<ws>` too, in both runtimes; without it an extension's web service answered 500. The `<httpServices>` flag of the 2026-10-01 local fix stays.
- **Republish right after `web-stop` works** (9ae792a9): the port check counts listening sockets only, so `TIME_WAIT` leftovers (owner PID 0) no longer read as "port busy by Idle".
- **The bind address survives a republish** (933414f2, 68a2a11a): every `Listen` address of the managed block is kept, only the port changes; URLs follow the first address; stock `Listen` lines are commented whole. A PowerShell publication over a Python-made config no longer opens Apache on all interfaces.
- **`web-info`** (fbf4d4f9, 88535a75, b8cbb011, 0d4933f1, 933414f2): OData is detected by `<standardOdata enable>`, `+ext` marks extension services, `Listen 127.0.0.1:port` parses as host + port, a TCP probe says whether the port answers, the log section shows only `error` and above (without `AH02538`) and names the log file.
- **`-InfoBasePath` normalization** (8d9e6c46): quotes, whitespace and trailing separators are forgiven, `C:x` and inner quotes refused, a relative path is anchored at the project root; `ProviderPath` for UNC working directories (d7a66b63); `PositionalBinding=$false` in all four scripts (0a0322fa).
- Local deltas re-applied: `.dev.env` `PLATFORM_PATH` first, install dir or `bin\` accepted (the per-database `v8path` of `.v8-project.json` comes after it); `<httpServices publishExtensionsByDefault>`; the `web-unpublish` `-DryRun` / `-Force` gate; the working-directory default `-ApachePath`, now also in `web-info` and `web-stop` (upstream's four-levels-up default pointed inside the skills directory in our layout).
- New local fixes: `web-publish` XML-escapes `Usr` / `Pwd` / `File` / `Srvr` / `Ref` in `default.vrd` (a password with `&` produced an invalid descriptor) and refuses a quote or line break, as the Python port; the relative-path anchor is the `.dev.env` directory, not `.v8-project.json`; the `PidFile` / `ErrorLog` lines of the managed block survive a rewrite; `-AppName` is validated with the Python rule in `web-publish` and `web-unpublish` (no path segment reaches the recursive delete; `-All` and `-AppName` are exclusive); `web-info` masks `Pwd` and reads the effective `ErrorLog` (the managed block's, else the last directive); `web-stop` hints name our scripts. Python: a relative `-InfoBasePath` is anchored like `.dev.env` values, `C:x` refused.
- Tests: `tools/tests/web-ops-regression.ps1` (new, PowerShell scripts end to end with a fake `httpd.exe`); `web-python-regression.py` pins the `<ws>` flag and the path anchor. Verified live on 8.3.27 (x86) with a Win32 Apache 2.4.69: Python publish on loopback → PowerShell republish over it (bind address, `PidFile`, `ErrorLog` kept; the 1C module answered with the escaped VRD) → `web-info` → `web-stop` → immediate republish → `web-unpublish -DryRun` / `-Force`.

### Local fix `2026-10-01` — extension HTTP services are published

`web-publish` (both runtimes) writes `publishExtensionsByDefault="true"` on `httpServices` in `default.vrd`, as the platform's own publication does; without it the HTTP services of the infobase's extensions were not published.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `web-publish` v1.2 → **v1.4**; `web-info` / `web-stop` unchanged; `web-unpublish` keeps the local `-DryRun` / `-Force` safety gate.

- **OData is enabled correctly in `default.vrd`** — via the `<standardOdata enable="true"/>` child element instead of the old `enableStandardOdata` attribute, which the platform ignored. Publications that need the standard OData interface actually get it now.
- Platform path resolution follows the `db-*` chain (explicit → `.dev.env` → `.v8-project.json` → auto-detect), locally patched to also accept the version install directory shape used by `.dev.env` `PLATFORM_PATH` (resolves `bin\` for `wsap24.dll`).

## xdto-manage.md

### Upstream sync `2026-11-01` (`2e75b0f`)

`xdto-compile` v1.1 → **v1.18**, `xdto-edit` v1.0 → **v1.9**, `xdto-decompile` v1.0 → **v1.3**, `xdto-info` v1.0 → **v1.3**, `xdto-validate` v1.1 → **v1.7**.

- `xdto-compile` stamps the package with the `Configuration.xml` format version (was hard-coded 2.17), 2.21 `xmlns:pal`; registration in `Configuration.xml` follows the kind order and `NEW_OBJECT_POSITION`.
- `xdto-compile` / `xdto-edit` use the shared support guard (see `support-manage.md`).
- `xdto-validate`: English messages; a `-MaxErrors` stop is reported.

Local deltas re-applied: `.dev.env` `SUPPORT_GUARD` and `NEW_OBJECT_POSITION` first; `xdto-edit` takes `xdto-decompile` / `xdto-compile` / `xdto-validate` from its own `scripts` dir. Deviation: a missing `xdto-validate` or its non-zero exit is now the exit code of `xdto-edit` (upstream prints `[SKIP]` / ignores the result and exits 0), like the other editing tools.
