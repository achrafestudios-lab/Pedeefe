# Pedeefe — Caja de herramientas PDF local

<p align="center">
  <span style="font-size:88px">📄</span>
</p>

<p align="center">
  <strong>Manipula tus PDFs sin subirlos a ningún servidor</strong><br>
  App web local. Sin cuenta, sin nube, sin base de datos. Todo en tu máquina.
</p>

<p align="center">
  <a href="https://github.com/achrafestudios-lab/Pedeefe/actions/workflows/ci.yml">
    <img src="https://github.com/achrafestudios-lab/Pedeefe/actions/workflows/ci.yml/badge.svg?style=for-the-badge" alt="CI">
  </a>
  <a href="https://github.com/achrafestudios-lab/Pedeefe">
    <img src="https://img.shields.io/badge/repo-Pedeefe-0A7CFF?style=for-the-badge&logo=github" alt="GitHub">
  </a>
  <a href="https://github.com/achrafestudios-lab/Pedeefe">
    <img src="https://img.shields.io/github/stars/achrafestudios-lab/Pedeefe?style=for-the-badge" alt="Stars">
  </a>
  <a href="https://github.com/achrafestudios-lab/Pedeefe/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/licencia-MIT%20%2B%20Commons%20Clause-blue?style=for-the-badge" alt="Licencia">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/docker-listo-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/escritorio-multiplataforma-6B4EFF?style=for-the-badge&logo=electron&logoColor=white" alt="Escritorio">
  <img src="https://img.shields.io/badge/tests-248%20passed-brightgreen?style=for-the-badge" alt="Tests">
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
  - [App de escritorio (v1.9)](#opción-3-app-de-escritorio-v19)
  - [PWA instalable (v1.9)](#opción-4-pwa-instalable-v19)
  - [API y CLI local (v2.0)](#opción-5-api-y-cli-local-v20)
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

Pedeefe es una aplicación web que reúne **29 herramientas para trabajar con
PDFs**: unir, dividir, recortar, reordenar, optimizar, comprimir, convertir,
rotar, numerar, marcar con agua, proteger, firmar, censurar, comparar, extraer
texto mediante OCR y ahorrar tiempo con lotes, historial local y plantillas.

**Todo ocurre en tu máquina.** No hay servidor público, no hay exposición de
red, no se envían archivos a ningún servicio externo y no hay base de datos.
El servidor Flask corre en `127.0.0.1:43210` por defecto (o en
`localhost:43210` si usas Docker).

### Características principales

- 📄 **29 herramientas en un solo lugar.** Organización, conversión, edición,
  optimización, seguridad, análisis y productividad.
- 🔒 **100 % local y privado.** Los archivos nunca salen del equipo; se eliminan
  al terminar la operación o tras la descarga.
- 🗜️ **Optimizar y Comprimir son cosas distintas.** *Optimizar* reescribe la
  estructura del PDF; *Comprimir* usa Ghostscript para reducir el tamaño real
  de las imágenes y muestra el porcentaje conseguido.
- 🔄 **Conversiones en ambos sentidos.** PDF ↔ Word, Excel, PowerPoint, HTML e
  imágenes, además de imágenes → PDF.
- ✍️ **Firma, censura y comparación.** Firma criptográfica con certificado
  PKCS#12, borrado real de texto y diferencias página a página.
- ♿ **Accesible y con tema oscuro.** Navegación por grupos, manejo por teclado,
  foco visible, enlace «Saltar al contenido principal», mensajes anunciados a
  lectores de pantalla y contraste AA. El tema oscuro sigue la preferencia del
  sistema, sin interruptor ni datos guardados.
- 🖥️ **App de escritorio (v1.9).** Una ventana local con el mismo backend para
  Linux, Windows y macOS; sin navegador visible, puertos fijos ni servicios de
  red nuevos.
- 📲 **PWA instalable (v1.9).** Instala la web como una app más en tu equipo desde
  `127.0.0.1` o `localhost`. Guarda solo la cáscara para abrirla sin servidor;
  las herramientas siguen necesitando el backend local.
- 🤖 **API y CLI local (v2.0).** Automatiza 27 herramientas de procesamiento desde
  scripts o la terminal, sobre el mismo backend de `127.0.0.1` y con un token
  local. No abre otro puerto ni duplica la lógica de PDF.
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
| Portada | Rejilla con las 29 herramientas y navegación desplegable por grupos |
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
| Productividad | Lotes con ZIP, historial local y plantillas reutilizables |

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

### Opción 3: App de escritorio (v1.9)

La ventana de escritorio usa el mismo backend Flask en `127.0.0.1`, pero con un
puerto efímero y un directorio de temporales propio dentro del perfil de la
aplicación. No hay navegador visible, cuenta, telemetría ni llamadas externas.
Hay instaladores para **Linux, Windows y macOS**; ninguno expone la app a la red.
Descárgalos desde la [pestaña Releases](https://github.com/achrafestudios-lab/Pedeefe/releases/latest) (`2.1.0`).

| Sistema | Artefacto |
|---|---|
| Linux | `Pedeefe-2.1.0-linux-x86_64.AppImage` |
| Windows | `Pedeefe-2.1.0-win-x64.exe` (NSIS) |
| macOS | `Pedeefe-2.1.0-mac-x64.dmg` / `Pedeefe-2.1.0-mac-arm64.dmg` (y `.zip`) |

Los binarios no están firmados: Windows puede mostrar SmartScreen y macOS
Gatekeeper puede pedir abrir la app desde «Privacidad y seguridad». Las
dependencias del sistema no se empaquetan; consulta la tabla de más abajo.

Para construirla desde el repo necesitas Node.js 22+ y Python 3.12+:

```bash
cd desktop
npm ci
../.venv/bin/python -m pip install pyinstaller==6.22.3
../.venv/bin/python -m PyInstaller --noconfirm --clean \
  --distpath backend-dist --workpath build pedeefe-backend.spec
npm run dist:linux   # o dist:win / dist:mac
```

PyInstaller no puede cruzar plataforma: los tres instaladores se generan en
runners nativos mediante `.github/workflows/desktop.yml` (tags `v*`). Los
artefactos quedan en `desktop/dist/`, se publican en la
[pestaña Releases](https://github.com/achrafestudios-lab/Pedeefe/releases/latest)
y también permanecen temporalmente en Actions.

En Linux, si el sistema no tiene FUSE (`libfuse.so.2`), usa el modo de
extracción integrado:

```bash
cd desktop
APPIMAGE_EXTRACT_AND_RUN=1 ./dist/Pedeefe-2.1.0-linux-x86_64.AppImage
```

Para probar sin empaquetar, ejecuta `npm start` desde `desktop/` (usa el `.venv`
del repo). PyInstaller es una herramienta de compilación: no se añade a
`requirements.txt` ni se necesita para la app web o Docker.

### Opción 4: PWA instalable (v1.9)

Con la app web abierta en Chrome, Edge u otro navegador compatible, usa el menú
«Instalar aplicación» del navegador. La PWA comparte el backend con la web: no
abre otro puerto, no crea cuentas y no envía datos a internet.

- **Contexto seguro:** el registro del service worker solo ocurre en
  `127.0.0.1`, `localhost` o HTTPS, y se omite dentro de Electron.
- **Offline limitado:** el service worker guarda la portada, los estilos, los
  scripts, el manifiesto y los iconos. Si el servidor local no responde, se
  muestra una página de aviso con un botón para reintentar.
- **Sin archivos ni contraseñas en caché:** no se interceptan subidas ni las
  descargas por token. Las páginas de herramientas siempre se piden a la red.
- Los iconos y el manifiesto viven en `static/`; el service worker se sirve en
  `/sw.js` y el manifiesto en `/manifest.webmanifest`.

### Opción 5: API y CLI local (v2.0)

Con el backend local en marcha (web, Docker o escritorio) puedes automatizar el
procesamiento desde un script o la terminal. La API comparte el servidor de
`127.0.0.1:43210`: **no abre un puerto nuevo** y reutiliza los mismos handlers
que la interfaz, así que no hay dos implementaciones que puedan divergir.

El acceso exige un token local. Se crea automáticamente en `~/.pedeefe/token`
(permisos `0600`, directorio `0700`) y se envía como `Authorization: Bearer`.
Para automatizaciones también puedes definir `PEDEEFE_TOKEN` con el mismo valor
en el backend y en el cliente, sin escribir nada en el perfil.

```bash
# CLI: catálogo y dos ejemplos
.venv/bin/python cli/pedeefe.py list
.venv/bin/python cli/pedeefe.py unir a.pdf b.pdf -o unido.pdf
.venv/bin/python cli/pedeefe.py rotar a.pdf --angle 90 -o rotado.pdf

# API: catálogo y una unión
TOKEN=$(cat ~/.pedeefe/token)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:43210/api/v1/tools
curl -H "Authorization: Bearer $TOKEN" \
  -F 'files=@a.pdf' -F 'files=@b.pdf' \
  http://127.0.0.1:43210/api/v1/tools/unir -o unido.pdf
```

- `GET /api/v1/tools` devuelve las **26 herramientas de procesamiento**, con sus
  campos de archivo y parámetros. «Historial» y «Plantillas» no aparecen: viven
  solo en el navegador.
- `POST /api/v1/tools/<slug>` devuelve el archivo resultante (`Content-Disposition`
  con su nombre) o un JSON cuando la herramienta produce una página de texto,
  como ocurre en «Comparar». Los errores de formulario son JSON con `ok: false`.
- `pedeefe list` muestra los nombres de archivo y las opciones de cada
  herramienta; `-o -` envía el resultado a stdout. El CLI usa solo la biblioteca
  estándar de Python.
- Los temporales siguen siendo efímeros y se borran tras la respuesta, igual que
  en la web. Ningún archivo, contraseña ni resultado se guarda en la API.
- La API escucha solo en loopback y exige el token: no sustituye a las
  recomendaciones de red de la sección «Seguridad y privacidad».

### Requisitos mínimos

| Recurso | Mínimo |
|---|---|
| CPU | 1 núcleo (2 recomendados para OCR y conversiones Office) |
| RAM | 2 GB (OCR y PDF → Word pueden consumir más) |
| Disco | ~500 MB para dependencias + espacio para los archivos temporales |
| SO | Linux, macOS o Windows con Python; Docker en cualquier plataforma; instaladores de escritorio para Linux, Windows y macOS |
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

Los paquetes de escritorio no incluyen estos motores. La portada muestra un
panel «Dependencias del sistema» con lo que está disponible y cómo instalar lo
que falte.

| Sistema | Comando o fuente |
|---|---|
| Ubuntu/Debian | `sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa ghostscript libreoffice` |
| macOS (Homebrew) | `brew install poppler ghostscript tesseract tesseract-lang` y `brew install --cask libreoffice` |
| Windows | Instala Poppler for Windows (añade su carpeta `bin` al PATH), Ghostscript, Tesseract OCR con datos en español y LibreOffice |

| Dependencia | Se necesita para | ¿Obligatoria? |
|---|---|---|
| Poppler (`pdftoppm`) | PDF → imagen, PDF → Word | Sí, para esas herramientas |
| Ghostscript (`gs`) | Comprimir PDF | Solo para esa herramienta |
| Tesseract (`spa`) | OCR de PDF | Solo para esa herramienta |
| LibreOffice | Convertir Office → PDF | Opcional: hay alternativa en Python para DOCX/XLSX/PPTX/HTML |

Si falta Tesseract, la tarjeta de OCR y el panel lo avisan. Si faltan Poppler,
Ghostscript o LibreOffice, la herramienta afectada muestra un mensaje con la
instrucción de instalación correspondiente a tu sistema.

---

## Requisitos del sistema

| Componente | Versión verificada |
|---|---|
| Python (local) | 3.14.4 |
| Python (Docker) | 3.12 |
| Flask | 3.x |
| Docker Engine | Cualquier versión reciente con Compose v2 |
| Escritorio | Electron 45 + backend PyInstaller 6.22.3 (Linux, Windows y macOS) |
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
| **Avanzadas** | Firmar, Censurar, Comparar | `/firmar`, `/censurar`, `/comparar` |
| **Productividad** | Lotes, Historial local, Plantillas | `/lotes`, `/historial`, `/plantillas` |

Notas de uso:

- **Firmar** usa tu certificado PKCS#12 (.p12/.pfx) y genera una firma real
  (`/ByteRange` + `/Sig`) con pyHanko. El certificado no se guarda.
- **Censurar** elimina el texto coincidente del PDF; no se limita a taparlo.
  Escribe un término por línea (también admite comas y punto y coma).
- **Comparar** muestra las diferencias de texto página a página. En documentos
  de más de 100 páginas solo se comparan las primeras 100.
- **Dividir** permite extraer páginas sueltas o un rango.
- **Recortar** conserva solo las páginas indicadas (`1-3,5,7-9`).
- **Reordenar** acepta un orden (`3,1,2`) y permite duplicar páginas (`1,1,2`).
- **Comprimir** informa del porcentaje real de reducción; si el archivo ya
  está optimizado, lo dice sin prometer una mejora.
- **OCR** depende de Tesseract con datos de idioma español.
- **Lotes** aplica una misma operación (rotar, optimizar, proteger, desproteger,
  marcar con agua o numerar) a varios PDFs y devuelve un ZIP. Límites por petición:
  10 archivos, 200 páginas en total y 50 MB. No incluye firma ni OCR.
- **Historial** y **Plantillas** funcionan solo en el navegador: el historial
  registra los últimos envíos (metadatos y opciones, nunca archivos, contenido
  ni contraseñas) y caduca a los 30 días; las plantillas guardan solo opciones
  durante 90 días. Ambos se pueden borrar en cualquier momento.

---

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Portada con el catálogo de herramientas |
| `GET` | `/manifest.webmanifest` | Manifiesto de la PWA (MIME `application/manifest+json`) |
| `GET` | `/sw.js` | Service worker de la PWA (ámbito `/`, sin caché) |
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
| `GET`/`POST` | `/pdf-a-markdown` | PDF → Markdown (.md) |
| `GET`/`POST` | `/word-a-pdf` | Word/HTML → PDF |
| `GET`/`POST` | `/excel-a-pdf` | Excel/CSV → PDF |
| `GET`/`POST` | `/powerpoint-a-pdf` | PowerPoint → PDF |
| `GET`/`POST` | `/html-a-pdf` | HTML → PDF |
| `GET` | `/descargar_pdf/<token>` | Descarga el PDF convertido |
| `GET`/`POST` | `/firmar` | Firma el PDF con un certificado PKCS#12 |
| `GET`/`POST` | `/censurar` | Elimina términos del texto del PDF |
| `GET`/`POST` | `/comparar` | Muestra diferencias de texto entre dos PDFs |
| `GET`/`POST` | `/lotes` | Aplica una operación a varios PDFs y devuelve un ZIP |
| `GET` | `/historial` | Historial local (solo en el navegador) |
| `GET` | `/plantillas` | Plantillas reutilizables (solo en el navegador) |
| `GET` | `/api/v1/tools` | Catálogo de la API local (requiere token) |
| `POST` | `/api/v1/tools/<slug>` | Ejecuta una herramienta y devuelve archivo o JSON (requiere token) |

Los archivos estáticos se sirven desde `/static/`. En total son **40 rutas de
aplicación**; `url_map` registra 41 porque Flask añade la regla de `/static/`.

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

**Historial y plantillas (v1.5):** viven en `localStorage` del navegador, nunca
en el servidor. El historial guarda como máximo 50 entradas durante 30 días y
las plantillas 20 entradas durante 90 días; al cargar la página se descartan las
caducadas. Solo se almacenan el nombre de la herramienta, nombres de archivo y
las opciones del formulario. Nunca se guardan los PDF, su contenido ni
contraseñas; para volver a procesar un archivo hay que seleccionarlo de nuevo.
Ambas vistas ofrecen borrar una entrada o todo el conjunto.

---

## Seguridad y privacidad

- La aplicación escucha en `127.0.0.1` por defecto. **No la expongas a una red
  no confiable**: no tiene autenticación, control de acceso ni protección CSRF.
- El modo debug está desactivado por defecto y solo se activa con
  `FLASK_DEBUG=1` en desarrollo local.
- Los tokens de descarga se validan como UUID y las rutas temporales se
  confinan al directorio `uploads/`.
- No se envían archivos ni telemetría a ningún servicio externo.
- Los lotes están acotados a 10 archivos, 200 páginas y 50 MB por petición para
  limitar CPU/RAM; los PDF cifrados se rechazan salvo en la operación
  «Desproteger», que usa la contraseña solo durante la petición.
- El historial y las plantillas se guardan en el navegador, sin cookies ni
  identificadores de usuario, y nunca incluyen contraseñas.
- La API local (v2.0) exige un token `Bearer` guardado en `~/.pedeefe/token` con
  permisos `0600` (o pasado con `PEDEEFE_TOKEN`). No hay auth web, CSRF ni
  rate limiting, así que la app sigue escuchando solo en `127.0.0.1`: no la
  expongas a una red no confiable ni publiques el token.

---

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

Incluye 258 casos (una omisión: OCR, porque Tesseract no está disponible en
este entorno local; en Docker se ejecuta y comprueba el texto extraído):

| Fichero | Qué cubre |
|---|---|
| `tests/test_smoke.py` | Rutas GET de la aplicación y estáticos |
| `tests/test_tools.py` | Flujos completos y errores de las herramientas |
| `tests/test_fase4.py` | Conversiones a y desde Office/HTML |
| `tests/test_fase5.py` | Firma real, censura y comparación de texto |
| `tests/test_fase6.py` | Lotes con ZIP, límites, errores y páginas de productividad |
| `tests/test_a11y.py` | Accesibilidad, tema oscuro y regresiones de contraste |
| `tests/test_desktop.py` | Sidecar local, compatibilidad multiplataforma y targets del empaquetado |
| `tests/test_dependencies.py` | Detección de motores externos y panel de la portada |
| `tests/test_pwa.py` | Manifiesto, iconos, service worker y registro seguro |
| `tests/test_api.py` | Token local, catálogo, ejecución de handlers y descargas por token desde la API |
| `tests/test_cli.py` | Catálogo, reparto de archivos, parámetros, salida y errores del CLI |
| `tests/test_hardening.py` | Temporales `0700`, limpieza con PDFs corruptos y descarga diferida |
| `tests/test_markdown.py` | PDF → Markdown: texto extraído, errores y limpieza del temporal |

Comprobaciones adicionales:

```bash
.venv/bin/python -m py_compile app.py local_token.py cli/pedeefe.py desktop/launcher.py
.venv/bin/python -m pip check
```

Estas mismas comprobaciones se ejecutan automáticamente en
[GitHub Actions](https://github.com/achrafestudios-lab/Pedeefe/actions/workflows/ci.yml)
en cada push y Pull Request a `main`.

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
app.py                  Aplicación Flask: rutas, validación, procesamiento y API
local_token.py          Token local compartido por backend y CLI (v2.0)
cli/pedeefe.py          CLI local sobre la API JSON (v2.0)
templates/              Plantillas Jinja2 (interfaz en español)
static/css/style.css    Estilos con tokens claros/oscuros (v1.6)
static/js/main.js       Scripts compartidos (drop zone, navbar, submit)
static/js/productivity.js  Historial y plantillas en localStorage (v1.5)
static/js/sw.js         Service worker de la PWA (v1.9)
static/manifest.json    Manifiesto de instalación (v1.9)
static/offline.html     Página de aviso sin servidor local (v1.9)
static/icons/           Iconos PNG de la PWA (v1.9)
tests/                  Suite unittest (humo, herramientas, conversiones, v1.4–v2.0)
desktop/                Cáscara Electron, sidecar Flask y spec de PyInstaller (v2.0)
.github/workflows/desktop.yml  Build multiplataforma de los instaladores
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
| `PEDEE_UPLOAD_FOLDER` | `uploads/` del repo | Directorio de temporales (lo fija el escritorio) |
| `PEDEEFE_TOKEN` | `~/.pedeefe/token` | Token de la API local; debe coincidir en backend y CLI (v2.0) |
| `PEDEEFE_URL` | `http://127.0.0.1:43210` | URL base que usa el CLI (v2.0) |

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
No está pensada para exponerse a internet: la app escucha en `127.0.0.1` por
defecto y no ofrece acceso por red local.

**¿La app de escritorio abre un puerto?**
Sí, pero solo en `127.0.0.1` y con un puerto efímero elegido al arrancar. No es
accesible desde otros equipos y se cierra al salir de la aplicación.

**¿La PWA funciona sin el servidor local?**
No. La PWA guarda solo la interfaz para abrirla y mostrar un aviso si el backend
no está en marcha. Los PDF se procesan siempre en local con Flask.

**¿Puedo automatizar Pedeefe desde un script?**
Sí. Con el backend en marcha, usa `python cli/pedeefe.py list` para ver las 27
herramientas disponibles y la API `POST /api/v1/tools/<slug>` desde cualquier
lenguaje. Todo sigue en `127.0.0.1` y con el mismo token local.

**¿Dónde se guarda el token de la API?**
En `~/.pedeefe/token`, con permisos restringidos. Si prefieres no crear ese
archivo, define `PEDEEFE_TOKEN` antes de arrancar el backend y pasa el mismo
valor al CLI. No compartas el token ni expongas la API fuera de tu equipo.

**¿Qué pasa si un PDF está protegido?**
Usa *Desproteger PDF* con la contraseña antes de aplicar otras operaciones.

---

## Solución de problemas (Troubleshooting)

| Error | Causa | Solución |
|---|---|---|
| `Error: Requiere Tesseract` | Falta el OCR del sistema | Instala `tesseract-ocr tesseract-ocr-spa` o usa Docker |
| Panel «Dependencias del sistema» en ámbar | Falta un motor externo | Sigue la pista del panel o usa Docker |
| Windows muestra SmartScreen | El instalador no está firmado | Verifica el origen del artefacto; si confías en él, elige «Más información» → «Ejecutar de todos modos» |
| macOS no abre la app | No está notarizada | Verifica el origen y permite la app en «Privacidad y seguridad» (o usa el `.zip`) |
| «No se pudo comprimir» | Falta Ghostscript | Instala `ghostscript` o usa Docker |
| «El formato .doc necesita LibreOffice» | Formato antiguo sin soporte Python | Instala LibreOffice o guarda como `.docx` |
| `El archivo supera el límite de 50 MB` | Archivo demasiado grande | Reduce el tamaño o divide el PDF |
| `Puerto 43210 ocupado` | Otra app usa el puerto | Cambia `PORT` en el entorno |
| `No se pudo abrir http://localhost:43210` | Contenedor caído | Ejecuta `docker compose up --build` y revisa `docker compose logs` |
| Conversión sin descarga | Conversión todavía en curso | Espera al enlace de descarga por token |
| Página de error 413 | Subida mayor al límite | Selecciona un archivo más pequeño |
| El navegador no ofrece «Instalar aplicación» | Contexto no seguro o navegador sin soporte | Abre `127.0.0.1`/`localhost` (o HTTPS) en Chrome/Edge; desde una IP de LAN la PWA no se registra |
| La PWA muestra «no está disponible» | El servidor Flask local no está en marcha | Inicia la app web y pulsa «Reintentar» |
| CLI: `Token de API local no válido` | El token del CLI no coincide con el del backend | Usa el mismo `PEDEEFE_TOKEN` en ambos o el archivo `~/.pedeefe/token` |
| CLI: `No se pudo conectar con el backend local` | La app no está arrancada o `PEDEEFE_URL` es incorrecto | Inicia Pedeefe y comprueba la URL (por defecto `http://127.0.0.1:43210`) |
| API: `401` con el token correcto | El backend se arrancó con otro `PEDEEFE_TOKEN` | Reinicia el backend con el mismo valor que usa el cliente |

---

## Changelog

### Sin publicar (después de v2.1.0)

- **PDF a Markdown:** nueva herramienta en «Convertir desde PDF» que extrae el
  texto de cada página con `pypdf` y descarga un `convertido.md` editable, sin
  dependencias nuevas ni servicios externos. También disponible en la API local
  como `pdf-a-markdown`. 6 tests nuevos (258 en total). Aún sin tag ni release.

### v2.1.0 (rediseño visual)

- **Interfaz nueva:** cabecera fija de 60 px, mega-menú de siete columnas, hero
  centrado, filtro por categorías y rejilla de tarjetas, inspirada en la
  plantilla de referencia pero con marca Pedeefe.
- **Sin servicios externos:** 28 iconos SVG y fondo locales, sin fuentes Graphik,
  analytics ni consent manager; cero peticiones a terceros.
- **PWA y accesibilidad:** caché `pedeefe-v2.3-ui` ampliada con los assets nuevos
  y Lighthouse 1,00 en `/` y `/unir`, también en modo oscuro.
- Los instaladores de escritorio se regeneran como `2.1.0`.

### v2.0.1 (consolidación y hardening)

- **Carpetas temporales privadas:** todas las peticiones crean su directorio
  `uploads/<uuid4>/` con modo `0700` mediante un helper compartido.
- **Limpieza de temporales reforzada:** nueve rutas de descarga diferida
  conservan la carpeta solo mientras el token sigue vivo; cualquier error
  (incluidos PDFs corruptos) limpia antes de devolver la respuesta.
- **Validación OOXML:** los DOCX/XLSX/PPTX corruptos se rechazan antes de
  llamar a LibreOffice, evitando conversiones vacías silenciosas.
- **OCR cubierto en Docker:** el test de `/ocr` se omite solo si falta
  Tesseract; con la imagen Docker (español incluido) se ejecuta y verifica.
- **CI sin aviso de Node 20:** las acciones de GitHub se actualizan a `@v7`
  (Node 24). Sin dependencias Python nuevas ni cambios de funcionalidad.
- **4 tests nuevos** (252 en total) y verificación real de U1 (9 tokens de
  traversal rechazados por un servidor WSGI), U3 (PDF de 46,4 MiB en 0,3 s),
  PWA en navegador (SW activo, caché solo de cáscara, Lighthouse 1,00).
  Los instaladores de escritorio se regeneran como `2.0.1`.

### v2.0 (API y CLI local)

- **API JSON local** en `GET /api/v1/tools` y `POST /api/v1/tools/<slug>`, sobre
  el mismo servidor Flask de `127.0.0.1`: sin puertos nuevos y sin duplicar la
  lógica de los handlers web. Catálogo de 26 herramientas de procesamiento;
  «Historial» y «Plantillas» siguen siendo solo del navegador.
- **Token local `0600`** en `~/.pedeefe/token`, con `PEDEEFE_TOKEN` como
  alternativa para tests y automatizaciones. La API devuelve el archivo
  resultante o JSON y sigue las descargas por token sin dejar temporales.
- **CLI local** (`cli/pedeefe.py`) con `list` y un subcomando por herramienta,
  multipart con la biblioteca estándar, salida a archivo o stdout y errores en
  stderr. Sin dependencias Python nuevas.
- **25 tests nuevos** (248 en total): autenticación, catálogo, ejecución y
  descargas de la API; catálogo, reparto de archivos y salida del CLI. Los
  instaladores de escritorio se regeneraron como `2.0.0`.

### v1.9 (PWA instalable)

- **PWA instalable** desde `127.0.0.1`/`localhost` con manifiesto, iconos PNG y
  service worker. El registro se omite en Electron y en contextos no seguros.
- **Offline acotado:** el service worker guarda solo la cáscara (portada, CSS,
  JS, iconos y manifiesto) y muestra una página de aviso si falta el servidor.
  Nunca cachea subidas, descargas por token ni páginas de herramientas.
- **Manifiesto con MIME correcto** en `/manifest.webmanifest` y service worker
  en `/sw.js` con `Service-Worker-Allowed: /`. Sin dependencias nuevas.
- 10 tests nuevos (223 en total): manifiesto, iconos, service worker y registro.
  Los instaladores de escritorio se regeneran como `1.9.0`.

### v1.8 (escritorio multiplataforma)

- **Instaladores para Windows y macOS** junto al AppImage de Linux: NSIS
  (`.exe`), DMG/ZIP para x64 y ARM, todos generados en runners nativos desde
  `.github/workflows/desktop.yml` al publicar un tag `v*`.
- **Monitor de PID portable**: el sidecar comprueba el proceso padre con la API
  de Windows cuando `os.kill(pid, 0)` no está disponible, y aísla los temporales
  en `Application Support` en macOS.
- **Detección de dependencias**: la portada muestra el estado de Poppler,
  Ghostscript, Tesseract y LibreOffice con instrucciones de instalación para
  Linux, macOS y Windows. Los mensajes de error usan la misma pista.
- **Sin firma de código**: Windows SmartScreen y macOS Gatekeeper pueden avisar
  al abrir la app. La API/CLI local y la PWA siguen diferidas; el backend sigue
  enlazando solo `127.0.0.1`.
- 10 tests nuevos (213 en total): compatibilidad del sidecar, targets de
  electron-builder y detección de dependencias.

### v1.7 (app de escritorio)

- **App de escritorio para Linux** con Electron y un backend Flask empaquetado
  con PyInstaller. La ventana abre el mismo backend en `127.0.0.1` con un puerto
  efímero, sin navegador visible ni servicios de red nuevos.
- **Aislamiento de temporales:** `PEDEE_UPLOAD_FOLDER` permite al paquete usar un
  directorio propio del perfil de la aplicación; la app web y Docker conservan
  `uploads/`.
- **Cáscara endurecida:** sin NodeIntegration, con `contextIsolation` y
  `sandbox`, navegación externa bloqueada y backend detenido al cerrar.
- **Entregable:** AppImage en `desktop/dist/`. Windows y macOS quedan para una
  versión posterior; la API local y la PWA siguen diferidas.
- 6 tests nuevos del sidecar (203 en total), incluido el apagado del backend si
  la ventana desaparece de forma brusca.

### v1.6 (accesibilidad y tema oscuro)
- **Tema oscuro** automático según la preferencia del sistema
  (`prefers-color-scheme`), implementado con tokens CSS y contraste AA verificado
  en tema claro y oscuro. Lighthouse accesibilidad **1,00** en las páginas
  auditadas, también en modo oscuro.
- **Accesibilidad:** enlace «Saltar al contenido principal», foco visible con
  anillo de contraste, región de anuncios para los cambios de historial y
  plantillas, etiqueta en el editor HTML y emojis de encabezado ocultos a
  lectores de pantalla.
- Sin dependencias nuevas ni superficie de red adicional: la app sigue escuchando
  solo en `127.0.0.1`. 14 tests nuevos (197 en total).

### v1.5 (Fase 6)
- **Lotes PDF**: una misma operación sobre varios PDF con descarga en ZIP.
  Operaciones: rotar, optimizar, proteger, desproteger, marcar con agua y numerar.
- **Límites explícitos** de 10 archivos, 200 páginas y 50 MB por lote, con
  mensajes de error legibles y limpieza de temporales.
- **Historial local**: últimas 50 operaciones durante 30 días, con búsqueda,
  reutilización de opciones y borrado.
- **Plantillas reutilizables**: hasta 20 conjuntos de opciones durante 90 días,
  aplicables con un clic desde cualquier herramienta.
- Todo el estado vive en `localStorage`: sin servidor que guarde archivos,
  contraseñas ni contenido. 28 tests nuevos (183 en total).

### v1.4 (Fase 5)
- **Firmar PDF**: firma criptográfica con certificado PKCS#12 mediante pyHanko.
- **Censurar PDF**: borrado real de palabras o frases en todas las páginas.
- **Comparar PDF**: diferencias de texto resaltadas página a página.
- Las tres herramientas se añaden a la portada, al menú «Avanzadas» y al
  desplegable «Todas las herramientas»; las conversiones ya existentes también
  quedan enlazadas en la navegación.
- 15 tests nuevos (155 en total).

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
| v1.4 | Seguridad avanzada: firmar, censurar, comparar | Completada |
| v1.5 | Productividad: lotes, historial y plantillas | Completada |
| v1.6 | Accesibilidad WCAG 2.1 AA y tema oscuro | Completada |
| v1.7 | Plataforma: app de escritorio (Linux) | Completada |
| v1.8 | Windows y macOS del escritorio | Completada |
| v1.9 | PWA instalable | Completada |
| v2.0 | API y CLI local | Completada |
| v2.0.1 | Consolidación y hardening | Completada |
| v2.1.0 | Rediseño visual con marca Pedeefe | Completada |

v2.0 añade una API JSON y un CLI para automatizar las herramientas desde el
propio equipo, con token local y sin abrir puertos ni guardar archivos. Línea
opcional de *PDF Intelligence*: resumen con IA y traducción. La exportación a
Markdown ya está disponible con `pypdf`, sin dependencias nuevas.

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
| API/CLI local | Sí | No | No | No | Sí |
| 29 herramientas | Sí | Parcial | Parcial | Parcial | No |

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
| Herramientas web | 29 (27 expuestas en la API local) |
| Rutas HTTP | 40 de aplicación (41 reglas en `url_map`) |
| Plantillas Jinja2 | 32 |
| Tests | 258 (1 omitido en local) |
| Líneas de `app.py` | ~3.200 |
| Dependencias Python | 15 (sin cambios en v2.0) |
| Puerto por defecto | 43210 (web) / efímero (escritorio) |
| Plataformas de escritorio | Linux, Windows y macOS |
| PWA | Instalable en contextos seguros, sin caché de archivos |
| API/CLI | Local, solo loopback, con token `0600` |
| Versión actual | 2.1.0 |

---

## Contribuir

1. Haz un fork del repositorio.
2. Crea una rama: `git checkout -b feature/mi-mejora`.
3. Haz tus cambios respetando las convenciones del proyecto.
4. Ejecuta los tests: `.venv/bin/python -m unittest discover -s tests`.
5. Comprueba la sintaxis:
   `.venv/bin/python -m py_compile app.py local_token.py cli/pedeefe.py`.
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

Copyright © 2026 **ach.dev**. Pedeefe se distribuye bajo la
[licencia MIT](https://opensource.org/license/mit) con la
[Commons Clause v1.0](https://commonsclause.com/) añadida; el texto completo
está en [`LICENSE`](LICENSE).

En resumen:

| Permite | Condiciones |
|---|---|
| Usar la app gratis | Incluir el aviso de copyright y la licencia en las copias |
| Modificar y adaptar el código | Conservar el texto de la licencia y el Commons Clause |
| Compartir, distribuir e integrar | No vender el software ni un producto cuyo valor derive sustancialmente de él |

El Commons Clause limita la concesión de derechos de la MIT: no autoriza
**vender Pedeefe** ni ofrecer como pago un producto o servicio cuyo valor
proceda sobre todo de esta app (incluye hosting, consultoría o soporte ligados a
ella). Sí se permiten trabajos con valor añadido propio, como integraciones o
herramientas separadas.

Atribución: *Pedeefe — por ach.dev*. Si modificas el proyecto, indica los
cambios respecto del original en el historial o en tu distribución.

---

## Aviso legal

Esta herramienta procesa documentos que tú aportas. Cada usuario es
responsable de tener los derechos o la autorización necesaria sobre los
archivos que manipula. El repositorio no incluye ni distribuye documentos con
copyright. Pedeefe no está afiliado a ningún fabricante de software de PDF.
