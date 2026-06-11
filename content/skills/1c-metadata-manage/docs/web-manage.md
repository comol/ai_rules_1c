# 1C Web Manage — Web Publishing for 1C Information Bases

Publish and operate a 1C information base over HTTP via Apache (or IIS) for thin web clients, OData, HTTP services and SOAP.

Four script-backed operations: **info / publish / stop / unpublish**. They form a stable workflow:

```
web-info → web-publish → (use the base) → web-unpublish   (or web-stop to keep the publication, just halt Apache)
```

Interactive web-client / UI testing of the published base is **not** part of this skill — it is delegated to the `1c-tester` subagent and the `/deploy-and-test` flow (see section 5).

---

## Connection parameters

All operations resolve the target infobase from `.v8-project.json` in the project root (the same file used by `db-manage`):

1. If the user passed an explicit infobase path/server — use it directly.
2. If the user passed an alias — resolve via `databases[].id|alias|name`.
3. Otherwise — match the current git branch against `databases[].branches`.
4. Fallback — the entry marked `default: true`.

**Always pass through:**

- `v8path` → `-V8Path` (so we don't accidentally publish via the wrong platform version).
- `user` / `password` → `-UserName` / `-Password` (when stored).
- `webPath` → `-ApachePath` (when the project bundles its own Apache).

If `.v8-project.json` is missing — stop and ask the user to register the base via `db-manage` (or fall back to `.dev.env`).

---

## 1. Web info — current state

Reports whether Apache is running, which infobases are published and the last error from `error.log`.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-info.ps1 [-ApachePath <path>]
```

Default `-ApachePath` is `tools/apache24` relative to the project root.

Output should answer three questions:

- Is the HTTP server process alive (PID, uptime, port)?
- What publications exist (URL, infobase reference, application name)?
- Last 5 lines of `error.log` if any errors are present.

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
| `-AppName` | no | Publication name; defaults to the base directory name. |
| `-ApachePath` | no | Apache root, default `tools/apache24`. |
| `-Port` | no | HTTP port, default `8081`. |
| `-Manual` | no | Verify configuration only, do not download/start anything. |

`*` — provide either `-InfoBasePath` **or** the pair `-InfoBaseServer` + `-InfoBaseRef`.

**Idempotency.** Repeated invocation with the same `-AppName` replaces the publication. Use this to:

- switch the embedded user (same `-AppName`, new `-UserName`);
- restart Apache after `web-stop` (same parameters).

**Parallel publication for the same base under different users** (e.g. testing role-based access) — give each one a distinct `-AppName`:

- `-AppName bpdemo-ivanov` (rights of `Иванов`);
- `-AppName bpdemo-admin` (admin).

After success, report:

- Web client URL: `http://localhost:<Port>/<AppName>`.
- OData: `http://localhost:<Port>/<AppName>/odata/standard.odata`.
- HTTP services: `http://localhost:<Port>/<AppName>/hs/<RootUrl>/...`.
- Web services: `http://localhost:<Port>/<AppName>/ws/<Name>?wsdl`.

---

## 3. Web stop — halt without removing the publication

Stops Apache but keeps the publication entries in `httpd.conf` and the generated `default.vrd` files. The next `web-publish` call (or `web-stop -Start`) brings it back up unchanged.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-stop.ps1 [-ApachePath <path>] [-Force]
```

Use this when:

- finishing the working day on a developer machine;
- temporarily releasing the port for another service;
- before backing up infobase files to avoid platform locks.

---

## 4. Web unpublish — remove the publication

Stops Apache, removes the publication block from `httpd.conf`, deletes the corresponding `default.vrd`. The infobase itself is **not** touched.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-web-ops/scripts/web-unpublish.ps1 `
    -AppName <publication> `
    [-ApachePath <path>] [-KeepApacheRunning]
```

Pass `-KeepApacheRunning` if other publications must keep serving — by default the script restarts Apache after editing the config.

---

## 5. Web-client / UI testing — out of scope here

This skill stops at **publishing** the base. Interactive testing of the published web client (smoke checks, scripted UI scenarios, regression runs) is **not** bundled with `1c-metadata-manage` — it is handled by the dedicated **`1c-tester`** subagent and the `/deploy-and-test` slash command, which own the browser-automation tooling and read their parameters (`INFOBASE_PUBLISH_URL`, credentials) from `.dev.env`.

Typical hand-off after a successful `web-publish`:

1. Report the web-client URL (`http://localhost:<Port>/<AppName>`) and the OData / HTTP-service endpoints.
2. Delegate the actual UI verification to the `1c-tester` subagent (or run `/deploy-and-test`), passing that URL.

Test frameworks (TDD harnesses, Vanessa, YAxUnit) are intentionally not part of this toolkit.

---

## When to delegate to `metadata-manager`

- Multiple operations chained (`publish → … → unpublish`).
- Configuration changes that require platform restart in between.
- Custom Apache layout or non-default port mapping.

For a single read-only `web-info` or a one-shot `web-publish`, run the script directly — delegation overhead is not worth it.
