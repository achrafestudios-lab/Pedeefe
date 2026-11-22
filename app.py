import os
import platform
import re
import sys
import uuid
import shutil
import subprocess
import zipfile
import difflib
import traceback
from io import BytesIO
from html import unescape
from flask import Flask, render_template, request, send_file, jsonify, make_response, Response
from werkzeug.exceptions import HTTPException
from local_token import get_or_create_api_token
from pypdf import PdfReader, PdfWriter
import pikepdf
# pdf2image requiere Poppler instalado en el sistema:
#   Ubuntu/Debian: sudo apt install poppler-utils
#   Fedora: sudo dnf install poppler-utils
#   macOS: brew install poppler
from pdf2image import convert_from_path
from PIL import Image

# pytesseract requiere Tesseract OCR instalado en el sistema:
#   Ubuntu/Debian: sudo apt install tesseract-ocr
#   Fedora: sudo dnf install tesseract
#   macOS: brew install tesseract
import pytesseract

# reportlab para generar la marca de agua como PDF
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.lib import colors

# pdf2docx importa el nombre "fitz" de PyMuPDF 1.x y eso emite un aviso a
# stdout; lo silenciamos para no romper el protocolo PEDEE_READY del escritorio.
_stdout = sys.stdout
try:
    sys.stdout = open(os.devnull, "w")
    from pdf2docx import Converter
finally:
    sys.stdout.close()
    sys.stdout = _stdout

# Conversiones adicionales (Fase 4)
try:
    import pymupdf as fitz  # PyMuPDF (el alias "fitz" está obsoleto)
except Exception:  # pragma: no cover — versiones antiguas solo exponen "fitz"
    try:
        import fitz
    except Exception:
        fitz = None
try:
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None
try:
    from pptx import Presentation
    from pptx.util import Inches
except Exception:  # pragma: no cover
    Presentation = None
    Inches = None
try:
    import openpyxl
except Exception:  # pragma: no cover
    openpyxl = None
try:
    from weasyprint import HTML as WeasyHTML
except Exception:  # pragma: no cover
    WeasyHTML = None
# Firma criptográfica (v1.4). Se degrada con un mensaje legible si falta.
try:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers as pyhanko_signers
    from pyhanko.sign.signers import PdfSignatureMetadata
except Exception:  # pragma: no cover
    IncrementalPdfFileWriter = None
    pyhanko_signers = None
    PdfSignatureMetadata = None

app = Flask(__name__)

# Configuración
# PEDEE_UPLOAD_FOLDER permite al paquete de escritorio usar un directorio
# escribible del usuario; el comportamiento por defecto no cambia.
UPLOAD_FOLDER = os.environ.get(
    "PEDEE_UPLOAD_FOLDER",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"),
)
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB máximo por archivo
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Asegurar que uploads/ existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _create_temp_dir():
    """Crea una carpeta temporal privada (0700) para una petición."""
    path = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(path, mode=0o700)
    return path


def cleanup_uploads_folder():
    """Limpia todos los archivos residuales en uploads/ al arrancar la app."""
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isdir(filepath):
                    shutil.rmtree(filepath)
                else:
                    os.remove(filepath)
            except Exception:
                pass  # Ignorar errores de archivos en uso o permisos


# Limpieza de seguridad al inicio
cleanup_uploads_folder()

# Detección de Tesseract OCR al arrancar (para la tarjeta de OCR en la portada)
TESSERACT_AVAILABLE = shutil.which("tesseract") is not None

# v1.8: los paquetes de escritorio no incluyen binarios del sistema. Detectamos
# las cuatro dependencias externas al arrancar para avisar en la portada y dar
# instrucciones de instalación según el sistema operativo.
DEPENDENCY_HINTS = {
    "Windows": {
        "poppler": "Instala Poppler para Windows y añade su carpeta bin al PATH.",
        "ghostscript": "Instala Ghostscript para Windows.",
        "tesseract": "Instala Tesseract OCR para Windows con datos en español.",
        "libreoffice": "Instala LibreOffice para convertir DOC, XLS y PPT antiguos.",
    },
    "Darwin": {
        "poppler": "Instálalo con: brew install poppler",
        "ghostscript": "Instálalo con: brew install ghostscript",
        "tesseract": "Instálalo con: brew install tesseract tesseract-lang",
        "libreoffice": "Instálalo con: brew install --cask libreoffice",
    },
    "Linux": {
        "poppler": "Instálalo con: sudo apt install poppler-utils",
        "ghostscript": "Instálalo con: sudo apt install ghostscript",
        "tesseract": (
            "Instálalo con: sudo apt install tesseract-ocr "
            "tesseract-ocr-spa tesseract-ocr-eng"
        ),
        "libreoffice": "Instálalo con: sudo apt install libreoffice",
    },
}
DEFAULT_DEPENDENCY_HINT = "Instala la dependencia y reinicia Pedeefe."

DEPENDENCY_LABELS = {
    "poppler": "Poppler",
    "ghostscript": "Ghostscript",
    "tesseract": "Tesseract",
    "libreoffice": "LibreOffice",
}

DEPENDENCY_BINARIES = {
    "poppler": ("pdftoppm",),
    "ghostscript": ("gs",),
    "tesseract": ("tesseract",),
    "libreoffice": ("soffice", "libreoffice"),
}


def dependency_status():
    """Devuelve disponibilidad y pista de instalación de cada dependencia."""
    hints = DEPENDENCY_HINTS.get(platform.system(), {})
    return {
        name: {
            "label": DEPENDENCY_LABELS[name],
            "available": any(shutil.which(binary) for binary in binaries),
            "hint": hints.get(name, DEFAULT_DEPENDENCY_HINT),
        }
        for name, binaries in DEPENDENCY_BINARIES.items()
    }


DEPENDENCIES = dependency_status()


def allowed_file(filename):
    """Comprueba si la extensión del archivo es permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_pdf(filepath):
    """Valida que un archivo sea un PDF real intentando leerlo con pypdf."""
    try:
        PdfReader(filepath)
        return True
    except Exception:
        return False


def cleanup_folder(folder_path):
    """Limpia todos los archivos de una carpeta temporal.

    Solo actúa si la ruta resuelta queda dentro de UPLOAD_FOLDER, para evitar
    borrar contenido fuera del directorio de subidas (defensa frente a C-01).
    """
    try:
        base = os.path.realpath(UPLOAD_FOLDER)
        target = os.path.realpath(folder_path)
    except (OSError, ValueError):
        return
    if target == base or not target.startswith(base + os.sep):
        return
    if os.path.exists(target):
        shutil.rmtree(target)


def _valid_download_token(token):
    """Valida que el token sea un UUID canónico (defensa frente a C-01)."""
    if not isinstance(token, str) or not token:
        return False
    try:
        return str(uuid.UUID(token)) == token
    except (ValueError, AttributeError, TypeError):
        return False


def _safe_upload_dir(token):
    """Devuelve la ruta de la carpeta temporal si el token es seguro, o None."""
    if not _valid_download_token(token):
        return None
    base = os.path.realpath(UPLOAD_FOLDER)
    target = os.path.realpath(os.path.join(base, token))
    if target == base or not target.startswith(base + os.sep):
        return None
    return target


# ─── Validación de tamaño por archivo ────────────────────────────────

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_file_size(file_storage, template_name, filename_label="El archivo"):
    """
    Valida que un archivo subido no supere MAX_FILE_SIZE.
    Devuelve una respuesta de error (Response) si falla, o None si es válido.
    """
    file_storage.seek(0, 2)  # Mover al final para obtener el tamaño
    file_size = file_storage.tell()
    file_storage.seek(0)  # Restaurar el puntero al inicio

    if file_size > MAX_FILE_SIZE:
        return render_template(
            template_name,
            error=f"{filename_label} supera el límite de 50 MB. Selecciona un archivo más pequeño."
        )
    return None


# ─── Productividad: lotes, historial y plantillas (v1.5) ─────────────

# Límites duros del procesamiento por lotes. El total de subida comparte el
# tope global de 50 MB por petición (MAX_CONTENT_LENGTH), así que un lote no
# puede multiplicar el consumo de CPU/RAM más allá de esos valores.
MAX_BATCH_FILES = 10
MAX_BATCH_PAGES = 200
MAX_BATCH_TOTAL_SIZE = MAX_FILE_SIZE

HISTORY_TTL_DAYS = 30
HISTORY_MAX_ENTRIES = 50
TEMPLATE_TTL_DAYS = 90
TEMPLATE_MAX_ENTRIES = 20

BATCH_OPERATIONS = (
    "rotar",
    "optimizar",
    "proteger",
    "desproteger",
    "marcar_agua",
    "numerar",
)

BATCH_SUFFIXES = {
    "rotar": "rotado",
    "optimizar": "optimizado",
    "proteger": "protegido",
    "desproteger": "desprotegido",
    "marcar_agua": "marcado",
    "numerar": "numerado",
}

BATCH_LIMITS = {
    "files": MAX_BATCH_FILES,
    "pages": MAX_BATCH_PAGES,
    "total_mb": MAX_BATCH_TOTAL_SIZE // (1024 * 1024),
}


# ─── Error 413 (archivo demasiado grande) ────────────────────────────

# Mapeo de referer a plantilla para redirigir al usuario a la página de origen
REFERER_TO_TEMPLATE = {
    "/unir": "unir.html",
    "/dividir": "dividir.html",
    "/comprimir": "comprimir.html",
    "/comprimir-real": "comprimir_real.html",
    "/pdf-a-imagen": "pdf_a_imagen.html",
    "/imagen-a-pdf": "imagen_a_pdf.html",
    "/pdf-a-word": "pdf_a_word.html",
    "/rotar": "rotar.html",
    "/proteger": "proteger.html",
    "/desproteger": "desproteger.html",
    "/ocr": "ocr.html",
    "/ocr-a-pdf": "ocr_a_pdf.html",
    "/limpiar-metadatos": "limpiar_metadatos.html",
    "/marcar-agua": "marcar_agua.html",
    "/numerar": "numerar.html",
    "/recortar-pdf": "recortar_pdf.html",
    "/reordenar-pdf": "reordenar_pdf.html",
    "/pdf-a-excel": "pdf_a_excel.html",
    "/pdf-a-powerpoint": "pdf_a_powerpoint.html",
    "/pdf-a-html": "pdf_a_html.html",
    "/word-a-pdf": "word_a_pdf.html",
    "/excel-a-pdf": "excel_a_pdf.html",
    "/powerpoint-a-pdf": "powerpoint_a_pdf.html",
    "/html-a-pdf": "html_a_pdf.html",
    "/firmar": "firmar.html",
    "/censurar": "censurar.html",
    "/comparar": "comparar.html",
    "/lotes": "lotes.html",
}


def _describe_unexpected_error(exc):
    """Devuelve causa y solución orientativas para errores no controlados."""
    msg = str(exc)
    low = msg.lower()
    exc_type = type(exc).__name__

    if isinstance(exc, PermissionError) or "permission denied" in low:
        return (
            "El sistema no permitió leer o escribir un archivo temporal.",
            "Comprueba que la carpeta de datos de Pedeefe tenga permisos de escritura. "
            "Si usas la app de escritorio, cierra otras instancias y vuelve a intentarlo. "
            "En Windows, revisa que el antivirus no esté bloqueando la carpeta de la app.",
        )
    if isinstance(exc, FileNotFoundError) or "no such file or directory" in low:
        return (
            "Falta un archivo o una herramienta externa necesaria para completar la acción.",
            "Si la herramienta usa PDF a imagen, OCR, compresión real u Office, instala la "
            "dependencia indicada (Poppler, Tesseract, Ghostscript o LibreOffice) y reinicia Pedeefe.",
        )
    if "tesseract" in low:
        return (
            "Tesseract OCR no está disponible o falló al procesar el archivo.",
            "Instala Tesseract y el idioma necesario. En la app de escritorio, instala Tesseract en el "
            "sistema y reinicia Pedeefe.",
        )
    if "poppler" in low or "pdftoppm" in low or "pdfinfo" in low:
        return (
            "Poppler no está disponible o falló al convertir el PDF.",
            "Instala Poppler y reinicia Pedeefe. En Windows, añade la carpeta bin de Poppler al PATH.",
        )
    if "ghostscript" in low or low.strip() == "gs" or "gswin" in low:
        return (
            "Ghostscript no está disponible o falló al comprimir el PDF.",
            "Instala Ghostscript y reinicia Pedeefe.",
        )
    if "libreoffice" in low or "soffice" in low:
        return (
            "LibreOffice no está disponible o falló al convertir el documento.",
            "Instala LibreOffice y reinicia Pedeefe.",
        )
    if isinstance(exc, MemoryError) or "memory" in low:
        return (
            "El archivo agotó la memoria disponible durante el procesamiento.",
            "Prueba con un archivo más pequeño, divide el PDF antes de procesarlo o cierra otras aplicaciones.",
        )
    if isinstance(exc, TimeoutError) or "timed out" in low or "timeout" in low:
        return (
            "La operación tardó demasiado y se detuvo.",
            "Prueba con un archivo más pequeño o con menos páginas. Si es una conversión compleja, inténtalo de nuevo.",
        )
    return (
        f"Se produjo un error inesperado ({exc_type}).",
        "Vuelve a intentarlo. Si se repite, comparte el detalle técnico de abajo para poder diagnosticarlo.",
    )


def _log_unexpected_error(exc):
    """Guarda el traceback en el directorio de uploads para diagnóstico local."""
    detail = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    stamp = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    try:
        req_info = f"{request.method} {request.path}"
    except Exception:
        req_info = "<sin contexto de petición>"
    payload = (
        f"[{stamp}] {req_info}\n"
        f"{detail}\n{'-' * 60}\n"
    )
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        log_path = os.path.join(UPLOAD_FOLDER, "pedeefe-error.log")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(payload)
    except Exception:
        pass
    print(payload, flush=True)
    return detail


@app.errorhandler(413)
def too_large(e):
    """Cuando un archivo supera los 50 MB, devuelve el error en la página de origen."""
    referer = request.headers.get("Referer", "")
    for route, template in REFERER_TO_TEMPLATE.items():
        if route in referer:
            return render_template(
                template,
                error="El archivo supera el límite de 50 MB. Selecciona un archivo más pequeño."
            ), 413
    return render_template("error.html", message="El archivo supera el límite de 50 MB."), 413


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    """Muestra errores no controlados con causa y solución para el usuario."""
    if isinstance(exc, HTTPException):
        return exc

    detail = _log_unexpected_error(exc)
    cause, fix = _describe_unexpected_error(exc)
    message = f"No se pudo completar la acción: {exc}"

    try:
        is_api = request.path.startswith("/api/")
    except Exception:
        is_api = False
    if is_api:
        return jsonify({
            "ok": False,
            "error": message,
            "cause": cause,
            "fix": fix,
            "detail": detail,
        }), 500

    try:
        return render_template(
            "error.html",
            message=message,
            cause=cause,
            fix=fix,
            detail=detail,
        ), 500
    except Exception:
        # Si la plantilla falla, devolvemos HTML simple para no perder el diagnóstico.
        body = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<title>Error - Pedeefe</title></head><body style='font-family:sans-serif;padding:24px;'>"
            f"<h1>Error</h1><p>{message}</p><p><strong>Causa:</strong> {cause}</p>"
            f"<p><strong>Cómo solucionarlo:</strong> {fix}</p>"
            f"<pre style='white-space:pre-wrap'>{detail}</pre></body></html>"
        )
        return body, 500, {"Content-Type": "text/html; charset=utf-8"}


# ─── Página principal ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        tesseract_available=TESSERACT_AVAILABLE,
        dependencies=DEPENDENCIES,
    )


# ─── PWA: manifiesto y service worker (v1.9) ────────────────────────

@app.route("/manifest.webmanifest")
def web_manifest():
    """Sirve el manifiesto con el MIME que exige la especificación PWA."""
    response = app.send_static_file("manifest.json")
    response.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    return response


@app.route("/sw.js")
def service_worker():
    """Sirve el service worker con ámbito '/' y sin caché del propio script."""
    response = app.send_static_file("js/sw.js")
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ─── Unir PDFs ──────────────────────────────────────────────────────

@app.route("/unir", methods=["GET", "POST"])
def unir():
    if request.method == "GET":
        return render_template("unir.html")

    # Recibir archivos
    files = request.files.getlist("files")
    if len(files) < 2:
        return render_template("unir.html", error="Selecciona al menos 2 PDFs para unir.")

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        valid_files = []

        for file in files:
            if file.filename == "":
                continue

            if not allowed_file(file.filename):
                return render_template(
                    "unir.html",
                    error=f"'{file.filename}' no es un PDF válido."
                )

            # Validar tamaño del archivo
            size_error = validate_file_size(file, "unir.html", f"'{file.filename}'")
            if size_error:
                return size_error

            # Guardar archivo temporalmente con nombre único
            ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
            unique_name = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(temp_dir, unique_name)
            file.save(filepath)

            # Validar que sea un PDF real (no solo la extensión)
            if not validate_pdf(filepath):
                return render_template(
                    "unir.html",
                    error=f"'{file.filename}' no se puede leer como PDF."
                )

            valid_files.append(filepath)

        if len(valid_files) < 2:
            return render_template(
                "unir.html",
                error="Se necesitan al menos 2 PDFs válidos para unir."
            )

        # Unir PDFs con pypdf
        writer = PdfWriter()
        for filepath in valid_files:
            reader = PdfReader(filepath)
            for page in reader.pages:
                writer.add_page(page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "unido.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="unido.pdf")

    except Exception as e:
        return render_template("unir.html", error=f"Error al unir: {str(e)}")
    finally:
        cleanup_folder(temp_dir)


# ─── Dividir PDFs ───────────────────────────────────────────────────

@app.route("/dividir", methods=["GET", "POST"])
def dividir():
    if request.method == "GET":
        return render_template("dividir.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("dividir.html", error="Selecciona un PDF para dividir.",
                              mode=request.form.get("mode", "individual"),
                              range_value=request.form.get("range", ""))

    if not allowed_file(file.filename):
        return render_template("dividir.html", error="El archivo seleccionado no es un PDF.",
                              mode=request.form.get("mode", "individual"),
                              range_value=request.form.get("range", ""))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "dividir.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("dividir.html", error="El archivo no se puede leer como PDF.",
                                  mode=request.form.get("mode", "individual"),
                                  range_value=request.form.get("range", ""))

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        # Obtener el modo de división
        mode = request.form.get("mode")

        if mode == "individual":
            # Separar cada página en un PDF individual y comprimir en zip
            zip_path = os.path.join(temp_dir, "paginas.zip")
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for i in range(total_pages):
                    writer = PdfWriter()
                    writer.add_page(reader.pages[i])
                    page_path = os.path.join(temp_dir, f"pagina_{i + 1}.pdf")
                    with open(page_path, "wb") as f:
                        writer.write(f)
                    zip_file.write(page_path, f"pagina_{i + 1}.pdf")

            return send_file(zip_path, as_attachment=True, download_name="paginas.zip")

        elif mode == "rango":
            # Dividir por rango de páginas indicado por el usuario
            range_str = request.form.get("range", "").strip()
            if not range_str:
                return render_template("dividir.html", error="Indica el rango de páginas.",
                                      mode="rango", range_value=range_str)

            # Parsear el rango (ej: "1-3", "5-10")
            try:
                if "-" in range_str:
                    parts = range_str.split("-", 1)
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                else:
                    # Solo un número: extraer esa página
                    start = int(range_str)
                    end = start
            except ValueError:
                return render_template(
                    "dividir.html",
                    error="El rango no es válido. Usa el formato 'inicio-fin' (ej: 1-3).",
                    mode="rango",
                    range_value=range_str
                )

            # Validar el rango
            if start < 1 or end < 1:
                return render_template(
                    "dividir.html",
                    error=f"El rango debe empezar desde 1. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}.",
                    mode="rango",
                    range_value=range_str
                )
            if start > total_pages or end > total_pages:
                return render_template(
                    "dividir.html",
                    error=f"El rango supera el número de páginas. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}.",
                    mode="rango",
                    range_value=range_str
                )
            if start > end:
                return render_template(
                    "dividir.html",
                    error="El inicio del rango no puede ser mayor que el fin.",
                    mode="rango",
                    range_value=range_str
                )

            # Extraer las páginas del rango
            writer = PdfWriter()
            for i in range(start - 1, end):  # Convertir a índice 0-based
                writer.add_page(reader.pages[i])

            output_path = os.path.join(temp_dir, "rango_extraido.pdf")
            with open(output_path, "wb") as f:
                writer.write(f)

            return send_file(output_path, as_attachment=True, download_name="rango_extraido.pdf")

        else:
            return render_template("dividir.html", error="Selecciona un modo de división.",
                                  mode=request.form.get("mode", "individual"),
                                  range_value=request.form.get("range", ""))

    except Exception as e:
        return render_template("dividir.html", error=f"Error al dividir: {str(e)}",
                              mode=request.form.get("mode", "individual"),
                              range_value=request.form.get("range", ""))
    finally:
        cleanup_folder(temp_dir)


# ─── Comprimir PDFs ─────────────────────────────────────────────

def format_size(bytes_size):
    """Formatea un tamaño en bytes a una lectura amigable (KB, MB)."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"


@app.route("/comprimir", methods=["GET", "POST"])
def comprimir():
    if request.method == "GET":
        return render_template("comprimir.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("comprimir.html", error="Selecciona un PDF para comprimir.")

    if not allowed_file(file.filename):
        return render_template("comprimir.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "comprimir.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()
    keep_temp = False

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("comprimir.html", error="El archivo no se puede leer como PDF.")

        original_size = os.path.getsize(filepath)

        # Comprimir con pikepdf: optimiza imágenes y estructura interna
        output_path = os.path.join(temp_dir, "comprimido.pdf")
        with pikepdf.open(filepath) as pdf:
            pdf.save(output_path)

        compressed_size = os.path.getsize(output_path)

        # Calcular porcentaje de reducción
        if original_size > 0:
            reduction = ((original_size - compressed_size) / original_size) * 100
        else:
            reduction = 0

        # Mostrar resultado con tamaños y enlace de descarga
        keep_temp = True
        return render_template(
            "comprimir.html",
            success=True,
            original_size=format_size(original_size),
            compressed_size=format_size(compressed_size),
            reduction=round(reduction, 1),
            download_token=os.path.basename(temp_dir)  # UUID de la carpeta temporal
        )

    except Exception as e:
        return render_template("comprimir.html", error=f"Error al comprimir: {str(e)}")
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_comprimido/<token>")
def descargar_comprimido(token):
    """Descarga el PDF comprimido y limpia la carpeta temporal."""
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    output_path = os.path.join(temp_dir, "comprimido.pdf")

    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    try:
        return send_file(output_path, as_attachment=True, download_name="comprimido.pdf")
    finally:
        cleanup_folder(temp_dir)


# ─── Comprimir PDF real (Ghostscript) ────────────────────────────

@app.route("/comprimir-real", methods=["GET", "POST"])
def comprimir_real():
    if request.method == "GET":
        return render_template("comprimir_real.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("comprimir_real.html", error="Selecciona un PDF para comprimir.")

    if not allowed_file(file.filename):
        return render_template("comprimir_real.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "comprimir_real.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()
    keep_temp = False

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("comprimir_real.html", error="El archivo no se puede leer como PDF.")

        original_size = os.path.getsize(filepath)

        # Comprimir con Ghostscript (pdfwrite, preset ebook)
        gs_bin = shutil.which("gs")
        if not gs_bin:
            return render_template(
                "comprimir_real.html",
                error=f"No se encontró Ghostscript en el sistema. {DEPENDENCIES['ghostscript']['hint']}"
            )

        output_path = os.path.join(temp_dir, "comprimido.pdf")
        try:
            subprocess.run(
                [
                    gs_bin,
                    "-sDEVICE=pdfwrite",
                    "-dCompatibilityLevel=1.4",
                    "-dPDFSETTINGS=/ebook",
                    "-dNOPAUSE",
                    "-dQUIET",
                    "-dBATCH",
                    f"-sOutputFile={output_path}",
                    filepath,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            err_msg = (e.stderr or b"").decode("utf-8", "replace").strip()
            if not err_msg:
                err_msg = "Ghostscript no pudo procesar el PDF."
            return render_template("comprimir_real.html", error=f"Error al comprimir: {err_msg}")
        except subprocess.TimeoutExpired:
            return render_template("comprimir_real.html", error="Error al comprimir: el proceso tardó demasiado.")
        except FileNotFoundError:
            return render_template(
                "comprimir_real.html",
                error=f"No se encontró Ghostscript en el sistema. {DEPENDENCIES['ghostscript']['hint']}"
            )

        if not os.path.exists(output_path):
            return render_template("comprimir_real.html", error="Error al comprimir: no se generó el archivo de salida.")

        compressed_size = os.path.getsize(output_path)

        # Calcular porcentaje de reducción
        if original_size > 0:
            reduction = ((original_size - compressed_size) / original_size) * 100
        else:
            reduction = 0

        already_optimized = compressed_size >= original_size

        # Mostrar resultado con tamaños y enlace de descarga
        keep_temp = True
        return render_template(
            "comprimir_real.html",
            success=True,
            original_size=format_size(original_size),
            compressed_size=format_size(compressed_size),
            reduction=round(reduction, 1),
            download_token=os.path.basename(temp_dir),
            already_optimized=already_optimized,
        )

    except Exception as e:
        return render_template("comprimir_real.html", error=f"Error al comprimir: {str(e)}")
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


# ─── PDF a Imágenes ──────────────────────────────────────────────


@app.route("/pdf-a-imagen", methods=["GET", "POST"])
def pdf_a_imagen():
    if request.method == "GET":
        return render_template("pdf_a_imagen.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_imagen.html", error="Selecciona un PDF para convertir.",
                              format=request.form.get("format", "jpg"))

    if not allowed_file(file.filename):
        return render_template("pdf_a_imagen.html", error="El archivo seleccionado no es un PDF.",
                              format=request.form.get("format", "jpg"))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "pdf_a_imagen.html")
    if size_error:
        return size_error

    # Obtener formato de imagen elegido
    format_choice = request.form.get("format", "jpg")
    if format_choice not in ("jpg", "png"):
        format_choice = "jpg"

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("pdf_a_imagen.html", error="El archivo no se puede leer como PDF.",
                                  format=request.form.get("format", "jpg"))

        # Convertir cada página a imagen con pdf2image
        images = convert_from_path(filepath, dpi=200)
        total_pages = len(images)

        # Guardar las imágenes
        image_files = []
        for i, image in enumerate(images):
            image_path = os.path.join(temp_dir, f"pagina_{i + 1}.{format_choice}")
            image.save(image_path, "JPEG" if format_choice == "jpg" else "PNG")
            image_files.append((f"pagina_{i + 1}.{format_choice}", image_path))

        if total_pages == 1:
            # Una sola página: descargar la imagen directamente
            image_name = f"pagina_1.{format_choice}"
            return send_file(
                image_files[0][1],
                as_attachment=True,
                download_name=image_name
            )
        else:
            # Varias páginas: comprimir en zip
            zip_path = os.path.join(temp_dir, "imagenes.zip")
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for name, path in image_files:
                    zip_file.write(path, name)

            return send_file(zip_path, as_attachment=True, download_name="imagenes.zip")

    except Exception as e:
        cleanup_folder(temp_dir)
        error_msg = str(e)
        # Mensaje amigable si Poppler no está instalado
        if "poppler" in error_msg.lower() or "not found" in error_msg.lower():
            error_msg = f"No se encontró Poppler en el sistema. {DEPENDENCIES['poppler']['hint']}"
        return render_template("pdf_a_imagen.html", error=f"Error al convertir: {error_msg}",
                              format=request.form.get("format", "jpg"))
    finally:
        cleanup_folder(temp_dir)


# ─── Imágenes a PDF ──────────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}


def allowed_image_file(filename):
    """Comprueba si la extensión del archivo es una imagen permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def validate_image(filepath):
    """Valida que un archivo sea una imagen real intentando abrirla con Pillow."""
    try:
        with Image.open(filepath) as img:
            img.load()
        return True
    except Exception:
        return False


@app.route("/imagen-a-pdf", methods=["GET", "POST"])
def imagen_a_pdf():
    if request.method == "GET":
        return render_template("imagen_a_pdf.html")

    # Recibir archivos
    files = request.files.getlist("files")
    if len(files) < 1:
        return render_template("imagen_a_pdf.html", error="Selecciona al menos una imagen.")

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        valid_files = []

        for file in files:
            if file.filename == "":
                continue

            if not allowed_image_file(file.filename):
                return render_template(
                    "imagen_a_pdf.html",
                    error=f"'{file.filename}' no es una imagen válida (JPG, PNG, GIF, BMP, TIFF, WEBP)."
                )

            # Validar tamaño del archivo
            size_error = validate_file_size(file, "imagen_a_pdf.html", f"'{file.filename}'")
            if size_error:
                return size_error

            # Guardar archivo temporalmente con nombre único
            ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
            unique_name = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(temp_dir, unique_name)
            file.save(filepath)

            # Validar que sea una imagen real
            if not validate_image(filepath):
                return render_template(
                    "imagen_a_pdf.html",
                    error=f"'{file.filename}' no se puede leer como imagen."
                )

            valid_files.append(filepath)

        if len(valid_files) < 1:
            return render_template(
                "imagen_a_pdf.html",
                error="Se necesita al menos una imagen válida."
            )

        # Convertir imágenes a PDF con Pillow
        # Cada página usa el tamaño real de su imagen (verificado en V9)
        pdf_images = []
        for filepath in valid_files:
            img = Image.open(filepath)
            # Convertir a RGB si es necesario (PDF no soporta RGBA ni modo P directamente)
            if img.mode in ("RGBA", "P", "LA"):
                # Fondo blanco para imágenes con transparencia
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])  # Usar canal alpha como máscara
                    img = background
                else:
                    img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            pdf_images.append(img)

        # Guardar resultado como PDF
        output_path = os.path.join(temp_dir, "imagenes.pdf")
        if len(pdf_images) == 1:
            pdf_images[0].save(output_path, "PDF")
        else:
            # Primera imagen como página principal, el resto como páginas adicionales
            pdf_images[0].save(
                output_path, "PDF", save_all=True, append_images=pdf_images[1:]
            )

        return send_file(output_path, as_attachment=True, download_name="imagenes.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("imagen_a_pdf.html", error=f"Error al convertir: {str(e)}")
    finally:
        cleanup_folder(temp_dir)


# ─── PDF a Word ──────────────────────────────────────────────────────

@app.route("/pdf-a-word", methods=["GET", "POST"])
def pdf_a_word():
    if request.method == "GET":
        return render_template("pdf_a_word.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_word.html", error="Selecciona un PDF para convertir.")

    if not allowed_file(file.filename):
        return render_template("pdf_a_word.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "pdf_a_word.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()
    keep_temp = False

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("pdf_a_word.html", error="El archivo no se puede leer como PDF.")

        # Detectar si el PDF parece ser escaneado (sin texto extraíble)
        reader = PdfReader(filepath)
        has_text = False
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                has_text = True
                break

        # Convertir con pdf2docx
        output_path = os.path.join(temp_dir, "convertido.docx")
        cv = Converter(filepath)
        cv.convert(output_path, start=0, end=None)
        cv.close()

        # Si el archivo resultante es muy pequeño, probablemente el PDF era escaneado
        output_size = os.path.getsize(output_path)
        is_likely_scanned = output_size < 1000  # Un .docx vacío pesa ~3KB, así que <1KB es sospechoso

        keep_temp = True
        return render_template(
            "pdf_a_word.html",
            success=True,
            download_token=os.path.basename(temp_dir),
            warning_scanned=(not has_text) or is_likely_scanned
        )

    except Exception as e:
        return render_template("pdf_a_word.html", error=f"Error al convertir: {str(e)}")
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_word/<token>")
def descargar_word(token):
    """Descarga el archivo .docx convertido y limpia la carpeta temporal."""
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    output_path = os.path.join(temp_dir, "convertido.docx")

    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    try:
        return send_file(output_path, as_attachment=True, download_name="convertido.docx")
    finally:
        cleanup_folder(temp_dir)


# ─── Rotar PDF ──────────────────────────────────────────────────────

@app.route("/rotar", methods=["GET", "POST"])
def rotar():
    if request.method == "GET":
        return render_template("rotar.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("rotar.html", error="Selecciona un PDF para rotar.",
                              angle=request.form.get("angle", "90"))

    if not allowed_file(file.filename):
        return render_template("rotar.html", error="El archivo seleccionado no es un PDF.",
                              angle=request.form.get("angle", "90"))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "rotar.html")
    if size_error:
        return size_error

    # Obtener el ángulo de rotación
    angle = request.form.get("angle", "90")
    if angle not in ("90", "180", "270"):
        angle = "90"
    angle = int(angle)

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("rotar.html", error="El archivo no se puede leer como PDF.",
                                  angle=request.form.get("angle", "90"))

        # Rotar todas las páginas con pypdf
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(angle)
            writer.add_page(page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "rotado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="rotado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("rotar.html", error=f"Error al rotar: {str(e)}",
                              angle=request.form.get("angle", "90"))
    finally:
        cleanup_folder(temp_dir)


# ─── Proteger PDF con contraseña ──────────────────────────────────────

@app.route("/proteger", methods=["GET", "POST"])
def proteger():
    if request.method == "GET":
        return render_template("proteger.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("proteger.html", error="Selecciona un PDF para proteger.")

    if not allowed_file(file.filename):
        return render_template("proteger.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "proteger.html")
    if size_error:
        return size_error

    # Obtener la contraseña y su confirmación
    password = request.form.get("password", "").strip()
    password_confirm = request.form.get("password_confirm", "").strip()
    if not password:
        return render_template("proteger.html", error="Introduce una contraseña para proteger el PDF.")
    if password != password_confirm:
        return render_template("proteger.html", error="Las contraseñas no coinciden. Vuelve a introducirlas.")

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("proteger.html", error="El archivo no se puede leer como PDF.")

        # Encriptar el PDF con la contraseña usando pypdf
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # La contraseña se usa tanto para abrir como para permisos (owner password igual)
        writer.encrypt(password)

        output_path = os.path.join(temp_dir, "protegido.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="protegido.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("proteger.html", error=f"Error al proteger: {str(e)}")
    finally:
        cleanup_folder(temp_dir)


# ─── Desproteger PDF ──────────────────────────────────────────────────

@app.route("/desproteger", methods=["GET", "POST"])
def desproteger():
    if request.method == "GET":
        return render_template("desproteger.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("desproteger.html", error="Selecciona un PDF para desproteger.")

    if not allowed_file(file.filename):
        return render_template("desproteger.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "desproteger.html")
    if size_error:
        return size_error

    # Obtener la contraseña
    password = request.form.get("password", "").strip()
    if not password:
        return render_template("desproteger.html", error="Introduce la contraseña del PDF.")

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("desproteger.html", error="El archivo no se puede leer como PDF.")

        # Intentar leer el PDF con la contraseña
        reader = PdfReader(filepath)

        # Si el PDF está encriptado, verificar la contraseña
        if reader.is_encrypted:
            # Intentar desbloquear con la contraseña proporcionada
            result = reader.decrypt(password)
            # PyPdf devuelve 0 si la contraseña no es válida
            if result == 0:
                return render_template(
                    "desproteger.html",
                    error="La contraseña es incorrecta. Verifica e intenta de nuevo."
                )
        else:
            return render_template(
                "desproteger.html",
                error="Este PDF no tiene contraseña."
            )

        # Crear un nuevo PDF sin encriptación
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        output_path = os.path.join(temp_dir, "desprotegido.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="desprotegido.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("desproteger.html", error=f"Error al desproteger: {str(e)}")
    finally:
        cleanup_folder(temp_dir)


# ─── OCR de PDFs escaneados ──────────────────────────────────────────

# Códigos aceptados por el selector. Se pasan tal cual a Tesseract, por lo que
# la lista es también un allowlist: nunca se envía un idioma arbitrario al motor.
# Cada idioma requiere su traineddata instalado en el sistema.
OCR_LANGUAGES = {
    "spa": "Español",
    "eng": "English",
    "fra": "Français",
    "deu": "Deutsch",
    "ita": "Italiano",
    "por": "Português",
}


def _ocr_error_message(exc, lang):
    """Convierte errores de Tesseract/Poppler en un mensaje accionable."""
    error_msg = str(exc)
    # Mensaje amigable si falta el traineddata del idioma elegido
    if "traineddata" in error_msg.lower():
        return (
            f"Falta el idioma '{lang}' en Tesseract. Instálalo con: "
            f"sudo apt install tesseract-ocr-{lang}"
        )
    # Mensaje amigable si Tesseract no está instalado
    if "tesseract" in error_msg.lower() or "not found" in error_msg.lower():
        return (
            "No se encontró Tesseract OCR en el sistema. "
            "Instálalo con: sudo apt install tesseract-ocr"
        )
    # Mensaje amigable si Poppler no está instalado
    if "poppler" in error_msg.lower():
        return f"No se encontró Poppler en el sistema. {DEPENDENCIES['poppler']['hint']}"
    return error_msg


@app.route("/ocr", methods=["GET", "POST"])
def ocr():
    if request.method == "GET":
        return render_template("ocr.html")

    # Idioma: allowlist estricto para no pasar códigos arbitrarios a Tesseract.
    lang = request.form.get("lang") or "spa"
    if lang not in OCR_LANGUAGES:
        return render_template("ocr.html", error="Selecciona un idioma de OCR válido.")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("ocr.html", error="Selecciona un PDF para procesar.")

    if not allowed_file(file.filename):
        return render_template("ocr.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "ocr.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("ocr.html", error="El archivo no se puede leer como PDF.")

        # Convertir cada página del PDF a imagen con pdf2image (necesita Poppler)
        images = convert_from_path(filepath, dpi=200)

        # Extraer texto de cada página con pytesseract (necesita Tesseract OCR)
        all_text = []
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image, lang=lang)
            all_text.append(f"--- Página {i + 1} ---\n{text}")

        # Unir todo el texto en un solo string
        full_text = "\n\n".join(all_text)

        # Guardar en un archivo .txt
        output_path = os.path.join(temp_dir, "texto_extraido.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        return send_file(output_path, as_attachment=True, download_name="texto_extraido.txt")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "ocr.html", error=f"Error al procesar: {_ocr_error_message(e, lang)}"
        )
    finally:
        cleanup_folder(temp_dir)


# ─── OCR a PDF buscable (capa de texto invisible) ─────────────────────

def _ocr_text_layer(pdf_bytes):
    """Quita la imagen de un PDF de Tesseract y deja solo su texto invisible.

    Tesseract genera una página con la imagen a 200 ppp y el texto reconocido
    en modo de renderizado 3 (invisible). Al eliminar los operadores `Do` y los
    XObject de imagen, queda una capa de texto que se puede superponer sobre el
    PDF original sin alterar su apariencia.
    """
    with pikepdf.open(BytesIO(pdf_bytes)) as layer_pdf:
        if not layer_pdf.pages:
            raise ValueError("Tesseract no devolvió ninguna página.")
        page = layer_pdf.pages[0]
        if "/Contents" in page.obj:
            operators = pikepdf.parse_content_stream(page.obj.Contents)
            page.obj.Contents = layer_pdf.make_stream(
                pikepdf.unparse_content_stream(
                    [op for op in operators if op.operator != "Do"]
                )
            )
        resources = page.obj.get("/Resources")
        if resources is not None and "/XObject" in resources:
            del resources["/XObject"]
        result = BytesIO()
        layer_pdf.save(result)
    result.seek(0)
    return result


@app.route("/ocr-a-pdf", methods=["GET", "POST"])
def ocr_a_pdf():
    if request.method == "GET":
        return render_template("ocr_a_pdf.html")

    # Mismo allowlist que /ocr: nunca se pasa un idioma arbitrario a Tesseract.
    lang = request.form.get("lang") or "spa"
    if lang not in OCR_LANGUAGES:
        return render_template("ocr_a_pdf.html", error="Selecciona un idioma de OCR válido.")

    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("ocr_a_pdf.html", error="Selecciona un PDF para procesar.")

    if not allowed_file(file.filename):
        return render_template("ocr_a_pdf.html", error="El archivo seleccionado no es un PDF.")

    size_error = validate_file_size(file, "ocr_a_pdf.html")
    if size_error:
        return size_error

    temp_dir = _create_temp_dir()
    keep_temp = False

    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}.{ext}")
        file.save(filepath)

        if not validate_pdf(filepath):
            return render_template(
                "ocr_a_pdf.html", error="El archivo no se puede leer como PDF."
            )

        # Una imagen por página, a 200 ppp como en /ocr.
        images = convert_from_path(filepath, dpi=200)
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for page, image in zip(reader.pages, images):
            layer_bytes = pytesseract.image_to_pdf_or_hocr(
                image, lang=lang, extension="pdf"
            )
            layer = PdfReader(_ocr_text_layer(layer_bytes))
            # pypdf 7 exige añadir la página antes de superponer (ver /marcar-agua).
            writer.add_page(page)
            writer.pages[-1].merge_page(layer.pages[0])

        output_path = os.path.join(temp_dir, "buscable.pdf")
        with open(output_path, "wb") as handle:
            writer.write(handle)

        keep_temp = True
        return render_template(
            "ocr_a_pdf.html",
            success=True,
            pages=len(images),
            download_token=os.path.basename(temp_dir),
        )

    except Exception as e:
        return render_template(
            "ocr_a_pdf.html",
            error=f"Error al procesar: {_ocr_error_message(e, lang)}",
        )
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_ocr_pdf/<token>")
def descargar_ocr_pdf(token):
    """Descarga el PDF con capa de texto y limpia su carpeta temporal."""
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    output_path = os.path.join(temp_dir, "buscable.pdf")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    try:
        return send_file(output_path, as_attachment=True, download_name="buscable.pdf")
    finally:
        cleanup_folder(temp_dir)


# ─── Limpieza de metadatos (sanitize) ─────────────────────────────────

METADATA_REPLACEMENT_FIELDS = {
    "title": "/Title",
    "author": "/Author",
    "subject": "/Subject",
    "keywords": "/Keywords",
}


@app.route("/limpiar-metadatos", methods=["GET", "POST"])
def limpiar_metadatos():
    if request.method == "GET":
        return render_template("limpiar_metadatos.html")

    def fail(message):
        return render_template("limpiar_metadatos.html", error=message)

    file = request.files.get("file")
    if not file or file.filename == "":
        return fail("Selecciona un PDF para limpiar.")
    if not allowed_file(file.filename):
        return fail("El archivo seleccionado no es un PDF.")

    size_error = validate_file_size(file, "limpiar_metadatos.html")
    if size_error:
        return size_error

    options = {
        "info": request.form.get("clear_info") == "on",
        "xmp": request.form.get("clear_xmp") == "on",
        "attachments": request.form.get("clear_attachments") == "on",
        "js": request.form.get("clear_js") == "on",
        "page_meta": request.form.get("clear_page_meta") == "on",
    }
    replacements = {}
    for field, pdf_key in METADATA_REPLACEMENT_FIELDS.items():
        value = request.form.get(field, "").strip()[:200]
        if value:
            replacements[pdf_key] = value

    temp_dir = _create_temp_dir()
    keep_temp = False

    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}.{ext}")
        file.save(filepath)

        if not validate_pdf(filepath):
            return fail("El archivo no se puede leer como PDF.")

        removed = []
        detected = []
        with pikepdf.open(filepath) as pdf:
            detected = [str(key) for key in pdf.docinfo.keys()]

            if options["info"]:
                for key in list(pdf.docinfo.keys()):
                    del pdf.docinfo[key]
                if detected:
                    removed.append(f"{len(detected)} campos de información")

            # Los valores nuevos se escriben después de borrar los antiguos.
            for key, value in replacements.items():
                pdf.docinfo[key] = value

            if options["xmp"] and "/Metadata" in pdf.Root:
                del pdf.Root["/Metadata"]
                removed.append("metadatos XMP")

            if options["attachments"]:
                names = pdf.Root.get("/Names")
                if names is not None and "/EmbeddedFiles" in names:
                    del names["/EmbeddedFiles"]
                    removed.append("archivos adjuntos")
                for obj in [pdf.Root] + list(pdf.pages):
                    page_obj = getattr(obj, "obj", obj)
                    if "/AF" in page_obj:
                        del page_obj["/AF"]

            if options["js"]:
                names = pdf.Root.get("/Names")
                if names is not None and "/JavaScript" in names:
                    del names["/JavaScript"]
                    removed.append("scripts JavaScript")
                action = pdf.Root.get("/OpenAction")
                if action is not None and (
                    "/JS" in action or action.get("/S") == pikepdf.Name.JavaScript
                ):
                    del pdf.Root["/OpenAction"]
                    if "scripts JavaScript" not in removed:
                        removed.append("scripts JavaScript")
                for page in pdf.pages:
                    if "/AA" in page.obj:
                        del page.obj["/AA"]

            if options["page_meta"]:
                page_count = 0
                for page in pdf.pages:
                    for key in ("/Metadata", "/PieceInfo", "/LastModified"):
                        if key in page.obj:
                            del page.obj[key]
                            page_count += 1
                if page_count:
                    removed.append(f"{page_count} metadatos de página")

            names = pdf.Root.get("/Names")
            if names is not None and len(names) == 0:
                del pdf.Root["/Names"]

            output_path = os.path.join(temp_dir, "sin_metadatos.pdf")
            pdf.save(output_path)

        keep_temp = True
        return render_template(
            "limpiar_metadatos.html",
            success=True,
            removed=removed,
            detected=detected,
            download_token=os.path.basename(temp_dir),
        )

    except pikepdf.PasswordError:
        return fail("El PDF está cifrado. Desprotégelo antes de limpiar sus metadatos.")
    except Exception as e:
        return fail(f"Error al limpiar metadatos: {str(e)}")
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_limpiar_metadatos/<token>")
def descargar_limpiar_metadatos(token):
    """Descarga el PDF saneado y limpia su carpeta temporal."""
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    output_path = os.path.join(temp_dir, "sin_metadatos.pdf")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404

    try:
        return send_file(
            output_path, as_attachment=True, download_name="sin_metadatos.pdf"
        )
    finally:
        cleanup_folder(temp_dir)


# ─── Marca de agua en PDF ─────────────────────────────────────────────

def create_watermark_pdf(text, page_width, page_height, angle=45, font_size=60, opacity=0.3):
    """
    Crea un PDF de una página con el texto de marca de agua semitransparente en diagonal.
    Usa reportlab para generar el PDF en memoria.
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Color gris semitransparente
    watermark_color = Color(0.5, 0.5, 0.5, alpha=opacity)

    c.setFillColor(watermark_color)
    c.setFont("Helvetica", font_size)

    # Rotar y centrar el texto en la página
    c.saveState()
    c.translate(page_width / 2, page_height / 2)
    c.rotate(angle)
    c.drawCentredString(0, 0, text)
    c.restoreState()

    c.save()
    packet.seek(0)
    return packet


@app.route("/marcar-agua", methods=["GET", "POST"])
def marcar_agua():
    if request.method == "GET":
        return render_template("marcar_agua.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("marcar_agua.html", error="Selecciona un PDF para marcar.",
                              watermark_text=request.form.get("watermark_text", ""))

    if not allowed_file(file.filename):
        return render_template("marcar_agua.html", error="El archivo seleccionado no es un PDF.",
                              watermark_text=request.form.get("watermark_text", ""))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "marcar_agua.html")
    if size_error:
        return size_error

    # Obtener el texto de la marca de agua
    watermark_text = request.form.get("watermark_text", "").strip()
    if not watermark_text:
        return render_template("marcar_agua.html", error="Introduce el texto para la marca de agua.",
                              watermark_text=request.form.get("watermark_text", ""))

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("marcar_agua.html", error="El archivo no se puede leer como PDF.",
                                  watermark_text=request.form.get("watermark_text", ""))

        # Leer el PDF original
        reader = PdfReader(filepath)
        writer = PdfWriter()

        # Superponer la marca de agua en cada página, adaptando el tamaño
        # de la marca al tamaño real de la página (mediabox/cropbox).
        for page in reader.pages:
            page_box = page.mediabox
            page_width = float(page_box.width)
            page_height = float(page_box.height)
            if page_width <= 0 or page_height <= 0:
                page_box = page.cropbox
                page_width = float(page_box.width)
                page_height = float(page_box.height)

            watermark_packet = create_watermark_pdf(
                watermark_text, page_width, page_height
            )
            watermark_page = PdfReader(watermark_packet).pages[0]
            # pypdf 7 exige que la página esté attachada al writer antes de
            # superponer; add_page primero funciona también en versiones 4-6.
            writer.add_page(page)
            writer.pages[-1].merge_page(watermark_page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "marcado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="marcado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("marcar_agua.html", error=f"Error al añadir marca de agua: {str(e)}",
                              watermark_text=request.form.get("watermark_text", ""))
    finally:
        cleanup_folder(temp_dir)


# ─── Numerar páginas de PDF ───────────────────────────────────────────

def create_page_number_pdf(page_width, page_height, number, position="bottom_center", font_size=12):
    """
    Crea un PDF de una página con el número de página en la posición elegida.
    Usa reportlab para generar el PDF en memoria.
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.setFont("Helvetica", font_size)
    c.setFillColor(colors.black)  # Negro

    text = str(number)

    # Posicionar el número según la opción elegida
    if position == "bottom_center":
        c.drawCentredString(page_width / 2, 30, text)
    elif position == "bottom_right":
        c.drawString(page_width - 50, 30, text)
    elif position == "bottom_left":
        c.drawString(50, 30, text)
    elif position == "top_center":
        c.drawCentredString(page_width / 2, page_height - 30, text)
    elif position == "top_right":
        c.drawString(page_width - 50, page_height - 30, text)
    elif position == "top_left":
        c.drawString(50, page_height - 30, text)

    c.save()
    packet.seek(0)
    return packet


@app.route("/numerar", methods=["GET", "POST"])
def numerar():
    if request.method == "GET":
        return render_template("numerar.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("numerar.html", error="Selecciona un PDF para numerar.",
                              position=request.form.get("position", "bottom_center"),
                              start_num=request.form.get("start_num", "1"))

    if not allowed_file(file.filename):
        return render_template("numerar.html", error="El archivo seleccionado no es un PDF.",
                              position=request.form.get("position", "bottom_center"),
                              start_num=request.form.get("start_num", "1"))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "numerar.html")
    if size_error:
        return size_error

    # Obtener la posición y el número inicial
    position = request.form.get("position", "bottom_center")
    if position not in ("bottom_center", "bottom_right", "bottom_left", "top_center", "top_right", "top_left"):
        position = "bottom_center"

    start_num_str = request.form.get("start_num", "1").strip()
    try:
        start_num = int(start_num_str)
        if start_num < 1:
            start_num = 1
    except ValueError:
        start_num = 1

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("numerar.html", error="El archivo no se puede leer como PDF.",
                                  position=request.form.get("position", "bottom_center"),
                                  start_num=request.form.get("start_num", "1"))

        # Leer el PDF original
        reader = PdfReader(filepath)
        writer = PdfWriter()

        # Añadir número a cada página
        for i, page in enumerate(reader.pages):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # Crear el PDF del número de página
            num_pdf = create_page_number_pdf(page_width, page_height, start_num + i, position)
            num_reader = PdfReader(num_pdf)
            num_page = num_reader.pages[0]

            # Superponer el número sobre la página attachada al writer
            # (obligatorio en pypdf 7, compatible con versiones 4-6).
            writer.add_page(page)
            writer.pages[-1].merge_page(num_page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "numerado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="numerado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("numerar.html", error=f"Error al numerar: {str(e)}",
                              position=request.form.get("position", "bottom_center"),
                              start_num=request.form.get("start_num", "1"))
    finally:
        cleanup_folder(temp_dir)


# ─── Helper: parsear lista de páginas (rangos y comas) ───────────────
def _parse_page_spec(spec, total_pages):
    """Parsea una especificación de páginas (ej. "1-3,5,7-9").

    Devuelve (lista_de_indices_0based, None) si es válida, o (None, mensaje_error)
    si no lo es. Permite duplicados y rangos inclusivos.
    """
    spec = (spec or "").strip()
    if not spec:
        return None, "Indica el rango de páginas."
    result = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            return None, "La lista de páginas no es válida. Usa el formato '1-3,5,7-9'."
        if "-" in part:
            pieces = part.split("-", 1)
            a, b = pieces[0].strip(), pieces[1].strip()
            if not a.isdigit() or not b.isdigit():
                return None, "La lista de páginas no es válida. Usa el formato '1-3,5,7-9'."
            start, end = int(a), int(b)
            if start < 1 or end < 1:
                return None, f"El rango debe empezar desde 1. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}."
            if start > end:
                return None, "El inicio del rango no puede ser mayor que el fin."
            if start > total_pages or end > total_pages:
                return None, f"El rango supera el número de páginas. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}."
            result.extend(range(start - 1, end))
        else:
            if not part.isdigit():
                return None, "La lista de páginas no es válida. Usa el formato '1-3,5,7-9'."
            n = int(part)
            if n < 1:
                return None, f"El rango debe empezar desde 1. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}."
            if n > total_pages:
                return None, f"El rango supera el número de páginas. El PDF tiene {total_pages} {'página' if total_pages == 1 else 'páginas'}."
            result.append(n - 1)
    if not result:
        return None, "Indica el rango de páginas."
    return result, None


# ─── Recortar PDF (conservar páginas seleccionadas) ──────────────────

@app.route("/recortar-pdf", methods=["GET", "POST"])
def recortar_pdf():
    if request.method == "GET":
        return render_template("recortar_pdf.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("recortar_pdf.html", error="Selecciona un PDF para recortar.",
                              range_value=request.form.get("range", ""))

    if not allowed_file(file.filename):
        return render_template("recortar_pdf.html", error="El archivo seleccionado no es un PDF.",
                              range_value=request.form.get("range", ""))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "recortar_pdf.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("recortar_pdf.html", error="El archivo no se puede leer como PDF.",
                                  range_value=request.form.get("range", ""))

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        # Obtener el rango de páginas a conservar (acepta varios nombres de campo)
        range_raw = (
            request.form.get("range")
            or request.form.get("pages")
            or request.form.get("rango")
            or request.form.get("page_range")
            or ""
        ).strip()

        indices, err = _parse_page_spec(range_raw, total_pages)
        if err:
            return render_template("recortar_pdf.html", error=err, range_value=range_raw)

        # Generar el PDF con las páginas seleccionadas, en el orden indicado
        writer = PdfWriter()
        for idx in indices:
            writer.add_page(reader.pages[idx])

        output_path = os.path.join(temp_dir, "recortado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="recortado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("recortar_pdf.html", error=f"Error al recortar: {str(e)}",
                              range_value=request.form.get("range", ""))
    finally:
        cleanup_folder(temp_dir)


# ─── Reordenar páginas de PDF ────────────────────────────────────────

@app.route("/reordenar-pdf", methods=["GET", "POST"])
def reordenar_pdf():
    if request.method == "GET":
        return render_template("reordenar_pdf.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("reordenar_pdf.html", error="Selecciona un PDF para reordenar.",
                              order_value=request.form.get("order", ""))

    if not allowed_file(file.filename):
        return render_template("reordenar_pdf.html", error="El archivo seleccionado no es un PDF.",
                              order_value=request.form.get("order", ""))

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "reordenar_pdf.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = _create_temp_dir()

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("reordenar_pdf.html", error="El archivo no se puede leer como PDF.",
                                  order_value=request.form.get("order", ""))

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        # Obtener el nuevo orden (acepta varios nombres de campo)
        order_raw = (
            request.form.get("order")
            or request.form.get("pages")
            or request.form.get("orden")
            or request.form.get("page_order")
            or request.form.get("range")
            or ""
        ).strip()

        indices, err = _parse_page_spec(order_raw, total_pages)
        if err:
            return render_template("reordenar_pdf.html", error=err, order_value=order_raw)

        # Generar el PDF con las páginas en el orden indicado (duplicados permitidos)
        writer = PdfWriter()
        for idx in indices:
            writer.add_page(reader.pages[idx])

        output_path = os.path.join(temp_dir, "reordenado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="reordenado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("reordenar_pdf.html", error=f"Error al reordenar: {str(e)}",
                              order_value=request.form.get("order", ""))
    finally:
        cleanup_folder(temp_dir)


# ─── Fase 4 · Conversión de formatos ─────────────────────────────────

class ConversionError(Exception):
    """Error de conversión con mensaje legible para la persona usuaria."""


def _friendly_error(action, exc):
    """Devuelve un mensaje accionable; nunca expone str(e) ni tracebacks."""
    if isinstance(exc, ConversionError):
        return str(exc)
    text = str(exc).lower()
    if "poppler" in text or "pdftoppm" in text:
        return f"No se pudo {action}: falta Poppler. Instálalo con: sudo apt install poppler-utils."
    if "weasyprint" in text:
        return f"No se pudo {action}: falta WeasyPrint. Instala las dependencias del proyecto."
    if "pdfplumber" in text:
        return f"No se pudo {action}: falta pdfplumber. Instala las dependencias del proyecto."
    return (
        f"No se pudo {action}. Comprueba que el archivo no esté dañado "
        "y que el formato sea el esperado."
    )


def _office_to_pdf_libreoffice(input_path, output_path):
    """Intenta convertir con LibreOffice headless. Devuelve True si funciona."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False
    out_dir = os.path.dirname(output_path)
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, input_path],
            check=True, capture_output=True, timeout=120,
            env={**os.environ, "HOME": "/tmp"},
        )
    except Exception:
        return False
    # LibreOffice genera un PDF con el mismo nombre base
    base = os.path.splitext(os.path.basename(input_path))[0]
    produced = os.path.join(out_dir, base + ".pdf")
    if produced != output_path and os.path.exists(produced):
        try:
            os.replace(produced, output_path)
        except OSError:
            return False
    return os.path.exists(output_path)


def _docx_to_html(input_path):
    """Convierte un .docx a HTML básico usando python-docx."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn

    doc = Document(input_path)
    parts = ["<html><body>"]
    for block in doc.element.body.iterchildren():
        if block.tag == qn("w:p"):
            p = Paragraph(block, doc)
            style = p.style.name if p.style is not None else ""
            text = p.text
            if style.startswith("Heading"):
                level = style.replace("Heading", "").strip() or "1"
                if not level.isdigit():
                    level = "1"
                parts.append(f"<h{level}>{_escape_html(text)}</h{level}>")
            else:
                parts.append(f"<p>{_escape_html(text)}</p>")
        elif block.tag == qn("w:tbl"):
            table = Table(block, doc)
            parts.append("<table border='1' cellpadding='4' cellspacing='0'>")
            for row in table.rows:
                parts.append("<tr>")
                for cell in row.cells:
                    parts.append(f"<td>{_escape_html(cell.text)}</td>")
                parts.append("</tr>")
            parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _xlsx_to_html(input_path):
    if openpyxl is None:
        raise ConversionError("Falta openpyxl para leer la hoja de cálculo.")
    wb = openpyxl.load_workbook(input_path, data_only=True)
    parts = ["<html><body>"]
    for ws in wb.worksheets:
        parts.append(f"<h2>{_escape_html(ws.title)}</h2>")
        parts.append("<table border='1' cellpadding='4' cellspacing='0'>")
        for row in ws.iter_rows():
            parts.append("<tr>")
            for cell in row:
                val = "" if cell.value is None else str(cell.value)
                parts.append(f"<td>{_escape_html(val)}</td>")
            parts.append("</tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _pptx_to_html(input_path):
    if Presentation is None:
        raise ConversionError("Falta python-pptx para leer la presentación.")
    prs = Presentation(input_path)
    parts = ["<html><body>"]
    for i, slide in enumerate(prs.slides, 1):
        parts.append(f"<h2>Diapositiva {i}</h2>")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = "".join(r.text for r in para.runs) or para.text
                    if text.strip():
                        parts.append(f"<p>{_escape_html(text)}</p>")
            if getattr(shape, "has_table", False):
                tbl = shape.table
                parts.append("<table border='1' cellpadding='4' cellspacing='0'>")
                for row in tbl.rows:
                    parts.append("<tr>")
                    for cell in row.cells:
                        parts.append(f"<td>{_escape_html(cell.text)}</td>")
                    parts.append("</tr>")
                parts.append("</table>")
        # notes
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text
            if notes.strip():
                parts.append(f"<p><em>Notas: {_escape_html(notes)}</em></p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _escape_html(s):
    import html as _html
    return _html.escape(str(s))


def _html_to_pdf(html_str, output_path):
    if WeasyHTML is None:
        raise ConversionError("Falta WeasyPrint para convertir HTML a PDF.")
    WeasyHTML(string=html_str).write_pdf(output_path)


OOXML_MEMBERS = {
    "docx": "word/document.xml",
    "xlsx": "xl/workbook.xml",
    "pptx": "ppt/presentation.xml",
}


def _valid_ooxml(path, ext):
    """Comprueba que un DOCX/XLSX/PPTX es un ZIP con su parte principal.

    La extensión por sí sola no basta: según la versión de LibreOffice, un
    archivo corrupto puede convertirse igualmente y devolver un PDF vacío.
    """
    member = OOXML_MEMBERS.get(ext.lower())
    if member is None:
        return True
    try:
        with zipfile.ZipFile(path) as archive:
            return member in archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def _office_to_pdf(input_path, output_path, ext):
    """Convierte un archivo Office/HTML a PDF. Usa LibreOffice si está disponible."""
    if _office_to_pdf_libreoffice(input_path, output_path):
        return True
    ext = ext.lower().lstrip(".")
    # Los formatos antiguos (.doc/.xls/.ppt) solo los lee LibreOffice.
    if ext in ("doc", "xls", "ppt"):
        raise ConversionError(
            f"El formato .{ext} necesita LibreOffice. Guarda el archivo como "
            f".{ext}x o instala LibreOffice para convertirlo."
        )
    try:
        if ext in ("docx",):
            html = _docx_to_html(input_path)
        elif ext in ("xlsx", "csv"):
            html = _xlsx_to_html(input_path)
        elif ext in ("pptx",):
            html = _pptx_to_html(input_path)
        elif ext in ("html", "htm"):
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
        else:
            raise ConversionError("Formato de archivo no compatible con la conversión a PDF.")
        _html_to_pdf(html, output_path)
        if not os.path.exists(output_path):
            raise ConversionError("No se generó el PDF. Comprueba el archivo de entrada.")
        return True
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(
            "No se pudo convertir el archivo a PDF. Comprueba que no esté dañado "
            "y que el formato sea el esperado."
        ) from exc


# ─── /pdf-a-excel ───────────────────────────────────────────────────
@app.route("/pdf-a-excel", methods=["GET", "POST"])
def pdf_a_excel():
    if request.method == "GET":
        return render_template("pdf_a_excel.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_excel.html", error="Selecciona un PDF para convertir.")
    if not allowed_file(file.filename):
        return render_template("pdf_a_excel.html", error="El archivo seleccionado no es un PDF.")
    size_error = validate_file_size(file, "pdf_a_excel.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not validate_pdf(filepath):
            raise ConversionError("El archivo no se puede leer como PDF. Puede estar dañado o protegido.")
        output_path = os.path.join(temp_dir, "convertido.xlsx")
        if pdfplumber is None or openpyxl is None:
            raise ConversionError("Faltan pdfplumber u openpyxl para extraer tablas del PDF.")
        wb = openpyxl.Workbook()
        sheet_count = 0
        text_lines = []
        with pdfplumber.open(filepath) as pdf:
            for page_idx, page in enumerate(pdf.pages, 1):
                for t_idx, table in enumerate(page.extract_tables() or [], 1):
                    sheet_count += 1
                    title = f"Pagina{page_idx}_T{t_idx}"[:31]
                    ws = wb.create_sheet(title=title)
                    for row in table:
                        ws.append(["" if c is None else str(c) for c in row])
                # texto de respaldo si la página no tiene tablas detectables
                for line in (page.extract_text() or "").splitlines():
                    if line.strip():
                        text_lines.append(line.strip())
        if sheet_count == 0:
            ws = wb.create_sheet(title="Texto")
            for line in text_lines:
                ws.append([line])
        if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
            del wb["Sheet"]
        wb.save(output_path)
        keep_temp = True
        return render_template(
            "pdf_a_excel.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "pdf_a_excel.html",
            error=_friendly_error("extraer los datos del PDF", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_excel/<token>")
def descargar_excel(token):
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    output_path = os.path.join(temp_dir, "convertido.xlsx")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    try:
        return send_file(output_path, as_attachment=True, download_name="convertido.xlsx")
    finally:
        cleanup_folder(temp_dir)


# ─── /pdf-a-powerpoint ──────────────────────────────────────────────
@app.route("/pdf-a-powerpoint", methods=["GET", "POST"])
def pdf_a_powerpoint():
    if request.method == "GET":
        return render_template("pdf_a_powerpoint.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_powerpoint.html", error="Selecciona un PDF para convertir.")
    if not allowed_file(file.filename):
        return render_template("pdf_a_powerpoint.html", error="El archivo seleccionado no es un PDF.")
    size_error = validate_file_size(file, "pdf_a_powerpoint.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not validate_pdf(filepath):
            raise ConversionError("El archivo no se puede leer como PDF. Puede estar dañado o protegido.")
        output_path = os.path.join(temp_dir, "convertido.pptx")
        if Presentation is None:
            raise ConversionError("Falta python-pptx para crear la presentación.")
        images = convert_from_path(filepath, dpi=150)
        prs = Presentation()
        blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1]
        for img in images:
            img_path = os.path.join(temp_dir, f"_slide_{len(prs.slides)}.png")
            img.save(img_path, "PNG")
            slide = prs.slides.add_slide(blank_layout)
            slide.shapes.add_picture(img_path, Inches(0), Inches(0), width=Inches(10), height=Inches(7.5))
            os.remove(img_path)  # python-pptx ya ha incrustado la imagen
        prs.save(output_path)
        keep_temp = True
        return render_template(
            "pdf_a_powerpoint.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "pdf_a_powerpoint.html",
            error=_friendly_error("convertir el PDF a PowerPoint", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_powerpoint/<token>")
def descargar_powerpoint(token):
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    output_path = os.path.join(temp_dir, "convertido.pptx")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    try:
        return send_file(output_path, as_attachment=True, download_name="convertido.pptx")
    finally:
        cleanup_folder(temp_dir)


# ─── /pdf-a-html ─────────────────────────────────────────────────────
@app.route("/pdf-a-html", methods=["GET", "POST"])
def pdf_a_html():
    if request.method == "GET":
        return render_template("pdf_a_html.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_html.html", error="Selecciona un PDF para convertir.")
    if not allowed_file(file.filename):
        return render_template("pdf_a_html.html", error="El archivo seleccionado no es un PDF.")
    size_error = validate_file_size(file, "pdf_a_html.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not validate_pdf(filepath):
            raise ConversionError("El archivo no se puede leer como PDF. Puede estar dañado o protegido.")
        output_path = os.path.join(temp_dir, "convertido.html")
        if fitz is None:
            raise ConversionError("Falta PyMuPDF para convertir el PDF a HTML.")
        doc = fitz.open(filepath)
        pages_html = []
        for i, page in enumerate(doc):
            pages_html.append(f"<section class='page' id='page{i+1}'>")
            pages_html.append(page.get_text("html"))
            pages_html.append("</section>")
        doc.close()
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>PDF convertido</title></head><body>"
            + "\n".join(pages_html)
            + "</body></html>"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        keep_temp = True
        return render_template(
            "pdf_a_html.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "pdf_a_html.html",
            error=_friendly_error("convertir el PDF a HTML", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


@app.route("/descargar_html/<token>")
def descargar_html(token):
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    output_path = os.path.join(temp_dir, "convertido.html")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    try:
        return send_file(output_path, as_attachment=True, download_name="convertido.html")
    finally:
        cleanup_folder(temp_dir)


# ─── /pdf-a-markdown ─────────────────────────────────────────────────
@app.route("/pdf-a-markdown", methods=["GET", "POST"])
def pdf_a_markdown():
    if request.method == "GET":
        return render_template("pdf_a_markdown.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_markdown.html", error="Selecciona un PDF para convertir.")
    if not allowed_file(file.filename):
        return render_template("pdf_a_markdown.html", error="El archivo seleccionado no es un PDF.")
    size_error = validate_file_size(file, "pdf_a_markdown.html")
    if size_error:
        return size_error

    temp_dir = _create_temp_dir()
    try:
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not validate_pdf(filepath):
            raise ConversionError("El archivo no se puede leer como PDF. Puede estar dañado o protegido.")

        reader = PdfReader(filepath)
        sections = ["# Documento extraído", ""]
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            sections.append(f"## Página {number}")
            sections.append("")
            sections.append(text if text else "_(sin texto extraíble)_")
            sections.append("")

        output_path = os.path.join(temp_dir, "convertido.md")
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(sections).rstrip() + "\n")

        return send_file(
            output_path,
            as_attachment=True,
            download_name="convertido.md",
            mimetype="text/markdown",
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "pdf_a_markdown.html",
            error=_friendly_error("convertir el PDF a Markdown", e),
        )
    finally:
        cleanup_folder(temp_dir)


# ─── /word-a-pdf ─────────────────────────────────────────────────────
@app.route("/word-a-pdf", methods=["GET", "POST"])
def word_a_pdf():
    if request.method == "GET":
        return render_template("word_a_pdf.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("word_a_pdf.html", error="Selecciona un archivo para convertir.")
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext not in ("docx", "doc", "html", "htm"):
        return render_template("word_a_pdf.html", error="El archivo no es un documento válido (DOCX/HTML).")
    size_error = validate_file_size(file, "word_a_pdf.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        unique_name = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}.bin"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not _valid_ooxml(filepath, ext):
            return render_template(
                "word_a_pdf.html", error="El archivo no es un documento DOCX válido."
            )
        output_path = os.path.join(temp_dir, "convertido.pdf")
        _office_to_pdf(filepath, output_path, ext)
        keep_temp = True
        return render_template(
            "word_a_pdf.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "word_a_pdf.html",
            error=_friendly_error("convertir el documento a PDF", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


# ─── /excel-a-pdf ────────────────────────────────────────────────────


@app.route("/excel-a-pdf", methods=["GET", "POST"])
def excel_a_pdf():
    if request.method == "GET":
        return render_template("excel_a_pdf.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("excel_a_pdf.html", error="Selecciona un archivo para convertir.")
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext not in ("xlsx", "xls", "csv"):
        return render_template("excel_a_pdf.html", error="El archivo no es una hoja de cálculo válida (XLSX/CSV).")
    size_error = validate_file_size(file, "excel_a_pdf.html")
    if size_error:
        return size_error
    # CSV -> convertir a xlsx primero
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        unique_name = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}.bin"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not _valid_ooxml(filepath, ext):
            return render_template(
                "excel_a_pdf.html", error="El archivo no es una hoja de cálculo XLSX válida."
            )
        if ext == "csv":
            # convertir CSV a xlsx para poder renderizarlo como tabla
            import csv as _csv
            if openpyxl is None:
                raise ConversionError("Falta openpyxl para leer la hoja de cálculo.")
            wb = openpyxl.Workbook()
            ws = wb.active
            with open(filepath, newline="", encoding="utf-8", errors="replace") as f:
                for row in _csv.reader(f):
                    ws.append(row)
            xlsx_path = os.path.join(temp_dir, "convertido.xlsx")
            wb.save(xlsx_path)
            filepath = xlsx_path
            ext = "xlsx"
        output_path = os.path.join(temp_dir, "convertido.pdf")
        _office_to_pdf(filepath, output_path, ext)
        keep_temp = True
        return render_template(
            "excel_a_pdf.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "excel_a_pdf.html",
            error=_friendly_error("convertir la hoja de cálculo a PDF", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


# ─── /powerpoint-a-pdf ───────────────────────────────────────────────


@app.route("/powerpoint-a-pdf", methods=["GET", "POST"])
def powerpoint_a_pdf():
    if request.method == "GET":
        return render_template("powerpoint_a_pdf.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("powerpoint_a_pdf.html", error="Selecciona un archivo para convertir.")
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext not in ("pptx", "ppt"):
        return render_template("powerpoint_a_pdf.html", error="El archivo no es una presentación válida (PPTX).")
    size_error = validate_file_size(file, "powerpoint_a_pdf.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    keep_temp = False
    try:
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        if not _valid_ooxml(filepath, ext):
            return render_template(
                "powerpoint_a_pdf.html", error="El archivo no es una presentación PPTX válida."
            )
        output_path = os.path.join(temp_dir, "convertido.pdf")
        _office_to_pdf(filepath, output_path, ext)
        keep_temp = True
        return render_template(
            "powerpoint_a_pdf.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "powerpoint_a_pdf.html",
            error=_friendly_error("convertir la presentación a PDF", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).
    finally:
        if not keep_temp:
            cleanup_folder(temp_dir)


# ─── /html-a-pdf ─────────────────────────────────────────────────────


@app.route("/html-a-pdf", methods=["GET", "POST"])
def html_a_pdf():
    if request.method == "GET":
        return render_template("html_a_pdf.html")
    file = request.files.get("file")
    if not file or file.filename == "":
        # permitir texto HTML pegado
        html_text = request.form.get("html_text", "").strip()
        if not html_text:
            return render_template("html_a_pdf.html", error="Selecciona un archivo HTML o pega el contenido.")
        temp_dir = _create_temp_dir()
        try:
            output_path = os.path.join(temp_dir, "convertido.pdf")
            _html_to_pdf(html_text, output_path)
            if not os.path.exists(output_path):
                raise ConversionError("No se generó el PDF a partir del HTML.")
            return render_template(
                "html_a_pdf.html",
                success=True,
                download_token=os.path.basename(temp_dir),
            )
        except Exception as e:
            cleanup_folder(temp_dir)
            return render_template(
                "html_a_pdf.html",
                error=_friendly_error("convertir el HTML a PDF", e),
            )
        # La carpeta se conserva hasta la descarga por token (UUID validado).
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext not in ("html", "htm"):
        return render_template("html_a_pdf.html", error="El archivo no es HTML válido.")
    size_error = validate_file_size(file, "html_a_pdf.html")
    if size_error:
        return size_error
    temp_dir = _create_temp_dir()
    try:
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)
        output_path = os.path.join(temp_dir, "convertido.pdf")
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        _html_to_pdf(html, output_path)
        if not os.path.exists(output_path):
            raise ConversionError("No se generó el PDF a partir del HTML.")
        return render_template(
            "html_a_pdf.html",
            success=True,
            download_token=os.path.basename(temp_dir),
        )
    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template(
            "html_a_pdf.html",
            error=_friendly_error("convertir el HTML a PDF", e),
        )
    # La carpeta se conserva hasta la descarga por token (UUID validado).


@app.route("/descargar_pdf/<token>")
def descargar_pdf_convertido(token):
    temp_dir = _safe_upload_dir(token)
    if temp_dir is None:
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    output_path = os.path.join(temp_dir, "convertido.pdf")
    if not os.path.exists(output_path):
        return render_template("error.html", message="El archivo ya no está disponible."), 404
    try:
        return send_file(output_path, as_attachment=True, download_name="convertido.pdf")
    finally:
        cleanup_folder(temp_dir)


# ─── v1.4 · Firma, censura y comparación ──────────────────────────────

MAX_COMPARE_PAGES = 100


def _page_texts(pdf_path):
    """Devuelve el texto extraído de cada página de un PDF."""
    reader = PdfReader(pdf_path)
    return [page.extract_text() or "" for page in reader.pages]


@app.route("/firmar", methods=["GET", "POST"])
def firmar():
    if request.method == "GET":
        return render_template("firmar.html")

    pdf_file = request.files.get("file")
    cert_file = request.files.get("certificate")
    password = request.form.get("password", "")

    if not pdf_file or pdf_file.filename == "":
        return render_template("firmar.html", error="Selecciona el PDF que quieres firmar.")
    if not cert_file or cert_file.filename == "":
        return render_template("firmar.html", error="Selecciona tu certificado digital (.p12 o .pfx).")
    if not allowed_file(pdf_file.filename):
        return render_template("firmar.html", error="El archivo seleccionado no es un PDF.")

    cert_name = cert_file.filename.lower()
    if not (cert_name.endswith(".p12") or cert_name.endswith(".pfx")):
        return render_template(
            "firmar.html",
            error="El certificado debe ser un archivo PKCS#12 (.p12 o .pfx).",
        )

    size_error = validate_file_size(pdf_file, "firmar.html")
    if size_error:
        return size_error
    size_error = validate_file_size(cert_file, "firmar.html", "El certificado")
    if size_error:
        return size_error

    if IncrementalPdfFileWriter is None:
        return render_template(
            "firmar.html",
            error="La firma digital no está disponible. Instala las dependencias del proyecto.",
        )

    temp_dir = _create_temp_dir()
    try:
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}.pdf")
        pdf_file.save(filepath)
        if not validate_pdf(filepath):
            return render_template("firmar.html", error="El archivo no es un PDF válido.")

        cert_data = cert_file.read()
        if not cert_data:
            return render_template("firmar.html", error="El certificado está vacío.")

        signer = pyhanko_signers.SimpleSigner.load_pkcs12_data(
            cert_data,
            other_certs=[],
            passphrase=password.encode("utf-8") if password else None,
        )
        signature = PdfSignatureMetadata(
            field_name="Firma",
            reason="Firmado digitalmente con Pedeefe",
            name="Pedeefe",
        )
        signed = BytesIO()
        with open(filepath, "rb") as src:
            writer = IncrementalPdfFileWriter(src)
            pyhanko_signers.sign_pdf(writer, signature, signer=signer, output=signed)

        output_path = os.path.join(temp_dir, "firmado.pdf")
        with open(output_path, "wb") as dst:
            dst.write(signed.getvalue())
        return send_file(output_path, as_attachment=True, download_name="firmado.pdf")
    except Exception:
        return render_template(
            "firmar.html",
            error="No se pudo firmar el PDF. Comprueba que el certificado y su contraseña sean correctos.",
        )
    finally:
        cleanup_folder(temp_dir)


@app.route("/censurar", methods=["GET", "POST"])
def censurar():
    if request.method == "GET":
        return render_template("censurar.html")

    pdf_file = request.files.get("file")
    terms_raw = request.form.get("terms", "")
    if not pdf_file or pdf_file.filename == "":
        return render_template("censurar.html", error="Selecciona el PDF que quieres censurar.")
    if not allowed_file(pdf_file.filename):
        return render_template("censurar.html", error="El archivo seleccionado no es un PDF.")

    terms = [
        term.strip()
        for term in terms_raw.replace(",", "\n").replace(";", "\n").splitlines()
        if term.strip()
    ]
    if not terms:
        return render_template(
            "censurar.html",
            error="Escribe al menos un término para censurar (uno por línea).",
        )

    size_error = validate_file_size(pdf_file, "censurar.html")
    if size_error:
        return size_error
    if fitz is None:
        return render_template(
            "censurar.html",
            error="La censura no está disponible. Instala las dependencias del proyecto.",
        )

    temp_dir = _create_temp_dir()
    try:
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}.pdf")
        pdf_file.save(filepath)
        if not validate_pdf(filepath):
            return render_template("censurar.html", error="El archivo no es un PDF válido.")

        output_path = os.path.join(temp_dir, "censurado.pdf")
        matches = 0
        with fitz.open(filepath) as doc:
            for page in doc:
                rects = []
                for term in terms:
                    rects.extend(page.search_for(term))
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                if rects:
                    page.apply_redactions()
                matches += len(rects)
            doc.save(output_path, garbage=4, deflate=True)

        if matches == 0:
            return render_template(
                "censurar.html",
                error="No se encontró ninguna coincidencia. Revisa los términos escritos.",
            )
        return send_file(output_path, as_attachment=True, download_name="censurado.pdf")
    except Exception:
        return render_template(
            "censurar.html",
            error="No se pudo censurar el PDF. Comprueba que el archivo no esté dañado.",
        )
    finally:
        cleanup_folder(temp_dir)


@app.route("/comparar", methods=["GET", "POST"])
def comparar():
    if request.method == "GET":
        return render_template("comparar.html")

    first = request.files.get("file1")
    second = request.files.get("file2")
    if not first or first.filename == "":
        return render_template("comparar.html", error="Selecciona el primer PDF.")
    if not second or second.filename == "":
        return render_template("comparar.html", error="Selecciona el segundo PDF.")

    for upload, label in ((first, "El primer PDF"), (second, "El segundo PDF")):
        if not allowed_file(upload.filename):
            return render_template("comparar.html", error=f"{label} no es un PDF.")
        size_error = validate_file_size(upload, "comparar.html", label)
        if size_error:
            return size_error

    temp_dir = _create_temp_dir()
    try:
        paths = []
        for upload in (first, second):
            path = os.path.join(temp_dir, f"{uuid.uuid4()}.pdf")
            upload.save(path)
            if not validate_pdf(path):
                return render_template(
                    "comparar.html", error="Uno de los archivos no es un PDF válido."
                )
            paths.append(path)

        texts = [_page_texts(path) for path in paths]
        total_pages = max(len(texts[0]), len(texts[1]))
        shown_pages = min(total_pages, MAX_COMPARE_PAGES)
        differ = difflib.HtmlDiff(wrapcolumn=78)
        diffs = []
        for index in range(shown_pages):
            lines1 = (texts[0][index] if index < len(texts[0]) else "").splitlines()
            lines2 = (texts[1][index] if index < len(texts[1]) else "").splitlines()
            diffs.append(
                {
                    "page": index + 1,
                    "changed": lines1 != lines2,
                    "table": differ.make_table(
                        lines1,
                        lines2,
                        fromdesc="PDF 1",
                        todesc="PDF 2",
                        context=True,
                        numlines=2,
                    ),
                }
            )

        return render_template(
            "comparar.html",
            success=True,
            diffs=diffs,
            changed=sum(1 for item in diffs if item["changed"]),
            total=shown_pages,
            truncated=total_pages > shown_pages,
            file1_name=first.filename,
            file2_name=second.filename,
        )
    except Exception:
        return render_template(
            "comparar.html",
            error="No se pudo comparar los PDF. Comprueba que no estén cifrados ni dañados.",
        )
    finally:
        cleanup_folder(temp_dir)


# ─── Lotes: una operación aplicada a varios PDF (v1.5) ───────────────


def _batch_page(message, **values):
    """Renderiza /lotes con un error legible y conserva los valores del formulario."""
    context = {
        "operations": BATCH_OPERATIONS,
        "limits": BATCH_LIMITS,
        "error": message,
    }
    context.update(values)
    return render_template("lotes.html", **context)


def _batch_output_name(filename, operation, index):
    """Nombre seguro y legible para el PDF resultante dentro del ZIP."""
    stem = os.path.splitext(os.path.basename(filename or "documento"))[0]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")[:60]
    stem = stem or "documento"
    return f"{stem}_{BATCH_SUFFIXES[operation]}.pdf"


def _upload_size(upload):
    """Tamaño real de un archivo subido, dejando el puntero al inicio."""
    upload.seek(0, os.SEEK_END)
    size = upload.tell()
    upload.seek(0)
    return size


def _process_batch_pdf(source, target, operation, params):
    """Aplica una operación a un PDF. Las excepciones se traducen en la ruta."""
    if operation == "optimizar":
        with pikepdf.open(source) as pdf:
            pdf.save(target)
        return

    reader = PdfReader(source)
    if operation == "desproteger":
        if not reader.is_encrypted:
            raise ValueError("Uno de los PDF no tiene contraseña.")
        if not reader.decrypt(params["password"]):
            raise ValueError("La contraseña no abre todos los PDF del lote.")
    elif reader.is_encrypted:
        raise ValueError("Uno de los PDF está protegido; desprotégelo antes del lote.")

    writer = PdfWriter()
    if operation == "rotar":
        for page in reader.pages:
            page.rotate(params["angle"])
            writer.add_page(page)
    elif operation == "proteger":
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(params["password"])
    elif operation == "desproteger":
        for page in reader.pages:
            writer.add_page(page)
    elif operation == "marcar_agua":
        for page in reader.pages:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            if width <= 0 or height <= 0:
                width = float(page.cropbox.width)
                height = float(page.cropbox.height)
            watermark = PdfReader(
                create_watermark_pdf(params["watermark_text"], width, height)
            ).pages[0]
            # pypdf 7 exige añadir la página antes de superponer.
            writer.add_page(page)
            writer.pages[-1].merge_page(watermark)
    elif operation == "numerar":
        for offset, page in enumerate(reader.pages):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            numbers = create_page_number_pdf(
                width, height, params["start_num"] + offset, params["position"]
            )
            writer.add_page(page)
            writer.pages[-1].merge_page(PdfReader(numbers).pages[0])

    with open(target, "wb") as handle:
        writer.write(handle)


@app.route("/lotes", methods=["GET", "POST"])
def lotes():
    """Aplica la misma operación a varios PDFs y entrega un ZIP con los resultados."""
    if request.method == "GET":
        return render_template(
            "lotes.html",
            operation="rotar",
            operations=BATCH_OPERATIONS,
            limits=BATCH_LIMITS,
        )

    operation = request.form.get("operation", "rotar")
    if operation not in BATCH_OPERATIONS:
        return _batch_page("Selecciona una operación válida para el lote.", operation="rotar")

    form_state = {
        "operation": operation,
        "angle": request.form.get("angle", "90"),
        "watermark_text": request.form.get("watermark_text", ""),
        "position": request.form.get("position", "bottom_center"),
        "start_num": request.form.get("start_num", "1"),
    }
    angle = form_state["angle"] if form_state["angle"] in ("90", "180", "270") else "90"
    form_state["angle"] = angle
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    watermark_text = form_state["watermark_text"].strip()
    position = form_state["position"]
    if position not in (
        "bottom_center", "bottom_right", "bottom_left",
        "top_center", "top_right", "top_left",
    ):
        position = "bottom_center"
    try:
        start_num = max(1, int(form_state["start_num"]))
    except (TypeError, ValueError):
        start_num = 1
    form_state["position"] = position
    form_state["start_num"] = str(start_num)

    if operation == "proteger":
        if not password:
            return _batch_page("Introduce una contraseña para proteger los PDF.", **form_state)
        if password != password_confirm:
            return _batch_page("Las contraseñas no coinciden. Vuelve a introducirlas.", **form_state)
    if operation == "desproteger" and not password:
        return _batch_page("Introduce la contraseña de los PDF.", **form_state)
    if operation == "marcar_agua" and not watermark_text:
        return _batch_page("Introduce el texto de la marca de agua.", **form_state)

    uploads = [item for item in request.files.getlist("files") if item and item.filename]
    if not uploads:
        return _batch_page("Selecciona al menos un PDF para el lote.", **form_state)
    if len(uploads) > MAX_BATCH_FILES:
        return _batch_page(
            f"El lote admite como máximo {MAX_BATCH_FILES} PDFs. Divide la selección en varios lotes.",
            **form_state,
        )

    params = {
        "angle": int(angle),
        "password": password,
        "watermark_text": watermark_text,
        "position": position,
        "start_num": start_num,
    }

    temp_dir = _create_temp_dir()
    try:
        total_size = 0
        total_pages = 0
        inputs = []
        for index, upload in enumerate(uploads, 1):
            if not allowed_file(upload.filename):
                return _batch_page(f"'{upload.filename}' no es un PDF.", **form_state)

            size = _upload_size(upload)
            if size > MAX_FILE_SIZE:
                return _batch_page(
                    f"'{upload.filename}' supera el límite de 50 MB.", **form_state
                )
            total_size += size
            if total_size > MAX_BATCH_TOTAL_SIZE:
                return _batch_page(
                    f"El lote supera el límite total de {BATCH_LIMITS['total_mb']} MB. "
                    "Procesa menos archivos por vez.",
                    **form_state,
                )

            source = os.path.join(temp_dir, f"entrada_{index}.pdf")
            upload.save(source)
            if not validate_pdf(source):
                return _batch_page(
                    f"'{upload.filename}' no se puede leer como PDF.", **form_state
                )

            reader = PdfReader(source)
            if reader.is_encrypted:
                if operation != "desproteger":
                    return _batch_page(
                        f"'{upload.filename}' está protegido. Desprotégelo antes del lote.",
                        **form_state,
                    )
                if not reader.decrypt(password):
                    return _batch_page(
                        "La contraseña no abre todos los PDF del lote.", **form_state
                    )
            elif operation == "desproteger":
                return _batch_page(f"'{upload.filename}' no tiene contraseña.", **form_state)

            total_pages += len(reader.pages)
            if total_pages > MAX_BATCH_PAGES:
                return _batch_page(
                    f"El lote supera el límite de {MAX_BATCH_PAGES} páginas en total. "
                    "Procesa menos archivos por vez.",
                    **form_state,
                )
            inputs.append((upload.filename, source))

        zip_path = os.path.join(temp_dir, f"lote_{operation}.zip")
        used_names = set()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, (filename, source) in enumerate(inputs, 1):
                base_name = _batch_output_name(filename, operation, index)
                output_name = base_name
                duplicate = 2
                while output_name in used_names:
                    stem, ext = os.path.splitext(base_name)
                    output_name = f"{stem}_{duplicate}{ext}"
                    duplicate += 1
                used_names.add(output_name)

                target = os.path.join(temp_dir, f"salida_{index}.pdf")
                try:
                    _process_batch_pdf(source, target, operation, params)
                except Exception:
                    # No exponer str(e): el archivo puede contener datos del equipo.
                    return _batch_page(
                        f"No se pudo procesar '{filename}'. Comprueba que el PDF no esté dañado.",
                        **form_state,
                    )
                archive.write(target, arcname=output_name)

        return send_file(
            zip_path, as_attachment=True, download_name=f"lote_{operation}.zip"
        )
    except Exception:
        return _batch_page(
            "No se pudo completar el lote. Revisa los archivos seleccionados.",
            **form_state,
        )
    finally:
        cleanup_folder(temp_dir)


# ─── Historial y plantillas locales (v1.5) ───────────────────────────
# El servidor solo entrega estas páginas: los datos viven en localStorage del
# navegador (metadatos y parámetros, nunca archivos ni su contenido).

@app.route("/historial")
def historial():
    return render_template(
        "historial.html",
        history_days=HISTORY_TTL_DAYS,
        history_max=HISTORY_MAX_ENTRIES,
    )


@app.route("/plantillas")
def plantillas():
    return render_template(
        "plantillas.html",
        template_days=TEMPLATE_TTL_DAYS,
        template_max=TEMPLATE_MAX_ENTRIES,
    )


# ─── API local JSON y CLI (v2.0) ──────────────────────────────────────
# La API comparte el único servidor Flask enlazado a 127.0.0.1: no abre puertos
# nuevos. Reutiliza los handlers web mediante un contexto de petición
# sintético, de modo que la lógica de procesamiento no se duplica y la API y la
# interfaz no puedan divergir. Toda petición exige el token local del perfil.


def _api_file(name, multiple=False, required=True):
    return {"name": name, "multiple": multiple, "required": required}


API_TOOLS = {
    "unir": {
        "label": "Unir PDFs", "endpoint": "unir", "route": "/unir",
        "files": [_api_file("files", multiple=True)], "params": [],
    },
    "dividir": {
        "label": "Dividir PDF", "endpoint": "dividir", "route": "/dividir",
        "files": [_api_file("file")], "params": ["mode", "range"],
    },
    "comprimir": {
        "label": "Optimizar PDF", "endpoint": "comprimir", "route": "/comprimir",
        "files": [_api_file("file")], "params": [],
    },
    "comprimir-real": {
        "label": "Comprimir con Ghostscript", "endpoint": "comprimir_real",
        "route": "/comprimir-real", "files": [_api_file("file")], "params": [],
    },
    "pdf-a-imagen": {
        "label": "PDF a imagen", "endpoint": "pdf_a_imagen",
        "route": "/pdf-a-imagen", "files": [_api_file("file")], "params": ["format"],
    },
    "imagen-a-pdf": {
        "label": "Imágenes a PDF", "endpoint": "imagen_a_pdf",
        "route": "/imagen-a-pdf", "files": [_api_file("files", multiple=True)],
        "params": [],
    },
    "pdf-a-word": {
        "label": "PDF a Word", "endpoint": "pdf_a_word", "route": "/pdf-a-word",
        "files": [_api_file("file")], "params": [],
    },
    "rotar": {
        "label": "Rotar PDF", "endpoint": "rotar", "route": "/rotar",
        "files": [_api_file("file")], "params": ["angle"],
    },
    "proteger": {
        "label": "Proteger PDF", "endpoint": "proteger", "route": "/proteger",
        "files": [_api_file("file")], "params": ["password", "password_confirm"],
    },
    "desproteger": {
        "label": "Desproteger PDF", "endpoint": "desproteger",
        "route": "/desproteger", "files": [_api_file("file")], "params": ["password"],
    },
    "ocr": {
        "label": "OCR", "endpoint": "ocr", "route": "/ocr",
        "files": [_api_file("file")], "params": ["lang"],
    },
    "ocr-a-pdf": {
        "label": "OCR a PDF buscable", "endpoint": "ocr_a_pdf",
        "route": "/ocr-a-pdf", "files": [_api_file("file")], "params": ["lang"],
    },
    "limpiar-metadatos": {
        "label": "Limpiar metadatos", "endpoint": "limpiar_metadatos",
        "route": "/limpiar-metadatos", "files": [_api_file("file")],
        "params": ["clear_info", "clear_xmp", "clear_attachments", "clear_js",
                   "clear_page_meta", "title", "author", "subject", "keywords"],
    },
    "marcar-agua": {
        "label": "Marcar con agua", "endpoint": "marcar_agua",
        "route": "/marcar-agua", "files": [_api_file("file")],
        "params": ["watermark_text"],
    },
    "numerar": {
        "label": "Numerar páginas", "endpoint": "numerar", "route": "/numerar",
        "files": [_api_file("file")], "params": ["position", "start_num"],
    },
    "recortar-pdf": {
        "label": "Recortar PDF", "endpoint": "recortar_pdf",
        "route": "/recortar-pdf", "files": [_api_file("file")], "params": ["range"],
    },
    "reordenar-pdf": {
        "label": "Reordenar páginas", "endpoint": "reordenar_pdf",
        "route": "/reordenar-pdf", "files": [_api_file("file")], "params": ["order"],
    },
    "pdf-a-excel": {
        "label": "PDF a Excel", "endpoint": "pdf_a_excel",
        "route": "/pdf-a-excel", "files": [_api_file("file")], "params": [],
    },
    "pdf-a-powerpoint": {
        "label": "PDF a PowerPoint", "endpoint": "pdf_a_powerpoint",
        "route": "/pdf-a-powerpoint", "files": [_api_file("file")], "params": [],
    },
    "pdf-a-html": {
        "label": "PDF a HTML", "endpoint": "pdf_a_html",
        "route": "/pdf-a-html", "files": [_api_file("file")], "params": [],
    },
    "pdf-a-markdown": {
        "label": "PDF a Markdown", "endpoint": "pdf_a_markdown",
        "route": "/pdf-a-markdown", "files": [_api_file("file")], "params": [],
    },
    "word-a-pdf": {
        "label": "Word a PDF", "endpoint": "word_a_pdf",
        "route": "/word-a-pdf", "files": [_api_file("file")], "params": [],
    },
    "excel-a-pdf": {
        "label": "Excel a PDF", "endpoint": "excel_a_pdf",
        "route": "/excel-a-pdf", "files": [_api_file("file")], "params": [],
    },
    "powerpoint-a-pdf": {
        "label": "PowerPoint a PDF", "endpoint": "powerpoint_a_pdf",
        "route": "/powerpoint-a-pdf", "files": [_api_file("file")], "params": [],
    },
    "html-a-pdf": {
        "label": "HTML a PDF", "endpoint": "html_a_pdf",
        "route": "/html-a-pdf", "files": [_api_file("file", required=False)],
        "params": ["html_text"],
    },
    "firmar": {
        "label": "Firmar PDF", "endpoint": "firmar", "route": "/firmar",
        "files": [_api_file("file"), _api_file("certificate")], "params": ["password"],
    },
    "censurar": {
        "label": "Censurar PDF", "endpoint": "censurar", "route": "/censurar",
        "files": [_api_file("file")], "params": ["terms"],
    },
    "comparar": {
        "label": "Comparar PDFs", "endpoint": "comparar", "route": "/comparar",
        "files": [_api_file("file1"), _api_file("file2")], "params": [],
    },
    "lotes": {
        "label": "Procesar lote", "endpoint": "lotes", "route": "/lotes",
        "files": [_api_file("files", multiple=True)],
        "params": ["operation", "angle", "password", "password_confirm",
                   "watermark_text", "position", "start_num"],
    },
}


@app.before_request
def _require_local_api_token():
    """La API exige el token local; el resto de rutas no cambian."""
    if not request.path.startswith("/api/"):
        return None
    expected = get_or_create_api_token()
    if request.headers.get("Authorization", "") != "Bearer " + expected:
        return jsonify({"ok": False, "error": "Token de API local no válido."}), 401
    return None


def _api_forward_data():
    """Copia archivos y campos de la petición API al contexto de la web."""
    data = {}
    for key in request.form.keys():
        values = request.form.getlist(key)
        data[key] = values if len(values) > 1 else values[0]
    for key in request.files.keys():
        values = request.files.getlist(key)
        data[key] = values if len(values) > 1 else values[0]
    return data


def _api_html_error(html):
    """Extrae el mensaje de error que la plantilla web habría mostrado."""
    pattern = r'class="alert alert-error"[^>]*>\s*(.*?)\s*</div>'
    match = re.search(pattern, html, re.S)
    if not match:
        match = re.search(r'<section class="error-page">.*?<p>(.*?)</p>', html, re.S)
    if not match:
        return None
    return unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() or None


def _api_html_download(html):
    """Sigue el enlace de descarga por token que renderiza la web."""
    match = re.search(
        r'href="(/descargar_[a-z_]+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
        r'[0-9a-f]{4}-[0-9a-f]{12})"',
        html,
    )
    if not match:
        return None
    return app.test_client().get(match.group(1))


def _response_body(response):
    """Lee el cuerpo de un send_file, que usa direct_passthrough por defecto."""
    try:
        if response.direct_passthrough:
            response.direct_passthrough = False
        return response.get_data()
    finally:
        response.close()


def _api_file_response(source, slug, body):
    """Devuelve el binario con el nombre que la web habría descargado."""
    header = source.headers.get("Content-Disposition", "")
    match = re.search(r'filename="?([^";]+)"?', header)
    download_name = match.group(1) if match else slug + ".bin"
    response = make_response(body)
    response.headers["Content-Type"] = source.mimetype or "application/octet-stream"
    response.headers["Content-Disposition"] = (
        'attachment; filename="' + os.path.basename(download_name) + '"'
    )
    response.headers["X-Pedeefe-Format"] = "file"
    response.headers["X-Pedeefe-Tool"] = slug
    return response


def _api_convert_response(web_response, slug):
    """Convierte la respuesta web en JSON o en el archivo resultante."""
    if isinstance(web_response, str):
        # render_template devuelve str cuando se llama al handler directamente.
        web_response = Response(web_response, mimetype="text/html")
    if web_response.status_code != 200:
        return jsonify({"ok": False, "error": "No se pudo procesar la petición."}), \
            web_response.status_code

    if web_response.mimetype != "text/html":
        return _api_file_response(web_response, slug, _response_body(web_response))

    html = web_response.get_data(as_text=True)
    error = _api_html_error(html)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    download = _api_html_download(html)
    if download is not None:
        if download.status_code != 200:
            return jsonify({
                "ok": False,
                "error": "El resultado ya no está disponible.",
            }), 404
        return _api_file_response(download, slug, _response_body(download))

    return jsonify({"ok": True, "tool": slug, "format": "html", "content": html})


@app.route("/api/v1/tools", methods=["GET"])
def api_tools():
    """Catálogo de herramientas disponibles para el CLI y scripts locales."""
    tools = []
    for slug, spec in API_TOOLS.items():
        tools.append({
            "slug": slug,
            "label": spec["label"],
            "files": spec["files"],
            "params": spec["params"],
        })
    return jsonify({
        "ok": True,
        "version": "2.4.1",
        "count": len(tools),
        "tools": tools,
    })


@app.route("/api/v1/tools/<slug>", methods=["POST"])
def api_run_tool(slug):
    """Ejecuta una herramienta web y devuelve su archivo o un JSON."""
    spec = API_TOOLS.get(slug)
    if spec is None:
        return jsonify({"ok": False, "error": f"Herramienta desconocida: {slug}"}), 404

    data = _api_forward_data()
    try:
        with app.test_request_context(spec["route"], method="POST", data=data):
            web_response = app.view_functions[spec["endpoint"]]()
        return _api_convert_response(web_response, slug)
    except Exception as exc:  # pragma: no cover — mensaje accionable al cliente
        detail = _log_unexpected_error(exc)
        cause, fix = _describe_unexpected_error(exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
            "cause": cause,
            "fix": fix,
            "detail": detail,
        }), 500


if __name__ == "__main__":
    # El modo debug se controla por la variable de entorno FLASK_DEBUG.
    # Por defecto False (seguro, incluido en Docker). Activar solo en
    # desarrollo local: FLASK_DEBUG=1.
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "43210"))
    app.run(host=host, port=port, debug=debug)
