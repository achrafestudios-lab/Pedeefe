"""Tests funcionales de las 12 herramientas de Pedeefe (Flask test client).

Complementan tests/test_smoke.py con casos válidos e inválidos por herramienta.
No requieren servidor ni puerto. Ejecutar:

    .venv/bin/python -m unittest discover -s tests -v

Tesseract está ausente en este entorno: /ocr se marca como no probado (skip),
no como fallo.
"""

import io
import os
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from PIL import Image

import app as app_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_pdf_bytes(text="Pedeefe test", pages=1, pagesize=A4):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=pagesize)
    for i in range(pages):
        c.drawString(100, 700, f"{text} - pagina {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def make_image_bytes(size=(20, 30), color="red", fmt="PNG"):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TempUploadMixin:
    def setUp(self):
        self._orig_upload = app_module.UPLOAD_FOLDER
        self._orig_config = app_module.app.config.get("UPLOAD_FOLDER")
        self.tmp_root = tempfile.mkdtemp(prefix="pedeefe_tools_", dir="/tmp/opencode")
        self.uploads = os.path.join(self.tmp_root, "uploads")
        os.makedirs(self.uploads, exist_ok=True)
        app_module.UPLOAD_FOLDER = self.uploads
        app_module.app.config["UPLOAD_FOLDER"] = self.uploads
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.UPLOAD_FOLDER = self._orig_upload
        app_module.app.config["UPLOAD_FOLDER"] = self._orig_config
        shutil.rmtree(self.tmp_root, ignore_errors=True)


def assert_no_traceback(test, body):
    test.assertNotIn("Traceback", body)
    test.assertNotIn("site-packages", body)


class TestUnirTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/unir").status_code, 200)

    def test_post_valid_two_pdfs(self):
        pdf = make_pdf_bytes()
        data = {"files": [(io.BytesIO(pdf), "a.pdf"), (io.BytesIO(pdf), "b.pdf")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("unido.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 2)

    def test_post_valid_three_pdfs_page_count(self):
        pdf = make_pdf_bytes(pages=2)
        data = {"files": [(io.BytesIO(pdf), "a.pdf"), (io.BytesIO(pdf), "b.pdf")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 4)

    def test_post_order_of_union(self):
        pdf_a = make_pdf_bytes(text="AAA", pages=1)
        pdf_b = make_pdf_bytes(text="BBB", pages=1)
        data = {"files": [(io.BytesIO(pdf_a), "a.pdf"), (io.BytesIO(pdf_b), "b.pdf")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        text = (reader.pages[0].extract_text() or "") + (reader.pages[1].extract_text() or "")
        self.assertLess(text.find("AAA"), text.find("BBB"))

    def test_post_one_file_error(self):
        pdf = make_pdf_bytes()
        data = {"files": [(io.BytesIO(pdf), "a.pdf")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("al menos 2", body.lower())

    def test_post_missing_files_error(self):
        resp = self.client.post("/unir", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("al menos 2", body.lower())

    def test_post_wrong_extension_error(self):
        data = {"files": [(io.BytesIO(b"x"), "a.txt"), (io.BytesIO(b"y"), "b.txt")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no es un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"files": [(io.BytesIO(b"no es pdf"), "a.pdf"), (io.BytesIO(b"tampoco"), "b.pdf")]}
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestDividirTools(TempUploadMixin, unittest.TestCase):
    def _pdf2(self):
        return make_pdf_bytes(pages=2)

    def test_get_200(self):
        self.assertEqual(self.client.get("/dividir").status_code, 200)

    def test_post_individual_zip(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "mode": "individual"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("paginas.zip", resp.headers.get("Content-Disposition", ""))
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        self.assertEqual(len(zf.namelist()), 2)
        self.assertIn("pagina_1.pdf", zf.namelist())

    def test_post_rango_pdf(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "mode": "rango", "range": "1-2"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("rango_extraido.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 2)

    def test_post_rango_single_page(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "mode": "rango", "range": "2"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 1)

    def test_post_rango_out_of_bounds_error(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "mode": "rango", "range": "5-10"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("supera el número de páginas", body)

    def test_post_rango_inverted_error(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "mode": "rango", "range": "2-1"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("inicio del rango no puede ser mayor", body)

    def test_post_missing_mode_error(self):
        pdf = self._pdf2()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un modo de división", body)

    def test_post_missing_file_error(self):
        resp = self.client.post("/dividir", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf"), "mode": "individual"}
        resp = self.client.post("/dividir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestComprimirTools(TempUploadMixin, unittest.TestCase):
    def _token_from(self, body):
        m = re.search(r"/descargar_comprimido/([0-9a-f-]{36})", body)
        return m.group(1) if m else None

    def test_get_200(self):
        self.assertEqual(self.client.get("/comprimir").status_code, 200)

    def test_post_valid_result_and_download(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/comprimir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("PDF optimizado", body)
        token = self._token_from(body)
        self.assertIsNotNone(token)
        dresp = self.client.get(f"/descargar_comprimido/{token}")
        self.assertEqual(dresp.status_code, 200)
        self.assertIn("comprimido.pdf", dresp.headers.get("Content-Disposition", ""))
        self.assertTrue(dresp.data.startswith(b"%PDF"))

    def test_post_missing_file_error(self):
        resp = self.client.post("/comprimir", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf")}
        resp = self.client.post("/comprimir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestPdfAImagenTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-imagen").status_code, 200)

    def test_post_one_page_jpg(self):
        pdf = make_pdf_bytes(pages=1)
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "format": "jpg"}
        resp = self.client.post("/pdf-a-imagen", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("pagina_1.jpg", cd)
        self.assertTrue(resp.data.startswith(b"\xff\xd8"))  # JPEG

    def test_post_one_page_png(self):
        pdf = make_pdf_bytes(pages=1)
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "format": "png"}
        resp = self.client.post("/pdf-a-imagen", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("pagina_1.png", cd)
        self.assertTrue(resp.data.startswith(b"\x89PNG"))

    def test_post_multi_page_zip_png(self):
        pdf = make_pdf_bytes(pages=2)
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "format": "png"}
        resp = self.client.post("/pdf-a-imagen", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("imagenes.zip", cd)
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        self.assertEqual(len(zf.namelist()), 2)

    def test_post_missing_file_error(self):
        resp = self.client.post("/pdf-a-imagen", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf")}
        resp = self.client.post("/pdf-a-imagen", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        # Poppler error or validation error; either way no traceback
        assert_no_traceback(self, body)


class TestImagenAPdfTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/imagen-a-pdf").status_code, 200)

    def test_post_valid_image(self):
        img = make_image_bytes()
        data = {"files": [(io.BytesIO(img), "a.png")]}
        resp = self.client.post("/imagen-a-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("imagenes.pdf", resp.headers.get("Content-Disposition", ""))

    def test_post_multiple_images(self):
        imgs = [make_image_bytes(color="red"), make_image_bytes(color="blue")]
        data = {"files": [(io.BytesIO(imgs[0]), "a.png"), (io.BytesIO(imgs[1]), "b.png")]}
        resp = self.client.post("/imagen-a-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 2)

    def test_post_wrong_extension_error(self):
        data = {"files": [(io.BytesIO(b"x"), "a.txt")]}
        resp = self.client.post("/imagen-a-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no es una imagen válida", body)

    def test_post_corrupt_image_error(self):
        data = {"files": [(io.BytesIO(b"basura"), "a.png")]}
        resp = self.client.post("/imagen-a-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como imagen", body)
        assert_no_traceback(self, body)

    def test_post_missing_files_error(self):
        resp = self.client.post("/imagen-a-pdf", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("al menos una imagen", body)


class TestPdfAWordTools(TempUploadMixin, unittest.TestCase):
    def _token_from(self, body):
        m = re.search(r"/descargar_word/([0-9a-f-]{36})", body)
        return m.group(1) if m else None

    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-word").status_code, 200)

    def test_post_valid_result_and_download(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/pdf-a-word", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Conversión completada", body)
        token = self._token_from(body)
        self.assertIsNotNone(token)
        dresp = self.client.get(f"/descargar_word/{token}")
        self.assertEqual(dresp.status_code, 200)
        self.assertIn("convertido.docx", dresp.headers.get("Content-Disposition", ""))
        self.assertTrue(dresp.data.startswith(b"PK"))  # DOCX (zip)

    def test_post_missing_file_error(self):
        resp = self.client.post("/pdf-a-word", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf")}
        resp = self.client.post("/pdf-a-word", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestRotarTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/rotar").status_code, 200)

    def test_post_valid_90(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "angle": "90"}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("rotado.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(reader.pages[0].rotation, 90)

    def test_post_valid_180(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "angle": "180"}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(reader.pages[0].rotation, 180)

    def test_post_invalid_angle_defaults_90(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "angle": "45"}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(reader.pages[0].rotation, 90)

    def test_post_missing_file_error(self):
        resp = self.client.post("/rotar", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf")}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestProtegerTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/proteger").status_code, 200)

    def test_post_valid_password(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "password": "secreta", "password_confirm": "secreta"}
        resp = self.client.post("/proteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("protegido.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertTrue(reader.is_encrypted)

    def test_post_empty_password_error(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "password": ""}
        resp = self.client.post("/proteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Introduce una contraseña", body)

    def test_post_missing_file_error(self):
        resp = self.client.post("/proteger", data={"password": "x"}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf"), "password": "x", "password_confirm": "x"}
        resp = self.client.post("/proteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestDesprotegerTools(TempUploadMixin, unittest.TestCase):
    def _protect(self, pdf, password="secreta"):
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "password": password, "password_confirm": password}
        resp = self.client.post("/proteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        return resp.data

    def test_get_200(self):
        self.assertEqual(self.client.get("/desproteger").status_code, 200)

    def test_post_valid_password_reversibility(self):
        pdf = make_pdf_bytes()
        protected = self._protect(pdf, "secreta")
        data = {"file": (io.BytesIO(protected), "p.pdf"), "password": "secreta"}
        resp = self.client.post("/desproteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("desprotegido.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertFalse(reader.is_encrypted)

    def test_post_wrong_password_error(self):
        pdf = make_pdf_bytes()
        protected = self._protect(pdf, "secreta")
        data = {"file": (io.BytesIO(protected), "p.pdf"), "password": "otra"}
        resp = self.client.post("/desproteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("La contraseña es incorrecta", body)

    def test_post_empty_password_error(self):
        pdf = make_pdf_bytes()
        protected = self._protect(pdf, "secreta")
        data = {"file": (io.BytesIO(protected), "p.pdf"), "password": ""}
        resp = self.client.post("/desproteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Introduce la contraseña", body)

    def test_post_not_encrypted_error(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "password": "x"}
        resp = self.client.post("/desproteger", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Este PDF no tiene contraseña", body)

    def test_post_missing_file_error(self):
        resp = self.client.post("/desproteger", data={"password": "x"}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)


class TestMarcarAguaTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/marcar-agua").status_code, 200)

    def test_post_valid_text(self):
        pdf = make_pdf_bytes(pages=2)
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "watermark_text": "CONFIDENCIAL"}
        resp = self.client.post("/marcar-agua", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("marcado.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 2)

    def test_post_empty_text_error(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "watermark_text": ""}
        resp = self.client.post("/marcar-agua", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Introduce el texto", body)

    def test_post_missing_file_error(self):
        resp = self.client.post("/marcar-agua", data={"watermark_text": "x"}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf"), "watermark_text": "x"}
        resp = self.client.post("/marcar-agua", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestNumerarTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/numerar").status_code, 200)

    def test_post_valid(self):
        pdf = make_pdf_bytes(pages=2)
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "position": "bottom_center", "start_num": "1"}
        resp = self.client.post("/numerar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("numerado.pdf", resp.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(resp.data))
        self.assertEqual(len(reader.pages), 2)

    def test_post_invalid_position_defaults(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "position": "invalid", "start_num": "1"}
        resp = self.client.post("/numerar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))

    def test_post_invalid_start_num_defaults(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf"), "position": "bottom_center", "start_num": "abc"}
        resp = self.client.post("/numerar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))

    def test_post_missing_file_error(self):
        resp = self.client.post("/numerar", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_post_corrupt_pdf_error(self):
        data = {"file": (io.BytesIO(b"basura"), "a.pdf")}
        resp = self.client.post("/numerar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        assert_no_traceback(self, body)


class TestOcrTools(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/ocr").status_code, 200)

    @unittest.skip("Tesseract ausente en este entorno: /ocr no probado")
    def test_post_ocr(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)


class TestRepoUploadsEmptyTools(unittest.TestCase):
    def test_repo_uploads_empty(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads = os.path.join(repo_root, "uploads")
        if os.path.exists(uploads):
            self.assertEqual(os.listdir(uploads), [], "uploads/ del repo no esta vacio")


if __name__ == "__main__":
    unittest.main()
