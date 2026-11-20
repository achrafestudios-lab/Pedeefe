#!/usr/bin/env python3
"""CLI local de Pedeefe (v2.0).

Habla con el backend Flask ya arrancado en 127.0.0.1 mediante la API JSON
autenticada con el token local. Solo usa la biblioteca estándar.

Ejemplos:

    python cli/pedeefe.py list
    python cli/pedeefe.py unir a.pdf b.pdf -o unido.pdf
    python cli/pedeefe rotar a.pdf --angle 90 -o rotado.pdf
"""

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from local_token import get_or_create_api_token  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:43210"
STATIC_HELP = """Uso: pedeefe [--url URL] [--token TOKEN] <herramienta> [opciones]

Con el backend local en marcha, `pedeefe list` muestra las herramientas y sus
archivos de entrada. Ejemplos:

  pedeefe list
  pedeefe unir a.pdf b.pdf -o unido.pdf
  pedeefe rotar a.pdf --angle 90 -o rotado.pdf

El token se lee de ~/.pedeefe/token o de PEDEEFE_TOKEN.
"""


class CLIError(Exception):
    """Error de uso o de comunicación con el backend local."""


def _http_error(exc):
    """Convierte un HTTPError en un mensaje de la API, si lo trae."""
    payload = exc.read().decode("utf-8", "replace")
    try:
        message = json.loads(payload).get("error", payload)
    except ValueError:
        message = payload
    return CLIError(message)


def api_get(base_url, token, path):
    """Realiza una petición GET autenticada y devuelve el JSON resultante."""
    request = Request(
        base_url.rstrip("/") + path,
        headers={"Authorization": "Bearer " + token},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise _http_error(exc) from exc


def _quoted(value):
    return str(value).replace('"', "%22").replace("\r", "").replace("\n", "")


def multipart_body(fields, files):
    """Construye un cuerpo multipart/form-data con la biblioteca estándar."""
    boundary = "----PedeefeBoundary" + uuid.uuid4().hex
    chunks = []
    for name, values in fields.items():
        for value in values:
            if value is None:
                continue
            chunks.append((
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{_quoted(name)}"\r\n\r\n'
            ).encode("utf-8") + str(value).encode("utf-8") + b"\r\n")
    for name, filename in files:
        path = Path(filename)
        chunks.append((
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{_quoted(name)}"; '
            f'filename="{_quoted(path.name)}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n'
        ).encode("utf-8") + path.read_bytes() + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def api_call(base_url, token, slug, fields, files):
    """Llama a una herramienta y devuelve (headers, bytes)."""
    body, content_type = multipart_body(fields, files)
    request = Request(
        base_url.rstrip("/") + "/api/v1/tools/" + slug,
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": content_type,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return dict(response.headers.items()), response.read()
    except HTTPError as exc:
        raise _http_error(exc) from exc


def _assign_files(spec, inputs):
    """Reparte los archivos posicionales según la definición de la herramienta."""
    assigned = []
    index = 0
    for field in spec["files"]:
        if field["multiple"]:
            values = list(inputs[index:])
            index = len(inputs)
        elif index < len(inputs):
            values = [inputs[index]]
            index += 1
        else:
            values = []
        if field["required"] and not values:
            raise CLIError(
                f"Falta el archivo '{field['name']}' para {spec['label']}."
            )
        if not field["multiple"] and len(values) > 1:
            raise CLIError(f"El campo '{field['name']}' solo admite un archivo.")
        assigned.extend((field["name"], value) for value in values)
    if index < len(inputs):
        raise CLIError("Se han pasado más archivos de los que admite esta herramienta.")
    return assigned


def _build_parser(catalog, default_url=DEFAULT_URL):
    parser = argparse.ArgumentParser(
        prog="pedeefe",
        description="CLI local de Pedeefe. Requiere el backend en 127.0.0.1.",
    )
    parser.add_argument(
        "--url", default=default_url, help="URL base del backend local"
    )
    parser.add_argument("--token", default=None, help="Token local (o PEDEEFE_TOKEN)")
    subparsers = parser.add_subparsers(dest="tool", required=True)
    subparsers.add_parser("list", help="Lista las herramientas disponibles")

    for entry in catalog["tools"]:
        tool = subparsers.add_parser(entry["slug"], help=entry["label"])
        tool.add_argument(
            "inputs", nargs="*",
            help="Archivos de entrada, en el orden indicado por 'list'",
        )
        tool.add_argument("-o", "--output", help="Archivo de salida ('-' para stdout)")
        for param in entry["params"]:
            tool.add_argument(
                "--" + param.replace("_", "-"),
                dest="param_" + param,
                default=None,
                help=f"Parámetro {param}",
            )
    return parser


def _output_name(headers, slug):
    disposition = headers.get("Content-Disposition", "")
    match = re.search(r'filename="?([^";]+)"?', disposition)
    if match:
        return os.path.basename(match.group(1))
    return slug + ".bin"


def _run(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(STATIC_HELP)
        return 0

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--url", default=os.environ.get("PEDEEFE_URL", DEFAULT_URL))
    pre.add_argument("--token", default=None)
    known, _ = pre.parse_known_args(argv)
    token = known.token or get_or_create_api_token()

    try:
        catalog = api_get(known.url, token, "/api/v1/tools")
    except (OSError, URLError) as exc:
        raise CLIError(
            f"No se pudo conectar con el backend local en {known.url}. "
            "Inicia Pedeefe antes de usar el CLI."
        ) from exc

    parser = _build_parser(catalog, known.url)
    args = parser.parse_args(argv)
    if args.tool == "list":
        for entry in catalog["tools"]:
            names = ", ".join(f["name"] for f in entry["files"])
            params = ", ".join(entry["params"]) or "-"
            print(f"{entry['slug']:<20} {entry['label']:<28} archivos: {names} | opciones: {params}")
        return 0

    spec = next(item for item in catalog["tools"] if item["slug"] == args.tool)
    files = _assign_files(spec, args.inputs)
    fields = {}
    for param in spec["params"]:
        value = getattr(args, "param_" + param, None)
        if value is not None:
            fields[param] = [value]

    headers, body = api_call(args.url, token, args.tool, fields, files)
    is_file = headers.get("X-Pedeefe-Format") == "file"

    if is_file:
        destination = args.output or _output_name(headers, args.tool)
        if destination != "-" and any(
            os.path.abspath(destination) == os.path.abspath(path) for _, path in files
        ):
            raise CLIError("El archivo de salida no puede sobrescribir un archivo de entrada.")
        if destination == "-":
            sys.stdout.buffer.write(body)
        else:
            Path(destination).write_bytes(body)
            print(f"Guardado: {destination}")
        return 0

    text = body.decode("utf-8", "replace")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Guardado: {args.output}")
    else:
        try:
            print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
        except ValueError:
            print(text)
    return 0


def main(argv=None):
    try:
        return _run(list(sys.argv[1:] if argv is None else argv))
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
