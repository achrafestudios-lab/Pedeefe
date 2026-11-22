"""Tests de Fase 4: conversión PDF <-> Excel/PowerPoint/HTML.

Comprueba las 7 rutas nuevas, sus descargas diferidas por token UUID y los
mensajes de error legibles. No abre puertos: usa el cliente de test de Flask.
Ejecutar con: .venv/bin/python -m unittest discover -s tests
"""

import io
import logging
import os
import re
import unittest
from unittest.mock import patch

from docx import Document
from openpyxl import Workbook, load_workbook
from pypdf import PdfReader
from pptx import Presentation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

import app as app_module

try:
    from test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes
except ImportError:  # ejecución como paquete (python -m unittest tests.test_fase4)
    from tests.test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes

# weasyprint es ruidoso en INFO; no afecta al resultado de los tests.
logging.getLogger("weasyprint").setLevel(logging.ERROR)

TOKEN_RE = re.compile(r"/descargar_[a-z_]+/([0-9a-f-]{36})")


def token_from(body):
    match = TOKEN_RE.search(body)
    return match.group(1) if match else None


def body_of(resp):
    return resp.data.decode("utf-8", "replace")


def assert_legible_error(test, resp):
    body = body_of(resp)
    assert_no_traceback(test, body)
    test.assertNotIn("Error al convertir:", body)
    test.assertIn("alert-error", body)


def make_table_pdf():
    """PDF con una tabla con rejilla real (detectable por pdfplumber)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    table = Table(
        [["Producto", "Cantidad", "Precio"],
         ["Manzana", "2", "1.50"],
         ["Pera", "3", "2.00"]],
        colWidths=[150, 100, 100],
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([table])
    return buf.getvalue()


def make_docx():
    doc = Document()
    doc.add_heading("Informe", level=1)
    doc.add_paragraph("Contenido de prueba Word.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_xlsx():
    wb = Workbook()
    wb.active["A1"] = "Ventas"
    wb.active["A2"] = 42
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_pptx():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 914400, 457200).text_frame.text = "Hola Diapositiva"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


class TestPdfAExcelFase4(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-excel").status_code, 200)

    def test_table_pdf_generates_sheet_with_cells(self):
        pdf = make_table_pdf()
        resp = self.client.post(
            "/pdf-a-excel",
            data={"file": (io.BytesIO(pdf), "tabla.pdf")},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token, body_of(resp)[:500])
        download = self.client.get(f"/descargar_excel/{token}")
        self.assertEqual(download.status_code, 200)
        wb = load_workbook(io.BytesIO(download.data))
        tables = [name for name in wb.sheetnames if name.startswith("Pagina")]
        self.assertTrue(tables, wb.sheetnames)
        rows = [[c.value for c in row] for row in wb[tables[0]].iter_rows()]
        self.assertEqual(rows[0], ["Producto", "Cantidad", "Precio"])
        self.assertIn(["Manzana", "2", "1.50"], rows)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_text_pdf_falls_back_to_text_sheet(self):
        pdf = make_pdf_bytes(text="Factura", pages=2)
        resp = self.client.post(
            "/pdf-a-excel",
            data={"file": (io.BytesIO(pdf), "texto.pdf")},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token)
        download = self.client.get(f"/descargar_excel/{token}")
        wb = load_workbook(io.BytesIO(download.data))
        self.assertEqual(wb.sheetnames, ["Texto"])
        values = [row[0].value for row in wb["Texto"].iter_rows()]
        self.assertIn("Factura - pagina 1", values)
        self.assertIn("Factura - pagina 2", values)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_missing_file_error(self):
        assert_legible_error(self, self.client.post("/pdf-a-excel", data={}))

    def test_wrong_extension_error(self):
        resp = self.client.post(
            "/pdf-a-excel",
            data={"file": (io.BytesIO(b"x"), "a.txt")},
            content_type="multipart/form-data",
        )
        assert_legible_error(self, resp)

    def test_corrupt_pdf_error(self):
        resp = self.client.post(
            "/pdf-a-excel",
            data={"file": (io.BytesIO(b"basura"), "a.pdf")},
            content_type="multipart/form-data",
        )
        assert_legible_error(self, resp)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_download_token_validated_and_cleanup(self):
        pdf = make_pdf_bytes()
        resp = self.client.post(
            "/pdf-a-excel",
            data={"file": (io.BytesIO(pdf), "a.pdf")},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token)
        self.assertEqual(self.client.get("/descargar_excel/..").status_code, 404)
        self.assertEqual(self.client.get("/descargar_excel/%2e%2e").status_code, 404)
        self.assertEqual(self.client.get("/descargar_excel/no-es-uuid").status_code, 404)
        self.assertEqual(self.client.get(f"/descargar_excel/{token}").status_code, 200)
        self.assertEqual(self.client.get(f"/descargar_excel/{token}").status_code, 404)
        self.assertEqual(os.listdir(self.uploads), [])


class TestPdfAPowerPointFase4(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-powerpoint").status_code, 200)

    def test_two_pages_become_two_slides(self):
        pdf = make_pdf_bytes(pages=2)
        resp = self.client.post(
            "/pdf-a-powerpoint",
            data={"file": (io.BytesIO(pdf), "a.pdf")},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token, body_of(resp)[:500])
        # Las imágenes temporales se eliminan tras incrustarlas en el PPTX.
        self.assertFalse(any(f.startswith("_slide_") for f in os.listdir(os.path.join(self.uploads, token))))
        download = self.client.get(f"/descargar_powerpoint/{token}")
        prs = Presentation(io.BytesIO(download.data))
        self.assertEqual(len(prs.slides), 2)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_corrupt_pdf_error(self):
        resp = self.client.post(
            "/pdf-a-powerpoint",
            data={"file": (io.BytesIO(b"basura"), "a.pdf")},
            content_type="multipart/form-data",
        )
        assert_legible_error(self, resp)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_missing_file_error(self):
        assert_legible_error(self, self.client.post("/pdf-a-powerpoint", data={}))


class TestPdfAHtmlFase4(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        self.assertEqual(self.client.get("/pdf-a-html").status_code, 200)

    def test_html_contains_text_from_both_pages(self):
        pdf = make_pdf_bytes(text="Factura", pages=2)
        resp = self.client.post(
            "/pdf-a-html",
            data={"file": (io.BytesIO(pdf), "a.pdf")},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token)
        download = self.client.get(f"/descargar_html/{token}")
        html = download.data.decode("utf-8", "replace")
        self.assertIn("Factura - pagina 1", html)
        self.assertIn("Factura - pagina 2", html)
        self.assertIn("page2", html)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_corrupt_pdf_error(self):
        resp = self.client.post(
            "/pdf-a-html",
            data={"file": (io.BytesIO(b"basura"), "a.pdf")},
            content_type="multipart/form-data",
        )
        assert_legible_error(self, resp)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_missing_file_error(self):
        assert_legible_error(self, self.client.post("/pdf-a-html", data={}))


class TestOfficeToPdfFase4(TempUploadMixin, unittest.TestCase):
    def test_get_200_all_routes(self):
        for route in ("/word-a-pdf", "/excel-a-pdf", "/powerpoint-a-pdf", "/html-a-pdf"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def _assert_pdf_download(self, route, name, blob, expected_text=None):
        resp = self.client.post(
            route,
            data={"file": (io.BytesIO(blob), name)},
            content_type="multipart/form-data",
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token, body_of(resp)[:500])
        download = self.client.get(f"/descargar_pdf/{token}")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.data.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(download.data))
        self.assertGreaterEqual(len(reader.pages), 1)
        if expected_text:
            text = " ".join((p.extract_text() or "") for p in reader.pages)
            # Según la versión de LibreOffice el texto puede partirse en líneas.
            self.assertIn("".join(expected_text.split()), "".join(text.split()))
        self.assertEqual(os.listdir(self.uploads), [])

    def test_docx_to_pdf(self):
        self._assert_pdf_download("/word-a-pdf", "a.docx", make_docx(), "Contenido de prueba Word.")

    def test_xlsx_to_pdf(self):
        self._assert_pdf_download("/excel-a-pdf", "a.xlsx", make_xlsx(), "Ventas")

    def test_csv_to_pdf(self):
        self._assert_pdf_download(
            "/excel-a-pdf", "a.csv", b"Producto,Total\nManzana,3\n", "Manzana"
        )

    def test_pptx_to_pdf(self):
        self._assert_pdf_download("/powerpoint-a-pdf", "a.pptx", make_pptx(), "Hola Diapositiva")

    def test_html_file_to_pdf(self):
        html = b"<html><body><h1>Texto HTML</h1></body></html>"
        self._assert_pdf_download("/html-a-pdf", "a.html", html, "Texto HTML")

    def test_html_textarea_to_pdf(self):
        resp = self.client.post(
            "/html-a-pdf",
            data={"html_text": "<html><body><h1>HTML pegado</h1></body></html>"},
        )
        token = token_from(body_of(resp))
        self.assertIsNotNone(token)
        download = self.client.get(f"/descargar_pdf/{token}")
        text = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(download.data)).pages)
        self.assertIn("HTML pegado", text)
        self.assertEqual(os.listdir(self.uploads), [])

    def test_wrong_extension_errors(self):
        for route, name in (("/word-a-pdf", "a.pdf"), ("/excel-a-pdf", "a.pdf"),
                            ("/powerpoint-a-pdf", "a.pdf"), ("/html-a-pdf", "a.pdf")):
            with self.subTest(route=route):
                resp = self.client.post(
                    route,
                    data={"file": (io.BytesIO(b"x"), name)},
                    content_type="multipart/form-data",
                )
                assert_legible_error(self, resp)

    def test_corrupt_docx_error_is_legible(self):
        resp = self.client.post(
            "/word-a-pdf",
            data={"file": (io.BytesIO(b"no es un zip"), "a.docx")},
            content_type="multipart/form-data",
        )
        assert_legible_error(self, resp)
        self.assertNotIn("zipfile", body_of(resp).lower())
        self.assertEqual(os.listdir(self.uploads), [])

    def test_missing_file_error(self):
        for route in ("/word-a-pdf", "/excel-a-pdf", "/powerpoint-a-pdf", "/html-a-pdf"):
            with self.subTest(route=route):
                assert_legible_error(self, self.client.post(route, data={}))

    def test_legacy_format_without_libreoffice_has_clear_message(self):
        # Se simula la ausencia del motor para que el caso se ejecute siempre,
        # también en el CI donde LibreOffice sí está instalado.
        with patch.object(app_module.shutil, "which", return_value=None):
            resp = self.client.post(
                "/word-a-pdf",
                data={"file": (io.BytesIO(b"antiguo"), "a.doc")},
                content_type="multipart/form-data",
            )
        assert_legible_error(self, resp)
        self.assertIn("LibreOffice", body_of(resp))


if __name__ == "__main__":
    unittest.main()
