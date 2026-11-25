# Interaction recipes

Call sequences for the frequent actions, run live on server 0.7.9 and platform 8.3.27.2130 (01.10.2026). They hold what the tool descriptions do not say: which calls, in which order, and what in the answer shows the step is done. Names of elements, tables and buttons are examples — take the real ones from the form (`ui_window_tree(detail="lite")`; buttons: `ui_form(action="command_bar")`).

Load a tool schema only for a selected action whose tool or argument is not shown here. Where the host loads schemas on demand, batch independent missing schemas for the chosen recipe; do not preload the tools of unrelated recipes.

| Goal | Calls, in order | Done when |
|---|---|---|
| Clean start | `ui_close_all()` | `windows`: the main window and the home page only |
| Open a list | `ui_open(kind="catalog", metadata_name="Организации")` (`kind` in English or Russian, or `metadata_name="Справочник.Организации"` alone) | `opened: true`, `form_name` |
| First item of the list | `ui_table(action="first", name="Список")` → `ui_table(action="select", name="Список")` | `window_after`: `title`, `form_name` of the item form; `url` from `ui_active_window()` when needed (empty with `url_unavailable` on a test client before 8.3.25 without MCPQAClient 0.6.2) |
| Item of a known row | `ui_table(action="select", name="Список", row={"Наименование": "Крон-Ц"})` — the choice is made on the column of `row=` (or `column=`) | same; a missing row is the error «Строка таблицы не найдена», nothing opened |
| Item in a long list | `ui_list(action="search", text="Крон")` → `select` with `row=` as above; `ui_list(action="clear_search")` before the list is used again | the search `rows` hold the row |
| The same object again | `ui_open(link="<url from ui_active_window>", target_form_name="<its form_name>")`; without a `url`: `ui_open(kind="document", metadata_name="<Имя>", uuid="<ref>")` with the ref taken by a query | `opened: true` |
| New object | on its list: `ui_table(action="add", name="Список")` | `window_after.title` ends with «(создание)» |
| Read a field | `ui_get_text(name="Наименование")` | `edit_text` |
| Plain field | `ui_input(text="12,5", name="Цена")` → `ui_activate(name="<next field>")` | `value_after`, `verified: true`; `ui_messages()` when the change has checks |
| Reference field | `ui_select(value="Молоко", name="Номенклатура")`; a composite type also needs `data_type=` | `actual` equals the value |
| Row of a tabular section | `ui_table(action="add", name="Товары")` → `ui_select(value="Молоко", name="ТоварыНоменклатура", table="Товары")` → `ui_table(action="input_cell", name="Товары", column="ТоварыКоличество", value="5")` | `value_after`, `verified: true`; `ui_table(action="current", name="Товары")` shows the row |
| Checkbox cell | `ui_table(action="input_cell", name="Товары", column="ТоварыОтметка", value="true")` or `ui_field(action="check", name="ТоварыОтметка", table="Товары")` on the current row; QA MCP before 0.8.3: `ui_activate(name="ТоварыОтметка", table="Товары")` first, and `uncheck` is not reliable — use `toggle` and read the cell | `value_after` «Да» / «Нет»; `ui_table(action="current")` |
| Write and stay | `ui_click(name="ФормаЗаписать")` → `ui_active_window()` → `ui_messages()`, `ui_errors()` | title without «(создание)» and « *», `modified: false`, `has_error: false` |
| Write or post and close | `ui_click(name="ФормаЗаписатьИЗакрыть")` (`ФормаПровестиИЗакрыть`) → `ui_wait(form_name="<form_name>", closed=True)` → `ui_messages()` | `closed: true`; a form that stayed open has the reason in the messages or in a question |
| Answer a question | `ui_active_window()` (`form_name: MessageBox`), its text in `ui_window_tree(detail="lite")` → `ui_dialog(title="Нет")` | `clicked: true`, then the window behind it |
| Close a form | `ui_close_form(form_name="<form_name>", on_prompt="discard")` (`save`, `cancel`) | `closed: true`; `blocked_by` names a question left open. `closed: false` without `blocked_by`, with `current_control` holding text the field did not accept: `ui_field(action="clear", name="<that field>")`, then close again |

What goes wrong around them:

1. `select`, `edit`, `delete` and `copy` act on the current row unless `row=` is given; then they go to that row first and refuse when it is missing. Reading rows keeps the cursor where it was and answers `current_row` (servers before 0.7.9 left it on the last row read).
2. `ui_table(action="edit")` on a list opens the item form (`window_after`, `editing: false`) — it does not edit the row in place; open items with `select` and never call `end_edit` after it.
3. `kind` values: `catalog`, `document`, `dataProcessor`, `report`, `informationRegister`, `accumulationRegister`, `chartOfCharacteristicTypes`, `chartOfAccounts`, `chartOfCalculationTypes`, `businessProcess`, `task`, `exchangePlan`, `commonForm`, or the Russian name of the kind (before 0.7.9 only the English ones).
4. Form selectors (`target_title`, `title=` of `ui_close_form` and `ui_wait`) compare the whole title, without wildcards, and a modified form's title gets « *». Address a form by `form_name`.
5. Elements are searched in the active window first, then in the whole application. An answer with `found_in` came from a window that is not the active one — a list under the card opened over it: check it is the window you mean.
6. A configuration may hide a standard button and show its own with the same title (`КомандаЗаписатьИЗакрыть` beside a hidden `ФормаЗаписатьИЗакрыть`): take the name from `ui_form(action="command_bar")` or the `lite` tree — both list visible buttons only.
7. `ui_window_tree()` is `lite` by default: visible elements without values, hidden ones counted in `hidden_skipped`. Values and states need `detail="form"`; on a large form that is tens of thousands of characters — read single fields with `ui_get_text` instead.
8. A wrong metadata name or an exception in the form's code ends `ui_open` at once with the error text, and the error window stays open: `ui_dialog(title="OK")`, then take the exact name from the metadata (`1c-meta-info`). `ui_errors` returns the text of an open `ErrorWindow`.
9. `ui_dialog(action="click")` needs `title=` or `name=` of the button; without them nothing is pressed.
10. `ui_set` with text several items start with may leave the choice list open: `dropdown_selected: false`, `dropdown_open: true` — pick with `ui_field(action="dropdown_select", value=…)`, `value` = the item's `displayed` text from `ui_field(action="dropdown_state")` (a reference is listed as «Наименование (Код)»; QA MCP 0.8.3+ also takes the `presentation` when one item has it), then confirm with `ui_get_text`. A click while the list is open only closes it.
11. A report after «Сформировать»: an empty `ui_spreadsheet(action="size")` with `state.text` «Отчет формируется...» is not ready — read again after a pause; «Изменились настройки…» means the click did not generate it, click again.

Two attempts one way are the limit. After the second failure read the window (`ui_active_window`, `ui_window_tree(detail="lite")`), then choose another way or report what was reached; do not vary arguments blindly.
