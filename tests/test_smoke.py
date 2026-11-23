"""Tests de humo de Pedeefe (Flask test client).

No requieren servidor ni puerto. Se ejecutan con:

    .venv/bin/python -m unittest discover -s tests -v

Convenciones:
- Cada caso documenta si es [CONFIRMADO] (medido) o [INFERIDO].
- Las pruebas destructivas de C-01 usan UPLOAD_FOLDER temporal en el directorio
  del sistema y monkeypatchean ``cleanup_folder`` para no borrar nada.
- Tesseract está ausente en este entorno: /ocr se omite aquí; el CI lo ejecuta
  con el motor real.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest import mock

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image

import app as app_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_pdf_bytes(text="Pedeefe test"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def make_image_bytes(size=(20, 30), color="red", fmt="PNG"):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TempUploadMixin:
    """Cambia UPLOAD_FOLDER a un directorio temporal del sistema."""

    def setUp(self):
        self._orig_upload = app_module.UPLOAD_FOLDER
        self._orig_config = app_module.app.config.get("UPLOAD_FOLDER")
        self.tmp_root = tempfile.mkdtemp(prefix="pedeefe_test_")
        self.uploads = os.path.join(self.tmp_root, "uploads")
        os.makedirs(self.uploads, exist_ok=True)
        app_module.UPLOAD_FOLDER = self.uploads
        app_module.app.config["UPLOAD_FOLDER"] = self.uploads
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.UPLOAD_FOLDER = self._orig_upload
        app_module.app.config["UPLOAD_FOLDER"] = self._orig_config
        shutil.rmtree(self.tmp_root, ignore_errors=True)


class TestSmokeGetRoutes(TempUploadMixin, unittest.TestCase):
    """14 GET de la app + CSS -> 200. [CONFIRMADO]"""

    ROUTES = [
        "/",
        "/unir",
        "/dividir",
        "/comprimir",
        "/pdf-a-imagen",
        "/imagen-a-pdf",
        "/pdf-a-word",
        "/pdf-a-markdown",
        "/rotar",
        "/proteger",
        "/desproteger",
        "/ocr",
        "/marcar-agua",
        "/numerar",
    ]

    def test_get_app_routes_200(self):
        for route in self.ROUTES:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 200, f"{route} -> {resp.status_code}")

    def test_get_static_css_200(self):
        resp = self.client.get("/static/css/style.css")
        self.assertEqual(resp.status_code, 200)


class TestDownloadsNoToken(TempUploadMixin, unittest.TestCase):
    """2 descargas por token -> 404 sin token valido. [CONFIRMADO]"""

    def test_descargar_comprimido_sin_token_404(self):
        resp = self.client.get("/descargar_comprimido/00000000-0000-0000-0000-000000000000")
        self.assertEqual(resp.status_code, 404)

    def test_descargar_word_sin_token_404(self):
        resp = self.client.get("/descargar_word/00000000-0000-0000-0000-000000000000")
        self.assertEqual(resp.status_code, 404)

    def test_descargar_comprimido_sin_segmento_404(self):
        resp = self.client.get("/descargar_comprimido/")
        self.assertEqual(resp.status_code, 404)

    def test_descargar_word_sin_segmento_404(self):
        resp = self.client.get("/descargar_word/")
        self.assertEqual(resp.status_code, 404)


class TestUnirPost(TempUploadMixin, unittest.TestCase):
    """POST /unir con 2 PDFs sinteticos -> 200 y unido.pdf. [CONFIRMADO]"""

    def test_post_unir_two_pdfs(self):
        pdf = make_pdf_bytes()
        data = {
            "files": [
                (io.BytesIO(pdf), "a.pdf"),
                (io.BytesIO(pdf), "b.pdf"),
            ]
        }
        resp = self.client.post("/unir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"), "La respuesta no es un PDF")
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("unido.pdf", cd)


class TestImagenAPdfPost(TempUploadMixin, unittest.TestCase):
    """POST /imagen-a-pdf -> 200. [CONFIRMADO]"""

    def test_post_imagen_a_pdf(self):
        img = make_image_bytes()
        data = {"files": [(io.BytesIO(img), "a.png")]}
        resp = self.client.post("/imagen-a-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"), "La respuesta no es un PDF")
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("imagenes.pdf", cd)


class TestDeferredDownloadsFixed(TempUploadMixin, unittest.TestCase):
    """Tras M0, /comprimir y /pdf-a-word entregan resultado y enlace de descarga. [CONFIRMADO]"""

    def test_post_comprimir_succeeds_after_m0(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/comprimir", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("PDF optimizado", body)
        self.assertIn("/descargar_comprimido/", body)

    def test_post_pdf_a_word_succeeds_after_m0(self):
        pdf = make_pdf_bytes()
        data = {"file": (io.BytesIO(pdf), "a.pdf")}
        resp = self.client.post("/pdf-a-word", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Conversión completada", body)
        self.assertIn("/descargar_word/", body)


class TestValidDownloadUUID(TempUploadMixin, unittest.TestCase):
    """Descarga valida con token UUID -> 200 y limpieza posterior. [CONFIRMADO]"""

    def test_descargar_comprimido_valid_uuid_200(self):
        token = str(uuid.uuid4())
        folder = os.path.join(self.uploads, token)
        os.makedirs(folder)
        with open(os.path.join(folder, "comprimido.pdf"), "wb") as f:
            f.write(b"%PDF-1.4\n%fake\n")

        resp = self.client.get(f"/descargar_comprimido/{token}")
        self.assertEqual(resp.status_code, 200)
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("comprimido.pdf", cd)
        self.assertFalse(os.path.exists(folder), "La carpeta temporal no se limpio")

    def test_descargar_word_valid_uuid_200(self):
        token = str(uuid.uuid4())
        folder = os.path.join(self.uploads, token)
        os.makedirs(folder)
        with open(os.path.join(folder, "convertido.docx"), "wb") as f:
            f.write(b"PK\x03\x04fake")

        resp = self.client.get(f"/descargar_word/{token}")
        self.assertEqual(resp.status_code, 200)
        cd = resp.headers.get("Content-Disposition", "")
        self.assertIn("convertido.docx", cd)
        self.assertFalse(os.path.exists(folder), "La carpeta temporal no se limpio")


class TestC01Traversal(TempUploadMixin, unittest.TestCase):
    """C-01: tokens de traversal. cleanup_folder monkeypatcheado (no borra).

    Estado actual (sin fix): '..' y el symlink sirven el archivo del padre (200)
    y cleanup_folder apuntaria fuera de uploads. Las aserciones de 404 documentan
    el comportamiento deseado y FALLAN hoy (evidencia del bug).
    """

    def setUp(self):
        super().setUp()
        self._orig_cleanup = app_module.cleanup_folder
        self.cleanup_calls = []

        def _spy(path):
            self.cleanup_calls.append(path)

        app_module.cleanup_folder = _spy

    def tearDown(self):
        app_module.cleanup_folder = self._orig_cleanup
        super().tearDown()

    def _make_sentinel(self, name):
        parent = os.path.dirname(self.uploads)
        path = os.path.join(parent, name)
        with open(path, "wb") as f:
            f.write(b"SENTINEL")
        return parent, path

    def test_c01_dotdot_returns_404_desired(self):
        self._make_sentinel("comprimido.pdf")
        resp = self.client.get("/descargar_comprimido/..")
        self.assertEqual(resp.status_code, 404)

    def test_c01_dotdot_does_not_delete_sentinel(self):
        parent, sentinel = self._make_sentinel("comprimido.pdf")
        self.client.get("/descargar_comprimido/..")
        self.assertTrue(os.path.exists(sentinel), "El centinela del padre fue borrado")

    def test_c01_dotdot_does_not_invoke_cleanup_outside_uploads(self):
        self._make_sentinel("comprimido.pdf")
        self.client.get("/descargar_comprimido/..")
        # Tras M0 el token invalido se rechaza antes de limpiar: no debe
        # invocarse cleanup_folder con rutas derivadas de la URL.
        self.assertFalse(
            self.cleanup_calls,
            "cleanup_folder no debe llamarse para un token invalido",
        )

    def test_c01_percent2e2e_returns_404(self):
        self._make_sentinel("comprimido.pdf")
        resp = self.client.get("/descargar_comprimido/%2e%2e")
        self.assertEqual(resp.status_code, 404)

    def test_c01_absolute_path_returns_404(self):
        resp = self.client.get("/descargar_comprimido/etc/passwd")
        self.assertEqual(resp.status_code, 404)

    def test_c01_symlink_returns_404_desired(self):
        parent, sentinel = self._make_sentinel("comprimido.pdf")
        link = os.path.join(self.uploads, "link_outside")
        os.symlink(parent, link)
        resp = self.client.get("/descargar_comprimido/link_outside")
        self.assertEqual(resp.status_code, 404)

    def test_c01_symlink_does_not_delete_sentinel(self):
        parent, sentinel = self._make_sentinel("comprimido.pdf")
        link = os.path.join(self.uploads, "link_outside")
        os.symlink(parent, link)
        self.client.get("/descargar_comprimido/link_outside")
        self.assertTrue(os.path.exists(sentinel), "El centinela fue borrado")


class TestErrorState(TempUploadMixin, unittest.TestCase):
    """Estado de error y ausencia de traceback/str(e) crudo. [CONFIRMADO]"""

    def test_invalid_pdf_returns_error_page_no_traceback(self):
        data = {"file": (io.BytesIO(b"esto no es un pdf"), "malo.pdf")}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("no se puede leer como PDF", body)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("site-packages", body)

    def test_missing_file_returns_error(self):
        resp = self.client.post("/rotar", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Selecciona un PDF", body)

    def test_unhandled_exception_shows_explicit_error(self):
        with mock.patch.object(app_module, "_create_temp_dir", side_effect=RuntimeError("boom")):
            data = {"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "angle": "90"}
            resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 500)
        body = resp.data.decode("utf-8", "replace")
        self.assertIn("Causa probable", body)
        self.assertIn("Cómo solucionarlo", body)
        self.assertIn("Detalle técnico", body)
        self.assertIn("boom", body)

    def test_unhandled_exception_api_returns_json(self):
        with mock.patch.object(app_module, "_create_temp_dir", side_effect=RuntimeError("boom")):
            resp = self.client.post(
                "/api/v1/tools/rotar",
                data={"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "angle": "90"},
                headers={"Authorization": f"Bearer {app_module.get_or_create_api_token()}"},
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 500)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("cause", payload)
        self.assertIn("fix", payload)
        self.assertIn("boom", payload["error"])


class TestSendFileAndCleanup(TempUploadMixin, unittest.TestCase):
    """El archivo se lee en memoria antes de limpiar (fix WinError 32). [CONFIRMADO]"""

    def test_send_file_and_cleanup_returns_data_and_removes_temp_dir(self):
        temp_dir = app_module._create_temp_dir()
        output_path = os.path.join(temp_dir, "marcado.pdf")
        with open(output_path, "wb") as fh:
            fh.write(b"%PDF-1.4 contenido")

        with app_module.app.test_request_context("/rotar"):
            resp = app_module._send_file_and_cleanup(
                output_path, "marcado.pdf", temp_dir, mimetype="application/pdf"
            )
            body = app_module._response_body(resp)

        self.assertEqual(body, b"%PDF-1.4 contenido")
        self.assertEqual(resp.headers["Content-Disposition"], "attachment; filename=marcado.pdf")
        self.assertEqual(resp.headers["Cache-Control"], "no-store")
        self.assertFalse(os.path.exists(temp_dir), "la carpeta temporal no se limpió")

    def test_send_file_and_cleanup_cleans_even_if_read_fails(self):
        temp_dir = app_module._create_temp_dir()
        missing_path = os.path.join(temp_dir, "no_existe.pdf")

        with self.assertRaises(FileNotFoundError):
            app_module._send_file_and_cleanup(missing_path, "x.pdf", temp_dir)

        self.assertFalse(os.path.exists(temp_dir), "la carpeta temporal no se limpió al fallar")

    def test_cleanup_runs_while_original_path_still_open(self):
        """Simula el bloqueo de Windows: limpiar con el archivo abierto no falla."""
        temp_dir = app_module._create_temp_dir()
        output_path = os.path.join(temp_dir, "marcado.pdf")
        with open(output_path, "wb") as fh:
            fh.write(b"%PDF-1.4 datos")

        with open(output_path, "rb") as still_open:
            self.assertEqual(still_open.read(), b"%PDF-1.4 datos")
            with app_module.app.test_request_context("/marcar-agua"):
                resp = app_module._send_file_and_cleanup(output_path, "marcado.pdf", temp_dir)
                body = app_module._response_body(resp)

        self.assertEqual(body, b"%PDF-1.4 datos")
        self.assertFalse(os.path.exists(temp_dir))

    def test_real_tool_post_leaves_no_temp_folder(self):
        """Una herramienta real (rotar) limpia su temporal y devuelve el PDF."""
        before = set(os.listdir(self.uploads))
        data = {"file": (io.BytesIO(make_pdf_bytes()), "ok.pdf"), "angle": "90"}
        resp = self.client.post("/rotar", data=data, content_type="multipart/form-data")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"), "no devolvió un PDF")
        after = set(os.listdir(self.uploads))
        self.assertEqual(after, before, f"quedaron temporales: {after - before}")

    def test_all_tool_routes_use_memory_helper(self):
        """Ninguna ruta envía un archivo por ruta (causa del WinError 32)."""
        with open(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
            encoding="utf-8",
        ) as handle:
            source = handle.read()
        sends = [line.strip() for line in source.splitlines() if "send_file(" in line]
        self.assertEqual(
            sends,
            ["response = send_file(BytesIO(data), **kwargs)"],
            f"quedan envíos por ruta: {sends}",
        )


class TestRepoUploadsEmpty(unittest.TestCase):
    """uploads/ del repo queda vacio al terminar. [CONFIRMADO]"""

    def test_repo_uploads_empty(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads = os.path.join(repo_root, "uploads")
        if os.path.exists(uploads):
            self.assertEqual(os.listdir(uploads), [], "uploads/ del repo no esta vacio")


if __name__ == "__main__":
    unittest.main()
