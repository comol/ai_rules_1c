"""Разобранная для раскладки форма (`Form`): родители, элементы, размер; `read`."""
from .. import anchors, edit
from .model import Holder, _items_of, _panel_tabs, _min_note, _item, _rows, _inner
from .coeffs import rule_box, hidden_page
from .area import PANEL_AREA_KINDS, panel_area, _panel_unframed


class Form:
    """Разобранная для раскладки форма: родители, элементы, размер."""

    def __init__(self, doc):
        self.doc = doc
        block = doc.get("form") if isinstance(doc, dict) else None
        if not isinstance(block, dict):
            raise edit.EditError("в документе нет блока формы — раскладку считать не по чему")
        self.width, self.height = block.get("width"), block.get("height")
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (self.width,
                                                                              self.height)):
            raise edit.EditError("у формы не разобран размер (width, height) — раскладку "
                                 "считать не от чего")
        self.holders = {}
        self.items = {}
        self.raw = []
        self.min_note = (f"DPI {doc['form'].get('dpi')}" if "device_width" in doc["form"]
                         and doc["form"].get("dpi") != 96 else None)
        # Страницы формы «Сверху» с номером от 1, пока скрыты, в сеансе не перекладываются (в записи `relayout` перекладываются).
        self.tabs_area = anchors.tabs_area(doc)
        # Страницы формы «Не отображать» с номером от 1 не показаны: платформа их элементы при смене размера не раскладывает.
        block_tabs = edit.layout_block(edit.container(doc), need=False)
        self.pages_off = isinstance(block_tabs, dict) and block_tabs.get(edit.SHOW_TABS) == "DontUse"
        self._walk(edit.container(doc), 0, None, None, ("form", "container"))
        if self.tabs_area is not None:
            self._by_rules_from_area()
        self._panels_by_rules_from_area()
        for holder in self.holders.values():
            holder.inner, holder.inner_note = _inner(self, holder)

    def _walk(self, node, key, name, owner, path):
        holder = Holder()
        holder.key, holder.node, holder.name, holder.item = key, node, name, owner
        holder.area = {}
        if owner is None:
            holder.size = (self.width, self.height)
        else:
            x, y, x2, y2 = owner.box
            holder.size = (x2 - x, y2 - y)
        holder.block = edit.layout_block(node, need=False)
        holder.rows = _rows(holder.block)
        holder.children = []
        self.holders[key] = holder
        for at, element in enumerate(_items_of(node)):
            if not isinstance(element, dict):
                continue
            item = _item(element, key)
            if not item.raw:
                item.min_note = _min_note(self.min_note, element)
            item.path = path + (edit.ELEMENTS, edit.ITEMS, at)
            item.owner = owner
            item.lazy = key != 0 or self.tabs_area is not None or self.pages_off
            item.stored = None
            if item.raw:
                self.raw.append(item)
            else:
                holder.children.append(item)
                self.items[item.index] = item
            if not item.raw and _items_of(element):
                self._walk(element, item.index, item.name, item, item.path)

    def holder_of(self, item):
        return self.holders[item.holder]

    def _by_rules_from_area(self):
        """У формы с закладками «Сверху» предприятие ставит показанные элементы по правилам от области страниц `(W−2, H−20)`, а не по
        сохранённому `box`; файловый `box` остаётся в `item.stored`, по нему `problems` называет несогласованные элементы.
        """
        memo = {}
        for item in self.holders[0].children:
            item.stored = item.box
            if hidden_page(item):
                continue
            box = _whole_box(rule_box(self, item, self.tabs_area, memo))
            if box != item.box:
                item.box = box

    def _panels_by_rules_from_area(self):
        """Вложенные элементы панели без рамки вида «Сверху», «Сверху (с прокруткой)», «Снизу», «Слева (горизонтально)» или «Не отображать»
        (DPI 96) предприятие ставит по правилам от края страницы, равного видимой области панели (`panel_area`), а не по `box` и не от
        направляющих края страницы: у страницы, чья направляющая дальше области, `box` согласован с направляющей, а при том же размере
        панели предприятие ставит элементы иначе (`Размеры` на 135 px). Область, которой не проверяли (картинка у закладки у «Сверху (с
        прокруткой)» и «Снизу», подпись «Слева», не измеренная шрифтом), правилом не охвачена (`panel_not_checked`): прежнее `box +
        рост`. Файловый `box` остаётся в `item.stored`; пока размер
        панели равен проектному, `box + k·рост` даёт `rule_box(область сейчас)`. `Holder.size` остаётся размером панели в файле (как
        у формы «Сверху»): рост вложенных считается от него.
        """
        if self.min_note:
            return
        for holder in list(self.holders.values()):
            owner = holder.item
            if owner is None:
                continue
            kind = _panel_tabs(owner)
            if kind not in PANEL_AREA_KINDS or not _panel_unframed(owner):
                continue
            edge, _why = panel_area(self.doc, owner, holder.size)
            if edge is None:
                continue
            memo = {}
            for child in holder.children:
                holder.area[child.page] = edge
                if child.stored is None:
                    child.stored = child.box
                box = _whole_box(rule_box(self, child, edge, memo))
                if box != child.box:
                    child.box = box
                child.from_area = True


def _whole_box(box):
    """Края по правилам с целыми значениями там, где они целые: `rule_box` отдаёт `float` (`77.0`), а он утекал в тексты отчётов и в
    запись координат (`typed.encode` дробное не принимает). Дробное (середина нечётной ширины) остаётся как есть."""
    return tuple(int(v) if isinstance(v, float) and v == int(v) else v for v in box)


def read(doc):
    """Форма для раскладки: `Form`. Отказ словами, если контейнер или размер не разобраны."""
    return Form(doc)
