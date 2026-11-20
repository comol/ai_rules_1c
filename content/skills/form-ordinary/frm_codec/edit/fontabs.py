"""Абсолютный шрифт элемента: гарнитура, размер и начертание, выбранные в диалоге «Выбор шрифта» без шрифта стиля.

Запись такого шрифта не несёт маски: все свойства лежат на своих позициях. Её пишет `set_font` с `source="Absolute"`; здесь
собирается сама запись и проверяются границы. Все имена доступны через фасад `frm_codec.edit`.
"""

import copy

from .base import EditError
from .names import ABSOLUTE, FONT_REF, FONT_SCALE, FONT_VERSION, STYLE_FONTS
from .platform import CORPUS_FONT_PLACES

# Запись, которую платформа пишет при выборе шрифта в диалоге: набор символов 1 (по умолчанию), три значения качества и
# отсечения 3, 2, 1, последнее число 1, масштаб 100 %. Ключи — в порядке позиций записи.
SHAPE = {"version": 7, "source": ABSOLUTE, "flags": 0, "size10": None, "u4": 0, "u5": 0, "u6": 0, "weight": 400,
         "italic": False, "underline": False, "strikeout": False, "u11": 1, "u12": 3, "u13": 2, "u14": 1, "u15": None,
         "face": None, "u17": 1, "scale": 100}
# Шаг и семейство гарнитуры — число `u15` (низшие биты — шаг, старшие — семейство); второе число записи, `u12`, — точность вывода:
# 3 у гарнитур TrueType и 1 у растровой. Все девять строк — записи платформы при выборе гарнитуры в диалоге «Выбор шрифта».
FACES = {"Arial": 34, "Tahoma": 34, "Times New Roman": 18, "Courier New": 49, "Verdana": 34, "Segoe UI": 34, "Calibri": 34,
         "Consolas": 49, "MS Sans Serif": 34}
# У растрового шрифта точность вывода своя: платформа писала 1 вместо 3.
FACE_PRECISION = {"MS Sans Serif": 1}
# Адреса, у которых платформа писала абсолютный шрифт; у остальных адресов шрифта запись та же, но платформа её там не писала.
MEASURED_PLACES = (("TextBox", "font"), ("ComboBox", "font"), ("TextDocumentField", "font"), ("CalendarBox", "font"),
                   ("RadioButton", "font"), ("Form", "font"), ("Label", "font"), ("Button", "font"), ("CheckBox", "font"),
                   ("Panel", "font"), ("GroupBox", "font"), ("TableBox", "font"), ("CommandBar", "font"),
                   ("PictureBox", "font"), ("ListBox", "font"), ("ProgressBar", "font"), ("TrackBar", "font"))
MEASURED_NAMES = ("ПолеВвода, ПолеВыбора, ПолеТекстовогоДокумента, ПолеКалендаря, Переключатель, Надпись, Кнопка, Флажок, Панель, "
                  "РамкаГруппы, ТабличноеПоле (основной шрифт), КоманднаяПанель, ПолеКартинки, ПолеСписка, Индикатор, Полоса, "
                  "самой формы")
# Возврат с абсолютного шрифта платформа писала у надписи (шрифт стиля и «Авто») и поля ввода (шрифт стиля).
RETURN_MEASURED = (("Label", "font"), ("TextBox", "font"))
UNSUPPORTED = {"style_font": "ссылки на шрифт стиля", "system_font": "ссылки на системный шрифт",
               "scale": "масштаба", "scale_set": "признака масштаба"}


def build(record, was_absolute, kind, name, values, given, typeface, unverified):
    """Новая запись абсолютного шрифта: `(черновик, слова отчёта)`.

    `values` — названные свойства (`size10`, `weight`, `italic`, `underline`, `strikeout`, `face`), `given` — названные параметры,
    которых у абсолютного шрифта нет. Если шрифта ещё нет (запись была другого вида), обязательны гарнитура и размер: значения
    по умолчанию платформа берёт из стиля, и операция их не угадывает. Прежнюю запись операция целиком заменяет, поэтому
    свойства прежнего шрифта (Авто, шрифт стиля) в новую не переходят.
    """
    if given:
        raise EditError("у абсолютного шрифта нет " + ", ".join(UNSUPPORTED[key] for key in given) + ": все свойства лежат "
                        "своими позициями записи, а эти значения платформа в абсолютной записи не писала")
    if typeface != "single":
        raise EditError("у абсолютного шрифта начертание — четыре отдельные позиции записи, способов записи нет: "
                        "уберите typeface")
    if kind.startswith("ColumnControl."):
        raise EditError("абсолютный шрифт вложенного элемента колонки не проверялся: у такого шрифта в режиме редактирования "
                        "действует только запись диалога со шрифтом стиля")
    if (kind, name) not in CORPUS_FONT_PLACES and (kind, name) not in MEASURED_PLACES and not unverified:
        raise EditError(f"шрифта {name!r} у элемента вида {kind} в образцах форм нет, абсолютный шрифт там не проверялся. "
                        "Чтобы всё же выполнить операцию, передайте unverified=True")
    version = record.get(FONT_VERSION)
    if version != SHAPE["version"] and not unverified:
        raise EditError(f"запись шрифта версии {version}: абсолютный шрифт платформа писала в записи версии {SHAPE['version']} "
                        "(форма поколения 16); у версии 6 нет позиции масштаба, и такая запись не проверялась. "
                        "Чтобы всё же выполнить операцию, передайте unverified=True")
    if was_absolute:
        wanted = [key for key in SHAPE if key != FONT_SCALE or version == SHAPE["version"]]
        if list(record) != wanted:
            raise EditError(f"запись абсолютного шрифта {name!r} лежит не так, как её пишет платформа (поля {', '.join(record)}): "
                            "править её именами нечем, правьте JSON по адресу")
        draft = copy.deepcopy(record)
    else:
        missing = [key for key in ("face", "size10") if key not in values]
        if missing:
            raise EditError("абсолютный шрифт задают гарнитурой и размером вместе (face и size): в диалоге «Выбор шрифта» после "
                            "снятия «Шрифт стиля» их значения берутся из стиля, и операция их не угадывает")
        draft = dict(SHAPE)
        draft[FONT_VERSION] = version
        if version != SHAPE["version"]:
            draft.pop(FONT_SCALE)
    tail = ""
    for key, value in values.items():
        draft[key] = value
    face = values.get("face")
    if face is not None:
        if face not in FACES:
            if was_absolute and face == record.get("face"):
                pass
            else:
                raise EditError(f"шаг и семейство гарнитуры {face!r} (позиция u15 записи) не известны: платформа писала их для "
                                f"{', '.join(FACES)}. Другую гарнитуру задайте правкой JSON по адресу шрифта")
        else:
            draft["u15"] = FACES[face]
            draft["u12"] = FACE_PRECISION.get(face, SHAPE["u12"])
    if (kind, name) not in MEASURED_PLACES:
        tail += (f"; абсолютный шрифт у {kind} ({name}): запись и адрес те же, что у прежних записей шрифта этого вида, "
                 f"платформа её писала у {MEASURED_NAMES}")
    size = draft["size10"] / 10
    shown = ", ".join([draft["face"], f"{size:g}"]
                      + [word for flag, word in (("weight", "полужирный"), ("italic", "наклонный"),
                                                 ("underline", "подчёркнутый"), ("strikeout", "зачёркнутый"))
                         if (draft[flag] == 700 if flag == "weight" else draft[flag])])
    return draft, f"Absolute: {shown}; шаг и семейство {draft['u15']}{tail}"


LEAVE_TARGETS = {"StyleFont": "шрифт стиля", "Auto": "«Авто»"}
DEFAULT_STYLE_FONT = "TextFont"


def leave(record, kind, name, target, style_font, values, given, typeface, unverified):
    """Возврат с абсолютного шрифта к шрифту стиля или к «Авто»: `(новая запись, слова отчёта)`.

    Платформа пишет возврат целиком новой записью: без позиций гарнитуры и размера, с пустым переопределением и масштабом 100.
    Шрифт стиля по умолчанию — «Шрифт текста» (`TextFont`), как в диалоге после возврата галочки «Шрифт стиля». Значения
    (`face`, `size`, начертание) вместе с возвратом не называют: после возврата они берутся из стиля, а переопределение рядом
    платформа в таком вызове не писала.
    """
    if target not in LEAVE_TARGETS:
        raise EditError(f"с абсолютного шрифта возвращают к шрифту стиля (source=StyleFont) или к «Авто» (reset=true либо "
                        f"source=Auto), а не к {target!r}: системный шрифт после абсолютного платформа не писала")
    if kind.startswith("ColumnControl."):
        raise EditError("возврат абсолютного шрифта вложенного элемента колонки не проверялся: у такого шрифта в режиме "
                        "редактирования действует только запись диалога со шрифтом стиля")
    if values or given or typeface != "single":
        said = sorted(values) + list(given) + (["typeface"] if typeface != "single" else [])
        raise EditError("при возврате с абсолютного шрифта значений не называют: после возврата свойства берутся из "
                        f"{'стиля' if target == 'StyleFont' else 'умолчаний'}, а переопределение рядом платформа в таком "
                        f"вызове не писала — названо {', '.join(said)}. Вернитесь вызовом без значений, потом задайте их "
                        "отдельным вызовом")
    if style_font is not None and target != "StyleFont":
        raise EditError("у «Авто» ссылки на шрифт стиля нет: style_font называют только с source=StyleFont")
    if style_font is not None and style_font not in STYLE_FONTS:
        raise EditError(f"style_font={style_font!r} карта не знает; есть {', '.join(STYLE_FONTS)}")
    version = record.get(FONT_VERSION)
    if version != SHAPE["version"]:
        raise EditError(f"запись шрифта версии {version}: возврат платформа писала в записи версии {SHAPE['version']}; у версии 6 "
                        "позиции масштаба нет, и такая запись не проверялась. Правьте JSON по адресу")
    if list(record) != list(SHAPE):
        raise EditError(f"запись абсолютного шрифта {name!r} лежит не так, как её пишет платформа (поля {', '.join(record)}): "
                        "править её именами нечем, правьте JSON по адресу")
    draft = {FONT_VERSION: version, "source": target, "overrides": {"scale_set": False}}
    said = target
    if target == "StyleFont":
        draft[FONT_REF] = {"style_font": style_font or DEFAULT_STYLE_FONT}
        said += f" (style_font={draft[FONT_REF]['style_font']!r})"
    draft["L1+0"] = 1
    draft[FONT_SCALE] = SHAPE["scale"]
    tail = ""
    if (kind, name) not in RETURN_MEASURED:
        tail = (f"; возврат у {kind} ({name}): запись и адрес те же, что у прежних записей шрифта этого вида, платформа её "
                "писала у Надписи и ПоляВвода")
    return draft, f"{said}; переопределений нет, маска 0, масштаб 100{tail}"
