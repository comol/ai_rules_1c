"""Картинки формы и поля картинки: где и как они рисуются (картинка формы под элементами, поле картинки, слова о том, что не сверено).

Что снято в предприятии (формы с картинками PNG, ICO и GIF; сверка по пикселям):

* **Картинка формы** («РазмерКартинки» «Растянуть») заливает всю клиентскую область, растянутая БЕЗ сглаживания: край картинки идёт ступеньками, пиксели картинки видны крупными квадратами.
  Прозрачные пиксели картинки показывают цвет формы. Поверх неё лежат элементы со своим фоном: надпись, поле картинки, панель (всей рамкой) — залиты цветом формы.
* **Поле картинки** («РазмерКартинки» «Реальный размер»): картинка в своём размере по центру поля, поле залито цветом формы; рамки у поля без «Рамки» нет совсем.

Поле картинки: сняты все режимы («Растянуть», «Пропорционально», «Замостить», «Автоматический размер», «По размеру шрифта»). Картинка формы в режиме «Реальный размер» стоит по центру
либо у правого края («Справа») — оба положения сняты, другие режимы картинки формы названы в `notes`. Картинка панели: «Реальный размер» по центру и «Справа» сняты, «Замостить» снято на одной
картинке 32 px с прозрачностью, остальные режимы названы в `notes` и нарисованы по смыслу названия.
Вложенная картинка, файл которой не читается, — серый квадрат 16×16 на месте картинки, а причину называет строка `notes` (`unreadable_note`).
"""
from . import picture_bitmap
from .core import FORM_BG, _back_of, _dig, _font_of, _line_pitch

FORM_PICTURE_LOCATION_NOTE = "«ПоложениеКартинки» картинки формы при «Реальном размере» снято для «По центру» и «Справа»; заданное в файле положение не сверялось, картинка нарисована по центру"
FORM_PICTURE_NOTE = ("картинка формы «Растянуть» нарисована как в предприятии (растянута без сглаживания на всю клиентскую область); фон надписей, полей картинки и панелей поверх неё залит цветом формы, "
                     "а фон прочих видов элементов поверх картинки формы не сверялся")
FORM_PICTURE_MODE_NOTE = "режим «РазмерКартинки» и «ПоложениеКартинки» картинки формы, кроме «Растянуть», не сверялся: картинка нарисована в своём размере в левом верхнем углу"
PANEL_PICTURE_NOTE = ("картинка панели (фон страницы): сверены «Реальный размер» (по центру, «Справа» — у правого края по центру) и «Замостить» с одной картинкой 32 px с прозрачностью (чёрный фон страницы "
                      "и одна картинка по центру, прозрачные места — цвет формы); у картинок без прозрачности и других размеров «Замостить», как и остальные режимы и положения, нарисованы по тому же правилу или по смыслу названия и не сверялись")
BUTTON_PICTURE_MODE_NOTE = "положения «Сверху», «Снизу» картинки кнопки не сверялись с предприятием: картинка нарисована слева"
LABEL_PICTURE_NOTE = "картинка надписи: «Реальный размер» крупнее надписи обрезан рамкой надписи (не сверялось, сверена картинка 16 px)"


def _picture_block(node):
    return _dig(node, "content", "u1", "pictures", "picture")


def form_picture_block(doc):
    """Блок картинки формы (`layout_list/pictures`): `(картинка, размер, положение)` либо `None`."""
    holder = _dig(doc, "form", "container", "layout_holder", "layout_list")
    pictures = holder.get("pictures") if isinstance(holder, dict) else None
    picture = pictures.get("picture") if isinstance(pictures, dict) else None
    if not isinstance(picture, dict) or picture.get("source") in (None, 0):
        return None
    return picture, pictures.get("picture_size"), holder.get("picture_location")


def form_picture(doc, width, height):
    """`([разметка], [слова])`: картинка формы под всеми элементами; пусто, если картинки нет или она не читается."""
    block = form_picture_block(doc)
    if block is None:
        return [], []
    picture, size, location = block
    bitmap = picture_bitmap.data_uri(picture)
    if not bitmap:
        return [], []
    if picture_bitmap.is_placeholder(bitmap):
        iw, ih = picture_bitmap.size_of(bitmap)
        return [picture_bitmap.image_at(*_located(location, 0, 0, width, height, iw, ih), iw, ih, bitmap, "form-picture")], [unreadable_note("картинка формы", picture)]
    if size == 1:
        return [picture_bitmap.scaled_at(0, 0, width, height, bitmap, "nearest", "form-picture")], [FORM_PICTURE_NOTE]
    iw, ih = picture_bitmap.size_of(bitmap)
    if size == 0:
        return [picture_bitmap.image_at(*_located(location, 0, 0, width, height, iw, ih), iw, ih, bitmap, "form-picture", clip=(0, 0, width, height))], ([] if location in (None, "Center", "Right") else [FORM_PICTURE_LOCATION_NOTE])
    return [picture_bitmap.image_at(0, 0, iw, ih, bitmap, "form-picture", clip=(0, 0, width, height))], [FORM_PICTURE_MODE_NOTE]


def _located(location, x, y, w, h, iw, ih):
    """`(x, y)` картинки `iw`×`ih` в области `(x, y, w, h)` при «Реальном размере»: «Справа» — у правого края, по высоте по центру; «По центру» и по умолчанию — по центру (снято у картинки формы и картинки страницы панели)."""
    top = y + (h - ih) // 2
    return (x + w - iw if location == "Right" else x + (w - iw) // 2), top


def box_bitmap(it):
    """Картинка поля картинки (`content/u1/pictures/picture`) — `Bitmap` либо `None`."""
    return picture_bitmap.data_uri(_picture_block(it.node))


def box_borderless(it):
    """У поля картинки нет рамки (`border_type` — «Нет рамки» либо не задан): по снимкам предприятия — ни линии, ни отступа."""
    return _dig(it.node, "content", "u1", "u0", "border", "border_type") in (None, "WithoutBorder")


def box_frameless(it):
    """Поле картинки без рамки: рамка не рисуется (а с картинкой и фоном поле — единственное, что видно)."""
    return it.type == "PictureBox" and box_borderless(it)


def picture_box(doc, it, x, y, w, h, **_):
    """Картинка поля картинки внутри рамки (рамка, если задана, занимает 1 px по краю)."""
    bitmap = box_bitmap(it)
    if not bitmap:
        return []
    inset = 0 if box_borderless(it) else 1
    ix, iy, iw_, ih_ = x + inset, y + inset, max(w - 2 * inset, 0), max(h - 2 * inset, 0)
    pw, ph = picture_bitmap.size_of(bitmap)
    mode = _dig(it.node, "content", "u1", "picture_size")
    if picture_bitmap.is_placeholder(bitmap):
        mode = None                          # серый квадрат не растягивается и не мостится: он стоит на месте картинки в своём размере
    clip = (ix, iy, iw_, ih_)
    if mode == "Stretch":
        return [picture_bitmap.scaled_at(ix, iy, iw_, ih_, bitmap, "area", "box-picture")]
    if mode == "Proportionally" and pw and ph:
        scale = min(iw_ / pw, ih_ / ph)
        dw, dh = round(pw * scale), round(ph * scale)
        return [picture_bitmap.scaled_at(ix + (iw_ - dw) // 2, iy + (ih_ - dh) // 2, dw, dh, bitmap, "area", "box-picture")]
    if mode == "ByFontSize" and pw and ph:
        dh = _line_pitch(_font_of(doc, it))          # «По размеру шрифта»: высота равна шагу строк шрифта (13 px), ширина пропорционально, по центру (снято: 40×20 → 26×13)
        dw = max(round(pw * dh / ph), 1)
        return [picture_bitmap.scaled_at(ix + (iw_ - dw) // 2, iy + (ih_ - dh) // 2, dw, dh, bitmap, "area", "box-picture", clip=clip)]
    if mode == "Tile" and pw and ph:
        cols, rows = -(-iw_ // pw), -(-ih_ // ph)
        if cols * rows <= 400:
            return [picture_bitmap.image_at(ix + c * pw, iy + r * ph, pw, ph, bitmap, "box-picture", clip=clip) for r in range(rows) for c in range(cols)]
    return [picture_bitmap.image_at(ix + (iw_ - pw) // 2, iy + (ih_ - ph) // 2, pw, ph, bitmap, "box-picture", clip=clip)]


def unreadable_note(what, picture):
    """Строка `notes` о вложенной картинке, файл которой не читается: чьё место, почему, что нарисовано."""
    return f"{what}: {picture_bitmap.unreadable_reason(picture)} — на её месте серый квадрат"


def _picture_blocks(it):
    """Блоки вложенных картинок элемента: кнопка, кнопки командной панели, кнопка выбора поля, надпись, поле картинки, панель (фон страницы и значки закладок)."""
    if it.type == "Button":
        return [_dig(it.node, "content", "u1", "picture")]
    if it.type == "CommandBar":
        from . import bars
        return bars.picture_blocks(it.node)
    if it.type in ("TextBox", "ComboBox"):
        return [_dig(it.node, "content", "u2", "u0", "choice_button_picture")]
    if it.type in ("Label", "PictureBox", "Panel"):
        blocks = [_dig(it.node, "content", "u1", "pictures", "picture")]
        if it.type == "Panel":
            from . import panels
            blocks += panels.page_picture_blocks(it.node)
        return blocks
    return []


def item_notes(it):
    """Слова о картинках элемента, которых снимки не показали, и о вложенных картинках, файл которых не читается."""
    out = [unreadable_note(f"картинка элемента «{it.qualified()}»", block) for block in _picture_blocks(it) if picture_bitmap.unreadable_reason(block)]
    out += [f"картинка элемента «{it.qualified()}»: {words}" for words in dict.fromkeys(picture_bitmap.transparent_point_outside(block) for block in _picture_blocks(it) if isinstance(block, dict)) if words]
    if it.type == "Panel" and panel_bitmap(it) is not None and not picture_bitmap.is_placeholder(panel_bitmap(it)) and not _panel_measured(it):
        out.append(PANEL_PICTURE_NOTE)
    if it.type == "Button":
        picture = _dig(it.node, "content", "u1", "picture")
        if isinstance(picture, dict) and picture.get("source") not in (None, 0) and _dig(it.node, "content", "u1", "picture_location") not in (None, "Left", "Right"):
            out.append(BUTTON_PICTURE_MODE_NOTE)
    if it.type == "Label":
        picture = _dig(it.node, "content", "u1", "pictures", "picture")
        if isinstance(picture, dict) and picture.get("source") not in (None, 0) and _dig(it.node, "content", "u1", "picture_size") == "RealSize" and _dig(it.node, "content", "u1", "picture_location") == "Center":
            out.append(LABEL_PICTURE_NOTE)
    return out


def _panel_measured(it):
    """Режим картинки панели, снятый в предприятии без оговорок: «Реальный размер» (или не задан) по центру либо «Справа»."""
    return (_dig(it.node, "content", "u1", "pictures", "picture_size") in (None, "RealSize")
            and _dig(it.node, "content", "u1", "picture_location") in (None, "Center", "Right"))


def background(doc, it):
    """Цвет заливки элемента поверх картинки формы: надпись (если не прозрачная) — своим цветом фона, при «Авто» цветом формы; поле картинки и панель залиты цветом формы; иначе `None`."""
    if it.type == "PictureBox" or it.type == "Panel":
        return FORM_BG
    if it.type == "Label" and _dig(it.node, "content", "u1", "u0", "transparent") is not True:
        kind, color, _words = _back_of(it.node)
        return color if kind == "rgb" else FORM_BG
    return None


def panel_bitmap(it):
    """Картинка панели (фон страницы, `content/u1/pictures/picture`) — `Bitmap` либо `None`."""
    return picture_bitmap.data_uri(_dig(it.node, "content", "u1", "pictures", "picture"))


def panel_picture(it, box):
    """Картинка панели внутри линий страницы `box` = `(x, y, w, h)` (внутренность — на 1 px внутрь). «Реальный размер» — по центру, «Справа» — у правого края по центру;
    «Замостить» — чёрный фон страницы и одна картинка по центру, её прозрачные места — цвет формы (снято с картинкой 32 px); остальные режимы — по смыслу названия."""
    bitmap = panel_bitmap(it)
    if not bitmap:
        return []
    bx, by, bw, bh = box
    x, y, w, h = bx + 1, by + 1, max(bw - 2, 0), max(bh - 2, 0)
    pw, ph = picture_bitmap.size_of(bitmap)
    mode = _dig(it.node, "content", "u1", "pictures", "picture_size")
    where = _dig(it.node, "content", "u1", "picture_location")
    if picture_bitmap.is_placeholder(bitmap):
        mode = None
    clip = (x, y, w, h)
    if mode == "Stretch":
        return [picture_bitmap.scaled_at(x, y, w, h, bitmap, "area", "panel-picture")]
    if mode == "Proportionally" and pw and ph:
        scale = min(w / pw, h / ph)
        dw, dh = round(pw * scale), round(ph * scale)
        return [picture_bitmap.scaled_at(x + (w - dw) // 2, y + (h - dh) // 2, dw, dh, bitmap, "area", "panel-picture")]
    ix, iy = _located(where, x, y, w, h, pw, ph)
    out = []
    if mode == "Tile":
        out += [f"<rect class='panel-picture' x='{x}' y='{y}' width='{w}' height='{h}' fill='#000000'/>", f"<rect class='panel-picture' x='{ix}' y='{iy}' width='{pw}' height='{ph}' fill='{FORM_BG}'/>"]
    return out + [picture_bitmap.image_at(ix, iy, pw, ph, bitmap, "panel-picture", clip=clip)]
