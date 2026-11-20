"""Tests de la PWA instalable de Pedeefe (v1.9).

La PWA no cambia el modelo local-first: el service worker solo guarda la
cáscara y el procesamiento de PDFs sigue necesitando el backend en loopback.
Ejecutar con:

    .venv/bin/python -m unittest discover -s tests
"""

import json
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402

STATIC = ROOT / "static"


class TestPWAManifest(unittest.TestCase):
    """Manifiesto e iconos de instalación. [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        with (STATIC / "manifest.json").open(encoding="utf-8") as handle:
            cls.manifest = json.load(handle)

    def test_installable_fields(self):
        manifest = self.manifest
        self.assertEqual(manifest["name"], "Pedeefe — Herramientas PDF locales")
        self.assertEqual(manifest["short_name"], "Pedeefe")
        self.assertEqual(manifest["lang"], "es")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#DE2B3F")

    def test_icons_are_local_and_have_required_sizes(self):
        icons = self.manifest["icons"]
        sizes = {icon["sizes"] for icon in icons}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        for icon in icons:
            self.assertTrue(icon["src"].startswith("/static/"))
            self.assertEqual(icon["type"], "image/png")
        any_icons = [i for i in icons if i["purpose"] == "any"]
        self.assertTrue({"192x192", "512x512"}.issubset({i["sizes"] for i in any_icons}))
        maskable = [i for i in icons if i["purpose"] == "maskable"]
        self.assertTrue(maskable)

    def test_icon_files_are_valid_pngs(self):
        expected = {
            "icon-192.png": (192, 192),
            "icon-512.png": (512, 512),
            "icon-maskable-512.png": (512, 512),
        }
        for name, size in expected.items():
            with self.subTest(icon=name):
                with Image.open(STATIC / "icons" / name) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.size, size)


class TestServiceWorker(unittest.TestCase):
    """Ruta, cabeceras y comportamiento del service worker. [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        cls.client = app_module.app.test_client()
        cls.response = cls.client.get("/sw.js")
        cls.source = (STATIC / "js" / "sw.js").read_text(encoding="utf-8")

    def test_route_serves_worker_with_scope_headers(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertIn("application/javascript", self.response.headers["Content-Type"])
        self.assertEqual(self.response.headers["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", self.response.headers["Cache-Control"])

    def test_manifest_route_uses_spec_mime_type(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response.headers["Content-Type"])
        self.assertEqual(json.loads(response.data)["short_name"], "Pedeefe")

    def test_worker_caches_only_app_shell(self):
        for asset in (
            "/static/css/style.css",
            "/static/js/main.js",
            "/static/js/productivity.js",
            "/manifest.webmanifest",
            "/static/offline.html",
        ):
            with self.subTest(asset=asset):
                self.assertIn(f'"{asset}"', self.source)
        self.assertIn("pedeefe-v2.3", self.source)

    def test_worker_never_intercepts_downloads_or_external_urls(self):
        self.assertIn('url.pathname.startsWith("/descargar_")', self.source)
        self.assertIn("url.origin !== self.location.origin", self.source)
        self.assertIn('request.method !== "GET"', self.source)
        self.assertNotIn("http://", self.source)
        self.assertNotIn("https://", self.source)

    def test_offline_page_is_local_and_actionable(self):
        offline = (STATIC / "offline.html").read_text(encoding="utf-8")
        self.assertIn('lang="es"', offline)
        self.assertIn("/static/css/style.css", offline)
        self.assertIn("Reintentar", offline)
        self.assertNotIn("http://", offline)
        self.assertNotIn("https://", offline)


class TestPWARegistration(unittest.TestCase):
    """El registro es seguro y no afecta a Electron. [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        cls.body = app_module.app.test_client().get("/").data.decode("utf-8", "replace")
        cls.main_js = (STATIC / "js" / "main.js").read_text(encoding="utf-8")

    def test_base_template_links_manifest_and_icon(self):
        self.assertIn('rel="manifest"', self.body)
        self.assertIn("/manifest.webmanifest", self.body)
        self.assertIn("icon-192.png", self.body)
        self.assertIn('name="theme-color"', self.body)

    def test_registration_is_secure_and_skips_electron(self):
        self.assertIn('serviceWorker" in navigator', self.main_js)
        self.assertIn("window.isSecureContext", self.main_js)
        self.assertIn('navigator.userAgent.indexOf("Electron")', self.main_js)
        self.assertIn('navigator.serviceWorker.register("/sw.js", { scope: "/" })', self.main_js)


if __name__ == "__main__":
    unittest.main()
