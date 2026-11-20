"""Внешняя рамка окна формы (без заголовка): четыре пикселя вокруг клиентской области, как рисует предприятие.

Окно обычной формы в предприятии: слева и сверху белая линия, затем две линии `#CED2CE` и тёмная `#737373` у самой клиентской области; справа и снизу изнутри наружу тёмная `#737373`, две линии `#CED2CE` и внешняя `#8C908C`.
У формы с «Не изменять размер» (`size_change` = `DontChange`) рамка тоньше — три пикселя, линия `#CED2CE` одна. Верх рисуется как левая сторона: заголовка окна рамка не несёт.
Углы: внешний левый верхний — белый; правый верхний — `#DEE2DE` над `#7B7B7B`, левый нижний — `#DEE2DE` над `#7B7B7B`; правый нижний — `#8C8C8C`; у внутреннего левого верхнего угла два пикселя вдоль
левой стороны `#7B7F7B`. Цвета и углы сняты на окнах 400×300 и 1000×700 (формы с изменением размера) и 707×521 (форма с «Не изменять размер»); цвета в 16-битном сеансе предприятия.

Рамка — оболочка вокруг готовой картинки клиентской области: `framed(svg, doc)` кладёт её в вложенный `<svg>` со сдвигом на толщину рамки, поэтому координаты внутри остаются клиентскими.
"""
import re

WHITE, BAND, DARK, OUTER = "#ffffff", "#ced2ce", "#737373", "#8c908c"
CORNER_LIGHT, CORNER_DARK, INNER_CORNER, BOTTOM_RIGHT = "#dee2de", "#7b7b7b", "#7b7f7b", "#8c8c8c"
THICK, THIN = 4, 3
ROOT = re.compile(r"<svg xmlns='http://www.w3.org/2000/svg' width='([0-9.]+)' height='([0-9.]+)'>")


def thickness(doc):
    """Толщина рамки окна в пикселях: 3 у формы «Не изменять размер», иначе 4."""
    return THIN if isinstance(doc, dict) and doc.get("size_change") == "DontChange" else THICK


def parts(width, height, t=THICK):
    """Рамка окна клиентской области `width`×`height` как `<rect>` на полотне `(width + 2t)×(height + 2t)`: полосы и угловые пиксели, без клиентской области."""
    tw, th = width + 2 * t, height + 2 * t
    r, b = tw - 1, th - 1

    def rect(x, y, w, h, color, cls="window-frame"):
        return f"<rect class='{cls}' x='{x}' y='{y}' width='{w}' height='{h}' fill='{color}'/>"
    out = [rect(0, 0, tw, th, BAND, "window-frame-band"),
           rect(0, 0, tw - 1, 1, WHITE), rect(0, 0, 1, th - 1, WHITE),                  # белые верх и лево
           rect(r, 2, 1, th - 3, OUTER), rect(1, b, tw - 2, 1, OUTER),                   # внешние право и низ
           rect(r, 0, 1, 1, CORNER_LIGHT), rect(r, 1, 1, 1, CORNER_DARK),
           rect(0, b - 1, 1, 1, CORNER_LIGHT), rect(0, b, 1, 1, CORNER_DARK), rect(r, b, 1, 1, BOTTOM_RIGHT)]
    inner = t - 1
    out += [rect(inner, inner, width + 2, 1, DARK), rect(inner, inner, 1, height + 2, DARK),                      # тёмная линия у клиентской области
            rect(inner, t + height, width + 2, 1, DARK), rect(t + width, inner, 1, height + 2, DARK),
            rect(inner, inner, 1, 2, INNER_CORNER)]
    return out


def framed(svg, doc=None):
    """Картинка клиентской области `svg` в рамке окна: `<svg>` на `(width + 2t)×(height + 2t)`, рамка и вложенная клиентская область со сдвигом на `t`. Картинка не из `render` — без изменений."""
    found = ROOT.match(svg)
    if not found:
        return svg
    width, height = found.group(1), found.group(2)
    w, h = float(width), float(height)
    if w != int(w) or h != int(h):
        return svg
    w, h = int(w), int(h)
    t = thickness(doc)
    inner = svg[found.end():]
    if inner.endswith("</svg>"):
        inner = inner[:-len("</svg>")]
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w + 2 * t}' height='{h + 2 * t}'>" + "".join(parts(w, h, t))
            + f"<svg class='client' x='{t}' y='{t}' width='{w}' height='{h}' overflow='hidden'>" + inner + "</svg></svg>")
