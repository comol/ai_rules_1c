"""Команда `epf-copyinfo`: дописать в `copyinfo` внешней обработки ссылки, которые нужны её обычным формам."""
import os
from pathlib import Path

from . import container as cont
from . import copyinfo, mainwarn, meta

FOREIGN_NOTE = ("Ссылки форм на объекты конфигурации (стиль, тип справочника и т. п.) команда не дописывает: из одного файла "
                "их не восстановить; нужны ли они платформе, не проверялось.")


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".epf-copyinfo.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def run(path, out=None, dry_run=False):
    """Возвращает `(строки отчёта, код возврата, изменён ли copyinfo)`. Код 0 — успех (изменён или полон), 1 — отказ."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"Отказ: файл не прочитан: {exc.strerror or exc}"], 1, False
    try:
        container = cont.read(data)
        proc = meta.load(container)
        if not proc.forms:
            return [f"{path.name}: обычных форм нет — файл не изменён"], 0, False
        res = copyinfo.merge(proc)
        warned = mainwarn.warnings(proc)
    except cont.EpfError as exc:
        return [f"Отказ: {exc}"], 1, False
    if not res.changed:
        return [f"{path.name}: copyinfo полный — файл не изменён", FOREIGN_NOTE] + warned, 0, False
    lines = [f"{path.name}: copyinfo дополнен — объектов {len(res.objects)}, типов {len(res.types)}, путей {len(res.paths)}"]
    for title, rows in (("объект", res.objects), ("тип", res.types), ("путь привязки", res.paths)):
        lines += [f"  {title}: {label}" for _, label in rows]
    lines.append(FOREIGN_NOTE)
    lines += warned
    target = Path(out) if out else path
    if dry_run:
        lines.append(f"Пробный прогон: {target} не записан")
        return lines, 0, True
    container.get("copyinfo").set_data(res.text)
    try:
        _write_atomic(target, cont.write(container))
    except OSError as exc:
        return lines + [f"Отказ: файл {target} не записан: {exc.strerror or exc}"], 1, False
    lines.append(f"Записано: {target}")
    return lines, 0, True
