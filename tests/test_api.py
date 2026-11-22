"""Tests de la API JSON local de Pedeefe (v2.0).

La API comparte el servidor Flask de loopback, exige el token local y reutiliza
los handlers web. Estos tests usan ``test_client``: no abren puertos ni dejan
archivos en el repositorio.

Ejecutar con:

    .venv/bin/python -m unittest discover -s tests
"""

import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from local_token import get_or_create_api_token, token_path  # noqa: E402

TOKEN = "test-token-local"


def sample_pdf():
    """Genera un PDF mínimo en memoria para las pruebas."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(20, 20, "Pedeefe")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class _ApiTestCase(unittest.TestCase):
    """Fija el token por entorno para no crear archivos en el perfil."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"PEDEEFE_TOKEN": TOKEN})
        self._env.start()
        self.client = app_module.app.test_client()
        self.headers = {"Authorization": "Bearer " + TOKEN}

    def tearDown(self):
        self._env.stop()


class TestApiAuthentication(_ApiTestCase):
    """El token protege solo la API, no la interfaz web. [CONFIRMADO]"""

    def test_catalog_requires_token(self):
        response = self.client.get("/api/v1/tools")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Token", response.get_json()["error"])

    def test_wrong_token_is_rejected(self):
        response = self.client.get(
            "/api/v1/tools", headers={"Authorization": "Bearer incorrecto"}
        )
        self.assertEqual(response.status_code, 401)

    def test_web_pages_remain_public_in_localhost(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/unir").status_code, 200)


class TestApiCatalog(_ApiTestCase):
    """El catálogo describe todas las herramientas de procesamiento. [CONFIRMADO]"""

    def test_catalog_lists_all_processing_tools(self):
        payload = self.client.get("/api/v1/tools", headers=self.headers).get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["version"], "2.4.1")
        self.assertEqual(payload["count"], 29)
        slugs = [tool["slug"] for tool in payload["tools"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for expected in (
            "unir", "dividir", "comprimir", "ocr", "ocr-a-pdf",
            "limpiar-metadatos", "firmar", "comparar", "lotes", "pdf-a-markdown",
        ):
            self.assertIn(expected, slugs)
        for tool in payload["tools"]:
            self.assertTrue(tool["label"])
            self.assertTrue(tool["files"])
            self.assertIsInstance(tool["params"], list)

    def test_catalog_describes_multi_file_fields(self):
        payload = self.client.get("/api/v1/tools", headers=self.headers).get_json()
        tools = {tool["slug"]: tool for tool in payload["tools"]}
        self.assertTrue(tools["unir"]["files"][0]["multiple"])
        self.assertTrue(tools["lotes"]["files"][0]["multiple"])
        self.assertFalse(tools["comparar"]["files"][0]["multiple"])
        self.assertIn("certificate", [f["name"] for f in tools["firmar"]["files"]])

    def test_catalog_describes_ocr_language_param(self):
        payload = self.client.get("/api/v1/tools", headers=self.headers).get_json()
        tools = {tool["slug"]: tool for tool in payload["tools"]}
        self.assertIn("lang", tools["ocr"]["params"])
        self.assertIn("lang", tools["ocr-a-pdf"]["params"])

    def test_catalog_describes_metadata_options(self):
        payload = self.client.get("/api/v1/tools", headers=self.headers).get_json()
        tools = {tool["slug"]: tool for tool in payload["tools"]}
        params = tools["limpiar-metadatos"]["params"]
        self.assertIn("clear_info", params)
        self.assertIn("clear_xmp", params)
        self.assertIn("title", params)


class TestApiExecution(_ApiTestCase):
    """Los handlers web se ejecutan y su salida se normaliza. [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="pedeefe_api_")
        cls.addClassCleanup(shutil.rmtree, cls._tmp, True)
        for name in ("a.pdf", "b.pdf"):
            Path(cls._tmp, name).write_bytes(sample_pdf())

    def _post(self, slug, data):
        return self.client.post(
            "/api/v1/tools/" + slug,
            headers=self.headers,
            data=data,
            content_type="multipart/form-data",
        )

    def test_unir_devuelve_pdf(self):
        with open(Path(self._tmp, "a.pdf"), "rb") as first, \
                open(Path(self._tmp, "b.pdf"), "rb") as second:
            response = self._post("unir", {"files": [(first, "a.pdf"), (second, "b.pdf")]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Pedeefe-Format"], "file")
        self.assertIn("unido.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.data[:5], b"%PDF-")

    def test_rotar_devuelve_pdf(self):
        response = self._post("rotar", {
            "file": (io.BytesIO(sample_pdf()), "a.pdf"),
            "angle": "90",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("rotado.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.data[:5], b"%PDF-")

    def test_descarga_diferida_se_sigue_y_se_limpia(self):
        response = self._post("comprimir", {
            "file": (io.BytesIO(sample_pdf()), "a.pdf"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("comprimido.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.data[:5], b"%PDF-")
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_limpiar_metadatos_devuelve_pdf(self):
        response = self._post("limpiar-metadatos", {
            "file": (io.BytesIO(sample_pdf()), "a.pdf"),
            "clear_info": "on",
            "clear_xmp": "on",
            "clear_attachments": "on",
            "clear_js": "on",
            "clear_page_meta": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("sin_metadatos.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.data[:5], b"%PDF-")
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_ocr_a_pdf_devuelve_pdf(self):
        try:
            from test_tools import make_tesseract_layer_bytes
        except ImportError:  # ejecución como paquete
            from tests.test_tools import make_tesseract_layer_bytes
        from PIL import Image

        with patch.object(
            app_module, "convert_from_path", return_value=[Image.new("RGB", (20, 20))]
        ), patch.object(
            app_module.pytesseract, "image_to_pdf_or_hocr",
            side_effect=lambda image, lang=None, extension=None:
                make_tesseract_layer_bytes(),
        ):
            response = self._post("ocr-a-pdf", {
                "file": (io.BytesIO(sample_pdf()), "a.pdf"), "lang": "spa",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("buscable.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.data[:5], b"%PDF-")
        self.assertEqual(os.listdir(app_module.UPLOAD_FOLDER), [])

    def test_error_de_formulario_es_json(self):
        response = self._post("unir", {})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertIn("PDFs", response.get_json()["error"])

    def test_herramienta_desconocida(self):
        response = self._post("no-existe", {})
        self.assertEqual(response.status_code, 404)
        self.assertIn("desconocida", response.get_json()["error"])


class TestLocalToken(unittest.TestCase):
    """El token se crea con permisos restringidos y respeta el entorno. [CONFIRMADO]"""

    def test_env_override_no_escribe_archivo(self):
        with patch.dict(os.environ, {"PEDEEFE_TOKEN": "desde-entorno"}):
            self.assertEqual(get_or_create_api_token(), "desde-entorno")

    def test_archivo_se_crea_con_permisos_600(self):
        if os.name == "nt":
            self.skipTest("los bits POSIX de permiso no aplican en Windows")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, ".pedeefe", "token")
            with patch.dict(os.environ, {}, clear=True), patch(
                "local_token.token_path", return_value=path
            ):
                token = get_or_create_api_token()
                self.assertEqual(get_or_create_api_token(), token)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            self.assertEqual(
                stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700
            )

    def test_ruta_por_defecto_esta_en_el_perfil(self):
        self.assertTrue(token_path().endswith(os.path.join(".pedeefe", "token")))


if __name__ == "__main__":
    unittest.main()
