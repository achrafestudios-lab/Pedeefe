"""Tests de detección de dependencias externas de Pedeefe (v1.8).

Los paquetes de escritorio no incluyen Poppler, Ghostscript, Tesseract ni
LibreOffice. La portada debe mostrar el estado de cada uno con una pista de
instalación acorde al sistema operativo.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402


class TestDependencyDetection(unittest.TestCase):
    """Helper de detección y portada. [CONFIRMADO]"""

    def test_status_has_four_known_dependencies(self):
        status = app_module.dependency_status()
        self.assertEqual(
            set(status),
            {"poppler", "ghostscript", "tesseract", "libreoffice"},
        )
        for item in status.values():
            self.assertIn("label", item)
            self.assertIsInstance(item["available"], bool)
            self.assertTrue(item["hint"])

    def test_hints_change_with_platform(self):
        with mock.patch.object(app_module.platform, "system", return_value="Windows"):
            windows = app_module.dependency_status()
        with mock.patch.object(app_module.platform, "system", return_value="Darwin"):
            macos = app_module.dependency_status()
        self.assertIn("PATH", windows["poppler"]["hint"])
        self.assertIn("brew", macos["poppler"]["hint"])
        self.assertNotIn("brew", windows["poppler"]["hint"])

    def test_index_exposes_dependency_panel(self):
        client = app_module.app.test_client()
        body = client.get("/").data.decode("utf-8", "replace")
        self.assertIn("Dependencias del sistema", body)
        self.assertIn("deps-panel", body)
        for label in ("Poppler", "Ghostscript", "Tesseract", "LibreOffice"):
            self.assertIn(label, body)


if __name__ == "__main__":
    unittest.main()
