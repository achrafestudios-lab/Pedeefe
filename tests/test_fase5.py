"""Tests de v1.4: firmar, censurar y comparar PDF.

Usa el cliente de test de Flask (sin abrir puertos), un certificado PKCS#12
autofirmado generado en memoria y directorios temporales aislados. Ejecutar:

    .venv/bin/python -m unittest discover -s tests
"""

import datetime
import io
import os
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pypdf import PdfReader

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover — versiones antiguas
    import fitz

import app as app_module

try:
    from test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes
except ImportError:  # ejecución como paquete
    from tests.test_tools import TempUploadMixin, assert_no_traceback, make_pdf_bytes


CERT_PASSWORD = "clave"


def _make_pkcs12(password=CERT_PASSWORD, common_name="Pedeefe Test"):
    """Genera un PKCS#12 autofirmado válido para probar la firma real."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        common_name.encode("utf-8"),
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(password.encode("utf-8")),
    )


PKCS12_BYTES = _make_pkcs12()


class TestFirmar(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        response = self.client.get("/firmar")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Firmar PDF", response.data)
        assert_no_traceback(self, response.data.decode("utf-8", "replace"))

    def test_post_valid_creates_real_signature(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes()), "documento.pdf"),
            "certificate": (io.BytesIO(PKCS12_BYTES), "firma.p12"),
            "password": CERT_PASSWORD,
        }
        response = self.client.post("/firmar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"%PDF"))
        self.assertIn("firmado.pdf", response.headers.get("Content-Disposition", ""))
        self.assertIn(b"/ByteRange", response.data)
        self.assertIn(b"/Sig", response.data)
        self.assertEqual(len(PdfReader(io.BytesIO(response.data)).pages), 1)
        self.assertEqual(os.listdir(self.uploads), [])
        response.close()

    def test_wrong_password_shows_friendly_error(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes()), "documento.pdf"),
            "certificate": (io.BytesIO(PKCS12_BYTES), "firma.p12"),
            "password": "incorrecta",
        }
        response = self.client.post("/firmar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No se pudo firmar", response.data)
        assert_no_traceback(self, response.data.decode("utf-8", "replace"))
        self.assertEqual(os.listdir(self.uploads), [])

    def test_certificate_extension_validated(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes()), "documento.pdf"),
            "certificate": (io.BytesIO(PKCS12_BYTES), "firma.txt"),
            "password": CERT_PASSWORD,
        }
        response = self.client.post("/firmar", data=data, content_type="multipart/form-data")
        self.assertIn(b"PKCS#12", response.data)

    def test_missing_pdf_shows_error(self):
        response = self.client.post("/firmar", data={}, content_type="multipart/form-data")
        self.assertIn(b"Selecciona el PDF", response.data)


class TestCensurar(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        response = self.client.get("/censurar")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Censurar PDF", response.data)

    def test_post_removes_text_permanently(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes(text="confidencial")), "documento.pdf"),
            "terms": "confidencial",
        }
        response = self.client.post("/censurar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"%PDF"))
        self.assertIn("censurado.pdf", response.headers.get("Content-Disposition", ""))
        with fitz.open(stream=response.data, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
        self.assertNotIn("confidencial", text)
        self.assertIn("pagina 1", text)
        self.assertEqual(os.listdir(self.uploads), [])
        response.close()

    def test_multiple_terms_separated_by_lines_and_commas(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes(text="secreto")), "documento.pdf"),
            "terms": "secreto, inexistente\n tampoco",
        }
        response = self.client.post("/censurar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"%PDF"))
        response.close()

    def test_no_match_shows_error(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes()), "documento.pdf"),
            "terms": "no aparece",
        }
        response = self.client.post("/censurar", data=data, content_type="multipart/form-data")
        self.assertIn(b"No se encontr", response.data)
        assert_no_traceback(self, response.data.decode("utf-8", "replace"))
        self.assertEqual(os.listdir(self.uploads), [])

    def test_empty_terms_shows_error(self):
        data = {
            "file": (io.BytesIO(make_pdf_bytes()), "documento.pdf"),
            "terms": "   ",
        }
        response = self.client.post("/censurar", data=data, content_type="multipart/form-data")
        self.assertIn(b"al menos un t", response.data)


class TestComparar(TempUploadMixin, unittest.TestCase):
    def test_get_200(self):
        response = self.client.get("/comparar")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Comparar PDF", response.data)

    def test_post_shows_diff_between_documents(self):
        data = {
            "file1": (io.BytesIO(make_pdf_bytes(text="original")), "uno.pdf"),
            "file2": (io.BytesIO(make_pdf_bytes(text="modificado")), "dos.pdf"),
        }
        response = self.client.post("/comparar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertIn(b"1 de 1", body)
        self.assertIn(b"con cambios", body)
        # HtmlDiff resalta los cambios con span; comprobamos las clases, no el texto continuo.
        self.assertIn(b"diff_chg", body)
        self.assertIn(b"diff_add", body)
        self.assertIn(b"pagina&nbsp;1", body)
        self.assertIn(b"table class=\"diff\"", body)
        assert_no_traceback(self, body.decode("utf-8", "replace"))
        self.assertEqual(os.listdir(self.uploads), [])

    def test_identical_documents_show_no_changes(self):
        pdf = make_pdf_bytes()
        data = {
            "file1": (io.BytesIO(pdf), "uno.pdf"),
            "file2": (io.BytesIO(pdf), "dos.pdf"),
        }
        response = self.client.post("/comparar", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"0 de 1", response.data)
        self.assertIn(b"sin cambios", response.data)

    def test_missing_second_file_shows_error(self):
        data = {
            "file1": (io.BytesIO(make_pdf_bytes()), "uno.pdf"),
        }
        response = self.client.post("/comparar", data=data, content_type="multipart/form-data")
        self.assertIn(b"segundo PDF", response.data)

    def test_invalid_pdf_shows_error(self):
        data = {
            "file1": (io.BytesIO(b"no es un pdf"), "uno.pdf"),
            "file2": (io.BytesIO(make_pdf_bytes()), "dos.pdf"),
        }
        response = self.client.post("/comparar", data=data, content_type="multipart/form-data")
        self.assertIn(b"no es un PDF v", response.data)


if __name__ == "__main__":
    unittest.main()
