"""Командная строка кодека обычных форм 1С 8.x.

Отказ печатается словами в stderr с кодом 1: команду читает человек, а `decode`, `diff` и `stat` печатают в
stdout данные, и отказ в том же потоке попал бы в конвейер. Дефект самого кодека выводит трассировку. Замечания
проверки (`ОТКАЗ (уровень N)`, `Предупреждение`) идут в stdout: это ответ команды `validate`, а не сбой. Все
названные отказы кодека (`Json0Error`, `FrmSyntaxError`, `SchemaError`, `TypedError`) — наследники `ValueError`
и перехватываются одним `except`.

Кроме них перехватывается `OSError`: каталог вместо файла, приёмник без права записи, слишком длинное имя — это
тоже названные отказы.
"""
import argparse, collections, copy, json, os, pathlib, shutil, sys, tempfile, textwrap

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
for _stream in (sys.stdout, sys.stderr):
    # Оба потока, а не один: отказ выводится в stderr по-русски, а команду запускают и на Windows, где кодировка
    # консоли по умолчанию не UTF-8.
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from frm_codec import census, patterns as patterns_mod
from frm_codec import addfield as addfield_mod, blank as blank_mod, design as design_mod, describe as describe_mod, edit as edit_mod, generate as generate_mod, meaning, schema, stat, typed
from frm_codec import metadata as metadata_mod
from frm_codec import brief as brief_mod
from frm_codec import formstate as formstate_mod
from frm_codec.brief import code_marks as brief_marks_mod, codenotes as brief_notes_mod, modulescan as brief_scan_mod
from frm_codec import formsource, configpics
from frm_codec import pagerefs as pagerefs_mod, guides as guides_mod, limits as limits_mod, layout as layout_mod, lint as lint_mod, preview as preview_mod, render as render_mod, repair as repair_mod, strip as strip_mod, validate as validate_mod
from frm_codec.layout import drag as drag_mod
from frm_codec.edit import final as edit_final_mod, scope as edit_scope_mod
from frm_codec.diff import change_dict, diff as diff_trees, find_named, path_str
from frm_codec.json0 import decode0, dumps, dumps_line, encode0, loads
from frm_codec.tree import parse as parse_text, read_file, render, write_file

SKILL = pathlib.Path(__file__).resolve().parent


def _notes(lines, stream=None):
    """Пояснения о том, откуда взята форма и что сделано с `Form.bin`: команды чтения печатают их в stderr (в stdout у
    них данные), команды правки — в stdout вместе с отчётом."""
    for line in lines:
        print(line, file=stream or sys.stderr)


def _form_node(path):
    """Дерево формы для команды чтения: `form.frm`, `Form.bin` (распаковывается в памяти, на диск ничего не пишется),
    каталог `Ext` или каталог формы. Любой другой файл читается как скобочный текст формы."""
    if not formsource.is_form_ref(path):
        return read_file(path)
    notes = []
    node, _ref = formsource.read_tree(path, notes)
    _notes(notes)
    return node


def _form_or_doc(path, level1=None):
    """Документ уровня 1 и путь его формы для команды чтения: форма (`form.frm`, `Form.bin`, каталог) разбирается картой,
    любой другой файл — документ уровня 1 (`.json`). Путь формы без `form.frm` указывает на место, где файл лежал бы."""
    if formsource.is_form_ref(path):
        notes = []
        node, ref = formsource.read_tree(path, notes)
        _notes(notes)
        return typed.decode(node), ref.frm
    return (level1 or _read_doc)(path), pathlib.Path(path)


def _out(path, flag, form=True):
    """Файл вывода команды: `Form.bin` и каталог отказывают до любой работы (`formsource.check_output`)."""
    if path:
        formsource.check_output(path, flag, form)
    return path


def _finish(paths, was, source=None):
    """После записи: недостающие файлы формы раскладываются рядом с `Form.bin` в каталоге записи, и `Form.bin` собирается
    заново, если содержимое разошлось с его секциями (в каталоге с внешней сборкой не собирается)."""
    notes = []
    try:
        formsource.finish_write([pathlib.Path(p) for p in paths if p], notes, was, source)
    finally:
        _notes(notes, sys.stdout)


def _read_json(path):
    return loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _read_doc(path):
    """Документ уровня 1 (или сырое дерево) из файла. Прежние имена краёв блока координат (`width`, `height`) —
    отказ `TypedError` со словами (подкласс `ValueError`, `main` печатает его как отказ): раскладка и дизайн ищут
    края по `right`/`bottom`."""
    doc = _read_json(path)
    return typed.refuse_old_coords(doc) if isinstance(doc, dict) else doc


def _write(path, text):
    """Вывод в файл или на экран выполняется одним писателем (`json0.dumps`): `json.dumps` взял бы дробное число в
    кавычки (`Dec` — подкласс `str`), и `encode` собрал бы из такого файла строку вместо числа."""
    if path:
        pathlib.Path(path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


# Сколько предупреждений о длине блока печатается поштучно; больше — одной строкой сводки (полный перечень — `--all-warnings`).
LENS_LISTED = 3


def _say(problems, was=None, all_warnings=False):
    """Замечания выводятся на экран одним форматом строки для команд, которые их печатают (`encode`, `validate`, `edit`).

    `was` — замечания исходной формы (`edit`): предупреждение, которое есть и у неё, помечено «было и в исходной форме» и идёт после новых.

    Предупреждения о длине блока вне виденных корпусом (`validate.LENS`) у формы старой конфигурации идут сотнями, а форма при этом собирается
    байт в байт. Больше `LENS_LISTED` таких предупреждений печатаются одной строкой: число позиций по видам элементов. У `edit` поштучно
    печатаются новые, сводкой — те, что были и в исходной форме. `all_warnings` печатает все поштучно."""
    old = {(p.level, p.where, p.text) for p in was or () if not p.fatal}
    fresh = [p for p in problems if p.fatal or (p.level, p.where, p.text) not in old]
    stale = [p for p in problems if not p.fatal and (p.level, p.where, p.text) in old]
    lens_fresh = [p for p in fresh if p.kind == validate_mod.LENS]
    lens_stale = [p for p in stale if p.kind == validate_mod.LENS]
    fold_fresh = not all_warnings and was is None and len(lens_fresh) > LENS_LISTED
    fold_stale = not all_warnings and len(lens_stale) > LENS_LISTED
    for p in fresh:
        if not (fold_fresh and p.kind == validate_mod.LENS):
            print(f"{'ОТКАЗ' if p.fatal else 'Предупреждение'} (уровень {p.level}): {p.text}")
    if fold_fresh:
        print(f"Предупреждение (уровень 2): {_lens_summary(lens_fresh)}")
    for p in stale:
        if not (fold_stale and p.kind == validate_mod.LENS):
            print(f"Предупреждение (уровень {p.level}, было и в исходной форме): {p.text}")
    if fold_stale:
        print(f"Предупреждение (уровень 2, было и в исходной форме): {_lens_summary(lens_stale)}")


def _lens_summary(found):
    """Одна строка вместо перечня предупреждений о длине блока: сколько позиций и у каких видов элементов."""
    kinds = collections.Counter(p.where.split(" ")[0] for p in found)
    platform = sum(1 for p in found if "платформа записывает сама" in p.text)
    shown = ", ".join(f"{kind} {n}" for kind, n in kinds.most_common())
    return (f"длина блока вне виденных корпусом — {schema.plural(len(found), 'позиция', 'позиции', 'позиций')} ({shown})"
            + (f", из них {platform} — длины, которые платформа записывает сама" if platform else "")
            + ". Длин блоков карта не знает: у формы, сохранённой конфигуратором, это не поломка; у правленой руками — сверяйте с исходным "
              "файлом (короткий блок по праву от блока с убранным последним полем u… не отличить). Перечень — ключ --all-warnings")


def cmd_decode(args):
    _out(args.out, "-o", form=False)
    root = _form_node(args.form)
    doc = decode0(root) if args.raw else typed.decode(root)
    _write(args.out, dumps(doc))
    if args.out:
        level = 0 if args.raw else 1
        print(f"Записано (уровень {level}): {args.out}")
    return 0


def cmd_encode(args):
    _out(args.out, "-o")
    doc = _read_doc(args.json)
    was = formsource.exists_before([args.out])
    # Уровень определяется до проверки: у сырого дерева (списка) нет ни ключей, ни карты, и три уровня проверки
    # к нему не применимы.
    if isinstance(doc, list):
        node = encode0(doc)
        write_file(args.out, node)
        print(f"Записано (уровень 0): {args.out} ({len(render(node).encode('utf-8'))} байт)")
        _finish([args.out], was)
        return 0
    problems = validate_mod.validate(doc)
    _say(problems, all_warnings=getattr(args, "all_warnings", False))
    if validate_mod.fatal(problems):
        return 1
    node = typed.encode(doc)
    write_file(args.out, node)
    print(f"Записано: {args.out} ({len(render(node).encode('utf-8'))} байт)")
    _finish([args.out], was)
    return 0


def cmd_validate(args):
    """Проверка формы: документ уровня 1 (`.json`) либо сама форма (`form.frm`, `Form.bin`, каталог формы) — её команда сначала разбирает картой."""
    if formsource.is_form_ref(args.json):
        doc, _form = _form_or_doc(args.json)
    else:
        doc = _read_json(args.json)  # прежние имена краёв координат отказывает сам validate — на каждом месте, где они стоят
    if isinstance(doc, list):
        # Уровень 0 проверять нечем: у сырого дерева нет ни ключей, ни карты. Сказать об этом нужно словами,
        # иначе «замечаний нет» читалось бы как «документ проверен».
        raise ValueError("это уровень 0 (сырое дерево): трёх уровней проверки к нему нет, "
                         "проверку обратным разбором выполняет команда encode")
    problems = validate_mod.validate(doc, config=_config_of(args))
    _say(problems, all_warnings=getattr(args, "all_warnings", False))
    if not problems:
        print("Проверка пройдена: три уровня без замечаний")
    if not validate_mod.fatal(problems):
        _say_layout(doc)
    return 1 if validate_mod.fatal(problems) else 0


LAYOUT_WARNING = "Предупреждение раскладки"


def _say_layout(doc, before=()):
    """Замечания раскладки выводятся отдельной строкой после трёх уровней проверки.

    Они не входят в `validate.validate`: проверка там — условие сборки и правки («операция не добавляет новых
    замечаний»), а раскладку считает вся форма целиком. Иначе каждое `add_element anchor="form"` (редактор пока
    не пишет для него встречных записей) нарушало бы проверку в чужой операции. На код возврата замечания
    раскладки не влияют.

    Функция вызывается только для документа без фатальных замечаний: если `validate` документ отверг, раскладка
    не считается. Строка называется «Предупреждение раскладки», а не «уровень 2»; при одних только замечаниях
    раскладки «Проверка пройдена» остаётся. `before` — замечания формы до правки (`edit`): печатаются только
    новые или изменившиеся."""
    seen = {(kind, text) for kind, _where, text in before}
    found = [p for p in layout_mod.problems(doc) if (p[0], p[2]) not in seen]
    for _kind, where, text in found:
        print(f"{LAYOUT_WARNING}: {'/'.join(str(p) for p in where)}: {text}")
    return found


def _say_limits(before, after):
    """Строки о смене пределов раскладки после правки: сужение — предупреждение (операции не отменяются), расширение — строка отчёта."""
    changes = limits_mod.compare(before, after)
    narrowed, widened = limits_mod.narrowed_words(changes), limits_mod.widened_words(changes)
    if narrowed:
        print(f"Предупреждение пределов раскладки: {narrowed}")
    if widened:
        print(f"Раскладка: {widened}")


def cmd_edit(args):
    """Правка формы перечнем операций: разбор, операции, проверка, обратный разбор, запись.

    Порядок одинаков для всех отказов: сначала вся работа, потом вся запись. Проверка выполняется после операций
    и до записи: собранная форма, о которой уровень 1 сказал «не соберётся», платформе не показывается. Форма и
    модуль записываются парой, в самом конце, через временные файлы рядом с целевыми: при отказе на любом шаге
    диск остаётся таким, каким был.

    Проверку «собранный файл читается обратно в тот же документ» выполняет сама сборка (самопроверка
    `typed.encode`): при правке вручную в JSON можно положить значение, которое запишется, но прочитается иначе.

    Модуль формы правится вместе с формой и только по запросу: `--bsl` и `--bsl-out` задаются оба или ни одного.
    Модуль читается и пишется байтами: у файла есть BOM и свой перевод строк.
    """
    if bool(args.bsl) != bool(args.bsl_out):
        named, missing = ("--bsl", "--bsl-out") if args.bsl else ("--bsl-out", "--bsl")
        raise ValueError(f"{named} без {missing}: модуль формы правится вместе с формой, и "
                         "нужны оба — откуда его взять и куда положить")
    _out(args.out, "-o")
    _out(args.bsl_out, "--bsl-out")
    ref = None
    if formsource.is_form_ref(args.form):
        notes = []
        data, ref = formsource.source_for_write(args.form, notes)
        _notes(notes, sys.stdout)
        form_path = ref.frm
        doc = typed.decode(parse_text(data.decode("utf-8")))
    else:
        form_path = pathlib.Path(args.form)
        doc = typed.decode(read_file(form_path))
    render_to = getattr(args, "render", None)
    original = copy.deepcopy(doc)
    ops = _read_json(args.ops)
    module_before = formsource.read_bsl(args.bsl) if args.bsl else _module_beside(form_path)
    if not isinstance(ops, list):
        raise ValueError("перечень операций — это массив JSON: "
                         "[{\"op\": \"add_button\", \"bar\": \"CB1\", …}, …]")
    before = layout_mod.problems(doc)
    bsl = formsource.read_bsl(args.bsl) if args.bsl else None
    siblings = None
    if args.siblings:
        siblings, said = _siblings(form_path, args.siblings, getattr(args, "origin", None))
        print(said)
    config = _config_of(args) if getattr(args, "root_xml", None) or getattr(args, "config", None) else None
    doc, bsl, log = edit_mod.apply(doc, ops, bsl, siblings, config, final_captions=True)
    for line in log:
        print(line)
    for line in edit_mod.page_index_lines(ops, bsl if args.bsl else module_before):      # перестановка страниц меняет их номера, а код модуля не правится
        print(line)
    problems = validate_mod.validate(doc, config=config)
    _say(problems, validate_mod.validate(original, config=config), all_warnings=getattr(args, "all_warnings", False))
    if validate_mod.fatal(problems):
        return 1
    _say_layout(doc, before)
    _say_limits(original, doc)
    node = typed.encode(doc)
    was = formsource.exists_before([args.out, args.bsl_out])
    written = [(args.out, render(node).encode("utf-8"))]
    if args.bsl_out:
        written.append((args.bsl_out, bsl))
    for path, size in _write_all(written):
        print(f"Записано: {path} ({size} байт)" + (", проверка обратным разбором уровня 1 пройдена"
                                                   if path == args.out else ""))
    _finish([args.out, args.bsl_out], was, ref)
    captions = [op["element"] for op in ops if isinstance(op, dict) and op.get("op") == "set_caption" and isinstance(op.get("element"), str)]
    for line in edit_final_mod.caption_lines(doc, captions, original, str(form_path.resolve())) if captions else []:
        print(line)
    if render_to:
        marks = _code_marks_pair(original, doc, form_path, module_before, bsl if args.bsl else module_before, getattr(args, "code_notes", None),
                                 getattr(args, "root_xml", None))
        failed = _show_change(*_with_coded_titles(original, doc, marks), render_to, marks=marks)
        if failed:
            print(f"Форма записана; {failed}")
    for line in edit_scope_mod.summarize(original, doc, ops):
        print(line)
    return 0


def _code_marks_pair(original, doc, form_path, module_before, module_after, notes_path, root_xml=None):
    """Пометки кода «до» и «после» для `edit --render --code-notes`; отклонённые записи и отсутствие модуля называются в stderr."""
    if not notes_path:
        return (None, None)
    notes = brief_notes_mod.read(notes_path)
    marks = (brief_marks_mod.module_marks(original, form_path, module_before, notes, root_xml=root_xml),
             brief_marks_mod.module_marks(doc, form_path, module_after, notes, root_xml=root_xml))
    _say_code_marks(marks[0], module_before)
    return marks


def _say_code_marks(marks, module):
    """В stderr: пометки кода не построены (нет модуля с кодом) либо записи, которые проверка отклонила, — как в `brief`."""
    if brief_scan_mod.effective(module) is None:
        print("--code-notes: рядом нет модуля формы с кодом (form.bsl) — пометки кода не построены", file=sys.stderr)
    for item in (marks.rejected if marks is not None else ()):
        print(f"Запись {item['index']} ({item['kind'] or '?'}) отклонена: {item['why']}", file=sys.stderr)


def _with_coded_titles(original, doc, marks):
    """Документы «до» и «после» с заголовками, которые код ставит безусловно, — как рисунок досье (`brief.images.coded_doc`)."""
    from frm_codec.brief import images as brief_images
    return tuple(brief_images.coded_doc(d, m)[0] if m is not None else d for d, m in zip((original, doc), marks))


def _module_beside(form_path):
    """Модуль формы рядом с `form.frm` (`form.bsl`, а при `Form.bin` без него — из контейнера) либо `None`: пометки кода на рисунке строятся по нему."""
    try:
        return formsource.read_bsl(pathlib.Path(form_path).with_name("form.bsl"))
    except (OSError, ValueError):
        return None


def _write_all(pairs):
    """Записывает все файлы парой: сначала временные рядом с целевыми, потом переименование.

    Переименование в пределах одного каталога атомарно; временный файл лежит рядом с целевым, чтобы оно не
    оказалось переносом между дисками. Если запись любого файла сорвалась, всё временное удаляется, и ни один
    целевой файл не меняется.
    """
    made = []
    try:
        for path, data in pairs:
            target = pathlib.Path(path)
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(data)
            made.append((tmp, target, len(data)))
        for tmp, target, _size in made:
            os.replace(tmp, target)
    except OSError:
        for tmp, _target, _size in made:
            tmp.unlink(missing_ok=True)
        raise
    return [(str(target), size) for _tmp, target, size in made]


def cmd_design(args):
    """Один дизайн формы: внутри формы и в сравнении с соседними формами каталога выгрузки.

    Внутри формы проверяется версия общего блока оформления у контейнера и у каждого элемента (смесь версий —
    предупреждение, как в `validate`) и сочетания оформления по типам. С `--siblings` форма сравнивается со
    сводками остальных форм каталога (`design.compare`): версия и стиль большинства, самое частое сочетание для
    типа, сочетания, которых у соседей нет совсем. Всё это предупреждения: код возврата 0; отказ (1) — только
    если саму форму не удалось прочитать.

    Форму можно передать файлом `form.frm` или документом уровня 1 (`.json`): отредактированный JSON сверяется
    до сборки. Соседи — все `*.frm` под каталогом, кроме самой формы; для документа уровня 1 исключается и его
    форма рядом (`form.json` или `form.frm.json` → `form.frm`), потому что сравнивать документ с ней значило бы
    сравнивать его с самим собой. Если прочитаны не все соседи, число непрочитанных называется. Соседи читаются
    пулом процессов."""
    doc, form = _form_or_doc(args.form)
    if not isinstance(doc, dict):
        raise ValueError("это уровень 0 (сырое дерево): оформление читается картой, дайте form.frm "
                         "или документ уровня 1")
    info, warnings = design_mod.in_form(doc)
    # Раскладка считается отдельно: «один дизайн» и раскладка — разные вопросы. Если `validate` документ отверг,
    # раскладка не считается.
    counted = not validate_mod.fatal(validate_mod.validate(doc))
    layout_found = layout_mod.problems(doc) if counted else []
    info = info + (_layout_design(doc) if counted else [])
    if args.siblings:
        siblings, said = _siblings(form, args.siblings, getattr(args, "origin", None))
        more, found = design_mod.compare(design_mod.summary(doc), siblings)
        info += [said] + more
        warnings += found
    for line in info:
        print(line)
    for _kind, text in warnings:
        print(f"Предупреждение: {text}")
    for _kind, _where, text in layout_found:
        print(f"{LAYOUT_WARNING}: {text}")
    print(f"Итог: предупреждений {len(warnings)}")
    if counted:
        print(f"Итог раскладки: предупреждений {len(layout_found)}")
    return 0


def cmd_lint(args):
    """Линтер ритма (`frm_codec.lint`): замечания к форме по нормам её вида и по раскладке.

    Проверяются ритм (отступы, шаг и высоты вне диапазона нормы вида), привязки, не соответствующие норме роли,
    наложение элементов, выход за форму, поле уже минимума, смесь версий и вида (со ссылкой на `design`). В
    каждом замечании указаны число из нормы и доля. Замечания не являются отказами: код возврата 0; отказ (1) —
    если форму нельзя прочитать или `validate` отверг документ (для такого документа раскладка не считается).
    Вид определяется по пути формы в выгрузке (`…/Catalogs/<Имя>/Forms/…`), иначе берётся из `--kind`;
    `--siblings` добавляет сравнение со своей конфигурацией (как у `design`)."""
    doc, form = _form_or_doc(args.form)
    if not isinstance(doc, dict):
        raise ValueError("это уровень 0 (сырое дерево): линтер читает документ уровня 1, дайте form.frm или документ уровня 1")
    problems = validate_mod.validate(doc)
    if validate_mod.fatal(problems):
        first = next(p for p in problems if p.fatal)
        raise ValueError("документ не проходит проверку, раскладку и ритм по нему считать нельзя: " + first.text +
                         " (подробно: frm_json.py validate)")
    siblings = None
    said = None
    if args.siblings:
        siblings, said = _siblings(form, args.siblings, getattr(args, "origin", None))
    result = lint_mod.lint(doc, str(form.resolve()), kind=args.kind, siblings=siblings, config=_config_of(args))
    for line in result.info + ([said] if said else []):
        print(line)
    for remark in result.remarks:
        print(f"Замечание [{remark.rule}]: {remark.text}")
    by = collections.Counter(r.group for r in result.remarks)
    print(f"Итог: замечаний {len(result.remarks)}" + (" (" + ", ".join(f"{lint_mod.GROUPS[k]} {v}" for k, v in sorted(by.items())) + ")" if by else ""))
    return 0


def cmd_brief(args):
    """Досье формы для модели (`frm_codec.brief`): `brief.md`, `brief.json` и три картинки в каталоге досье.

    Форма — `form.frm`, `Form.bin`, каталог формы или документ уровня 1. Модуль берётся из `form.bsl` рядом с формой (при `Form.bin` без
    `form.bsl` — из контейнера); без модуля, выгрузки (`--config`) и соседних форм досье строится, а шапка называет недостающее.
    Умолчание `-o` — `.v8tmp/brief/` рядом с формой. Форму досье не меняет. Форма, которую проверка отвергает или раскладка не читает, —
    слова в stderr и код 2."""
    doc, form = _form_or_doc(args.form)
    if not isinstance(doc, dict):
        raise ValueError("это уровень 0 (сырое дерево): досье читает документ уровня 1, дайте form.frm или документ уровня 1")
    fatal = [p for p in validate_mod.validate(doc) if p.fatal]
    if fatal:
        print(f"ОТКАЗ: документ не проходит проверку (отказов {len(fatal)}, первый — уровень {fatal[0].level}: {fatal[0].text}) — "
              "досье по нему не строю; все замечания назовёт frm_json.py validate", file=sys.stderr)
        return 2
    out = pathlib.Path(args.out) if args.out else form.parent / brief_mod.DEFAULT_DIR
    if out.is_file():
        raise ValueError(f"-o называет файл ({out}): нужен каталог досье")
    module = None
    try:
        module = brief_scan_mod.effective(formsource.read_bsl(form.with_name("form.bsl")))       # модуль без процедур и операторов — модуля нет
    except (OSError, ValueError):
        pass
    if args.code_notes and args.no_code:
        raise ValueError("--code-notes и --no-code вместе не нужны: первый собирает досье с разбором кода, второй — без него")
    if args.code_notes and module is None:
        raise ValueError("--code-notes: у формы нет модуля (form.bsl рядом или модуль в контейнере), разбирать нечего")
    notes = brief_notes_mod.read(args.code_notes) if args.code_notes else None
    if module is not None and notes is None and not args.no_code:
        command = f"frm_json.py brief {args.form}" + (f" --config {args.config}" if args.config else "") + (f" --root-xml {args.root_xml}" if args.root_xml else "") + f" --code-notes {out / 'code-notes.json'}" + (
            f" -o {args.out}" if args.out else "")
        try:
            task = brief_mod.code_task(doc, form, args.config, out, module, f"`{command}`", root_xml=args.root_xml)
        except edit_mod.EditError as why:
            print(f"ОТКАЗ: {why}", file=sys.stderr)
            return 2
        except PermissionError as why:
            print(f"ОТКАЗ: в каталог досье «{out}» писать нельзя ({why.strerror}): каталог формы доступен только для чтения — "
                  "назовите другой каталог ключом -o", file=sys.stderr)
            return 1
        print("Сначала разбор кода по docs/brief-code.md, затем " + command)
        print(f"Задание на разбор кода: {task['task']}")
        print(f"Модуль формы (номера строк записей — его): {task['module']}")
        print(f"Заготовка записей: {task['notes']}")
        print(f"Досье не собрано; без разбора кода: frm_json.py brief {args.form} --no-code" + (f" --config {args.config}" if args.config else "") + (f" --root-xml {args.root_xml}" if args.root_xml else "") + (f" -o {args.out}" if args.out else ""))
        return 0
    try:
        state = formstate_mod.read(args.state) if args.state else None
        if state is not None and args.hidden:
            state["hidden"] = args.hidden          # ключ командной строки сильнее поля `hidden` файла состояния
        if state is not None and args.conditional:
            state["conditional"] = args.conditional
        brief = brief_mod.build(doc, form, args.config, out, module, getattr(args, "origin", None), notes, state, args.hidden or (state or {}).get("hidden", "hatch"), args.conditional or (state or {}).get("conditional", "plain"),
                                getattr(args, "detail", None), root_xml=args.root_xml)
    except edit_mod.EditError as why:
        print(f"ОТКАЗ: {why}", file=sys.stderr)
        return 2
    except PermissionError as why:
        print(f"ОТКАЗ: в каталог досье «{out}» писать нельзя ({why.strerror}): каталог формы доступен только для чтения — "
              "назовите другой каталог ключом -o", file=sys.stderr)
        return 1
    print(f"Досье: {out / 'brief.md'}")
    if getattr(args, "detail", None):
        print(f"Подробности: {out / 'brief-full.md'}")
    print(f"Досье для машины: {out / 'brief.json'}")
    images = brief["images"]
    if "error" in images:
        print(images["error"], file=sys.stderr)
    else:
        for key in ("clean", "marked", "behavior"):
            print(f"Картинка {key}: {out / images[key]}")
        if images["note"]:
            print(images["note"], file=sys.stderr)
    head = brief["head"]
    for item in head["missing"]:
        print(f"Нет: {item['what']} — {item['without']}", file=sys.stderr)
    code = head.get("code") or {}
    if code.get("masked"):
        print(f"Учётные данные (Pwd=, User ID=, UID= и им подобные) в записях разбора и модуле заменены на ***: {code['masked']}; уберите их из code-notes.json", file=sys.stderr)
    if code.get("state") == "parsed":
        print(f"Разбор кода: принято записей {len(code['accepted'])}, отклонено {len(code['rejected'])}")
        cover_log = brief["purpose"]["module"].get("coverage") or {}
        print(f"Журнал сборок: {brief_notes_mod.log_build(out, code['accepted'], code['rejected'], len(cover_log.get('unparsed') or ()))}")
        for item in code["rejected"]:
            print(f"Запись {item['index']} ({item['kind'] or '?'}) отклонена: {item['why']}", file=sys.stderr)
        for item in code.get("warnings") or ():
            print(f"Предупреждение: {item}", file=sys.stderr)
        cover = brief["purpose"]["module"].get("coverage") or {}
        if cover.get("unparsed"):
            print(f"Не разобран ({cover['unit']} разобрано {cover['parsed']} из {cover['handlers']}): " + ", ".join(cover["unparsed"][:30])
                  + (f" …и ещё {len(cover['unparsed']) - 30}" if len(cover["unparsed"]) > 30 else "") + " — запись при частности, default при умолчании", file=sys.stderr)
        if code.get("uncovered"):
            print(f"Не разобрано на пути открытия: {len(code['uncovered'])} " + ("строка" if len(code["uncovered"]) == 1 else "строк") + f"; полный перечень — {out / 'uncovered.txt'}",
                  file=sys.stderr)
    elif code.get("state") == "not_parsed":
        print("Код формы не разобран: что видно на экране, неизвестно (--no-code)", file=sys.stderr)
    return 0


def _checked_doc(path):
    """Документ уровня 1 для команд привязок: уровень 0 и документ, не прошедший `validate`, — отказ словами."""
    doc, _path = _form_or_doc(path)
    if not isinstance(doc, dict):
        raise ValueError("это уровень 0 (сырое дерево): привязки читаются картой, дайте form.frm или документ уровня 1")
    fatal = [p for p in validate_mod.validate(doc) if p.fatal]
    if fatal:
        raise ValueError(f"документ не проходит проверку (отказов {len(fatal)}, первый — уровень {fatal[0].level}: {fatal[0].text}) — "
                         "привязки по нему не считаю; все замечания назовёт frm_json.py validate")
    return doc


def cmd_anchors_check(args):
    """Диагноз поломок привязок (`frm_codec.repair.diagnose`): форма не растягивается, столкновения при малом изменении размера, наезды,
    расхождение выравнивания, мёртвые правила, циклы, формальные рисунки. У каждой поломки названы виновники. Код возврата 0."""
    doc = _checked_doc(args.form)
    found = repair_mod.diagnose(doc)
    if found.error:
        raise ValueError(found.error)
    if not found.findings:
        print("поломок привязок нет")
    for line in repair_mod.describe(found):
        print(line)
    for line in guides_mod.far_words(doc):
        print(line.strip())
    for line in guides_mod.below_words(doc):
        print(line.strip())
    panel_lines = guides_mod.panel_words(doc)
    for line in panel_lines:
        print(line.strip())
    if panel_lines:
        print("исправляет: frm_json.py edit form.frm --ops '[{\"op\": \"normalize_guides\"}]' -o out.frm (направляющие от панелей на 8 px, элементы не двигаются)")
    if found.findings:
        print("исправляет: frm_json.py repair-anchors (с --dry-run — только отчёт)")
    for line in found.info[:3]:
        print(line)
    if len(found.info) > 3:
        print(f"справка: и ещё {len(found.info) - 3} (не поломки)")
    return 0


def cmd_repair_anchors(args):
    """Исправление привязок (`repair_anchors`): диагноз, `normalize_anchors` по формальным рисункам, затем по каждому виновнику наименьшая
    правка из кандидатов движка выбора привязок. `box` не меняется. `--dry-run` печатает отчёт, ничего не записывая; иначе нужен `-o`."""
    if not args.dry_run and not args.out:
        raise ValueError("назовите -o ФАЙЛ (куда записать исправленную форму) либо --dry-run (только отчёт)")
    op = {"op": "repair_anchors"}
    if args.element:
        op["elements"] = list(args.element)
    if args.dry_run:
        op["dry_run"] = True
    if args.unverified:
        op["unverified"] = True
    ref = None
    if args.dry_run:
        doc = _checked_doc(args.form)
    else:
        _out(args.out, "-o")
        if formsource.is_form_ref(args.form):
            notes = []
            data, ref = formsource.source_for_write(args.form, notes)
            _notes(notes, sys.stdout)
            doc = typed.decode(parse_text(data.decode("utf-8")))
        else:
            doc = typed.decode(read_file(pathlib.Path(args.form)))
    original = copy.deepcopy(doc)
    doc, _bsl, log = edit_mod.apply(doc, [op], None, None, None)
    for line in log:
        print(line)
    if args.dry_run:
        return 0
    problems = validate_mod.validate(doc)
    _say(problems)
    if validate_mod.fatal(problems):
        return 1
    _say_limits(original, doc)
    node = typed.encode(doc)
    was = formsource.exists_before([args.out])
    for path, size in _write_all([(args.out, render(node).encode("utf-8"))]):
        print(f"Записано: {path} ({size} байт), проверка обратным разбором уровня 1 пройдена")
    _finish([args.out], was, ref)
    return 0


def _layout_design(doc):
    """Строка сведений о раскладке для `design`: в каких пределах она следует за размером окна."""
    try:
        form = layout_mod.read(doc)
    except edit_mod.EditError:
        return []
    (w_lo, w_hi), (h_lo, h_hi), _limits = layout_mod.form_range(form)
    return [f"раскладка следует за окном: ширина {layout_mod._size_words(w_lo, w_hi)}, высота "
            f"{layout_mod._size_words(h_lo, h_hi)} (frm_json.py layout — подробно)"]


def cmd_layout(args):
    """Раскладка формы при заданных размерах окна: предел с ограничивающей парой, мёртвые правила, элементы,
    которые остаются на месте и держат предел, и таблица координат для каждого `--size`.

    Форма — `form.frm` или документ уровня 1. Код возврата 0: это справочные сведения, а не проверка."""
    doc, form_path = _form_or_doc(args.form)
    if not isinstance(doc, dict):
        raise ValueError("это уровень 0 (сырое дерево): раскладка читается картой, дайте form.frm "
                         "или документ уровня 1")
    # Документ, который `validate` отвергает, раскладка не считает: модель читала бы испорченные данные и
    # печатала догадку. Отказ выдаётся словами, с первым замечанием и отсылкой.
    fatal = [p for p in validate_mod.validate(doc) if p.fatal]
    if fatal:
        raise ValueError(f"документ не проходит проверку (отказов {len(fatal)}, первый — "
                         f"уровень {fatal[0].level}: {fatal[0].text}) — раскладку по нему не "
                         "считаю; все замечания назовёт frm_json.py validate")
    form = layout_mod.read(doc)
    for line in layout_mod.summary(form, detail=args.range):
        print(line)
    if not args.size and (args.order != "wh" or args.at_open or args.shown or args.stale):
        raise ValueError("--order, --shown, --stale и --at-open задают состояние для раскладки при размере: "
                         "без --size ШxВ они ничего не делают — назовите размер")
    state = {"order": args.order, "at_open": bool(args.at_open)}
    if args.shown:
        state["shown"] = _shown_pages(form, args.shown)
        if args.stale:
            state["stale"] = _size_arg("--stale", args.stale)
    elif args.stale:
        raise ValueError("--stale без --shown: размер скрытых страниц называют, когда сказано, какая страница "
                         "показана (--shown РОДИТЕЛЬ=СТРАНИЦА)")
    for size in args.size or ():
        width, height = _size_arg("--size", size)
        for line in layout_mod.table(form, width, height, **state):
            print(line)
    for grow in args.grow or ():
        grow_w, grow_h = _size_arg("--grow", grow)
        for line in drag_mod.window_table(form, grow_w, grow_h):
            print(line)
    if args.drag_by and not args.drag:
        raise ValueError("--drag-by задаёт сдвиги для --drag ИМЯ: без разделителя он ничего не делает")
    for name in args.drag or ():
        for line in drag_mod.table(form, name, tuple(args.drag_by or (50, -50))):
            print(line)
        print("   не проверено платформой: " + " | ".join(drag_mod.QUESTIONS))
    return 0


def _read_form_doc(path):
    """Форма для рендера: `form.frm` или документ уровня 1; для уровня 0 — отказ со словами."""
    doc, path = _form_or_doc(path, _read_json)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: это уровень 0 (сырое дерево): рендер читает документ уровня 1, дайте form.frm "
                         "или документ уровня 1")
    return doc


def _show_change(before, after, out, width=None, height=None, shown=None, marks=(None, None)):
    """Картинка «до | после» в `out` (`.png` через конвертер, иначе SVG) и перечень словами в stdout.

    Если картинки нет (нет конвертера или раскладка отказала), возвращает слова, а не бросает исключение: правка
    к этому времени уже записана, и отказ картинки её не отменяет."""
    try:
        cmp = preview_mod.compare(before, after, width, height, shown, marks)
    except ValueError as why:
        return f"картинки нет: {why}"
    for line in cmp.lines:
        print(line)
    if any(marks):
        print("Разбор кода: безусловное применено на картинке, условное (видимость, доступность, заголовок по условию) нарисовано как в файле; что и при каком условии, названо в заметках")
    for note in cmp.notes:
        print(f"Заметка: {note}", file=sys.stderr)
    try:
        path, why = preview_mod.write_picture(cmp.svg, out)
    except OSError as err:
        return f"картинки нет: {err}"
    if why:
        return why
    print(f"Картинка «до | после»: {path}")
    return None


def cmd_render(args):
    """Каркас формы в SVG или PNG: клиентская область предприятия при заданном размере окна.

    Форма — `form.frm` или документ уровня 1. Незнакомые типы и то, чего рендер не знает (вид закладок с
    неизвестным отступом), выводятся в stderr. SVG пишется в `-o`, без него — в stdout; `-o x.png` создаёт PNG
    первым найденным конвертером (если конвертера нет — отказ со словами, а SVG остаётся рядом). С `--before ДО`
    рисуются две формы рядом с пометками новых, сдвинутых и убранных элементов, а перечень этих же элементов
    словами выводится в stdout. Отказ проверки или раскладки — словами, с кодом 1."""
    _out(args.output, "-o", form=False)
    doc = _read_form_doc(args.form)
    width = height = None
    if args.size:
        width, height = _size_arg("--size", args.size)
    shown = None
    if args.shown:
        form = layout_mod.read(doc)
        shown = _shown_pages(form, args.shown, form_pages_always=True)
    if args.sizes:
        if args.size:
            raise ValueError("--sizes и --size вместе не нужны: --sizes сам называет размеры кадров (715x440,968x561,min,max)")
        result = strip_mod.strip(doc, args.sizes, _read_form_doc(args.before) if args.before else None, shown)
        for line in result.lines:
            print(line)
        for note in result.notes:
            print(f"Заметка: {note}", file=sys.stderr)
        if not args.output:
            sys.stdout.write(result.svg + "\n")
            return 0
        path, why = preview_mod.write_picture(result.svg, args.output)
        if why:
            print(why, file=sys.stderr)
            return 1
        print(f"Полоса кадров: {path}")
        return 0
    if args.before:
        if not args.output:
            raise ValueError("--before без -o: «до | после» — картинка, ей нужен файл (-o cmp.png или cmp.svg)")
        failed = _show_change(_read_form_doc(args.before), doc, args.output, width, height, shown)
        if failed:
            print(failed, file=sys.stderr)
            return 1
        return 0
    marks = None
    state = formstate_mod.read(args.state) if args.state else None
    notes_file = brief_notes_mod.read(args.code_notes) if args.code_notes else None
    if notes_file is not None:
        _doc, form_path = _form_or_doc(args.form, _read_json)          # форма каталогом: модуль лежит рядом с form.frm в каталоге формы
        module = _module_beside(form_path)
        marks = brief_marks_mod.module_marks(doc, form_path, module, notes_file)
        _say_code_marks(marks, module)
    marks, said_size = formstate_mod.apply(doc, state or {}, marks if marks is not None else render_mod.CodeMarks())
    if args.hidden or "hidden" not in (state or {}):
        marks.hatch_hidden = (args.hidden or "hatch") == "hatch"
    if args.conditional or "conditional" not in (state or {}):
        marks.hatch_conditional = (args.conditional or "plain") == "hatch"
    if said_size and not args.size:
        width, height = said_size
    from frm_codec.brief import images as brief_images
    shown_doc, _failed = brief_images.coded_doc(doc, marks)          # заголовки и недоступность формы — в копии документа
    out = render_mod.render(shown_doc, width, height, shown, marks=marks)
    if not args.no_frame:
        out.svg = render_mod.window_frame.framed(out.svg, doc)
    for item in out.unknown:
        print(f"Незнакомый тип, нарисован серым: {item}", file=sys.stderr)
    for note in out.notes:
        print(f"Заметка: {note}", file=sys.stderr)
    if args.output:
        path, why = preview_mod.write_picture(out.svg, args.output)
        if why:
            print(why, file=sys.stderr)
            return 1
    else:
        sys.stdout.write(out.svg + "\n")
    return 0


def _search_config_pictures(args):
    """Рендер ищет общие картинки конфигурации в выгрузке: `--config`, иначе корень выгрузки по пути формы (`frm_codec/configpics.py`). Включается у команд с формой (`form`, `--form`)."""
    form = getattr(args, "form", None)
    config = getattr(args, "config", None)
    configpics.deactivate()
    if isinstance(form, str) or isinstance(config, str):
        configpics.activate(form if isinstance(form, str) else None, config if isinstance(config, str) else None)


def _say_config_pictures():
    """По концу команды: чего не хватило для картинок конфигурации (одна строка «нужны файлы выгрузки: …») и что не рисуется; в stderr."""
    for line in configpics.problem_lines():
        print(f"Заметка: {line}", file=sys.stderr)
    need = configpics.need_line()
    if need:
        print(need, file=sys.stderr)


def _size_arg(flag, size):
    try:
        width, height = (int(v) for v in size.lower().replace("х", "x").split("x"))
    except ValueError:
        raise ValueError(f"{flag} {size!r}: размер пишется ШxВ, например 1050x630") from None
    return width, height


def _shown_pages(form, items, form_pages_always=False):
    """`--shown ИМЯ=СТРАНИЦА` (имя панели или `форма`) → `{ключ панели или формы: страница}`; можно и просто `T2` — закладка из структуры досье, без названия панели.

    Страница — одно из четырёх (`frm_codec/pagerefs.py`): подпись закладки как в обзоре досье, имя страницы в файле, узел `T<N>` структуры, номер с нуля.
    `layout` использует это для раскладки: страницы формы модель скрывает только при закладках «Сверху» (DPI 96,
    без Рамки) и «Не отображать» (`form_pages_always=False`). `render` показывает страницу ≥ 1 формы и там, где
    модель её не скрывает, — скрывает сам (`render._hidden`), поэтому ему страницу формы можно называть всегда
    (`True`). Если панели или страницы не существует, выдаётся отказ."""
    out = {}
    for item in items:
        name, _eq, page = item.rpartition("=")
        if not _eq and pagerefs_mod.NODE.match(item.strip()):          # `--shown T2`: панель называет сам узел
            name, page = None, item
        if (not name and name is not None) or not page.strip():
            raise ValueError(f"--shown {item!r}: пишется ИМЯ=СТРАНИЦА (имя панели или «форма», страница — подпись закладки как в обзоре досье, "
                             "имя страницы, узел T<N> или число с нуля), например Панель1=Облако, Панель1=T3 или просто T3")
        if name is None:
            try:
                key, at = pagerefs_mod.resolve_node(form, page)
            except ValueError as why:
                raise ValueError(f"--shown {item!r}: {why}") from why
            if key in out and out[key] != at:
                raise ValueError(f"--shown {item!r}: для этой панели уже названа другая страница ({out[key]}): страница панели — одна")
            out[key] = at
            continue
        keys = [key for key, holder in form.holders.items()
                if (name == "форма" and key == 0)
                or (holder.item is not None and name in (holder.item.name, holder.item.qualified()))]
        if len(keys) != 1:
            raise ValueError(f"--shown {item!r}: " + (f"панели «{name}» в форме нет" if not keys
                                                      else f"имя «{name}» встречается несколько раз — назовите панель полным именем"))
        holder = form.holders[keys[0]]
        if keys[0] == 0 and form.tabs_area is None and not form.pages_off and not form_pages_always:
            raise ValueError(f"--shown {item!r}: у формы без закладок «Сверху» страницы не скрываются "
                             "(проверялось только при закладках «Сверху», DPI 96, без Рамки)")
        try:
            at = int(page) if page.strip().lstrip("-").isdigit() else pagerefs_mod.resolve(form, keys[0], page, what=f"панели «{name}»" if keys[0] else "формы")
        except ValueError as why:
            raise ValueError(f"--shown {item!r}: {why}") from why
        pages = {c.page for c in holder.children if isinstance(c.page, int)} | {0}
        if at not in pages and at not in pagerefs_mod.pages_of(form, keys[0]):
            raise ValueError(f"--shown {item!r}: у панели «{name}» нет страницы {at} (есть: {', '.join(str(p) for p in sorted(pages))})")
        if keys[0] in out and out[keys[0]] != at:
            raise ValueError(f"--shown {item!r}: для «{name}» уже названа другая страница ({out[keys[0]]}): страница панели — одна")
        out[keys[0]] = at
    return out


def _siblings(form, root, origin=None):
    """Свод соседних форм каталога выгрузки и строка о нём: `(свод, «соседи — …: форм N»)`.

    Соседи — все `*.frm` под каталогом, кроме самой формы; для документа уровня 1 исключается и его форма рядом
    (`form.json` или `form.frm.json` → `form.frm`). Функция общая для `design` и `edit`: во втором случае свод
    определяет вид конфигурации. Сама форма не сосед: исключаются её путь, форма с тем же видом, объектом и именем формы в выгрузке и неправленая
    копия; `origin` — форма выгрузки, копия которой правится (`--origin`)."""
    mine = {form} | ({pathlib.Path(origin)} if origin else set())
    if form.suffix.lower() != ".frm":
        mine |= {form.with_suffix(".frm"), form.with_suffix("")}
    twins = formsource.same_forms(root, mine)
    paths, lost, pool = design_mod.read_siblings(root, mine)
    bare = sum(1 for p in paths if p.name.lower() == "form.bin")
    return pool, (f"соседи — {pathlib.Path(root)}: форм {len(paths)}"
                  + (f", сама форма исключена из соседей ({twins[0]})" if twins else "")
                  + (f" (из них {bare} прочитано из Form.bin без form.frm рядом)" if bare else "")
                  + (f", не прочитано {len(lost)} (первая — {lost[0]})" if lost else ""))


def cmd_diff(args):
    if args.meaning:
        return _diff_meaning(args)
    a, b = _form_node(args.a), _form_node(args.b)
    names = {}
    if args.names:
        for name, (path, _) in find_named(a, "").items():
            names[path] = name
    changes = diff_trees(a, b)
    for change in changes:
        owner = ""
        if args.names:
            # Из вложенных элементов выбирается самый глубокий: кнопка внутри панели лежит и в поддереве панели,
            # и назвать владельцем панель значило бы отправить человека искать правку не в том элементе.
            best = max((p for p in names if change.path[:len(p)] == p), key=len, default=None)
            if best is not None:
                # Адрес внутри элемента печатается только если он не пуст: у изменения самого блока элемента
                # остатка адреса нет.
                tail = path_str(change.path[len(best):])
                owner = f" ({names[best]}{', ' + tail if tail else ''})"
        # Значения печатаются тем же `change_dict`, которым их записывает журнал изменений: `repr` вывел бы
        # `Scalar(kind='INT', text='5')`.
        d = change_dict(change)
        print(f"{d['path']}{owner}: {dumps_line(d['base'])} → {dumps_line(d['exp'])}")
    print(f"Изменений: {len(changes)}")
    return 0


def _diff_meaning(args):
    """Смысловой дифф: сравнение по именам карты без шума платформы (`frm_codec.meaning`).

    Ключ `--names` сюда не передаётся: он называет элемент, в чьём поддереве лежит числовой адрес, а здесь путь
    и так состоит из имён."""
    if args.names:
        raise ValueError("--names и --meaning вместе не работают: у смыслового диффа путь и так "
                         "из имён, и владельца в нём видно без ключа")
    changes = meaning.changes(meaning.canon(typed.decode(_form_node(args.a))),
                              meaning.canon(typed.decode(_form_node(args.b))))
    for path, left, right in changes:
        print(f"{'/'.join(str(part) for part in path)}: "
              f"{meaning.show(left)} → {meaning.show(right)}")
    print(f"Смысловых изменений: {len(changes)}")
    return 0


def cmd_stat(args):
    paths = [p for root in args.dirs for p in sorted(pathlib.Path(root).rglob("form.frm"))]
    if not paths:
        raise ValueError("в названных каталогах нет ни одного form.frm")
    stats = stat.collect(paths)
    if args.out:
        pathlib.Path(args.out).write_text(stat.dump_json(stats), encoding="utf-8")
    if args.md:
        pathlib.Path(args.md).write_text(stat.to_markdown(stats), encoding="utf-8")
    if args.commit_summary:
        # Сводка и заявка в git — вход для разделов «Открытые позиции» и «Типы вне карты» в FORMAT.md. Они
        # записываются одним ключом: обновлять одну без другой нельзя, иначе документ сошлётся на корпус,
        # которого уже нет. Ключ отдельный от рабочего прогона, чтобы сгенерированные файлы не менялись
        # мимоходом.
        common = stat.common_guids(paths, census.config_of)
        stat.SUMMARY_PATH.write_text(stat.dump_summary(stats, common=common), encoding="utf-8")
        stat.UNKNOWN_PATH.write_text(stat.dump_unknown(stats), encoding="utf-8")
        print(f"Сводка перезаписана: {stat.SUMMARY_PATH}, {stat.UNKNOWN_PATH} — "
              "перегенерируйте FORMAT.md")
    kinds = {k for k, _ in stats}
    print(f"Форм: {len(paths)}, узлов: {len(kinds)}, позиций: {len(stats)}")
    return 0


def cmd_schema(args):
    try:
        from frm_codec import docs
    except ImportError:
        raise ValueError("команда schema пересобирает FORMAT.md, схему и приложения к карте и работает только в "
                         "репозитории навыка; в установленной копии навыка они лежат готовыми: FORMAT.md и "
                         "schema/frm.schema.json") from None
    targets = [pathlib.Path(args.md) if args.md else SKILL / "FORMAT.md",
               pathlib.Path(args.open) if args.open else SKILL / docs.OPEN_FILE,
               pathlib.Path(args.json) if args.json else SKILL / "schema" / "frm.schema.json",
               pathlib.Path(args.sources) if args.sources else SKILL / docs.SOURCES_FILE]
    # Записывает по-прежнему `docs.write`, а CLI только раскладывает результат по названным путям: собственная
    # запись тех же файлов была бы вторым правилом печати (отступ, перевод строки, `ensure_ascii`).
    with tempfile.TemporaryDirectory() as tmp:
        written = docs.write(pathlib.Path(tmp))
        for src, dst in zip(written, targets):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    print(f"Записано: {', '.join(str(t) for t in targets)}; узлов в карте {len(schema.MAP)}")
    return 0


def cmd_patterns(args):
    """Нормы компоновки из переписи снимка корпуса форм. Без снимка команда отказывает: нормы, снятые на
    живом зеркале, менялись бы вместе с ним, а `patterns.json` должен совпадать с пересборкой."""
    if not (SKILL / "tests" / "corpus.py").exists():
        raise ValueError("команда patterns пересчитывает нормы и работает только в репозитории навыка, где есть снимок "
                         "корпуса форм; в установленной копии навыка нужны готовые нормы — они лежат в "
                         "frm_codec/data/patterns.json")
    sys.path.insert(0, str(SKILL / "tests"))
    import corpus
    try:
        root, why = corpus.snapshot()
    except corpus.SnapshotChanged as exc:
        raise ValueError(f"снимок корпуса не годится — {exc}") from None
    if root is None:
        raise ValueError(f"нормы пишутся только со снимка корпуса форм: {why}")
    problems = corpus.check_snapshot(root)
    if problems:
        raise ValueError("снимок изменился: " + "; ".join(problems))
    if corpus.sample_step() > 1:
        raise ValueError("FRM_SAMPLE задан: нормы по части снимка не пишутся и не сверяются — снимите переменную")
    recs = corpus.pmap(census.record_path, corpus.forms())
    table = patterns_mod.aggregate(recs, stamp=patterns_mod.STAMP)
    target = pathlib.Path(args.out) if args.out else patterns_mod.PATTERNS_PATH
    if args.check:
        if not target.exists():
            print(f"patterns.json нет: {target}", file=sys.stderr)
            return 1
        have = patterns_mod.load(target)
        if have != table:
            print(f"patterns.json разошёлся с переписью снимка (первое различие — "
                  f"{patterns_mod.first_difference(have, table)}): "
                  "python3 frm_json.py patterns — пересобрать и закоммитить", file=sys.stderr)
            return 1
        print(f"patterns.json совпадает с переписью: форм {len(recs)}")
        return 0
    patterns_mod.write(table, target)
    print(f"Записано: {target}; форм {len(recs)}, видов {len(table['kinds'])}, "
          f"исключено {sum(table['excluded'].values())}")
    return 0


def _config_of(args):
    """`Config` по ключам `--config` (выгрузка конфигурации) и `--root-xml` (корневой XML внешней обработки или отчёта): любой из них, оба вместе
    или `None`. Внешний объект и одноимённый объект выгрузки вместе — отказ (`metadata.load_for`)."""
    try:
        return metadata_mod.load_for(getattr(args, "config", None), getattr(args, "root_xml", None))
    except metadata_mod.MetadataError as e:
        raise ValueError(f"{'метаданные' if getattr(args, 'root_xml', None) else 'выгрузка конфигурации'}: {e}") from None


def cmd_generate(args):
    """Форма по описанию из блоков-паттернов (`frm_codec.generate`): исходная форма + выгрузка + нормы → форма и
    отметка.

    Порядок такой же, как у `edit`: вся работа и проверка выполняются до записи, а форма и отметка записываются
    парой. Отметку перегенерации команда кладёт рядом с описанием; форму, которую правили после прошлой
    генерации, без `--overwrite` она не перезаписывает.

    Без `--form` исходной формой служит заготовка навыка того же вида (`frm_codec.blank`, команда `new`)."""
    _out(args.out, "-o")
    desc = _read_json(args.description)
    ref, scratch = None, None
    from_blank = not args.form
    blank_keys = [k for k, given in (("--type-id", args.type_id), ("--dialog", args.dialog)) if given]
    if blank_keys and not from_blank:
        raise ValueError(f"{', '.join(blank_keys)} — ключ{'и' if len(blank_keys) > 1 else ''} заготовки, а исходная форма названа (--form): "
                         "заготовка не берётся, тип основного реквизита — у исходной формы")
    if from_blank:
        made = generate_mod.blank_for_description(desc, config_dir=args.config, type_id=args.type_id, root_xml=args.root_xml, dialog=args.dialog)
        scratch = tempfile.TemporaryDirectory()
        pathlib.Path(scratch.name, "form.frm").write_bytes(made.frm_bytes())
        args.form = str(pathlib.Path(scratch.name, "form.frm"))
        args.blank_module = made.module
        print(f"Исходная форма не названа: взята заготовка навыка — {made.source}")
        for note in made.notes:
            if note.startswith(("основной реквизит формы", "форма-диалог")):       # размер и заголовок заготовки — не итог: их берёт описание
                print(note)
    elif formsource.is_form_ref(args.form):
        notes = []
        data, ref = formsource.source_for_write(args.form, notes)
        _notes(notes, sys.stdout)
        if ref.frm.is_file():
            args.form = str(ref.frm)
        else:
            # Исходная форма читается из контейнера в памяти; генератору нужен файл, он кладётся во временный каталог.
            scratch = tempfile.TemporaryDirectory()
            pathlib.Path(scratch.name, "form.frm").write_bytes(data)
            args.form = str(pathlib.Path(scratch.name, "form.frm"))
    try:
        return _generate(args, desc, ref, from_blank, _config_of(args) if args.root_xml else None)
    finally:
        if scratch is not None:
            scratch.cleanup()


def _generate(args, desc, ref, from_blank=False, config=None):
    shell = None
    if args.render:
        try:
            shell = _read_form_doc(args.form)  # до записи: файл -o может лежать поверх --form
        except (ValueError, OSError):
            shell = None
    if from_blank:
        pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)       # как у `new`: каталог формы новой формы может не существовать
    was = formsource.exists_before([args.out])
    report = generate_mod.apply(desc, args.form, args.config, args.out, overwrite=args.overwrite,
                                desc_path=args.description, siblings=args.siblings, relayout=args.relayout, from_blank=from_blank, config=config)
    module_line = None
    if from_blank and not report.unchanged:        # как у `new`: пустой form.bsl рядом с -o, существующий не трогается (платформа пишет пустой модуль BOM-ом)
        module = pathlib.Path(args.out).with_name("form.bsl")
        if module.exists():
            module_line = f"Модуль {module} уже есть и не тронут"
        else:
            module.write_bytes(args.blank_module)
            module_line = f"Записано: {module} ({len(args.blank_module)} байт) — пустой модуль формы, как у new"
    if report.unchanged:
        print(f"Ничего не изменилось: {report.out_path} не тронут (описание то же, файл равен записанному прошлой генерацией)")
        for line in report.log:
            print(line)
        return 0
    if report.mode:
        print(report.mode)
    for line in report.log:
        print(line)
    for line in report.notes:
        print(f"Решено движком: {line}")
    for line in report.warnings:
        print(f"Предупреждение: {line}")
    shown = ", ".join(f"{kind} {count}" for kind, count in sorted(report.elements.items()))
    print(f"Сгенерировано: операций {report.ops}; элементов верхнего уровня и вложенных по видам: {shown}")
    print(f"Записано: {report.out_path} ({report.size} байт), проверка обратным разбором уровня 1 пройдена"
          + (f"; отметка: {report.stamp_path}" if report.stamp_path else ""))
    if module_line:
        print(module_line)
    _finish([report.out_path], was, ref)
    if args.render:
        made = _read_form_doc(report.out_path)
        failed = _show_change(shell, made, args.render) if shell is not None else _show_plain(made, args.render)
        if failed:
            print(f"Форма записана; {failed}")
    return 0


def cmd_new(args):
    """Форма с нуля (`frm_codec.blank`): пустая заготовка формы, как её создаёт конструктор, и пустой `form.bsl` рядом.

    Новых форм в метаданных команда не заводит: форму объекту создают в конфигураторе либо берут существующую, а навык пишет её содержимое.
    Заготовка записывается парой с модулем; существующий файл `-o` без `--overwrite` не затирается, существующий `form.bsl` не трогается."""
    _out(args.out, "-o")
    config = None
    if args.config:
        try:
            config = metadata_mod.load(args.config)
        except metadata_mod.MetadataError as e:
            raise ValueError(f"выгрузка конфигурации: {e}") from None
    if args.object and not args.config:
        raise ValueError("--object называет объект выгрузки и нужен вместе с --config (каталог выгрузки конфигурации); "
                         "внешняя обработка и внешний отчёт берут тип основного реквизита из --root-xml или --type-id")
    size = blank_mod.parse_size(args.size) if args.size else None
    made = blank_mod.build(args.kind, object_name=args.object, config=config, title=args.title, size=size, type_id=args.type_id,
                           root_xml=args.root_xml, dialog=args.dialog)
    out = pathlib.Path(args.out)
    if out.exists() and not args.overwrite:
        raise ValueError(f"{out} уже есть: новая форма его не затирает (--overwrite — затереть осознанно; готовую форму правят командой edit)")
    module = pathlib.Path(args.bsl_out) if args.bsl_out else out.with_name("form.bsl")
    was = formsource.exists_before([args.out])
    data = made.frm_bytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    pairs = [(args.out, data)]
    keep_module = module.exists()
    if not keep_module:
        pairs.append((str(module), made.module))
    print(f"Заготовка: {made.source}")
    for line in made.notes:
        print(line)
    for path, size_bytes in _write_all(pairs):
        print(f"Записано: {path} ({size_bytes} байт)" + (", проверка обратным разбором уровня 1 пройдена" if path == args.out else ""))
    if keep_module:
        print(f"Модуль {module} уже есть и не тронут")
    _finish([args.out], was)
    return 0


def cmd_add_field(args):
    """Вывод реквизитов шапки на форму одним вызовом (`frm_codec.addfield`): `describe` → поля в описание → бережный `generate`.

    Режим движка (полная раскладка) не включается никогда: форма меняется только разницей, а отказ бережного режима —
    отказ команды без записи. `--dry-run` печатает отчёт и рисунок, форму не пишет."""
    if not args.dry_run and not args.out:
        raise ValueError("-o нужен: куда записать форму (чтобы только посмотреть результат, дайте --dry-run)")
    if args.out:
        _out(args.out, "-o")
    if not formsource.is_form_ref(args.form):
        raise ValueError(f"{args.form}: add-field читает форму — form.frm, Form.bin или каталог формы")
    notes = []
    data, ref = formsource.source_for_write(args.form, notes)
    _notes(notes, sys.stdout)
    with tempfile.TemporaryDirectory() as tmp:
        form_path = str(ref.frm) if ref.frm.is_file() else str(pathlib.Path(tmp, "form.frm"))
        if not ref.frm.is_file():
            pathlib.Path(form_path).write_bytes(data)
        if not args.config and not args.root_xml:
            raise ValueError("add-field берёт реквизиты объекта из метаданных: дайте --config (каталог выгрузки конфигурации) или --root-xml (корневой XML внешней обработки)")
        config = _config_of(args)
        kind, object_name = describe_mod.hints_from_path(ref.frm.resolve())
        out = pathlib.Path(tmp, "dry.frm") if args.dry_run else pathlib.Path(args.out)
        if not args.dry_run and out.exists() and not args.overwrite and out.read_bytes() != pathlib.Path(form_path).read_bytes():
            raise ValueError(f"{out} уже существует и не равен исходной форме: add-field не затирает чужой файл. Назовите другой -o, "
                             "исходную форму (правка на месте) либо дайте --overwrite")
        before = _read_form_doc(form_path) if args.render else None
        was = formsource.exists_before([out])
        outcome = addfield_mod.run(form_path, config, args.config, args.attr, args.after, out, tmp, siblings=args.siblings,
                                   kind=kind, object_name=object_name)
        for name, elements in outcome.present:
            print(f"уже на форме: {name}" + (f" (элементы: {', '.join(elements)})" if elements else " (назван в блоках полей формы)"))
        for name, elements in outcome.hidden:
            print(f"уже на форме, но скрыт: {name} (элементы {', '.join(elements)}: видимость выключена); вставка не нужна. Редактор видимость не правит: "
                  "включите её в конфигураторе либо в JSON формы (`decode`) поставьте у элемента `coords.visible` = true и соберите форму (`encode`)")
        if not outcome.steps:
            print("Форма не изменена: все названные реквизиты уже на форме")
            return 0
        for number, step in enumerate(outcome.steps):
            print(f"{step.name}: место — {step.place}"
                  + (f"; проверено мест {step.tried}, отвергнуто {len(step.rejected)}" if step.rejected else ""))
            for line in addfield_mod.reason_lines(step.rejected):
                print(f"  отвергнуто:{line}")
            if number == 0:
                print(step.report.mode)
            for line in step.report.log[1:]:
                print(line)
            for line in step.report.notes:
                print(f"Решено движком: {line}")
            for line in step.report.warnings:
                print(f"Предупреждение: {line}")
        added = ", ".join(step.name for step in outcome.steps)
        ops = sum(step.report.ops for step in outcome.steps)
        if args.dry_run:
            print(f"Пробный прогон: выведено бы {added}; форма не записана (операций {ops}, проверка обратным разбором и проверка правки пройдены)")
        else:
            report = outcome.steps[-1].report
            print(f"Выведено: {added}; операций {ops}")
            print(f"Записано: {report.out_path} ({report.size} байт), проверка обратным разбором уровня 1 и проверка правки пройдены")
            _finish([out], was, ref)
        if args.render:
            result = strip_mod.strip(_read_form_doc(str(out)), ADD_FIELD_SIZES, before)
            for line in result.lines:
                print(line)
            for note in result.notes:
                print(f"Заметка: {note}", file=sys.stderr)
            path, why = preview_mod.write_picture(result.svg, args.render)
            print(f"Картинка «до | после»: {path}" if not why else f"{why}" + ("" if args.dry_run else "; форма записана"))
    return 0


ADD_FIELD_SIZES = "715x440,968x561,min,max"


def _show_plain(doc, out):
    """Без исходной формы сравнивать не с чем: просто рендер результата в `out` (при отказе — слова, как у
    `_show_change`)."""
    try:
        rendered = render_mod.render(doc)
        _path, why = preview_mod.write_picture(rendered.svg, out)
    except (ValueError, OSError) as err:
        return f"картинки нет: {err}"
    return why or None


def cmd_describe(args):
    """Описание формы по самой форме (`frm_codec.describe`): образец → блоки словаря `generate`.

    Описание записывается в `-o` или выводится в stdout (это данные); пояснения для человека идут в stderr,
    чтобы не попасть в конвейер: что решено по именам и ролям, что пропущено (блоки с типами) и чего в форме не
    нашлось."""
    _out(args.out, "-o", form=False)
    doc, form = _form_or_doc(args.form)
    config = _config_of(args)
    kind, object_name = describe_mod.hints_from_path(form.resolve())
    kind, object_name = args.kind or kind, args.object or object_name
    result = describe_mod.describe(doc, config, form_use=args.form_use, kind=kind, object_name=object_name)
    text = json.dumps(result.description, ensure_ascii=False, indent=2)
    _write(args.out, text)
    for line in result.notes:
        print(f"Решено: {line}", file=sys.stderr)
    blocks = ", ".join(f"{k[7:]} {v}" for k, v in sorted(result.counts.items()) if k.startswith("blocks:")) or "нет"
    skipped = ", ".join(f"{k[8:]} {v}" for k, v in sorted(result.counts.items()) if k.startswith("skipped:")) or "ничего"
    print(f"Описание: блоков по видам — {blocks}; полей {result.counts['fields']}, колонок {result.counts['columns']}; "
          f"пропущено ({sum(v for k, v in result.counts.items() if k.startswith('skipped:'))}) — {skipped}"
          + (f"; записано: {args.out}" if args.out else ""), file=sys.stderr)
    return 0


def cmd_fragment(args):
    """Описание формы обработки по скелету вида (`generate.fragment`): заготовка в `-o` или в stdout."""
    _out(args.out, "-o", form=False)
    fields = []
    for text in args.field:
        name, _colon, source = text.partition(":")
        if source not in ("", "form"):
            raise ValueError(f"--field {text!r}: после двоеточия — только «form» (реквизит формы), а пришло {source!r}")
        fields.append({"data": name, "source": "form"} if source else name)
    desc = generate_mod.fragment(args.name, args.object, fields, title=args.title, columns=args.columns, sheet=args.sheet, bar=args.bar)
    _write(args.out, json.dumps(desc, ensure_ascii=False, indent=2))
    return 0


def cmd_unpack(args):
    lines, code = formsource.unpack_command(args.path, args.all, args.force)
    for line in lines:
        print(line)
    return code


def cmd_pack(args):
    if args.create and args.all:
        raise ValueError("--create делает контейнер одной форме и с --all не сочетается: назовите форму")
    lines, code = (formsource.create_command(args.path, args.force) if args.create
                   else formsource.pack_command(args.path, args.all, args.force))
    for line in lines:
        print(line)
    return code


def cmd_selftest(args):
    """Самопроверка навыка на этой машине (`frm_codec.selftest`): заготовки, правка, рендер, контейнер, файлы; код 1, если отказала хоть одна."""
    from frm_codec import selftest
    lines, failed = selftest.run()
    for line in lines:
        print(line)
    return 1 if failed else 0


def cmd_epf_copyinfo(args):
    from frm_codec.epf import command as epf_command
    lines, code, _ = epf_command.run(args.path, args.out, args.dry_run)
    for line in lines:
        print(line, file=sys.stderr if code else sys.stdout)
    return code


def cmd_propose(args):
    if not (SKILL / "lab" / "propose.py").exists():
        # Без этой проверки в установленной копии возникла бы трассировка ModuleNotFoundError, а не сообщение.
        # Так же отказывает patterns.
        raise ValueError("команда propose доступна только в репозитории навыка: в установленной копии нет журнала "
                         "изменений и матриц свойств, по которым строятся предложения к карте")
    sys.path.insert(0, str(SKILL / "lab"))
    import propose, tickets
    matrix_dir = pathlib.Path(args.matrix_dir) if args.matrix_dir else SKILL / "lab" / "matrix"
    ledger = pathlib.Path(args.ledger) if args.ledger else SKILL / "lab" / "ledger.jsonl"
    # Отсутствующий журнал — отказ именно здесь, а не в `tickets.load_ledger`: для предложений журнал —
    # единственный вход, и результат «полей 0, конфликтов 0» читался бы как «в журнале нового нет».
    if not ledger.exists():
        raise ValueError(f"журнала нет: {ledger} — предлагать нечего; журнал пишет lab.py check")
    if not matrix_dir.is_dir():
        # Без матриц вид свойства неизвестен ни у одного поля, и предложение превращается в список «назовите вид
        # вручную».
        raise ValueError(f"каталога матриц нет: {matrix_dir} — матрицы пишет lab.py matrix")
    rows = tickets.load_ledger(ledger)
    p = propose.proposals(rows, propose.load_kinds(matrix_dir),
                          propose.load_enum_values(matrix_dir))
    print(propose.render_fragments(p))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(propose.to_json(p), ensure_ascii=False,
                                                     indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="frm_json.py", description="Кодек обычных форм 1С 8.x")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("decode", help="form.frm → JSON (уровень 1, при --raw — уровень 0)")
    p.add_argument("form", help="form.frm, Form.bin или каталог формы (Ext, Forms/<Имя>)")
    p.add_argument("-o", "--out"); p.add_argument("--raw", action="store_true")
    p = sub.add_parser(
        "encode", help="JSON → form.frm с проверкой и проверкой обратным разбором",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="JSON → form.frm с проверкой и проверкой обратным разбором.\n\n"
                    "ВАЖНО: этот JSON нельзя читать и писать стандартными средствами JSON\n"
                    "(`json` в Python, `jq`). Дробное число записано в нём без кавычек\n"
                    "(`1e2`), как в файле формы. Стандартный разборщик читает его как float и\n"
                    "пишет обратно `100.0`: значение то же, но знаки другие, и в собранной\n"
                    "форме появятся посторонние отличия. Дробные значения есть у большинства\n"
                    "форм, и почти все они равны `1e2`.\n"
                    "Читайте и пишите этот JSON функциями `frm_codec.json0.loads` и `dumps`.\n"
                    "Правка в текстовом редакторе безопасна: она знаков не трогает.")
    p.add_argument("json"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--all-warnings", action="store_true", help="предупреждения о длине блока поштучно (без ключа больше трёх — одной строкой сводки)")
    p = sub.add_parser("validate", help="три уровня проверки: документ JSON либо форма (form.frm, Form.bin, каталог формы)")
    p.add_argument("json", help="документ уровня 1 (.json), form.frm, Form.bin или каталог формы")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/ в XML): ещё сверка типа таблиц на "
                                    "табличных частях с TypeId части")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): то же для "
                                                      "табличных частей внешнего объекта")
    p.add_argument("--all-warnings", action="store_true", help="предупреждения о длине блока поштучно (без ключа больше трёх — одной строкой сводки)")
    p = sub.add_parser(
        "edit", help="правка формы перечнем операций (frm_codec.edit)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Правка формы перечнем операций.\n\n"
                    "Перечень — массив JSON, имя операции в поле \"op\", остальные ключи\n"
                    "её параметры:\n\n"
                    "  [{\"op\": \"set_form_title\", \"text\": \"Заголовок\"},\n"
                    "   {\"op\": \"add_element\", \"template\": \"Label\", \"name\": \"Надпись1\",\n"
                    "    \"box\": [32, 300, 220, 19], \"caption\": \"Текст\"}]\n\n"
                    "Операции сами пересчитывают индексы и номера элементов, счётчики списков,\n"
                    "номер на странице, порядок обхода и встречные записи привязок. После операций\n"
                    "форма проверяется, в том числе обратным разбором (собранный файл\n"
                    "разбирается снова и сравнивается с исходным), и записывается.\n\n"
                    "Операции: " + ", ".join(sorted(edit_mod.FORM_OPS)
                                             + sorted(edit_mod.MODULE_OPS) + sorted(edit_mod.COMBINED_OPS)) + "\n\n"
                    "ЧЕРНОВИКИ (платформа их не проверяла, по умолчанию они отказывают;\n"
                    "отказ снимает ключ \"unverified\": true в самой операции): "
                    + (", ".join(sorted(edit_mod.DRAFTS)) or "нет") + ".\n\n"
                    + textwrap.fill(
                        "ПРОВЕРЕНЫ ПЛАТФОРМОЙ В СВОИХ СЛУЧАЯХ (в этих случаях ключ не нужен; в прочих "
                        "случаях операция отказывает, и отказ снимает \"unverified\": true): "
                        + "; ".join(f"{op} — {words}" for op, words
                                    in sorted(edit_mod.PARTLY_CHECKED.items())) + ".", 70)
                    + "\n\n"
                    + textwrap.fill(
                        "Платформа проверяла вариант, а не операцию целиком. Если вызов шире "
                        "проверенного, операция его выполняет и пишет в отчёте пометку «"
                        + edit_mod.ON_CORPUS_NOTE + "»; варианты: "
                        + ", ".join(sorted(edit_mod.ON_CORPUS)) + ".", 70) + "\n\n"
                    + textwrap.fill(edit_mod.UNVERIFIED_KEPT + ".", 70))
    p.add_argument("form", help="form.frm, Form.bin или каталог формы (Ext, Forms/<Имя>); исходная форма читается в памяти")
    p.add_argument("--ops", required=True)
    p.add_argument("-o", "--out", required=True,
                   help="куда записать форму. Чтобы собрать Form.bin, назовите form.frm рядом с ним (…/Ext/form.frm); "
                        "иной путь Form.bin не меняет; сам Form.bin и каталог отвергаются")
    p.add_argument("--bsl", help="модуль формы (байты: BOM и перевод строк сохраняются)")
    p.add_argument("--all-warnings", action="store_true", help="предупреждения о длине блока поштучно (без ключа больше трёх — одной строкой сводки)")
    p.add_argument("--bsl-out", help="куда положить правленый модуль (form.bsl рядом с Form.bin; сам Form.bin отвергается)")
    p.add_argument("--siblings", help="каталог выгрузки той же конфигурации или обработки: вид "
                                      "конфигурации для add_element и set_view")
    p.add_argument("--origin", help="форма выгрузки (form.frm), копия которой проверяется или правится: она не сосед. Без ключа исключаются форма с тем же "
                                    "видом, объектом и именем формы в выгрузке и неправленая копия")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/ в формате "
                                    "XML): объекты, реквизиты и табличные части для bind с путём "
                                    "\"Объект.Реквизит\" и для set_saved_values с реквизитом обработки")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): реквизиты и табличные части объекта формы "
                                                      "для путей по метаданным; рядом можно дать --config (ссылочные типы реквизитов). Объект с тем же именем в выгрузке — отказ")
    p.add_argument("--render", metavar="CMP", help="после записи — картинка «до | после» (CMP.png или CMP.svg) и перечень "
                                                   "новых, сдвинутых и убранных элементов в stdout; если конвертер отказал, "
                                                   "правка остаётся записанной")
    p.add_argument("--code-notes", metavar="FILE", help="записи разбора кода (code-notes.json, docs/brief-code.md): рисунок --render получает то же состояние формы по коду, что досье; "
                                                        "без ключа кода на рисунке нет")
    p = sub.add_parser(
        "generate", help="форма по описанию из блоков-паттернов (frm_codec.generate): исходная форма + выгрузка + нормы",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Форма элемента справочника или документа либо формы обработки (kind processing) по описанию\n"
                    "(docs/generate.md): блоки command_bar, fields, group, tabs, table, spreadsheet (обработка) и\n"
                    "доводка tune, без координат; новые реквизиты формы обработки — ключ attributes.\n"
                    "Исходная форма --form — существующая форма того же объекта (её основной\n"
                    "реквизит — объект выгрузки); её содержимое переписывается. Без --form форма строится\n"
                    "с нуля на заготовке навыка того же вида (команда new, docs/from-scratch.md). Отметка\n"
                    "перегенерации лежит рядом с описанием (<описание>.stamp.json). Если файл -o\n"
                    "правили после прошлой генерации или он не назван в отметке, команда не\n"
                    "затирает его без --overwrite. Если описание не изменилось и файл -o равен\n"
                    "записанному, команда сообщает «ничего не изменилось» и файл не трогает.")
    p.add_argument("description", help="описание формы (JSON, schema/describe.schema.json)")
    p.add_argument("--form", help="исходная форма: form.frm, Form.bin или каталог формы. Без ключа — заготовка навыка того же вида, "
                                  "что команда new (форма с нуля; docs/from-scratch.md); у справочника и документа тогда нужен --config")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/ в XML); обязателен у "
                                    "справочника и документа; у вида processing без него поля — только реквизиты формы; отчёт конфигурации — каталог Reports/")
    p.add_argument("-o", "--out", required=True, help="куда положить форму; …/Ext/form.frm рядом с Form.bin — и Form.bin соберётся; "
                   "сам Form.bin и каталог отвергаются")
    p.add_argument("--type-id", help="без --form, вид processing: GUID типа Object обработки или отчёта (по имени в object) — тип основного реквизита заготовки (как у new)")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или отчёта (<Имя>.xml): поля и таблицы привязываются к реквизитам и табличным частям "
                                                      "объекта; без --form — ещё и тип основного реквизита заготовки (как у new: обработка или отчёт по корню)")
    p.add_argument("--dialog", action="store_true", help="без --form, вид processing: заготовка-диалог без основного реквизита (как у new; у отчёта — отказ)")
    p.add_argument("--overwrite", action="store_true",
                   help="затереть файл -o, который правили вручную после прошлой генерации или который не назван в отметке; "
                        "также перегенерировать описание, которое не изменилось")
    p.add_argument("--relayout", action="store_true",
                   help="полная раскладка: форма перекладывается целиком по нормам вида. Без ключа исходная форма, которая не проходит "
                        "проверку обратным разбором describe → generate (форма, правленная человеком), правится бережно: "
                        "меняется только разница описаний, остальное не сдвигается; то, что выразить нельзя, — отказ")
    p.add_argument("--siblings", help="каталог выгрузки той же конфигурации: высота поля и надписи — самое частое значение у её форм "
                                      "(все *.frm под ним, кроме --form и -o); без него — норма вида")
    p.add_argument("--render", metavar="CMP", help="после записи — картинка «до | после» (исходная форма --form | результат; "
                                                   "CMP.png или CMP.svg) и перечень в stdout; если конвертер отказал, "
                                                   "форма остаётся записанной")
    p = sub.add_parser(
        "new", help="форма с нуля: пустая заготовка формы, как её создаёт конструктор (frm_codec.blank), и пустой form.bsl рядом",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Пустая форма обычного приложения (docs/from-scratch.md). Виды: " + ", ".join(blank_mod.KINDS) + ".\n"
                    "processing — форма обработки с основным реквизитом ОбработкаОбъект; его тип один из: --root-xml <Имя>.xml (корневой XML\n"
                    "выгрузки внешней обработки), --type-id GUID (TypeId её GeneratedType category=Object), --object Обработка.Имя --config\n"
                    "(обработка выгрузки конфигурации). Без источника типа — отказ; --dialog — форма-диалог без основного реквизита и\n"
                    "реквизитов формы (модуль формы не видит реквизитов и экспортных методов модуля обработки).\n"
                    "report — форма внешнего отчёта или отчёта конфигурации с основным реквизитом ОтчетОбъект (нижняя панель с кнопкой\n"
                    "«Закрыть», «Сформировать» не ставится); тип: --root-xml (внешний отчёт), --type-id или --object Отчет.Имя --config;\n"
                    "без источника типа и с --dialog — отказ.\n"
                    "catalog.item, document.item, catalog.list, document.list — с --config и --object: основной реквизит несёт тип объекта\n"
                    "(Object у элемента, List у списка). В заготовке панели формы как у конструктора и нет кнопок с обработчиками; у списка —\n"
                    "табличное поле со стандартными колонками. Новых форм в МЕТАДАННЫХ команда не заводит: форму объекту сначала создают в\n"
                    "конфигураторе (или берут существующую), навык пишет её содержимое. Дальше — generate (форма по описанию) и edit.")
    p.add_argument("kind", choices=blank_mod.KINDS, help="вид формы")
    p.add_argument("-o", "--out", required=True, help="куда положить форму (form.frm); …/Ext/form.frm рядом с Form.bin — и Form.bin соберётся; "
                   "сам Form.bin и каталог отвергаются; существующий файл без --overwrite не затирается")
    p.add_argument("--title", help="заголовок формы; без него — по синониму объекта, как у конструктора, а без объекта «Форма»")
    p.add_argument("--size", metavar="ШxВ", help=f"размер формы в пикселях (умолчание {blank_mod.DEFAULT_SIZE[0]}x{blank_mod.DEFAULT_SIZE[1]}); панели встают по краям")
    p.add_argument("--object", help="полное имя объекта выгрузки: «Справочник.Имя», «Документ.Имя», у processing «Обработка.Имя», у report «Отчет.Имя»; нужен вместе с --config")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/, Reports/ в XML): по нему берётся тип основного реквизита")
    p.add_argument("--type-id", help="GUID типа основного реквизита, заданный явно, когда выгрузки нет, а тип известен (Object обработки, справочника, документа; List списка); вместе с --object не берётся")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="processing, report: корневой XML выгрузки внешней обработки (<Имя>.xml, ExternalDataProcessor) или внешнего отчёта (ExternalReport): тип основного "
                   "реквизита — его GeneratedType category=Object, заголовок — по синониму; вид формы по корню (processing — обработка, report — отчёт); вместе с --type-id, "
                   "--object, --config, --dialog не берётся")
    p.add_argument("--dialog", action="store_true", help="processing: форма-диалог без основного реквизита и реквизитов формы; модуль формы не видит "
                   "реквизитов и экспортных методов модуля обработки; вместе с источником типа не берётся; у report — отказ")
    p.add_argument("--bsl-out", help="куда положить пустой модуль (умолчание form.bsl рядом с -o; существующий не трогается)")
    p.add_argument("--overwrite", action="store_true", help="затереть существующий файл -o")
    p = sub.add_parser(
        "add-field", help="вывести реквизиты шапки на форму одним вызовом: describe → поле в описание → бережный generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Реквизиты шапки объекта формы (в том числе стандартные: Код, Наименование, Дата, Номер) выводятся на готовую\n"
                    "форму парой «надпись + поле» по правилам бережного режима generate (docs/generate.md). Реквизит, который\n"
                    "уже на форме (полем или надписью с данными), пропускается строкой «уже на форме». Реквизит табличной части и\n"
                    "реквизит формы не выводятся. Режим движка (полная раскладка) не включается: если бережный режим отказывает,\n"
                    "команда отказывает его словами без записи; выход — generate --relayout или edit.")
    p.add_argument("form", help="форма: form.frm, Form.bin или каталог формы")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/ в XML); нужен он или --root-xml")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): реквизиты и табличные части объекта формы "
                                                      "для путей по метаданным; рядом можно дать --config (ссылочные типы реквизитов). Объект с тем же именем в выгрузке — отказ")
    p.add_argument("--attr", action="append", required=True, metavar="ИМЯ",
                   help="реквизит шапки (можно несколько раз; порядок — порядок вывода)")
    p.add_argument("--after", metavar="ПОЛЕ", help="поставить после этого поля, в его блоке (пробуется только это место, подвал под таблицей допустим); "
                                                   "без ключа места перебираются: концы блоков полей шапки, затем места после каждого поля самого большого блока")
    p.add_argument("--overwrite", action="store_true", help="затереть существующий файл -o, который не равен исходной форме")
    p.add_argument("-o", "--out", help="куда записать форму; …/Ext/form.frm рядом с Form.bin — и Form.bin соберётся; "
                                       "сам Form.bin и каталог отвергаются. Обязателен без --dry-run")
    p.add_argument("--render", metavar="CMP", help="картинка «до | после» с полосой размеров (CMP.png или CMP.svg) и перечень в stdout")
    p.add_argument("--dry-run", action="store_true", help="только отчёт и рисунок, форма не записывается")
    p.add_argument("--siblings", help="каталог выгрузки той же конфигурации: высота поля и надписи — самое частое значение у её форм")
    p = sub.add_parser(
        "brief", help="досье формы для модели: короткий обзор (что за форма, состав, код, проблемы, особенное для правки, как исследовать дальше), подробности по --detail, три картинки",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Досье одной формы для разбора моделью (docs/brief.md): brief.md и brief.json, clean.png (форма как её видит пользователь),\n"
                    "marked.png (номера узлов структуры, порядок обхода, рамки областей) и behavior.png (кадры при разных размерах окна).\n"
                    "Обзор brief.md короткий; подробности разделов (--detail) пишутся в brief-full.md, полные данные — в brief.json.\n"
                    "Форму команда не меняет. Без --config, без form.bsl и без соседних форм досье строится, а шапка называет, чего без них\n"
                    "не оценить. Отказ формы (проверка, раскладка) — слова в stderr и код 2.")
    p.add_argument("form", help="форма: form.frm, Form.bin, каталог формы или документ уровня 1")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/ в XML и формы под ним): "
                                    "метаданные объекта и стиль конфигурации по соседним формам того же вида")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): реквизиты и табличные части объекта формы "
                                                      "для путей по метаданным; рядом можно дать --config (ссылочные типы реквизитов). Объект с тем же именем в выгрузке — отказ")
    p.add_argument("-o", "--out", help="каталог досье (умолчание — .v8tmp/brief/ рядом с формой)")
    p.add_argument("--origin", help="форма выгрузки (form.frm), копия которой строится: она не сосед для стиля конфигурации. Без ключа исключаются форма с тем же "
                                    "видом, объектом и именем формы в выгрузке и неправленая копия")
    p.add_argument("--code-notes", metavar="FILE", help="записи разбора кода, который сделала модель (code-notes.json, docs/brief-code.md): проверяются и собираются в досье, "
                                                        "безусловное применяется на рисунке; без ключа и без --no-code у формы с модулем команда выдаёт только задание на разбор кода")
    p.add_argument("--detail", metavar="ЧАСТИ", help="подробности к обзору brief.md — в brief-full.md: structure (объект, дерево, элементы, растяжение, картинки), columns (колонки таблиц), "
                                                     "facts, norms, style, editing (ограничения и примеры правок), code (модуль формы); части через запятую, all — все")
    p.add_argument("--no-code", action="store_true", help="досье без разбора кода: что код делает на экране, неизвестно (как у формы без модуля)")
    p.add_argument("--state", metavar="FILE", help="состояние формы для картинок (state.json, docs/layout.md): показать скрытое, спрятать видимое, выбрать страницу панели и т. п.; "
                                                   "накладывается поверх разбора кода и сильнее его")
    p.add_argument("--hidden", choices=("hide", "hatch"), help="скрытое на картинках: hatch (умолчание) — на своём месте со штриховкой; hide — как на экране, не нарисовано")
    p.add_argument("--conditional", choices=("plain", "hatch"), help="то, что код скрывает или показывает по условию: plain (умолчание) — как в файле; hatch — со штриховкой, как скрытое")
    p = sub.add_parser(
        "fragment", help="описание формы обработки по скелету вида (generate.fragment): pairs_run, params_sheet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Заготовка описания формы обработки по скелету вида (docs/generate.md, «Обработка»):\n"
                    + "\n".join(f"  {k} — {v}" for k, v in generate_mod.FRAGMENTS.items()) + "\n"
                    "Описание записывается в -o или выводится в stdout; затем его правят и передают в generate.")
    p.add_argument("name", choices=sorted(generate_mod.FRAGMENTS), help="фрагмент")
    p.add_argument("--object", required=True, help="полное имя обработки («Обработка.Имя»)")
    p.add_argument("--field", action="append", required=True,
                   help="поле: имя реквизита обработки либо «Имя:form» — реквизита формы; ключ повторяют")
    p.add_argument("--title", help="заголовок формы")
    p.add_argument("--columns", type=int, default=1, help="колонок пар (1…3)")
    p.add_argument("--sheet", help=f"имя поля табличного документа (только params_sheet; умолчание «{generate_mod.FRAGMENT_SHEET}»)")
    p.add_argument("--bar", choices=generate_mod.FRAGMENT_BARS,
                   help=f"панель команд (только params_sheet): top — верхняя, bottom — нижняя ({generate_mod.FRAGMENT_BAR}, умолчание: у большинства "
                        "форм скелета), none — без неё")
    p.add_argument("-o", "--out", help="куда положить описание (JSON); без ключа — в stdout")
    p = sub.add_parser(
        "describe", help="описание формы из самой формы-образца (frm_codec.describe): блоки словаря generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Форма → описание из блоков (command_bar, fields с columns, group, tabs, table) того же словаря, что\n"
                    "у generate (docs/describe.md). С --config имена реквизитов объекта берутся из метаданных; привязка к\n"
                    "реквизиту формы — имя реквизита формы. Что словарь не знает (кнопка, картинка, надпись без поля,\n"
                    "таблица на реквизит формы, колонка без данных…) попадает в ключ skipped с типом, именем и причиной.\n"
                    "Описание записывается в -o или выводится в stdout; пояснения выводятся в stderr.")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/ в XML): имена реквизитов объекта")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): реквизиты и табличные части объекта формы "
                                                      "для путей по метаданным; рядом можно дать --config (ссылочные типы реквизитов). Объект с тем же именем в выгрузке — отказ")
    p.add_argument("--form-use", choices=generate_mod.ROLE_FORMS,
                   help="у справочника с группами — форма элемента или группы (без ключа: по именам полей)")
    p.add_argument("--kind", help="вид описания, когда по метаданным его не найти (processing); для формы под "
                                  "DataProcessors/<Имя>/Forms/ берётся сам")
    p.add_argument("--object", help="полное имя объекта описания («Обработка.Имя»), когда по метаданным его не найти")
    p.add_argument("-o", "--out", help="куда положить описание (JSON); без ключа — в stdout")
    p = sub.add_parser(
        "design", help="один дизайн: версия общего блока, стиль и оформление — внутри формы и "
                       "против соседних форм (--siblings)")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("--siblings", help="каталог выгрузки той же конфигурации или обработки: "
                                      "все *.frm под ним, кроме самой формы")
    p.add_argument("--origin", help="форма выгрузки (form.frm), копия которой проверяется или правится: она не сосед. Без ключа исключаются форма с тем же "
                                    "видом, объектом и именем формы в выгрузке и неправленая копия")
    p = sub.add_parser(
        "lint", help="линтер ритма: отступы и шаг вне диапазона нормы вида, привязки не по роли, наложение элементов, "
                     "выход за форму, поле уже минимума, смесь версий и вида (замечания, не отказы)")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("--siblings", help="каталог выгрузки той же конфигурации: ещё сверка версии, стиля и вида полей "
                                      "со своей конфигурацией (все *.frm под ним, кроме самой формы)")
    p.add_argument("--origin", help="форма выгрузки (form.frm), копия которой проверяется или правится: она не сосед. Без ключа исключаются форма с тем же "
                                    "видом, объектом и именем формы в выгрузке и неправленая копия")
    p.add_argument("--kind", help="вид формы по перечню норм (catalog.item, document.list, processing …), когда по "
                                  "пути в выгрузке его не найти")
    p.add_argument("--config", help="каталог выгрузки конфигурации (Catalogs/, Documents/, DataProcessors/ в XML): замечание о типе таблиц "
                                    "на табличных частях (TypeId части)")
    p.add_argument("--root-xml", metavar="ФАЙЛ", help="корневой XML выгрузки внешней обработки или внешнего отчёта (<Имя>.xml): то же для "
                                                      "табличных частей внешнего объекта")
    p = sub.add_parser(
        "layout", help="раскладка при размерах окна: предел с ограничивающей парой, мёртвые "
                       "правила, элементы, остающиеся на месте на пути, координаты")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("--size", action="append", help="размер клиентской области ШxВ (можно "
                                                   "несколько): таблица координат при нём")
    p.add_argument("--range", action="store_true",
                   help="подробно: по пять ограничений на направление и пределы панелей")
    p.add_argument("--order", choices=layout_mod.ORDERS, default="wh",
                   help="порядок осей, в котором окно приходит к размеру (--size): wh — сначала ширина, потом "
                        "высота (по умолчанию, так окно открывает пускач), hw — сначала высота, потом ширина; "
                        "предел второй оси считается при фактическом росте первой")
    p.add_argument("--shown", action="append",
                   help="показанная страница панели или формы ИМЯ=СТРАНИЦА (имя панели или «форма»; можно "
                        "несколько): показанная страница перекладывается на размер, скрытая не сдвигается")
    p.add_argument("--stale", help="размер ШxВ, на котором скрытые страницы перекладывались в последний "
                                   "раз (с --shown); без него скрытые страницы остаются на проектном месте")
    p.add_argument("--grow", action="append", metavar="ШxВ",
                   help="прирост клиентской области ШxВ (например 200x100): что делает каждый элемент родителя формы, разделитель — по "
                        "своим правилам, соседи — вслед за ним (можно несколько)")
    p.add_argument("--drag", action="append", metavar="РАЗДЕЛИТЕЛЬ",
                   help="перетаскивание разделителя мышью (модель, в предприятии не проверялась): таблица «сдвиг → что с каждым "
                        "элементом» и пределы хода; можно несколько разделителей")
    p.add_argument("--drag-by", type=int, action="append", metavar="PX",
                   help="сдвиг разделителя в px для --drag (+ вправо или вниз; можно несколько; по умолчанию +50 и −50)")
    p.add_argument("--at-open", action="store_true",
                   help="размер задан открытием формы в запомненном размере, а не переходом: предел «край» у "
                        "элемента, остающегося на месте, не действует")
    p = sub.add_parser(
        "anchors-check", help="диагноз поломок привязок: форма не растягивается, столкновения при малом изменении размера, "
                              "наезды, расхождение выравнивания, мёртвые правила, циклы; с виновниками")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p = sub.add_parser(
        "repair-anchors", help="исправление поломок привязок: normalize_anchors по формальным рисункам, затем наименьшая правка "
                               "по каждому виновнику; box не меняется; --dry-run — только отчёт")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("-o", "--out", help="куда записать исправленную форму (нужен без --dry-run)")
    p.add_argument("--dry-run", action="store_true", help="только отчёт: что найдено и что было бы исправлено; ничего не записывается")
    p.add_argument("--element", action="append", help="править только этого виновника (имя; во вложенной панели — Панель/Имя; можно несколько)")
    p.add_argument("--unverified", action="store_true", help="разрешить правки там, где край родителя не проверялся (как у set_anchors)")
    p = sub.add_parser(
        "render", help="каркас формы в SVG или PNG по модели раскладки: клиентская область при размере окна; --before — «до | после»")
    p.add_argument("form", help="form.frm, Form.bin, каталог формы или документ уровня 1 (.json)")
    p.add_argument("-o", "--output", help="куда положить картинку: .png — PNG первым найденным конвертером (rsvg-convert, "
                                          "magick, inkscape, qlmanage), иначе SVG (без ключа — SVG в stdout)")
    p.add_argument("--before", metavar="ДО", help="форма ДО правки: «до | после» рядом, новые обведены зелёным, сдвинутые "
                                                  "оранжевым, убранные красным; перечень словами в stdout (нужен -o)")
    p.add_argument("--config", help="каталог выгрузки конфигурации (корень с Catalogs/, CommonPictures/): оттуда рисуются общие картинки, на которые ссылается форма; "
                                    "без ключа выгрузка ищется выше формы по раскладке каталогов; чего не хватило — строка «нужны файлы выгрузки: …» в stderr")
    p.add_argument("--size", help="размер клиентской области ШxВ (умолчание — размер формы)")
    p.add_argument("--sizes", metavar="РАЗМЕРЫ", help="полоса кадров в ряд: ШxВ через запятую, min — минимум раскладки, max — предел роста "
                   "(715x440,968x561,min,max); значки поведения при растяжении окна (растягивается, сдвигается, пропорционально, мёртвые правила) и перечень словами в stdout; "
                   "с --before — две полосы и смена поведения")
    p.add_argument("--shown", action="append",
                   help="показанная страница панели или формы ИМЯ=СТРАНИЦА (имя панели или «форма»; можно несколько)")
    p.add_argument("--state", metavar="FILE", help="состояние формы (state.json, docs/layout.md): показать скрытое, спрятать видимое, выбрать страницу панели, доступность, заголовки, размер")
    p.add_argument("--hidden", choices=("hide", "hatch"), help="скрытое: hatch (умолчание) — на своём месте со штриховкой (кто скрыл, называют заметки и досье); hide — как на экране")
    p.add_argument("--conditional", choices=("plain", "hatch"), help="то, что код скрывает или показывает по условию: plain (умолчание) — как в файле; hatch — со штриховкой, как скрытое")
    p.add_argument("--no-frame", action="store_true", help="картинка без внешней рамки окна формы (без ключа одиночная картинка клиентской области лежит в рамке окна в 4 px, у формы «Не изменять размер» в 3 px, без заголовка)")
    p.add_argument("--code-notes", metavar="FILE", help="записи разбора кода (code-notes.json): безусловное применяется, условное помечается; нужен form.bsl рядом с формой")
    p = sub.add_parser("diff", help="различия двух form.frm по адресам")
    p.add_argument("a"); p.add_argument("b"); p.add_argument("--names", action="store_true",
                   help="назвать элемент, в чьём поддереве лежит адрес")
    p.add_argument("--meaning", action="store_true",
                   help="смысловой дифф: сравнение по ИМЕНАМ карты, без шума платформы "
                        "(платформа при каждой выгрузке заново выдаёт GUID кнопок и переставляет записи действий). "
                        "Адресов не печатает")
    p = sub.add_parser("stat", help="вариативность позиций по каталогам форм")
    p.add_argument("dirs", nargs="+"); p.add_argument("-o", "--out"); p.add_argument("--md")
    p.add_argument("--commit-summary", action="store_true",
                   help="перезаписать frm_codec/data/corpus_stat.json и corpus_unknown.json — файлы в git")
    p = sub.add_parser("schema", help="перегенерировать FORMAT.md, схему и приложения к карте (только в репозитории навыка)")
    p.add_argument("--md", help="куда положить карту (умолчание — FORMAT.md)")
    p.add_argument("--json", help="куда положить схему (умолчание — schema/frm.schema.json)")
    p.add_argument("--open",
                   help="куда положить приложение «Открытые позиции» (умолчание — FORMAT-open.md)")
    p.add_argument("--sources", help="куда положить карту с источниками (умолчание — FORMAT-sources.md)")
    p = sub.add_parser("patterns", help="нормы компоновки по виду формы из переписи корпуса (patterns.json)")
    p.add_argument("--check", action="store_true", help="не писать: сверить файл с пересборкой, код 1 при разнице")
    p.add_argument("-o", "--out", help="куда писать (умолчание — frm_codec/data/patterns.json)")
    p = sub.add_parser(
        "unpack", help="Form.bin → form.frm, form.bsl, info.txt рядом с контейнером (как инструмент выгрузки); уже разложенные формы не трогает",
        description="Раскладывает Form.bin рядом с ним: form.frm (описание формы), form.bsl (модуль), info.txt (метаинформация). "
                    "Форма, у которой form.frm уже лежит рядом, не трогается (с --force файлы перезаписываются из контейнера). Вывод — число разложенных и перечень нечитаемых.")
    p.add_argument("path", help="Form.bin, каталог Ext, каталог формы; с --all — каталог с формами (обход всего дерева)")
    p.add_argument("--all", action="store_true", help="разложить все Form.bin под каталогом")
    p.add_argument("--force", action="store_true",
                   help="перезаписать form.frm, form.bsl, info.txt из контейнера, даже если они уже лежат рядом (файлы устарели после "
                        "новой выгрузки); несохранённые правки файлов пропадают")
    p = sub.add_parser(
        "pack", help="form.frm, form.bsl, info.txt → Form.bin, если содержимое разошлось с контейнером",
        description="Собирает Form.bin из form.frm, form.bsl, info.txt рядом. Контейнер переписывается, только если содержимое "
                    "файлов разошлось с его секциями; иначе — «не изменился». В каталоге с внешней сборкой (.v8mirror.json выше по дереву) "
                    "контейнер собирает внешний инструмент, команда отказывает; ключ --force собирает вручную.")
    p.add_argument("path", help="form.frm, Form.bin, каталог Ext, каталог формы; с --all — каталог с формами")
    p.add_argument("--all", action="store_true", help="собрать все Form.bin под каталогом, где содержимое разошлось")
    p.add_argument("--force", action="store_true", help="собрать и в каталоге с внешней сборкой")
    p.add_argument("--create", action="store_true", help="новый Form.bin у формы без контейнера: form.frm, form.bsl (нет — пустой модуль), "
                                                         "info.txt, если есть")
    sub.add_parser("selftest", help="самопроверка навыка на этой машине: формы, которые навык собирает сам (тесты в комплект не входят)",
                   description="Строит заготовки всех видов, правит и рисует их, собирает Form.bin и проходит круг «файл → JSON → файл» во "
                               "временном каталоге с кириллицей в пути. Код 0 — все проверки прошли, 1 — отказ хоть одной (причина в строке).")
    p = sub.add_parser(
        "epf-copyinfo", help=".epf/.erf → дописать в copyinfo ссылки обычных форм (обработка, собранная ibcmd)",
        description="Дописывает в элемент copyinfo внешней обработки или отчёта ссылки, которые нужны её обычным формам; уже записанное "
                    "не трогает. Файл (или -o) пишется, только если copyinfo изменился. Отказ — словами, код 1.")
    p.add_argument("path", help=".epf или .erf")
    p.add_argument("-o", "--out", help="куда писать результат (умолчание — тот же файл); без изменений ничего не пишется")
    p.add_argument("--dry-run", action="store_true", help="только сообщить, что будет дописано")
    p = sub.add_parser("propose", help="предложения к карте из журнала изменений (только в репозитории навыка)")
    p.add_argument("--ledger"); p.add_argument("-o", "--out")
    p.add_argument("--matrix-dir", help="каталог матриц свойств (умолчание — каталог матриц репозитория навыка)")
    args = ap.parse_args(argv)
    handler = {"decode": cmd_decode, "encode": cmd_encode, "validate": cmd_validate,
               "edit": cmd_edit, "generate": cmd_generate, "new": cmd_new, "add-field": cmd_add_field, "fragment": cmd_fragment, "describe": cmd_describe, "brief": cmd_brief, "design": cmd_design, "lint": cmd_lint, "layout": cmd_layout, "render": cmd_render, "anchors-check": cmd_anchors_check, "repair-anchors": cmd_repair_anchors,
               "diff": cmd_diff, "stat": cmd_stat, "unpack": cmd_unpack, "pack": cmd_pack, "selftest": cmd_selftest, "epf-copyinfo": cmd_epf_copyinfo,
               "schema": cmd_schema, "propose": cmd_propose, "patterns": cmd_patterns}[args.cmd]
    _search_config_pictures(args)
    try:
        code = handler(args)
        _say_config_pictures()
        # Поток дописывается здесь, внутри блока `try`: иначе обрыв трубы всплыл бы при выходе из процесса, где
        # перехватить его уже нечем.
        sys.stdout.flush()
        return code
    except BrokenPipeError:
        # `diff … | head` закрывает трубу раньше, чем мы дописали вывод. Это не отказ команды и не дефект:
        # читателю хватило. Этот `except` стоит перед `OSError`, наследником которого является, иначе обрыв
        # печатался бы как отказ. Остаток вывода отбрасывается, чтобы Python не повторил ту же ошибку при
        # закрытии потока.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except (ValueError, OSError) as e:
        # В stderr, а не в stdout: `decode`, `diff` и `stat` без `-o` печатают данные, и отказ в том же потоке
        # попал бы в конвейер и в файл. Замечания проверки (`_say`) остаются в stdout: это ответ команды.
        print(f"ОТКАЗ: {e}", file=sys.stderr)
        return 1
    finally:
        configpics.deactivate()


if __name__ == "__main__":
    sys.exit(main())
