# 1C Web Manage — Web Publishing for 1C Information Bases

Publish and operate a 1C information base over HTTP via Apache (or IIS) for thin web clients, OData, HTTP services and SOAP.

Four script-backed operations: **info / publish / stop / unpublish**. They form a stable workflow:

```
web-info → web-publish → (use the base) → web-unpublish   (or web-stop to keep the publication, just halt Apache)
```

Interactive web-client / UI testing of the published base is **not** part of this skill — it is delegated to the `1c-tester` subagent and the `/deploy-and-test` flow (see section 5).

## Python runtime

The four commands also ship as `web-publish.py`, `web-info.py`, `web-stop.py`
and `web-unpublish.py` beside the PowerShell files. Run them with Python 3.9+
(`python3` on Linux); they use the standard library and `web_common.py`, not
PowerShell. The sections below describe the existing PowerShell workflow; the
following differences apply to Python:

- Provide a dedicated, already installed compatible Apache tree with
  `conf/httpd.conf` and a supported executable under `bin/` or `sbin/`.
  `-ApachePath` defaults to `tools/apache24` relative to the working directory;
  use an absolute path when running outside the project root. No download,
  service installation or elevation is performed. `-Manual` is accepted by
  publish for compatibility but does not turn it into a preview; use `-DryRun`.
- Supply the installed 1C web extension through `-WebExtension <file>` when
  discovery via `-V8Path` / `.dev.env` `PLATFORM_PATH` is insufficient. The
  module must match Apache, the platform and OS. Availability of Python alone
  does not establish Linux/macOS deployment support.
- Unset target and credential parameters come from `.dev.env`
  (`INFOBASE_KIND`, `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`). Any explicit
  file/server target replaces the target defaults as a whole; explicit empty
  credentials remain empty. A relative infobase path — from `.dev.env` or from
  `-InfoBasePath` — resolves against the `.dev.env` directory (the working
  directory without one), the same rule as PowerShell. Pass settings from a
  multi-base registry explicitly.
- Use a dedicated Apache configuration without external `Include` directives.
  Python binds it to `127.0.0.1`, restricts the publication to local requests
  and retains unrelated configuration outside its managed blocks. It is a
  local development publication workflow, not a general web-server manager.
- Only an Apache process started by these Python tools, with matching saved
  PID, executable and creation identity, can be stopped or restarted. An
  occupied port, foreign PID or process started by PowerShell/service tooling
  is not adopted. Stop that instance through its own authorized workflow first.
- `-DryRun` is available for publish, stop and unpublish and does not write or
  start/stop a server. Actual unpublish requires `-Force` and only removes
  selected managed publication directories; the infobase is untouched.
  Publish updates an existing managed publication and restarts its managed
  process. Failed updates restore previous configuration/publication files;
  failure to restart the previous server is reported separately.
- `web-info.py` reports managed process/publication state and the error-log
  path; it does not print connection strings or dump logs. Supplied credentials
  are still stored in the generated VRD, as in PowerShell; keep it outside
  version control and treat it as a local credential-bearing artifact.
- Exit codes: `0` successful operation/status, `1` dependency/execution/IO
  failure, `2` rejected parameters or safety boundary. A status command can
  successfully report that Apache is not installed or not running.

Example from the project root (substitute the verified paths for this project):

```sh
python3 skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-publish.py -ApachePath /srv/dev-apache -WebExtension /opt/1c/web-module -InfoBasePath /srv/test-base -AppName demo -DryRun
python3 skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-info.py -ApachePath /srv/dev-apache
python3 skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-unpublish.py -ApachePath /srv/dev-apache -AppName demo -DryRun
```

Use the skill's installed path prefix in place of `skills/` (see its path
convention). Offline regression tests exercise files, refusal paths and mocked
process operations (`tools/tests/web-python-regression.py`; the PowerShell
scripts in `tools/tests/web-ops-regression.ps1` with a fake `httpd.exe`); a real
Apache/1C deployment still needs verification in the target environment. Optional reusable UI suites live in
`content/skills/1c-ui-regression/SKILL.md`, not in these publication scripts.

---

## Connection parameters

All operations resolve the target infobase from **`.dev.env`** in the project root — the toolkit's single source of truth (see [db-manage.md](db-manage.md) → Part 1):

1. If the user passed an explicit infobase path / server — use it directly.
2. Otherwise take `INFOBASE_KIND`, `INFOBASE_PATH` (or server + ref), `IB_USER`, `IB_PASSWORD` from `.dev.env`.
3. Only if the project deliberately keeps a `.v8-project.json` multi-base registry — resolve by alias, then git branch, then the `default` entry.

**Always pass through:**

- `PLATFORM_PATH` → `-V8Path` (so we don't accidentally publish via the wrong platform version). The script also reads it from `.dev.env` itself when the flag is omitted; the install directory and its `bin\` are both accepted.
- `IB_USER` / `IB_PASSWORD` → `-UserName` / `-Password` (when set).
- `-ApachePath` — when the project bundles its own Apache (default: `tools\apache24` under the working directory, for all four scripts).

`-InfoBasePath` is normalized before it reaches `default.vrd`: surrounding whitespace / quotes and a trailing separator are dropped; a **relative** path is anchored at the project root — the directory of `.dev.env` (else `.v8-project.json`, else the working directory) — never at the platform's current directory; a drive-relative `C:x` or a quote inside the path is refused.

`wsap24.dll` must match Apache's bitness: a 32-bit platform (`Program Files (x86)`) needs a Win32 Apache. The automatic download fetches the Win64 build — install a Win32 Apache under `-ApachePath` yourself for an x86 platform.

If `.dev.env` has no infobase configured — stop and ask the user to fill `INFOBASE_PATH` rather than guessing.

---

## 1. Web info — current state

Reports whether Apache is running, which infobases are published and the latest errors of the Apache log.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-info.ps1 [-ApachePath <path>]
```

Default `-ApachePath` is `tools/apache24` relative to the working directory (the project root).

How to read the output:

- `Status` — our `httpd.exe` processes (PIDs); `[WARN]` names a foreign Apache.
- `Port: [host:]port (слушается | не отвечает)` — the `Listen` of the managed block (`Listen 127.0.0.1:19081` reads as host + port) and a 1-second TCP probe of that address. A live process with `не отвечает` means Apache did not come up (busy port, broken config). Publications themselves are not requested: a request starts a 1C session and takes a license.
- One line per publication: URL (by the bind address, else `localhost`), the connection string with the password shown as `Pwd=***`, and service tags `WS` / `HTTP` (`+ext` = extension services published too) and `OData`.
- `Журнал:` — the effective `ErrorLog` (the managed block's, else the last directive; builds differ between `error.log` and `error_log`). Only the last 5 lines of level `error` and above are printed; `AH02538` (trace of our own restart) is skipped. Read the file for anything else.

---

## 2. Web publish — register the infobase

Generates `default.vrd`, patches `httpd.conf`, downloads a portable Apache if needed, and starts the service.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-publish.ps1 `
    [-V8Path <path>] `
    [-InfoBasePath <path> | -InfoBaseServer <name> -InfoBaseRef <name>] `
    [-UserName <name>] [-Password <secret>] `
    [-AppName <publication>] [-ApachePath <path>] [-Port <port>] `
    [-Manual]
```

| Parameter | Required | Description |
|---|:--:|---|
| `-V8Path` | no | Platform `bin/` directory (used to locate `wsap24.dll`/`wsisapi.dll`). |
| `-InfoBasePath` | * | Path to a file infobase. |
| `-InfoBaseServer` | * | 1C cluster name (server-mode infobase). |
| `-InfoBaseRef` | * | Infobase reference on the cluster. |
| `-UserName` / `-Password` | no | Credentials embedded into `default.vrd`. |
| `-AppName` | no | Publication name; defaults to the base directory name. Letters, digits, `_`, `-` (up to 64), lower-cased; anything else is refused. |
| `-ApachePath` | no | Apache root, default `tools/apache24`. |
| `-Port` | no | HTTP port, default `8081`. |
| `-Manual` | no | Do not download a missing Apache; an already installed instance still follows normal publication/start behavior. |

`*` — provide either `-InfoBasePath` **or** the pair `-InfoBaseServer` + `-InfoBaseRef`.

**`default.vrd`.** The connection values (`File` / `Srvr` / `Ref` / `Usr` / `Pwd`) are XML-escaped, so a password with `&` or `<` is safe; a value containing a quote or a line break is refused before anything is written (the 1C connection string cannot carry it). `publishExtensionsByDefault="true"` is set on both `<ws>` and `<httpServices>`: without it an extension's SOAP service answers 500 and its HTTP service 404. The flag covers every extension applied to the infobase.

**Bind address and the managed block.** The first publication comments out the stock `Listen` lines and writes `# --- 1C: global ---` with `Listen <Port>` — all interfaces. To keep the publication local, edit that block to `Listen 127.0.0.1:<port>` (and `Listen [::1]:<port>` if needed) or publish once with the Python port. Every later publication keeps all bind addresses of the block and its `PidFile` / `ErrorLog` lines, changes only the port and the module path, and prints URLs by the first address.

**Port check.** Only a listening socket makes the port busy; the `TIME_WAIT` leftovers of an Apache just stopped by `web-stop` do not.

**Idempotency.** Repeated invocation with the same `-AppName` replaces the publication. Use this to:

- switch the embedded user (same `-AppName`, new `-UserName`);
- restart Apache after `web-stop` (same parameters).

**Parallel publication for the same base under different users** (e.g. testing role-based access) — give each one a distinct `-AppName`:

- `-AppName bpdemo-ivanov` (rights of `Иванов`);
- `-AppName bpdemo-admin` (admin).

After success, report the URLs the script prints (`<host>` is the bind address of the block, else `localhost`):

- Web client URL: `http://<host>:<Port>/<AppName>`.
- OData: `http://<host>:<Port>/<AppName>/odata/standard.odata`.
- HTTP services: `http://<host>:<Port>/<AppName>/hs/<RootUrl>/...` — the configuration's and its extensions'.
- Web services: `http://<host>:<Port>/<AppName>/ws/<Name>?wsdl` — the configuration's and its extensions'.

---

## 3. Web stop — halt without removing the publication

Stops Apache but keeps the publication entries in `httpd.conf` and the generated `default.vrd` files. Re-run `web-publish` with the same publication parameters to start it again.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-stop.ps1 [-ApachePath <path>]
```

Use this when:

- finishing the working day on a developer machine;
- temporarily releasing the port for another service;
- before backing up infobase files to avoid platform locks.

---

## 4. Web unpublish — remove the publication

Removes the publication block from `httpd.conf` and deletes the publication directory (including `default.vrd`). If this Apache instance is running, the script restarts it when other publications remain or stops it when none remain. The infobase itself is **not** touched.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-unpublish.ps1 `
    -AppName <publication> `
    [-ApachePath <path>] -DryRun

powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-unpublish.ps1 `
    -AppName <publication> `
    [-ApachePath <path>] -Force
```

Preview is mandatory in the workflow; the script refuses a real unpublish without `-Force` (exit `2`). Use `-All -DryRun` / `-All -Force` for all publications; `-All` and `-AppName` are exclusive. `-AppName` follows the publish naming rule, and a corrupted marker name in `httpd.conf` stops `-All` before any change, so no path segment ever reaches the recursive delete.

---

## 5. Web-client / UI testing — out of scope here

This skill stops at **publishing** the base. Interactive testing of the published web client (smoke checks, scripted UI scenarios, regression runs) is **not** bundled with `1c-metadata-manage` — it is handled by the dedicated **`1c-tester`** subagent and the `/deploy-and-test` slash command, which own the browser-automation tooling and read their parameters (`INFOBASE_PUBLISH_URL`, credentials) from `.dev.env`.

Typical hand-off after a successful `web-publish`:

1. Report the web-client URL (`http://localhost:<Port>/<AppName>`) and the OData / HTTP-service endpoints.
2. Delegate the actual UI verification to the `1c-tester` subagent (or run `/deploy-and-test`), passing that URL.

---

## When to delegate to `metadata-manager`

- Multiple operations chained (`publish → … → unpublish`).
- Configuration changes that require platform restart in between.
- Custom Apache layout or non-default port mapping.

For a single read-only `web-info` or a one-shot `web-publish`, run the script directly — delegation overhead is not worth it.

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
