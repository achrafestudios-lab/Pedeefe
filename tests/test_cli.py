"""Tests del CLI local de Pedeefe (v2.0).

El CLI se prueba sin abrir puertos: se sustituyen las dos funciones que hablan
con la API y se comprueban el reparto de archivos, los parámetros y la salida.

Ejecutar con:

    .venv/bin/python -m unittest discover -s tests
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "cli")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import app as app_module  # noqa: E402
import pedeefe as cli  # noqa: E402


def catalog_payload():
    """Catálogo idéntico al que sirve la API, sin red."""
    tools = []
    for slug, spec in app_module.API_TOOLS.items():
        tools.append({
            "slug": slug,
            "label": spec["label"],
            "files": spec["files"],
            "params": spec["params"],
        })
    return {"ok": True, "version": "2.0.1", "count": len(tools), "tools": tools}


class _CliTestCase(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"PEDEEFE_TOKEN": "cli-token"})
        self._env.start()
        self.catalog = patch.object(cli, "api_get", return_value=catalog_payload())
        self.catalog.start()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def tearDown(self):
        self.catalog.stop()
        self._env.stop()

    def run_cli(self, argv):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            return cli.main(argv)


class TestCliCatalog(_CliTestCase):
    """El listado sale del catálogo de la API. [CONFIRMADO]"""

    def test_list_shows_tools_and_fields(self):
        code = self.run_cli(["list"])
        output = self.stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("unir", output)
        self.assertIn("certificate", output)
        self.assertIn("archivos:", output)

    def test_help_does_not_need_backend(self):
        self.catalog.stop()
        code = self.run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("pedeefe list", self.stdout.getvalue())

    def test_missing_backend_is_reported(self):
        self.catalog.stop()
        with patch.object(cli, "api_get", side_effect=URLError("sin servidor")):
            code = self.run_cli(["list"])
        self.assertEqual(code, 1)
        self.assertIn("backend local", self.stderr.getvalue())


class TestCliExecution(_CliTestCase):
    """El CLI envía archivos y parámetros y guarda el resultado. [CONFIRMADO]"""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory(prefix="pedeefe_cli_")
        self.addCleanup(self._tmp.cleanup)
        self.first = Path(self._tmp.name, "a.pdf")
        self.second = Path(self._tmp.name, "b.pdf")
        self.first.write_bytes(b"%PDF-1.4 first")
        self.second.write_bytes(b"%PDF-1.4 second")
        self.response = patch.object(cli, "api_call", return_value=(
            {
                "X-Pedeefe-Format": "file",
                "Content-Disposition": 'attachment; filename="unido.pdf"',
            },
            b"%PDF-1.4 result",
        ))

    def test_unir_envia_dos_archivos_y_guarda_salida(self):
        with self.response as call:
            output = Path(self._tmp.name, "salida.pdf")
            code = self.run_cli(["unir", str(self.first), str(self.second), "-o", str(output)])
        self.assertEqual(code, 0)
        self.assertEqual(output.read_bytes(), b"%PDF-1.4 result")
        args = call.call_args.args
        self.assertEqual(args[2], "unir")
        self.assertEqual(args[4], [("files", str(self.first)), ("files", str(self.second))])

    def test_parametros_se_envian_como_campos(self):
        with self.response as call:
            self.run_cli([
                "rotar", str(self.first), "--angle", "270",
                "-o", str(Path(self._tmp.name, "rotado.pdf")),
            ])
        self.assertEqual(call.call_args.args[3], {"angle": ["270"]})

    def test_pedeefe_url_se_usa_tambien_al_ejecutar(self):
        with patch.dict(os.environ, {"PEDEEFE_URL": "http://127.0.0.1:49999"}), \
                self.response as call:
            code = self.run_cli([
                "comprimir", str(self.first),
                "-o", str(Path(self._tmp.name, "salida.pdf")),
            ])
        self.assertEqual(code, 0)
        self.assertEqual(call.call_args.args[0], "http://127.0.0.1:49999")

    def test_salida_no_sobrescribe_entrada(self):
        with self.response:
            code = self.run_cli(["comprimir", str(self.first), "-o", str(self.first)])
        self.assertEqual(code, 1)
        self.assertEqual(self.first.read_bytes(), b"%PDF-1.4 first")

    def test_error_de_la_api_se_muestra_en_stderr(self):
        with patch.object(cli, "api_call", side_effect=cli.CLIError("PDF no válido")):
            code = self.run_cli(["comprimir", str(self.first)])
        self.assertEqual(code, 1)
        self.assertIn("PDF no válido", self.stderr.getvalue())

    def test_respuesta_json_se_imprime(self):
        with patch.object(cli, "api_call", return_value=(
            {"Content-Type": "application/json"},
            b'{"ok": true, "tool": "comparar"}',
        )):
            code = self.run_cli(["comparar", str(self.first), str(self.second)])
        self.assertEqual(code, 0)
        self.assertIn('"tool": "comparar"', self.stdout.getvalue())


class TestCliHelpers(unittest.TestCase):
    """Funciones puras del CLI. [CONFIRMADO]"""

    def test_reparto_de_archivos_multiples_y_simples(self):
        spec = next(t for t in catalog_payload()["tools"] if t["slug"] == "unir")
        files = cli._assign_files(spec, ["a.pdf", "b.pdf", "c.pdf"])
        self.assertEqual([name for name, _ in files], ["files"] * 3)

        spec = next(t for t in catalog_payload()["tools"] if t["slug"] == "firmar")
        files = cli._assign_files(spec, ["a.pdf", "cert.p12"])
        self.assertEqual(files, [("file", "a.pdf"), ("certificate", "cert.p12")])
        with self.assertRaises(cli.CLIError):
            cli._assign_files(spec, ["a.pdf"])

    def test_api_get_muestra_error_de_token(self):
        error = HTTPError(
            "http://127.0.0.1:43210/api/v1/tools", 401, "Unauthorized", {},
            io.BytesIO(b'{"ok": false, "error": "Token de API local no v\\u00e1lido."}'),
        )
        with patch.object(cli, "urlopen", side_effect=error):
            with self.assertRaises(cli.CLIError) as raised:
                cli.api_get("http://127.0.0.1:43210", "incorrecto", "/api/v1/tools")
        self.assertIn("Token de API local", str(raised.exception))

    def test_multipart_incluye_campos_y_archivos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "a.pdf")
            path.write_bytes(b"%PDF-1.4")
            body, content_type = cli.multipart_body({"angle": ["90"]}, [("file", path)])
        self.assertIn("multipart/form-data; boundary=", content_type)
        self.assertIn(b'name="angle"', body)
        self.assertIn(b'name="file"', body)
        self.assertIn(b'filename="a.pdf"', body)
        self.assertIn(b"%PDF-1.4", body)


if __name__ == "__main__":
    unittest.main()
