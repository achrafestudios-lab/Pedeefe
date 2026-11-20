"""Tests de v1.5: lotes con ZIP e historial/plantillas locales.

Usa el cliente de test de Flask (sin abrir puertos) y directorios temporales
aislados. Ejecutar:

    .venv/bin/python -m unittest discover -s tests
"""

import io
import os
import unittest
import zipfile
from unittest import mock

from pypdf import PdfReader, PdfWriter

import app as app_module

try:
    from test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes
except ImportError:  # ejecución como paquete
    from tests.test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes


def make_encrypted_pdf_bytes(password="clave", text="secreto"):
    """PDF cifrado en memoria para probar el lote de desprotección."""
    source = PdfReader(io.BytesIO(make_pdf_bytes(text=text)))
    writer = PdfWriter()
    for page in source.pages:
        writer.add_page(page)
    writer.encrypt(password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestProductivityPages(TempUploadMixin, unittest.TestCase):
    def test_get_lotes_200(self):
        response = self.client.get("/lotes")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", "replace")
        self.assertIn("Lotes PDF", body)
        self.assertIn("Límites del lote", body)
        self.assertIn("data-tool", body)
        assert_no_traceback(self, body)

    def test_get_historial_200(self):
        response = self.client.get("/historial")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", "replace")
        self.assertIn("Historial local", body)
        self.assertIn("history-list", body)
        self.assertIn("localStorage", body)
        self.assertIn("noscript", body)
        assert_no_traceback(self, body)

    def test_get_plantillas_200(self):
        response = self.client.get("/plantillas")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", "replace")
        self.assertIn("Plantillas reutilizables", body)
        self.assertIn("template-list", body)
        self.assertIn("Guardar como plantilla", body)
        assert_no_traceback(self, body)

    def test_index_and_nav_include_productivity(self):
        body = self.client.get("/").data.decode("utf-8", "replace")
        for path in ("/lotes", "/historial", "/plantillas"):
            self.assertIn(path, body)
        self.assertIn("Productividad", body)

    def test_productivity_js_is_served_and_safe(self):
        response = self.client.get("/static/js/productivity.js")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", "replace")
        self.assertIn("pedeefe.history.v1", body)
        self.assertIn("pedeefe.templates.v1", body)
        self.assertIn("textContent", body)
        self.assertIn("DEFAULT_HISTORY_TTL", body)
        self.assertNotIn("innerHTML", body)

    def test_413_maps_lotes_to_its_template(self):
        self.assertEqual(app_module.REFERER_TO_TEMPLATE.get("/lotes"), "lotes.html")


class BatchPostMixin:
    def post_batch(self, operation, files, **extra):
        data = {"operation": operation}
        for filename, content in files:
            data.setdefault("files", [])
            data["files"].append((io.BytesIO(content), filename))
        data.update(extra)
        response = self.client.post(
            "/lotes", data=data, content_type="multipart/form-data"
        )
        self.addCleanup(response.close)
        return response

    @staticmethod
    def zip_pdf_names(response):
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = archive.namelist()
            payloads = [archive.read(name) for name in names]
        return names, payloads


class TestBatchOperations(BatchPostMixin, TempUploadMixin, unittest.TestCase):
    def test_rotate_returns_zip_with_rotated_pages(self):
        response = self.post_batch("rotar", [
            ("uno.pdf", make_pdf_bytes(pages=2)),
            ("dos.pdf", make_pdf_bytes()),
        ], angle="180")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"PK"))
        self.assertIn("lote_rotar.zip", response.headers.get("Content-Disposition", ""))
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(sorted(names), ["dos_rotado.pdf", "uno_rotado.pdf"])
        for payload in payloads:
            self.assertTrue(payload.startswith(b"%PDF"))
            reader = PdfReader(io.BytesIO(payload))
            self.assertEqual(int(reader.pages[0].get("/Rotate", 0)), 180)

    def test_optimize_returns_zip(self):
        response = self.post_batch("optimizar", [
            ("informe.pdf", make_pdf_bytes()),
        ])
        self.assertEqual(response.status_code, 200)
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(names, ["informe_optimizado.pdf"])
        self.assertTrue(PdfReader(io.BytesIO(payloads[0])).pages)

    def test_protect_returns_encrypted_pdfs(self):
        response = self.post_batch("proteger", [
            ("a.pdf", make_pdf_bytes()),
        ], password="secreto", password_confirm="secreto")
        self.assertEqual(response.status_code, 200)
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(names, ["a_protegido.pdf"])
        reader = PdfReader(io.BytesIO(payloads[0]))
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt("secreto"))

    def test_unprotect_returns_readable_pdfs(self):
        response = self.post_batch("desproteger", [
            ("cerrado.pdf", make_encrypted_pdf_bytes()),
        ], password="clave")
        self.assertEqual(response.status_code, 200)
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(names, ["cerrado_desprotegido.pdf"])
        reader = PdfReader(io.BytesIO(payloads[0]))
        self.assertFalse(reader.is_encrypted)
        self.assertIn("secreto", reader.pages[0].extract_text())

    def test_watermark_returns_zip(self):
        response = self.post_batch("marcar_agua", [
            ("a.pdf", make_pdf_bytes()),
        ], watermark_text="CONFIDENCIAL")
        self.assertEqual(response.status_code, 200)
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(names, ["a_marcado.pdf"])
        self.assertTrue(PdfReader(io.BytesIO(payloads[0])).pages)

    def test_number_returns_zip(self):
        response = self.post_batch("numerar", [
            ("a.pdf", make_pdf_bytes(pages=2)),
        ], start_num="5", position="bottom_right")
        self.assertEqual(response.status_code, 200)
        names, payloads = self.zip_pdf_names(response)
        self.assertEqual(names, ["a_numerado.pdf"])
        self.assertEqual(len(PdfReader(io.BytesIO(payloads[0])).pages), 2)

    def test_output_names_are_sanitized_and_unique(self):
        response = self.post_batch("rotar", [
            ("../../informe final.pdf", make_pdf_bytes()),
            ("../../informe final.pdf", make_pdf_bytes()),
        ])
        self.assertEqual(response.status_code, 200)
        names, _ = self.zip_pdf_names(response)
        self.assertEqual(names, ["informe_final_rotado.pdf", "informe_final_rotado_2.pdf"])
        for name in names:
            self.assertNotIn("/", name)
            self.assertNotIn("..", name)


class TestBatchErrors(BatchPostMixin, TempUploadMixin, unittest.TestCase):
    def assert_batch_error(self, response, expected):
        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", "replace")
        self.assertIn(expected, body)
        assert_no_traceback(self, body)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_no_files(self):
        response = self.post_batch("rotar", [])
        self.assert_batch_error(response, "Selecciona al menos un PDF")

    def test_too_many_files(self):
        files = [(f"doc{i}.pdf", make_pdf_bytes()) for i in range(11)]
        self.assert_batch_error(
            self.post_batch("rotar", files), "como máximo 10 PDFs"
        )

    def test_invalid_extension(self):
        response = self.post_batch("rotar", [("nota.txt", make_pdf_bytes())])
        self.assert_batch_error(response, "no es un PDF")

    def test_invalid_pdf_content(self):
        response = self.post_batch("rotar", [("roto.pdf", b"esto no es un pdf")])
        self.assert_batch_error(response, "no se puede leer como PDF")

    def test_unknown_operation(self):
        response = self.post_batch("firmar", [("a.pdf", make_pdf_bytes())])
        self.assert_batch_error(response, "operación válida")

    def test_protect_requires_password(self):
        response = self.post_batch("proteger", [("a.pdf", make_pdf_bytes())])
        self.assert_batch_error(response, "Introduce una contraseña")

    def test_protect_password_mismatch(self):
        response = self.post_batch("proteger", [("a.pdf", make_pdf_bytes())],
                                   password="uno", password_confirm="dos")
        self.assert_batch_error(response, "no coinciden")

    def test_unprotect_requires_password(self):
        response = self.post_batch("desproteger", [
            ("a.pdf", make_encrypted_pdf_bytes()),
        ])
        self.assert_batch_error(response, "Introduce la contraseña")

    def test_unprotect_wrong_password(self):
        response = self.post_batch("desproteger", [
            ("a.pdf", make_encrypted_pdf_bytes()),
        ], password="incorrecta")
        self.assert_batch_error(response, "no abre todos los PDF")

    def test_unprotect_plain_pdf(self):
        response = self.post_batch("desproteger", [("a.pdf", make_pdf_bytes())],
                                   password="clave")
        self.assert_batch_error(response, "no tiene contraseña")

    def test_encrypted_input_is_rejected_for_other_operations(self):
        response = self.post_batch("rotar", [
            ("a.pdf", make_encrypted_pdf_bytes()),
        ])
        self.assert_batch_error(response, "está protegido")

    def test_watermark_requires_text(self):
        response = self.post_batch("marcar_agua", [("a.pdf", make_pdf_bytes())])
        self.assert_batch_error(response, "Introduce el texto de la marca de agua")

    def test_page_limit(self):
        with mock.patch.object(app_module, "MAX_BATCH_PAGES", 1):
            response = self.post_batch("rotar", [
                ("a.pdf", make_pdf_bytes(pages=2)),
                ("b.pdf", make_pdf_bytes()),
            ])
        self.assert_batch_error(response, "páginas en total")

    def test_total_size_limit(self):
        with mock.patch.object(app_module, "MAX_BATCH_TOTAL_SIZE", 1):
            response = self.post_batch("rotar", [("a.pdf", make_pdf_bytes())])
        self.assert_batch_error(response, "límite total")

    def test_uploads_are_cleaned_after_success(self):
        response = self.post_batch("rotar", [("a.pdf", make_pdf_bytes())])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(os.listdir(self.uploads), [])
