# Pedeefe

**Tu caja de herramientas PDF, en tu máquina.**

Pedeefe es una aplicación web local que reúne **22 herramientas para trabajar
con PDFs**: unir, dividir, recortar, reordenar, comprimir, convertir, editar y
proteger documentos. La interfaz está en español, no hay cuentas de usuario y
**los archivos nunca se envían a internet**: todo se procesa en el equipo donde
se ejecuta la aplicación.

```
Local · Privado · Sin registro · Español
```

---

## Características

- **Privacidad por diseño.** Procesamiento local, sin servicios externos ni
  base de datos. Los archivos temporales se eliminan después de cada operación.
- **22 herramientas en un solo lugar.** Organización, compresión, conversión,
  edición y seguridad.
- **Dos formas de reducir un PDF.** *Optimizar* reescribe la estructura del
  archivo; *Comprimir* usa Ghostscript para reducir el tamaño real de las
  imágenes y muestra el porcentaje obtenido.
- **Conversiones en ambos sentidos.** PDF ↔ Word, Excel, PowerPoint, HTML e
  imágenes, además de imágenes → PDF.
- **Interfaz accesible.** Navegación por grupos, manejo por teclado, estados de
  foco visibles y mensajes de error claros.
- **Lista para Docker.** Una imagen con todas las dependencias del sistema y
  arranque en `localhost:43210`.

---

## Herramientas

| Categoría | Herramientas | Ruta |
|---|---|---|
| **Organizar** | Unir, Dividir, Recortar, Reordenar | `/unir`, `/dividir`, `/recortar-pdf`, `/reordenar-pdf` |
| **Optimizar e OCR** | Optimizar, Comprimir, OCR | `/comprimir`, `/comprimir-real`, `/ocr` |
| **Convertir a PDF** | Imágenes, Word, Excel, PowerPoint, HTML | `/imagen-a-pdf`, `/word-a-pdf`, `/excel-a-pdf`, `/powerpoint-a-pdf`, `/html-a-pdf` |
| **Convertir desde PDF** | Imagen, Word, Excel, PowerPoint, HTML | `/pdf-a-imagen`, `/pdf-a-word`, `/pdf-a-excel`, `/pdf-a-powerpoint`, `/pdf-a-html` |
| **Editar** | Rotar, Numerar páginas, Marca de agua | `/rotar`, `/numerar`, `/marcar-agua` |
| **Seguridad** | Proteger, Desproteger | `/proteger`, `/desproteger` |

Todas están disponibles desde la portada. El límite de subida es de **50 MB
por archivo**. En las herramientas que reciben PDFs se comprueban tanto la
extensión como el contenido real del archivo.

---

## Inicio rápido

### Con Docker (recomendado)

```bash
docker compose up --build
```

Abre <http://localhost:43210>. La imagen incluye Poppler, Tesseract (con
soporte en español), Ghostscript y LibreOffice.

### Sin Docker

Requiere **Python 3.12 o superior**. En Ubuntu/Debian, instala primero las
dependencias del sistema:

```bash
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa ghostscript libreoffice
```

Después:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Abre <http://127.0.0.1:43210>.

#### Dependencias del sistema por función

| Dependencia | Se necesita para | ¿Obligatoria? |
|---|---|---|
| Poppler (`pdftoppm`) | PDF → imagen, PDF → Word | Sí |
| Ghostscript (`gs`) | Comprimir PDF | Sí, solo para esa herramienta |
| Tesseract (`spa`) | OCR de PDF | Sí, solo para esa herramienta |
| LibreOffice | Convertir Office → PDF | Opcional: hay una alternativa en Python para DOCX/XLSX/PPTX/HTML |

Si falta Tesseract, la tarjeta de OCR indica *«Requiere Tesseract»*. Si falta
Ghostscript o LibreOffice, la herramienta afectada muestra un mensaje
explicativo en lugar de fallar de forma silenciosa.

---

## Configuración

La aplicación se configura con variables de entorno:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `PORT` | `43210` | Puerto de escucha |
| `FLASK_HOST` | `127.0.0.1` | Interfaz de escucha (en Docker, `0.0.0.0`) |
| `FLASK_DEBUG` | `0` | Activa el debugger de Werkzeug solo si se pone a `1` |

Los archivos se guardan en `uploads/<uuid>/` mientras se procesan y se borran
al terminar. No hay persistencia entre reinicios.

---

## Desarrollo y pruebas

```bash
.venv/bin/python -m py_compile app.py
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests
```

La suite tiene **140 pruebas** (una omitida: OCR, porque Tesseract no está
disponible en este entorno). No se necesita `pytest`.

### Estructura del proyecto

```
app.py                  Aplicación Flask: rutas, validación y procesamiento
templates/              Plantillas Jinja2 (interfaz en español)
static/css/style.css    Estilos
static/js/main.js       Scripts compartidos
tests/                  Suite unittest (humo + herramientas)
docs/                   Arquitectura, auditoría, cobertura, roadmap y coord.
Dockerfile              Imagen de producción local
docker-compose.yml      Arranque en el puerto 43210
requirements.txt        Dependencias Python
```

---

## Seguridad y privacidad

- La aplicación escucha en `127.0.0.1` por defecto. **No la expongas a una red
  no confiable**: no tiene autenticación, control de acceso ni protección CSRF.
- El debugger está desactivado por defecto; actívalo solo en desarrollo local.
- Las descargas usan tokens UUID validados y las rutas temporales se confinan
  al directorio `uploads/`.
- Si necesitas procesar información sensible, ejecútala con Docker en tu propio
  equipo y desactiva cualquier publicación del puerto fuera de `localhost`.

---

## Documentación

| Documento | Contenido |
|---|---|
| [Arquitectura](docs/ARCHITECTURE.md) | Estructura y flujo de las peticiones |
| [Módulos](docs/MODULES.md) | Funciones y responsabilidades |
| [Calidad](docs/QUALITY.md) | Deuda técnica y riesgos |
| [Verificación](docs/VERIFICATION.md) | Evidencia de las comprobaciones |
| [Cobertura](docs/COVERAGE.md) | Archivos y rutas cubiertos |
| [Auditoría de producto](docs/PRODUCT_AUDIT.md) | UX, accesibilidad y propuesta de valor |
| [Mejoras](docs/IMPROVEMENTS.md) | incidencias R-01…R-21 cerradas |
| [Ideas](docs/IDEAS.md) | Ideas de valor y roadmap de fases |
| [Preguntas abiertas](docs/OPEN_QUESTIONS.md) | Decisiones pendientes |
| [Coordinación del equipo](docs/team/STATUS.md) | Estado y avisos entre agentes |

El roadmap de las siguientes fases (seguridad avanzada, productividad y
plataforma) está registrado en [`docs/IDEAS.md` §9](docs/IDEAS.md).

---

## Licencia

Sin licencia declarada en el repositorio.
