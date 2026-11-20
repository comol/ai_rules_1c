"""Тип реквизита словами: имена типов платформы по-русски, типы стандартных реквизитов."""

from . import vocab


def platform_type_words(name):
    """Тип из выгрузки (`v8:ValueTable`, `cfg:CatalogRef.Товары`, `cfg:ReportObject.Отчёт`) русским именем платформы; неизвестный — как в выгрузке."""
    if name in vocab.PLATFORM_TYPE_WORDS:
        return vocab.PLATFORM_TYPE_WORDS[name]
    bare = name[4:] if name.startswith("cfg:") else name
    head, dot, tail = bare.partition(".")
    if head in vocab.REF_WORDS:
        return f"{vocab.REF_WORDS[head]}.{tail}" if dot else vocab.REF_WORDS[head]
    return bare


def _type_words(attr):
    parts = []
    for name in attr.types:
        if name == "xs:string":
            text = "Строка" + (f"({attr.string_length})" if attr.string_length else "")
            parts.append(text + (", фиксированная длина" if attr.allowed_length == "Fixed" else ""))
        elif name == "xs:decimal":
            text = "Число" + (f"({attr.digits},{attr.fraction or 0})" if attr.digits else "")
            parts.append(text + (", неотрицательное" if attr.allowed_sign == "Nonnegative" else ""))
        elif name == "xs:dateTime":
            parts.append(vocab.DATE_WORDS.get(attr.date_fractions, "Дата"))
        elif name in vocab.TYPE_WORDS:
            parts.append(vocab.TYPE_WORDS[name])
        else:
            parts.append(platform_type_words(name))
    parts += [platform_type_words(name) for name in attr.type_sets]
    return " | ".join(parts) if parts else "произвольный тип"


def _std_type_words(obj, name):
    got = obj.std_types.get(name)
    if not got:
        return {"Дата": "Дата и время", "Родитель": f"СправочникСсылка.{obj.name}", "Владелец": ", ".join(obj.owners)}.get(name, "")
    kind, length, allowed = got
    text = {"String": "Строка", "Number": "Число"}.get(kind, str(kind))
    return text + (f"({length})" if length else "") + (", фиксированная длина" if allowed == "Fixed" else "")
