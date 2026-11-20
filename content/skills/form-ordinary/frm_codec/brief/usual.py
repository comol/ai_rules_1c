"""Обычное и частное в разделе «Что делает код»: обзор называет только частности, а обычное для формы этого вида сводится в одну строку «Остальное — как обычно».

Обычными считаются обработчики, после которых на экране нет ничего, кроме того, что платформа и форма делают всегда: подстановка и пересчёт значений полей
(«связанные поля шапки», «пересчёт строк своей таблицы»), обычный выбор значения из списка или справочника, запись данных, отметка изменённости. Признак обычного —
виды эффекта записи (`value`, `recalc`, `fill`, `write`) без сообщений, окон, видимости, доступности, отбора, отказа и текущей страницы, и поле, которое обработчик меняет,
не входит в условие видимости, доступности, заголовка или страницы другого элемента (иначе вид формы меняется через данные — это частность).
Решение о категориях принимает и навык разбора (`brief.codenotes`, ключ `code.defaults` в `brief.json`: `[{procedure, category, by}]`): процедуры из него обычные
независимо от видов эффекта, а их категории — те же слова.
"""

import collections
import re

from . import handler_defaults as hd, moduleview as mv

CHANGE_EVENTS = frozenset({"приизменении", "очистка", "приначалередактирования", "передокончаниемредактирования", "послеудаления", "регулирование",
                           "окончаниевводатекста", "автоподбортекста"})            # события, после которых поля подставляются и пересчитываются; кнопки и «Нажатие» — действия пользователя, они частности
VALUE_WHATS = frozenset({"value", "recalc", "fill"})
SHOWN_BY_DATA = ("visibility", "enabled", "read_only", "title", "current_page")      # значение этих записей читает условие — вид формы меняется через данные
FILLS_ROWS = re.compile(r"очища|очистк|очищ|удаля|удал[ёе]н|загруж|заполня|перезаполн|добавля[её]т строк|строк[уи] (?:добавля|в таблиц)", re.I)       # слова о заполнении, очистке, загрузке, удалении строк таблицы
LINKED = "связанные поля шапки"
OWN_TABLE = "пересчёт строк своей таблицы"
CHOICE = "обычный выбор значения"
WRITE = "только запись данных"
QUIET = "без видимого следа"
WORDS = {"write": WRITE, "rows": OWN_TABLE, "choice": CHOICE, "silent": QUIET, "linked": LINKED}      # категории модели словами обзора; прочие (`modified`, `empty`, `standard`) — `handler_defaults.CATEGORY_WORDS`
ORDER = (LINKED, OWN_TABLE, CHOICE, WRITE)       # прочие категории (из `code.defaults`) идут после них, в порядке появления; «без видимого следа» — последней
ALL_FOLDED = 4             # имён в группе одинаковых частностей называется поимённо


def norm(text):
    return re.sub(r"[\s_]+", "", str(text or "")).casefold()


class Words:
    """Имена для строки обзора: подписи кнопок, надписей и колонок вместо имён; родитель-таблица у колонок."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.button = {}
        for row in ctx.module.get("handlers") or ():
            if row.get("owner") == "panel":
                self.button[row["element"]] = row.get("button_text") or ""
        self.caption = {}
        for e in (ctx.brief.get("structure") or {}).get("elements", ()):
            if e["type"] == "Label" and e.get("caption"):
                self.caption[e["element"]] = e["caption"]
        self.tables = {t["element"] for t in (ctx.brief.get("structure") or {}).get("tables", ())}
        self.table_names = {t["short"].casefold() for t in (ctx.brief.get("structure") or {}).get("tables", ())}
        self.labels = None
        self.dead = None          # элементы, которых на экране нет (скрыты в файле или кодом); считаются при первой кнопке

    def in_table(self, source):
        """Источник события лежит в таблице (сама таблица, её колонка или поле колонки)."""
        parts = source.split("/")
        return any("/".join(parts[:i]) in self.tables for i in range(1, len(parts) + 1)) or any(self.ctx.types().get("/".join(parts[:i])) == "TableBox" for i in range(1, len(parts) + 1))

    def affects_label(self, ev):
        """Эффект события называет надпись формы (`Label`): «связанные поля шапки» — только поля ввода."""
        if self.labels is None:
            self.labels = {e["element"].split("/")[-1].casefold() for e in (self.ctx.brief.get("structure") or {}).get("elements", ()) if e["type"] == "Label"}
        return any(a.split(".")[-1].split("/")[-1].casefold() in self.labels for e in ev["effects"] for a in e["affects"])

    def hidden(self, element):
        """Элемент скрыт в файле или безусловно скрыт кодом, либо лежит под таким: на экране его нет."""
        if self.dead is None:
            from . import areas
            structure = self.ctx.brief.get("structure") or {}
            self.dead = set(structure.get("hidden", ())) | areas._hidden_by_code(self.ctx.brief)          # страница, не открытая при открытии, элемента не прячет: переключить её может пользователь
        parts = element.split("/")
        return bool(element) and any("/".join(parts[:i]) in self.dead for i in range(1, len(parts) + 1))

    def source(self, ev):
        """Кто вызывает: «кнопка «Подпись» (Имя) панели «П»», «колонка «К» таблицы «Т» (событие)», «Имя (событие)», «форма (событие)»."""
        source = ev["source"]
        if source == "форма":
            return f"форма ({ev['event']})"
        parts = source.split("/")
        name = parts[-1]
        if ev["event"] == "действие кнопки":
            text = self.button.get(source) or ""
            label = f"«{text}»" + (f" ({name})" if norm(text) != norm(name) else "") if text else f"«{name}»"
            return f"кнопка {label}" + (f" панели «{parts[-2]}»" if len(parts) > 1 else "") + (" (при открытии на экране её нет)" if self.hidden("/".join(parts[:-1])) else "")
        if len(parts) > 1 and self.ctx.types().get("/".join(parts[:-1])) == "TableBox" and self.ctx.types().get(source) is None:
            return f"колонка «{name}» таблицы «{parts[-2]}» ({ev['event']})"
        return f"«{name}» ({ev['event']})"


def procedures_of(ctx):
    """`{(источник, событие): процедура}` по назначенным обработчикам формы."""
    return {(r["element"] if r.get("element") else "форма", r["event"]): r["procedure"] for r in ctx.module.get("handlers") or ()}


def word(category):
    """Слова для строки обзора по коду из разбора (`write`, `rows`, …); слово остаётся словом. Счёт идёт по слову, поэтому одна группа обычного не считается дважды."""
    return WORDS.get(category) or hd.CATEGORY_WORDS.get(category) or category


def defaults_of(ctx):
    """`{процедура без регистра: слово категории}` из `code.defaults` (разбор кода: навык и модель); без ключа — пусто."""
    return {str(d.get("procedure", "")).casefold(): word(d["category"]) for d in ctx.code.get("defaults") or () if d.get("procedure") and d.get("category")}


def procedure_at(ctx, line):
    """Имя процедуры модуля, в которой стоит строка `line`: процедура с ближайшей выше строкой начала (обработчики и прочие процедуры), либо `None`."""
    starts = sorted([(r["line"], r["procedure"]) for r in ctx.module.get("handlers") or () if r.get("line")] + [(o["line"], o["name"]) for o in ctx.module.get("others") or () if o.get("line")])
    owner = [name for at, name in starts if at <= line]
    return owner[-1] if owner else None


def appearance_procedures(ctx):
    """Имена (без регистра) процедур модуля, в которых разбор нашёл оформление или список выбора: такой обработчик что-то меняет на экране, «без видимого следа» он не бывает."""
    return {str(name).casefold() for name in (procedure_at(ctx, n["lines"][0]) for n in ctx.accepted if n["kind"] in ("appearance", "list_content")) if name}


def read_by_conditions(ctx):
    """Имена (без регистра), которые читает условие или выражение видимости, доступности, заголовка, текущей страницы: поле с таким именем меняет вид формы через данные."""
    text = []
    for n in ctx.accepted:
        if n["kind"] in SHOWN_BY_DATA:
            text.append(n.get("condition") or "")
            text.append(n.get("value") or "")
    return {w.casefold() for w in re.findall(mv.NAME, " ".join(text))}


def category(ctx, ev, words, defaults, procedures, read):
    """Группа обычного обработчика события либо `None` — частность."""
    if defaults:
        proc = procedures.get((ev["source"], ev["event"]))
        found = defaults.get(proc.casefold()) if proc else None
        return None if found == LINKED and words.affects_label(ev) else found          # разбор назвал умолчания: обычное — только названное навыком и моделью, частность модели обзор не снимает
    effects = ev["effects"]
    whats = {e["what"] for e in effects}
    event = str(ev["event"]).casefold()
    own = ev["source"].split("/")[-1]
    if whats == {"write"}:
        return WRITE
    if event in CHANGE_EVENTS and words.affects_label(ev):
        return None          # пересчитывается надпись: это видно на экране, а не подстановка значения в соседнее поле
    if event == "началовыбора" and whats <= {"open_form", "value", "fill"} and all(set(e["affects"]) <= {own} for e in effects):
        return CHOICE
    if event in CHANGE_EVENTS and whats and whats <= VALUE_WHATS:
        affected = {a.split(".")[-1].casefold() for e in effects for a in e["affects"]}
        if affected & read:
            return None
        if affected & words.table_names and any(FILLS_ROWS.search(e["text"] or "") for e in effects):
            return None          # строки таблицы заполняются, очищаются или удаляются целиком — частность
        return OWN_TABLE if words.in_table(ev["source"]) else LINKED
    return None


def split(ctx, events, words):
    """`(частности, счёт обычного {категория: число})` по событиям, кроме событий открытия."""
    defaults = defaults_of(ctx)
    procedures = procedures_of(ctx)
    read = read_by_conditions(ctx)
    particular, counts = [], collections.OrderedDict()
    for ev in events:
        cat = category(ctx, ev, words, defaults, procedures, read)
        if cat is None:
            particular.append(ev)
        else:
            counts[cat] = counts.get(cat, 0) + 1
    return particular, counts


def silent_split(ctx, shown):
    """`{категория: число}` обработчиков, назначенных на форме, но не попавших в события обзора (разбор не нашёл у них следа на экране): категория из `code.defaults`, иначе «без видимого следа»;
    непрочитанные обработчики в счёт не идут."""
    from . import opening
    defaults = defaults_of(ctx)
    drawn = appearance_procedures(ctx)
    have = {(e["source"], e["event"]) for e in shown}
    out = collections.OrderedDict()
    for r in ctx.module.get("handlers") or ():
        if r["owner"] == "form" and str(r["event"]).casefold() in opening.OPEN_EVENTS:
            continue
        if ((r["element"] if r.get("element") else "форма"), r["event"]) in have:
            continue
        if str(r["procedure"]).casefold() in drawn:
            continue          # оформление и списки выбора обзор называет сам
        cat = defaults.get(str(r["procedure"]).casefold(), QUIET)
        out[cat] = out.get(cat, 0) + 1
    cover = ctx.module.get("coverage") or {}
    if QUIET in out:
        out[QUIET] = max(out[QUIET] - (cover.get("handlers", 0) - cover.get("parsed", 0)), 0)
        if not out[QUIET]:
            del out[QUIET]
    return out


def write_words(ctx):
    """Что «как обычно» для записи объекта: форма документа или элемента справочника записи и проведения не перехватывает, пока выше не названы её обработчики; проверки, отказы и сообщения при записи и
    проведении — в модуле объекта, а не в форме. У прочих форм — пусто."""
    kind = str(ctx.brief["head"].get("kind") or "")
    if kind == "document.item":
        return "запись и проведение документа — по правилам модуля объекта (его проверки, отказы и сообщения форма не меняет)"
    if kind.endswith(".item"):
        return "запись элемента — по правилам модуля объекта (его проверки, отказы и сообщения форма не меняет)"
    return ""


def rest_line(counts, writes=""):
    """Строка «Остальное — как обычно у формы этого вида: …» либо `None`: категории обычного с числами и слова о записи объекта (`write_words`). Обработчики «не проверено» (зовут код, которого навык не
    разобрал) обычными не названы: о них отдельная фраза."""
    unchecked = word("unchecked")
    names = [c for c in ORDER if c in counts] + [c for c in counts if c not in ORDER and c not in (QUIET, unchecked)] + ([QUIET] if QUIET in counts else [])
    parts = []
    if names or writes:
        listed = [f"{c} — {counts[c]}" for c in names] + ([writes] if writes else [])
        parts.append("Остальное — как обычно у формы этого вида: " + "; ".join(listed) + " (перечень — `brief --detail code`).")
    if unchecked in counts:
        parts.append(f"Не проверено: {counts[unchecked]} — обработчики зовут код других модулей, навык его не прочитал (перечень — `brief --detail code`).")
    return " ".join(parts) or None
