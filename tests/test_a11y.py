"""Tests de v1.6: accesibilidad y tema oscuro.

Comprobaciones estáticas de plantillas/CSS/JS más render con el cliente de test
de Flask. No requieren servidor ni puerto. Ejecutar:

    .venv/bin/python -m unittest discover -s tests
"""

import re
import unittest
from pathlib import Path

try:
    from test_tools import TempUploadMixin, assert_no_traceback
except ImportError:  # ejecución como paquete
    from tests.test_tools import TempUploadMixin, assert_no_traceback


ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "static" / "css" / "style.css"
JS_PATH = ROOT / "static" / "js"

PAGE_ROUTES = [
    "/", "/unir", "/dividir", "/recortar-pdf", "/reordenar-pdf",
    "/comprimir", "/comprimir-real", "/ocr", "/ocr-a-pdf",
    "/limpiar-metadatos", "/pdf-a-imagen", "/imagen-a-pdf",
    "/pdf-a-word", "/pdf-a-excel", "/pdf-a-powerpoint", "/pdf-a-html", "/pdf-a-markdown",
    "/word-a-pdf", "/excel-a-pdf", "/powerpoint-a-pdf", "/html-a-pdf",
    "/rotar", "/numerar", "/marcar-agua", "/proteger", "/desproteger",
    "/firmar", "/censurar", "/comparar", "/lotes", "/historial", "/plantillas",
]

HEADING_EMOJIS = [
    "✂️", "⚠️", "🗜️", "🖼️", "✍️", "🔗", "🔀", "📦", "📷", "📝",
    "📊", "📽️", "🌐", "📄", "📈", "🔄", "🔒", "🔓", "🔍", "💧",
    "🔢", "🖤", "🔎", "🧰", "🕘", "🧩", "✅",
]


class TestBaseAccessibility(TempUploadMixin, unittest.TestCase):
    """Estructura accesible común a todas las páginas. [CONFIRMADO]"""

    def test_html_language_and_color_scheme(self):
        body = self.client.get("/").data.decode("utf-8", "replace")
        self.assertIn('<html lang="es">', body)
        self.assertIn('name="color-scheme" content="light dark"', body)

    def test_skip_link_targets_main(self):
        body = self.client.get("/").data.decode("utf-8", "replace")
        self.assertIn('class="skip-link" href="#main-content"', body)
        self.assertIn('id="main-content" tabindex="-1"', body)
        self.assertIn("Saltar al contenido principal", body)

    def test_skip_link_on_every_page(self):
        for route in PAGE_ROUTES:
            with self.subTest(route=route):
                body = self.client.get(route).data.decode("utf-8", "replace")
                self.assertIn('class="skip-link"', body)
                self.assertIn('id="main-content"', body)
                assert_no_traceback(self, body)

    def test_global_live_region(self):
        for route in ("/", "/lotes", "/historial", "/plantillas"):
            with self.subTest(route=route):
                body = self.client.get(route).data.decode("utf-8", "replace")
                self.assertIn('id="productivity-status"', body)
                self.assertIn('role="status"', body)
                self.assertIn('aria-live="polite"', body)

    def test_file_inputs_have_accessible_name(self):
        for route in PAGE_ROUTES:
            with self.subTest(route=route):
                body = self.client.get(route).data.decode("utf-8", "replace")
                for tag in re.findall(r"<input[^>]*type=\"file\"[^>]*>", body):
                    labelled = re.search(r'aria-labelledby="([^"]+)"', tag)
                    if labelled:
                        self.assertIn(f'id="{labelled.group(1)}"', body)
                        continue
                    field_id = re.search(r'id="([^"]+)"', tag)
                    self.assertIsNotNone(
                        field_id, f"{route}: input de archivo sin nombre accesible"
                    )
                    self.assertIn(f'<label for="{field_id.group(1)}"', body)

    def test_html_editor_has_label(self):
        body = self.client.get("/html-a-pdf").data.decode("utf-8", "replace")
        self.assertIn('<label for="html_text"', body)
        self.assertIn('id="html_text"', body)
        self.assertNotIn('style="width:100%', body)


class TestDarkThemeAssets(unittest.TestCase):
    """Tokens y preferencia del sistema, sin dependencias nuevas. [CONFIRMADO]"""

    @classmethod
    def setUpClass(cls):
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.main_js = (JS_PATH / "main.js").read_text(encoding="utf-8")
        cls.productivity_js = (JS_PATH / "productivity.js").read_text(encoding="utf-8")

    def test_css_prefers_color_scheme(self):
        self.assertIn("@media (prefers-color-scheme: dark)", self.css)
        for token in ("--color-nav-bg", "--color-on-primary", "--color-bg-alt",
                      "--color-diff-add-bg", "--color-focus-ring"):
            with self.subTest(token=token):
                self.assertIn(token, self.css)

    def test_css_has_no_invalid_zero_var_values(self):
        self.assertNotIn("0.var(", self.css)

    def test_css_has_no_hardcoded_surface_colors(self):
        self.assertNotIn("background: white", self.css)
        self.assertNotIn("color: white", self.css)

    def test_skip_link_styles(self):
        self.assertIn(".skip-link", self.css)
        self.assertIn(".skip-link:focus", self.css)

    def test_js_loading_status_is_announced(self):
        self.assertIn('setAttribute("role", "status")', self.main_js)
        self.assertIn('setAttribute("aria-live", "polite")', self.main_js)
        self.assertIn('event.key !== "Enter"', self.main_js)

    def test_js_list_changes_are_announced(self):
        self.assertIn("function announce(message)", self.productivity_js)
        self.assertIn('getElementById("productivity-status")', self.productivity_js)
        self.assertIn("Entrada eliminada.", self.productivity_js)


class TestTemplateHeadingEmojis(unittest.TestCase):
    """Los emojis de encabezado se ocultan a lectores de pantalla. [CONFIRMADO]"""

    def test_no_bare_emoji_after_heading_open_tag(self):
        for path in sorted((ROOT / "templates").glob("*.html")):
            with self.subTest(template=path.name):
                body = path.read_text(encoding="utf-8")
                for match in re.finditer(r"<h[123]>([^<\s]+) ", body):
                    self.assertNotIn(match.group(1), HEADING_EMOJIS)

    def test_hidden_emoji_spans_exist(self):
        total = 0
        for path in (ROOT / "templates").glob("*.html"):
            total += len(re.findall(r"<h[123]><span aria-hidden=\"true\">", path.read_text(encoding="utf-8")))
        self.assertGreaterEqual(total, 16)


if __name__ == "__main__":
    unittest.main()
