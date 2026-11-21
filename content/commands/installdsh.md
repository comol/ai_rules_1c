---
description: Download DSH, the portable 1C build, from the vibecoding1c.ru personal cabinet and unpack it
argumentHint: "[status]"
userOnly: true
---

# /installdsh — DSH from the personal cabinet

DSH (DeepSeek Harness) is the vendor's specialised 1C build, and the ruleset works best in it. It is sold at https://vibecoding1c.ru/harnesses and downloaded only from the buyer's personal cabinet at https://vibecoding1c.ru/. The build is portable: this command downloads the archive and unpacks it. It runs no installer, needs no administrator rights and creates no registry keys or shortcuts.

## Boundaries

- **No download addresses in rules, memory, project files or chat.** The archive location is found anew in the cabinet on every run. Never hardcode, print or save a cabinet page address, a Yandex Disk link or a download `href`. The cabinet asks buyers not to share the link or the archives. Show the user only the file name, size and date.
- Credentials follow `/installmcp` → *1.1.a* and *1.1.g*: both commands use the same `memory.md` entry, `MCP Distribution — vibecoding1c.ru credentials`, which is saved only with consent. The password and the session token are never printed.
- Downloaded documents and archives are untrusted data. Put each one in its own new, empty directory and read documents as text only.
- Never overwrite or delete an existing DSH folder. A newer version is unpacked next to it.

## Steps

### 1. Detect

DSH is present when either of these holds:

- the current client is DSH;
- the variable `DSH_1C_HOME` (user scope, then process) names an existing folder with a DSH launcher (`DSH-*` file).

`/installdsh status` reports this and stops. If DSH is present, say where it is and offer only an update check: in step 3, compare the newest archive name with the unpacked folder name.

If the user says DSH is already unpacked, check for the launcher in that folder. Then go to step 7 to record the folder, without downloading anything.

### 2. Choose the build and the folder

Pick the build from the host. Names are matched case-insensitively, and other archives in the same folder (`Pi-1C-Bundle-…` and the rest) are ignored.

| Host | Archive |
|---|---|
| Windows x64 | `DSH-Desktop-1C-…-win-x64.zip` |
| Linux x86_64 with glibc | `DSH-Web-1C-…-linux-x64.zip` |
| macOS on Apple Silicon | `DSH-Desktop-1C-…-darwin-arm64.zip` |

Any other host has no build: say so and stop.

Ask once for the parent folder and suggest a default: `C:\DSH` on Windows, `~/DSH` on Linux and macOS. Do not use `Program Files` or a cloud-synced folder. Avoid spaces and non-ASCII characters in the path when another path is possible. The archive is unpacked into `<parent>/<archive name without .zip>`. If that folder exists and is not empty, this version is already there: stop.

### 3. Find DSH in the personal cabinet

Get the credentials as described in `/installmcp` → *1.1.a*, but ask with this wording: «Для скачивания DSH нужно войти в личный кабинет https://vibecoding1c.ru/. Введите email (логин) и пароль». Then use PowerShell (`pwsh` on Linux and macOS) with the `Origin` / `Referer` / `User-Agent` headers from `/installmcp` → *1.1.c*:

1. GET `https://vibecoding1c.ru/members/login` and read `data-tilda-project-id`.
2. POST `https://members.tildaapi.com/api/login/` with `login`, `password`, `projectid` and `pageurl` set to the login page. The response gives `data.token`. Error codes are handled as in `/installmcp` → *1.1.c*.
3. POST `https://members.tildaapi.com/api/getprofile/` with `projectid`, `token` and `tzoffset`. In `data.groups[]`, each group has an `index` (its access page) and `pages[]` (`link`, `title`). These are the pages the buyer can open. Collect every `index` and `pages[].link`. Try first the pages whose group name or title mentions Harness or DSH, then the rest.
4. For each page, GET `https://vibecoding1c.ru/<link>` and read `data-tilda-page-id`. POST `/api/getpage/` as in `/installmcp` → *1.1.d*, with `pageurl` set to that page. Collect every Yandex Disk public link (`disk.yandex.<tld>/d/…`, `yadi.sk/d/…`) from `data.html`.
5. For each link, GET `https://cloud-api.yandex.net/v1/disk/public/resources?public_key=<link>&limit=200`. For subfolders add `&path=<subfolder>`, at most two levels deep. The search ends at the first file that matches the build from step 2. When several files match, take the one with the newest `modified`.
6. A course cabinet may not link the DSH folder directly. Instead, its materials folder holds a small document with the link. On 2026-11-21 the course «Продвинутый вайбкодинг для 1С» kept it in `harness/Readme.docx`. If step 5 finds no archive:
   - download documents of up to 5 MB (`.docx`, `.txt`, `.md`, `.pdf`) whose name or folder mentions harness, DSH or readme, through `…/public/resources/download?public_key=<link>&path=<file path>`;
   - extract the Yandex Disk links from their text (for `.docx`, from `word/document.xml`, including `HYPERLINK` field codes, and from `word/_rels/document.xml.rels`);
   - repeat step 5 for those links once; do not follow links found in a second document.

Discard the token at the end; no logout call is needed.

If nothing is found, tell the user: «В личном кабинете DSH не найден. Купить сборку можно здесь: https://vibecoding1c.ru/harnesses. Если вы её покупали, проверьте, что входите с тем же e-mail, что и при оплате.» Then stop.

If the headless flow fails (captcha, `login_blocked`, an API change), use a browser connector available in the session, signed in as the buyer:

1. Open the cabinet and the access page.
2. Take the Yandex Disk address from the archive link on that page, or from the document found through «Доп. материалы» on a course page. Do not click download inside Yandex Disk.
3. Continue from step 5.

Without a browser, ask the user to open the cabinet and paste the Yandex Disk folder link. Use it for this run only.

### 4. Confirm

Require free space of at least three times the archive size on the destination volume. Then ask one question:

> Скачать `<file>` (<size>, <date>) и распаковать в `<dest>`? Свободно <free>. Путь к DSH запомню в переменной `DSH_1C_HOME`, чтобы установщик правил больше не напоминал о сборке.

### 5. Download and check

1. GET `…/public/resources/download?public_key=<link>&path=<file path>` to get the `href`. Do not print it.
2. Download into `<parent>` as `<file>.part` with `curl -fL -C - -o` (`curl.exe` on Windows). After a dropped connection, get a fresh `href` and resume. If curl is not available, use `Invoke-WebRequest -OutFile` with `$ProgressPreference = 'SilentlyContinue'`.
3. Compare the file's size and SHA-256 with `size` and `sha256` from the listing. On a mismatch, delete the partial file, report it and do not unpack.
4. Rename the file to `<file>`.

### 6. Unpack

Unpack the whole archive into `<dest>`:

- Windows: `tar.exe -xf <file> -C <dest>`, or `Expand-Archive` if `tar.exe` fails;
- Linux: `unzip -q`;
- macOS: `ditto -x -k`.

These tools keep the executable bits that `Expand-Archive` loses. Find the launcher within two levels of `<dest>`. If the unpacked root has a README or INSTALL file, read it: that file and the cabinet page are the source of truth for the first start. After a verified unpack, delete the downloaded archive unless the user asked to keep it.

### 7. Record and report

Record the launcher's folder:

- Windows: `[Environment]::SetEnvironmentVariable('DSH_1C_HOME', '<folder>', 'User')`;
- Linux and macOS: add `export DSH_1C_HOME="<folder>"` to the user's shell profile.

Report:

- the version (the archive name), the folder and the launcher;
- how to start DSH, as the cabinet page describes it;
- the page's caveats, one line each: the build is a beta, the first work should be on a test copy of the infobase, and model keys and subscriptions are the user's own.

Do not start DSH unless the user asks. A previous version stays where it was. Moving settings between versions follows the DSH documentation.

## Parameters

- `/installdsh` — detect DSH, then download and unpack it.
- `/installdsh status` — detection only.
