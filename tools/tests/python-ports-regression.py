#!/usr/bin/env python3
"""Behaviour regressions for the Python runtime of the 1c-metadata-manage skill.

The toolchain of that skill is PowerShell-only, so a Linux / macOS install
receives tools it cannot execute. The fix is to ship each tool twice - a
PowerShell script for Windows and a Python port next to it - vendored from
Nikolay-Shirokov/cc-1c-skills (MIT) at the commit the PowerShell family was
synced from: ecd289fe11733028d87b55284ea9fb5feff8f513.

This file is the regression net for that runtime. It currently covers the first
ported tool, ``remove-form`` - a tool that deletes files, so its contract is
pinned rather than trusted. Upstream rejects ``-DryRun`` as an unknown argument,
deletes without ``-Force``, accepts any string as a name, and deletes the form
files *before* parsing the root XML. Pinned here, for the Python port and, where
the behaviour is shared, for ``remove-form.ps1`` too:

  1. ``-DryRun`` prints the full removal / reference-cleanup plan and performs
     zero filesystem mutation.
  2. A real deletion without ``-Force`` exits 2 before every mutation;
     ``-Force`` authorizes the deletion of the form itself, and the reference
     cleanup stays explicit - every cleared slot is named in the plan.
  3. Input safety: names must be 1C identifiers and every resolved path must
     stay inside the object's own ``Forms`` directory. Traversal, separators,
     absolute and UNC paths, trailing dots / spaces, look-alike letters and
     symlinked targets are refused with exit 2 before any mutation.
  4. Transactionality: a fault injected at *any* mutation step leaves the tree
     either fully original or fully final, never in between, and leaves no
     quarantine behind; a rollback that cannot complete says so instead of
     reporting success; a quarantine left by an interrupted run stops the next
     run rather than being written into.
  5. XML style: the exact ``ChildObjects`` indentation, BOM, EOL, encoding case
     and final newline of the original file survive the edit.
  6. PowerShell / Python parity of all of the above, where a PowerShell host is
     available.
  7. Licensing and packaging - the upstream MIT notice is present, distributable
     and installed; the installer ships the Python entry point, tracks both in
     ``.ai-rules.json``, and the installed copies match the source byte for byte.

The remaining metadata tools are ported in follow-up units; add their cases
here as they land.

Cases materialize their own fixtures into a temp directory (exact bytes: BOM and
chosen EOL) and assert on the raw bytes of the result, so no 1C platform is
needed. Fixtures under ``fixtures/`` are stored LF-only; the runner applies the
target EOL itself and is therefore immune to the checkout EOL policy
(``core.autocrlf``) of the machine it runs on. Nothing here reaches the network.

Usage::

    python -B tools/tests/python-ports-regression.py
    python -B tools/tests/python-ports-regression.py --python-only
    python -B tools/tests/python-ports-regression.py --filter 'remove-form*'
    python -B tools/tests/python-ports-regression.py --keep-work-dir
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import fnmatch
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import uuid
from collections import OrderedDict
from xml.etree import ElementTree

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TOOLS_DIR = os.path.join(REPO_ROOT, "content", "skills", "1c-metadata-manage", "tools")

REMOVE_FORM_PY = os.path.join(TOOLS_DIR, "1c-form-scaffold", "scripts", "remove-form.py")
REMOVE_FORM_PS1 = os.path.join(TOOLS_DIR, "1c-form-scaffold", "scripts", "remove-form.ps1")
FORM_COMPILE_PY = os.path.join(TOOLS_DIR, "1c-form-compile", "scripts", "form-compile.py")
FORM_COMPILE_PS1 = os.path.join(TOOLS_DIR, "1c-form-compile", "scripts", "form-compile.ps1")
FORM_ADD_PY = os.path.join(TOOLS_DIR, "1c-form-scaffold", "scripts", "form-add.py")
FORM_ADD_PS1 = os.path.join(TOOLS_DIR, "1c-form-scaffold", "scripts", "form-add.ps1")
META_EDIT_PY = os.path.join(TOOLS_DIR, "1c-meta-edit", "scripts", "meta-edit.py")
META_EDIT_PS1 = os.path.join(TOOLS_DIR, "1c-meta-edit", "scripts", "meta-edit.ps1")
META_VALIDATE_PY = os.path.join(TOOLS_DIR, "1c-meta-validate", "scripts", "meta-validate.py")
META_VALIDATE_PS1 = os.path.join(TOOLS_DIR, "1c-meta-validate", "scripts", "meta-validate.ps1")
DEV_ENV_PY = os.path.join(TOOLS_DIR, "_common", "dev_env.py")


# ---------------------------------------------------------------- infrastructure

class CaseFailure(Exception):
    pass


class CaseSkipped(Exception):
    """Raised when a case needs a runtime the machine does not have (e.g. a
    PowerShell host on a bare Linux container). Reported, never fatal."""


CASES: list[tuple[str, "callable", bool]] = []


def case(name, needs_powershell=False):
    """Register a case. ``needs_powershell`` marks the ones a Python-only host
    (the Linux CI job) has to skip - the PowerShell parity and packaging gates
    belong to the Windows job."""

    def wrap(fn):
        CASES.append((name, fn, needs_powershell))
        return fn

    return wrap


def fail(message):
    raise CaseFailure(message)


def assert_true(condition, message):
    if not condition:
        fail(message)


def assert_equal(expected, actual, what):
    if str(expected) != str(actual):
        fail(f"{what} : expected [{expected}], got [{actual}]")


def file_facts(path):
    """Byte-level properties of a file: BOM, EOL mix, text, lines."""
    with open(path, "rb") as handle:
        raw = handle.read()
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    body = raw[3:] if has_bom else raw
    text = body.decode("utf-8")
    crlf = text.count("\r\n")
    lf = text.count("\n")
    return {
        "path": path,
        "bom": has_bom,
        "text": text,
        "crlf": crlf,
        "lf": lf,
        "lone_lf": lf - crlf,
        "lines": re.split(r"\r\n|\n", text),
        "sha": base64.b64encode(raw).decode("ascii"),
    }


def copy_fixture(name, dest, eol="\n"):
    """Materialize a fixture tree into *dest* with the requested EOL and a BOM."""
    src = os.path.join(FIXTURES_DIR, name)
    if not os.path.isdir(src):
        raise CaseFailure(f"Fixture not found: {src}")
    os.makedirs(dest, exist_ok=True)
    for root, _dirs, files in os.walk(src):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, src)
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if fname.endswith(".bin"):
                shutil.copyfile(full, out)
                continue
            with open(full, "rb") as handle:
                raw = handle.read()
            if raw[:3] == b"\xef\xbb\xbf":
                raw = raw[3:]
            text = raw.decode("utf-8").replace("\r\n", "\n")
            if eol != "\n":
                text = text.replace("\n", eol)
            with open(out, "wb") as handle:
                handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))


def make_directory_link(target, link):
    """A directory symlink, or a junction when the host will not grant one.

    ``mklink /J`` needs no privilege at all, so a Windows box without Developer
    Mode still runs the containment cases instead of skipping them - and a
    junction is exactly the reparse point the tool has to refuse."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError) as exc:
        if os.name != "nt":
            raise CaseSkipped(f"directory links unavailable on this host ({exc})")
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                               capture_output=True, text=True)
    if completed.returncode != 0 or not os.path.exists(link):
        raise CaseSkipped(f"no directory link available on this host: "
                          f"{(completed.stderr or completed.stdout).strip()}")
    return "junction"


def snapshot_tree(root):
    """Path -> raw bytes for every file under *root*. Used for no-mutation asserts."""
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            full = os.path.join(dirpath, fname)
            with open(full, "rb") as handle:
                out[os.path.relpath(full, root).replace("\\", "/")] = handle.read()
    return out


def find_powershell_host():
    """`pwsh` on any OS, Windows PowerShell as the fallback. None when neither exists."""
    for exe in ("pwsh", "powershell.exe" if os.name == "nt" else None):
        if exe and shutil.which(exe):
            return exe
    return None


def run_powershell_tool(script, tool_args, work_dir):
    host = find_powershell_host()
    if not host:
        raise CaseSkipped("no PowerShell host on PATH (pwsh / powershell.exe)")
    proc = subprocess.run(
        [host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *tool_args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout or "", "stderr": proc.stderr or ""}


def run_python_tool(script, tool_args, work_dir):
    proc = subprocess.run(
        [sys.executable, "-B", script, *tool_args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout or "", "stderr": proc.stderr or ""}


def load_tool_module(script):
    """Import a tool script as a module so a case can inject a fault into a
    specific filesystem call. Kept out of the tool itself on purpose: shipping a
    fault-injection hook in a script that deletes files is its own hazard."""
    spec = importlib.util.spec_from_file_location("_1c_tool_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_tool_in_process(script, tool_args, work_dir, faults=None):
    """Run ``main()`` in-process with ``faults`` patched over ``os`` / ``shutil``.

    ``faults`` maps a callable name (``os.replace``, ``os.remove``,
    ``shutil.copyfile``, ``shutil.rmtree``) to a predicate taking the call's
    positional args; when the predicate is true the call raises OSError instead
    of running. Returns the same shape as the subprocess runners plus the raised
    exception, if any."""
    faults = faults or {}
    module = load_tool_module(script)
    originals = {}
    targets = {"os.replace": os, "os.remove": os, "os.rmdir": os,
               "shutil.copyfile": shutil, "shutil.rmtree": shutil, "shutil.move": shutil}

    def patch(dotted, predicate):
        holder = targets[dotted]
        attr = dotted.split(".", 1)[1]
        real = getattr(holder, attr)
        originals[dotted] = (holder, attr, real)

        def wrapper(*call_args, **call_kwargs):
            if predicate(*call_args):
                raise OSError(5, f"injected failure in {dotted}")
            return real(*call_args, **call_kwargs)

        setattr(holder, attr, wrapper)

    for dotted, predicate in faults.items():
        patch(dotted, predicate)

    out, err = io.StringIO(), io.StringIO()
    exit_code, raised = 0, None
    prev_argv, prev_cwd = sys.argv, os.getcwd()
    try:
        sys.argv = [os.path.basename(script), *tool_args]
        os.chdir(work_dir)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                module.main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
            except BaseException as exc:  # noqa: BLE001 - the case inspects it
                raised = exc
                exit_code = 1
    finally:
        os.chdir(prev_cwd)
        sys.argv = prev_argv
        for holder, attr, real in originals.values():
            setattr(holder, attr, real)
    return {"exit_code": exit_code, "stdout": out.getvalue(), "stderr": err.getvalue(), "raised": raised}


def assert_tree_identical(before, after, what):
    """Every path and every byte the same - the rollback contract."""
    assert_equal(sorted(before), sorted(after), f"{what}: the file list changed")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after[rel]), f"{what}: {rel} changed")


def assert_no_leftovers(root, what):
    """No temp / quarantine artifact survives a run, successful or not."""
    stray = sorted(
        p for p in list_all_entries(root)
        if ".remove-form" in os.path.basename(p) or os.path.basename(p).endswith(".tmp")
    )
    assert_true(not stray, f"{what}: temp / quarantine artifacts left behind: {stray}")


def list_all_entries(root):
    """Every file AND directory path under *root*, relative and slash-normalized."""
    entries = []
    for dirpath, dirnames, files in os.walk(root):
        for name in list(dirnames) + list(files):
            full = os.path.join(dirpath, name)
            entries.append(os.path.relpath(full, root).replace("\\", "/"))
    return entries


def childobjects_block(text):
    """The `<ChildObjects>` element with its surrounding indentation, verbatim."""
    match = re.search(r"(?s)([ \t]*<ChildObjects[ >].*?</ChildObjects>|[ \t]*<ChildObjects/>)", text)
    return match.group(1) if match else None


# ---------------------------------------------------------------- remove-form

@case("remove-form: -DryRun prints the full plan and mutates nothing")
def _(work):
    copy_fixture("epf-with-form", work)
    before = snapshot_tree(work)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work, "-DryRun"],
        work,
    )
    assert_equal(0, run["exit_code"], f"dry-run exit code (stderr: {run['stderr']})")

    out = run["stdout"]
    assert_true("Planned changes:" in out, f"plan header missing:\n{out}")
    assert_true("remove ChildObjects/Form 'MainForm'" in out, f"plan does not name the registration removal:\n{out}")
    assert_true("clear DefaultForm" in out, f"plan does not name the default-form cleanup:\n{out}")
    assert_true("Obrabotka/Forms/MainForm.xml" in out.replace("\\", "/"), f"plan does not name the metadata file:\n{out}")
    assert_true("Obrabotka/Forms/MainForm" in out.replace("\\", "/"), f"plan does not name the form directory:\n{out}")
    assert_true("[DRY-RUN]" in out, f"dry-run marker missing:\n{out}")

    after = snapshot_tree(work)
    assert_equal(sorted(before), sorted(after), "dry-run changed the file list")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after[rel]), f"dry-run modified {rel}")


@case("remove-form: a non-dry run without -Force exits 2 before any mutation")
def _(work):
    copy_fixture("epf-with-form", work)
    before = snapshot_tree(work)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work],
        work,
    )
    assert_equal(2, run["exit_code"], f"missing -Force must exit 2 (stderr: {run['stderr']})")
    assert_true("-Force" in run["stderr"], f"stderr does not name the required switch: {run['stderr']}")

    after = snapshot_tree(work)
    assert_equal(sorted(before), sorted(after), "refused removal changed the file list")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after[rel]), f"refused removal modified {rel}")
    assert_true(
        not any(p.endswith(".remove-form.tmp") for p in after),
        f"refused removal left a temporary file behind: {sorted(after)}",
    )


@case("remove-form: -Force deletes the form and clears the default-form reference")
def _(work):
    copy_fixture("epf-with-form", work)
    root_xml = os.path.join(work, "Obrabotka.xml")
    before = file_facts(root_xml)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work, "-Force"],
        work,
    )
    assert_equal(0, run["exit_code"], f"-Force run exit code (stderr: {run['stderr']})")

    assert_true(not os.path.exists(os.path.join(work, "Obrabotka", "Forms", "MainForm.xml")),
                "form metadata file survived the -Force run")
    assert_true(not os.path.isdir(os.path.join(work, "Obrabotka", "Forms", "MainForm")),
                "form directory survived the -Force run")
    assert_true(os.path.exists(os.path.join(work, "Obrabotka", "Forms", "AuxForm.xml")),
                "the sibling form was deleted too")

    after = file_facts(root_xml)
    assert_true("<Form>MainForm</Form>" not in after["text"], "ChildObjects still registers the removed form")
    assert_true("<Form>AuxForm</Form>" in after["text"], "the sibling registration was removed too")
    assert_true("DataProcessor.Obrabotka.Form.MainForm" not in after["text"],
                "DefaultForm still points at the removed form")
    assert_true(after["bom"], "root XML lost its BOM")
    assert_equal(0, after["crlf"], "CRLF introduced into an LF file")
    assert_true(before["lines"].count("") == after["lines"].count(""), "blank-line structure changed")
    assert_true(not os.path.exists(root_xml + ".remove-form.tmp"), "temporary root XML left behind")


@case("remove-form: every slot referencing the form is named in the plan and cleared")
def _(work):
    copy_fixture("epf-with-form", work)
    root_xml = os.path.join(work, "Obrabotka.xml")
    # form-add writes the purpose-specific slot, so a form can be referenced from
    # more than one place. Clearing only the generic DefaultForm would leave a
    # dangling reference to a file that no longer exists.
    facts = file_facts(root_xml)
    text = facts["text"].replace(
        "<AuxiliarySearchForm/>",
        "<AuxiliarySearchForm>DataProcessor.Obrabotka.Form.MainForm</AuxiliarySearchForm>")
    assert_true(text != facts["text"], "fixture no longer carries AuxiliarySearchForm - the case cannot arm itself")
    with open(root_xml, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))

    dry = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work, "-DryRun"],
        work,
    )
    assert_equal(0, dry["exit_code"], f"dry-run exit code (stderr: {dry['stderr']})")
    assert_true("clear DefaultForm" in dry["stdout"], f"plan omits DefaultForm:\n{dry['stdout']}")
    assert_true("clear AuxiliarySearchForm" in dry["stdout"],
                f"plan omits the second referencing slot:\n{dry['stdout']}")

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work, "-Force"],
        work,
    )
    assert_equal(0, run["exit_code"], f"-Force run exit code (stderr: {run['stderr']})")
    after = file_facts(root_xml)["text"]
    assert_true("DataProcessor.Obrabotka.Form.MainForm" not in after,
                f"a reference to the removed form survived:\n{after}")
    assert_true("<AuxiliarySearchForm></AuxiliarySearchForm>" in after or "<AuxiliarySearchForm/>" in after,
                f"AuxiliarySearchForm was not cleared but dropped:\n{after}")


@case("remove-form: an absent form is refused before any mutation")
def _(work):
    copy_fixture("epf-with-form", work)
    before = snapshot_tree(work)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "NoSuchForm", "-SrcDir", work, "-Force"],
        work,
    )
    assert_equal(1, run["exit_code"], f"absent form must exit 1 (stderr: {run['stderr']})")

    after = snapshot_tree(work)
    assert_equal(sorted(before), sorted(after), "refused run changed the file list")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after[rel]), f"refused run modified {rel}")


@case("remove-form: a form absent from ChildObjects is refused before any mutation")
def _(work):
    copy_fixture("epf-with-form", work)
    root_xml = os.path.join(work, "Obrabotka.xml")
    # Unregister AuxForm but keep its files: upstream would delete them and leave
    # the root XML alone, which is exactly the half-applied state to refuse.
    facts = file_facts(root_xml)
    text = facts["text"].replace("\t\t\t<Form>AuxForm</Form>\n", "")
    assert_true(text != facts["text"], "fixture no longer registers AuxForm - the case cannot arm itself")
    with open(root_xml, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))
    before = snapshot_tree(work)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "AuxForm", "-SrcDir", work, "-Force"],
        work,
    )
    assert_equal(1, run["exit_code"], f"unregistered form must exit 1 (stderr: {run['stderr']})")
    assert_true("ChildObjects" in run["stderr"], f"stderr does not explain the refusal: {run['stderr']}")

    after = snapshot_tree(work)
    assert_equal(sorted(before), sorted(after), "refused run changed the file list")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after[rel]), f"refused run modified {rel}")


def _rename_fixture_to_unicode(sandbox, object_name, form_name):
    """Rewrite the epf-with-form fixture in place to Cyrillic object / form names.

    1C identifiers cannot contain spaces, so the space risk is exercised through
    the containing directory instead - which is where a real project hits it
    (`C:\\My Projects\\...`, `/home/user/1c src/...`)."""
    root_xml = os.path.join(sandbox, "Obrabotka.xml")
    facts = file_facts(root_xml)
    text = facts["text"].replace("Obrabotka", object_name).replace("MainForm", form_name)
    with open(root_xml, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))
    os.replace(root_xml, os.path.join(sandbox, f"{object_name}.xml"))

    obj_dir = os.path.join(sandbox, "Obrabotka")
    forms_dir = os.path.join(obj_dir, "Forms")
    meta = os.path.join(forms_dir, "MainForm.xml")
    meta_facts = file_facts(meta)
    with open(meta, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + meta_facts["text"].replace("MainForm", form_name).encode("utf-8"))
    os.replace(meta, os.path.join(forms_dir, f"{form_name}.xml"))
    os.replace(os.path.join(forms_dir, "MainForm"), os.path.join(forms_dir, form_name))
    os.replace(obj_dir, os.path.join(sandbox, object_name))


@case("remove-form: Cyrillic names under a path with spaces behave identically")
def _(work):
    object_name = "ТестоваяОбработка"
    form_name = "ОсновнаяФорма"
    sandbox = os.path.join(work, "My 1C Sources", "src dump")
    copy_fixture("epf-with-form", sandbox)
    _rename_fixture_to_unicode(sandbox, object_name, form_name)

    before = snapshot_tree(sandbox)
    dry = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", object_name, "-FormName", form_name, "-SrcDir", sandbox, "-DryRun"],
        sandbox,
    )
    assert_equal(0, dry["exit_code"], f"dry-run exit code (stderr: {dry['stderr']})")
    assert_true(form_name in dry["stdout"], f"plan lost the Cyrillic form name:\n{dry['stdout']}")
    assert_true("clear DefaultForm" in dry["stdout"], f"plan lost the reference cleanup:\n{dry['stdout']}")
    after_dry = snapshot_tree(sandbox)
    assert_equal(sorted(before), sorted(after_dry), "dry-run changed the file list")
    for rel, data in before.items():
        assert_equal(base64.b64encode(data), base64.b64encode(after_dry[rel]), f"dry-run modified {rel}")

    refused = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", object_name, "-FormName", form_name, "-SrcDir", sandbox],
        sandbox,
    )
    assert_equal(2, refused["exit_code"], f"missing -Force must exit 2 (stderr: {refused['stderr']})")
    assert_equal(sorted(before), sorted(snapshot_tree(sandbox)), "refused run changed the file list")

    forced = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", object_name, "-FormName", form_name, "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(0, forced["exit_code"], f"-Force exit code (stderr: {forced['stderr']})")
    assert_true(not os.path.exists(os.path.join(sandbox, object_name, "Forms", f"{form_name}.xml")),
                "form metadata file survived")
    assert_true(not os.path.isdir(os.path.join(sandbox, object_name, "Forms", form_name)),
                "form directory survived")
    text = file_facts(os.path.join(sandbox, f"{object_name}.xml"))["text"]
    assert_true(f"<Form>{form_name}</Form>" not in text, "registration survived")
    assert_true("<Form>AuxForm</Form>" in text, "sibling registration lost")
    assert_true(f"DataProcessor.{object_name}.Form.{form_name}" not in text,
                "DefaultForm still points at the removed form")


@case("remove-form: a leftover quarantine from an interrupted run stops the next one")
def _(work):
    """An interrupted run can leave the quarantine behind - it then holds the only
    copy of the removed files. The next run must refuse and point at it rather
    than write into it or delete it."""
    copy_fixture("epf-with-form", work)
    quarantine = os.path.join(work, ".remove-form-quarantine")
    os.makedirs(quarantine)
    with open(os.path.join(quarantine, "form-meta.xml"), "wb") as handle:
        handle.write(b"<recoverable/>")
    before = snapshot_tree(work)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", work, "-Force"],
        work,
    )
    assert_equal(2, run["exit_code"], f"a stale quarantine did not stop the run: {run['stdout'][:300]!r}")
    assert_true(".remove-form-quarantine" in run["stderr"],
                f"the refusal does not name the quarantine: {run['stderr'][:300]!r}")
    assert_tree_identical(before, snapshot_tree(work), "stale-quarantine refusal")


@case("remove-form parity: PowerShell and Python agree on the safety contract", needs_powershell=True)
def _(work):
    """Same scenarios through both runtimes, same observable safety outcome.

    Byte equality of the root XML is deliberately NOT asserted: remove-form.ps1
    re-serializes through System.Xml.XmlWriter and loses the Configurator style
    (CRLF into an LF file, `<Tag />` for `<Tag/>`, lower-cased encoding), while
    the Python port keeps upstream's round-trip style preservation. What has to
    match is the safety contract - exit codes, what the plan announces, and which
    files survive."""

    def plan_steps(text, sandbox):
        """The plan is the operator-facing half of the contract: normalize the
        sandbox prefix away and compare what each runtime announces."""
        prefix = os.path.abspath(sandbox)
        steps = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("modify:", "delete:")):
                continue
            steps.append(stripped.replace(prefix, "<src>").replace("\\", "/"))
        return steps

    scenarios = [
        ("dry-run", ["-DryRun"], 0),
        ("no-force", [], 2),
        ("force", ["-Force"], 0),
    ]
    for label, extra, expected_exit in scenarios:
        results = {}
        for runtime, script, runner in (
            ("ps", REMOVE_FORM_PS1, run_powershell_tool),
            ("py", REMOVE_FORM_PY, run_python_tool),
        ):
            sandbox = os.path.join(work, f"{label}-{runtime}")
            copy_fixture("epf-with-form", sandbox)
            run = runner(
                script,
                ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, *extra],
                sandbox,
            )
            results[runtime] = (run, sorted(snapshot_tree(sandbox)), sandbox)

        for runtime, (run, _files, _sandbox) in results.items():
            assert_equal(expected_exit, run["exit_code"],
                         f"{label}/{runtime} exit code (stderr: {run['stderr']})")

        ps_run, ps_files, ps_sandbox = results["ps"]
        py_run, py_files, py_sandbox = results["py"]
        assert_equal(ps_files, py_files, f"{label}: surviving file lists differ between runtimes")

        ps_plan = plan_steps(ps_run["stdout"], ps_sandbox)
        py_plan = plan_steps(py_run["stdout"], py_sandbox)
        assert_true(ps_plan, f"{label}: the PowerShell run announced no plan at all")
        assert_true(ps_plan == py_plan,
                    f"{label}: plans differ\n  ps: {ps_plan}\n  py: {py_plan}")

    # And the committed result has to be semantically identical.
    for runtime in ("ps", "py"):
        text = file_facts(os.path.join(work, f"force-{runtime}", "Obrabotka.xml"))["text"]
        assert_true("<Form>MainForm</Form>" not in text, f"force/{runtime}: registration survived")
        assert_true("<Form>AuxForm</Form>" in text, f"force/{runtime}: sibling registration lost")
        assert_true("DataProcessor.Obrabotka.Form.MainForm" not in text,
                    f"force/{runtime}: DefaultForm still points at the removed form")


# ------------------------------------------------- remove-form: input validation

# Names that must never reach the filesystem. 1C identifiers are Latin / Cyrillic
# letters, digits and underscore, not starting with a digit - everything below is
# either a path expression or not an identifier at all.
ADVERSARIAL_NAMES = [
    "../../victim", "..", ".", "../victim",
    "Forms/MainForm", "Forms\\MainForm", "a/b", "a\\b",
    "/etc/passwd", "C:/Windows/System32/drivers", "C:\\Windows",
    "\\\\server\\share\\x", "//server/share/x",
    "MainForm.", "MainForm ", " MainForm", "MainForm\t",
    "\u039cainForm",          # Greek capital Mu - a Latin "M" confusable
    "\u041c\u0430inForm\u200b",  # trailing zero-width space
    "1MainForm", "Main-Form", "Main Form", "",
]

# argv itself cannot carry a NUL on either platform, so this one is asserted
# in-process: the validator must still refuse it (defence in depth).
NUL_NAME = "Main\x00Form"


@case("remove-form: pathlike and non-identifier names are refused with exit 2, no mutation")
def _(work):
    for index, bad in enumerate(ADVERSARIAL_NAMES):
        sandbox = os.path.join(work, f"case{index:02d}")
        copy_fixture("epf-with-form", sandbox)
        before = snapshot_tree(sandbox)
        for slot, argv in (
            ("FormName", ["-ObjectName", "Obrabotka", "-FormName", bad]),
            ("ObjectName", ["-ObjectName", bad, "-FormName", "MainForm"]),
        ):
            run = run_python_tool(REMOVE_FORM_PY, [*argv, "-SrcDir", sandbox, "-Force"], sandbox)
            assert_equal(2, run["exit_code"],
                         f"{slot}={bad!r} must be refused with exit 2 "
                         f"(stdout: {run['stdout'][:200]!r} stderr: {run['stderr'][:200]!r})")
            assert_tree_identical(before, snapshot_tree(sandbox), f"{slot}={bad!r}")
        # -DryRun must refuse just as hard: the plan itself would echo the path.
        run = run_python_tool(
            REMOVE_FORM_PY,
            ["-ObjectName", "Obrabotka", "-FormName", bad, "-SrcDir", sandbox, "-DryRun"],
            sandbox,
        )
        assert_equal(2, run["exit_code"], f"FormName={bad!r} must be refused in -DryRun too")
        assert_tree_identical(before, snapshot_tree(sandbox), f"dry-run {bad!r}")
        assert_no_leftovers(sandbox, f"refused {bad!r}")

    # "nul" is a reserved device name on Windows - do not name a directory that.
    sandbox = os.path.join(work, "nul-name")
    copy_fixture("epf-with-form", sandbox)
    before = snapshot_tree(sandbox)
    run = run_tool_in_process(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", NUL_NAME, "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(2, run["exit_code"], f"FormName={NUL_NAME!r} must be refused with exit 2")
    assert_tree_identical(before, snapshot_tree(sandbox), "NUL name")


@case("remove-form: a traversal name cannot delete anything outside Forms/")
def _(work):
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    # `Forms/../../victim` resolves to <SrcDir>/victim - outside the form directory.
    with open(os.path.join(sandbox, "victim.xml"), "w", encoding="utf-8") as handle:
        handle.write("<x/>")
    os.makedirs(os.path.join(sandbox, "victim"), exist_ok=True)
    with open(os.path.join(sandbox, "victim", "payload.txt"), "w", encoding="utf-8") as handle:
        handle.write("data")
    # Register the traversal name so nothing but the identifier check can stop it.
    root_xml = os.path.join(sandbox, "Obrabotka.xml")
    text = file_facts(root_xml)["text"].replace(
        "<Form>AuxForm</Form>", "<Form>AuxForm</Form>\n\t\t\t<Form>../../victim</Form>")
    with open(root_xml, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))
    before = snapshot_tree(sandbox)

    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "../../victim", "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(2, run["exit_code"], f"traversal was not refused (stdout: {run['stdout'][:300]!r})")
    assert_tree_identical(before, snapshot_tree(sandbox), "traversal run")


@case("remove-form: a symlinked form directory or metadata file is refused")
def _(work):
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    outside_dir = os.path.join(work, "outside-dir")
    os.makedirs(outside_dir, exist_ok=True)
    with open(os.path.join(outside_dir, "payload.txt"), "w", encoding="utf-8") as handle:
        handle.write("data")

    forms = os.path.join(sandbox, "Obrabotka", "Forms")
    link = os.path.join(forms, "MainForm")
    shutil.rmtree(link)
    try:
        os.symlink(outside_dir, link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as exc:
        raise CaseSkipped(f"symlinks unavailable on this host ({exc})")

    before = snapshot_tree(sandbox)
    outside_before = snapshot_tree(outside_dir)
    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(2, run["exit_code"],
                 f"a symlinked form directory was not refused (stdout: {run['stdout'][:300]!r})")
    assert_tree_identical(outside_before, snapshot_tree(outside_dir), "symlink target")
    assert_equal(sorted(before), sorted(snapshot_tree(sandbox)), "sandbox file list changed")


@case("remove-form: an object directory reached through a link is refused")
def _(work):
    """Containment has to start at -SrcDir, the one path the caller vouched for.

    Checking Forms/ against the object directory says nothing when the object
    directory is itself a link: both sides resolve into the same foreign tree and
    the check passes, so a -Force run deleted a stranger's files and exited 0."""
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    outside = os.path.join(work, "outside-object")
    shutil.move(os.path.join(sandbox, "Obrabotka"), outside)
    kind = make_directory_link(outside, os.path.join(sandbox, "Obrabotka"))

    outside_before = snapshot_tree(outside)
    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox)
    assert_equal(2, run["exit_code"],
                 f"a {kind} object directory was not refused "
                 f"(stdout: {run['stdout'][:300]!r} stderr: {run['stderr'][:300]!r})")
    assert_tree_identical(outside_before, snapshot_tree(outside),
                          f"files outside SrcDir behind a {kind}")
    assert_no_leftovers(sandbox, "refused ancestor link")


@case("remove-form ancestor confinement parity: PowerShell refuses a linked object directory",
      needs_powershell=True)
def _(work):
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    outside = os.path.join(work, "outside-object")
    shutil.move(os.path.join(sandbox, "Obrabotka"), outside)
    kind = make_directory_link(outside, os.path.join(sandbox, "Obrabotka"))

    outside_before = snapshot_tree(outside)
    run = run_powershell_tool(
        REMOVE_FORM_PS1,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox)
    assert_equal(2, run["exit_code"],
                 f"PowerShell accepted a {kind} object directory "
                 f"(stdout: {run['stdout'][:300]!r} stderr: {run['stderr'][:300]!r})")
    assert_tree_identical(outside_before, snapshot_tree(outside),
                          f"files outside SrcDir behind a {kind} (PowerShell)")
    assert_no_leftovers(sandbox, "PowerShell refused ancestor link")


@case("remove-form: a linked object directory is refused for -DryRun and without -Force too")
def _(work):
    """The refusal belongs before the plan, not after it: neither of the two modes
    that are documented as non-mutating may touch the foreign tree either."""
    for index, extra in enumerate((["-DryRun"], [])):
        sandbox = os.path.join(work, f"mode{index}")
        copy_fixture("epf-with-form", sandbox)
        outside = os.path.join(work, f"outside{index}")
        shutil.move(os.path.join(sandbox, "Obrabotka"), outside)
        make_directory_link(outside, os.path.join(sandbox, "Obrabotka"))
        outside_before = snapshot_tree(outside)
        run = run_python_tool(
            REMOVE_FORM_PY,
            ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, *extra],
            sandbox)
        assert_equal(2, run["exit_code"],
                     f"{extra or ['(no -Force)']}: a linked object directory was not refused")
        assert_tree_identical(outside_before, snapshot_tree(outside),
                              f"{extra or ['(no -Force)']}: files outside SrcDir")


# ------------------------------------------------- remove-form: transactionality

def _expected_final_state(work):
    """Tree of a clean, successful removal - the only acceptable non-rollback outcome."""
    reference = os.path.join(work, "_reference")
    copy_fixture("epf-with-form", reference)
    run = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", reference, "-Force"],
        reference,
    )
    assert_equal(0, run["exit_code"], f"reference removal failed (stderr: {run['stderr']})")
    return snapshot_tree(reference)


def _count_calls(work, primitive):
    """How many times a clean run calls *primitive*, so faults can target each one."""
    sandbox = os.path.join(work, f"_count-{primitive.replace('.', '-')}")
    copy_fixture("epf-with-form", sandbox)
    seen = []

    def counting(*call_args):
        seen.append(call_args)
        return False

    run = run_tool_in_process(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox,
        faults={primitive: counting},
    )
    assert_equal(0, run["exit_code"], f"counting run failed (stderr: {run['stderr']})")
    return len(seen)


@case("remove-form: a fault at any mutation step leaves the tree fully original or fully final")
def _(work):
    final_state = _expected_final_state(work)
    checked = 0
    for primitive in ("shutil.copyfile", "os.replace", "os.remove", "shutil.rmtree", "shutil.move"):
        total = _count_calls(work, primitive)
        for nth in range(1, total + 1):
            sandbox = os.path.join(work, f"fault-{primitive.replace('.', '-')}-{nth}")
            copy_fixture("epf-with-form", sandbox)
            original = snapshot_tree(sandbox)
            counter = {"n": 0}

            def boom(*call_args, _c=counter, _n=nth):
                _c["n"] += 1
                return _c["n"] == _n

            run = run_tool_in_process(
                REMOVE_FORM_PY,
                ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
                sandbox,
                faults={primitive: boom},
            )
            after = snapshot_tree(sandbox)
            what = f"fault in {primitive} call #{nth}"
            leftovers = sorted(p for p in after if ".remove-form" in p or p.endswith(".tmp"))
            visible = {k: v for k, v in after.items() if k not in leftovers}
            if sorted(visible) == sorted(original):
                assert_tree_identical(original, visible, f"{what}: partial rollback")
                assert_true(run["exit_code"] != 0, f"{what}: rolled back but reported success")
                assert_true(not leftovers, f"{what}: rollback left artifacts behind: {leftovers}")
            else:
                # Committed. The visible tree must be exactly the successful result;
                # a quarantine may only survive a failure of the post-commit cleanup,
                # and then the run must say so instead of claiming success.
                assert_tree_identical(final_state, visible, f"{what}: neither original nor final")
                if leftovers:
                    assert_true(run["exit_code"] != 0,
                                f"{what}: left {leftovers} behind but reported success")
                    assert_true(".remove-form-quarantine" in (run["stdout"] + run["stderr"]),
                                f"{what}: leftover quarantine is not named in the output")
            checked += 1
    assert_true(checked >= 5, f"only {checked} mutation boundaries exercised - too few to be meaningful")


QUARANTINE = ".remove-form-quarantine"

# The form files the fixture puts inside Obrabotka/Forms, and the quarantine slot
# each one is parked in. Recovery is asserted on these exact bytes: "the directory
# exists" is what let the old case pass while the payload was already gone.
PARKED_PAYLOADS = {
    "form-meta.xml": "Obrabotka/Forms/MainForm.xml",
    "form-dir/Ext/Form.xml": "Obrabotka/Forms/MainForm/Ext/Form.xml",
    "form-dir/Ext/Form/Module.bsl": "Obrabotka/Forms/MainForm/Ext/Form/Module.bsl",
}


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def run_remove_form_in_process(sandbox, faults):
    return run_tool_in_process(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox,
        faults=faults,
    )


def counting_predicate(failing_ordinals):
    """Fail exactly the listed calls of a primitive, and let the rest through."""
    seen = {"n": 0}

    def predicate(*call_args):
        seen["n"] += 1
        return seen["n"] in failing_ordinals

    return predicate


def assert_recovery_bytes(quarantine, original, slots, what):
    """Every listed quarantine slot holds the original file, byte for byte."""
    for slot in slots:
        parked = os.path.join(quarantine, *slot.split("/"))
        assert_true(os.path.isfile(parked), f"{what}: recovery copy missing: {parked}")
        assert_equal(base64.b64encode(original[PARKED_PAYLOADS[slot]]),
                     base64.b64encode(read_bytes(parked)),
                     f"{what}: recovery copy of {PARKED_PAYLOADS[slot]} is not the original bytes")


@case("remove-form: a rollback that cannot put a parked file back keeps the quarantine")
def _(work):
    """The case the old one could not reach.

    Failing the *first* rename means nothing has been parked yet, so deleting the
    quarantine on the way out costs nothing and the run looks safe. Let both
    parking renames succeed first and the picture changes: the tree has a hole,
    the restores fail, and the quarantine is the only copy of three files left
    anywhere. Deleting it there is data loss, and the message that pointed at it
    was a lie."""
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    original = snapshot_tree(sandbox)

    # Renames 1 and 2 park the form directory and the descriptor; rename 3 would
    # publish the root XML. From there on every rename - the publish and both
    # put-backs the rollback attempts - fails.
    run = run_remove_form_in_process(sandbox, {"os.replace": counting_predicate(range(3, 99))})

    assert_true(run["exit_code"] != 0, "a wholly failed run reported success")
    quarantine = os.path.join(sandbox, QUARANTINE)
    assert_true(os.path.isdir(quarantine),
                "the rollback destroyed the only surviving copy of the deleted files")
    assert_recovery_bytes(quarantine, original, sorted(PARKED_PAYLOADS), "failed rollback")

    # Nothing was published, so the root file is still the original.
    assert_equal(base64.b64encode(original["Obrabotka.xml"]),
                 base64.b64encode(read_bytes(os.path.join(sandbox, "Obrabotka.xml"))),
                 "the root XML changed although the publish failed")

    err = run["stderr"]
    assert_true("injected failure" in err,
                f"the primary failure was masked by the rollback report:\n{err}")
    assert_true(quarantine in err, f"the kept quarantine is not named:\n{err}")
    for slot, rel in PARKED_PAYLOADS.items():
        if "/" in slot and not slot.startswith("form-meta"):
            continue  # the directory is reported as one payload, not file by file
        parked = os.path.join(quarantine, *slot.split("/"))
        original_path = os.path.join(sandbox, *rel.split("/"))
        assert_true(parked in err, f"the recovery path does not name {parked}:\n{err}")
        assert_true(original_path in err,
                    f"the recovery path does not say where {parked} belongs:\n{err}")


@case("remove-form: a failed publish whose restore also fails keeps the root backup")
def _(work):
    """Primary failure plus a failing restore, with the put-backs succeeding.

    Nothing is left parked, so the quarantine looks empty of payload - but the
    root backup is the only thing that knows what the root XML used to be, and
    the restore that should have used it did not run to completion."""
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    original = snapshot_tree(sandbox)

    run = run_remove_form_in_process(sandbox, {
        # Rename 3 is the publish; the put-backs (4, 5) are allowed to succeed.
        "os.replace": counting_predicate({3}),
        # Copy 1 took the backup; copy 2 is the restore that puts it back.
        "shutil.copyfile": counting_predicate({2}),
    })

    assert_true(run["exit_code"] != 0, "a failed publish reported success")
    quarantine = os.path.join(sandbox, QUARANTINE)
    assert_true(os.path.isdir(quarantine),
                "the quarantine went even though the root restore had failed")
    backup = os.path.join(quarantine, "root-backup.xml")
    assert_equal(base64.b64encode(original["Obrabotka.xml"]),
                 base64.b64encode(read_bytes(backup)),
                 "the kept backup is not the original root bytes")

    # The two parked payloads came back, so they are not reported as outstanding.
    for slot, rel in PARKED_PAYLOADS.items():
        assert_true(os.path.exists(os.path.join(sandbox, *rel.split("/"))),
                    f"the rollback did not put {rel} back")
    err = run["stderr"]
    assert_true(backup in err, f"the kept backup is not named:\n{err}")
    assert_true(os.path.join(sandbox, "Obrabotka.xml") in err,
                f"the recovery path does not say where the backup belongs:\n{err}")
    assert_true("injected failure" in err, f"the primary failure was masked:\n{err}")


@case("remove-form: a partial rollback keeps exactly what it could not put back")
def _(work):
    """One put-back fails, the other succeeds. The quarantine must keep the first
    and must not still be holding the second."""
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    original = snapshot_tree(sandbox)

    # 3 = publish, 4 = put back the descriptor (fails), 5 = put back the form
    # directory (succeeds).
    run = run_remove_form_in_process(sandbox, {"os.replace": counting_predicate({3, 4})})

    assert_true(run["exit_code"] != 0, "a partial rollback reported success")
    quarantine = os.path.join(sandbox, QUARANTINE)
    assert_true(os.path.isdir(quarantine), "the unrestored descriptor was destroyed")
    assert_recovery_bytes(quarantine, original, ["form-meta.xml"], "partial rollback")
    assert_true(not os.path.exists(os.path.join(quarantine, "form-dir")),
                "the restored form directory is still sitting in the quarantine")

    restored = os.path.join(sandbox, "Obrabotka", "Forms", "MainForm", "Ext", "Form.xml")
    assert_equal(base64.b64encode(original["Obrabotka/Forms/MainForm/Ext/Form.xml"]),
                 base64.b64encode(read_bytes(restored)),
                 "the form directory did not come back with its original bytes")

    err = run["stderr"]
    assert_true(os.path.join(quarantine, "form-meta.xml") in err,
                f"the one unrestored payload is not named:\n{err}")
    assert_true(os.path.join(quarantine, "form-dir") not in err,
                f"a payload that was put back is still reported as lost:\n{err}")


@case("remove-form: a rollback that succeeds and a commit both clear the quarantine")
def _(work):
    """The other half of the contract: keeping the quarantine is for unrecovered
    payload only. A clean rollback and a clean commit must both leave nothing
    behind, or the next run refuses to start."""
    rolled_back = os.path.join(work, "rolled-back")
    copy_fixture("epf-with-form", rolled_back)
    original = snapshot_tree(rolled_back)

    run = run_remove_form_in_process(rolled_back, {"os.replace": counting_predicate({3})})
    assert_true(run["exit_code"] != 0, "a failed publish reported success")
    assert_tree_identical(original, snapshot_tree(rolled_back), "successful rollback")
    assert_no_leftovers(rolled_back, "successful rollback")
    assert_true("rollback" in (run["stdout"] + run["stderr"]).lower()
                or "откат" in (run["stdout"] + run["stderr"]).lower(),
                f"a failed run does not mention the rollback:\n{run['stderr'][:600]}")

    committed = os.path.join(work, "committed")
    copy_fixture("epf-with-form", committed)
    clean = run_python_tool(
        REMOVE_FORM_PY,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", committed, "-Force"],
        committed)
    assert_equal(0, clean["exit_code"], f"clean removal (stderr: {clean['stderr'][-400:]})")
    assert_no_leftovers(committed, "successful commit")


# ------------------------------------------------- remove-form: XML style

@case("remove-form: ChildObjects keeps its exact indentation for first / middle / last")
def _(work):
    # Three forms so the removed one can be first, middle or last in the block.
    variants = {"MainForm": None, "AuxForm": None}
    for position, form_name in (("first", "MainForm"), ("last", "AuxForm")):
        sandbox = os.path.join(work, position)
        copy_fixture("epf-with-form", sandbox)
        root_xml = os.path.join(sandbox, "Obrabotka.xml")
        before = file_facts(root_xml)

        run = run_python_tool(
            REMOVE_FORM_PY,
            ["-ObjectName", "Obrabotka", "-FormName", form_name, "-SrcDir", sandbox, "-Force"],
            sandbox,
        )
        assert_equal(0, run["exit_code"], f"{position} removal (stderr: {run['stderr']})")

        after = file_facts(root_xml)
        expected_block = (before["text"]
                          .replace(f"\n\t\t\t<Form>{form_name}</Form>", "", 1))
        expected_block = childobjects_block(expected_block)
        assert_equal(expected_block, childobjects_block(after["text"]),
                     f"{position}: ChildObjects block was restyled")
        assert_true(after["bom"], f"{position}: BOM lost")
        assert_equal(0, after["crlf"], f"{position}: CRLF introduced into an LF file")
        assert_true(after["text"].endswith("\n"), f"{position}: final newline lost")
        assert_true('encoding="UTF-8"' in after["text"], f"{position}: encoding declaration restyled")
        assert_true(" />" not in after["text"], f"{position}: Configurator writes <Tag/>, found <Tag />")
        variants[form_name] = childobjects_block(after["text"])

    # Removing the only remaining form must not leave a dangling indentation island.
    sandbox = os.path.join(work, "only")
    copy_fixture("epf-with-form", sandbox)
    root_xml = os.path.join(sandbox, "Obrabotka.xml")
    for form_name in ("MainForm", "AuxForm"):
        run = run_python_tool(
            REMOVE_FORM_PY,
            ["-ObjectName", "Obrabotka", "-FormName", form_name, "-SrcDir", sandbox, "-Force"],
            sandbox,
        )
        assert_equal(0, run["exit_code"], f"removing {form_name} (stderr: {run['stderr']})")
    block = childobjects_block(file_facts(root_xml)["text"])
    assert_true(block.strip() in ("<ChildObjects/>", "<ChildObjects></ChildObjects>"),
                f"an emptied ChildObjects was left malformed: {block!r}")


@case("remove-form style parity: both runtimes emit the same ChildObjects block", needs_powershell=True)
def _(work):
    blocks = {}
    for runtime, script, runner in (
        ("ps", REMOVE_FORM_PS1, run_powershell_tool),
        ("py", REMOVE_FORM_PY, run_python_tool),
    ):
        sandbox = os.path.join(work, runtime)
        copy_fixture("epf-with-form", sandbox)
        run = runner(
            script,
            ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
            sandbox,
        )
        assert_equal(0, run["exit_code"], f"{runtime} removal (stderr: {run['stderr']})")
        block = childobjects_block(file_facts(os.path.join(sandbox, "Obrabotka.xml"))["text"])
        blocks[runtime] = block.replace("\r\n", "\n")
    # EOL is normalized on purpose: remove-form.ps1 rewrites the whole file through
    # XmlWriter and turns an LF dump into CRLF, which the Python-only style case
    # asserts and docs/form-manage.md documents. What must match here is the
    # indentation structure of the block both runtimes produce.
    assert_equal(repr(blocks["ps"]), repr(blocks["py"]),
                 "the two runtimes indent ChildObjects differently")


# ---------------------------------------------------------------- licensing

UPSTREAM_NOTICE_REL = "content/skills/1c-metadata-manage/NOTICE.md"
UPSTREAM_PIN = "ecd289fe11733028d87b55284ea9fb5feff8f513"


@case("remove-form safety parity: PowerShell refuses the same names and paths", needs_powershell=True)
def _(work):
    """The two runtimes ship the same tool; a hole patched only in one of them is
    still a hole for every Windows user."""
    for index, bad in enumerate(["../../victim", "Forms/MainForm", "MainForm ", "1MainForm",
                                 "\u039cainForm", "C:\\Windows"]):
        sandbox = os.path.join(work, f"bad{index:02d}")
        copy_fixture("epf-with-form", sandbox)
        before = snapshot_tree(sandbox)
        run = run_powershell_tool(
            REMOVE_FORM_PS1,
            ["-ObjectName", "Obrabotka", "-FormName", bad, "-SrcDir", sandbox, "-Force"],
            sandbox,
        )
        assert_equal(2, run["exit_code"],
                     f"PowerShell accepted FormName={bad!r} "
                     f"(stdout: {run['stdout'][:200]!r} stderr: {run['stderr'][:200]!r})")
        assert_tree_identical(before, snapshot_tree(sandbox), f"PowerShell refused {bad!r}")
        assert_no_leftovers(sandbox, f"PowerShell refused {bad!r}")

    # And the traversal must not reach outside even when the name is registered.
    sandbox = os.path.join(work, "traversal")
    copy_fixture("epf-with-form", sandbox)
    with open(os.path.join(sandbox, "victim.xml"), "w", encoding="utf-8") as handle:
        handle.write("<x/>")
    root_xml = os.path.join(sandbox, "Obrabotka.xml")
    text = file_facts(root_xml)["text"].replace(
        "<Form>AuxForm</Form>", "<Form>AuxForm</Form>\n\t\t\t<Form>../../victim</Form>")
    with open(root_xml, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))
    before = snapshot_tree(sandbox)
    run = run_powershell_tool(
        REMOVE_FORM_PS1,
        ["-ObjectName", "Obrabotka", "-FormName", "../../victim", "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(2, run["exit_code"], f"PowerShell traversal not refused: {run['stdout'][:300]!r}")
    assert_tree_identical(before, snapshot_tree(sandbox), "PowerShell traversal run")


@case("remove-form safety parity: PowerShell rolls a failed removal back", needs_powershell=True)
def _(work):
    """A read-only form metadata file makes the deletion step fail for real. The
    PowerShell run must restore the root XML and the form directory, exactly as
    the Python port does."""
    sandbox = os.path.join(work, "src")
    copy_fixture("epf-with-form", sandbox)
    # A stale quarantine is the one fault both runtimes can be given deterministically
    # and portably: it aborts before the first mutation and must change nothing.
    quarantine = os.path.join(sandbox, ".remove-form-quarantine")
    os.makedirs(quarantine)
    with open(os.path.join(quarantine, "form-meta.xml"), "wb") as handle:
        handle.write(b"<recoverable/>")
    before = snapshot_tree(sandbox)

    run = run_powershell_tool(
        REMOVE_FORM_PS1,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-Force"],
        sandbox,
    )
    assert_equal(2, run["exit_code"],
                 f"PowerShell ignored a stale quarantine: {run['stdout'][:300]!r}")
    assert_true(".remove-form-quarantine" in run["stderr"],
                f"the refusal does not name the quarantine: {run['stderr'][:300]!r}")
    assert_tree_identical(before, snapshot_tree(sandbox), "PowerShell stale-quarantine refusal")


@case("licensing: the vendored MIT notice is present and complete in the source tree")
def _(work):
    path = os.path.join(REPO_ROOT, *UPSTREAM_NOTICE_REL.split("/"))
    assert_true(os.path.isfile(path), f"missing upstream notice: {UPSTREAM_NOTICE_REL}")
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8-sig")
    for required in (
        "MIT License",
        "Copyright (c) 2025-2026 Nick Shirokov",
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        'THE SOFTWARE IS PROVIDED "AS IS"',
        "Nikolay-Shirokov/cc-1c-skills",
        UPSTREAM_PIN,
        "remove-form.py",
    ):
        assert_true(required in text, f"upstream notice does not carry: {required!r}")


@case("licensing: the notice is distributable and travels with the committed archive")
def _(work):
    def git(*argv):
        return subprocess.run(["git", *argv], cwd=REPO_ROOT, capture_output=True)

    # A notice that .gitignore swallows would never reach a consumer.
    ignored = git("check-ignore", "-q", UPSTREAM_NOTICE_REL).returncode == 0
    assert_true(not ignored, f"{UPSTREAM_NOTICE_REL} is gitignored and would never be distributed")

    tracked = git("ls-files", "--error-unmatch", UPSTREAM_NOTICE_REL).returncode == 0
    if not tracked:
        # Pre-commit state: the file must at least be a pending addition, not a
        # stray that a clean checkout would lose.
        listed = git("ls-files", "--others", "--exclude-standard", "--", UPSTREAM_NOTICE_REL)
        assert_true(listed.stdout.strip(),
                    f"{UPSTREAM_NOTICE_REL} is neither tracked nor a pending addition")
        return

    proc = git("archive", "HEAD")
    assert_equal(0, proc.returncode, f"git archive failed: {proc.stderr[:400]!r}")
    archive = os.path.join(work, "head.tar")
    with open(archive, "wb") as handle:
        handle.write(proc.stdout)
    import tarfile
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert_true(UPSTREAM_NOTICE_REL in names,
                f"the distribution archive carries no upstream notice at {UPSTREAM_NOTICE_REL}")


# ---------------------------------------------------------------- CI wiring

@case("ci: the workflow runs the Python port regression on Windows and on Linux")
def _(work):
    path = os.path.join(REPO_ROOT, ".github", "workflows", "validate-rules.yml")
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8")
    assert_true("python-ports-regression.py" in text,
                "the workflow never runs tools/tests/python-ports-regression.py")
    assert_true("ubuntu-latest" in text, "the workflow has no Linux job for the Python ports")
    assert_true("windows-latest" in text, "the workflow lost its Windows PowerShell parity job")
    assert_true("--python-only" in text,
                "the Linux job does not skip the PowerShell-bound cases (--python-only)")
    assert_true("python -B" in text or "python3 -B" in text,
                "the workflow runs Python without -B, so CI writes __pycache__ into the tree")
    assert_true("lxml" in text, "the workflow never installs the lxml dependency of the ports")
    # A YAML parser is the real gate; fall back to a structural check when absent.
    try:
        import yaml  # noqa: PLC0415 - optional on the developer machine
    except ImportError:
        assert_true(text.lstrip().startswith("name:"), "workflow does not start with a name: key")
        return
    document = yaml.safe_load(text)
    jobs = document.get("jobs") or {}
    runners = {name: job.get("runs-on") for name, job in jobs.items()}
    assert_true("windows-latest" in runners.values(), f"no windows job: {runners}")
    assert_true("ubuntu-latest" in runners.values(), f"no linux job: {runners}")


# ---------------------------------------------------------------- packaging

@case("packaging: install ships remove-form.py, tracks it, and the installed copy runs", needs_powershell=True)
def _(work):
    """The skill tree is copied verbatim by Invoke-PlaceSkill, so a new tool file
    needs no installer change - but "needs no change" is exactly the kind of claim
    that rots silently. Install into a clean project and check the real output."""
    host = find_powershell_host()
    if not host:
        raise CaseSkipped("no PowerShell host on PATH (pwsh / powershell.exe)")

    project = os.path.join(work, "project")
    os.makedirs(project, exist_ok=True)
    installer = os.path.join(REPO_ROOT, "install.ps1")
    proc = subprocess.run(
        [host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", installer, "init",
         "-Tools", "claude-code", "-ProjectRoot", project, "-Source", REPO_ROOT,
         "-NonInteractive", "-AssumeYes", "-McpMode", "managed"],
        cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert_equal(0, proc.returncode, f"installer exit code (stderr: {proc.stderr[-800:]})")

    rel = ".claude/skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.py"
    installed = os.path.join(project, *rel.split("/"))
    assert_true(os.path.isfile(installed), f"installer did not ship the Python entry point: {rel}")
    with open(installed, "rb") as handle:
        installed_bytes = handle.read()
    with open(REMOVE_FORM_PY, "rb") as handle:
        source_bytes = handle.read()
    assert_equal(base64.b64encode(source_bytes), base64.b64encode(installed_bytes),
                 "installed remove-form.py differs from the source copy")

    manifest_path = os.path.join(project, ".ai-rules.json")
    assert_true(os.path.isfile(manifest_path), "installer wrote no .ai-rules.json manifest")
    with open(manifest_path, "rb") as handle:
        manifest = json.loads(handle.read().decode("utf-8-sig"))
    assert_true(rel in manifest.get("files", {}),
                f"manifest does not track the Python entry point: {rel}")

    # The MIT notice has to travel with the distribution the installer produces,
    # not only with the source repository.
    notice_rel = ".claude/skills/1c-metadata-manage/NOTICE.md"
    notice = os.path.join(project, *notice_rel.split("/"))
    assert_true(os.path.isfile(notice), f"installer did not ship the upstream notice: {notice_rel}")
    with open(notice, "rb") as handle:
        installed_notice = handle.read()
    with open(os.path.join(REPO_ROOT, *UPSTREAM_NOTICE_REL.split("/")), "rb") as handle:
        source_notice = handle.read()
    assert_equal(base64.b64encode(source_notice), base64.b64encode(installed_notice),
                 "installed NOTICE.md differs from the source copy")
    assert_true(notice_rel in manifest.get("files", {}),
                f"manifest does not track the upstream notice: {notice_rel}")

    # The installed copy is the one users actually run.
    sandbox = os.path.join(work, "installed-run")
    copy_fixture("epf-with-form", sandbox)
    dry = run_python_tool(
        installed,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox, "-DryRun"],
        sandbox,
    )
    assert_equal(0, dry["exit_code"], f"installed copy dry-run (stderr: {dry['stderr']})")
    refused = run_python_tool(
        installed,
        ["-ObjectName", "Obrabotka", "-FormName", "MainForm", "-SrcDir", sandbox],
        sandbox,
    )
    assert_equal(2, refused["exit_code"], f"installed copy without -Force (stderr: {refused['stderr']})")


# ---------------------------------------------------------------- form-compile: events
#
# Upstream accepts three spellings of the same thing and silently drops one of
# them: a standalone ``handlers`` map compiles happily and produces no event at
# all, and ``OnEditEnd`` is misspelled in the suffix map, so its auto-named
# handler falls through to the literal fallback. Neither defect shows up in an
# exit code or in "the form loads" - only the emitted XML shows them, so every
# case below asserts on parsed ``Table/Events/Event`` pairs.

FORM_DSL_AUTO_ACTIVATE = "ТПриАктивизацииСтроки"
FORM_DSL_AUTO_EDITEND = "ТПриОкончанииРедактирования"
FORM_DSL_TABLE = "Т"

# name -> (element keys, expected [(event, handler)] in the compiled Form.xml)
EVENT_ACCEPTED = OrderedDict((
    ("canonical events", ({"events": {"OnActivateRow": "TActivate"}},
                          [("OnActivateRow", "TActivate")])),
    ("legacy on + handlers", ({"on": ["OnActivateRow"], "handlers": {"OnActivateRow": "TActivate"}},
                              [("OnActivateRow", "TActivate")])),
    ("standalone handlers", ({"handlers": {"OnActivateRow": "TActivate"}},
                             [("OnActivateRow", "TActivate")])),
    ("on only, auto-named", ({"on": ["OnActivateRow"]},
                             [("OnActivateRow", FORM_DSL_AUTO_ACTIVATE)])),
    ("events with a null handler", ({"events": {"OnActivateRow": None}},
                                    [("OnActivateRow", FORM_DSL_AUTO_ACTIVATE)])),
    ("OnEditEnd auto-name", ({"events": {"OnEditEnd": None}},
                             [("OnEditEnd", FORM_DSL_AUTO_EDITEND)])),
))

# name -> element keys that must be refused with a non-zero exit and no output file
EVENT_REFUSED = OrderedDict((
    ("events and on together", {"events": {"OnActivateRow": "A"}, "on": ["OnActivateRow"]}),
    ("events and handlers together", {"events": {"OnActivateRow": "A"},
                                      "handlers": {"OnActivateRow": "A"}}),
    ("an unknown event name", {"events": {"OnEndEdit": None}}),
    ("a handlers key absent from on", {"on": ["OnActivateRow"], "handlers": {"OnEditEnd": "X"}}),
))


def table_events(path):
    """``[(event name, handler)]`` of the compiled Table, parsed - not grepped.

    A substring assertion would pass on a handler that landed in a comment or on
    the wrong element; the defect pinned here is exactly "the XML looks fine but
    the event is not in it"."""
    if not os.path.exists(path):
        return None
    pairs = []
    for element in ElementTree.parse(path).getroot().iter():
        if element.tag.rsplit("}", 1)[-1] != "Table":
            continue
        for child in element:
            if child.tag.rsplit("}", 1)[-1] != "Events":
                continue
            for event in child:
                if event.tag.rsplit("}", 1)[-1] != "Event":
                    continue
                pairs.append((event.get("name"), (event.text or "").strip()))
    return pairs


def compile_form(script, work, tag, element_keys):
    """Compile a one-table form whose single element carries *element_keys*."""
    directory = os.path.join(work, "fc-" + re.sub(r"[^A-Za-z0-9]+", "-", tag))
    os.makedirs(directory, exist_ok=True)
    source = os.path.join(directory, "input.json")
    out = os.path.join(directory, "Form.xml")
    element = OrderedDict((("table", FORM_DSL_TABLE), ("columns", [])))
    element.update(element_keys)
    with open(source, "w", encoding="utf-8") as handle:
        json.dump({"title": "Test", "elements": [element], "attributes": [], "commands": []},
                  handle, ensure_ascii=False)
    runner = run_python_tool if script.endswith(".py") else run_powershell_tool
    return runner(script, ["-JsonPath", source, "-OutputPath", out], directory), out


@case("form-compile: every accepted event spelling reaches Form.xml with the right handler")
def _(work):
    for tag, (keys, expected) in EVENT_ACCEPTED.items():
        run, out = compile_form(FORM_COMPILE_PY, work, tag, keys)
        assert_equal(0, run["exit_code"], f"{tag}: exit code (stderr: {run['stderr'][-400:]})")
        assert_equal(expected, table_events(out), f"{tag}: compiled Table events")


@case("form-compile: an ambiguous or unknown event spelling is refused before Form.xml exists")
def _(work):
    for tag, keys in EVENT_REFUSED.items():
        run, out = compile_form(FORM_COMPILE_PY, work, tag, keys)
        assert_true(run["exit_code"] != 0,
                    f"{tag}: expected a non-zero exit, got 0 (events: {table_events(out)})")
        assert_true(not os.path.exists(out),
                    f"{tag}: refused but still wrote {out} - the refusal is not pre-mutation")


@case("form-compile events parity: PowerShell resolves and refuses identically",
      needs_powershell=True)
def _(work):
    for tag, (keys, expected) in EVENT_ACCEPTED.items():
        run, out = compile_form(FORM_COMPILE_PS1, work, "ps-" + tag, keys)
        assert_equal(0, run["exit_code"], f"ps {tag}: exit code (stderr: {run['stderr'][-400:]})")
        assert_equal(expected, table_events(out), f"ps {tag}: compiled Table events")
    for tag, keys in EVENT_REFUSED.items():
        run, out = compile_form(FORM_COMPILE_PS1, work, "ps-" + tag, keys)
        assert_true(run["exit_code"] != 0,
                    f"ps {tag}: expected a non-zero exit, got 0 (events: {table_events(out)})")
        assert_true(not os.path.exists(out), f"ps {tag}: refused but still wrote {out}")


# ------------------------------------------------- meta-edit: add-form and the validator gate


def broken_skill_tree(work, name, mutate):
    """A private copy of the tool tree, damaged by *mutate*, so a case can run the
    real entry point with a missing / failing validator next to it."""
    root = os.path.join(work, name)
    shutil.copytree(TOOLS_DIR, root)
    mutate(root)
    return root


def catalog_target(work, name):
    directory = os.path.join(work, name)
    copy_fixture("config-dump", directory)
    return directory, os.path.join(directory, "Catalogs", "TestCatalog.xml")


@case("meta-edit: add-form is refused before any mutation and names form-add instead")
def _(work):
    directory, target = catalog_target(work, "add-form-refusal")
    before = snapshot_tree(directory)
    run = run_python_tool(
        META_EDIT_PY, ["-ObjectPath", target, "-Operation", "add-form", "-Value", "TestForm"],
        directory)
    assert_equal(2, run["exit_code"], f"add-form must exit 2 (stderr: {run['stderr'][-400:]})")
    assert_tree_identical(before, snapshot_tree(directory), "refused add-form")
    assert_true("form-add" in run["stderr"],
                f"the refusal does not point at form-add: {run['stderr'][-400:]}")
    assert_true("form-add.py" in run["stderr"],
                "the refusal names no Python entry point to use instead")


@case("support: meta-edit add-template refuses inline and mixed JSON before mutation")
def _(work):
    directory, target = catalog_target(work, "add-template-refusal")
    definition = write_definition(directory, {
        "modify": {"properties": {"Comment": "must not apply"}},
        "\u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c": {"\u043c\u0430\u043a\u0435\u0442\u044b": ["Print"]},
    })
    before = snapshot_tree(directory)
    for arguments in (["-Operation", "add-template", "-Value", "Print"],
                      ["-DefinitionFile", definition]):
        run = run_python_tool(META_EDIT_PY, ["-ObjectPath", target, *arguments], directory)
        assert_equal(2, run["exit_code"], f"add-template refusal: {run['stdout'][-400:]}")
        assert_tree_identical(before, snapshot_tree(directory), "refused add-template")
        assert_true("add-template.ps1" in run["stderr"] and "TemplateType" in run["stderr"],
                    "missing actionable template command")


# Every spelling the production dispatcher resolves to the "add" operation, and
# every spelling it resolves to the "forms" child type. The gate has to refuse all
# of them: they are not exotic input, they are what meta-edit documents and what
# resolve_operation_key / resolve_child_type_key already accept.
ADD_FORM_SPELLINGS = [
    ("add", "forms"),
    ("Add", "forms"),
    ("ADD", "Forms"),
    ("\u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c", "forms"),
    ("\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c", "\u0444\u043e\u0440\u043c\u044b"),
    (" add ", "\u0424\u043e\u0440\u043c\u044b"),
]


def write_definition(directory, payload):
    path = os.path.join(directory, "definition.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return path


def assert_add_form_refused(script, runner, work, label, prefix):
    """Every accepted spelling exits 2 with the tree byte-identical."""
    for index, (operation, child) in enumerate(ADD_FORM_SPELLINGS):
        directory, target = catalog_target(work, f"{prefix}-{index}")
        definition = write_definition(directory, {operation: {child: ["ReviewForm"]}})
        before = snapshot_tree(directory)
        run = runner(script, ["-ObjectPath", target, "-DefinitionFile", definition], directory)
        what = f"{label}: {{{operation!r}: {{{child!r}: [...]}}}}"
        assert_equal(2, run["exit_code"],
                     f"{what} was not refused (stdout: {run['stdout'][-300:]!r} "
                     f"stderr: {run['stderr'][-300:]!r})")
        assert_tree_identical(before, snapshot_tree(directory), what)
        assert_true("form-add" in run["stderr"],
                    f"{what}: the refusal does not point at form-add")

    # A mixed definition is refused as a whole: the unrelated half must not be
    # applied on the way to discovering the add-form half.
    directory, target = catalog_target(work, f"{prefix}-mixed")
    definition = write_definition(directory, {
        "modify": {"properties": {"Comment": "regression"}},
        "\u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c": {"forms": ["ReviewForm"]},
    })
    before = snapshot_tree(directory)
    run = runner(script, ["-ObjectPath", target, "-DefinitionFile", definition], directory)
    assert_equal(2, run["exit_code"],
                 f"{label}: a mixed definition was not refused "
                 f"(stdout: {run['stdout'][-300:]!r} stderr: {run['stderr'][-300:]!r})")
    assert_tree_identical(before, snapshot_tree(directory),
                          f"{label}: mixed definition applied its other half")


@case("meta-edit: every accepted spelling of add-form is refused before any mutation")
def _(work):
    """The gate matched the literal key `add` while the dispatcher below it went
    through resolve_operation_key. `{"\u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c": {"forms": [...]}}` therefore walked
    straight past it and wrote the inline FormType=Ordinary descriptor the gate
    exists to prevent - the validator then failed the run, after the damage."""
    assert_add_form_refused(META_EDIT_PY, run_python_tool, work, "python", "alias-py")


@case("meta-edit add-form parity: PowerShell refuses the same spellings", needs_powershell=True)
def _(work):
    assert_add_form_refused(META_EDIT_PS1, run_powershell_tool, work, "powershell", "alias-ps")


@case("meta-edit: a missing validator is refused before the edit is written")
def _(work):
    root = broken_skill_tree(
        work, "skill-no-validator",
        lambda r: os.remove(os.path.join(r, "1c-meta-validate", "scripts", "meta-validate.py")))
    directory, target = catalog_target(work, "no-validator")
    before = snapshot_tree(directory)
    run = run_python_tool(
        os.path.join(root, "1c-meta-edit", "scripts", "meta-edit.py"),
        ["-ObjectPath", target, "-Operation", "add-attribute", "-Value", "RegrFlag: Boolean"],
        directory)
    assert_true(run["exit_code"] != 0,
                f"a missing validator exited 0 (stdout: {run['stdout'][-400:]})")
    assert_tree_identical(before, snapshot_tree(directory), "edit with no validator available")
    assert_true("meta-validate" in run["stderr"],
                f"the refusal does not name the missing validator: {run['stderr'][-400:]}")
    assert_true("[SKIP]" not in run["stdout"] + run["stderr"],
                "a missing validator is still degraded to a [SKIP] instead of a refusal")


@case("meta-edit: -NoValidate is the explicit opt-out and the only one")
def _(work):
    root = broken_skill_tree(
        work, "skill-no-validator-optout",
        lambda r: os.remove(os.path.join(r, "1c-meta-validate", "scripts", "meta-validate.py")))
    directory, target = catalog_target(work, "no-validator-optout")
    before = file_facts(target)
    run = run_python_tool(
        os.path.join(root, "1c-meta-edit", "scripts", "meta-edit.py"),
        ["-ObjectPath", target, "-Operation", "add-attribute", "-Value", "RegrFlag: Boolean",
         "-NoValidate"],
        directory)
    assert_equal(0, run["exit_code"], f"-NoValidate exit code (stderr: {run['stderr'][-400:]})")
    after = file_facts(target)
    assert_true("<Name>RegrFlag</Name>" in after["text"], "-NoValidate did not apply the edit")
    assert_true(before["text"] != after["text"], "the baseline and the result are the same bytes")
    assert_equal(before["bom"], after["bom"], "-NoValidate changed the BOM")


@case("meta-edit: a validator that reports errors propagates its non-zero exit")
def _(work):
    def break_validator(root):
        stub = os.path.join(root, "1c-meta-validate", "scripts", "meta-validate.py")
        with open(stub, "w", encoding="utf-8") as handle:
            handle.write("import sys\nprint('stub validator: refusing')\nsys.exit(3)\n")

    root = broken_skill_tree(work, "skill-failing-validator", break_validator)
    directory, target = catalog_target(work, "failing-validator")
    run = run_python_tool(
        os.path.join(root, "1c-meta-edit", "scripts", "meta-edit.py"),
        ["-ObjectPath", target, "-Operation", "add-attribute", "-Value", "RegrFlag: Boolean"],
        directory)
    assert_true(run["exit_code"] != 0,
                f"a failing validator was summarized as success (stdout: {run['stdout'][-400:]})")
    combined = run["stdout"] + run["stderr"]
    assert_true("--- Running meta-validate ---" in combined,
                f"the validator banner never appeared: {combined[-400:]}")
    assert_true("3" in run["stderr"], f"the child exit code is not reported: {run['stderr'][-400:]}")


@case("meta-edit auto-validation parity: PowerShell runs the validator, never prints [SKIP]",
      needs_powershell=True)
def _(work):
    for label, script, runner in (("ps", META_EDIT_PS1, run_powershell_tool),
                                  ("py", META_EDIT_PY, run_python_tool)):
        directory, target = catalog_target(work, "autovalidate-" + label)
        before = file_facts(target)
        run = runner(script,
                     ["-ObjectPath", target, "-Operation", "add-attribute",
                      "-Value", "RegrFlag: Boolean"], directory)
        assert_equal(0, run["exit_code"], f"{label}: exit code (stderr: {run['stderr'][-400:]})")
        combined = run["stdout"] + run["stderr"]
        assert_true("--- Running meta-validate ---" in combined,
                    f"{label}: the validator was never invoked: {combined[-400:]}")
        assert_true("[SKIP]" not in combined, f"{label}: validation was skipped: {combined[-400:]}")
        after = file_facts(target)
        assert_true(before["text"] != after["text"], f"{label}: baseline and result are identical")
        assert_true("<Name>RegrFlag</Name>" in after["text"], f"{label}: the edit was not applied")
        assert_equal(before["bom"], after["bom"], f"{label}: BOM changed")
        # The edit adds lines, so the LF count must grow - what may not change is
        # the EOL *style*: not one CRLF may appear in an LF dump.
        assert_equal(before["crlf"], after["crlf"], f"{label}: CRLF crept into an LF dump")
        assert_true(after["lone_lf"] > before["lone_lf"], f"{label}: the edit added no lines")


# ---------------------------------------------------------------- meta-validate: form checks

INLINE_FORM_DESCRIPTOR = (
    "\t\t\t<Form uuid=\"11111111-1111-1111-1111-111111111111\">\n"
    "\t\t\t\t<Properties>\n"
    "\t\t\t\t\t<Name>BadForm</Name>\n"
    "\t\t\t\t\t<FormType>Ordinary</FormType>\n"
    "\t\t\t\t</Properties>\n"
    "\t\t\t</Form>\n"
)


def inject_child(target, block):
    """Append a raw ChildObjects entry, byte-preserving - the shapes under test
    are exactly the ones a generic child builder emits."""
    with open(target, "rb") as handle:
        raw = handle.read()
    bom = raw[:3] == b"\xef\xbb\xbf"
    text = (raw[3:] if bom else raw).decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("</ChildObjects>", block.replace("\n", eol) + "\t\t</ChildObjects>", 1)
    with open(target, "wb") as handle:
        handle.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def assert_form_check_refuses(script, runner, directory, target, marker, what):
    run = runner(script, ["-ObjectPath", target], directory)
    combined = run["stdout"] + run["stderr"]
    assert_true(run["exit_code"] != 0, f"{what}: the validator exited 0\n{combined[-600:]}")
    assert_true(marker in combined, f"{what}: no {marker} diagnostic\n{combined[-600:]}")


@case("meta-validate: an inline ChildObjects/Form descriptor is rejected (6a)")
def _(work):
    directory, target = catalog_target(work, "validate-inline")
    inject_child(target, INLINE_FORM_DESCRIPTOR)
    assert_form_check_refuses(META_VALIDATE_PY, run_python_tool, directory, target,
                              "6a.", "inline form descriptor")


@case("meta-validate: a form registered without its descriptor file is rejected (6b)")
def _(work):
    directory, target = catalog_target(work, "validate-dangling")
    inject_child(target, "\t\t\t<Form>GhostForm</Form>\n")
    assert_form_check_refuses(META_VALIDATE_PY, run_python_tool, directory, target,
                              "6b.", "dangling form reference")


@case("meta-validate form checks parity: PowerShell rejects the same two shapes",
      needs_powershell=True)
def _(work):
    directory, target = catalog_target(work, "validate-inline-ps")
    inject_child(target, INLINE_FORM_DESCRIPTOR)
    assert_form_check_refuses(META_VALIDATE_PS1, run_powershell_tool, directory, target,
                              "6a.", "ps inline form descriptor")
    directory, target = catalog_target(work, "validate-dangling-ps")
    inject_child(target, "\t\t\t<Form>GhostForm</Form>\n")
    assert_form_check_refuses(META_VALIDATE_PS1, run_powershell_tool, directory, target,
                              "6b.", "ps dangling form reference")


# ---------------------------------------------------------------- form-add: the remediation


def scaffold_facts(directory, form):
    """What the scaffolder actually produced: the registration shape and the files."""
    target = os.path.join(directory, "Catalogs", "TestCatalog.xml")
    root = ElementTree.parse(target).getroot()
    scalar, inline, default = [], 0, []
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local == "ChildObjects":
            for child in element:
                if child.tag.rsplit("}", 1)[-1] != "Form":
                    continue
                nested = list(child)
                inline += len(nested)
                if not nested:
                    scalar.append((child.text or "").strip())
        elif local == "DefaultObjectForm":
            default.append((element.text or "").strip())
    base = os.path.join(directory, "Catalogs", "TestCatalog", "Forms")
    return {
        "scalar": scalar,
        "inline": inline,
        "default": default,
        "descriptor": os.path.isfile(os.path.join(base, form + ".xml")),
        "form_xml": os.path.isfile(os.path.join(base, form, "Ext", "Form.xml")),
        "module": os.path.isfile(os.path.join(base, form, "Ext", "Form", "Module.bsl")),
    }


def run_form_add(script, runner, work, label):
    directory, target = catalog_target(work, "form-add-" + label)
    run = runner(script, ["-ObjectPath", target, "-FormName", "SmokeForm",
                          "-Purpose", "Object", "-SetDefault"], directory)
    assert_equal(0, run["exit_code"],
                 f"{label}: form-add exit code (stderr: {run['stderr'][-400:]})")
    facts = scaffold_facts(directory, "SmokeForm")
    assert_true("SmokeForm" in facts["scalar"],
                f"{label}: the form is not registered as a scalar reference: {facts}")
    assert_equal(0, facts["inline"], f"{label}: the registration carries an inline descriptor")
    assert_true(facts["descriptor"], f"{label}: no Forms/SmokeForm.xml descriptor")
    assert_true(facts["form_xml"], f"{label}: no Ext/Form.xml")
    assert_true(facts["module"], f"{label}: no Ext/Form/Module.bsl")
    assert_equal(["Catalog.TestCatalog.Form.SmokeForm"], facts["default"],
                 f"{label}: -SetDefault did not set DefaultObjectForm")
    return directory, target, facts


@case("form-add: the managed scaffold it writes is accepted by meta-validate")
def _(work):
    directory, target, _facts = run_form_add(FORM_ADD_PY, run_python_tool, work, "py")
    check = run_python_tool(META_VALIDATE_PY, ["-ObjectPath", target], directory)
    assert_equal(0, check["exit_code"],
                 "meta-validate rejected the form-add scaffold: "
                 f"{(check['stdout'] + check['stderr'])[-600:]}")


@case("form-add parity: PowerShell and Python write the same managed scaffold",
      needs_powershell=True)
def _(work):
    ps_dir, ps_target, ps_facts = run_form_add(FORM_ADD_PS1, run_powershell_tool, work, "ps")
    _dir, _target, py_facts = run_form_add(FORM_ADD_PY, run_python_tool, work, "py-parity")
    assert_equal(ps_facts, py_facts, "the two runtimes disagree on the scaffold")
    check = run_powershell_tool(META_VALIDATE_PS1, ["-ObjectPath", ps_target], ps_dir)
    assert_equal(0, check["exit_code"],
                 "PowerShell meta-validate rejected the PowerShell scaffold: "
                 f"{(check['stdout'] + check['stderr'])[-600:]}")


# ---------------------------------------------------------------- form-add: XML safety

# Ordinary user-facing strings, not attacks: an ampersand between two words, a
# quoted phrase, an angle-bracketed one. Every one of them used to be interpolated
# into the descriptor verbatim.
XML_UNSAFE_SYNONYMS = [
    "A & B",
    "\u041e\u0442\u0447\u0451\u0442 \"\u0418\u0442\u043e\u0433\u0438\" & \u043a\u043e\u043f\u0438\u044f",
    "<\u0421\u043f\u0438\u0441\u043e\u043a> & '\u0432\u044b\u0431\u043e\u0440'",
]


def descriptor_identity(path):
    """Parse the descriptor for real and read back what it declares."""
    tree = ElementTree.parse(path)
    root = tree.getroot()
    name, synonym = None, None
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag == "Name" and name is None:
            name = (node.text or "").strip()
        if tag == "content" and synonym is None:
            synonym = node.text or ""
    return {"name": name, "synonym": synonym}


def assert_xml_safe_scaffold(script, runner, validator, validator_runner, work, label):
    for index, synonym in enumerate(XML_UNSAFE_SYNONYMS):
        directory, target = catalog_target(work, f"synonym-{label}-{index}")
        run = runner(script, ["-ObjectPath", target, "-FormName", "ReviewForm",
                              "-Synonym", synonym], directory)
        assert_equal(0, run["exit_code"],
                     f"{label}: form-add refused an ordinary synonym {synonym!r} "
                     f"(stderr: {run['stderr'][-300:]})")
        descriptor = os.path.join(directory, "Catalogs", "TestCatalog", "Forms",
                                  "ReviewForm.xml")
        try:
            identity = descriptor_identity(descriptor)
        except ElementTree.ParseError as exc:
            fail(f"{label}: synonym {synonym!r} produced an unparseable descriptor: {exc}")
        assert_equal("ReviewForm", identity["name"], f"{label}: descriptor Name")
        assert_equal(synonym, identity["synonym"],
                     f"{label}: the synonym did not survive escaping intact")

        check = validator_runner(validator, ["-ObjectPath", target], directory)
        assert_equal(0, check["exit_code"],
                     f"{label}: meta-validate rejected a correctly escaped scaffold: "
                     f"{(check['stdout'] + check['stderr'])[-400:]}")


@case("form-add: XML metacharacters in user text produce a parseable descriptor")
def _(work):
    """`-Synonym "A & B"` exited 0 and wrote a descriptor no XML parser accepts
    (`xmlParseEntityRef: no name`), and meta-validate passed the object because it
    only checked that the descriptor path existed."""
    assert_xml_safe_scaffold(FORM_ADD_PY, run_python_tool, META_VALIDATE_PY,
                             run_python_tool, work, "python")


@case("form-add XML safety parity: PowerShell escapes the same user text",
      needs_powershell=True)
def _(work):
    assert_xml_safe_scaffold(FORM_ADD_PS1, run_powershell_tool, META_VALIDATE_PS1,
                             run_powershell_tool, work, "powershell")


@case("form-add XML safety parity: both runtimes write the same escaped descriptor",
      needs_powershell=True)
def _(work):
    descriptors = {}
    for label, script, runner in (("py", FORM_ADD_PY, run_python_tool),
                                  ("ps", FORM_ADD_PS1, run_powershell_tool)):
        directory, target = catalog_target(work, "escaped-" + label)
        run = runner(script, ["-ObjectPath", target, "-FormName", "ReviewForm",
                              "-Synonym", "A & B <\"x\">"], directory)
        assert_equal(0, run["exit_code"], f"{label}: form-add (stderr: {run['stderr'][-300:]})")
        path = os.path.join(directory, "Catalogs", "TestCatalog", "Forms", "ReviewForm.xml")
        text = file_facts(path)["text"]
        descriptors[label] = re.search(r"(?s)<Synonym>.*?</Synonym>", text).group(0)
    assert_equal(repr(descriptors["ps"]), repr(descriptors["py"]),
                 "the two runtimes escape the synonym differently")


def break_descriptor(path, replacement):
    """Rewrite a descriptor's bytes, keeping BOM and EOL, so the case controls
    exactly what the validator is handed."""
    facts = file_facts(path)
    text = facts["text"].replace("<Name>ReviewForm</Name>", replacement, 1)
    with open(path, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))


def assert_descriptor_validated(script, runner, validator, validator_runner, work, label):
    # Control: an untouched scaffold still passes. A validator that rejects
    # everything would satisfy the negative half on its own.
    directory, target = catalog_target(work, f"descriptor-ok-{label}")
    run = runner(script, ["-ObjectPath", target, "-FormName", "ReviewForm"], directory)
    assert_equal(0, run["exit_code"], f"{label}: form-add (stderr: {run['stderr'][-300:]})")
    check = validator_runner(validator, ["-ObjectPath", target], directory)
    assert_equal(0, check["exit_code"],
                 f"{label}: a valid scaffold was rejected: "
                 f"{(check['stdout'] + check['stderr'])[-400:]}")

    # Malformed: the shape an unescaped user string produced.
    directory, target = catalog_target(work, f"descriptor-broken-{label}")
    runner(script, ["-ObjectPath", target, "-FormName", "ReviewForm"], directory)
    descriptor = os.path.join(directory, "Catalogs", "TestCatalog", "Forms", "ReviewForm.xml")
    break_descriptor(descriptor, "<Name>ReviewForm</Name>\n\t\t\t<Raw>A & B</Raw>")
    check = validator_runner(validator, ["-ObjectPath", target], directory)
    combined = check["stdout"] + check["stderr"]
    assert_true(check["exit_code"] != 0,
                f"{label}: an unparseable descriptor was accepted: {combined[-400:]}")
    assert_true("6c." in combined, f"{label}: no 6c diagnostic: {combined[-400:]}")

    # Mismatched identity: a descriptor that parses but describes another form.
    directory, target = catalog_target(work, f"descriptor-mismatch-{label}")
    runner(script, ["-ObjectPath", target, "-FormName", "ReviewForm"], directory)
    descriptor = os.path.join(directory, "Catalogs", "TestCatalog", "Forms", "ReviewForm.xml")
    break_descriptor(descriptor, "<Name>OtherForm</Name>")
    check = validator_runner(validator, ["-ObjectPath", target], directory)
    combined = check["stdout"] + check["stderr"]
    assert_true(check["exit_code"] != 0,
                f"{label}: a descriptor for another form was accepted: {combined[-400:]}")
    assert_true("6d." in combined, f"{label}: no 6d diagnostic: {combined[-400:]}")


@case("meta-validate: a form descriptor is parsed and matched, not just counted")
def _(work):
    assert_descriptor_validated(FORM_ADD_PY, run_python_tool, META_VALIDATE_PY,
                                run_python_tool, work, "python")


@case("meta-validate descriptor parity: PowerShell parses and matches it too",
      needs_powershell=True)
def _(work):
    assert_descriptor_validated(FORM_ADD_PS1, run_powershell_tool, META_VALIDATE_PS1,
                                run_powershell_tool, work, "powershell")


# ------------------------------------------ 2026-09-25: vendor-shaped defaults and new checks
#
# Pinned for both runtimes: form-compile from-object gives a document choice form
# ChoiceMode and a document form the posting defaults, binds Description only when
# DescriptionLength > 0 and refuses enum values the platform does not have;
# form-add refuses a non-identifier -FormName and names an information register's
# object-form main attribute "Запись"; meta-validate rejects the shapes of checks
# 1e, 2, 6f, 6g, 8, 12 and 16a with the same diagnostics in both runtimes.

MINIMAL_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core"'
    ' xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.17">\n'
    '\t<Document uuid="5e0c6f3a-1b1d-4c8e-9a51-0d3c2b7a9e11">\n'
    '\t\t<Properties>\n'
    '\t\t\t<Name>TestDocument</Name>\n'
    '\t\t\t<NumberType>String</NumberType>\n'
    '\t\t</Properties>\n'
    '\t\t<ChildObjects/>\n'
    '\t</Document>\n'
    '</MetaDataObject>\n'
)

MINIMAL_REGISTER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core"'
    ' xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.17">\n'
    '\t<InformationRegister uuid="7a2f4c1e-3d5b-4e6f-8a9b-1c2d3e4f5a6b">\n'
    '\t\t<Properties>\n'
    '\t\t\t<Name>TestRegister</Name>\n'
    '\t\t\t<DefaultRecordForm/>\n'
    '\t\t</Properties>\n'
    '\t\t<ChildObjects/>\n'
    '\t</InformationRegister>\n'
    '</MetaDataObject>\n'
)

OBJECT_PREFIX = "Объект."   # "Объект."
LIST_PREFIX = "Список."      # "Список."
RECORD_NAME = "Запись"       # "Запись"


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + text.encode("utf-8"))


def edit_text(path, old, new):
    facts = file_facts(path)
    assert_true(old in facts["text"], f"fixture edit: '{old}' not found in {path}")
    write_text(path, facts["text"].replace(old, new, 1))


def form_facts(path):
    """Root properties, table ChoiceMode flags and DataPaths of a compiled form."""
    root = ElementTree.parse(path).getroot()
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    props = {local(c): (c.text or "").strip() for c in root if len(c) == 0}
    choice = [(c.text or "").strip() for el in root.iter() if local(el) == "Table"
              for c in el if local(c) == "ChoiceMode"]
    paths = {(el.text or "").strip() for el in root.iter() if local(el) == "DataPath"}
    return {"props": props, "choice": choice, "paths": paths}


def compile_from_object(script, directory, kind_dir, object_file, form, purpose):
    runner = run_python_tool if script.endswith(".py") else run_powershell_tool
    out = os.path.join(directory, kind_dir, object_file[:-4], "Forms", form, "Ext", "Form.xml")
    run = runner(script, ["-FromObject", "-OutputPath", out, "-ObjectPath",
                          os.path.join(directory, kind_dir, object_file), "-Purpose", purpose], directory)
    assert_equal(0, run["exit_code"], f"{form}: from-object exit code (stderr: {run['stderr'][-400:]})")
    return form_facts(out)


def assert_from_object_defaults(script, work, label):
    directory = os.path.join(work, "from-object-" + label)
    copy_fixture("config-dump", directory)
    write_text(os.path.join(directory, "Documents", "TestDocument.xml"), MINIMAL_DOCUMENT)

    choice = compile_from_object(script, directory, "Documents", "TestDocument.xml", "ChoiceForm", "Choice")
    assert_equal(["true"], choice["choice"], f"{label}: document choice form ChoiceMode")
    assert_equal("LockOwnerWindow", choice["props"].get("WindowOpeningMode"),
                 f"{label}: document choice form WindowOpeningMode")
    item = compile_from_object(script, directory, "Documents", "TestDocument.xml", "ItemForm", "Item")
    for prop, value in (("AutoTime", "CurrentOrLast"), ("UsePostingMode", "Auto"), ("RepostOnWrite", "true")):
        assert_equal(value, item["props"].get(prop), f"{label}: document form {prop}")

    edit_text(os.path.join(directory, "Catalogs", "TestCatalog.xml"),
              "<DescriptionLength>25</DescriptionLength>", "<DescriptionLength>0</DescriptionLength>")
    catalog_item = compile_from_object(script, directory, "Catalogs", "TestCatalog.xml", "ItemForm", "Item")
    assert_true(OBJECT_PREFIX + "Description" not in catalog_item["paths"],
                f"{label}: a catalog without a description binds it: {sorted(catalog_item['paths'])}")
    assert_true(OBJECT_PREFIX + "Code" in catalog_item["paths"], f"{label}: the code field is gone too")
    catalog_list = compile_from_object(script, directory, "Catalogs", "TestCatalog.xml", "ListForm", "List")
    assert_true(LIST_PREFIX + "Description" not in catalog_list["paths"],
                f"{label}: the list of a catalog without a description binds it")

    source = os.path.join(directory, "bad-enum.json")
    with open(source, "w", encoding="utf-8") as handle:
        json.dump({"title": "T", "properties": {"windowOpeningMode": "Modeless"}, "elements": [],
                   "attributes": []}, handle)
    out = os.path.join(directory, "bad-enum", "Form.xml")
    runner = run_python_tool if script.endswith(".py") else run_powershell_tool
    run = runner(script, ["-JsonPath", source, "-OutputPath", out], directory)
    assert_true(run["exit_code"] != 0, f"{label}: windowOpeningMode=Modeless was accepted")
    assert_true(not os.path.exists(out), f"{label}: refused but still wrote {out}")


@case("form-compile: from-object defaults follow vendor forms, enum values are a closed set")
def _(work):
    assert_from_object_defaults(FORM_COMPILE_PY, work, "py")


@case("form-compile defaults parity: PowerShell writes the same defaults and refusals",
      needs_powershell=True)
def _(work):
    assert_from_object_defaults(FORM_COMPILE_PS1, work, "ps")


def assert_form_add_name_and_record(script, runner, work, label):
    directory, target = catalog_target(work, "form-add-names-" + label)
    before = snapshot_tree(directory)
    for bad in ("..\\Escape", "a/b", "x'y", "1Form"):
        run = runner(script, ["-ObjectPath", target, "-FormName", bad], directory)
        assert_equal(2, run["exit_code"], f"{label}: -FormName {bad!r} exit code")
    assert_tree_identical(before, snapshot_tree(directory), f"{label}: refused -FormName")

    register = os.path.join(directory, "InformationRegisters", "TestRegister.xml")
    write_text(register, MINIMAL_REGISTER)
    run = runner(script, ["-ObjectPath", register, "-FormName", "ObjectForm", "-Purpose", "Object"], directory)
    assert_equal(0, run["exit_code"], f"{label}: register object form (stderr: {run['stderr'][-400:]})")
    form = os.path.join(directory, "InformationRegisters", "TestRegister", "Forms", "ObjectForm", "Ext", "Form.xml")
    names = [a.get("name") for a in ElementTree.parse(form).getroot().iter()
             if a.tag.rsplit("}", 1)[-1] == "Attribute"]
    assert_equal([RECORD_NAME], names, f"{label}: register object-form main attribute")


@case("form-add: a non-identifier -FormName is refused, a register's object form uses Запись")
def _(work):
    assert_form_add_name_and_record(FORM_ADD_PY, run_python_tool, work, "py")


@case("form-add names parity: PowerShell refuses the same names and names the attribute Запись",
      needs_powershell=True)
def _(work):
    assert_form_add_name_and_record(FORM_ADD_PS1, run_powershell_tool, work, "ps")


CLASH_ATTRIBUTE = (
    "\t\t\t<Attribute uuid=\"0b7c9d2e-4f61-4a8b-9c3d-2e1f0a9b8c7d\">\n"
    "\t\t\t\t<Properties>\n"
    "\t\t\t\t\t<Name>Clash</Name>\n"
    "\t\t\t\t\t<Type>\n"
    "\t\t\t\t\t\t<v8:Type>xs:string</v8:Type>\n"
    "\t\t\t\t\t</Type>\n"
    "\t\t\t\t</Properties>\n"
    "\t\t\t</Attribute>\n"
    "\t\t\t<TabularSection uuid=\"1c8d0e3f-5a72-4b9c-8d4e-3f2a1b0c9d8e\">\n"
    "\t\t\t\t<Properties>\n"
    "\t\t\t\t\t<Name>clash</Name>\n"
    "\t\t\t\t</Properties>\n"
    "\t\t\t\t<ChildObjects/>\n"
    "\t\t\t</TabularSection>\n"
)

FOLDER_TYPE_ATTRIBUTE = (
    "\t\t\t<Attribute uuid=\"2d9e1f4a-6b83-4cad-9e5f-4a3b2c1d0e9f\">\n"
    "\t\t\t\t<Properties>\n"
    "\t\t\t\t\t<Name>Link</Name>\n"
    "\t\t\t\t\t<Type>\n"
    "\t\t\t\t\t\t<v8:Type>cfg:Catalogs.TestCatalog</v8:Type>\n"
    "\t\t\t\t\t</Type>\n"
    "\t\t\t\t</Properties>\n"
    "\t\t\t</Attribute>\n"
)


def meta_validate_shapes(work, label):
    """Directory, target and expected marker of every shape the new checks reject."""
    shapes = []

    directory, target = catalog_target(work, f"mv-{label}-1e")
    edit_text(os.path.join(directory, "Configuration.xml"), 'version="2.17"', 'version="2.20"')
    shapes.append(("1e", directory, target))

    directory, target = catalog_target(work, f"mv-{label}-2")
    text = file_facts(target)["text"]
    start = text.index('<xr:GeneratedType name="CatalogList.TestCatalog"')
    end = text.index("</xr:GeneratedType>", start) + len("</xr:GeneratedType>")
    write_text(target, text[:start] + text[end:])
    shapes.append(("2.", directory, target))

    directory, target = catalog_target(work, f"mv-{label}-6f")
    edit_text(target, "<DefaultObjectForm/>", "<DefaultObjectForm>Catalog.TestCatalog.Form.Ghost</DefaultObjectForm>")
    shapes.append(("6f.", directory, target))

    directory, target = catalog_target(work, f"mv-{label}-6g")
    run = run_python_tool(FORM_ADD_PY, ["-ObjectPath", target, "-FormName", "ItemForm"], directory)
    assert_equal(0, run["exit_code"], f"{label}: form-add for 6g (stderr: {run['stderr'][-300:]})")
    edit_text(target, "<DescriptionLength>25</DescriptionLength>", "<DescriptionLength>0</DescriptionLength>")
    edit_text(os.path.join(directory, "Catalogs", "TestCatalog", "Forms", "ItemForm", "Ext", "Form.xml"),
              "<ChildItems/>",
              "<ChildItems>\n\t\t<InputField name=\"Name\" id=\"1\">\n\t\t\t<DataPath>" + OBJECT_PREFIX
              + "Description</DataPath>\n\t\t</InputField>\n\t</ChildItems>")
    shapes.append(("6g.", directory, target))

    directory, target = catalog_target(work, f"mv-{label}-8")
    inject_child(target, CLASH_ATTRIBUTE)
    shapes.append(("8.", directory, target))

    directory, target = catalog_target(work, f"mv-{label}-12")
    register = os.path.join(directory, "InformationRegisters", "TestRegister.xml")
    write_text(register, MINIMAL_REGISTER.replace("<DefaultRecordForm/>", "<Periodicity>Day</Periodicity>"))
    shapes.append(("12.", directory, register))

    directory, target = catalog_target(work, f"mv-{label}-16a")
    inject_child(target, FOLDER_TYPE_ATTRIBUTE)
    shapes.append(("16a.", directory, target))
    return shapes


def diagnostics(run):
    return sorted(line.strip() for line in (run["stdout"] + run["stderr"]).splitlines()
                  if line.startswith("[ERROR]") or line.startswith("[WARN]"))


@case("meta-validate: versions, generated types, default forms, names, IR properties, folder types")
def _(work):
    directory, target = catalog_target(work, "mv-clean")
    run = run_python_tool(META_VALIDATE_PY, ["-ObjectPath", target], directory)
    assert_equal(0, run["exit_code"], f"the clean fixture is rejected: {run['stdout'][-400:]}")
    for marker, directory, target in meta_validate_shapes(work, "py"):
        run = run_python_tool(META_VALIDATE_PY, ["-ObjectPath", target], directory)
        combined = run["stdout"] + run["stderr"]
        assert_true(run["exit_code"] != 0, f"{marker}: the validator exited 0\n{combined[-600:]}")
        assert_true(f"[ERROR] {marker}" in combined, f"no [ERROR] {marker} diagnostic\n{combined[-600:]}")


@case("meta-validate new checks parity: PowerShell prints the same diagnostics",
      needs_powershell=True)
def _(work):
    for marker, directory, target in meta_validate_shapes(work, "parity"):
        py = run_python_tool(META_VALIDATE_PY, ["-ObjectPath", target], directory)
        ps = run_powershell_tool(META_VALIDATE_PS1, ["-ObjectPath", target], directory)
        assert_equal(py["exit_code"], ps["exit_code"], f"{marker}: exit codes differ")
        assert_equal(diagnostics(py), diagnostics(ps), f"{marker}: diagnostics differ")


# ---------------------------------------------------------------- the five shipped ports

PORTED_COMMANDS = OrderedDict((
    ("form-compile", "1c-form-compile"),
    ("form-add", "1c-form-scaffold"),
    ("remove-form", "1c-form-scaffold"),
    ("meta-edit", "1c-meta-edit"),
    ("meta-validate", "1c-meta-validate"),
))


@case("ports: exactly the five documented commands have a Python peer, and each one runs")
def _(work):
    """The scope claim is itself a gate. Every command documented as ported must
    have a runnable entry point, and nothing else under ``tools/`` may have one -
    so the day a sixth port lands, the docs are forced to grow with it."""
    found = {}
    for entry in sorted(os.listdir(TOOLS_DIR)):
        scripts = os.path.join(TOOLS_DIR, entry, "scripts")
        if not os.path.isdir(scripts):
            continue
        for name in sorted(os.listdir(scripts)):
            if name.endswith(".py"):
                found[name[:-3]] = entry
    assert_equal(sorted(PORTED_COMMANDS), sorted(found),
                 "the set of Python ports on disk is not the documented set")
    for stem, tool in PORTED_COMMANDS.items():
        script = os.path.join(TOOLS_DIR, tool, "scripts", stem + ".py")
        assert_true(os.path.isfile(script), f"missing entry point: {tool}/scripts/{stem}.py")
        run = run_python_tool(script, ["--help"], work)
        assert_equal(0, run["exit_code"], f"{stem}.py --help exit (stderr: {run['stderr'][-300:]})")
        assert_true("usage" in run["stdout"].lower(), f"{stem}.py --help printed no usage")


@case("ports: every shipped Python file compiles under the interpreter that runs it")
def _(work):
    import py_compile
    targets = [os.path.join(TOOLS_DIR, tool, "scripts", stem + ".py")
               for stem, tool in PORTED_COMMANDS.items()]
    targets.append(DEV_ENV_PY)
    targets.append(os.path.abspath(__file__))
    for path in targets:
        try:
            py_compile.compile(path, cfile=os.path.join(work, os.path.basename(path) + "c"),
                               doraise=True)
        except py_compile.PyCompileError as exc:
            fail(f"{os.path.relpath(path, REPO_ROOT)} does not compile: {exc}")


@case("licensing: the notice lists every vendored Python port with the upstream pin")
def _(work):
    path = os.path.join(REPO_ROOT, *UPSTREAM_NOTICE_REL.split("/"))
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8-sig")
    assert_true(UPSTREAM_PIN in text, "the notice carries no upstream pin")
    for stem in PORTED_COMMANDS:
        assert_true(f"{stem}.py" in text, f"the notice does not list the port {stem}.py")
    assert_true("dev_env.py" in text, "the notice does not mention the shared helper dev_env.py")


@case("docs: the skill documents the Python runtime for those five commands only")
def _(work):
    path = os.path.join(REPO_ROOT, "content", "skills", "1c-metadata-manage", "SKILL.md")
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8-sig")
    for stem in PORTED_COMMANDS:
        assert_true(f"{stem}.py" in text,
                    f"SKILL.md does not name the ported entry point {stem}.py")
    # The honest half: a tool with no Python peer must not be advertised with one.
    unported = sorted(
        entry for entry in os.listdir(TOOLS_DIR)
        if os.path.isdir(os.path.join(TOOLS_DIR, entry, "scripts"))
        and not any(n.endswith(".py")
                    for n in os.listdir(os.path.join(TOOLS_DIR, entry, "scripts")))
    )
    assert_true(unported, "fixture assumption broken: every tool now has a Python peer")
    for entry in unported:
        for name in os.listdir(os.path.join(TOOLS_DIR, entry, "scripts")):
            if not name.endswith(".ps1"):
                continue
            promised = name[:-4] + ".py"
            assert_true(promised not in text,
                        f"SKILL.md promises {promised}, which does not exist under {entry}")


@case("packaging: install ships all five Python entry points, tracks them, and they run",
      needs_powershell=True)
def _(work):
    host = find_powershell_host()
    if not host:
        raise CaseSkipped("no PowerShell host on PATH (pwsh / powershell.exe)")
    project = os.path.join(work, "project")
    os.makedirs(project, exist_ok=True)
    proc = subprocess.run(
        [host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(REPO_ROOT, "install.ps1"), "init", "-Tools", "claude-code",
         "-ProjectRoot", project, "-Source", REPO_ROOT, "-NonInteractive", "-AssumeYes",
         "-McpMode", "managed"],
        cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert_equal(0, proc.returncode, f"installer exit code (stderr: {proc.stderr[-800:]})")

    with open(os.path.join(project, ".ai-rules.json"), "rb") as handle:
        manifest = json.loads(handle.read().decode("utf-8-sig"))

    installed = {}
    relatives = [f".claude/skills/1c-metadata-manage/tools/{tool}/scripts/{stem}.py"
                 for stem, tool in PORTED_COMMANDS.items()]
    relatives.append(".claude/skills/1c-metadata-manage/tools/_common/dev_env.py")
    for rel in relatives:
        target = os.path.join(project, *rel.split("/"))
        assert_true(os.path.isfile(target), f"the installer did not ship {rel}")
        source = os.path.join(REPO_ROOT, *rel.replace(
            ".claude/skills/1c-metadata-manage/",
            "content/skills/1c-metadata-manage/").split("/"))
        with open(target, "rb") as handle:
            got = handle.read()
        with open(source, "rb") as handle:
            want = handle.read()
        assert_equal(base64.b64encode(want), base64.b64encode(got),
                     f"the installed copy of {rel} differs from the source")
        assert_true(rel in manifest.get("files", {}), f"the manifest does not track {rel}")
        installed[os.path.basename(rel)[:-3]] = target

    # The installed copies are the ones users run: exercise the two contracts this
    # change is about from the installed tree, not from the repository.
    sandbox = os.path.join(work, "installed-compile")
    run, out = compile_form(installed["form-compile"], sandbox, "installed",
                            {"handlers": {"OnActivateRow": "TActivate"}})
    assert_equal(0, run["exit_code"], f"installed form-compile (stderr: {run['stderr'][-400:]})")
    assert_equal([("OnActivateRow", "TActivate")], table_events(out),
                 "the installed form-compile drops a standalone handlers map")

    directory, target = catalog_target(work, "installed-add-form")
    before = snapshot_tree(directory)
    refusal = run_python_tool(
        installed["meta-edit"],
        ["-ObjectPath", target, "-Operation", "add-form", "-Value", "TestForm"], directory)
    assert_equal(2, refusal["exit_code"],
                 f"the installed meta-edit did not refuse add-form: {refusal['stderr'][-400:]}")
    assert_tree_identical(before, snapshot_tree(directory), "installed add-form refusal")


# ---------------------------------------------------------------- run

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--filter", default="*", help="Run only cases whose name matches this wildcard pattern.")
    parser.add_argument("--keep-work-dir", action="store_true", help="Do not delete the temp working directory.")
    parser.add_argument("--python-only", action="store_true",
                        help="Skip cases that need a PowerShell host (Linux CI job).")
    args = parser.parse_args()

    # Case names and failure messages carry Cyrillic 1C names; a redirected
    # Windows stdout (the CI runner) defaults to cp1252 and cannot encode them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

    root = os.path.join(tempfile.gettempdir(), "1c-rules-py-regr-" + uuid.uuid4().hex[:8])
    os.makedirs(root, exist_ok=True)
    print(f"Work dir: {root}")
    print(f"Python:   {sys.version.split()[0]} ({sys.executable})")
    print()

    failures = []
    skipped = []
    index = 0
    for name, body, needs_powershell in CASES:
        if not fnmatch.fnmatch(name, args.filter):
            continue
        index += 1
        work = os.path.join(root, f"case{index:02d}")
        os.makedirs(work, exist_ok=True)
        try:
            if needs_powershell and args.python_only:
                raise CaseSkipped("--python-only: case needs a PowerShell host")
            body(work)
            print(f"[PASS] {name}")
        except CaseSkipped as exc:
            skipped.append(f"{name}: {exc}")
            print(f"[SKIP] {name} - {exc}")
        except Exception as exc:  # noqa: BLE001 - a case may fail in any way
            failures.append(f"{name}: {exc}")
            print(f"[FAIL] {name}")
            print(f"       {exc}")
            if not isinstance(exc, CaseFailure):
                traceback.print_exc()

    print()
    if index == 0:
        print(f"No case matched filter '{args.filter}'.")
        return 1
    passed = index - len(failures) - len(skipped)
    if not failures:
        print(f"{passed}/{index} passed, {len(skipped)} skipped.")
        if not args.keep_work_dir:
            shutil.rmtree(root, ignore_errors=True)
        return 0
    print(f"{passed}/{index} passed, {len(skipped)} skipped, {len(failures)} failed.")
    print(f"Work dir kept for inspection: {root}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
