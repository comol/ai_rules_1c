"""Native Python peers of the local web-*.ps1 tools; Python 3.9+, stdlib only.

The publication/VRD layout follows the vendored PowerShell scripts (MIT,
Nikolay-Shirokov/cc-1c-skills; ../../../NOTICE.md). This implementation manages
only its own foreground Apache process, never a service or an untracked PID.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from xml.etree import ElementTree as ET


class WebError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def require(condition, message, code=2):
    if not condition:
        raise WebError(message, code)


def checked_path(path):
    """Reject links/reparse points in mutable paths, including absent leaves."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not part.is_symlink() and not (getattr(info, "st_file_attributes", 0) & 0x400),
                f"Символическая ссылка или reparse point запрещены: {part}")
    return path


def app_name(value):
    value = value.lower()
    require(bool(re.fullmatch(r"[\w-]{1,64}", value)), "Недопустимое имя публикации")
    require(not re.fullmatch(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", value),
            "Зарезервированное имя публикации")
    return value


def apache_quote(path):
    value = str(path).replace("\\", "/")
    require(not any(c in value for c in ('"', '\r', '\n', '$', '\x00')),
            "Путь содержит недопустимые символы конфигурации Apache")
    return '"' + value + '"'


class Layout:
    def __init__(self, path=None):
        self.root = checked_path(path or Path.cwd() / "tools" / "apache24")
        require(self.root not in (Path(self.root.anchor), Path.home().resolve(), Path.cwd().resolve()),
                "Для Apache нужен отдельный каталог")
        apache_quote(self.root)
        self.conf = checked_path(self.root / "conf" / "httpd.conf")
        self.publish = checked_path(self.root / "publish")
        self.logs = checked_path(self.root / "logs")
        self.state = checked_path(self.logs / "1c-web-python.json")
        for name in ("error.log", "python-start.log", "1c-web-httpd.pid", "httpd.pid"):
            checked_path(self.logs / name)
        candidates = ("bin/httpd.exe",) if os.name == "nt" else ("bin/httpd", "sbin/httpd", "bin/apache2", "sbin/apache2")
        self.exe = next((checked_path(self.root / x) for x in candidates if (self.root / x).is_file()), None)

    def directory(self, name):
        target = checked_path(self.publish / app_name(name))
        require(target.parent == self.publish and target != self.publish, "Путь вышел за каталог публикаций")
        require(not target.exists() or target.is_dir(), "Путь публикации должен быть каталогом")
        return target

    def read_conf(self):
        require(self.conf.is_file(), f"httpd.conf не найден: {self.conf}", 1)
        return self.conf.read_text(encoding="utf-8-sig")

    def command(self, *args, conf=None):
        require(self.exe is not None, f"Apache не найден в {self.root}; установите его отдельно", 1)
        return [str(self.exe), "-d", str(self.root), "-f", str(conf or self.conf), *args]


def block_pattern(name=None):
    start = "# --- 1C: global ---" if name is None else f"# --- 1C Publication: {name} ---"
    end = "# --- End: global ---" if name is None else f"# --- End: {name} ---"
    return re.compile(r"(?m)^" + re.escape(start) + r"\r?\n[\s\S]*?^" + re.escape(end) + r"[ \t]*(?:\r?\n|$)")


def publications(text):
    names = re.findall(r"(?m)^# --- 1C Publication: (.+?) ---[ \t]*$", text)
    require(len(names) == len(set(names)), "Повторяющиеся маркеры публикации")
    for name in names:
        require(app_name(name) == name and len(block_pattern(name).findall(text)) == 1,
                "Повреждённый маркер публикации")
    if "# --- 1C: global ---" in text:
        require(text.count("# --- 1C: global ---") == 1 and len(block_pattern().findall(text)) == 1,
                "Повреждённый глобальный маркер")
    return names


def replace_block(text, name, body):
    pattern = block_pattern(name)
    if pattern.search(text):
        return pattern.sub(lambda _: body + "\n", text)
    return text.rstrip() + "\n\n" + body + "\n"


def project_settings():
    helper = Path(__file__).resolve().parents[2] / "_common" / "dev_env.py"
    if not helper.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("web_dev_env", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {key: module.get_value(key) for key in
              ("PLATFORM_PATH", "INFOBASE_KIND", "INFOBASE_PATH", "IB_USER", "IB_PASSWORD")}
    source = module.find_dev_env_file()
    result["root"] = Path(source).parent if source else Path.cwd()
    return result


def infobase_path(value, root):
    """Absolute file-infobase path; the same rules as web-publish.ps1.

    Surrounding whitespace / quotes and a trailing separator are forgiven; a quote left
    inside, or a drive-relative "C:x", is refused. A relative path is anchored at the
    project root (the .dev.env directory, else the working directory), never at the
    platform's own current directory.
    """
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    require(not re.match(r"^[A-Za-z]:(?![\\/])", text),
            f"Путь к базе относителен текущему каталогу диска ({value}); укажите полный путь")
    require('"' not in text, "Путь к базе содержит кавычку")
    require(bool(text), "Пустой путь к базе")
    path = Path(text)
    if not path.is_absolute():
        path = Path(root) / path
    return str(Path(os.path.abspath(path)))


def fill_connection(args, settings):
    # Any explicitly supplied target excludes target defaults as a whole.
    if all(getattr(args, key) is None for key in ("InfoBasePath", "InfoBaseServer", "InfoBaseRef")):
        kind = (settings.get("INFOBASE_KIND") or "file").lower()
        require(kind in ("file", "server"), "INFOBASE_KIND должен быть file или server")
        value = settings.get("INFOBASE_PATH", "")
        if value and kind == "file":
            args.InfoBasePath = value
        elif value:
            parts = re.split(r"[/\\]", value)
            require(len(parts) == 2 and all(parts), "INFOBASE_PATH серверной базы: сервер/имяБазы")
            args.InfoBaseServer, args.InfoBaseRef = parts
    if args.InfoBasePath:
        args.InfoBasePath = infobase_path(args.InfoBasePath, settings.get("root") or Path.cwd())
    for attribute, setting in (("UserName", "IB_USER"), ("Password", "IB_PASSWORD")):
        if getattr(args, attribute) is None:
            setattr(args, attribute, settings.get(setting, ""))


def platform_module(value=None, explicit=None, settings=None):
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        require(candidate.is_file(), f"Модуль веб-расширения не найден: {candidate}", 1)
        apache_quote(candidate)
        return candidate
    if not value:
        settings = project_settings() if settings is None else settings
        value = settings.get("PLATFORM_PATH")
        if value and not Path(value).is_absolute():
            value = str(settings["root"] / value)
        if not value:
            for folder in (Path.cwd(), *Path.cwd().parents):
                project = folder / ".v8-project.json"
                if project.is_file():
                    try:
                        value = json.loads(project.read_text(encoding="utf-8-sig")).get("v8path")
                    except (OSError, ValueError):
                        pass
                    break
    roots = []
    if value:
        root = Path(value).expanduser().resolve()
        roots = [root.parent if root.is_file() else root]
    elif os.name == "nt":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = Path(os.environ.get(env, "C:/Program Files")) / "1cv8"
            roots.extend(base.glob("*/bin"))
        roots.sort(key=lambda p: tuple(int(x) for x in re.findall(r"\d+", str(p))), reverse=True)
    else:
        # Conventional candidates only; explicit paths cover other distributions.
        for base in (Path("/opt/1cv8/x86_64"), Path("/opt/1cv8")):
            roots.extend(sorted(base.glob("8.*"), reverse=True))
    filename = "wsap24.dll" if os.name == "nt" else "wsap24.so"
    for root in roots:
        for candidate in (root / filename, root / "bin" / filename):
            if candidate.is_file():
                apache_quote(candidate)
                return candidate
    raise WebError("Модуль веб-расширения не найден; укажите -WebExtension или -V8Path / PLATFORM_PATH")


def vrd_content(args, name):
    server = bool(args.InfoBaseServer or args.InfoBaseRef)
    require(bool(args.InfoBasePath) != server and (not server or bool(args.InfoBaseServer and args.InfoBaseRef)),
            "Укажите только -InfoBasePath или пару -InfoBaseServer + -InfoBaseRef")
    parts = [("Srvr", args.InfoBaseServer), ("Ref", args.InfoBaseRef)] if server else [("File", str(Path(args.InfoBasePath).resolve()))]
    if not server:
        require(Path(args.InfoBasePath).is_dir(), "Каталог информационной базы не найден", 1)
    parts += [(key, value) for key, value in (("Usr", args.UserName), ("Pwd", args.Password)) if value]
    for _, value in parts:
        require(not any(c in value for c in ('"', '\r', '\n', '\x00')), "Недопустимый символ параметра соединения")
    ET.register_namespace("", "http://v8.1c.ru/8.2/virtual-resource-system")
    root = ET.Element("{http://v8.1c.ru/8.2/virtual-resource-system}point",
                      {"base": "/" + name, "ib": "".join(f'{key}="{value}";' for key, value in parts)})
    ET.SubElement(root, "standardOdata", {"enable": "true"})
    # Without publishExtensionsByDefault the services of the infobase's extensions are not
    # published: an HTTP service answers 404, a SOAP web service 500 "service not found".
    ET.SubElement(root, "ws", {"pointEnableCommon": "true", "publishExtensionsByDefault": "true"})
    ET.SubElement(root, "httpServices", {"publishByDefault": "true", "publishExtensionsByDefault": "true"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def publish_config(layout, text, name, extension, port):
    publications(text)
    require(1 <= port <= 65535, "Порт должен быть от 1 до 65535")
    require(not re.search(r"(?im)^\s*Include(?:Optional)?\s", text),
            "Конфигурация содержит Include: используйте отдельный Apache без внешних конфигураций")
    outside_global = block_pattern().sub("", text)
    require(not re.search(r"(?im)^\s*LoadModule\s+_1cws_module\s", outside_global),
            "Модуль 1С уже настроен вне управляемого блока")
    # Every unmanaged listener is disabled, including wildcard and IPv6 forms.
    text = re.sub(r"(?im)^([ \t]*Listen[ \t]+[^\n]+)$", r"#\1  # commented by web-publish.py", text)
    # Directive names ignore case; the defined variable name itself does not.
    text = re.sub(r"(?m)^[ \t]*(?i:Define)[ \t]+SRVROOT[ \t]+[^\n]+", lambda _: "Define SRVROOT " + apache_quote(layout.root), text)
    text = re.sub(r"(?im)^[ \t]*ServerRoot[ \t]+[^\n]+", lambda _: "ServerRoot " + apache_quote(layout.root), text)
    global_block = ("# --- 1C: global ---\n"
                    f"Listen 127.0.0.1:{port}\nLoadModule _1cws_module {apache_quote(extension)}\n"
                    f"PidFile {apache_quote(layout.logs / '1c-web-httpd.pid')}\n"
                    f"ErrorLog {apache_quote(layout.logs / 'error.log')}\n# --- End: global ---")
    directory = layout.directory(name)
    pub_block = (f"# --- 1C Publication: {name} ---\nAlias \"/{name}\" {apache_quote(directory)}\n"
                 f"<Directory {apache_quote(directory)}>\n    AllowOverride None\n    Require local\n"
                 f"    SetHandler 1c-application\n    ManagedApplicationDescriptor {apache_quote(directory / 'default.vrd')}\n"
                 f"</Directory>\n# --- End: {name} ---")
    return replace_block(replace_block(text, None, global_block), name, pub_block)


def process_identity(pid):
    """Executable and birth token: stale/reused PIDs never authorize termination."""
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return None
            raise WebError("Не удалось подтвердить владельца процесса; остановка запрещена", 2)
        try:
            code = wintypes.DWORD()
            require(kernel.GetExitCodeProcess(handle, ctypes.byref(code)), "Не удалось проверить процесс")
            if code.value != 259:
                return None
            buffer, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            require(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)), "Не удалось прочитать путь процесса")
            times = [wintypes.FILETIME() for _ in range(4)]
            require(kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in times]), "Не удалось прочитать время процесса")
            birth = str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
            return {"exe": os.path.normcase(os.path.realpath(buffer.value)), "birth": birth}
        finally:
            kernel.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        folder = Path("/proc") / str(pid)
        try:
            fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] == "Z":
                return None
            return {"exe": os.path.realpath(folder / "exe"), "birth": fields[19]}
        except FileNotFoundError:
            return None
    if sys.platform == "darwin":
        result = subprocess.run(["/bin/ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "comm="], capture_output=True, text=True, timeout=5)
        if result.returncode == 1 and not result.stdout.strip():
            return None
        fields = result.stdout.strip().split(None, 5)
        require(result.returncode == 0 and len(fields) == 6, "Не удалось подтвердить процесс через ps")
        return {"exe": os.path.realpath(fields[5]), "birth": " ".join(fields[:5])}
    raise WebError("Проверка владельца процесса на этой ОС не поддерживается", 2)


def managed_process(layout):
    if not layout.state.exists():
        return None
    try:
        state = json.loads(layout.state.read_text(encoding="utf-8"))
        require(type(state.get("pid")) is int and state["pid"] > 1 and state.get("root") == str(layout.root),
                "Повреждён файл владельца процесса")
        require(layout.exe is not None and state.get("exe") == os.path.normcase(os.path.realpath(layout.exe)),
                "Исполняемый файл управляемого Apache изменился")
        identity = process_identity(state["pid"])
        if identity is None:
            return None
        require(identity == {key: state.get(key) for key in ("exe", "birth")},
                "PID принадлежит другому процессу; операция запрещена")
        return state
    except (ValueError, TypeError) as error:
        raise WebError("Повреждён файл владельца процесса", 2) from error


def port_of(text):
    match = re.search(r"(?im)^\s*Listen\s+(?:[^\s]+:)?(\d+)(?:\s+https?)?\s*$", text)
    return int(match[1]) if match else None


def port_open(port):
    if port is None:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def refuse_unmanaged(layout, text):
    state = managed_process(layout)
    pid_files = {layout.logs / "1c-web-httpd.pid", layout.logs / "httpd.pid"}
    for match in re.finditer(r'(?im)^\s*PidFile\s+(?:"([^"]+)"|([^\s#]+))', text):
        value = match[1] or match[2]
        require("$" not in value, "PidFile с подстановкой переменных не поддерживается")
        candidate = Path(value)
        pid_files.add(candidate if candidate.is_absolute() else layout.root / candidate)
    for pid_file in pid_files:
        pid_file = checked_path(pid_file)
        require(layout.root in pid_file.parents, "PID-файл находится вне каталога Apache")
        if not state and pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except ValueError as error:
                raise WebError("Некорректный PID-файл Apache", 2) from error
            require(pid > 1 and process_identity(pid) is None,
                    "Apache запущен без подтверждённого владельца; остановите его штатными средствами")
    require(state is not None or not port_open(port_of(text)),
            "Порт занят неуправляемым процессом; операция запрещена")
    return state


def run_checked(command):
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise WebError(f"Apache завершился с кодом {result.returncode}: {(result.stderr or result.stdout).strip()}")


def test_config(layout, text):
    layout.logs.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="1c-web-check-", suffix=".conf", dir=layout.conf.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        run_checked(layout.command("-t", conf=temporary))
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_write(path, data):
    path = checked_path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".1c-web-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def stop_server(layout):
    state = managed_process(layout)
    if not state:
        return
    pid = state["pid"]
    # Check immediately before sending a signal; no process-name-wide kills.
    require(process_identity(pid) == {key: state[key] for key in ("exe", "birth")}, "Владелец процесса изменился")
    if os.name == "nt":
        run_checked([str(Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"), "/PID", str(pid), "/T", "/F"])
    else:
        require(os.getpgid(pid) == pid, "Apache больше не владеет своей группой процессов")
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while process_identity(pid) is not None and time.monotonic() < deadline:
        time.sleep(0.1)
    require(process_identity(pid) is None, "Apache не остановлен; файлы не изменены", 1)
    layout.state.unlink(missing_ok=True)


def start_server(layout, port):
    require(not port_open(port), f"Порт {port} занят", 1)
    layout.logs.mkdir(parents=True, exist_ok=True)
    with checked_path(layout.logs / "python-start.log").open("ab") as log:
        command = layout.command(*(() if os.name == "nt" else ("-DFOREGROUND",)))
        process = subprocess.Popen(command, cwd=layout.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                   start_new_session=os.name != "nt")
    saved_state = None
    try:
        identity = process_identity(process.pid)
        require(identity is not None and identity["exe"] == os.path.normcase(os.path.realpath(layout.exe)),
                "Не удалось подтвердить запущенный Apache", 1)
        new_state = json.dumps({"root": str(layout.root), "pid": process.pid, **identity}).encode("utf-8")
        atomic_write(layout.state, new_state)
        saved_state = new_state
        deadline = time.monotonic() + 5
        while process.poll() is None and not port_open(port) and time.monotonic() < deadline:
            time.sleep(0.1)
        require(process.poll() is None and port_open(port), "Apache не запущен; см. logs/python-start.log", 1)
    except Exception:
        owns_state = saved_state is not None and layout.state.exists() and layout.state.read_bytes() == saved_state
        if process.poll() is None:
            # The Popen handle itself belongs to the process just created here.
            if owns_state:
                stop_server(layout)
            else:
                process.terminate()
                process.wait(timeout=5)
        if owns_state and layout.state.exists() and layout.state.read_bytes() == saved_state:
            layout.state.unlink()
        raise


def publish(args):
    settings = project_settings()
    fill_connection(args, settings)
    layout = Layout(args.ApachePath)
    old_conf = layout.read_conf()
    module = platform_module(args.V8Path, args.WebExtension, settings)
    name = app_name(args.AppName or re.sub(r"[^\w]", "", Path(args.InfoBasePath).name if args.InfoBasePath else (args.InfoBaseRef or "")))
    vrd = vrd_content(args, name)
    updated = publish_config(layout, old_conf, name, module, args.Port)
    layout.command()  # Resolve dependencies before any mutation, including DryRun.
    directory = layout.directory(name)
    target = checked_path(directory / "default.vrd")
    existed = directory.exists()
    require(not existed or name in publications(old_conf), "Каталог публикации не принадлежит управляемому блоку")
    print(f"Публикация: {name}; конфигурация: {layout.conf}; VRD: {target}")
    if args.DryRun:
        print(f"[DRY-RUN] Без записи и запуска; Listen 127.0.0.1:{args.Port}")
        return
    state = refuse_unmanaged(layout, old_conf)
    require(state is not None or not port_open(args.Port), f"Порт {args.Port} занят", 1)
    test_config(layout, updated)
    backup_conf = layout.conf.read_bytes()
    backup_vrd = target.read_bytes() if target.exists() else None
    if state:
        stop_server(layout)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        atomic_write(target, vrd)
        atomic_write(layout.conf, updated.encode("utf-8"))
        start_server(layout, args.Port)
    except Exception as error:
        atomic_write(layout.conf, backup_conf)
        if backup_vrd is not None:
            atomic_write(target, backup_vrd)
        else:
            target.unlink(missing_ok=True)
        if not existed and directory.exists():
            directory.rmdir()
        if state:
            try:
                start_server(layout, port_of(old_conf))
            except Exception as recovery:
                raise WebError(f"Запуск не удался; файлы восстановлены, повторный запуск также не удался: {recovery}") from error
        raise
    print(f"Готово: http://127.0.0.1:{args.Port}/{name}")


def info(args):
    layout = Layout(args.ApachePath)
    print(f"Apache: {layout.root}")
    if layout.exe is None:
        print("Статус: не установлен")
        return
    text = layout.read_conf()
    state = managed_process(layout)
    port = port_of(text)
    print(f"Статус: {'запущен (PID ' + str(state['pid']) + ')' if state else 'управляемый процесс не запущен'}")
    print(f"Порт: {port or 'не определён'}")
    if not state and port_open(port):
        print("Порт занят; владелец не подтверждён")
    for name in publications(text):
        target = checked_path(layout.directory(name) / "default.vrd")
        services = []
        if target.is_file():
            root = ET.fromstring(target.read_bytes())
            for node in root:
                tag = node.tag.rsplit("}", 1)[-1]
                if tag == "standardOdata" and node.get("enable") == "true":
                    services.append("OData")
                elif tag == "ws" and node.get("pointEnableCommon") == "true":
                    services.append("WS")
                elif tag == "httpServices" and node.get("publishByDefault") == "true":
                    services.append("HTTP")
        # Never print the IB connection string: it can contain credentials.
        print(f"{name}: http://127.0.0.1:{port or '?'}/{name} [{' '.join(services)}]")
    print(f"Журнал Apache: {layout.logs / 'error.log'}")


def stop(args):
    layout = Layout(args.ApachePath)
    text = layout.read_conf() if layout.conf.exists() else ""
    state = refuse_unmanaged(layout, text)
    if args.DryRun:
        print("[DRY-RUN] Остановка управляемого Apache" if state else "Apache не запущен")
        return
    stop_server(layout)
    print("Apache остановлен; публикации сохранены" if state else "Apache не запущен")


def unpublish(args):
    require(bool(args.All) != bool(args.AppName), "Укажите только -AppName или -All")
    layout = Layout(args.ApachePath)
    original = layout.read_conf()
    names = publications(original)
    selected = names if args.All else [app_name(args.AppName)]
    require(all(name in names for name in selected), "Публикация не найдена в управляемых блоках")
    directories = [layout.directory(name) for name in selected]
    # Walk before deleting: an embedded junction/symlink cannot escape the root.
    for directory in directories:
        for folder, subdirs, files in os.walk(directory, followlinks=False):
            for leaf in (*subdirs, *files):
                checked_path(Path(folder) / leaf)
    print(f"Изменить: {layout.conf}")
    for directory in directories:
        print(f"Удалить: {directory}")
    if args.DryRun:
        print("[DRY-RUN] Файлы и процессы не изменены")
        return
    require(args.Force, "Удаление требует -Force; сначала выполните -DryRun")
    if not selected:
        print("Нет публикаций для удаления")
        return
    updated = original
    for name in selected:
        updated = block_pattern(name).sub("", updated)
    remaining = publications(updated)
    if not remaining:
        updated = block_pattern().sub("", updated)
    state = refuse_unmanaged(layout, original)
    if remaining:
        test_config(layout, updated)
    if state:
        stop_server(layout)
    backups = []
    original_bytes = layout.conf.read_bytes()
    try:
        for directory in directories:
            if directory.exists():
                backup = checked_path(layout.publish / (".1c-web-remove-" + uuid.uuid4().hex))
                directory.rename(backup)
                backups.append((directory, backup))
        atomic_write(layout.conf, updated.encode("utf-8"))
        if state and remaining:
            start_server(layout, port_of(updated))
    except Exception as error:
        atomic_write(layout.conf, original_bytes)
        for directory, backup in reversed(backups):
            backup.rename(directory)
        if state:
            try:
                start_server(layout, port_of(original))
            except Exception as recovery:
                raise WebError(f"Удаление отменено, файлы восстановлены; Apache не перезапущен: {recovery}") from error
        raise
    for _, backup in backups:
        shutil.rmtree(checked_path(backup))
    print(f"Публикации удалены: {', '.join(selected)}")


def main(operation, argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=f"1C Apache: {operation} (Python)", allow_abbrev=False)
    parser.add_argument("-ApachePath", "--apache-path", dest="ApachePath")
    if operation != "info":
        parser.add_argument("-DryRun", "--dry-run", dest="DryRun", action="store_true")
    if operation in ("publish", "unpublish"):
        parser.add_argument("-AppName", "--app-name", dest="AppName")
    if operation == "publish":
        for name in ("V8Path", "WebExtension", "InfoBasePath", "InfoBaseServer", "InfoBaseRef", "UserName", "Password"):
            parser.add_argument("-" + name)
        parser.add_argument("-Port", type=int, default=8081)
        parser.add_argument("-Manual", action="store_true", help="Совместимость: Apache всегда устанавливается отдельно")
    if operation == "unpublish":
        parser.add_argument("-All", "--all", dest="All", action="store_true")
        parser.add_argument("-Force", "--force", dest="Force", action="store_true")
    args = parser.parse_args(argv)
    try:
        {"publish": publish, "info": info, "stop": stop, "unpublish": unpublish}[operation](args)
        return 0
    except WebError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return error.code
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f"Ошибка выполнения: {error}", file=sys.stderr)
        return 1
