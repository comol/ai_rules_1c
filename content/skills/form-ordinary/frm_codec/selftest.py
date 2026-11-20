"""Самопроверка навыка на этой машине (`frm_json.py selftest`): формы, которые навык собирает сам.

Тесты навыка стоят на формах настоящих конфигураций и в комплект не входят. Самопроверка обходится без них: она строит заготовки всех видов,
правит их, рисует, собирает контейнер и проходит круг «файл → JSON → файл» на диске, во временном каталоге с кириллицей в пути. Так видно, что
навык работает с этой версией Python, кодировками и файловой системой. Проверки форм настоящих конфигураций она не заменяет.

`run()` — `(строки отчёта, число отказов)`; каждая проверка — строка «ok …» либо «ОТКАЗ …» с причиной, отказ одной не останавливает остальные.
"""
import pathlib
import platform
import shutil
import sys
import tempfile

from . import blank, formbin, formsource, render, typed, validate
from . import edit
from .tree import parse, read_file, render as render_text

TYPE_ID = "11111111-2222-3333-4444-555555555555"     # тип основного реквизита заготовок: любой GUID, выгрузка не нужна
BOM = blank.MODULE_BYTES


def _blanks():
    """Заготовки всех видов: `[(вид, байты form.frm)]`."""
    out = [(kind, blank.build(kind, type_id=TYPE_ID).frm_bytes()) for kind in blank.KINDS]
    return out + [("processing --dialog", blank.build("processing", dialog=True).frm_bytes())]


def _round(data):
    """Круг «текст → JSON → текст» байт в байт и три уровня проверки без отказа; документ уровня 1."""
    text = data.decode("utf-8")
    doc = typed.decode(parse(text))
    fatal = [p.text for p in validate.validate(doc) if p.fatal]
    if fatal:
        raise AssertionError("проверка отказала: " + fatal[0])
    again = render_text(typed.encode(doc))
    if again != text:
        raise AssertionError("сборка разошлась с исходным текстом")
    return doc


def check_blanks():
    names = []
    for kind, data in _blanks():
        _round(data)
        names.append(kind)
    return f"заготовки {', '.join(names)}: разбор, проверка и сборка байт в байт"


def check_edit():
    doc = typed.decode(parse(blank.build("processing", type_id=TYPE_ID).frm_bytes().decode("utf-8")))
    doc, bsl, _log = edit.apply(doc, [{"op": "set_form_title", "text": "Самопроверка"},
                                      {"op": "append_procedure", "name": "Самопроверка", "body": ["Возврат;"]}], BOM)
    _round(render_text(typed.encode(doc)).encode("utf-8"))
    if not bsl.startswith(BOM) or bsl.count(b"\r\n") != bsl.count(b"\n") or b"\r\n" not in bsl:
        raise AssertionError(f"модуль после append_procedure: {bsl[:40]!r} — ожидались BOM и CRLF")
    return "правка: заголовок формы и процедура модуля (BOM и CRLF сохранены)"


def check_render():
    doc = typed.decode(parse(blank.build("document.list", type_id=TYPE_ID).frm_bytes().decode("utf-8")))
    svg = render.render(doc).svg
    if not svg.lstrip().startswith("<svg") or "</svg>" not in svg:
        raise AssertionError("рендер не дал SVG")
    return f"рендер формы списка: SVG {len(svg)} знаков"


def check_container():
    data = blank.build("catalog.item", type_id=TYPE_ID).frm_bytes()
    sections = {formbin.SECTION_FORM: data, formbin.SECTION_MODULE: BOM}
    if formbin.unpack(formbin.pack(sections)) != sections:
        raise AssertionError("Form.bin: разобранные секции не равны собранным")
    return "Form.bin: сборка и разбор секций"


def check_files():
    root = pathlib.Path(tempfile.mkdtemp(prefix="form-ordinary-selftest-"))
    try:
        ext = root / "Формы" / "Проба" / "Ext"
        ext.mkdir(parents=True)
        (ext / "form.frm").write_bytes(blank.build("document.item", type_id=TYPE_ID).frm_bytes())
        lines, code = formsource.create_command(ext, force=True)
        if code:
            raise AssertionError("; ".join(lines))
        doc = typed.decode(formsource.read_form_node(ext / formbin.BIN_NAME))
        if doc != typed.decode(read_file(ext / "form.frm")):
            raise AssertionError("форма из Form.bin не равна form.frm")
        return "файлы: Form.bin создан и прочитан в каталоге с кириллицей в пути"
    finally:
        shutil.rmtree(root, ignore_errors=True)


CHECKS = (check_blanks, check_edit, check_render, check_container, check_files)


def run():
    lines = [f"Python {platform.python_version()} ({sys.platform}), кодировка файловой системы {sys.getfilesystemencoding()}"]
    failed = 0
    for check in CHECKS:
        try:
            lines.append("ok    " + check())
        except Exception as e:  # noqa: BLE001 — отказ одной проверки не останавливает остальные и называется словами
            failed += 1
            name = check.__name__
            lines.append(f"ОТКАЗ {name[len('check_'):] if name.startswith('check_') else name}: {type(e).__name__}: {e}")
    lines.append(f"Самопроверка пройдена: проверок {len(CHECKS)}" if not failed
                 else f"Самопроверка: отказов {failed} из {len(CHECKS)}")
    return lines, failed
