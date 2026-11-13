# Imagen base Python (slim) para Pedeefe (Flask monolítico).
FROM python:3.12-slim

# Dependencias del sistema: Poppler (pdftoppm) y Tesseract OCR (español).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-spa \
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
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]