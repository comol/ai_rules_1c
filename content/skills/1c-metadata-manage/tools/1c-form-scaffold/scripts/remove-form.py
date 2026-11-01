#!/usr/bin/env python3
# remove-form v1.11 — Remove form from 1C object
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills, synced at
#         2e75b0f483eb020e9f09562d1a7be1982bc5ac6e — the same upstream state the
#         vendored remove-form.ps1 was synced from.
# Licence: MIT, Copyright (c) 2025-2026 Nick Shirokov. Full notice and permission
#          text: ../../../NOTICE.md (installed as
#          skills/1c-metadata-manage/NOTICE.md).
# Local: hardening on top of upstream v1.4, mirroring remove-form.ps1's contract.
#        Upstream deletes the form files first and parses the root XML afterwards,
#        accepts any string as a name, and has no confirmation gate. Here:
#          * names must be 1C identifiers and every resolved path must stay inside
#            the object's own Forms directory (no traversal, no symlink escape);
#          * -DryRun prints the plan and changes nothing; a real deletion needs
#            -Force and otherwise exits 2 before any mutation;
#          * the mutation itself is a bounded transaction — deletions are renames
#            into a quarantine on the same filesystem and every step has an undo,
#            so a failure anywhere restores the original tree.
#        From upstream 1.5–1.11 only the reference check of 93d9511a is taken (the
#        full reference "<Kind>.<Object>.Form.<Name>" instead of the "Form.<Name>"
#        tail, a scan of the rest of the configuration) and the case-insensitive
#        parameter names (d325a3d5). Upstream's -Force also cleans foreign
#        references; here -Force stays the deletion gate and the cleaning is the
#        separate -CleanReferences switch, inside the same transaction.

import argparse
import os
import re
import shutil
import stat
import sys

from lxml import etree

NSMAP = {"md": "http://v8.1c.ru/8.3/MDClasses"}

QUARANTINE_NAME = ".remove-form-quarantine"

# A 1C metadata identifier: a Latin or Cyrillic letter or underscore, then letters,
# digits and underscores, up to the platform's 128-character limit. Deliberately an
# allowlist - it rejects path separators, `..`, drive letters, UNC prefixes, trailing
# dots and spaces (which Windows silently strips), embedded NULs, and look-alike
# letters from other scripts.
CYRILLIC = "А-яЁё"
IDENTIFIER_RE = re.compile(
    rf"^[A-Za-z_{CYRILLIC}][0-9A-Za-z_{CYRILLIC}]{{0,127}}$")


# Case-insensitive parameter names, as PowerShell binds them (upstream d325a3d5).
def ci_parse_args(parser, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    names = {s.lower(): s for a in parser._actions for s in a.option_strings}
    for i, tok in enumerate(argv):
        if tok.startswith('-') and tok.lower() in names:
            argv[i] = names[tok.lower()]
    return parser.parse_args(argv)


def die(message, code):
    print(message, file=sys.stderr)
    sys.exit(code)


def require_identifier(value, what):
    """Refuse anything that is not a plain 1C identifier, before any path is built."""
    if not IDENTIFIER_RE.match(value or ""):
        die(f"Недопустимое имя {what}: {value!r}. Ожидается идентификатор 1С "
            f"(латиница или кириллица, цифры и подчёркивание, не начинается с цифры, "
            f"до 128 символов).", 2)


def is_link_or_reparse(path):
    """True for a POSIX symlink and for a Windows symlink / junction / reparse point."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse)


def require_inside(path, parent, what):
    """The resolved *path* must be a direct child of the resolved *parent*.

    realpath() collapses `..` and follows symlinks, so this catches both a name that
    escaped validation and a directory that was symlinked out of the tree. The
    explicit link check refuses the remaining case - a link that still resolves
    inside, where deleting the link is not what the caller asked for.

    On its own this is *not* containment: it compares a path against its immediate
    parent, so when that parent is itself a link both sides resolve into the same
    foreign directory and the check passes. require_chain() below anchors the whole
    chain at the one directory the caller actually vouched for."""
    real_parent = os.path.realpath(parent)
    real_path = os.path.realpath(path)
    if os.path.dirname(real_path) != real_parent:
        die(f"Путь {what} выходит за пределы каталога {real_parent}: {real_path}. "
            f"Операция отклонена.", 2)
    if is_link_or_reparse(path):
        die(f"Путь {what} является символической ссылкой / точкой повторной обработки: "
            f"{path}. Удаление отклонено — проверьте выгрузку вручную.", 2)


def require_chain(root, path, what):
    """Every component between the trusted *root* and *path* must be a real directory.

    -SrcDir is the only path the caller vouched for; everything under it is derived.
    A link or reparse point anywhere on the way - the object directory as much as
    Forms/ or the form itself - silently redirects the whole subtree elsewhere, and a
    parent-relative check cannot see it because it resolves both sides through the
    same link. So walk the chain from the trusted root down and refuse a redirect on
    any component, before the first mutation."""
    root_full = os.path.abspath(root)
    full = os.path.abspath(path)
    chain = []
    current = full
    while os.path.normcase(current) != os.path.normcase(root_full):
        chain.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            die(f"Путь {what} выходит за пределы каталога {root_full}: {full}. "
                f"Операция отклонена.", 2)
        current = parent
    for component in chain:
        if is_link_or_reparse(component):
            die(f"Путь {what} проходит через символическую ссылку / точку повторной "
                f"обработки: {component}. Удаление отклонено — проверьте выгрузку "
                f"вручную.", 2)


class _Step:
    """One reversible step of the transaction.

    ``undo`` puts the original state back. ``recovery`` is the pair
    ``(copy inside the quarantine, path it belongs at)``, and ``outstanding()``
    answers the only question a rollback has to get right: is that copy still the
    *only* copy of this payload? For a parked file the answer is read off the
    filesystem - it is outstanding for exactly as long as it is still sitting in the
    quarantine - so no bookkeeping slip can make the quarantine look disposable
    while it is not."""

    def __init__(self, what, undo, recovery, still_needed):
        self.what = what
        self.undo = undo
        self.recovery = recovery
        self._still_needed = still_needed
        self.restored = False

    def outstanding(self):
        return self._still_needed(self)


class RollbackReport:
    """What the rollback managed to undo, and what it deliberately kept.

    ``outstanding`` lists ``(copy in the quarantine, path it belongs at)`` for every
    payload the rollback could not put back. While it is non-empty the quarantine is
    the only copy of those files, so it must survive whatever else went wrong."""

    def __init__(self, problems, outstanding, quarantine_kept):
        self.problems = problems
        self.outstanding = outstanding
        self.quarantine_kept = quarantine_kept


class Transaction:
    """Bounded filesystem transaction with an explicit undo stack.

    Every step registers its undo *before* it runs, so a failure at any point
    restores the original bytes and the original existence of every touched path.
    Deletions are renames into a quarantine directory on the same filesystem: a
    rename is atomic and reversible, unlike a recursive delete that can stop
    half-way. The quarantine is discarded once the whole transaction has committed -
    or once a rollback has verifiably put every payload back, and not before.

    Discarding it is deliberately *not* one of the undo steps. As a step it was the
    oldest one and therefore ran last, i.e. after earlier restores had already
    failed: the tree kept the hole, and the only surviving copy of the deleted files
    was deleted along with the quarantine the error message was pointing at."""

    def __init__(self, quarantine):
        self.quarantine = quarantine
        self.steps = []
        self.started = False

    def begin(self):
        # A leftover quarantine means a previous run died between rollback steps.
        # Refuse rather than write into it: its contents are the only copy left.
        if os.path.exists(self.quarantine):
            die(f"Найден каталог карантина от прерванного запуска: {self.quarantine}. "
                f"Проверьте его содержимое и удалите вручную, затем повторите операцию.", 2)
        os.makedirs(self.quarantine)
        self.started = True

    def backup_file(self, path, slot="root-backup.xml"):
        """Keep a copy so a later step can restore the original bytes."""
        backup = os.path.join(self.quarantine, slot)
        shutil.copyfile(path, backup)

        def restore():
            shutil.copyfile(backup, path)

        # A copy, not a move: it stops being the only copy once it is back in place,
        # so its own success flag is what decides - and a failed copy leaves it set.
        self.steps.append(_Step(f"restore {path}", restore, (backup, path),
                                lambda step: not step.restored))
        return backup

    def move_away(self, path, slot):
        """Delete by renaming into the quarantine - reversible and never partial."""
        parked = os.path.join(self.quarantine, slot)
        os.replace(path, parked)
        self.steps.append(_Step(f"put back {path}", lambda: os.replace(parked, path),
                                (parked, path),
                                lambda step: os.path.exists(step.recovery[0])))

    def replace_file(self, path, payload, slot="root-new.xml"):
        """Swap in new bytes atomically; the undo is the backup taken earlier."""
        staged = os.path.join(self.quarantine, slot)
        with open(staged, "wb") as handle:
            handle.write(payload)
        os.replace(staged, path)

    def commit(self):
        """Point of no return: drop the quarantine, and with it the deleted files."""
        self.steps = []
        shutil.rmtree(self.quarantine)
        self.started = False

    def rollback(self):
        """Undo every recorded step, newest first, then decide the quarantine's fate.

        The quarantine goes only when nothing is outstanding: no payload is still
        parked in it and every restore reported success. Otherwise it stays, and the
        caller is told which file in it belongs where."""
        problems = []
        for step in reversed(self.steps):
            try:
                step.undo()
                step.restored = True
            except Exception as exc:  # noqa: BLE001 - keep undoing the rest
                problems.append(f"{step.what}: {exc}")
        outstanding = [step.recovery for step in self.steps if step.outstanding()]
        self.steps = []
        self.started = False
        if outstanding:
            return RollbackReport(problems, outstanding, True)
        try:
            shutil.rmtree(self.quarantine)
        except OSError as exc:
            problems.append(f"remove quarantine {self.quarantine}: {exc}")
            return RollbackReport(problems, [], True)
        return RollbackReport(problems, [], False)


def _detect_xml_style(path):
    """Стиль существующего файла для round-trip-сохранения: BOM / EOL / регистр encoding /
    финальный перенос. None → файл новый (сохранить текущее поведение)."""
    try:
        raw = open(path, "rb").read()
    except OSError:
        return None
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    crlf = b"\r\n" in body
    m = re.search(rb'encoding="([^"]+)"', body[:200])
    enc = m.group(1).decode("ascii") if m else "utf-8"
    final_nl = body.endswith(b"\n")
    return {"bom": bom, "crlf": crlf, "enc": enc, "final_nl": final_nl}


def _finalize_xml_bytes(xml_bytes, style):
    """Привести сериализованные байты к стилю оригинала (или к дефолту, если style is None)."""
    enc_decl = style["enc"] if style else "utf-8"
    xml_bytes = xml_bytes.replace(
        b"<?xml version='1.0' encoding='UTF-8'?>",
        b'<?xml version="1.0" encoding="' + enc_decl.encode("ascii") + b'"?>')
    # Канонизировать переносы к LF (убирает &#13; от \r в tail'ах)
    xml_bytes = (xml_bytes.replace(b"&#13;\n", b"\n").replace(b"&#13;", b"")
                 .replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    # Финальный перенос — как в оригинале (новый файл → есть)
    want_final_nl = style["final_nl"] if style else True
    xml_bytes = xml_bytes.rstrip(b"\n")
    if want_final_nl:
        xml_bytes += b"\n"
    # EOL — как в оригинале (новый файл → LF, текущее поведение)
    if style and style["crlf"]:
        xml_bytes = xml_bytes.replace(b"\n", b"\r\n")
    return xml_bytes


def render_xml_with_bom(tree, path):
    """Serialize the tree into the bytes that would replace *path*, preserving its
    BOM / EOL / encoding-case / final-newline. Split out of the upstream
    save_xml_with_bom so the safety gate can render before committing anything."""
    style = _detect_xml_style(path)
    xml_bytes = etree.tostring(tree, xml_declaration=True, encoding="UTF-8")
    xml_bytes = _finalize_xml_bytes(xml_bytes, style)
    if style is None or style["bom"]:
        xml_bytes = b"\xef\xbb\xbf" + xml_bytes
    return xml_bytes


def drop_element_keeping_indent(node):
    """Remove *node* without disturbing the pretty-printing around it.

    lxml keeps the whitespace that follows an element in that element's ``tail``,
    and the whitespace before the first child in the parent's ``text``. Removing an
    element therefore also removes the indentation of the *next* sibling unless the
    tails are rearranged first:

      * middle / first element - dropping the node and its own tail is exactly
        right, the survivors keep their own indentation;
      * last element - its tail is the parent's closing indentation, so hand it to
        the previous sibling;
      * only element - the block becomes empty, so drop the parent's text as well
        and let it serialize as ``<ChildObjects/>``, the way Configurator writes it.
    """
    parent = node.getparent()
    if node.getnext() is None:
        previous = node.getprevious()
        if previous is not None:
            previous.tail = node.tail
        else:
            parent.text = None
    parent.remove(node)


def remove_node_with_indent(node):
    """Remove an element with the whitespace in front of it; an emptied container
    becomes self-closing. Mirror of Remove-NodeWithIndent in remove-form.ps1."""
    parent = node.getparent()
    if parent is None:
        return
    prev = node.getprevious()
    if prev is not None:
        prev.tail = node.tail
    else:
        parent.text = node.tail
    parent.remove(node)
    if len(parent) == 0 and not (parent.text or "").strip():
        parent.text = None


def clear_form_refs(tree, ref):
    """Clear every reference to the form, matched on the FULL reference (upstream
    93d9511a). The old tail match on ``Form.<Name>`` also blanked
    ``DocumentJournal.J.Form.<Name>`` and ``CommonForm.<Name>`` slots. The canonical
    "not set" depends on the file: an empty slot in an object / Configuration.xml,
    an absent property inside Ext/Form.xml, and a home-page Item is cut out whole.
    Returns the touched slots, for the plan. Mirror of Clear-FormRefs in PS."""
    root = tree.getroot()
    is_form_file = etree.QName(root).localname == "Form"
    touched = []
    ref_lc = ref.lower()
    for el in list(root.iter()):
        if not isinstance(el.tag, str) or len(el) > 0:   # leaves only
            continue
        if (el.text or "").strip().lower() != ref_lc:     # case-insensitive, like PS -ne
            continue
        ln = etree.QName(el).localname
        parent = el.getparent()
        if ln == "Form" and parent is not None and etree.QName(parent).localname == "Item":
            touched.append("remove Item/Form")
            remove_node_with_indent(parent)
        elif is_form_file:
            touched.append(f"remove {ln}")
            remove_node_with_indent(el)
        else:
            touched.append(f"clear {ln}")
            el.text = None                                # <Tag/>, never <Tag></Tag>
    return touched


def find_foreign_references(scan_root, skip_files, skip_dirs, form_ref):
    """``[{path, rel, tags}]`` of every other XML under *scan_root* that names the
    form by its full reference. Read-only; ordinal order, as the PS port sorts."""
    pattern = re.compile(r"<([A-Za-z0-9_.]+)>" + re.escape(form_ref) + r"</")
    skip_files = {os.path.normcase(f) for f in skip_files}
    skip_dirs = [os.path.normcase(d.rstrip("\\/") + os.sep) for d in skip_dirs]
    found = []
    candidates = []
    for dirpath, _dirnames, filenames in os.walk(scan_root):
        for fn in filenames:
            if fn.lower().endswith(".xml"):
                candidates.append(os.path.join(dirpath, fn))
    for fp in sorted(candidates):
        norm = os.path.normcase(fp)
        if norm in skip_files or any(norm.startswith(d) for d in skip_dirs):
            continue
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as handle:
            content = handle.read()
        if form_ref not in content:
            continue
        tags = [m.group(1) for m in pattern.finditer(content)]
        if tags:
            found.append({"path": fp, "rel": os.path.relpath(fp, scan_root), "tags": tags,
                          "tree": None, "touched": [], "payload": None})
    return found


def main():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Remove form from 1C object", allow_abbrev=False)
    parser.add_argument("-ObjectName", "-ProcessorName", required=True)
    parser.add_argument("-FormName", required=True)
    parser.add_argument("-SrcDir", default="src")
    # Local: same safety switches as remove-form.ps1.
    parser.add_argument("-DryRun", action="store_true",
                        help="Print the full plan and change nothing.")
    parser.add_argument("-Force", action="store_true",
                        help="Authorize the deletion. Without it the run stops before any mutation.")
    parser.add_argument("-CleanReferences", action="store_true",
                        help="Also clear references to the form in other files of the configuration.")
    args = ci_parse_args(parser)

    # --- Input validation: before a single path is built ---

    require_identifier(args.ObjectName, "объекта (-ObjectName)")
    require_identifier(args.FormName, "формы (-FormName)")
    object_name = args.ObjectName
    form_name = args.FormName
    src_dir = args.SrcDir

    # --- Checks ---

    root_xml_path = os.path.join(src_dir, f"{object_name}.xml")
    if not os.path.exists(root_xml_path):
        die(f"Корневой файл обработки не найден: {root_xml_path}", 1)

    processor_dir = os.path.join(src_dir, object_name)
    forms_dir = os.path.join(processor_dir, "Forms")
    form_meta_path = os.path.join(forms_dir, f"{form_name}.xml")
    form_dir = os.path.join(forms_dir, form_name)

    # Containment: every path this run may touch has to resolve inside the object's
    # own directory, whatever the filesystem has done with links in between.
    require_inside(root_xml_path, src_dir, "корневого XML")
    require_inside(processor_dir, src_dir, "каталога объекта")
    require_inside(forms_dir, processor_dir, "каталога Forms")
    require_inside(form_meta_path, forms_dir, "метаданных формы")
    require_inside(form_dir, forms_dir, "каталога формы")
    for target, label in ((root_xml_path, "корневого XML"),
                          (processor_dir, "каталога объекта"),
                          (forms_dir, "каталога Forms"),
                          (form_meta_path, "метаданных формы"),
                          (form_dir, "каталога формы")):
        require_chain(src_dir, target, label)

    if not os.path.exists(form_meta_path):
        die(f"Метаданные формы не найдены: {form_meta_path}", 1)

    # --- Preflight: parse and modify XML in memory before deleting anything ---

    root_xml_full = os.path.abspath(root_xml_path)
    parser_xml = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(root_xml_full, parser_xml)
    root = tree.getroot()

    # Kind and name of the object: the full form reference is built from them.
    type_node = next((c for c in root if isinstance(c.tag, str)), None)
    if type_node is None:
        die(f"Не удалось определить вид объекта в {root_xml_path}", 1)
    md_type = etree.QName(type_node).localname
    name_node = type_node.find("md:Properties/md:Name", NSMAP)
    obj_meta_name = (name_node.text or "").strip() if name_node is not None else ""
    if not obj_meta_name:
        obj_meta_name = object_name
    form_ref = f"{md_type}.{obj_meta_name}.Form.{form_name}"

    # Remove <Form>FormName</Form> from ChildObjects
    form_node_found = False
    for node in root.findall(".//md:ChildObjects/md:Form", NSMAP):
        if node.text and node.text.strip() == form_name:
            form_node_found = True
            drop_element_keeping_indent(node)
            break
    if not form_node_found:
        die(f"Form is not registered in ChildObjects: {form_name}", 1)

    # Clear every slot of the object itself that points to this form: form-add writes
    # the purpose-specific Default*/Auxiliary*Form, attributes may carry a ChoiceForm.
    own_touched = clear_form_refs(tree, form_ref)

    # --- References from the rest of the configuration (upstream 93d9511a) ---
    #
    # The configuration root is -SrcDir or one of its three parents that holds
    # Configuration.xml. Without one (an external data processor, a partial tree)
    # only the object's own directory is scanned - its other forms can still point here.
    src_full = os.path.abspath(src_dir).rstrip("\\/")
    scan_root = None
    probe = src_full
    for _ in range(4):
        if os.path.exists(os.path.join(probe, "Configuration.xml")):
            scan_root = probe
            break
        up = os.path.dirname(probe)
        if not up or up == probe:
            break
        probe = up
    config_found = scan_root is not None
    if scan_root is None:
        scan_root = os.path.abspath(processor_dir).rstrip("\\/")

    foreign = []
    if os.path.isdir(scan_root):
        foreign = find_foreign_references(
            scan_root,
            [os.path.abspath(root_xml_path), os.path.abspath(form_meta_path)],
            [os.path.abspath(form_dir), os.path.join(src_full, QUARANTINE_NAME)],
            form_ref)

    if args.CleanReferences:
        for ref in foreign:
            # Every file this run writes must be reached without a link on the way.
            require_chain(scan_root, ref["path"], f"файла со ссылкой ({ref['rel']})")
            ref_tree = etree.parse(ref["path"], parser_xml)
            ref["touched"] = clear_form_refs(ref_tree, form_ref)
            if not ref["touched"]:
                die(f"Ссылку на {form_ref} в {ref['rel']} нельзя очистить автоматически "
                    f"(она не в отдельном свойстве). Уберите её вручную и повторите.", 1)
            ref["tree"] = ref_tree

    # Render now: a serialization failure must surface before anything is deleted.
    payload = render_xml_with_bom(tree, root_xml_full)
    for ref in foreign:
        if ref["tree"] is not None:
            ref["payload"] = render_xml_with_bom(ref["tree"], ref["path"])

    # --- Safety gate ---

    print("Planned changes:")
    print(f"  modify: {root_xml_path} (remove ChildObjects/Form '{form_name}')")
    for step in own_touched:
        print(f"  modify: {root_xml_path} ({step})")
    print(f"  delete: {form_meta_path}")
    if os.path.isdir(form_dir):
        print(f"  delete: {form_dir} (recursive)")
    if foreign:
        print(f"References to {form_ref} from other files: {len(foreign)}")
        for ref in foreign:
            if args.CleanReferences:
                for step in sorted(set(ref["touched"]), key=str.lower):
                    print(f"  modify: {os.path.join(scan_root, ref['rel'])} ({step})")
            else:
                tags = ", ".join(sorted(set(ref["tags"]), key=str.lower))
                print(f"  reference: {os.path.join(scan_root, ref['rel'])} <{tags}>")
        if not args.CleanReferences:
            print("  These references block the removal: clear them by hand, or add "
                  "-CleanReferences to clear them in the same transaction.")
    if not config_found:
        print(f"[WARN] Configuration.xml not found within three levels above -SrcDir: "
              f"only {scan_root} was checked for references.")

    if args.DryRun:
        print("[DRY-RUN] No files changed.")
        sys.exit(0)
    if not args.Force:
        die("Removal requires explicit -Force. Run with -DryRun first to review the plan.", 2)
    if foreign and not args.CleanReferences:
        die(f"Форма {form_ref} используется в других файлах ({len(foreign)}) — удаление "
            f"остановлено, ничего не изменено. Уберите ссылки или повторите с "
            f"-Force -CleanReferences.", 2)

    # --- Mutation: one bounded transaction, rolled back as a whole on any failure ---

    form_dir_existed = os.path.isdir(form_dir)
    transaction = Transaction(os.path.join(os.path.abspath(src_dir), QUARANTINE_NAME))
    transaction.begin()
    try:
        transaction.backup_file(root_xml_full)
        if form_dir_existed:
            transaction.move_away(form_dir, "form-dir")
        transaction.move_away(form_meta_path, "form-meta.xml")
        transaction.replace_file(root_xml_full, payload)
        # -CleanReferences: the other files, each backed up first so the rollback
        # can put its original bytes back.
        index = 0
        for ref in foreign:
            if ref["payload"] is None:
                continue
            index += 1
            transaction.backup_file(ref["path"], f"ref-backup-{index}.xml")
            transaction.replace_file(ref["path"], ref["payload"], f"ref-new-{index}.xml")
    except BaseException as exc:  # noqa: BLE001 - every failure mode rolls back
        report = transaction.rollback()
        # The primary failure first and unmasked - it is what has to be acted on.
        print(f"[error] Операция прервана: {exc}", file=sys.stderr)
        if report.outstanding or report.problems:
            print("[error] Откат (rollback) выполнен не полностью.", file=sys.stderr)
            for problem in report.problems:
                print(f"  - не удалось: {problem}", file=sys.stderr)
            if report.outstanding:
                print(f"[error] Карантин {transaction.quarantine} НЕ удалён: в нём "
                      f"единственные копии перечисленного ниже. Восстановите вручную:",
                      file=sys.stderr)
                for parked, original in report.outstanding:
                    print(f"  - {parked} -> {original}", file=sys.stderr)
        elif report.quarantine_kept:
            print("[error] Откат (rollback) выполнен, дерево исходников не изменено, но "
                  f"каталог карантина остался — удалите вручную: {transaction.quarantine}",
                  file=sys.stderr)
        else:
            print("[error] Откат (rollback) выполнен, дерево исходников не изменено.", file=sys.stderr)
        sys.exit(1)

    try:
        transaction.commit()
    except BaseException as exc:  # noqa: BLE001 - the tree is already correct here
        print(f"[error] Форма удалена, но каталог карантина не удалён ({exc}). "
              f"Удалите вручную: {transaction.quarantine}", file=sys.stderr)
        sys.exit(1)

    if form_dir_existed:
        print(f"[OK] Removed directory: {form_dir}")
    print(f"[OK] Removed file: {form_meta_path}")
    print(f"[OK] Form {form_name} removed from {root_xml_path}")
    for ref in foreign:
        if ref["payload"] is not None:
            print(f"[OK] Cleared reference in {ref['rel']}: "
                  f"{', '.join(sorted(set(ref['touched']), key=str.lower))}")


if __name__ == "__main__":
    main()
