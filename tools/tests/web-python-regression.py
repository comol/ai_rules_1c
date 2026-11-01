#!/usr/bin/env python3
"""Offline behavioral checks for web Python ports; no Apache, IB or network.

Run: python -B tools/tests/web-python-regression.py
All CLI cases use temp fixtures; lifecycle methods and socket probes are mocked.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content/skills/1c-metadata-manage/tools/1c-web-ops/scripts"
spec = importlib.util.spec_from_file_location("web_common", SCRIPTS / "web_common.py")
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class WebRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="web ports ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.apache = self.base / "Apache Root"
        for name in ("bin", "conf", "logs"):
            (self.apache / name).mkdir(parents=True)
        (self.apache / "bin" / ("httpd.exe" if os.name == "nt" else "httpd")).write_bytes(b"fixture; never execute")
        self.conf = self.apache / "conf/httpd.conf"
        self.conf.write_text('Define SRVROOT "C:/stale"\nServerRoot "${SRVROOT}"\nListen 80\n# Keep unrelated settings\n', encoding="utf-8")
        self.module = self.base / "Platform Root" / "bin" / ("wsap24.dll" if os.name == "nt" else "wsap24.so")
        self.module.parent.mkdir(parents=True)
        self.module.write_bytes(b"fixture")
        self.ib = self.base / "Base & Name"
        self.ib.mkdir()
        self.layout = web.Layout(self.apache)
        self.addCleanup(patch.stopall)
        self.probe = patch.object(web, "port_open", return_value=False).start()
        self.syntax = patch.object(web, "run_checked").start()
        self.real_start = web.start_server
        self.real_stop = web.stop_server
        self.start = patch.object(web, "start_server").start()
        self.stop = patch.object(web, "stop_server").start()

    def run_tool(self, action, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = web.main(action, ["-ApachePath", str(self.apache), *args])
        return code, output.getvalue()

    def publish(self, *args):
        return self.run_tool("publish", "-WebExtension", str(self.module), "-InfoBasePath", str(self.ib), "-AppName", "demo", *args)

    def snapshot(self):
        return {str(p.relative_to(self.apache)): p.read_bytes() for p in self.apache.rglob("*") if p.is_file()}

    def add_publication(self, name="demo"):
        self.assertEqual(0, self.run_tool("publish", "-WebExtension", str(self.module), "-InfoBasePath", str(self.ib), "-AppName", name)[0])

    def tracked(self, pid=991):
        state = {"pid": pid, "root": str(self.apache), "exe": os.path.normcase(os.path.realpath(self.layout.exe)), "birth": "12345"}
        self.layout.state.write_text(json.dumps(state), encoding="utf-8")
        return state

    def test_publish_configuration_is_escaped_local_and_idempotent(self):
        code, output = self.publish("-UserName", "user&name", "-Password", "secret<&value")
        self.assertEqual(0, code, output)
        self.assertNotIn("secret", output)
        text = self.conf.read_text(encoding="utf-8")
        self.assertIn("Listen 127.0.0.1:8081", text)
        self.assertIn("Require local", text)
        self.assertIn("AllowOverride None", text)
        self.assertIn("# Keep unrelated settings", text)
        self.assertNotIn('\nListen 80', text)
        self.assertEqual(1, text.count("# --- 1C Publication: demo ---"))
        root = ET.parse(self.apache / "publish/demo/default.vrd").getroot()
        self.assertEqual("/demo", root.get("base"))
        self.assertIn('Pwd="secret<&value";', root.get("ib"))
        self.assertIn(str(self.ib), root.get("ib"))
        # Extension services are published on both service kinds: without the flag on <ws>
        # a SOAP service of an extension answers 500, on <httpServices> an HTTP one 404.
        ns = "{http://v8.1c.ru/8.2/virtual-resource-system}"
        self.assertEqual("true", root.find(ns + "ws").get("publishExtensionsByDefault"))
        self.assertEqual("true", root.find(ns + "httpServices").get("publishExtensionsByDefault"))
        self.assertEqual(0, self.publish()[0])
        self.assertEqual(text, self.conf.read_text(encoding="utf-8"))
        self.assertEqual(2, self.syntax.call_count)
        command = self.syntax.call_args[0][0]
        self.assertEqual(str(self.layout.exe), command[0])
        self.assertEqual(str(self.apache), command[command.index("-d") + 1])

    def test_publish_dry_run_never_writes_or_launches(self):
        before = self.snapshot()
        self.assertEqual(0, self.publish("-DryRun")[0])
        self.assertEqual(before, self.snapshot())
        self.syntax.assert_not_called()
        self.start.assert_not_called()
        self.stop.assert_not_called()

    def test_mixed_case_directives_keep_only_loopback_listener(self):
        self.conf.write_text('define SRVROOT "C:/stale"\nSeRvErRoOt "${SRVROOT}"\n'
                             'listen 0.0.0.0:80\n  LiStEn [::]:8080\nLISTEN 9090\n'
                             '# lIsTeN 1234\nDefine srvroot "preserve-case-sensitive-variable"\n')
        self.assertEqual(80, web.port_of(self.conf.read_text()))
        code, output = self.publish()
        self.assertEqual(0, code, output)
        text = self.conf.read_text()
        self.assertEqual(["127.0.0.1:8081"], re.findall(r"(?im)^[ \t]*listen[ \t]+([^\n]+)$", text))
        self.assertEqual(8081, web.port_of(text))
        self.assertEqual(8080, web.port_of("  LiStEn [::]:8080\n"))
        self.assertIn("Define SRVROOT " + web.apache_quote(self.apache), text)
        self.assertIn("ServerRoot " + web.apache_quote(self.apache), text)
        self.assertIn('Define srvroot "preserve-case-sensitive-variable"', text)
        self.assertNotIn('"C:/stale"', text)

    def test_unpublish_requires_force_and_dry_run_is_read_only(self):
        self.add_publication()
        before = self.snapshot()
        self.assertEqual(2, self.run_tool("unpublish", "-AppName", "demo")[0])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0, self.run_tool("unpublish", "-AppName", "demo", "-DryRun", "-Force")[0])
        self.assertEqual(before, self.snapshot())

    def test_unpublish_one_retains_other_and_all_removes_global(self):
        self.add_publication()
        self.add_publication("second")
        self.assertEqual(0, self.run_tool("unpublish", "-AppName", "demo", "-Force")[0])
        self.assertFalse((self.apache / "publish/demo").exists())
        self.assertEqual(["second"], web.publications(self.conf.read_text()))
        self.assertTrue((self.apache / "publish/second/default.vrd").exists())
        self.assertEqual(0, self.run_tool("unpublish", "-All", "-Force")[0])
        self.assertNotIn("1C: global", self.conf.read_text())
        self.assertEqual([], list((self.apache / "publish").iterdir()))

    def test_traversal_and_unowned_directory_are_refused(self):
        self.add_publication()
        for name in ("../outside", "demo/../../bad", "demo\\..\\bad", "/root", "C:\\Windows", "CON", "demo."):
            before = self.snapshot()
            self.assertEqual(2, self.run_tool("unpublish", "-AppName", name, "-Force")[0], name)
            self.assertEqual(before, self.snapshot())
        (self.apache / "publish/unknown").mkdir()
        self.assertEqual(2, self.run_tool("publish", "-WebExtension", str(self.module), "-InfoBasePath", str(self.ib), "-AppName", "unknown")[0])
        self.assertEqual(2, self.run_tool("unpublish", "-AppName", "unknown", "-Force")[0])

    def test_corrupt_markers_and_includes_refuse_before_write(self):
        for text in ("# --- 1C Publication: demo ---\nno end\n", "Include conf/extra.conf\nListen 8081\n"):
            self.conf.write_text(text)
            before = self.snapshot()
            self.assertEqual(2, self.publish()[0])
            self.assertEqual(before, self.snapshot())

    def test_invalid_connection_and_port_refuse_before_write(self):
        before = self.snapshot()
        self.assertEqual(2, self.publish("-InfoBaseServer", "server", "-InfoBaseRef", "base")[0])
        self.assertEqual(2, self.publish("-Port", "65536")[0])
        self.assertEqual(2, self.publish("-UserName", 'name";Pwd="injected')[0])
        self.assertEqual(before, self.snapshot())

    def test_config_test_failure_preserves_original(self):
        before = self.snapshot()
        self.syntax.side_effect = web.WebError("configuration rejected")
        self.assertEqual(1, self.publish()[0])
        self.assertEqual(before, self.snapshot())
        self.start.assert_not_called()

    def test_start_failure_rolls_back_publish(self):
        before = self.snapshot()
        self.start.side_effect = web.WebError("start failed")
        self.assertEqual(1, self.publish()[0])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.apache / "publish/demo").exists())

    def test_unpublish_write_failure_restores_directory(self):
        self.add_publication()
        before = self.snapshot()
        original = web.atomic_write
        calls = 0

        def fail_once(path, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("disk full")
            original(path, data)

        with patch.object(web, "atomic_write", side_effect=fail_once):
            code, output = self.run_tool("unpublish", "-All", "-Force")
        self.assertEqual(1, code, output)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(["demo"], sorted(p.name for p in (self.apache / "publish").iterdir()))

    def test_info_lists_services_but_never_password(self):
        self.assertEqual(0, self.publish("-Password", "top-secret")[0])
        before = self.snapshot()
        code, output = self.run_tool("info")
        self.assertEqual(0, code, output)
        self.assertIn("demo:", output)
        self.assertIn("OData WS HTTP", output)
        self.assertNotIn("top-secret", output)
        self.assertEqual(before, self.snapshot())

    def test_pid_reuse_prevents_stop_publish_unpublish(self):
        self.add_publication()
        self.tracked()
        before = self.snapshot()
        with patch.object(web, "process_identity", return_value={"exe": "foreign", "birth": "different"}):
            self.assertEqual(2, self.run_tool("stop")[0])
            self.assertEqual(2, self.publish()[0])
            self.assertEqual(2, self.run_tool("unpublish", "-All", "-Force")[0])
        self.assertEqual(before, self.snapshot())
        self.stop.assert_not_called()

    def test_unmanaged_listener_refuses_mutations(self):
        self.add_publication()
        before = self.snapshot()
        self.probe.return_value = True
        self.assertEqual(2, self.run_tool("stop")[0])
        self.assertEqual(2, self.publish()[0])
        self.assertEqual(2, self.run_tool("unpublish", "-All", "-Force")[0])
        self.assertEqual(before, self.snapshot())
        self.stop.assert_not_called()

    def test_unmanaged_pid_refuses_stop_even_without_listener(self):
        (self.apache / "logs/1c-web-httpd.pid").write_text("992")
        with patch.object(web, "process_identity", return_value={"exe": "foreign", "birth": "different"}):
            self.assertEqual(2, self.run_tool("stop")[0])
        self.stop.assert_not_called()

    def test_legacy_and_configured_pid_files_refuse_unmanaged_stop(self):
        for relative in ("logs/httpd.pid", "logs/custom.pid"):
            pid_file = self.apache / relative
            pid_file.write_text("992")
            if "custom" in relative:
                self.conf.write_text('Listen 0.0.0.0:8081\nPidFile "logs/custom.pid"\n')
            with patch.object(web, "process_identity", return_value={"exe": "foreign", "birth": "different"}):
                self.assertEqual(2, self.run_tool("stop")[0])
            pid_file.unlink()
        self.stop.assert_not_called()

    def test_foreground_start_records_identity_and_uses_argument_array(self):
        identity = {"exe": os.path.normcase(os.path.realpath(self.layout.exe)), "birth": "12345"}
        self.probe.side_effect = [False, True, True]
        with patch.object(web.subprocess, "Popen") as popen, patch.object(web, "process_identity", return_value=identity):
            process = popen.return_value
            process.pid = 991
            process.poll.return_value = None
            self.real_start(self.layout, 8081)
            argv = popen.call_args.args[0]
            self.assertIsInstance(argv, list)
            self.assertIn(str(self.apache), argv)
            self.assertIn(str(self.conf), argv)
            self.assertEqual(os.name != "nt", popen.call_args.kwargs["start_new_session"])
            self.assertNotIn("shell", popen.call_args.kwargs)
        state = json.loads(self.layout.state.read_text())
        self.assertEqual(991, state["pid"])
        self.assertEqual(identity["birth"], state["birth"])

    def test_stop_validated_pid_only_and_clears_state(self):
        state = self.tracked()
        identity = {key: state[key] for key in ("exe", "birth")}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(web, "process_identity", side_effect=[identity, identity, None, None]))
            if os.name != "nt":
                stack.enter_context(patch.object(web.os, "getpgid", return_value=991))
                kill = stack.enter_context(patch.object(web.os, "killpg"))
            self.real_stop(self.layout)
            if os.name == "nt":
                argv = self.syntax.call_args.args[0]
                self.assertEqual(["/PID", "991", "/T", "/F"], argv[1:])
            else:
                kill.assert_called_once_with(991, web.signal.SIGTERM)
        self.assertFalse(self.layout.state.exists())

    def test_failed_start_state_write_cleans_new_process_and_preserves_old_state(self):
        self.tracked(pid=881)
        previous = self.layout.state.read_bytes()
        identity = {"exe": os.path.normcase(os.path.realpath(self.layout.exe)), "birth": "new-birth"}
        with patch.object(web.subprocess, "Popen") as popen, patch.object(web, "process_identity", return_value=identity), \
                patch.object(web, "atomic_write", side_effect=OSError("state write failed")):
            process = popen.return_value
            process.pid = 991
            process.poll.return_value = None
            with self.assertRaisesRegex(OSError, "state write failed"):
                self.real_start(self.layout, 8081)
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)
        self.assertEqual(previous, self.layout.state.read_bytes())
        self.stop.assert_not_called()

    def test_process_identity_reads_this_process_without_mutation(self):
        identity = web.process_identity(os.getpid())
        self.assertEqual(os.path.normcase(os.path.realpath(sys.executable)), identity["exe"])
        self.assertTrue(identity["birth"])

    def test_managed_publish_stops_then_starts_and_stop_dry_run_is_safe(self):
        self.add_publication()
        state = self.tracked()
        identity = {key: state[key] for key in ("exe", "birth")}
        self.start.reset_mock()
        with patch.object(web, "process_identity", return_value=identity):
            self.assertEqual(0, self.run_tool("stop", "-DryRun")[0])
            self.stop.assert_not_called()
            self.assertEqual(0, self.publish()[0])
        self.stop.assert_called_once()
        self.start.assert_called_once()

    def test_platform_dev_env_wins_over_v8_project_and_accepts_install_root(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            (self.base / ".dev.env").write_text(f'PLATFORM_PATH="{self.module.parent.parent}"\n')
            (self.base / ".v8-project.json").write_text('{"v8path":"missing-platform"}')
            self.assertEqual(self.module, web.platform_module())
        finally:
            os.chdir(previous)

    def test_connection_dev_env_defaults_and_cli_precedence(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            (self.base / ".dev.env").write_text(
                f'PLATFORM_PATH="{self.module.parent.parent}"\nINFOBASE_KIND=file\n'
                f'INFOBASE_PATH="{self.ib.name}"\nIB_USER=env-user\nIB_PASSWORD=env-secret\n', encoding="utf-8")
            child = self.base / "nested"
            child.mkdir()
            os.chdir(child)
            self.assertEqual(0, self.run_tool("publish", "-AppName", "from-env")[0])
            root = ET.parse(self.apache / "publish/from-env/default.vrd").getroot()
            self.assertIn(f'File="{self.ib}";', root.get("ib"))
            self.assertIn('Pwd="env-secret";', root.get("ib"))
            code, output = self.run_tool("publish", "-AppName", "server", "-InfoBaseServer", "explicit-server",
                                         "-InfoBaseRef", "explicit-db", "-UserName", "cli-user", "-Password", "")
            self.assertEqual(0, code, output)
            root = ET.parse(self.apache / "publish/server/default.vrd").getroot()
            self.assertEqual('Srvr="explicit-server";Ref="explicit-db";Usr="cli-user";', root.get("ib"))
            self.assertEqual(2, self.run_tool("publish", "-AppName", "incomplete", "-InfoBaseServer", "server")[0])
        finally:
            os.chdir(previous)

    def test_relative_infobase_path_is_anchored_at_dev_env_root(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            (self.base / ".dev.env").write_text("IB_USER=\n", encoding="utf-8")
            child = self.base / "nested"
            child.mkdir()
            os.chdir(child)
            code, output = self.run_tool("publish", "-WebExtension", str(self.module), "-AppName", "rel",
                                         "-InfoBasePath", f' "{self.ib.name}{os.sep}" ')
            self.assertEqual(0, code, output)
            root = ET.parse(self.apache / "publish/rel/default.vrd").getroot()
            self.assertIn(f'File="{self.ib}";', root.get("ib"))
            before = self.snapshot()
            for bad in ('C:base', f'{self.ib}"x'):
                code, output = self.run_tool("publish", "-WebExtension", str(self.module), "-AppName", "bad",
                                             "-InfoBasePath", bad)
                self.assertEqual(2, code, output)
            self.assertEqual(before, self.snapshot())
        finally:
            os.chdir(previous)

    def test_server_dev_env_and_invalid_kind(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            env_file = self.base / ".dev.env"
            env_file.write_text('INFOBASE_KIND=server\nINFOBASE_PATH=server\\base\n')
            code, output = self.run_tool("publish", "-WebExtension", str(self.module))
            self.assertEqual(0, code, output)
            root = ET.parse(self.apache / "publish/base/default.vrd").getroot()
            self.assertEqual('Srvr="server";Ref="base";', root.get("ib"))
            for value in ("INFOBASE_KIND=invalid\nINFOBASE_PATH=server/base\n", "INFOBASE_KIND=server\nINFOBASE_PATH=missing-ref\n"):
                env_file.write_text(value)
                before = self.snapshot()
                self.assertEqual(2, self.run_tool("publish", "-WebExtension", str(self.module))[0])
                self.assertEqual(before, self.snapshot())
        finally:
            os.chdir(previous)

    def test_missing_dependencies_are_clear_and_nonzero(self):
        self.assertEqual(1, self.run_tool("publish", "-V8Path", str(self.base / "absent"), "-InfoBasePath", str(self.ib))[0])
        self.layout.exe.unlink()
        self.assertEqual(1, self.publish("-Manual")[0])
        code, output = self.run_tool("info")
        self.assertEqual(0, code)
        self.assertIn("не установлен", output)

    def test_all_entry_points_help_without_platform(self):
        for action in ("publish", "info", "stop", "unpublish"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPTS / f"web-{action}.py"), "--help"],
                                    cwd=self.base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ApachePath", result.stdout)

    def test_symlinked_publication_is_refused(self):
        self.add_publication()
        target = self.apache / "publish/demo/linked"
        outside = self.base / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_text("keep")
        try:
            target.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation is not permitted on this host")
        try:
            self.assertEqual(2, self.run_tool("unpublish", "-All", "-Force")[0])
            self.assertEqual("keep", sentinel.read_text())
        finally:
            target.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
