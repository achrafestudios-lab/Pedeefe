"""Token local compartido entre el backend Flask y el CLI de Pedeefe (v2.0).

Solo usa la biblioteca estándar para que el CLI no tenga que importar las
dependencias pesadas de la app. El token se guarda en ``~/.pedeefe/token`` con
permisos 0600 (0700 el directorio); ``PEDEEFE_TOKEN`` lo sustituye sin escribir
nada en disco, lo que resulta útil en tests y automatizaciones.
"""

import os
import secrets

TOKEN_ENV = "PEDEEFE_TOKEN"
TOKEN_DIRECTORY = ".pedeefe"
TOKEN_FILENAME = "token"


def token_path():
    """Devuelve la ruta del archivo de token del perfil del usuario."""
    return os.path.join(os.path.expanduser("~"), TOKEN_DIRECTORY, TOKEN_FILENAME)


def get_or_create_api_token():
    """Devuelve el token local, creándolo con permisos restringidos si falta."""
    configured = os.environ.get(TOKEN_ENV, "").strip()
    if configured:
        return configured

    path = token_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read().strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    except OSError:
        # Un archivo ilegible no impide generar un token en memoria para esta
        # petición; el CLI avisará de que no puede compartirlo.
        return secrets.token_urlsafe(32)

    token = secrets.token_urlsafe(32)
    directory = os.path.dirname(path)
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
        try:
            os.chmod(path, 0o600)
            os.chmod(directory, 0o700)
        except OSError:
            pass  # Windows no expone los mismos bits de permiso.
    except OSError:
        return token
    return token
