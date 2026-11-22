"""Tests de ramas y casos borde con valor funcional.

Complementan la suite principal cubriendo los helpers internos, los errores
legibles de las rutas y las validaciones de opciones. No usan mocks de motores
externos: todo se ejecuta con el cliente de test de Flask.
"""

import io
import os
import re
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from pypdf import PdfReader

import app as app_module

try:
    from test_tools import (
        TempUploadMixin, assert_no_traceback, make_image_bytes, make_pdf_bytes,
    )
except ImportError:  # ejecución como paquete (python -m unittest tests.test_coverage)
    from tests.test_tools import (
        TempUploadMixin, assert_no_traceback, make_image_bytes, make_pdf_bytes,
    )

BAD_PDF = b"%PDF-1.4\nthis is not a real pdf\n%%EOF"
MISSING_TOKEN = "00000000-0000-0000-0000-000000000000"
TOKEN_RE = re.compile(r"/descargar_[a-z_]+/([0-9a-f-]{36})")


class TestInternalHelpers(unittest.TestCase):
    """Helpers puros: formato, limpieza, mensajes y parseo de páginas."""

    def test_format_size_three_units(self):
        self.assertEqual(app_module.format_size(512), "512 B")
        self.assertEqual(app_module.format_size(2048), "2.0 KB")
        self.assertEqual(app_module.format_size(5 * 1024 * 1024), "5.0 MB")

    def test_parse_page_spec_valid(self):
        pages, error = app_module._parse_page_spec("1-2,4", 5)
        self.assertEqual(pages, [0, 1, 3])
        self.assertIsNone(error)

    def test_parse_page_spec_invalid_variants(self):
        for spec in ("", "   ", "1,,2", "a-b", "0", "3-1", "9", "x", "2-a"):
            with self.subTest(spec=spec):
                pages, error = app_module._parse_page_spec(spec, 5)
                self.assertIsNone(pages)
                self.assertTrue(error)

    def test_parse_page_spec_singular_message(self):
        _, error = app_module._parse_page_spec("1-2", 1)
        self.assertIn("1 página", error)

    def test_friendly_error_known_causes(self):
        self.assertEqual(
            app_module._friendly_error("convertir", app_module.ConversionError("Mensaje claro")),
            "Mensaje claro",
        )
        for cause, expected in (
            ("fallo de Poppler", "Poppler"),
            ("no está pdftoppm", "Poppler"),
            ("weasyprint ausente", "WeasyPrint"),
            ("falta pdfplumber", "pdfplumber"),
        ):
            with self.subTest(cause=cause):
                self.assertIn(expected, app_module._friendly_error("convertir", Exception(cause)))

    def test_friendly_error_generic_hides_exception(self):
        message = app_module._friendly_error("convertir", Exception("secreto interno"))
        self.assertIn("Comprueba", message)
        self.assertNotIn("secreto", message)

    def test_cleanup_folder_removes_tree_inside_uploads(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "temporal")
            os.makedirs(os.path.join(target, "sub"))
            Path(target, "sub", "archivo.txt").write_text("contenido", encoding="utf-8")
            with patch.object(app_module, "UPLOAD_FOLDER", root):
                app_module.cleanup_folder(target)
            self.assertFalse(os.path.exists(target))

    def test_cleanup_folder_ignores_paths_outside_uploads(self):
        with tempfile.TemporaryDirectory() as root:
            uploads = os.path.join(root, "uploads")
            outside = os.path.join(root, "afuera")
            os.makedirs(uploads)
            os.makedirs(outside)
            Path(outside, "archivo.txt").write_text("se conserva", encoding="utf-8")
            with patch.object(app_module, "UPLOAD_FOLDER", uploads):
                app_module.cleanup_folder(outside)
            self.assertTrue(os.path.exists(os.path.join(outside, "archivo.txt")))

    def test_cleanup_uploads_folder_removes_files_and_dirs(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "suelta.txt").write_text("x", encoding="utf-8")
            os.makedirs(os.path.join(root, "carpeta"))
            Path(root, "carpeta", "dentro.txt").write_text("x", encoding="utf-8")
            with patch.object(app_module, "UPLOAD_FOLDER", root):
                app_module.cleanup_uploads_folder()
            self.assertEqual(os.listdir(root), [])

    def test_status_413_known_and_unknown_referer(self):
        for referer in ("http://127.0.0.1:43210/dividir", "http://otro.example/"):
            with self.subTest(referer=referer):
                with app_module.app.test_request_context(headers={"Referer": referer}):
                    body, status = app_module.too_large(None)
                self.assertEqual(status, 413)
                self.assertIn("50 MB", body)


class TestPageNumberPositions(unittest.TestCase):
    """Las seis posiciones de numeración generan un PDF."""

    def test_all_positions_render(self):
        for position in (
            "bottom_center", "bottom_right", "bottom_left",
            "top_center", "top_right", "top_left",
        ):
            with self.subTest(position=position):
                packet = app_module.create_page_number_pdf(595, 842, 7, position=position)
                self.assertGreater(len(packet.getvalue()), 100)


class TestCorruptPdfBranches(TempUploadMixin, unittest.TestCase):
    """Un PDF corrupto produce un error legible y limpia el temporal en cada ruta."""

    CASES = {
        "/dividir": {"file": "file", "mode": "individual"},
        "/recortar-pdf": {"file": "file", "range": "1"},
        "/reordenar-pdf": {"file": "file", "order": "1"},
        "/rotar": {"file": "file", "angle": "90"},
        "/proteger": {"file": "file", "password": "abc", "password_confirm": "abc"},
        "/desproteger": {"file": "file", "password": "abc"},
        "/marcar-agua": {"file": "file", "watermark_text": "Prueba"},
        "/numerar": {"file": "file", "position": "bottom_center", "start_num": "1"},
        "/comprimir": {"file": "file"},
        "/pdf-a-imagen": {"file": "file", "format": "jpg"},
        "/pdf-a-word": {"file": "file"},
        "/pdf-a-excel": {"file": "file"},
        "/pdf-a-powerpoint": {"file": "file"},
        "/pdf-a-html": {"file": "file"},
        "/pdf-a-markdown": {"file": "file"},
        "/censurar": {"file": "file", "terms": "secreto"},
        "/ocr": {"file": "file"},
    }

    def test_corrupt_pdf_error_in_every_route(self):
        for route, fields in self.CASES.items():
            with self.subTest(route=route):
                data = {
                    name: (io.BytesIO(BAD_PDF), "roto.pdf")
                    if name.startswith("file") else value
                    for name, value in fields.items()
                }
                resp = self.client.post(route, data=data, content_type="multipart/form-data")
                self.assertEqual(resp.status_code, 200, f"{route} -> {resp.status_code}")
                body = resp.data.decode("utf-8", "replace")
                assert_no_traceback(self, body)
                self.assertIn("alert-error", body, f"{route}: falta mensaje de error")
                self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_missing_file_error_in_representative_routes(self):
        for route in ("/recortar-pdf", "/reordenar-pdf", "/proteger", "/marcar-agua",
                      "/numerar", "/censurar", "/comparar", "/firmar", "/lotes"):
            with self.subTest(route=route):
                resp = self.client.post(route, data={}, content_type="multipart/form-data")
                self.assertEqual(resp.status_code, 200)
                body = resp.data.decode("utf-8", "replace")
                assert_no_traceback(self, body)
                self.assertIn("alert-error", body)


class TestInvalidOptions(TempUploadMixin, unittest.TestCase):
    """Opciones fuera de rango se rechazan con un mensaje legible."""

    def _post(self, route, data):
        resp = self.client.post(route, data=data, content_type="multipart/form-data")
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertEqual(resp.status_code, 200, f"{route} -> {resp.status_code}")
        self.assertIn("alert-error", body)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_invalid_page_range(self):
        self._post("/recortar-pdf", {
            "file": (io.BytesIO(make_pdf_bytes(pages=2)), "ok.pdf"),
            "range": "9",
        })

    def test_invalid_page_order(self):
        self._post("/reordenar-pdf", {
            "file": (io.BytesIO(make_pdf_bytes(pages=2)), "ok.pdf"),
            "order": "3",
        })

    def test_invalid_rotation_angle_uses_default(self):
        resp = self.client.post("/rotar", data={
            "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
            "angle": "45",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertEqual(PdfReader(io.BytesIO(resp.data)).pages[0].get("/Rotate"), 90)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_invalid_start_number_uses_default(self):
        resp = self.client.post("/numerar", data={
            "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
            "position": "bottom_center",
            "start_num": "abc",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertIn("1", PdfReader(io.BytesIO(resp.data)).pages[0].extract_text())
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_invalid_batch_operation(self):
        self._post("/lotes", {
            "files": [(io.BytesIO(make_pdf_bytes()), "ok.pdf")],
            "operation": "no-existe",
        })

    def test_certificate_validations(self):
        for data in (
            {"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf")},
            {
                "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
                "certificate": (io.BytesIO(b"x"), "certificado.txt"),
            },
        ):
            with self.subTest(fields=sorted(data)):
                resp = self.client.post("/firmar", data=data, content_type="multipart/form-data")
                body = resp.data.decode("utf-8", "replace")
                assert_no_traceback(self, body)
                self.assertEqual(resp.status_code, 200)
                self.assertIn("alert-error", body)


class TestDownloadTokens(TempUploadMixin, unittest.TestCase):
    """Los tokens inexistentes se rechazan en todas las descargas diferidas."""

    def test_unknown_token_is_404_everywhere(self):
        for endpoint in (
            "descargar_comprimido", "descargar_word", "descargar_excel",
            "descargar_powerpoint", "descargar_html", "descargar_pdf",
        ):
            with self.subTest(endpoint=endpoint):
                resp = self.client.get(f"/{endpoint}/{MISSING_TOKEN}")
                self.assertEqual(resp.status_code, 404)


class TestApiErrorResponse(unittest.TestCase):
    """La API normaliza los errores de plantilla en JSON."""

    def test_form_error_from_template_is_json(self):
        with patch.dict(os.environ, {"PEDEEFE_TOKEN": "token-de-prueba"}):
            client = app_module.app.test_client()
            resp = client.post(
                "/api/v1/tools/pdf-a-markdown",
                headers={"Authorization": "Bearer token-de-prueba"},
                data={"file": (io.BytesIO(BAD_PDF), "roto.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 400)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["error"])


class TestOfficeHtmlHelpers(unittest.TestCase):
    """DocX/PPTX reales ejercitan el convertidor HTML sin LibreOffice."""

    def test_docx_to_html_with_heading_paragraph_and_table(self):
        from docx import Document

        document = Document()
        document.add_heading("Titulo", level=1)
        document.add_paragraph("Texto sencillo")
        document.add_table(rows=1, cols=1).cell(0, 0).text = "Celda"

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "doc.docx")
            document.save(path)
            html = app_module._docx_to_html(path)

        self.assertIn("<h1>Titulo</h1>", html)
        self.assertIn("<p>Texto sencillo</p>", html)
        self.assertIn("<td>Celda</td>", html)

    def test_pptx_to_html_with_text_table_and_notes(self):
        from pptx import Presentation
        from pptx.util import Inches

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1)).text_frame.text = "Hola"
        table = slide.shapes.add_table(1, 1, Inches(1), Inches(3), Inches(2), Inches(1)).table
        table.cell(0, 0).text = "Celda"
        slide.notes_slide.notes_text_frame.text = "Nota"

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "doc.pptx")
            presentation.save(path)
            html = app_module._pptx_to_html(path)

        self.assertIn("Diapositiva 1", html)
        self.assertIn("<p>Hola</p>", html)
        self.assertIn("<td>Celda</td>", html)
        self.assertIn("Notas: Nota", html)

    def test_legacy_formats_require_libreoffice(self):
        with patch.object(app_module, "_office_to_pdf_libreoffice", return_value=False):
            for ext in ("doc", "xls", "ppt"):
                with self.subTest(ext=ext), self.assertRaises(app_module.ConversionError):
                    app_module._office_to_pdf("entrada." + ext, "salida.pdf", ext)

    def test_unsupported_format_is_rejected(self):
        with patch.object(app_module, "_office_to_pdf_libreoffice", return_value=False):
            with self.assertRaises(app_module.ConversionError):
                app_module._office_to_pdf("entrada.xyz", "salida.pdf", "xyz")

    def test_unexpected_error_is_wrapped(self):
        with patch.object(app_module, "_office_to_pdf_libreoffice", return_value=False), \
                patch.object(app_module, "_docx_to_html", side_effect=OSError("boom")):
            with self.assertRaises(app_module.ConversionError) as caught:
                app_module._office_to_pdf("entrada.docx", "salida.pdf", "docx")
        self.assertIn("Comprueba", str(caught.exception))


class TestLibreOfficeBranches(unittest.TestCase):
    """La rama de LibreOffice se prueba simulando solo la respuesta del motor."""

    def test_success_renames_produced_pdf(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "documento.docx")
            produced = os.path.join(root, "documento.pdf")
            target = os.path.join(root, "salida.pdf")
            Path(source).write_bytes(b"entrada")
            Path(produced).write_bytes(make_pdf_bytes())
            with patch.object(app_module.shutil, "which", return_value="/usr/bin/soffice"), \
                    patch.object(app_module.subprocess, "run", return_value=MagicMock()):
                result = app_module._office_to_pdf_libreoffice(source, target)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(target))
            self.assertFalse(os.path.exists(produced))

    def test_subprocess_failure_returns_false(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "documento.docx")
            target = os.path.join(root, "salida.pdf")
            Path(source).write_bytes(b"entrada")
            error = subprocess.CalledProcessError(1, ["soffice"], stderr=b"fallo")
            with patch.object(app_module.shutil, "which", return_value="/usr/bin/soffice"), \
                    patch.object(app_module.subprocess, "run", side_effect=error):
                self.assertFalse(app_module._office_to_pdf_libreoffice(source, target))

    def test_rename_failure_returns_false(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "documento.docx")
            produced = os.path.join(root, "documento.pdf")
            target = os.path.join(root, "salida.pdf")
            Path(source).write_bytes(b"entrada")
            Path(produced).write_bytes(b"pdf")
            with patch.object(app_module.shutil, "which", return_value="/usr/bin/soffice"), \
                    patch.object(app_module.subprocess, "run", return_value=MagicMock()), \
                    patch.object(app_module.os, "replace", side_effect=OSError("ocupado")):
                self.assertFalse(app_module._office_to_pdf_libreoffice(source, target))


class TestGhostscriptErrorBranches(TempUploadMixin, unittest.TestCase):
    """Los fallos de Ghostscript se convierten en mensajes legibles."""

    def _post(self):
        return self.client.post(
            "/comprimir-real",
            data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf")},
            content_type="multipart/form-data",
        )

    def _assert_error(self, resp):
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertTrue(
            "Error al comprimir" in body or "No se encontró Ghostscript" in body,
            "falta un mensaje de error legible",
        )
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_ghostscript_missing(self):
        with patch.object(app_module.shutil, "which", return_value=None):
            self._assert_error(self._post())

    def test_called_process_error_with_stderr(self):
        error = subprocess.CalledProcessError(1, ["gs"], stderr=b"fallo de gs")
        with patch.object(app_module.subprocess, "run", side_effect=error):
            self._assert_error(self._post())

    def test_called_process_error_without_stderr(self):
        error = subprocess.CalledProcessError(1, ["gs"], stderr=b"")
        with patch.object(app_module.subprocess, "run", side_effect=error):
            self._assert_error(self._post())

    def test_timeout(self):
        error = subprocess.TimeoutExpired(["gs"], 120)
        with patch.object(app_module.subprocess, "run", side_effect=error):
            self._assert_error(self._post())

    def test_binary_disappears(self):
        with patch.object(app_module.subprocess, "run", side_effect=FileNotFoundError("gs")):
            self._assert_error(self._post())

    def test_no_output_file(self):
        with patch.object(app_module.subprocess, "run", return_value=MagicMock()):
            self._assert_error(self._post())


class TestOcrBranches(TempUploadMixin, unittest.TestCase):
    """El flujo de OCR se prueba simulando el texto que devolvería Tesseract."""

    def _post(self):
        return self.client.post(
            "/ocr",
            data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf")},
            content_type="multipart/form-data",
        )

    def test_extracted_text_is_downloaded(self):
        from PIL import Image

        image = Image.new("RGB", (10, 10), color="white")
        with patch.object(app_module, "convert_from_path", return_value=[image]), \
                patch.object(app_module.pytesseract, "image_to_string",
                             return_value="Texto reconocido"):
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Texto reconocido", resp.data.decode("utf-8", "replace"))
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_default_language_is_spanish(self):
        from PIL import Image

        image = Image.new("RGB", (10, 10), color="white")
        with patch.object(app_module, "convert_from_path", return_value=[image]), \
                patch.object(app_module.pytesseract, "image_to_string",
                             return_value="Texto") as recognize:
            self._post()
        recognize.assert_called_once_with(image, lang="spa")

    def test_selected_language_is_forwarded(self):
        from PIL import Image

        image = Image.new("RGB", (10, 10), color="white")
        with patch.object(app_module, "convert_from_path", return_value=[image]), \
                patch.object(app_module.pytesseract, "image_to_string",
                             return_value="Text") as recognize:
            resp = self.client.post(
                "/ocr",
                data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "lang": "eng"},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 200)
        recognize.assert_called_once_with(image, lang="eng")

    def test_invalid_language_is_rejected(self):
        with patch.object(app_module.pytesseract, "image_to_string") as recognize:
            resp = self.client.post(
                "/ocr",
                data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "lang": "xx"},
                content_type="multipart/form-data",
            )
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("idioma de OCR", body)
        recognize.assert_not_called()
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_missing_language_pack_has_clear_message(self):
        with patch.object(app_module, "convert_from_path",
                          side_effect=RuntimeError("Error opening data file fra.traineddata")):
            resp = self.client.post(
                "/ocr",
                data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "lang": "fra"},
                content_type="multipart/form-data",
            )
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("tesseract-ocr-fra", body)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_poppler_error_is_explained(self):
        with patch.object(app_module, "convert_from_path",
                          side_effect=Exception("poppler no encontrado")):
            resp = self._post()
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("Poppler", body)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])


class TestImageConversion(TempUploadMixin, unittest.TestCase):
    """Imagen a PDF usa el modo real de cada imagen (RGB, RGBA y escala de grises)."""

    def test_single_jpg_becomes_one_page_pdf(self):
        resp = self.client.post("/imagen-a-pdf", data={
            "files": [(io.BytesIO(make_image_bytes(fmt="JPEG")), "foto.jpg")],
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertEqual(len(PdfReader(io.BytesIO(resp.data)).pages), 1)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_multiple_images_with_alpha_and_grayscale(self):
        from PIL import Image

        rgba = Image.new("RGBA", (12, 12), (255, 0, 0, 128))
        buffer = io.BytesIO()
        rgba.save(buffer, format="PNG")
        gray = Image.new("L", (10, 10), 128)
        gray_buffer = io.BytesIO()
        gray.save(gray_buffer, format="PNG")

        resp = self.client.post("/imagen-a-pdf", data={
            "files": [
                (io.BytesIO(buffer.getvalue()), "transparente.png"),
                (io.BytesIO(gray_buffer.getvalue()), "gris.png"),
                (io.BytesIO(make_image_bytes(fmt="JPEG")), "opaca.jpg"),
            ],
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(PdfReader(io.BytesIO(resp.data)).pages), 3)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_invalid_extension_and_fake_image_are_rejected(self):
        for filename, payload in (("archivo.txt", b"texto"), ("foto.png", b"no es imagen")):
            with self.subTest(filename=filename):
                resp = self.client.post("/imagen-a-pdf", data={
                    "files": [(io.BytesIO(payload), filename)],
                }, content_type="multipart/form-data")
                body = resp.data.decode("utf-8", "replace")
                assert_no_traceback(self, body)
                self.assertIn("alert-error", body)
                self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_only_blank_filenames_is_rejected(self):
        resp = self.client.post("/imagen-a-pdf", data={
            "files": [(io.BytesIO(b""), "")],
        }, content_type="multipart/form-data")
        self.assertIn("alert-error", resp.data.decode("utf-8", "replace"))


class TestPdfToImage(TempUploadMixin, unittest.TestCase):
    """Una página descarga la imagen suelta; varias, un ZIP."""

    def test_single_page_returns_jpg(self):
        resp = self.client.post("/pdf-a-imagen", data={
            "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
            "format": "jpg",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/jpeg")
        self.assertIn("pagina_1.jpg", resp.headers.get("Content-Disposition", ""))
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_two_pages_with_png_returns_zip(self):
        resp = self.client.post("/pdf-a-imagen", data={
            "file": (io.BytesIO(make_pdf_bytes(pages=2)), "ok.pdf"),
            "format": "png",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(resp.data)) as archive:
            self.assertEqual(sorted(archive.namelist()), ["pagina_1.png", "pagina_2.png"])
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_unknown_format_falls_back_to_jpg(self):
        resp = self.client.post("/pdf-a-imagen", data={
            "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
            "format": "gif",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/jpeg")
        self.assertIn("pagina_1.jpg", resp.headers.get("Content-Disposition", ""))

    def test_poppler_error_is_explained(self):
        with patch.object(app_module, "convert_from_path",
                          side_effect=Exception("pdftoppm not found")):
            resp = self.client.post("/pdf-a-imagen", data={
                "file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"),
                "format": "jpg",
            }, content_type="multipart/form-data")
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("Poppler", body)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])


class TestHtmlToPdf(TempUploadMixin, unittest.TestCase):
    """HTML pegado o subido genera un PDF descargable por token."""

    def _download_and_assert(self, resp):
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        match = TOKEN_RE.search(body)
        self.assertIsNotNone(match, "falta el enlace de descarga por token")
        download = self.client.get(f"/descargar_pdf/{match.group(1)}")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.data.startswith(b"%PDF"))
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_pasted_html_creates_pdf(self):
        resp = self.client.post("/html-a-pdf", data={
            "html_text": "<h1>Pedeefe</h1><p>Contenido local</p>",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self._download_and_assert(resp)

    def test_uploaded_html_file_creates_pdf(self):
        resp = self.client.post("/html-a-pdf", data={
            "file": (io.BytesIO(b"<html><body>Archivo</body></html>"), "pagina.html"),
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self._download_and_assert(resp)

    def test_invalid_extension_is_rejected(self):
        resp = self.client.post("/html-a-pdf", data={
            "file": (io.BytesIO(b"<p>x</p>"), "pagina.txt"),
        }, content_type="multipart/form-data")
        self.assertIn("alert-error", resp.data.decode("utf-8", "replace"))

    def test_weasyprint_failure_is_explained(self):
        with patch.object(app_module, "_html_to_pdf",
                          side_effect=Exception("weasyprint roto")):
            resp = self.client.post("/html-a-pdf", data={
                "html_text": "<p>x</p>",
            }, content_type="multipart/form-data")
        body = resp.data.decode("utf-8", "replace")
        assert_no_traceback(self, body)
        self.assertIn("WeasyPrint", body)
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])


class TestLocalToken(unittest.TestCase):
    """El token local se comparte de forma segura y tolera fallos de permisos."""

    def test_reads_existing_token(self):
        import local_token

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "token")
            Path(path).write_text("token-existente\n", encoding="utf-8")
            with patch.object(local_token, "token_path", return_value=path):
                self.assertEqual(local_token.get_or_create_api_token(), "token-existente")

    def test_creates_token_with_restricted_permissions(self):
        import local_token

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, ".pedeefe", "token")
            with patch.dict(os.environ, {local_token.TOKEN_ENV: ""}), \
                    patch.object(local_token, "token_path", return_value=path):
                token = local_token.get_or_create_api_token()
            self.assertTrue(token)
            self.assertEqual(Path(path).read_text(encoding="utf-8").strip(), token)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)

    def test_unreadable_file_returns_memory_token(self):
        import local_token

        with patch.dict(os.environ, {local_token.TOKEN_ENV: ""}), \
                patch.object(local_token, "token_path", return_value="/no/leible"), \
                patch("builtins.open", side_effect=OSError("denegado")):
            self.assertTrue(local_token.get_or_create_api_token())

    def test_chmod_failure_is_ignored(self):
        import local_token

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, ".pedeefe", "token")
            with patch.dict(os.environ, {local_token.TOKEN_ENV: ""}), \
                    patch.object(local_token, "token_path", return_value=path), \
                    patch.object(local_token.os, "chmod", side_effect=OSError("windows")):
                self.assertTrue(local_token.get_or_create_api_token())
            self.assertTrue(os.path.exists(path))

    def test_unwritable_directory_returns_memory_token(self):
        import local_token

        with patch.dict(os.environ, {local_token.TOKEN_ENV: ""}), \
                patch.object(local_token, "token_path", return_value="/no/escribible/token"), \
                patch.object(local_token.os, "makedirs", side_effect=OSError("denegado")):
            self.assertTrue(local_token.get_or_create_api_token())


if __name__ == "__main__":
    unittest.main()
