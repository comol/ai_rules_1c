"""Пометки кода для рисунка формы вне досье (`render --code-notes`, `edit --render --code-notes`): что код модуля делает на экране по разбору модели — те же записи,
та же проверка и то же состояние, что на картинках досье."""
import pathlib

from .. import bar_platform, census, describe, edit, layout, lstring, metadata
from .. import structure as structure_mod
from . import codenotes, facts, images, module_effects as module, paths
from .assemble import _object_module, make_targets
from .purpose import _Binder, parse_module


def module_marks(doc, form_path, module_text, code_notes, config_dir=None, root_xml=None):
    """Пометки кода для `render.render(…, marks=…)`: `render.CodeMarks`, как на картинках досье (`brief.images.marks_of`); отклонённые записи — в `marks.rejected`
    (`[{index, kind, why}]`), рисунок называет их в `notes`, команда — в stderr.

    `code_notes` — записи разбора кода (`code-notes.json`, `brief.codenotes`); без модуля, без записей или с модулем без кода, а также если форму или модуль разобрать нельзя,
    — `None`: рисунок строится без пометок. Безусловный заголовок остаётся в `marks.applied`: документ с подставленными заголовками даёт `brief.images.coded_doc`, как у досье."""
    from . import modulescan
    module_text = modulescan.effective(module_text)
    if module_text is None or code_notes is None:
        return None
    try:
        with lstring.main_language(None), bar_platform.context():
            form = layout.read(doc)
            kind = census.record(doc, str(pathlib.Path(form_path).resolve()))["kind"]
            structure = structure_mod.recognize(doc, kind)
            names = facts._Names(form, structure)
            config = config_dir if config_dir is not None else paths.config_of(form_path)     # выгрузка нужна для `source` записей; форма в выгрузке находит её сама
            try:
                meta = metadata.load_for(config, root_xml)          # имена реквизитов объекта для привязок даёт выгрузка
            except metadata.MetadataError:
                meta = None
            _hint_kind, hint_object = describe.hints_from_path(pathlib.Path(form_path).resolve())
            targets = make_targets(doc, form, names, None, _Binder(doc, meta, hint_object), module_text, config, _object_module(form_path, config))
            accepted, rejected = codenotes.check(code_notes, targets)
            procedures = parse_module(module_text)
            effects = module.group(codenotes.effect_rows(accepted, procedures))
            marks = images.marks_of(doc, structure, effects, codenotes.form_rows(accepted, procedures))
            marks.rejected = [{"index": r["index"], "kind": r["kind"], "why": r["why"]} for r in rejected]
            return marks
    except (edit.EditError, ValueError, KeyError, TypeError):
        return None
