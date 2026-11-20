"""Tests de v1.7: sidecar HTTP de Pedeefe Desktop.

Usa un subprocess real en 127.0.0.1 con puerto efímero para comprobar que el
backend arranca y anuncia su URL. No abre puertos a la red local ni requiere
Electron. Ejecutar:

    .venv/bin/python -m unittest discover -s tests
"""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop import launcher  # noqa: E402


class TestLauncherHelpers(unittest.TestCase):
    """Funciones puras del sidecar. [CONFIRMADO]"""

    def test_host_is_loopback_only(self):
        self.assertEqual(launcher.HOST, "127.0.0.1")
        with self.assertRaises(SystemExit):
            launcher.main(["--host", "0.0.0.0"])

    def test_ready_line_roundtrip(self):
        line = launcher.format_ready("127.0.0.1", 43210)
        self.assertEqual(line, "PEDEE_READY http://127.0.0.1:43210")
        self.assertEqual(launcher.parse_ready(line), 43210)
        self.assertIsNone(launcher.parse_ready("GET / HTTP/1.1 200"))

    def test_upload_dir_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "uploads")
            self.assertEqual(launcher.prepare_upload_dir(target), target)
            self.assertTrue(os.path.isdir(target))

    def test_choose_port_returns_free_loopback_port(self):
        port = launcher.choose_port()
        self.assertGreater(port, 1024)
        self.assertEqual(launcher.parse_ready(launcher.format_ready(launcher.HOST, port)), port)

    def test_parent_watcher_stops_when_electron_disappears(self):
        stopped = threading.Event()
        with mock.patch.object(launcher, "parent_alive", return_value=False):
            watcher = threading.Thread(
                target=launcher.watch_parent,
                args=(1234, stopped.set, 0.01),
                daemon=True,
            )
            watcher.start()
            self.assertTrue(stopped.wait(timeout=2))

    def test_parent_alive_posix(self):
        with mock.patch.object(launcher.os, "name", "posix"), mock.patch.object(
            launcher.os, "kill", side_effect=ProcessLookupError
        ):
            self.assertFalse(launcher.parent_alive(1234))
        with mock.patch.object(launcher.os, "name", "posix"), mock.patch.object(
            launcher.os, "kill", side_effect=PermissionError
        ):
            self.assertTrue(launcher.parent_alive(1234))

    @staticmethod
    def _kernel_mock(exit_code=launcher.STILL_ACTIVE, handle=99):
        kernel = mock.Mock()
        kernel.OpenProcess.return_value = handle
        kernel.GetExitCodeProcess.side_effect = (
            lambda _handle, pointer: setattr(pointer._obj, "value", exit_code) or 1
        )
        return kernel

    def test_parent_alive_windows(self):
        for exit_code, expected in ((launcher.STILL_ACTIVE, True), (0, False)):
            with self.subTest(exit_code=exit_code):
                kernel = self._kernel_mock(exit_code=exit_code)
                with mock.patch.object(launcher.os, "name", "nt"), mock.patch.object(
                    launcher.ctypes, "WinDLL", return_value=kernel, create=True
                ), mock.patch.object(
                    launcher.ctypes, "get_last_error", return_value=0, create=True
                ):
                    self.assertEqual(launcher.parent_alive(4242), expected)
                kernel.CloseHandle.assert_called_once_with(99)

    def test_parent_alive_windows_access_denied_means_alive(self):
        kernel = self._kernel_mock(handle=0)
        with mock.patch.object(launcher.os, "name", "nt"), mock.patch.object(
            launcher.ctypes, "WinDLL", return_value=kernel, create=True
        ):
            with mock.patch.object(
                launcher.ctypes, "get_last_error", return_value=launcher.ERROR_ACCESS_DENIED, create=True
            ):
                self.assertTrue(launcher.parent_alive(4242))
            with mock.patch.object(
                launcher.ctypes, "get_last_error", return_value=2, create=True
            ):
                self.assertFalse(launcher.parent_alive(4242))

    def test_default_upload_dir_macos(self):
        with mock.patch.object(launcher.os, "name", "posix"), mock.patch.object(
            launcher.sys, "platform", "darwin"
        ), mock.patch.dict(launcher.os.environ, {"HOME": "/tmp/fakehome"}, clear=False):
            result = launcher.default_upload_dir()
        self.assertIn("Library", result)
        self.assertTrue(result.endswith(os.path.join("Pedeefe", "uploads")))

    def test_default_upload_dir_windows(self):
        with mock.patch.object(launcher.os, "name", "nt"), mock.patch.dict(
            launcher.os.environ, {"APPDATA": "C:\\AppData"}, clear=False
        ):
            result = launcher.default_upload_dir()
        self.assertIn("AppData", result)
        self.assertTrue(result.endswith(os.path.join("Pedeefe", "uploads")))


class TestDesktopPackaging(unittest.TestCase):
    """Configuración electron-builder multiplataforma (v1.8). [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        with (ROOT / "desktop" / "package.json").open(encoding="utf-8") as handle:
            cls.config = json.load(handle)

    def test_version_and_scripts(self):
        self.assertEqual(self.config["version"], "2.0.1")
        self.assertEqual(self.config["desktopName"], "Pedeefe")
        for script in ("dist:linux", "dist:win", "dist:mac"):
            self.assertIn(script, self.config["scripts"])

    def test_targets_by_platform(self):
        build = self.config["build"]
        self.assertIn("AppImage", build["linux"]["target"])
        self.assertTrue(build["linux"]["syncDesktopName"])
        win_targets = [target["target"] for target in build["win"]["target"]]
        self.assertIn("nsis", win_targets)
        mac_targets = [target["target"] for target in build["mac"]["target"]]
        self.assertIn("dmg", mac_targets)
        self.assertIn("zip", mac_targets)
        self.assertIsNone(build["mac"]["identity"])


class TestDesktopSidecar(unittest.TestCase):
    """Arranque real del backend local. [CONFIRMADO]"""

    def test_sidecar_announces_url_and_serves_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = os.path.join(tmp, "uploads")
            command = [
                sys.executable,
                str(ROOT / "desktop" / "launcher.py"),
                "--upload-dir",
                upload_dir,
            ]
            env = dict(os.environ)
            env.pop("PEDEE_UPLOAD_FOLDER", None)
            env["FLASK_DEBUG"] = "0"
            proc = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            lines = queue.Queue()
            threading.Thread(
                target=lambda: lines.put(proc.stdout.readline()),
                daemon=True,
            ).start()

            try:
                line = lines.get(timeout=20)
                port = launcher.parse_ready(line)
                self.assertIsNotNone(port, f"línea inesperada: {line!r}")

                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
                    body = response.read().decode("utf-8", "replace")
                    self.assertEqual(response.status, 200)
                self.assertIn("Manipula tus PDFs de forma local", body)
                self.assertEqual(os.listdir(upload_dir), [])
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
