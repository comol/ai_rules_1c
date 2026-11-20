"""Положение знаков надписей в PNG: по метрике шрифта форм, а не запасного шрифта растеризатора.

Подписи рисунка заданы шрифтом Tahoma, которого у растеризатора (rsvg-convert, ImageMagick) почти всегда нет: он берёт другой, и надпись выходит уже или шире
настоящей на 7–10 % (на снимках предприятия «Основание:» 84 px, у запасного шрифта 76). Перед переводом SVG в PNG каждая надпись с проверенным шрифтом
(`textwidth`: таблицы hdmx для 9…24 px, обычный и жирный; курсив — по таблице прямого шрифта) разбивается на знаки, и у каждого знака записан свой левый край — по сумме ширин знаков шрифта форм.
Занятое надписью место становится равным измеренному, форма знаков остаётся запасной. SVG-текст рисунка не меняется: правка идёт только на пути в PNG.
Привязка `middle` и `end` пересчитана в левый край: у знаков с собственным `x` привязка действует на каждый знак по отдельности. Пробел места не занимает, но сдвигает остальные.
Растеризатор, читающий список `x` или `textLength`, здесь не нужен: rsvg их не читает, а `tspan` с собственным `x` читает.
"""
import html
import re

from .. import textwidth
from . import font_metrics

# Позиции знаков считаны по таблицам Microsoft Sans Serif (hdmx), а формы знаков у Tahoma уже (у «Ф» при 11 px — на два пикселя): между знаками появлялись разрывы
# («Ф ирмы»). В PNG надпись рисуется самим Microsoft Sans Serif, если он есть у растеризатора; нет — следующая гарнитура, как раньше. В SVG гарнитура прежняя.
PNG_FACE = "Microsoft Sans Serif, Tahoma, sans-serif"
# У Microsoft Sans Serif нет жирного начертания: растеризатор рисовал бы жирную подпись обычной. Жирная (и жирная курсивная) подпись в PNG идёт гарнитурой Tahoma,
# у которой жирное начертание есть; позиции знаков при этом те же (таблицы Microsoft Sans Serif плюс пиксель на знак). Курсива нет ни у одной из двух: наклон
# создаёт растеризатор, ширины курсива — как у прямого шрифта (оценка).
PNG_FACE_BOLD = "Tahoma, sans-serif"
# Линии подчёркивания и зачёркивания в PNG рисуются прямоугольником в 1 px по всей ширине надписи вместе с пробелами (`text-decoration` растеризатора
# разрывается там, где знаков нет). Положение по экрану предприятия (Tahoma 11 px и Arial 13 px): толщина 1 px, цвет текста, подчёркивание — на строке ниже нижней строки знаков
# через одну (нижняя строка знаков + 2), зачёркивание — на 3 строки выше нижней строки знаков; линия сплошная, в том числе под пробелами. Для других размеров — тот же закон, оценка.
UNDERLINE_DY = 2          # строка подчёркивания: нижняя строка знаков + 2 (в SVG `y` — граница под нижней строкой, поэтому прямоугольник на `y + 1`)
STRIKE_UP = 1 / 3         # строка зачёркивания: `y` − round(ppem / 3) (11 и 13 px — 4 строки от границы базовой линии)
# Хинтинг предприятия растягивает «Ф», «/», «\\» и тире до ячейки таблицы (`hdmx`); контур растеризатора у этих знаков уже ячейки на 1,3 px и больше, и после знака оставался зазор
# («Ф искальный», «https:/ /»). Такой знак в PNG растягивается по горизонтали до ширины ячейки: отдельная надпись с `scale`. Нет шрифта растеризатора — знаки как были.
STRETCH_FROM = 1.3
_TEXT = re.compile(r"<text\b([^>]*)>([^<]*)</text>")
_SIZE = re.compile(r"\bfont-size='(\d+(?:\.\d+)?)'")
_X = re.compile(r"\bx='(-?\d+(?:\.\d+)?)'")
_ANCHOR = re.compile(r"\btext-anchor='(\w+)'")
_Y = re.compile(r"\by='(-?\d+(?:\.\d+)?)'")
_FILL = re.compile(r"\bfill='([^']+)'")
_DECORATION = re.compile(r"\s*\btext-decoration='([^']*)'")


def _glyphs(match):
    attrs, content = match.group(1), match.group(2)
    if "font-family='Tahoma, sans-serif'" not in attrs:
        return match.group(0)
    size, x = _SIZE.search(attrs), _X.search(attrs)
    if not size or not x or float(size.group(1)) != int(float(size.group(1))):
        return match.group(0)
    ppem = int(float(size.group(1)))
    text = html.unescape(content)
    if ppem not in textwidth._ADVANCE_BY_PPEM or len(text.strip()) < 2:
        return match.group(0)
    advance, unknown = textwidth._ADVANCE_BY_PPEM[ppem], textwidth._UNKNOWN_BY_PPEM[ppem]
    bold = 1 if "font-weight='700'" in attrs else 0
    widths = [advance.get(ch, unknown) + bold for ch in text]
    anchor = (_ANCHOR.search(attrs) or [None, "start"])[1]
    total = sum(widths)
    at = float(x.group(1)) - (total / 2 if anchor == "middle" else total if anchor == "end" else 0)
    spans, stretched = [], []
    for ch, width in zip(text, widths):
        if not ch.isspace():
            raster = font_metrics.advance(ch, ppem, bool(bold))
            if raster and width - raster >= STRETCH_FROM:
                stretched.append((at, width / raster, ch))
            else:
                spans.append(f"<tspan x='{at:g}'>{html.escape(ch, quote=False)}</tspan>")
        at += width
    new_attrs = _ANCHOR.sub("text-anchor='start'", attrs) if _ANCHOR.search(attrs) else attrs
    face = PNG_FACE_BOLD if bold else PNG_FACE
    new_attrs = new_attrs.replace("font-family='Tahoma, sans-serif'", f"font-family='{face}'", 1)
    decoration = _DECORATION.search(new_attrs)
    new_attrs = _DECORATION.sub("", new_attrs, count=1)
    first = float(x.group(1)) - (total / 2 if anchor == "middle" else total if anchor == "end" else 0)
    new_attrs = _X.sub(f"x='{first:g}'", new_attrs, count=1)
    wide = "".join(f"<text{_X.sub('x=' + chr(39) + '0' + chr(39), new_attrs, count=1)} transform='translate({left:g},0) scale({factor:.3f},1)'>{html.escape(ch, quote=False)}</text>"
                   for left, factor, ch in stretched)
    return f"<text{new_attrs}>{''.join(spans)}</text>" + wide + _lines(decoration.group(1) if decoration else "", attrs, first, total, ppem)


def _lines(decoration, attrs, left, total, ppem):
    """Прямоугольники подчёркивания и зачёркивания для надписи, записанной по знакам (`UNDERLINE_DY`, `STRIKE_UP`)."""
    base, fill = _Y.search(attrs), _FILL.search(attrs)
    if not decoration or not base:
        return ""
    colour = fill.group(1) if fill else "#000"
    rows = []
    if "underline" in decoration:
        rows.append(float(base.group(1)) + UNDERLINE_DY - 1)
    if "line-through" in decoration:
        rows.append(float(base.group(1)) - round(ppem * STRIKE_UP))
    return "".join(f"<rect class='text-line' x='{left:g}' y='{row:g}' width='{total:g}' height='1' fill='{colour}'/>" for row in rows)


def exact(svg):
    """SVG с надписями по знакам (для перевода в PNG); надписи с непроверенным шрифтом и одним знаком остаются как были."""
    return _TEXT.sub(_glyphs, svg)
