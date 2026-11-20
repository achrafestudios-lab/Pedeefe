# Pedeefe — Caja de herramientas PDF local

<p align="center">
  <span style="font-size:88px">📄</span>
</p>

<p align="center">
  <strong>Manipula tus PDFs sin subirlos a ningún servidor</strong><br>
  App web local. Sin cuenta, sin nube, sin base de datos. Todo en tu máquina.
</p>

<p align="center">
  <a href="https://github.com/achrafestudios-lab/Pedeefe">
    <img src="https://img.shields.io/badge/repo-Pedeefe-0A7CFF?style=for-the-badge&logo=github" alt="GitHub">
  </a>
  <a href="https://github.com/achrafestudios-lab/Pedeefe">
    <img src="https://img.shields.io/github/stars/achrafestudios-lab/Pedeefe?style=for-the-badge" alt="Stars">
  </a>
  <a href="https://github.com/achrafestudios-lab/Pedeefe">
    <img src="https://img.shields.io/badge/licencia-sin%20definir-lightgrey?style=for-the-badge" alt="Licencia">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/docker-listo-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/tests-140%20passed-brightgreen?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/local-sin%20servidor-58e99e?style=for-the-badge" alt="Local">
  <img src="https://img.shields.io/badge/puerto-43210-orange?style=for-the-badge" alt="Puerto">
</p>

<p align="center">
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="#instalación-desde-fuente">Instalar desde fuente</a> ·
  <a href="#herramientas">Herramientas</a> ·
  <a href="#documentación">Documentación</a>
</p>

---

## Índice

- [¿Qué es Pedeefe?](#qué-es-pedeefe)
- [Características principales](#características-principales)
- [Capturas de pantalla](#capturas-de-pantalla)
- [Para usuarios](#para-usuarios)
- [Instalación desde fuente](#instalación-desde-fuente)
- [Requisitos del sistema](#requisitos-del-sistema)
- [Formatos soportados](#formatos-soportados)
- [Herramientas](#herramientas)
- [Endpoints](#endpoints)
- [Persistencia](#persistencia)
- [Seguridad y privacidad](#seguridad-y-privacidad)
- [Tests](#tests)
- [Lint](#lint)
- [Build (Docker)](#build-docker)
- [Estructura](#estructura)
- [Variables de entorno](#variables-de-entorno)
- [Documentación](#documentación)
- [Inicio rápido](#inicio-rápido)
- [Preguntas frecuentes (FAQ)](#preguntas-frecuentes-faq)
- [Solución de problemas (Troubleshooting)](#solución-de-problemas-troubleshooting)
- [Changelog](#changelog)
- [Roadmap](#roadmap)
- [Comparación con alternativas](#comparación-con-alternativas)
- [Agradecimientos](#agradecimientos)
- [Estadísticas del proyecto](#estadísticas-del-proyecto)
- [Contribuir](#contribuir)
- [Contacto y soporte](#contacto-y-soporte)
- [Licencia](#licencia)
- [Aviso legal](#aviso-legal)

## ¿Qué es Pedeefe?

Pedeefe es una aplicación web que reúne **22 herramientas para trabajar con
PDFs**: unir, dividir, recortar, reordenar, optimizar, comprimir, convertir,
rotar, numerar, marcar con agua, proteger y extraer texto mediante OCR.

**Todo ocurre en tu máquina.** No hay servidor público, no hay exposición de
red, no se envían archivos a ningún servicio externo y no hay base de datos.
El servidor Flask corre en `127.0.0.1:43210` por defecto (o en
`localhost:43210` si usas Docker).

### Características principales

- 📄 **22 herramientas en un solo lugar.** Organización, conversión, edición,
  optimización y seguridad.
- 🔒 **100 % local y privado.** Los archivos nunca salen del equipo; se eliminan
  al terminar la operación o tras la descarga.
- 🗜️ **Optimizar y Comprimir son cosas distintas.** *Optimizar* reescribe la
  estructura del PDF; *Comprimir* usa Ghostscript para reducir el tamaño real
  de las imágenes y muestra el porcentaje conseguido.
- 🔄 **Conversiones en ambos sentidos.** PDF ↔ Word, Excel, PowerPoint, HTML e
  imágenes, además de imágenes → PDF.
- ♿ **Accesible.** Navegación por grupos, manejo por teclado, foco visible,
  mensajes de error claros y contraste mejorado.
- 🐳 **Lista para Docker.** Imagen con Poppler, Tesseract (español),
  Ghostscript y LibreOffice incluidos.
- 🚫 **Sin cuentas ni registro.** Sin límites de uso más allá de 50 MB por
  archivo.

---

## Capturas de pantalla

Este repositorio no incluye imágenes. Puedes ver la interfaz ejecutando la app
con Docker y abriendo `http://localhost:43210`.

| Vista | Descripción |
|---|---|
| Portada | Rejilla con las 22 herramientas y navegación desplegable por grupos |
| Herramienta | Formulario de subida, opciones, resultado y descarga |
| Resultado | Enlace de descarga temporal por token UUID para conversiones largas |

### Funcionalidades

| Grupo | Qué permite |
|---|---|
| Organizar | Unir varios PDFs, dividir por páginas o rangos, conservar páginas concretas y cambiar su orden |
| Optimizar e OCR | Optimizar la estructura, comprimir con Ghostscript y extraer texto de escaneos |
| Convertir a PDF | Imágenes, Word, Excel, PowerPoint y HTML → PDF |
| Convertir desde PDF | PDF → imagen, Word, Excel, PowerPoint y HTML |
| Editar | Rotar, numerar páginas y añadir marca de agua |
| Seguridad | Proteger con contraseña y desproteger |

---

## Para usuarios

### Opción 1: Docker (recomendado)

```bash
docker compose up --build
```

Abre <http://localhost:43210>. No necesitas instalar Python ni dependencias
del sistema: todo viene en la imagen.

### Opción 2: Python en local

Requiere Python 3.12+ y las dependencias del sistema indicadas más abajo.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Abre <http://127.0.0.1:43210>.

### Requisitos mínimos

| Recurso | Mínimo |
|---|---|
| CPU | 1 núcleo (2 recomendados para OCR y conversiones Office) |
| RAM | 2 GB (OCR y PDF → Word pueden consumir más) |
| Disco | ~500 MB para dependencias + espacio para los archivos temporales |
| SO | Linux, macOS o Windows con Python; Docker en cualquier plataforma |
| Navegador | Chrome, Firefox, Edge o Safari (moderno) |
| Red | Ninguna una vez instalado |

---

## Instalación desde fuente

```bash
# Clonar el repositorio
git clone https://github.com/achrafestudios-lab/Pedeefe.git
cd Pedeefe

# Crear entorno virtual
python3 -m venv .venv

# Instalar dependencias Python
.venv/bin/python -m pip install -r requirements.txt

# Ejecutar
.venv/bin/python app.py
```

También puedes arrancar con la CLI de Flask:

```bash
.venv/bin/flask --app app run
```

> El arranque con `flask run` no activa el debug por defecto. El puerto se
> controla con la variable `PORT` (por defecto `43210`).

### Dependencias del sistema

```bash
# Ubuntu/Debian
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa ghostscript libreoffice
```

| Dependencia | Se necesita para | ¿Obligatoria? |
|---|---|---|
| Poppler (`pdftoppm`) | PDF → imagen, PDF → Word | Sí |
| Ghostscript (`gs`) | Comprimir PDF | Solo para esa herramienta |
| Tesseract (`spa`) | OCR de PDF | Solo para esa herramienta |
| LibreOffice | Convertir Office → PDF | Opcional: hay alternativa en Python para DOCX/XLSX/PPTX/HTML |

Si falta Tesseract, la tarjeta de OCR muestra *«Requiere Tesseract»*. Si
faltan Ghostscript o LibreOffice, la herramienta afectada muestra un mensaje
explicativo.

---

## Requisitos del sistema

| Componente | Versión verificada |
|---|---|
| Python (local) | 3.14.4 |
| Python (Docker) | 3.12 |
| Flask | 3.x |
| Docker Engine | Cualquier versión reciente con Compose v2 |
| Poppler | 26.01.0 |

---

## Formatos soportados

| Entrada | Salida |
|---|---|
| PDF | PDF, JPG/PNG, DOCX, XLSX, PPTX, HTML, TXT |
| JPG, PNG, BMP, TIFF | PDF |
| DOCX, DOC, HTML | PDF |
| XLSX, XLS, CSV | PDF |
| PPTX, PPT | PDF |

Límite de subida: **50 MB por archivo**. En las herramientas que reciben PDFs
se valida tanto la extensión como el contenido real del archivo.

---

## Herramientas

| Categoría | Herramientas | Ruta |
|---|---|---|
| **Organizar** | Unir, Dividir, Recortar, Reordenar | `/unir`, `/dividir`, `/recortar-pdf`, `/reordenar-pdf` |
| **Optimizar e OCR** | Optimizar, Comprimir, OCR | `/comprimir`, `/comprimir-real`, `/ocr` |
| **Convertir a PDF** | Imágenes, Word, Excel, PowerPoint, HTML | `/imagen-a-pdf`, `/word-a-pdf`, `/excel-a-pdf`, `/powerpoint-a-pdf`, `/html-a-pdf` |
| **Convertir desde PDF** | Imagen, Word, Excel, PowerPoint, HTML | `/pdf-a-imagen`, `/pdf-a-word`, `/pdf-a-excel`, `/pdf-a-powerpoint`, `/pdf-a-html` |
| **Editar** | Rotar, Numerar, Marca de agua | `/rotar`, `/numerar`, `/marcar-agua` |
| **Seguridad** | Proteger, Desproteger | `/proteger`, `/desproteger` |

Notas de uso:

- **Dividir** permite extraer páginas sueltas o un rango.
- **Recortar** conserva solo las páginas indicadas (`1-3,5,7-9`).
- **Reordenar** acepta un orden (`3,1,2`) y permite duplicar páginas (`1,1,2`).
- **Comprimir** informa del porcentaje real de reducción; si el archivo ya
  está optimizado, lo dice sin prometer una mejora.
- **OCR** depende de Tesseract con datos de idioma español.

---

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Portada con el catálogo de herramientas |
| `GET`/`POST` | `/unir` | Une varios PDFs en uno |
| `GET`/`POST` | `/dividir` | Divide o extrae un rango de páginas |
| `GET`/`POST` | `/recortar-pdf` | Conserva solo las páginas indicadas |
| `GET`/`POST` | `/reordenar-pdf` | Reordena y duplica páginas |
| `GET`/`POST` | `/comprimir` | Optimiza la estructura del PDF |
| `GET` | `/descargar_comprimido/<token>` | Descarga el PDF optimizado |
| `GET`/`POST` | `/comprimir-real` | Comprime con Ghostscript |
| `GET`/`POST` | `/pdf-a-imagen` | PDF → JPG/PNG o ZIP de imágenes |
| `GET`/`POST` | `/imagen-a-pdf` | Imágenes → PDF |
| `GET`/`POST` | `/pdf-a-word` | PDF → DOCX |
| `GET` | `/descargar_word/<token>` | Descarga el DOCX convertido |
| `GET`/`POST` | `/rotar` | Rota páginas 90°/180°/270° |
| `GET`/`POST` | `/proteger` | Añade contraseña al PDF |
| `GET`/`POST` | `/desproteger` | Quita la contraseña del PDF |
| `GET`/`POST` | `/ocr` | Extrae texto de un PDF escaneado |
| `GET`/`POST` | `/marcar-agua` | Añade marca de agua de texto |
| `GET`/`POST` | `/numerar` | Añade números de página |
| `GET`/`POST` | `/pdf-a-excel` | PDF → XLSX |
| `GET` | `/descargar_excel/<token>` | Descarga el XLSX convertido |
| `GET`/`POST` | `/pdf-a-powerpoint` | PDF → PPTX |
| `GET` | `/descargar_powerpoint/<token>` | Descarga el PPTX convertido |
| `GET`/`POST` | `/pdf-a-html` | PDF → HTML |
| `GET` | `/descargar_html/<token>` | Descarga el HTML convertido |
| `GET`/`POST` | `/word-a-pdf` | Word/HTML → PDF |
| `GET`/`POST` | `/excel-a-pdf` | Excel/CSV → PDF |
| `GET`/`POST` | `/powerpoint-a-pdf` | PowerPoint → PDF |
| `GET`/`POST` | `/html-a-pdf` | HTML → PDF |
| `GET` | `/descargar_pdf/<token>` | Descarga el PDF convertido |

Los archivos estáticos se sirven desde `/static/`.

---

## Persistencia

No hay base de datos. Los archivos se guardan en `uploads/<uuid>/` mientras se
procesan:

1. Se valida la extensión, el tamaño (≤ 50 MB) y, cuando aplica, que el PDF sea
   real.
2. Se crea una carpeta temporal con un UUID.
3. Se procesa el archivo con la librería correspondiente.
4. La respuesta inmediata se devuelve con `send_file` y la carpeta se borra en
   `finally`.
5. En las conversiones largas se entrega un token UUID y la carpeta se limpia
   tras la descarga.

Al arrancar la aplicación se limpia cualquier resto de `uploads/`. No hay
persistencia entre reinicios.

---

## Seguridad y privacidad

- La aplicación escucha en `127.0.0.1` por defecto. **No la expongas a una red
  no confiable**: no tiene autenticación, control de acceso ni protección CSRF.
- El modo debug está desactivado por defecto y solo se activa con
  `FLASK_DEBUG=1` en desarrollo local.
- Los tokens de descarga se validan como UUID y las rutas temporales se
  confinan al directorio `uploads/`.
- No se envían archivos ni telemetría a ningún servicio externo.

---

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

Incluye 140 casos (una omisión: OCR, porque Tesseract no está disponible en
este entorno):

| Fichero | Qué cubre |
|---|---|
| `tests/test_smoke.py` | Rutas GET de la aplicación y estáticos |
| `tests/test_tools.py` | Flujos completos y errores de las herramientas |
| `tests/test_fase4.py` | Conversiones añadidas en la última fase |

Comprobaciones adicionales:

```bash
.venv/bin/python -m py_compile app.py
.venv/bin/python -m pip check
```

---

## Lint

No hay linter ni formateador configurado (`ruff`, `flake8` y `black` no están
instalados). El estilo del proyecto es: 4 espacios, `snake_case`, comillas
dobles y secciones separadas con comentarios `# ─── ...`.

---

## Build (Docker)

```bash
docker compose up --build
```

La imagen `pedeefe:latest` incluye Python 3.12, Poppler, Ghostscript,
Tesseract con español y LibreOffice. El contenedor publica el puerto `43210`
y se reinicia automáticamente.

Paradetener y eliminar el contenedor:

```bash
docker compose down
```

---

## Estructura

```
app.py                  Aplicación Flask: rutas, validación y procesamiento
templates/              Plantillas Jinja2 (interfaz en español)
static/css/style.css    Estilos
static/js/main.js       Scripts compartidos
tests/                  Suite unittest (humo + herramientas + conversiones)
Dockerfile              Imagen con dependencias del sistema
docker-compose.yml      Arranque en el puerto 43210
requirements.txt        Dependencias Python
.gitignore              Ignora entornos, subidas y documentación interna
AGENTS.md               Convenciones para agentes (solo en local)
docs/                   Documentación técnica interna (no publicada)
```

---

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `PORT` | `43210` | Puerto de escucha |
| `FLASK_HOST` | `127.0.0.1` | Interfaz de escucha (en Docker, `0.0.0.0`) |
| `FLASK_DEBUG` | `0` | Activa el debugger de Werkzeug si se pone a `1` |
| `PYTHONUNBUFFERED` | `1` | Salida sin buffer en Docker |

---

## Documentación

La documentación técnica detallada (arquitectura, módulos, calidad,
verificación, cobertura, auditoría de producto y coordinación del equipo) se
mantiene **fuera del repositorio público**. En este repo solo se publica el
código, las plantillas, los tests y este `README.md`.

---

## Inicio rápido

```bash
git clone https://github.com/achrafestudios-lab/Pedeefe.git
cd Pedeefe
docker compose up --build
```

Abre <http://localhost:43210>.

---

## Preguntas frecuentes (FAQ)

**¿Por qué el puerto 43210?**
El puerto 5000 estaba ocupado por otra aplicación. Puedes cambiarlo con la
variable `PORT` si lo necesitas.

**¿Se suben mis archivos a internet?**
No. Todo se procesa en local y los archivos temporales se eliminan. La app no
tiene telemetría ni servicios externos.

**¿Necesito cuenta o pago?**
No. No hay registro, límites de uso ni marcas de agua. El único límite es de
50 MB por archivo.

**¿Por qué la tarjeta de OCR dice «Requiere Tesseract»?**
Porque el binario de Tesseract no está instalado. Instálalo con
`tesseract-ocr tesseract-ocr-spa` o usa Docker.

**¿Cuál es la diferencia entre Optimizar y Comprimir?**
Optimizar reescribe la estructura del PDF con pikepdf. Comprimir usa
Ghostscript para reducir el tamaño real de las imágenes y muestra el
porcentaje de reducción.

**¿Puedo usar la app desde el móvil?**
Sí si accedes desde la misma red, pero la app escucha en `127.0.0.1` por
defecto. No está pensada para exponerse a internet.

**¿Qué pasa si un PDF está protegido?**
Usa *Desproteger PDF* con la contraseña antes de aplicar otras operaciones.

---

## Solución de problemas (Troubleshooting)

| Error | Causa | Solución |
|---|---|---|
| `Error: Requiere Tesseract` | Falta el OCR del sistema | Instala `tesseract-ocr tesseract-ocr-spa` o usa Docker |
| «No se pudo comprimir» | Falta Ghostscript | Instala `ghostscript` o usa Docker |
| «El formato .doc necesita LibreOffice» | Formato antiguo sin soporte Python | Instala LibreOffice o guarda como `.docx` |
| `El archivo supera el límite de 50 MB` | Archivo demasiado grande | Reduce el tamaño o divide el PDF |
| `Puerto 43210 ocupado` | Otra app usa el puerto | Cambia `PORT` en el entorno |
| `No se pudo abrir http://localhost:43210` | Contenedor caído | Ejecuta `docker compose up --build` y revisa `docker compose logs` |
| Conversión sin descarga | Conversión todavía en curso | Espera al enlace de descarga por token |
| Página de error 413 | Subida mayor al límite | Selecciona un archivo más pequeño |

---

## Changelog

### v1.3 (Fase 4)
- Conversiones añadidas: PDF → Excel, PowerPoint y HTML.
- Conversiones a PDF: Word, Excel, PowerPoint y HTML.
- Descargas por token UUID para los resultados largos.
- 26 tests nuevos (140 en total).

### v1.2 (Fase 3)
- `Recortar PDF` y `Reordenar PDF`, con validación de rangos y duplicados.
- Integración en portada y navegación.
- 24 tests nuevos (114 en total).

### v1.1
- *Comprimir* real con Ghostscript y porcentaje de reducción medido.
- *Optimizar* se mantiene como herramienta independiente.
- Detección de Tesseract al arrancar y aviso en la tarjeta de OCR.
- Separación clara de *Comprimir* y *Optimizar* en portada y menú.

### v1.0
- 12 herramientas iniciales.
- Corrección de la vulnerabilidad de descarga por token (traversal).
- Subida por teclado, estados de error visibles y accesibilidad básica.
- Navegación desplegable por grupos.
- Docker y arranque en el puerto 43210.
- Suite inicial de 90 tests.

---

## Roadmap

| Versión | Objetivo | Estado |
|---|---|---|
| v1.0 | Seguridad accesibilidad y Docker | Completada |
| v1.1 | Compresión real y OCR integrado | Completada |
| v1.2 | Edición: recortar y reordenar | Completada |
| v1.3 | Conversión PDF ↔ Office/HTML | Completada |
| v1.4 | Seguridad avanzada: firmar, censurar, comparar | Planificada |
| v1.5 | Productividad: lotes, historial y plantillas | Planificada |
| v1.6 | Plataforma: escritorio, API local y accesibilidad completa | Planificada |

Línea opcional de *PDF Intelligence*: resumen con IA, traducción y exportación
a Markdown.

---

## Comparación con alternativas

| Característica | Pedeefe | Smallpdf | ILovePDF | PDF24 | qpdf |
|---|---|---|---|---|---|
| Interfaz web local | Sí | No | No | Sí (escritorio) | No (CLI) |
| Sin subir archivos | Sí | No | No | Sí (escritorio) | Sí |
| Sin cuenta | Sí | No | No | Sí | Sí |
| Código abierto | Sí | No | No | Parcial | Sí |
| Interfaz en español | Sí | Sí | Sí | Sí | No |
| Docker | Sí | No | No | No | Sí |
| Conversiones Office | Sí | Sí | Sí | Sí | No |
| 22 herramientas | Sí | Parcial | Parcial | Parcial | No |

**Diferenciador clave:** Pedeefe es una caja de herramientas PDF en español,
local y sin cuenta, con Docker listo y conversiones en ambos sentidos.

---

## Agradecimientos

Pedeefe se construye sobre proyecto open source:

- Flask — servidor web local
- pypdf y pikepdf — manipulación y optimización de PDFs
- pdf2docx y PyMuPDF — conversión PDF → Word y HTML
- pdfplumber — extracción de tablas
- python-pptx y openpyxl — PowerPoint y Excel
- WeasyPrint — HTML → PDF
- pdf2image y Pillow — imágenes
- pytesseract y Tesseract — OCR
- reportlab — marcas de agua y numeración
- Poppler, Ghostscript y LibreOffice — motor de conversión del sistema

---

## Estadísticas del proyecto

| Métrica | Valor |
|---|---|
| Herramientas | 22 |
| Rutas HTTP | 29 |
| Plantillas | 25 |
| Tests | 140 (1 omitido) |
| Líneas de `app.py` | ~2.180 |
| Dependencias Python | 14 |
| Puerto por defecto | 43210 |
| Versión actual | 1.3 |

---

## Contribuir

1. Haz un fork del repositorio.
2. Crea una rama: `git checkout -b feature/mi-mejora`.
3. Haz tus cambios respetando las convenciones del proyecto.
4. Ejecuta los tests: `.venv/bin/python -m unittest discover -s tests`.
5. Comprueba la sintaxis: `.venv/bin/python -m py_compile app.py`.
6. Commitea y haz push.
7. Abre un Pull Request.

### Convenciones

- Todo en español (UI, mensajes, comentarios y nombres de rutas).
- Helpers internos en `snake_case` y comillas dobles.
- Una ruta por herramienta, sin blueprints ni factory.
- Mensajes de error legibles para el usuario.

---

## Contacto y soporte

- Issues: <https://github.com/achrafestudios-lab/Pedeefe/issues>
- Código: <https://github.com/achrafestudios-lab/Pedeefe>

---

## Licencia

Copyright © 2026. Licencia **sin definir** en el repositorio. Si quieres
reutilizar el proyecto, consulta antes con el autor.

---

## Aviso legal

Esta herramienta procesa documentos que tú aportas. Cada usuario es
responsable de tener los derechos o la autorización necesaria sobre los
archivos que manipula. El repositorio no incluye ni distribuye documentos con
copyright. Pedeefe no está afiliado a ningún fabricante de software de PDF.
