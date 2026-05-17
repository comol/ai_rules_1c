# 1C Database Manage — Registry and Platform Operations

Comprehensive database management: registry (.v8-project.json) and platform operations (create, run, update, dump/load configuration).

---

## Part 1: Database Registry (.v8-project.json)

Manages the `.v8-project.json` file — the project's infobase registry. Stores connection parameters, aliases, Git branch bindings.

> **Relationship with `.dev.env`.** Across the rest of the 1c-rules toolkit (slash commands `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test`, the `1c-tester` subagent and all on-demand rules), the **single source of truth** for project parameters — including the current dev infobase — is `.dev.env` at the project root (created by the 1c-rules installer). `.v8-project.json` is an **optional advanced multi-base registry** for the `1c-metadata-manage` skill scripts when you need to juggle several infobases bound to Git branches/aliases. When both files are present, keep them in sync: the `default` entry in `.v8-project.json` should mirror `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`, `EXTENSION_NAME`, `PLATFORM_PATH` (`v8path`) from `.dev.env`. For single-base projects `.v8-project.json` is not required at all — the skill scripts accept the same parameters via command-line flags driven by `.dev.env` values.

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

If `v8path` is not set in config:

```powershell
$v8 = Get-ChildItem "C:\Program Files\1cv8\*\bin\1cv8.exe" | Sort-Object -Descending | Select-Object -First 1
```

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
| `-V8Path <path>` | Platform bin directory (auto-detect if not set) |
| `-InfoBasePath <path>` | File infobase path |
| `-InfoBaseServer <server>` | 1C server (for server databases) |
| `-InfoBaseRef <name>` | Database name on server |
| `-UserName <name>` | User name |
| `-Password <password>` | Password |

Either `-InfoBasePath` or the `-InfoBaseServer` + `-InfoBaseRef` pair is required.

### Database Resolution

Read `.v8-project.json` from the project root. Take `v8path` and resolve the database (see Part 1 for the full algorithm). If `v8path` is not set — auto-detect platform.

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
| `-Dynamic <+/->` | `+` dynamic update, `-` disable |
| `-Server` | Server-side update |
| `-WarningsAsErrors` | Treat warnings as errors |

**Warning**: Non-dynamic update requires exclusive database access (all users must exit).

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

After loading: offer to run `db-update` to apply changes to the database.

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
| `-Extension <name>` | Dump extension |
| `-Format <format>` | `Hierarchical` (default) / `Plain` |

#### Dump Modes

| Mode | Description |
|------|-------------|
| `Full` | Full dump — all configuration objects |
| `Changes` | Incremental — only changed since last dump (uses ConfigDumpInfo.xml) |
| `Partial` | Partial — selected objects from `-Objects` parameter |
| `UpdateInfo` | Update only ConfigDumpInfo.xml without dumping files |

> **When dumping**: if user doesn't specify dump type (full or incremental), ask before executing.

---

### 7. Load Configuration from XML

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-load-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "src/cf" -Mode Full
```

> **Warning**: Full load **replaces the entire configuration**. Request user confirmation.

| Extra Parameter | Description |
|-----------------|-------------|
| `-ConfigDir <path>` | XML source directory (required) |
| `-Mode <mode>` | `Full` (default) / `Partial` |
| `-Files <list>` | Relative file paths comma-separated (for Partial) |
| `-ListFile <path>` | File with path list (alternative to `-Files`) |
| `-Extension <name>` | Load into extension |
| `-Format <format>` | `Hierarchical` (default) / `Plain` |

After loading: offer to run `db-update`.

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
| `-Extension <name>` | Load into extension |
| `-DryRun` | Only show what would be loaded (no actual load) |

#### Change Sources

| Source | Description |
|--------|-------------|
| `All` | All uncommitted: staged + unstaged + untracked |
| `Staged` | Only indexed (git add) |
| `Unstaged` | Modified but not indexed + untracked |
| `Commit` | Files from commit range (requires `-CommitRange`) |

After loading: offer to run `db-update`.

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
| 1 | Error (check log) |

### Important

- **DO NOT READ the scripts — just RUN them**
- After any load operation, suggest running `db-update`
- Check logs after execution and show results to user

---

## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-db-ops/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`db-load-xml`** — strict log parsing. Catches "Неверное свойство объекта метаданных", "Неизвестное имя типа" and similar messages that the platform writes to the log despite a formal "success" exit. Previously a partial silent metadata loss was reported as a green run.
- **`db-load-xml` / `db-load-git`** — `-UpdateDB` flag combines load + database update in a single Configurator launch (was two separate calls).
- **`db-load-git`** — picks up changes to HTML help (`ru.html` and similar) via partial load even without the accompanying `Help.xml` in the commit. Previously such edits were silently dropped and the help text in the base stayed stale. Fixed search for changed files when sources live in a nested folder of the repo (`src/cf` etc.); path normalisation for the configuration directory is corrected. Python port: Cyrillic paths in git output no longer break on Windows (explicit UTF-8 decoding).
- **db-list** — already fully described in Part 1 of this doc (registry of `.v8-project.json`). It is a no-script skill in upstream — the agent reads / writes the JSON directly. No script files were added under `tools/`.

## MCP Integration

- **metadatasearch** — Verify object names when doing partial loads.
- **get_metadata_details** — Get object structure for verifying load targets.
- **docsearch** — Platform documentation on Designer command-line parameters.

## SDD Integration

When creating or modifying databases as part of a project, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: If the database setup is part of a tracked change, note the environment configuration in the active proposal under `openspec/changes/<change-id>/design.md`.
