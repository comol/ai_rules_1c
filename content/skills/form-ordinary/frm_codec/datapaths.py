"""Где лежат данные пакета: единственное место, знающее путь к `frm_codec/data/`.

Данные — не код: нормы вида (`patterns.json`), сводка и перепись корпуса, таблица старых версий, формы блоков типа, шаблоны элементов
(`data/templates/*.json`) и заготовки форм (`data/blanks/*.json`). Все чтения и записи данных берут путь отсюда; каталог `data/` — не пакет Python, `__init__.py` в нём нет.
"""
import pathlib

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"
TEMPLATES_DIR = DATA_DIR / "templates"
BLANKS_DIR = DATA_DIR / "blanks"
PLATFORM_PICTURES_DIR = DATA_DIR / "platform_pictures"       # картинки библиотеки платформы 8.3.27 (файлы PNG и SVG и `index.json`)
