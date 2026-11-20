"""Sidecar HTTP local para el paquete de escritorio de Pedeefe (v1.7).

Arranca la app Flask existente en 127.0.0.1 con un puerto efímero y anuncia la
URL por stdout con una línea ``PEDEE_READY http://127.0.0.1:<puerto>``. Electron
lee esa línea para abrir la ventana. No hay autenticación, TLS ni exposición a
red: el único cambio respecto a la app web es el directorio de subidas, que en
el escritorio apunta a un área escribible del usuario.

Uso en desarrollo:

    .venv/bin/python desktop/launcher.py --upload-dir /tmp/pedeefe-uploads

Dentro del paquete PyInstaller se invoca sin argumentos (Electron aporta el
directorio de subidas).
"""

import argparse
import os
import re
import signal
import socket
import sys
import threading
import time

HOST = "127.0.0.1"
READY_PATTERN = re.compile(r"^PEDEE_READY http://127\.0\.0\.1:(\d+)$")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backend local de Pedeefe Desktop")
    parser.add_argument("--host", default=HOST, help="solo se admite 127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 elige un puerto libre")
    parser.add_argument("--upload-dir", default=None, help="directorio temporal del usuario")
    return parser.parse_args(argv)


def project_root():
    """Raíz donde vive app.py, tanto en desarrollo como en el bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return bundled
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def choose_port(host=HOST):
    """Reserva un puerto efímero en loopback y lo devuelve."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def default_upload_dir():
    """Directorio de subidas por defecto cuando Electron no lo especifica."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    return os.path.join(base, "Pedeefe", "uploads")


def prepare_upload_dir(path):
    expanded = os.path.abspath(os.path.expanduser(path))
    os.makedirs(expanded, exist_ok=True)
    return expanded


def load_flask_app(upload_dir):
    """Importa app.py con el directorio de subidas ya configurado."""
    os.environ["PEDEE_UPLOAD_FOLDER"] = upload_dir
    root = project_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    import app as app_module  # noqa: WPS433 (import diferido intencionado)

    return app_module.app


def format_ready(host, port):
    return f"PEDEE_READY http://{host}:{port}"


def parse_ready(line):
    """Devuelve el puerto de una línea PEDEE_READY válida, o None."""
    match = READY_PATTERN.match(line.strip())
    return int(match.group(1)) if match else None


def parent_alive(pid):
    """Comprueba que el proceso de Electron sigue vivo (si se nos indicó)."""
    if not pid:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def watch_parent(pid, stop, interval=1.0):
    """Apaga el servidor si muere el proceso que lo arrancó."""
    while True:
        time.sleep(interval)
        if not parent_alive(pid):
            stop()
            return


def main(argv=None):
    args = parse_args(argv)
    if args.host != HOST:
        raise SystemExit("Pedeefe Desktop solo enlaza 127.0.0.1")

    upload_dir = prepare_upload_dir(args.upload_dir or default_upload_dir())
    flask_app = load_flask_app(upload_dir)

    from werkzeug.serving import make_server

    port = args.port or choose_port(HOST)
    server = make_server(HOST, port, flask_app, threaded=True)
    print(format_ready(HOST, server.server_port), flush=True)

    def stop(*_unused):
        # shutdown() debe ejecutarse fuera del hilo que sirve las peticiones.
        threading.Thread(target=server.shutdown, daemon=True).start()

    # En el paquete Electron pasamos su PID: si la ventana muere de forma
    # brusca, el bootloader de PyInstaller podría dejar este proceso huérfano.
    parent_pid = os.environ.get("PEDEE_DESKTOP_PARENT_PID", "")
    if parent_pid.isdigit() and int(parent_pid) > 0:
        threading.Thread(
            target=watch_parent,
            args=(int(parent_pid), stop),
            daemon=True,
        ).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
