"""Углы закладок: пиксели срезанного угла, снятые со снимков предприятия (форма Опыт73, панели «Снизу», T333; в 16-битном цвете сеанса).

Угол — 5 строк на 7 столбцов от внешнего угла закладки: у закладки «Снизу» строки идут сверху вниз и последняя — нижняя граница; у закладки «Сверху» тот же рисунок перевёрнут по вертикали
(строка нижней границы наверху; совпало с углами «Сверху» на тех же снимках). Правый угол — зеркало левого по горизонтали (проверено: у активной и неактивной закладок совпал). Первые два столбца
и срез дают расхождение с прямым путём SVG, поэтому угол рисуется пикселями поверх пути; пиксели цвета заливки закладки и цвета формы (`#ffffef`) не пишутся — их даёт путь и подложка.
"""

ACTIVE = (
    ("#bdb994", "#efebd6", "#ffffef", "#ffffef", "#ffffef", "#ffffef", "#ffffef"),
    ("#d6d6bd", "#cec6a5", "#ffffef", "#ffffef", "#ffffef", "#ffffef", "#ffffef"),
    ("#f7fbe7", "#b5b58c", "#e7e2c6", "#ffe7ad", "#ffe2a5", "#ffe2a5", "#ffe2a5"),
    ("#ffffef", "#efefde", "#b5b58c", "#cec6a5", "#efdaa5", "#ffe2a5", "#ffe2a5"),
    ("#ffffef", "#ffffef", "#f7fbe7", "#cecead", "#b5b58c", "#b5b184", "#b5b184"),
)
INACTIVE = (
    ("#d6d2b5", "#e7e2c6", "#efebce", "#efebce", "#efebce", "#efebce", "#efebce"),
    ("#e7e2ce", "#d6d2b5", "#efebce", "#efebce", "#efebce", "#efebce", "#efebce"),
    ("#fffbe7", "#d6ceb5", "#ded6bd", "#efebce", "#efebce", "#efebce", "#efebce"),
    ("#ffffef", "#f7f7de", "#d6ceb5", "#d6d2b5", "#e7e2c6", "#efebce", "#efebce"),
    ("#ffffef", "#ffffef", "#fffbe7", "#e7e2ce", "#d6d2b5", "#cecaad", "#cecaad"),
)
WIDTH, HEIGHT = 7, 5
SKIP = ("#ffffef", "#efebce")
# Сопряжение активной закладки «Снизу» с линией страницы (строка над закладкой): на один пиксель внутрь от правого края — `#f7f7de`, правее края два пикселя `#bdb994`.
JOINT_INNER, JOINT_OUTER = "#f7f7de", "#bdb994"


def corner_pixels(active, flip, x, y, w, h):
    """`[(x, y, цвет)]` пикселей двух нижних (flip) либо верхних углов закладки `x, y, w, h`; пусто, когда закладка уже двух углов."""
    if w < 2 * WIDTH:
        return []
    table = ACTIVE if active else INACTIVE
    out = []
    for r, row in enumerate(table):
        py = y + h - HEIGHT + r if flip else y + HEIGHT - 1 - r
        for c, color in enumerate(row):
            if color in SKIP:
                continue
            out.append((x + c, py, color))
            out.append((x + w - 1 - c, py, color))
    return out
