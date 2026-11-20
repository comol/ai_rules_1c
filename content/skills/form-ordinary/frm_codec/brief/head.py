"""Раздел «шапка» досье: вид формы, объект, версия, размер, DPI, что досье получило и чего нет."""

import pathlib

from .. import census, describe, design, edit
from . import vocab
from .fmt import _kind_words
from .paths import _display_path, _object_by_path


def _head(doc, form, rec, form_path, config_dir, meta, binder, module_text, style, images, hint_object=None, extra=None):
    layout_version = design.form_version(doc)
    dpi = (doc.get("form") or {}).get("dpi")
    obj = binder.obj
    missing = []
    common = rec["kind"] == "other:CommonForms"
    if config_dir is None:
        external = obj is not None and getattr(obj, "external", False)       # реквизиты внешнего объекта дал `--root-xml`: выгрузка нужна только стилю и ссылочным типам
        missing.append({"what": "выгрузка конфигурации (`--config`)", "without": vocab.WITHOUT["config_external" if external else "config"]})
    elif obj is None and not common and extra is None:
        missing.append({"what": f"объект формы в выгрузке (по типу основного реквизита; читаются {vocab.READ_WORDS})",
                        "without": vocab.WITHOUT["object"]})
    if module_text is None:
        missing.append({"what": "модуль формы (`form.bsl` рядом с формой)", "without": vocab.WITHOUT["module"]})
    if config_dir is not None and style["forms"] == 0:
        missing.append({"what": "соседние формы того же вида в выгрузке", "without": vocab.WITHOUT["neighbors"]})
    notes = []
    if layout_version != vocab.REFERENCE_VERSION:
        notes.append(f"версия общего блока формы — {layout_version}: картинки и нормы вида рассчитаны на версию {vocab.REFERENCE_VERSION}; "
                     "на этой форме возможны различия в оформлении элементов")
    if dpi is None:
        notes.append(f"в записи формы нет DPI (короткое поколение блока формы): она считается как DPI {vocab.REFERENCE_DPI}")
    elif dpi != vocab.REFERENCE_DPI:
        notes.append(f"DPI формы — {dpi}: размеры в пикселях, ширины текста, нормы вида и картинки рассчитаны на DPI {vocab.REFERENCE_DPI}; "
                     "оценки по ним на этой форме приблизительны")
    if images.get("note"):
        notes.append(images["note"])
    return {"form": _display_path(form_path, config_dir), "kind": rec["kind"], "kind_words": _kind_words(rec["kind"]),
            "kind_from": _kind_source(doc, form_path, rec["kind"]),
            "object": obj.full_name if obj is not None else (extra[0].full_name if extra is not None else None),
            "object_by_path": (hint_object or _object_by_path(form_path)) if obj is None and not common and extra is None else None,
            "object_note": "у общей формы объекта нет: её данные — реквизиты самой формы" if common else None,
            "layout_version": layout_version, "dpi": dpi,
            "size": [form.width, form.height], "fixed_size": doc.get("size_change") == "DontChange",
            "received": {"config": config_dir is not None, "config_object": obj is not None or extra is not None, "module": module_text is not None,
                         "neighbors": style["forms"]},
            "missing": missing, "notes": notes}


def _kind_source(doc, form_path, kind):
    """Слова о том, откуда вид формы, когда он по основному реквизиту формы расходится с видом по пути (обработка с реквизитом
    `ОтчетОбъект` — форма вида «отчёт»), либо `None`."""
    klass, obj, form = census.where(str(pathlib.Path(form_path).resolve()))
    by_path = census.kind_of(klass, obj, form, None)
    main = census.main_attribute(doc)
    if by_path == kind or by_path.startswith("other:") or main not in census.KNOWN or census.KNOWN[main] != kind:
        return None
    return (f"вид определён по основному реквизиту формы «{main}», а не по месту формы в конфигурации (по нему — {_kind_words(by_path)}): "
            f"нормы вида и замечания взяты от формы вида «{kind}»")


def _description(doc, meta, kind, object_name):
    try:
        return describe.describe(doc, meta, kind=kind if kind == "processing" else None, object_name=object_name).description
    except (edit.EditError, ValueError):
        return None


def _object_line(head):
    if head["object"]:
        return head["object"]
    if head.get("object_note"):
        return head["object_note"]
    if head.get("object_by_path"):
        why = "выгрузка конфигурации не задана" if not head["received"]["config"] else "в выгрузке объект не найден"
        return f"не определён ({why}); по пути формы — {head['object_by_path']}"
    return "не определён"


def _md_head(head):
    got = head["received"]
    lines = ["## 1. Шапка", "",
             f"- Форма: `{head['form']}`",
             f"- Вид формы: {head['kind']} ({head['kind_words']})" + (f"; {head['kind_from']}" if head.get("kind_from") else ""),
             f"- Объект: {_object_line(head)}",
             f"- Версия общего блока формы: {head['layout_version']}; DPI: {head['dpi'] if head['dpi'] is not None else 'не записан'}; "
             f"размер клиентской области: {head['size'][0]}×{head['size'][1]} px",
             "- Размер окна: " + (vocab.FIXED_SIZE_WORDS if head.get("fixed_size") else vocab.REMEMBERED_SIZE_WORDS),
             "- Получено: " + "; ".join([
                 "выгрузка конфигурации — " + ("да" if got["config"] else "нет"),
                 "модуль формы — " + ("да" if got["module"] else "нет"),
                 f"соседних форм того же вида — {got['neighbors']}"])]
    code = head.get("code") or {}
    if code.get("state") == "not_parsed":
        lines.append("- Код формы не разобран: что видно на экране, неизвестно (видимость, доступность, колонки и кнопки, которые создаёт код, отказ открыть форму); "
                     "разбор — задание `code-task.md` и инструкция `docs/brief-code.md`")
    elif code.get("state") == "parsed":
        lines.append(f"- Код формы разобран моделью: {len(code['accepted'])} записей; отклонено {len(code['rejected'])}")
        for r in code.get("form_title") or []:
            lines.append("- Заголовок формы задаёт код: " + (f"выражение «{r['expr']}»" if r["expr"] else f"«{r['value']}»") + (f", условие «{r['condition']}»" if r["condition"] else "")
                         + f" (строки {r['lines'][0]}–{r['lines'][1]})")
        for r in code.get("open_refused") or []:
            lines.append("- Форма может не открыться: " + (f"условие «{r['condition']}»" if r["condition"] else "безусловно") + (f", сообщение «{r['message']}» " if r["message"] else ", без сообщения ")
                         + f"(строки {r['lines'][0]}–{r['lines'][1]})")
    pic = head.get("pictures") or {}
    if pic:
        lines.append("- Скрытое на картинках: " + ("режим «hatch» — скрытое нарисовано на своём месте со штриховкой (подписи на картинке нет; кто скрыл — файл, код или запрос — назван в разделе 8); «как на экране» — `--hidden hide`"
                                                    if pic["hidden"] == "hatch" else "режим «hide» — скрытое не нарисовано, как на экране"))
        lines.append("- Условно скрываемое кодом: " + ("режим «hatch» — видимость, которую код меняет по условию или вероятно, нарисована со штриховкой, как скрытое (элемент, закладка страницы, шапка колонки, значок кнопки; подписи на картинке нет); как в файле — `--conditional plain`"
                                                       if pic.get("conditional") == "hatch" else "режим «plain» — условно скрываемое нарисовано как в файле, без штриховки; со штриховкой — `--conditional hatch`"))
        if pic["requested"]:
            lines.append("- Состояние формы по запросу (`--state`), накладывается поверх разбора кода: " + "; ".join(pic["requested"]))
    if head["missing"]:
        lines += ["- Чего нет и что без этого не оценить:"] + [f"  - {m['what']}: {m['without']}" for m in head["missing"]]
    for note in head["notes"]:
        lines.append(f"- Оговорка: {note}")
    return lines + [""]
