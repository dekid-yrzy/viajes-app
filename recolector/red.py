"""Cliente HTTP mínimo sobre urllib que devuelve JSON."""
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ErrorRed(Exception):
    def __init__(self, mensaje: str, estado: int | None = None):
        super().__init__(mensaje)
        self.estado = estado


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 30) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    peticion = urllib.request.Request(url, headers={"User-Agent": "viajes-app/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErrorRed(f"HTTP {e.code}", estado=e.code) from e
    # OSError y HTTPException cubren cortes de conexión que urllib no envuelve en URLError
    except (OSError, http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErrorRed(str(e)) from e
