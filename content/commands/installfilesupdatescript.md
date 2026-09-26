---
description: Create an infobase-to-MCP XML export script and install it in Windows Task Scheduler
userOnly: true
argumentHint: "[interval-minutes]"
---

# /installfilesupdatescript — schedule the MCP source refresh

Create a project-local PowerShell launcher and register a recurring Windows Task Scheduler task. Every run reads the connection from the project's `.dev.env`, exports the main configuration or `EXTENSION_NAME` through the bundled `db-dump-xml.ps1`, checks the result, and refreshes the **verified MCP source directory**. Installation is explicitly requested by invoking this command; do not stop at producing instructions or ask again to register the task.

This is an infobase → dedicated Designer XML snapshot operation. It never loads files into the infobase. A full snapshot is staged on every run, so deleted metadata does not leave stale files in the published directory. No BSL is generated. Read `content/rules/getconfigfiles.md` and `content/skills/1c-metadata-manage/docs/db-manage.md` for the export contract.

## Resolve the project and MCP destination

1. Windows only. Read the current project's `.dev.env` (the canonical filename includes the leading dot; do not introduce a second `dev.env`). Require `PLATFORM_PATH` and `INFOBASE_PATH`; use `INFOBASE_KIND=file` when empty. Read optional `IB_USER`, `IB_PASSWORD`, `EXTENSION_NAME` and `PLATFORM_ARGS`. Relative paths resolve from the project root. Do not copy credentials into the launcher, task arguments or a second settings file. The helper uses the installed Designer at `PLATFORM_PATH/bin/1cv8.exe` for both file and clustered infobases; it does not use `IBCMD_CONFIG`.
2. Locate the **current project's** MCP installation/registration from `.ai-rules.json`, the active client's MCP config or the external distribution manifest, following `content/commands/setupmcp.md`. Read only relevant settings; do not print secrets. Resolve the effective `PATH_CODE` to its **Windows host path**, including the current Docker bind mount / project source-root mapping. A container path such as `/app/code` is not a host destination. Do not guess that `EXPORT_PATH` is the indexed directory, and do not select another project's registration. Multiple candidate projects or paths need one focused clarification before installation.
3. Confirm the consumers accept a **Designer XML** dump. `PATH_METADATA` in legacy report mode is a separate text report, not an XML dump; this command does not generate that report. An EDT source tree cannot be overwritten with Designer XML. If either is in use, resolve a supported Designer XML source registration through the MCP distribution's documented setup procedure first, or report that the current consumer is incompatible; never claim that its report / EDT index was refreshed.
4. The destination must be dedicated to generated files. It cannot overlap the infobase, explicit `EXPORT_PATH` / `EXTENSIONS_PATH`, a working Git/EDT project, or the generated scripts. Prefer an existing dedicated MCP dump directory. If MCP currently reads editable sources, resolve a separate dump and its MCP mapping before installing; do not silently overwrite the working tree or retarget other projects. A non-empty, previously unmanaged dump requires explicit authorization to replace **that directory's contents**; only then use `-AdoptExisting`. An already-owned destination needs no repeated confirmation. Never infer adoption from a request to install the task.
5. Scope is main configuration when `EXTENSION_NAME` is empty, otherwise that exact extension. `EXTENSION_NAMES` does not silently broaden the task. For an index needing main plus extensions, resolve separate project/target mappings before installing; do not mix their XML roots.

## Create the script and task

Resolve `content/skills/1c-metadata-manage/tools/1c-db-ops/scripts/install-files-update.ps1` through the active client's canonical skills directory and assign the **existing absolute path** to `$helper`; the source path is not a literal installed-project path. Default interval: **30 minutes**; a positive integer argument overrides it. The task runs under the current Windows user, with limited privileges, **while that user is logged on**. State this explicitly. A requirement to run after logout needs a separately agreed Windows service account / logon mode; do not assume SYSTEM or store a Windows password in the project.

```powershell
& $helper `
    -ProjectRoot '<absolute-project-root>' -IndexPath '<verified-host-PATH_CODE>' `
    -IntervalMinutes 30 -CheckOnly
```

After the preflight passes, run the same helper without `-CheckOnly`. Add `-AdoptExisting` to both calls only when the existing directory was explicitly approved. `-WhatIf` also performs no writes and no registration. Do not substitute platform commands of your own.

The helper creates `.1c-files-update/<project-and-path-id>/update-files.ps1`, a destination ownership marker, and task `1C-MCP-Files-<id>`. Reinstallation updates that same task; it refuses another task's identity or an installation while the task is running. Add `.1c-files-update/` and any project-local dedicated dump to the project's `.gitignore` without replacing existing entries. Keep the launcher and installed skill files available for subsequent runs.

Task details: first trigger in one minute, recurring indefinitely; explicit working directory; hidden noninteractive PowerShell; `IgnoreNew` plus an exclusive file lock to prevent concurrent exports. The task does not impose a time limit on a long Designer export. Inspect a stuck task and its own child process before stopping it; never kill unrelated platform sessions. Task Scheduler registration uses the native `ScheduledTasks` module, not Codex automations.

## Verify and report

Read back `Get-ScheduledTask` and `Get-ScheduledTaskInfo` for the exact returned task name. Check the action, working directory, interval, user and enabled state. Run `Start-ScheduledTask` once, wait for that run with bounded status checks, then check `LastTaskResult=0`, `last-run.log` ending in `SUCCESS`, and the exported `Configuration.xml` and `ConfigDumpInfo.xml`. Installation alone is not evidence of a successful export. A startup / authentication / permission error is a failed first run; retain the log and fix the specific cause instead of silently changing the infobase or account.

The helper stages a full dump and checks the wrapper's exit code (which includes `/DumpResult`), platform log and XML artifacts before copying. An export failure leaves the previous published files intact. Publication uses `robocopy /MIR` inside the explicitly owned destination, preserves the directory for Docker bind mounts, and removes stale files. Copying is **not atomic**: a copying failure may leave a partial snapshot, is reported as a failure, and needs a successful rerun. Coordinate the MCP scanner to read only after success if it cannot tolerate concurrent filesystem changes. File refresh does not prove index ingestion: verify the consumer's documented status separately; do not invent a reindex API or force a graph refresh as recovery.

Report the script path, task name, effective interval/user/logon mode, exact source target, destination and log, first-run result and observed MCP ingestion status. Do not print credentials. If no live infobase or MCP mapping is available, report the unresolved prerequisite rather than claiming installation/synchronization succeeded.

Rollback: `Disable-ScheduledTask -TaskName '<exact-name>'` stops future triggers; let an active run finish, then `Unregister-ScheduledTask -TaskName '<exact-name>' -Confirm:$false`. Keep the dump and logs; deleting them is a separate request. Retargeting an existing installation requires disabling its old task first, because a new destination has a different task identity.

References: [Windows recurring triggers](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger), [1C XML export](https://kb.1ci.com/1C_Enterprise_Platform/What___s_New/Functional_Highlights/Incremental_export_of_configurations_to_XML_files/).
