"""Семейство диаграмм: диаграмма, диаграмма Ганта, дендрограмма и сводная диаграмма.

Все четыре вида хранят содержимое одной записью — телом диаграммы. Первая позиция тела — версия записи:
платформа 8.3.27 пишет версию 74, формы старых конфигураций несут версии 64 (диаграмма) и 65 (диаграмма Ганта).

| Вид | Где лежит тело |
|---|---|
| `Chart` | позиция 3 узла элемента (`u3`); блок содержимого состоит только из `content_kind` |
| `GanttChart`, `Dendrogram`, `PivotChart` | позиция 2 списка `u1` блока содержимого: `{0, {11}, тело}` |

Остальное содержимое диаграммы Ганта, дендрограммы и сводной диаграммы лежит в позициях блока содержимого рядом с `u1`.
Шаблоны `add_element` записаны версией 74, поэтому в форму версии 10, 13 или 15 они не встают: диаграммы таких форм записаны
версиями 64 и 65, а сведения шаблона к старой записи нет.
"""

import re

KINDS = ("Chart", "GanttChart", "Dendrogram", "PivotChart")
TEMPLATE_BODY_VERSION = 74
OLD_FORM_VERSIONS = (10, 13, 15)
NAMES = {"Chart": "диаграмма", "GanttChart": "диаграмма Ганта", "Dendrogram": "дендрограмма", "PivotChart": "сводная диаграмма"}


def body(node):
    """Тело диаграммы элемента (список) либо `None`, если элемент не диаграмма или тело не читается."""
    if not isinstance(node, dict):
        return None
    kind = node.get("type")
    if kind == "Chart":
        found = node.get("u3")
    elif kind in KINDS:
        holder = (node.get("content") or {}).get("u1")
        found = holder[2] if isinstance(holder, list) and len(holder) > 2 else None
    else:
        return None
    return found if isinstance(found, list) and found else None


def body_version(node):
    """Версия записи тела диаграммы (первая позиция тела) либо `None`."""
    found = body(node)
    version = found[0] if found else None
    return version if isinstance(version, int) and not isinstance(version, bool) else None


def old_form_refusal(kind, form_version):
    """Отказ словами для формы версии 10, 13 или 15; `None` — форма версии 16 или другой вид."""
    if kind not in KINDS or form_version not in OLD_FORM_VERSIONS:
        return None
    return (f"шаблон ({NAMES[kind]}) записан версией {TEMPLATE_BODY_VERSION} (так пишет платформа 8.3.27), а диаграммы форм версии "
            f"{form_version} записаны старыми версиями тела (64 и 65); сведения шаблона к старой записи нет")


def mixed_note(doc_elements):
    """Фраза отчёта, если в форме уже есть диаграммы семейства с записью другой версии, чем шаблон; иначе `None`.

    `doc_elements` — пары `(имя, узел)` элементов формы (`design.elements`)."""
    other = {}
    for name, node in doc_elements:
        version = body_version(node)
        if version is not None and version != TEMPLATE_BODY_VERSION:
            other.setdefault(version, []).append(name)
    if not other:
        return None
    listed = "; ".join(f"версия {v}: {', '.join(map(str, names[:3]))}{' …' if len(names) > 3 else ''}" for v, names in sorted(other.items()))
    return (f"в форме уже есть диаграммы с записью другой версии, чем у шаблона ({listed}); шаблон записан версией "
            f"{TEMPLATE_BODY_VERSION}, и в форме окажутся записи разных версий")


# Внутренний заголовок диаграммы — многоязычная строка `[1, 1, ["ru", текст]]` в теле: позиция 29 (позиция 117 у сводной диаграммы: смещение 88 тела
# с четырьмя сериями и точками). Конструктор называет новую диаграмму «Диаграмма1», «ДиаграммаГанта1», … и тем же текстом пишет заголовок; при
# переименовании элемента заголовок остаётся прежним (в формах, где элемент переименовали, заголовок остался «Диаграмма1»). В палитре строки заголовка нет.
TITLE_AT = {"Chart": 29, "GanttChart": 29, "Dendrogram": 29, "PivotChart": 117}
TITLE_STEMS = {"Chart": "Диаграмма", "GanttChart": "ДиаграммаГанта", "Dendrogram": "Дендрограмма", "PivotChart": "СводнаяДиаграмма"}


def title_cell(node):
    """`(многоязычная строка заголовка, текст)` тела шаблонной записи (версия 74) либо `None`, если тело или строение другие."""
    found = body(node)
    kind = node.get("type") if isinstance(node, dict) else None
    if found is None or kind not in TITLE_AT or body_version(node) != TEMPLATE_BODY_VERSION or len(found) <= TITLE_AT[kind]:
        return None
    cell = found[TITLE_AT[kind]]
    if not (isinstance(cell, list) and len(cell) == 3 and isinstance(cell[2], list) and len(cell[2]) == 2 and isinstance(cell[2][1], str)):
        return None
    return cell, cell[2][1]


def name_the_title(node, name):
    """Новая диаграмма из шаблона получает заголовок, равный имени элемента, как у конструктора. Заголовок трогается, только пока он такой, каким его
    пишет шаблон («Диаграмма1», …): своё слово автора не затирается. Возвращает слова отчёта (пусто, если ничего не сделано)."""
    found = title_cell(node)
    if found is None:
        return ""
    cell, text = found
    if not re.fullmatch(re.escape(TITLE_STEMS[node["type"]]) + r"\d*", text) or text == name:
        return ""
    cell[2][1] = name
    return f"заголовок диаграммы «{text}» → «{name}» (позиция {TITLE_AT[node['type']]} тела): как у конструктора, заголовок новой диаграммы равен её имени"
