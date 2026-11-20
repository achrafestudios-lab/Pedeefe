"""Tests de endurecimiento de v2.0.1 (temporales privados y limpieza).

No requieren servidor ni puerto: usan el cliente de test de Flask.
"""

import io
import os
import re
import shutil
import stat
import tempfile
import unittest

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import app as app_module


def make_pdf_bytes(text="Pedeefe test"):
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.drawString(100, 700, text)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


class TempUploadMixin:
    """Aísla UPLOAD_FOLDER en un directorio temporal del sistema."""

    def setUp(self):
        self._orig_upload = app_module.UPLOAD_FOLDER
        self._orig_config = app_module.app.config.get("UPLOAD_FOLDER")
        self.tmp_root = tempfile.mkdtemp(prefix="pedeefe_hardening_")
        self.uploads = os.path.join(self.tmp_root, "uploads")
        os.makedirs(self.uploads, exist_ok=True)
        app_module.UPLOAD_FOLDER = self.uploads
        app_module.app.config["UPLOAD_FOLDER"] = self.uploads
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.UPLOAD_FOLDER = self._orig_upload
        app_module.app.config["UPLOAD_FOLDER"] = self._orig_config
        shutil.rmtree(self.tmp_root, ignore_errors=True)


class TestPrivateTempDirs(TempUploadMixin, unittest.TestCase):
    def test_helper_crea_carpeta_0700(self):
        path = app_module._create_temp_dir()
        try:
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700)
            self.assertEqual(len(os.listdir(path)), 0)
        finally:
            app_module.cleanup_folder(path)

    def test_rutas_usan_carpetas_privadas(self):
        original = app_module._create_temp_dir
        created = []

        def spy():
            path = original()
            created.append((path, stat.S_IMODE(os.stat(path).st_mode)))
            return path

        app_module._create_temp_dir = spy
        try:
            data = {
                "files": [
                    (io.BytesIO(make_pdf_bytes("uno")), "uno.pdf"),
                    (io.BytesIO(make_pdf_bytes("dos")), "dos.pdf"),
                ]
            }
            resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        finally:
            app_module._create_temp_dir = original

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0][1], 0o700)
        self.assertFalse(os.path.exists(created[0][0]))


class TestCorruptPdfCleanup(TempUploadMixin, unittest.TestCase):
    CASES = {
        "/rotar": lambda bad: {"file": (io.BytesIO(bad), "bad.pdf"), "angle": "90"},
        "/comprimir": lambda bad: {"file": (io.BytesIO(bad), "bad.pdf")},
        "/comprimir-real": lambda bad: {"file": (io.BytesIO(bad), "bad.pdf")},
        "/pdf-a-imagen": lambda bad: {"file": (io.BytesIO(bad), "bad.pdf")},
        "/unir": lambda bad: {
            "files": [
                (io.BytesIO(bad), "bad.pdf"),
                (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
            ]
        },
        "/ocr": lambda bad: {"file": (io.BytesIO(bad), "bad.pdf")},
    }

    def test_pdf_corruptos_no_dejan_temporales_ni_traceback(self):
        bad = b"%PDF-1.4\nthis is not a real pdf\n%%EOF"
        for route, build in self.CASES.items():
            with self.subTest(route=route):
                resp = self.client.post(
                    route, data=build(bad), content_type="multipart/form-data"
                )
                self.assertNotEqual(resp.status_code, 500)
                self.assertNotIn(b"Traceback", resp.data)
                self.assertEqual(os.listdir(self.uploads), [], route)


class TestDeferredDownloadStillWorks(TempUploadMixin, unittest.TestCase):
    def test_descarga_diferida_sigue_limpia(self):
        resp = self.client.post(
            "/comprimir",
            data={"file": (io.BytesIO(make_pdf_bytes()), "a.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        match = re.search(rb"/descargar_comprimido/([0-9a-f-]{36})", resp.data)
        self.assertIsNotNone(match)

        download = self.client.get(
            "/descargar_comprimido/" + match.group(1).decode("ascii")
        )
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.data.startswith(b"%PDF-"))
        self.assertEqual(os.listdir(self.uploads), [])


if __name__ == "__main__":
    unittest.main()
