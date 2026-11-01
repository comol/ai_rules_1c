# 1C Support State Manage — Vendor Support, "На замке", Editability

Read and change the **support state** of a vendor (typical) configuration: whether the configuration can be modified at all, and whether a particular object is locked ("на замке"), editable-with-support, or taken off support.

This matters because editing a supported object directly is not a style question — it **silently breaks future vendor updates**. Two layers implement this:

1. **The guard** — built into the mutating tools of this skill. Automatic, no setup.
2. **`support-edit`** — the deliberate override, used *after* the guard refuses.

---

## Part 1: The Guard (automatic)

Every mutating tool of this skill checks the support state before touching anything:

`cf-edit`, `meta-edit`, `meta-compile`, `meta-remove`, `form-edit`, `form-add`, `form-compile`, `skd-edit`, `skd-compile`, `mxl-compile`, `role-compile`, `subsystem-edit`, `subsystem-compile`, `interface-edit`, `add-template`, `add-help`, `xdto-compile`, `xdto-edit`.

**Trigger.** The guard activates only when the configuration is genuinely on vendor support — i.e. `Ext/ParentConfigurations.bin` is present next to `Configuration.xml` (found by walking up from the target path). Own configurations, extensions and autonomous external objects (EPF/ERF) are never affected. A support-state file that exists but cannot be read or parsed gets the same `deny|warn|off` reaction (fail-closed — an unknown state may be a locked object); other guard errors (the state cannot even be located) degrade to *allow* with a stderr notice.

**What is blocked:**

| Situation | Guard verdict |
|-----------|---------------|
| Configuration-wide "possibility of modification" is off (read-only out of the box) | blocked — `capability-off` |
| Object is on support and locked ("на замке") | blocked — `locked` |
| Deleting an object that is still on support (`meta-remove`) | blocked — `not-removed` |
| Object is `editable` or off support | allowed |

A blocked run exits with code `1` and prints a diagnostic naming the state, the recommended path (extension) and the exact `support-edit` command for this case.

**Reaction mode** comes from **`.dev.env`, key `SUPPORT_GUARD`**:

| Value | Behaviour |
|-------|-----------|
| `deny` (default, also when the key is empty or absent) | The edit is refused, exit code `1`, diagnostic with the ready-made `support-edit` command |
| `warn` | Warning to stderr, the edit proceeds |
| `off` | No check at all |

`.dev.env` is looked up by walking up from the working directory, exactly like the rest of the toolkit. Upstream `cc-1c-skills` reads `editingAllowedCheck` from `.v8-project.json` instead; that path still works as a fallback for projects that have such a file, but **`.dev.env` wins** — it is this project's single source of truth ([db-manage.md](db-manage.md)).

**Direct edits (optional hook, experimental).** The guard runs inside the tools, so an agent that writes the XML or a module of a locked object with its own `Edit` / `Write` is not stopped by it. In Claude Code with the `1c-rules` plugin, `SUPPORT_GUARD_HOOK=on` in `.dev.env` adds a `PreToolUse` hook that applies the same rule and the same `SUPPORT_GUARD` reaction to such edits of dump files (Node 18+; without Node it lets the edit through with a notice). It is off by default and absent on other hosts — there the tools' guard and this document are the protection. A refusal from the hook is answered exactly like one from a tool: an extension, or `support-edit`; never a write through another tool. Details: `plugins/1c-rules/README.md` in the ruleset source.

---

## Part 2: The Right Answer Is Usually an Extension

Before changing any support state, the default answer to "the typical object needs a change" is: **do it in an extension** — `cfe-borrow` to borrow the object, `cfe-patch-method` to intercept a method ([cfe-manage.md](cfe-manage.md)). Support state stays untouched, vendor updates keep flowing, and the change survives the next release.

Changing support state is the right call when the change genuinely cannot live in an extension, or the object is being permanently forked from the vendor line. It is a decision with consequences for every future update — make it explicitly, and say so in the task report.

---

## Part 3: `support-edit` — Changing the State

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-support-manage/scripts/support-edit.ps1 -Path "<target>" -Set editable
```

| Parameter | Description |
|-----------|-------------|
| `-Path <path>` | Object XML, form, template or the dump root directory. Alias — `-TargetPath`. Use exactly the path the guard rejected |
| `-Set editable\|off-support\|locked` | Per-object state |
| `-Capability on\|off` | Configuration-wide possibility of modification |

Exactly one of `-Set` / `-Capability` is required.

| What you need | Command |
|---------------|---------|
| Allow editing an object | `-Path <object> -Set editable` |
| Take an object off support | `-Path <object> -Set off-support` |
| Put an object back "на замок" | `-Path <object> -Set locked` |
| Allow adding new objects to the configuration | `-Path <dump root> -Set editable` |
| Turn the possibility of modification on / off | `-Path <dump root> -Capability on` / `off` |

### editable or off-support?

- **editable** — edits allowed, the object **keeps receiving vendor updates** (merge conflicts possible on update). Choose it when you want to keep developing *and* keep updates.
- **off-support** — the object is **removed from support**: edits are free, vendor updates for it stop arriving. It is not a deletion of the object. Choose it when the object leaves the vendor update line for good.
- **locked** — the way back: edits forbidden again.

### If the possibility of modification is off

For a stock read-only configuration, per-object `-Set` will not work — turn the capability on first, then open the specific object:

```powershell
... support-edit.ps1 -Path "<dump root>" -Capability on      # objects all stay locked
... support-edit.ps1 -Path "<object>"    -Set editable       # open this one
```

`-Capability off` makes the whole configuration read-only again **and resets per-object rules**.

---

## Part 4: Applying It

`support-edit` changes the **dump only** (`Ext/ParentConfigurations.bin`). To apply it to the infobase, load the dump — a **full** load, not partial (`db-load-xml` / `db-load-cf`, see [db-manage.md](db-manage.md)), followed by `db-update`.

Take a `db-dump-dt` rollback point first: this class of change bypasses the vendor update mechanism, and getting the state back afterwards is not a one-liner.

---

## Reporting

When a task changed support state, say it in one line in the report: which object, `editable` / `off-support`, and why an extension was not the answer. Support state is a decision the next developer inherits — it does not belong only in the diff.
