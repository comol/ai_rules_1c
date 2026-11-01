# 1C Database Manage — Registry and Platform Operations

Comprehensive database management: registry (.v8-project.json) and platform operations (create, run, update, dump/load configuration, extensions in the infobase).

## Integration with configuration synchronization

Read `content/rules/getconfigfiles.md → Configuration file synchronization contract` for transfer scope, object lists vs file lists, baseline handling and failure boundaries. `/loadfrom1cbase` orchestrates directory refresh (full / changes / partial via `/getconfigfiles`); `/update1cbase` orchestrates full / partial / Git load, checks and database apply; `/deploy-and-test` inherits that deployment sequence.

These scripts implement individual stages. When a database update is already requested, continue from a successful load through the required checks to `db-update`; do not stop to offer the already requested next stage. Keep load and apply separate (omit loader `-UpdateDB`) when the orchestrator must run extension applicability checks between them. Use one executor per stage and the same infobase, extension and source root throughout.

---

## Part 1: Database Registry (.v8-project.json)

Manages the `.v8-project.json` file — the project's infobase registry. Stores connection parameters, aliases, Git branch bindings.

> **`.dev.env` is the single source of truth — `.v8-project.json` is an optional fallback.** Across the whole 1c-rules toolkit the authoritative file for project parameters is **`.dev.env`** at the project root (created by the installer). The vendored scripts natively read `.v8-project.json` (that is upstream's config); a local patch inside their own lookup functions consults `.dev.env` **first**, so a project never has to maintain a second config:
>
> | Script looks for | Taken from `.dev.env` | Upstream fallback in `.v8-project.json` |
> |---|---|---|
> | Platform path | `PLATFORM_PATH` | `v8path` of the database record matching the connection, then the root `v8path` |
> | Extra `1cv8` arguments | `PLATFORM_ARGS` | `v8args` |
> | Extra `ibcmd` arguments | `IBCMD_ARGS` | `ibcmdargs` |
> | Support-guard reaction | `SUPPORT_GUARD` | `editingAllowedCheck` |
> | Repository credentials (`db-load-xml`, `db-load-git`, `db-dump-xml`, `db-update`, `db-cfe-admin`) | `REPOSITORY_PATH`, `REPOSITORY_USER`, `REPOSITORY_PASSWORD` — the main configuration's repository | `databases[].repository`; an extension's own repository only as `databases[].extensions[].repository` |
> | Configuration dump for the `epf-build` source check | `EXPORT_PATH` (relative to the `.dev.env` directory; empty = the project root, used only when it holds `Configuration.xml`) | `databases[].configSrc` |
> | Extension applicability check after a load | — off unless `-ApplyCheck` (the gate is `/update1cbase` Step 2c) | `extensionApplyCheck: true` turns it on |
> | `epf-build` source check | — on unless `-Checks off` | `externalCheck: false` turns it off |
>
> Resolution order per value: explicit command-line parameter → `.dev.env` → `.v8-project.json` → built-in default (auto-detect for the platform, `deny` for the guard). For the platform that is `-V8Path` → `PLATFORM_PATH` → `v8path` of the matching database record → root `v8path` → auto-detect. An empty key in `.dev.env` counts as "not set" and falls through. Repository credentials passed to an infobase that is not bound to a repository are harmless (checked on 8.3.27.2130), so they are passed whenever they are known.
>
> Connection parameters (`INFOBASE_PATH`, `INFOBASE_KIND`, `IB_USER`, `IB_PASSWORD`, `EXPORT_PATH`, `EXTENSION_NAME`) are passed to the scripts as flags by the calling slash command (`/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test`) from the same `.dev.env`. **`.v8-project.json` is not required and not created by the installer** — describe it only if you deliberately want the upstream multi-base registry below (several infobases bound to Git branches / aliases). If you do create one, remember `.dev.env` still wins for the values in the table.

### Usage

```
1c-db-manage                    — show database list
1c-db-manage add                — add database (interactive)
1c-db-manage remove <id>        — remove database from registry
1c-db-manage show <id|alias>    — show database details
```

### .v8-project.json Format

File is placed at the project root (next to `.git/`).

```json
{
  "v8path": "C:\\Program Files\\1cv8\\8.3.25.1257\\bin",
  "databases": [
    {
      "id": "dev",
      "name": "Development",
      "type": "file",
      "path": "C:\\Bases\\MyApp_Dev",
      "user": "Admin",
      "password": "",
      "aliases": ["dev", "разработка"],
      "branches": ["dev", "develop", "feature/*"],
      "configSrc": "C:\\WS\\myapp\\cfsrc"
    },
    {
      "id": "test",
      "name": "Test",
      "type": "server",
      "server": "srv01",
      "ref": "MyApp_Test",
      "user": "Admin",
      "password": "123",
      "aliases": ["test", "тест"]
    }
  ],
  "default": "dev"
}
```

### Root Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `v8path` | string | 1C platform bin directory. Optional — auto-detect if not set |
| `databases` | array | Array of databases |
| `default` | string | Default database id |

### Database Object Fields

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `id` | string | yes | Unique identifier (Latin, no spaces) |
| `name` | string | yes | Human-readable name |
| `type` | `"file"` / `"server"` | yes | Connection type |
| `path` | string | for file | Path to file infobase directory |
| `server` | string | for server | 1C server address |
| `ref` | string | for server | Database name on server |
| `user` | string | no | 1C user name |
| `password` | string | no | Password |
| `aliases` | string[] | no | Alternative names for quick access |
| `branches` | string[] | no | Git branches or glob patterns (`release/*`, `feature/*`) bound to this database |
| `configSrc` | string | no | Configuration XML export directory |
| `v8path` | string | no | Platform of this database — wins over the root `v8path` (not over `.dev.env` `PLATFORM_PATH`) |
| `repository` | object | no | `{ "path", "user", "password" }` of the main configuration's repository |
| `extensions` | array | no | `[{ "name", "repository": { … } }]` — an extension bound to its own repository |

### Database Resolution Algorithm

This algorithm is used by ALL skills (`1c-db-ops`, `1c-epf-build`, `1c-epf-dump`, etc.) to determine the target database.

1. If user specified **connection parameters** (path, server) — use directly
2. If user specified **database by name** — search in order:
   1. By `id` (exact match)
   2. By `aliases` (match in array)
   3. By `name` (fuzzy match)
3. If user **didn't specify** a database — match current Git branch with `databases[].branches`:
   - Exact match: branch `dev` → `"branches": ["dev"]`
   - Glob pattern: branch `release/2.1` → `"branches": ["release/*"]`
4. If branch didn't match — use `default`
5. If not found or ambiguous — ask the user
6. If `.v8-project.json` not found — ask for connection parameters and offer to create the file

### Platform Auto-Detection

Only when neither `-V8Path`, nor `.dev.env` `PLATFORM_PATH`, nor a `.v8-project.json` `v8path` (database record or root) gives a value — the newest installed platform is picked:

```powershell
$v8 = Get-ChildItem "C:\Program Files\1cv8\*\bin\1cv8.exe" | Sort-Object -Descending | Select-Object -First 1
```

All three shapes of the path are accepted: the **version install directory** (the shape `PLATFORM_PATH` uses, e.g. `C:\Program Files\1cv8\8.3.27.2130` — resolved through `bin\`), the **`bin` directory**, or the **full path to the executable** (`1cv8.exe` or `ibcmd.exe`; naming `ibcmd` is how the `db-*` / `epf-*` tools switch engines).

### Connection String Formation

**File database:**
```
/F "<path>"
```

**Server database:**
```
/S "<server>/<ref>"
```

**Authentication** (added if user is set):
```
/N"<user>" /P"<password>"
```

> **Important**: No space between `/N` and username. No space between `/P` and password. If password is empty — omit `/P` entirely.

### Operations

#### Show Database List

Read `.v8-project.json`, output table:

```
ID      Name           Type     Path/Server              Default
dev     Development    file     C:\Bases\MyApp_Dev       ✓
test    Test           server   srv01/MyApp_Test
```

#### Add Database

Ask the user for: id, name, type (file/server), path or server+ref, user, password, aliases, branches. Add to `databases` array. If first database — set as `default`.

#### Remove Database

Remove from `databases` array by id. If removed was `default` — ask for new default.

#### Show Database Details

Output all fields for a specific database.

---

## Part 2: Platform Operations

Platform operations with 1C infobases via PowerShell scripts. All scripts share a common database resolution mechanism via `.v8-project.json` (see Part 1 above).

### Common Parameters

All scripts accept the same connection parameters:

| Parameter | Description |
|-----------|-------------|
| `-V8Path <path>` | Platform path passed to `-V8Path`: **version install directory** (same shape as `.dev.env` `PLATFORM_PATH`, e.g. `C:\Program Files (x86)\1cv8\8.3.27.2130`), **`bin` directory**, or full path to `1cv8.exe`. Scripts resolve `bin\1cv8.exe` automatically when the version root is supplied. Auto-detect if not set. |
| `-InfoBasePath <path>` | File infobase path |
| `-InfoBaseServer <server>` | 1C server (for server databases) |
| `-InfoBaseRef <name>` | Database name on server |
| `-UserName <name>` | User name |
| `-Password <password>` | Password |
| `-AdditionalV8Arguments <list>` | Extra `1cv8.exe` launch arguments, comma-separated (e.g. `/UseHwLicenses+`) |
| `-AdditionalIbcmdArguments <list>` | Extra `ibcmd` arguments, comma-separated, in `--key=value` form |
| `-RepositoryPath` / `-RepositoryUser` / `-RepositoryPassword` | Repository credentials (`/ConfigurationRepositoryF` / `N` / `P`) for `db-load-xml`, `db-load-git`, `db-dump-xml`, `db-update`, `db-cfe-admin`. Default: `.dev.env` `REPOSITORY_*` (main configuration only), then the registry record |

Either `-InfoBasePath` or the `-InfoBaseServer` + `-InfoBaseRef` pair is required. A relative `-InfoBasePath` resolves from the project root (the nearest directory with `.dev.env` or `.v8-project.json`); other relative paths resolve from the working directory. Only absolute paths reach the platform: `ibcmd` would read a relative `--db-path` from its temporary `--data` directory.

**Additional arguments are validated, not passed through blindly.** The platform accepts only one batch operation per launch, and a duplicate connection / output key fails with an opaque 1C error — so the scripts reject any argument the tool owns itself (`/F`, `/S`, `/N`, `/P`, `/DumpIB`, `/UpdateDBCfg`, `--db-path`, `--out`, …) and name the proper parameter instead. Batch commands are refused too (`/CheckConfig`, `/CheckModules`, `/CheckCanApplyConfigurationExtensions`, `/DumpDBCfgList`, `/DeleteCfg`, `/UpdateCfg`, `/CompareCfg`, `/MergeCfg`, `/ManageCfgSupport`, `/RollbackCfg`, `/ConvertFiles`): a Designer command line runs only its **last** batch command, so a smuggled one would replace the tool's own operation while `/DumpResult` reports 0. Passing a `1cv8` argument to an `ibcmd` run (or vice versa) is also an error. Project-wide defaults live in **`.dev.env` as `PLATFORM_ARGS` / `IBCMD_ARGS`** (comma-separated) — same validation applies; the upstream `.v8-project.json` `v8args` / `ibcmdargs` keys remain as a fallback. Secrets (`/P`, `/UC`, `/WSP`, `/AWSP`, `/ConfigurationRepositoryP`, `--password`) are masked in the echoed command line.

### Launch and verdict

- **Batch verdict.** Every Designer launch — the operation itself, the opt-in applicability check, `db-cfe-admin`, the `epf-build` source check and the stub infobase — passes `/DumpResult` beside `/Out`; a non-zero result or a missing file turns exit code 0 into a failure (`content/rules/designer-batch-checks.md → The verdict is three signals`).
- **No false success.** An unhandled error inside a script (before or after the launch) exits 1 and prints the script line, not 0.
- **No hang on 8.5.** The platform is started with an explicit list of the three handles it may inherit, so a process it leaves behind (`crashpad_handler`) cannot hold the caller's output pipe open. Where `Add-Type` is blocked (AppLocker, Constrained Language Mode), the scripts fall back to `Process.Start` and still return when the platform exits.

### Database Resolution

Take the platform path from `.dev.env` `PLATFORM_PATH` (falling back to `.v8-project.json` `v8path`, then auto-detect) and the connection parameters from `.dev.env` (`INFOBASE_KIND`, `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`). Only when the project deliberately keeps a `.v8-project.json` multi-base registry does the alias / Git-branch resolution of Part 1 apply.

---

### 1. Create Infobase

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-create.ps1 -InfoBasePath "C:\Bases\NewDB"
```

| Extra Parameter | Description |
|-----------------|-------------|
| `-UseTemplate <file>` | Create from template (.cf or .dt) |
| `-AddToList` | Add to 1C infobase list |
| `-ListName <name>` | Name in the infobase list |

After creation: offer to register via `1c-db-manage add`.

---

### 2. Run 1C Enterprise

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-run.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin"
```

| Extra Parameter | Description |
|-----------------|-------------|
| `-Execute <file.epf>` | Auto-open external data processor |
| `-CParam <string>` | Launch parameter (/C) |
| `-URL <link>` | Navigation link (`e1cib/...` format) |

Launches 1C in background — control returns immediately.

---

### 3. Update Database Configuration

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-update.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin"
```

Applies main configuration changes to the database configuration (`/UpdateDBCfg`). Required step after `db-load-cf`, `db-load-xml`, `db-load-git`.

| Extra Parameter | Description |
|-----------------|-------------|
| `-Extension <name>` | Update extension |
| `-AllExtensions` | Update all extensions |
| `-Dynamic <on/off>` | `on` dynamic update, `off` turn it off. `auto` / `disable` (the `ibcmd` spellings) and `yes` / `no` are accepted too; `+` / `-` still work in-process, but a lone `-` never reaches the script through `powershell.exe -File` — PowerShell 5.1 exits silently |
| `-Server` | Server-side update |
| `-WarningsAsErrors` | Treat warnings as errors |
| `-ApplyCheck` | After an extension update, run `/CheckCanApplyConfigurationExtensions`; a refusal exits 1. Off by default — see below |

**Warning**: Non-dynamic update requires exclusive database access (all users must exit).

The update log is scanned after an exit-0 run: metadata rejections (`Неверное свойство объекта метаданных`, `Неизвестное имя типа`, …), a compatibility mode above the platform (`Для работы с конфигурацией необходима версия платформы не меньше …`) and the update's own `Ошибка [при] обновлени… конфигурации базы данных` exit **1** — the database configuration is not the one that was asked for.

**Extension applicability check is opt-in** in `db-update`, `db-load-xml`, `db-load-cf` and `db-load-git`. Upstream runs it after every extension load; here `/update1cbase` Step 2c is the gate (`/CheckModules`, then `/CheckCanApplyConfigurationExtensions`, between load and update), so the loaders do not add a second Designer pass. `-ApplyCheck` turns it on for a standalone call (a refusal then exits 1); `-NoApplyCheck` always wins; `.v8-project.json` `extensionApplyCheck: true` turns it on project-wide (refusal = warning, exit 1 only with `-StrictLog`).

---

### 4. Dump Configuration to CF

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -OutputFile "config.cf"
```

| Extra Parameter | Description |
|-----------------|-------------|
| `-OutputFile <path>` | Output CF file (required) |
| `-Extension <name>` | Dump extension |
| `-AllExtensions` | Dump all extensions |

---

### 5. Load Configuration from CF

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-load-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -InputFile "config.cf"
```

> **Warning**: Loading CF **completely replaces** the configuration. Request user confirmation before executing.

| Extra Parameter | Description |
|-----------------|-------------|
| `-InputFile <path>` | Input CF file (required) |
| `-Extension <name>` | Load as extension |
| `-ApplyCheck` / `-NoApplyCheck` | Extension applicability check after the load — off by default (section 3) |

After loading: offer to run `db-update` to apply changes to the database.

Within `/update1cbase` or `/deploy-and-test`, the apply stage is already part of the request: run the required checks, then continue to it.

---

### 6. Dump Configuration to XML

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "src/cf" -Mode Full
```

| Extra Parameter | Description |
|-----------------|-------------|
| `-ConfigDir <path>` | Export directory (required) |
| `-Mode <mode>` | `Full` / `Changes` (default) / `Partial` / `UpdateInfo` |
| `-Objects <list>` | Object names comma-separated (for Partial) |
| `-ObjectsFile <path>` | UTF-8 file with one object name per line (`#` comments allowed) — e.g. the list a repository `update` reported; merged with `-Objects` |
| `-Extension <name>` | Dump extension |
| `-AllExtensions` | Dump all extensions |
| `-Format <format>` | `Hierarchical` (default) / `Plain` |

#### Dump Modes

| Mode | Description |
|------|-------------|
| `Full` | Full dump — all configuration objects |
| `Changes` | Incremental — only changed since last dump (uses ConfigDumpInfo.xml) |
| `Partial` | Partial — selected objects from `-Objects` parameter |
| `UpdateInfo` | Update only ConfigDumpInfo.xml without dumping files |

Choose the mode from the task and `/loadfrom1cbase → Select scope`; state the inferred choice instead of asking again when the scope is established. Partial mode accepts **metadata names**, not import file paths; include needed separate development objects explicitly. Check the dirty destination and a non-empty selection before running.

Designer mappings: `Full` → `/DumpConfigToFiles`; `Changes` → `-update` (**without** `-force`); `Partial` → `-listFile` generated from `-Objects`; `UpdateInfo` → `-configDumpInfoOnly`. Mode resolution:

- An object list (`-Objects` / `-ObjectsFile`) always means `Partial` — `-Mode Full` / `Changes` is ignored with a note (the list was silently dropped before). `UpdateInfo` with a list is refused.
- `Changes` into a directory with no dump yet (no `ConfigDumpInfo.xml`, no `Configuration.xml`; `.git`, a README are fine) runs as the first, full dump. A dump without `ConfigDumpInfo.xml` is refused — choose `-Mode Full` deliberately.
- `Changes` on a format-version mismatch (the directory was dumped by another platform) now fails with a hint instead of silently re-dumping every file; `-Mode Full` is the deliberate wider overwrite.

Missing baselines must be resolved before the run; `UpdateInfo` does not export files or establish that their contents match the infobase. Through `ibcmd`, a full export into a non-empty directory goes to a temp directory and is copied over `-ConfigDir`, like Designer writes it.

For `-getChanges` reports or `-configDumpInfoForChanges` delta exports, use the Designer procedure in the synchronization contract. This wrapper has no dedicated parameters for those modes. Keep their report/baseline/output paths distinct; a delta output directory must start empty.

---

### 7. Load Configuration from XML

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-load-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "src/cf" -Mode Full
```

> **Warning**: Full load **replaces the entire configuration**. Request user confirmation.

| Extra Parameter | Description |
|-----------------|-------------|
| `-ConfigDir <path>` | XML source directory (required) |
| `-Mode <mode>` | `Full` / `Partial`; when omitted — `Partial` if files are listed, otherwise `Full` |
| `-Files <list>` | Relative file paths comma-separated (for Partial) |
| `-ListFile <path>` | File with path list (alternative to `-Files`) |
| `-Extension <name>` | Load into extension |
| `-Format <format>` | `Hierarchical` (default) / `Plain` |
| `-UpdateDB` | Add `/UpdateDBCfg` to the same launch |
| `-ApplyCheck` / `-NoApplyCheck` | Extension applicability check after the load — off by default (section 3) |
| `-StrictLog` | Exit 1 when the log holds silent rejections (otherwise a warning) |

**A listed file set is always a partial load.** `-Files` / `-ListFile` without `-Mode` (or with `-Mode Full`, which is then ignored with a note) loads only the listed files on both engines; before this sync the 1cv8 branch defaulted to `Full` and **replaced the whole configuration**. Only a call without a list is a full load.

Partial mode accepts **file paths** through exactly one of `-Files` / `-ListFile`; validate scope, existence and dependencies first. A raw platform list is UTF-8 with no blank lines. The Designer branch writes its own list, adds `-partial -updateConfigDumpInfo`, and uses `-Format`; confirm the platform supports the intended flags. It excludes service files (`ConfigDumpInfo.xml`, `ParentConfigurations.bin`) from partial loading. If those exclusions omit part of the requested change, resolve the scope instead of reporting a complete deployment. A partial load with `-AllExtensions` is refused (Designer rejects it, `ibcmd` would load every extension whole) — load extensions one by one with `-Extension`.

After an exit-0 load the log is scanned for silent rejections — metadata dropped, or a compatibility mode above the platform (`Для работы с конфигурацией необходима версия платформы не меньше …`: the objects never reach the base). They are printed as a warning; `-StrictLog` makes them exit 1. In a repository-bound base the script adds the action to three platform messages: «текущая конфигурация помещена в хранилище» (a full load is impossible — lock the objects through `1c-repository-manage` and load partially), «… не захвачен в хранилище» (lock that object; the root «Конфигурация» is needed to add or remove a top-level object), «Соединение с хранилищем конфигурации не установлено» (set `REPOSITORY_*` in `.dev.env`, or the repository server is unreachable). When the list includes `Configuration.xml` (for example after a new object is borrowed into an extension), Designer reads every object file in the directory, not only the listed ones (reported on 8.3.27 extension loads): an unlisted file that does not load, such as a borrowed form referring to an unborrowed `CommonPicture` or `StyleItem`, fails the whole load. Run `cfe-validate` on the extension directory before such a load.

Standalone load-only requests finish after loading. In `/update1cbase` / `/deploy-and-test`, continue with checks and `db-update`; a successful import or updated baseline is not a completed database update.

---

### 8. Load Changes from Git

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-load-git.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "src/cf" -Source All
```

Determines changed configuration files from Git data and performs partial load into the infobase.

| Extra Parameter | Description |
|-----------------|-------------|
| `-ConfigDir <path>` | XML export directory (git repository, required) |
| `-Source <source>` | `All` (default) / `Staged` / `Unstaged` / `Commit` |
| `-CommitRange <range>` | Commit range for Source=Commit (e.g. `HEAD~3..HEAD`) |
| `-Extension <name>` | Load into extension (`-AllExtensions` is refused — one extension per partial load) |
| `-UpdateDB` | Add `/UpdateDBCfg` to the same launch |
| `-DryRun` | Only show what would be loaded (no actual load) |

#### Change Sources

| Source | Description |
|--------|-------------|
| `All` | All uncommitted: staged + unstaged + untracked |
| `Staged` | Only indexed (git add) |
| `Unstaged` | Modified but not indexed + untracked |
| `Commit` | Files from commit range (requires `-CommitRange`) |

Run `-DryRun` first to inspect the exact scope. Deletions are reported, not skipped silently: a deleted object description is applied only when its owner (`Configuration.xml` or the parent object) is in the load and no longer lists it in `ChildObjects` (`[note] удаление применится …`); every other deletion — a deleted module or `Ext/` file, an object whose owner did not change, anything in `Plain` format — is listed under `[ВНИМАНИЕ] Удаления, которые загрузка частями НЕ применит` and stays in the base until a full load. A change set that consists only of such deletions exits 1. Renames show up as a deletion plus an addition (`--no-renames`). `Configuration.xml` in the diff triggers a warning that the platform will load the whole configuration. Resolve deletions, renames, missing dependencies and excluded files before loading. A no-change plan is a no-op. The log is scanned for silent rejections as in section 7. After a successful load, follow the same checks → `db-update` sequence when database update was requested.

---

### 9. Dump Infobase to DT (backup / rollback point)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-dt.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -OutputFile "C:\backup\base.dt"
```

Dumps the **whole infobase** — configuration **plus data**, settings and users. Unlike `db-dump-cf` (configuration only), a `.dt` is a full snapshot: this is the backup / rollback point, not a metadata export.

| Extra Parameter | Description |
|-----------------|-------------|
| `-OutputFile <path>` | Output DT file (required) |

Take a DT dump before any irreversible operation: `db-load-dt`, a CF load over an existing base, a risky `db-update`, or a platform version upgrade.

---

### 10. Load Infobase from DT

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-load-dt.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -InputFile "C:\backup\base.dt"
```

> **Irreversible.** Loading a `.dt` **completely overwrites the infobase** — configuration *and* all data. Whatever is in the base now is lost. `db-update` afterwards is **not** needed: the database configuration is already in sync inside the snapshot.

Mandatory order before running it:

1. Offer to `db-dump-dt` the current state first — without it there is nothing to roll back to.
2. Ask for **explicit user confirmation** that data + configuration will be overwritten.
3. Only then execute.

| Extra Parameter | Description |
|-----------------|-------------|
| `-InputFile <path>` | Input DT file (required) |
| `-JobsCount <N>` | Background load jobs (`0` = one per CPU) |
| `-UnlockCode <code>` | Unlock code (`/UC`) when session start is blocked |

Do **not** use it to create a *new* base from a `.dt` — that is `db-create` from a DT template. To update configuration only (no data) — `db-load-cf` / `db-load-xml`.

If the base is busy (active sessions), the load fails: for a server base pass `-UnlockCode`, otherwise free the base and retry.

---

### 11. Extensions in the Infobase (`db-cfe-admin`)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-cfe-admin.ps1 -Command list -InfoBasePath "C:\Bases\MyDB"
```

The infobase side of extensions: what is connected, checks, connection properties, removal. Extension **sources** are [cfe-manage.md](cfe-manage.md); loading them is `db-load-xml -Extension` / `db-load-cf -Extension`, applying them `db-update -Extension`.

| Command | What it does | Runs through |
|---|---|---|
| `list` | Extension names (`/DumpDBCfgList -AllExtensions`, file or server base) and a property table: purpose, active, **safe mode**, **unsafe-action protection**, used in a distributed infobase, **scope** (`Информационная база` / `Область данных`). The properties come from `ibcmd`, so they are shown only for a file infobase with `ibcmd` next to `1cv8`; otherwise the columns read `—` and the reason is printed | 1cv8 (+ `ibcmd`) |
| `check` | `-Checks` (default `apply,modules`): `apply` — `/CheckCanApplyConfigurationExtensions`; `modules` — syntax check in `-Context` contexts (default `ThinClient,Server`; `WebClient`, `ExternalConnection`, `MobileClient`, … accepted); `config` — integrity, references, unreferenced procedures, handler existence, empty handlers. `modules` + `config` share one `/CheckConfig` launch. Only the extension is checked, not the main configuration. Without `-Name` — every extension. Any `/Out` line of the applicability check is a refusal: some refusals arrive with exit code 0 | 1cv8 |
| `set-properties` | `-SafeMode`, `-Active`, `-UnsafeActionProtection`, `-UsedInDistributedInfobase` (`on` / `off`), `-Scope infobase` / `data-separation`, `-SecurityProfile <name>`. Only the passed properties change; the state is re-read and a value that did not stick exits 1 | **`ibcmd`, file infobase only** |
| `delete` | Removes the extension **and its data** from the infobase, then re-reads the list | 1cv8 |

| Parameter | Description |
|---|---|
| `-Command <cmd>` | `list` / `check` / `set-properties` / `delete` (required) |
| `-Name <name>` (alias `-Extension`) | The extension. Required for `set-properties`; for `delete` — or `-All`. Omitted in `list` / `check` = all extensions |
| `-All` | `delete` only: every extension, removed one by one by name |
| `-DryRun` / `-Force` | `delete` and `set-properties` only: `-DryRun` prints the plan (exit 0), `-Force` applies it; neither → exit 2 |
| `-Checks`, `-Context` | `check` only, see above |

Safety:

- **An empty name never reaches the platform.** `-Name ""` / `-Extension ""` is refused in every command, and `delete` without a name needs an explicit `-All`. Reason: `/DeleteCfg -Extension ""` exits 0, writes `/DumpResult` 0 and deletes the **first** extension of the list (reproduced on 8.3.27.2130) — never compose that line by hand (`content/rules/designer-batch-checks.md → Never run these switches`).
- `delete` and `set-properties` mutate the infobase: follow the `INFOBASE_ROLE` gates, run `-DryRun` first, offer `db-dump-dt` before deleting an extension that holds data.
- **An extension that first reaches an infobase through a load is created in safe mode** (upstream observation; `ibcmd` is not part of the local 8.3.27 / 8.5.1 installs, so not re-measured here). Upstream reports that a module extension does not apply in that mode. Check `list`, and switch it off with `set-properties -SafeMode off -Force` when the extension needs it.
- `check` is the standalone form of `/update1cbase` Step 2c's applicability gate; inside `/update1cbase` the Step 2c ladder stays the gate.

Return codes: 0 — success / all checks passed / dry run; 1 — error, a failed check, a property that did not stick; 2 — `delete` / `set-properties` without `-Force`.

```powershell
# What is connected, with properties (file infobase with ibcmd)
... -Command list -InfoBasePath "C:\Bases\MyDB"
# Applicability + syntax of one extension, web-client context
... -Command check -InfoBasePath "C:\Bases\MyDB" -Name "Расш1" -Checks apply,modules -Context WebClient,Server
# Plan, then switch safe mode off
... -Command set-properties -InfoBasePath "C:\Bases\MyDB" -Name "Расш1" -SafeMode off -DryRun
... -Command set-properties -InfoBasePath "C:\Bases\MyDB" -Name "Расш1" -SafeMode off -Force
# Plan, then remove
... -Command delete -InfoBasePath "C:\Bases\MyDB" -Extension "Расш1" -DryRun
... -Command delete -InfoBasePath "C:\Bases\MyDB" -Extension "Расш1" -Force
```

---

### Common Workflows

#### Fix a Bug in a Data Processor

1. Dump: `db-dump-xml` or use `1c-epf-dump`
2. Edit BSL files
3. Build: `1c-epf-build`
4. Test: `db-run` with the built EPF

#### Load a Modified Module

```powershell
# Partial load of a single module
... db-load-xml ... -Mode Partial -Files "CommonModules/MyModule/Ext/Module.bsl"
```

Within a database update, continue with the applicable checks and `db-update`. If a source-directory refresh is also requested, use `/loadfrom1cbase` after successful apply, preserving local changes and the same extension scope.

#### Load Git Changes into Database

```powershell
# All uncommitted changes
... db-load-git ... -Source All
# Then apply
... db-update ...
```

### Return Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (check log); also any unhandled script error |
| 2 | `db-cfe-admin delete` / `set-properties` refused without `-Force` |

### Update retry discipline — mandatory for load / update operations

`db-load-cf` / `db-load-xml` / `db-load-git` / `db-update` failures are handled **iteratively**, mirroring `content/commands/update1cbase.md → Update retry loop`:

1. **Log after every attempt, success or not.** Exit code 0 does not prove success — the platform writes errors like `Неверное свойство объекта метаданных`, `Неизвестное имя типа`, `Ошибка при обновлении конфигурации базы данных` to the log while formally exiting clean. The scripts already close part of that gap: every Designer launch passes `/DumpResult` and turns a non-zero (or missing) batch result into a non-zero script exit, `db-update` fails on known failure lines in its log, and `db-load-xml` / `db-load-git` print them as a warning (exit 1 with `-StrictLog`). Still read the log output the script shows. A diagnostic line = failed attempt — but classify the platform's **success phrases first** (`Ошибок не обнаружено`, `Предупреждений: 0` contain the same word stems), otherwise a clean run reads as a failure. Order and pattern list — `content/rules/designer-batch-checks.md → The success-phrase trap`.
2. **Terminate a hung / failed Configurator before retrying.** A dead-but-alive Designer process holds the configuration lock, and every next attempt fails with `База данных заблокирована`. Kill only the process this run started (by PID with a timeout); never blanket-kill all `1cv8` processes — the user's own Designer / client sessions may be among them. A lock that survives your process's death is foreign — report it, do not kill further.
3. **Fix before retry.** Re-running against unchanged sources is forbidden. Fix the logged cause first (source XML/BSL — through this skill's tools plus `verify_xml` / `syntaxcheck`; parameters — in `.dev.env` / flags). After a failed **load**, restart from the load step, not from `db-update` — the half-loaded state is not trustworthy.
4. **Budget: 3 full attempts.** Then stop and report the last log fragment, the fixes applied between attempts, and the remaining error. A failed update is never reported as done.

### Important

- **DO NOT READ the scripts — just RUN them**
- Before an irreversible operation (`db-load-dt`, a CF load over an existing base, a risky `db-update`, a platform upgrade) — offer `db-dump-dt` as the rollback point
- After any load operation, suggest running `db-update` (exception: `db-load-dt` — the snapshot is already in sync)
- Check logs after execution and show results to user — following the retry discipline above on any failure

---

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
