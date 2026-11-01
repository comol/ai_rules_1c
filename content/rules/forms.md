---
description: Entry point for managed-form work — pick the exact companion rules for `Form.xml`, `Form.Module.bsl`, events, async code, reserved names, and XML validation. Load first for any form task; load companions only via the routing table below.
alwaysApply: false
category: forms
---

# Managed Forms — Entry Point

This file is the **router** for managed-form work. Load it first, then load only the companion rules selected by the table below — companion files are not auto-attached by file pattern.

> **Execution gate.** Companion rules define *what* a correct form looks like; the *mutation* of `Form.xml` / layouts itself goes through the **`1c-metadata-manage`** skill (`content/skills/1c-metadata-manage/docs/form-manage.md`, form-compile DSL) or the `1c-metadata-manager` subagent — hard gate per `AGENTS.md → Skills and Subagents`, exceptions only per the skill's `SKILL.md → Hard rule`. Editing `Form.Module.bsl` logic is regular BSL work and is not covered by this gate. The form tools also append empty handler stubs to `Form.Module.bsl` for every handler they bind (no switch) — expect the module to change and see `form-module.md → Adding Form Event Handlers`.

## Routing

| Task | Load |
|---|---|
| Design a form layout from scratch, or when requirements do not specify element placement | `standards(name="form-patterns")` |
| Create or structurally modify `Form.xml` | `forms-add.md`, `metadata-xml-workarounds.md` |
| Programmatic modification of typical forms (element placement, fill checking, form commands) | `forms-add.md → Form-Presentation Rules` |
| Add or rename form event handlers | `form-module.md → Adding Form Event Handlers` |
| Edit `Form.Module.bsl` logic | `form-module.md` |
| Server-side form-module code (reserved names `ПараметрыВыбора`, `СвязиПараметровВыбора`, `СписокВыбора`, `ПараметрыОтбора`, `ОтборСтрок`) | `form-module.md → Reserved Names` |
| Set up module regions in a new form module | `module-structure.md → Form Module` (5 mandatory regions) |
| Client-server architecture (directives, round trips) | `standards(name="dev-standards-architecture") §3 → "Client-Server Interaction"`, `standards(name="anti-patterns") → "Excessive Client-Server Calls"`, `standards(name="anti-patterns") → "Using &НаСервере Instead of &НаСервереБезКонтекста"` |
| Client-side async code (`Асинх` / `Ждать`) | `standards(name="async-methods")` |
| Working on an adopted form of an extension | `standards(name="extension-patterns")`, `standards(name="dev-standards-architecture") §2` |
| **Ordinary form (обычная форма)** — `Ext/Form.bin` and no `Form.xml` | `content/skills/v8unpack-cf/SKILL.md → Ordinary forms` — nothing on this page applies |

> **Ordinary forms are a different document, not a variant of this one.** A 1C form is either managed (`Forms/<Имя>/Ext/Form.xml`, declarative, `DataPath` bindings) or ordinary (`Forms/<Имя>/Ext/Form.bin`, a binary container holding the layout and the form module). The sidecar `Forms/<Имя>.xml` says which, via `<FormType>`. Everything on this page — `forms-add.md`, `standards(name="form-patterns")`, the `1c-metadata-manage` gate — is about the managed document. For an ordinary form the layout is binary: read and write it with `unpack_ordinary_form` / `build_ordinary_form` per the `v8unpack-cf` skill, and never hand-edit `Form.bin`. Its form module is regular BSL and `form-module.md` still applies to the code you put in it.

Each companion file is self-contained — load only the ones that match the task. Do not preload the whole set "to be safe".
