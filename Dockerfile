# Imagen base Python (slim) para Pedeefe (Flask monolítico).
FROM python:3.12-slim

# Dependencias del sistema: Poppler (pdftoppm) y Tesseract OCR (español).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        ghostscript \
        tesseract-ocr \
        tesseract-ocr-spa \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        libreoffice \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python primero (mejor caché de capas).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código (ver .dockerignore: .venv, uploads, __pycache__, .git).
COPY . .

# Configuración de ejecución.
ENV FLASK_HOST=0.0.0.0
ENV FLASK_DEBUG=0
ENV PORT=43210
ENV PYTHONUNBUFFERED=1

EXPOSE 43210

CMD ["python", "app.py"]