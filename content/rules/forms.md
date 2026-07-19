---
description: Entry point for managed-form work — pick the exact companion rules for `Form.xml`, `Form.Module.bsl`, events, async code, reserved names, and XML validation. Load first for any form task; load companions only via the routing table below.
alwaysApply: false
category: forms
---

# Managed Forms — Entry Point

This file is the **router** for managed-form work. Load it first, then load only the companion rules selected by the table below — companion files are not auto-attached by file pattern.

## Routing

| Task | Load |
|---|---|
| Design a form layout from scratch, or when requirements do not specify element placement | `form-patterns.md` |
| Create or structurally modify `Form.xml` | `forms-add.md`, `metadata-xml-workarounds.md` |
| Programmatic modification of typical forms (element placement, fill checking, form commands) | `forms-add.md → Form-Presentation Rules` |
| Add or rename form event handlers | `form-module.md → Adding Form Event Handlers` |
| Edit `Form.Module.bsl` logic | `form-module.md` |
| Server-side form-module code (reserved names `ПараметрыВыбора`, `СвязиПараметровВыбора`, `СписокВыбора`, `ПараметрыОтбора`, `ОтборСтрок`) | `form-module.md → Reserved Names` |
| Set up module regions in a new form module | `module-structure.md → Form Module` (5 mandatory regions) |
| Client-server architecture (directives, round trips) | `dev-standards-architecture.md §3 → "Client-Server Interaction"`, `anti-patterns.md → "Excessive Client-Server Calls"`, `anti-patterns.md → "Using &НаСервере Instead of &НаСервереБезКонтекста"` |
| Client-side async code (`Асинх` / `Ждать`) | `async-methods.md` |
| Working on an adopted form of an extension | `extension-patterns.md`, `dev-standards-architecture.md §2` |

Each companion file is self-contained — load only the ones that match the task. Do not preload the whole set "to be safe".
