"""Tests de PDF a Markdown: extracción de texto local sin dependencias nuevas.

Comprueba la ruta web, el archivo .md generado y los errores legibles.
No abre puertos: usa el cliente de test de Flask.
"""

import io
import os
import unittest

import app as app_module

try:
    from test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes
except ImportError:  # ejecución como paquete (python -m unittest tests.test_markdown)
    from tests.test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes


class TestPdfAMarkdown(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-markdown").status_code, 200)

    def test_extracts_text_to_markdown(self):
        pdf = make_pdf_bytes(text="Hola Markdown", pages=2)
        resp = self.client.post(
            "/pdf-a-markdown",
            data={"file": (io.BytesIO(pdf), "documento.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/markdown")
        self.assertIn("convertido.md", resp.headers.get("Content-Disposition", ""))
        body = resp.data.decode("utf-8")
        self.assertIn("# Documento extraído", body)
        self.assertIn("## Página 1", body)
        self.assertIn("## Página 2", body)
        self.assertIn("Hola Markdown", body)

    def test_missing_file_shows_error(self):
        resp = self.client.post("/pdf-a-markdown", data={}, content_type="multipart/form-data")
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("alert-error", body)
        self.assertIn("Selecciona un PDF", body)

    def test_invalid_extension_shows_error(self):
        resp = self.client.post(
            "/pdf-a-markdown",
            data={"file": (io.BytesIO(b"contenido"), "mal.txt")},
            content_type="multipart/form-data",
        )
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("alert-error", body)
        self.assertIn("no es un PDF", body)

    def test_corrupt_pdf_shows_friendly_error(self):
        resp = self.client.post(
            "/pdf-a-markdown",
            data={"file": (io.BytesIO(b"no es un pdf"), "mal.pdf")},
            content_type="multipart/form-data",
        )
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("alert-error", body)
        self.assertNotIn("Error al convertir:", body)

    def test_temporary_folder_is_cleaned(self):
        pdf = make_pdf_bytes(text="Limpieza")
        self.client.post(
            "/pdf-a-markdown",
            data={"file": (io.BytesIO(pdf), "documento.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])


if __name__ == "__main__":
    unittest.main()
