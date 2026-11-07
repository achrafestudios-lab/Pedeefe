import os
import uuid
import shutil
import zipfile
from io import BytesIO
from flask import Flask, render_template, request, send_file, abort
from pypdf import PdfReader, PdfWriter
import pikepdf
# pdf2image requiere Poppler instalado en el sistema:
#   Ubuntu/Debian: sudo apt install poppler-utils
#   Fedora: sudo dnf install poppler-utils
#   macOS: brew install poppler
from pdf2image import convert_from_path
from PIL import Image
from pdf2docx import Converter

# pytesseract requiere Tesseract OCR instalado en el sistema:
#   Ubuntu/Debian: sudo apt install tesseract-ocr
#   Fedora: sudo dnf install tesseract
#   macOS: brew install tesseract
import pytesseract

# reportlab para generar la marca de agua como PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color
from reportlab.lib import colors

app = Flask(__name__)

# Configuración
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB máximo por archivo
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Asegurar que uploads/ existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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


# ─── Error 413 (archivo demasiado grande) ────────────────────────────

# Mapeo de referer a plantilla para redirigir al usuario a la página de origen
REFERER_TO_TEMPLATE = {
    "/unir": "unir.html",
    "/dividir": "dividir.html",
    "/comprimir": "comprimir.html",
    "/pdf-a-imagen": "pdf_a_imagen.html",
    "/imagen-a-pdf": "imagen_a_pdf.html",
    "/pdf-a-word": "pdf_a_word.html",
    "/rotar": "rotar.html",
    "/proteger": "proteger.html",
    "/desproteger": "desproteger.html",
    "/ocr": "ocr.html",
    "/marcar-agua": "marcar_agua.html",
    "/numerar": "numerar.html",
}


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


# ─── Página principal ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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
        return render_template("dividir.html", error="Selecciona un PDF para dividir.")

    if not allowed_file(file.filename):
        return render_template("dividir.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "dividir.html")
    if size_error:
        return size_error

    # Carpeta temporal única para esta petición
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("dividir.html", error="El archivo no se puede leer como PDF.")

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
                return render_template("dividir.html", error="Indica el rango de páginas.")

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
                    error="El rango no es válido. Usa el formato 'inicio-fin' (ej: 1-3)."
                )

            # Validar el rango
            if start < 1 or end < 1:
                return render_template(
                    "dividir.html",
                    error=f"El rango debe empezar desde 1. El PDF tiene {total_pages} páginas."
                )
            if start > total_pages or end > total_pages:
                return render_template(
                    "dividir.html",
                    error=f"El rango supera el número de páginas. El PDF tiene {total_pages} páginas."
                )
            if start > end:
                return render_template(
                    "dividir.html",
                    error="El inicio del rango no puede ser mayor que el fin."
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
            return render_template("dividir.html", error="Selecciona un modo de división.")

    except Exception as e:
        return render_template("dividir.html", error=f"Error al dividir: {str(e)}")
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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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
        return render_template(
            "comprimir.html",
            success=True,
            original_size=format_size(original_size),
            compressed_size=format_size(compressed_size),
            reduction=round(reduction, 1),
            download_token=os.path.basename(temp_dir)  # UUID de la carpeta temporal
        )

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("comprimir.html", error=f"Error al comprimir: {str(e)}")


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


# ─── PDF a Imágenes ──────────────────────────────────────────────

@app.route("/pdf-a-imagen", methods=["GET", "POST"])
def pdf_a_imagen():
    if request.method == "GET":
        return render_template("pdf_a_imagen.html")

    # Recibir archivo
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("pdf_a_imagen.html", error="Selecciona un PDF para convertir.")

    if not allowed_file(file.filename):
        return render_template("pdf_a_imagen.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "pdf_a_imagen.html")
    if size_error:
        return size_error

    # Obtener formato de imagen elegido
    format_choice = request.form.get("format", "jpg")
    if format_choice not in ("jpg", "png"):
        format_choice = "jpg"

    # Carpeta temporal única para esta petición
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("pdf_a_imagen.html", error="El archivo no se puede leer como PDF.")

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
            error_msg = "No se encontró Poppler en el sistema. Instálalo con: sudo apt install poppler-utils"
        return render_template("pdf_a_imagen.html", error=f"Error al convertir: {error_msg}")
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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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
        # La primera imagen define el tamaño base del PDF
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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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

        return render_template(
            "pdf_a_word.html",
            success=True,
            download_path=output_path,
            download_token=os.path.basename(temp_dir),
            warning_scanned=(not has_text) or is_likely_scanned
        )

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("pdf_a_word.html", error=f"Error al convertir: {str(e)}")


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
        return render_template("rotar.html", error="Selecciona un PDF para rotar.")

    if not allowed_file(file.filename):
        return render_template("rotar.html", error="El archivo seleccionado no es un PDF.")

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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("rotar.html", error="El archivo no se puede leer como PDF.")

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
        return render_template("rotar.html", error=f"Error al rotar: {str(e)}")
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

    # Obtener la contraseña
    password = request.form.get("password", "").strip()
    if not password:
        return render_template("proteger.html", error="Introduce una contraseña para proteger el PDF.")

    # Carpeta temporal única para esta petición
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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

@app.route("/ocr", methods=["GET", "POST"])
def ocr():
    if request.method == "GET":
        return render_template("ocr.html")

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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

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
            text = pytesseract.image_to_string(image, lang="spa")
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
        error_msg = str(e)
        # Mensaje amigable si Tesseract no está instalado
        if "tesseract" in error_msg.lower() or "not found" in error_msg.lower():
            error_msg = "No se encontró Tesseract OCR en el sistema. Instálalo con: sudo apt install tesseract-ocr"
        # Mensaje amigable si Poppler no está instalado
        elif "poppler" in error_msg.lower():
            error_msg = "No se encontró Poppler en el sistema. Instálalo con: sudo apt install poppler-utils"
        return render_template("ocr.html", error=f"Error al procesar: {error_msg}")
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
        return render_template("marcar_agua.html", error="Selecciona un PDF para marcar.")

    if not allowed_file(file.filename):
        return render_template("marcar_agua.html", error="El archivo seleccionado no es un PDF.")

    # Validar tamaño del archivo
    size_error = validate_file_size(file, "marcar_agua.html")
    if size_error:
        return size_error

    # Obtener el texto de la marca de agua
    watermark_text = request.form.get("watermark_text", "").strip()
    if not watermark_text:
        return render_template("marcar_agua.html", error="Introduce el texto para la marca de agua.")

    # Carpeta temporal única para esta petición
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("marcar_agua.html", error="El archivo no se puede leer como PDF.")

        # Leer el PDF original
        reader = PdfReader(filepath)
        writer = PdfWriter()

        # Crear la marca de agua como PDF
        watermark_packet = create_watermark_pdf(watermark_text, A4[0], A4[1])
        watermark_reader = PdfReader(watermark_packet)
        watermark_page = watermark_reader.pages[0]

        # Superponer la marca de agua en cada página
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "marcado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="marcado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("marcar_agua.html", error=f"Error al añadir marca de agua: {str(e)}")
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
        return render_template("numerar.html", error="Selecciona un PDF para numerar.")

    if not allowed_file(file.filename):
        return render_template("numerar.html", error="El archivo seleccionado no es un PDF.")

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
    temp_dir = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(temp_dir)

    try:
        # Guardar archivo temporalmente con nombre único
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(temp_dir, unique_name)
        file.save(filepath)

        # Validar que sea un PDF real
        if not validate_pdf(filepath):
            return render_template("numerar.html", error="El archivo no se puede leer como PDF.")

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

            # Superponer el número sobre la página
            page.merge_page(num_page)
            writer.add_page(page)

        # Guardar resultado
        output_path = os.path.join(temp_dir, "numerado.pdf")
        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="numerado.pdf")

    except Exception as e:
        cleanup_folder(temp_dir)
        return render_template("numerar.html", error=f"Error al numerar: {str(e)}")
    finally:
        cleanup_folder(temp_dir)


if __name__ == "__main__":
    app.run(debug=True)
