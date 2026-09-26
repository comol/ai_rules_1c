---
description: Driving the 1C web client in UI tests — accessibility snapshot, lists / grids / reports, field filling, dialogs, shortcuts, anti-loop discipline. Load after the `ui-testing-tools.md` preflight, before the first action on the web client.
alwaysApply: false
category: tooling
---

# 1C web client — reading and driving the UI

`ui-testing-tools.md` decides **which** driver runs (`agent-browser` → built-in browser MCP → `Windows-MCP`). This file is the layer above: **how the 1C web client behaves** once a driver is attached. The behaviours below are properties of the 1C managed-form web client, not of any one tool — they hold for `agent-browser` snapshots, for a browser MCP, and for raw CDP alike.

**When to load:** after the preflight gate of `ui-testing-tools.md`, before the first navigation to `INFOBASE_PUBLISH_URL` — `1c-tester`, `/deploy-and-test` Step 4, or an ad-hoc web check.

> **Terminology.** "Snapshot" = whatever structured view the active driver returns (accessibility tree with refs for `agent-browser`, DOM/a11y dump for a browser MCP). Everything here is expressed in terms of what the snapshot *shows*, never in terms of CSS selectors — selectors of the 1C web client are generated and unstable.

## 1. Session facts that change how you drive

| Fact | Consequence |
|---|---|
| **Headed only.** The 1C web client does not run reliably headless. | Launch the driver in headed mode. A headless run that "works" is usually rendering a login page and nothing else. |
| **Cold start is 30–60 s.** First connect loads the whole managed-application client. | Wait for the section panel to appear in the snapshot before the first action. Do not treat a slow first load as a failure and retry — the retry restarts the same 60 s. |
| **1C emits non-breaking spaces (` `)**, not regular spaces, in captions, numbers and totals. | Normalize ` ` → space on **both** sides before comparing snapshot text to an expected string. A "не найдено" on a caption you can plainly see in a screenshot is almost always this. |
| **Section panel must display text.** With "Картинка" (icon-only) display mode the section names are not in the accessible tree. | If sections are unreadable, switch the panel to "Картинка и текст" / "Текст" in the client settings, or navigate by metadata path (§2) instead. |
| **The open-windows tab bar can be hidden** by client settings. | Never infer "how many forms are open" from the tab bar. Count the open form containers in the snapshot instead. |

## 2. Navigation

Preference order — cheapest and most robust first:

1. **By metadata path (`Shift+F11`).** Opens the "Перейти по ссылке" dialog; accepts `Документ.ЗаказКлиента`, `Справочник.Контрагенты`, `РегистрНакопления.ЗаказыКлиентов`. Bypasses the section panel and the command panel entirely. This is the fastest way to reach a specific object in tests, and it is immune to interface / subsystem layout differences between configurations.
2. **Section → command.** Click the section in the panel, then the command in the function panel. Use when the test is *about* the command interface, or when the object has no direct link.
3. **External processor / report (`*.epf` / `*.erf`)** — "Файл → Открыть". The platform raises a **security confirmation dialog** ("Открытие файла... небезопасно") before loading. Expect it and confirm it; a hang here reads as "the processor never opened".

After any navigation, re-snapshot before acting — refs from a previous snapshot are stale.

## 3. Reading form state from the snapshot

Things to actively look for, because they change what to do next:

- **Modal dialog** — a form that blocks the rest of the UI. Nothing else on the page is clickable until it is dismissed. If an action "does nothing", check for an unnoticed modal first.
- **Confirmation dialog** (`Да` / `Нет` / `Отмена`) — typically raised by closing a modified form or by a delete. Answer it explicitly; never `Escape` out of it blindly.
- **Error dialog** — read the message text into the report verbatim. A failed test with the platform's own error message is a useful result; "clicking failed" is not.
- **Required unfilled fields** — the platform marks them (red underline / "Заполните ..." message on save). Enumerate them before saving rather than discovering them one error at a time.
- **Report info bar** — for a spreadsheet result area, the platform shows a state message *instead of* data: `"Отчет не сформирован..."`, `"Не установлено значение параметра ..."`, `"Изменились настройки..."`. Treat it as a first-class result: the report did not run, and the reason is written on screen.

## 4. Lists, trees and grids

- **Single click selects a row. Double-click opens it.** This is the single most common failed assumption — a test that "clicked the document and nothing happened" almost always single-clicked.
- **Tree nodes:** a click on the row **selects**; expanding / collapsing requires activating the node's own expander (the triangle), or `→` / `←` on the focused row. Clicking the caption to expand a node does not work.
- **Multi-select:** `Ctrl`+click adds to the selection, `Shift`+click selects a range. Verify by re-reading which rows the snapshot reports as selected — do not assume the modifier registered.
- **Hierarchical catalogs:** searching inside a hierarchy is unreliable while the tree view is on. Apply a list filter to flatten the view, act, then clear the filter to restore the hierarchy.
- **Forms with more than one grid** (e.g. "Входящие" and "Исходящие" on one form): every grid has its **own** command panel. An unscoped click on "Добавить" hits the *first* one on the form, and an unscoped table read returns the *first* grid — silently the wrong one. Identify the target grid by its visible group title, then act inside that grid's own subtree of the snapshot.
- **Paginate long lists.** Read in bounded chunks; a full read of a large list is a token sink with no test value.

## 5. Filling fields

- **Typing stays the default** — human-like typing with 50–100 ms between characters, `TAB` between fields, per `1c-tester` → "Browser Interaction Guidelines". Reference fields need real input events for the typeahead (подбор) to fire, and typing produces them.
- **Clipboard paste is the documented fallback**, not the default: if a typed value does not register (the field clears on `TAB`, or the platform never fires its change event), fill via clipboard paste, then `TAB` and verify the field kept the value. Note the fallback in the test report — a field that only accepts paste is itself a finding.
- **Clearing a field is `Shift+F4`**, not selecting the text and deleting. Deleting characters leaves reference fields in a "partially typed" state that the platform may re-resolve on exit.
- **Reference fields:** `F4` opens the selection form (use it when the typeahead is ambiguous — pick the row explicitly), `F8` creates a new catalog item from the field.
- **Composite-type fields** (accepting several types — `Документ`, `Субконто`, ...) need three steps: clear the field → the platform offers a **type-choice dialog** → pick the type → only then pick the value. Typing a value straight into an empty composite field does nothing.
- **DCS report filters have a paired checkbox.** Setting the value without ticking the filter's checkbox leaves the filter **disabled** — the report runs unfiltered and the test silently asserts against the wrong data. Tick the checkbox, then set the value, then confirm both stuck.

## 6. Reports (SpreadsheetDocument)

- The rendered spreadsheet is a **separate embedded document**, not part of the ordinary form tree — read it as its own region of the snapshot.
- **Wait for composition after "Сформировать"** before reading. A read that happens during composition returns the previous result or an empty area, which looks exactly like "the report is empty".
- Before asserting on data, check for the info-bar state messages of §3 — they mean the run never produced rows.
- **Drill-down (расшифровка)** is a double-click on a data cell → the platform opens the "Выбор поля" dialog → choose the field → the drill-down report composes. Expect the intermediate dialog; a single click only selects the cell.
- Verify **totals** separately from rows. Totals come from the composition engine and can be correct while a row-level filter is wrong, or vice versa.

## 7. Closing forms

| Goal | Do |
|---|---|
| Post & close a document | Click **"Провести и закрыть"** |
| Save & close a catalog item | Click **"Записать и закрыть"** |
| Close without saving | `Escape`, then answer **"Нет"** to the confirmation |
| Close and save | `Escape`, then answer **"Да"** |

Prefer the form's own command over hunting the `×` glyph — close buttons on tabs are ambiguous in the snapshot and easy to hit on the wrong window.

**Always verify the form actually closed.** `Escape` can be swallowed (a cell editor is open, a modal is up, the form vetoed the close). Re-snapshot and confirm the form is gone before continuing; a test that keeps driving a form it believes is closed produces nonsense.

## 8. Keyboard shortcuts worth knowing

| Key | Context | Action |
|---|---|---|
| `Shift+F11` | Anywhere | Open object by metadata path (§2) |
| `F4` | Reference field focused | Open selection form |
| `F8` | Reference field focused | Create a new catalog item |
| `Shift+F4` | Any input focused | Clear the field |
| `Alt+F` | List / table form | Advanced search dialog |
| `→` / `←` | Tree row focused | Expand / collapse the node |

## 9. Anti-loop discipline

UI automation degenerates into retry loops faster than any other work in this ruleset. Hard limits:

- **Two attempts per operation, maximum.** Same action failing twice the same way → stop, report what was tried.
- **Not found means not found.** An empty list after a filter, or a search returning nothing, is evidence about the *infobase*, not a prompt to try five spelling variants. Report it as a finding.
- **Change the method, not the wording.** Section navigation failed → try the metadata path (§2). Typeahead failed → try `F4` selection form. Re-running the same approach with a tweaked string is the loop.
- **Report partial results.** "Found the list, could not find item X; the list contains A, B, C" is a useful result. Silent retrying is not.
- Failures are documented with reproduction steps and evidence per `1c-tester` → "Test Report Format" — a blocked scenario is a reportable outcome, not a reason to keep grinding.

## 10. Companion rules

| Concern | File |
|---|---|
| Which browser / desktop driver to use, and the mandatory preflight | `ui-testing-tools.md` |
| `UI_TESTING`, `INFOBASE_PUBLISH_URL` and the rest of the test parameters | `dev-standards-env.md` |
| Test workflow, scenario template, report format | `content/agents/tester.md` |
| Deploy step that precedes UI testing | `content/commands/deploy-and-test.md` |
| Publishing the infobase for the web client | `content/skills/1c-metadata-manage/docs/web-manage.md` |
